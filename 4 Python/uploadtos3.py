#!/usr/bin/env python3
import argparse
import logging
import os
import sys
import threading
from datetime import datetime
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('upload.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class S3Uploader:
    def __init__(self, profile_name=None):
        """Initialize S3 client with optional profile"""
        import boto3
        if profile_name:
            session = boto3.Session(profile_name=profile_name)
            self.s3_client = session.client('s3')
        else:
            self.s3_client = boto3.client('s3')
        
        self.multipart_threshold = 100 * 1024 * 1024  # 100MB

    def get_file_size(self, file_path):
        """Get file size in bytes"""
        return os.path.getsize(file_path)

    def format_file_size(self, size_bytes):
        """Convert bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"

    def upload_file_simple(self, file_path, bucket, key):
        """Upload file using simple put_object (for small files)"""
        try:
            with open(file_path, 'rb') as file:
                self.s3_client.put_object(
                    Bucket=bucket,
                    Key=key,
                    Body=file
                )
            return True
        except ClientError as e:
            logger.error(f"Simple upload failed: {e}")
            return False

    def upload_file_multipart(self, file_path, bucket, key):
        """Upload large file using multipart upload"""
        try:
            # Initiate multipart upload
            response = self.s3_client.create_multipart_upload(
                Bucket=bucket,
                Key=key
            )
            upload_id = response['UploadId']
            
            # Upload parts
            part_number = 1
            parts = []
            chunk_size = 50 * 1024 * 1024  # 50MB chunks
            
            with open(file_path, 'rb') as file:
                while True:
                    chunk = file.read(chunk_size)
                    if not chunk:
                        break
                    
                    response = self.s3_client.upload_part(
                        Bucket=bucket,
                        Key=key,
                        PartNumber=part_number,
                        UploadId=upload_id,
                        Body=chunk
                    )
                    parts.append({
                        'ETag': response['ETag'],
                        'PartNumber': part_number
                    })
                    logger.info(f"Uploaded part {part_number}")
                    part_number += 1
            
            # Complete multipart upload
            self.s3_client.complete_multipart_upload(
                Bucket=bucket,
                Key=key,
                UploadId=upload_id,
                MultipartUpload={'Parts': parts}
            )
            return True
            
        except ClientError as e:
            logger.error(f"Multipart upload failed: {e}")
            # Abort upload on failure
            try:
                self.s3_client.abort_multipart_upload(
                    Bucket=bucket,
                    Key=key,
                    UploadId=upload_id
                )
            except:
                pass
            return False

    def upload_file(self, file_path, bucket, key=None, max_retries=3):
        """Main upload method with retry logic"""
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return False
        
        if key is None:
            key = os.path.basename(file_path)
        
        file_size = self.get_file_size(file_path)
        human_size = self.format_file_size(file_size)
        
        logger.info(f"Starting upload: {file_path} -> s3://{bucket}/{key} ({human_size})")
        
        # Retry logic
        for attempt in range(max_retries):
            try:
                if file_size > self.multipart_threshold:
                    logger.info("Using multipart upload (file > 100MB)")
                    success = self.upload_file_multipart(file_path, bucket, key)
                else:
                    logger.info("Using simple upload")
                    success = self.upload_file_simple(file_path, bucket, key)
                
                if success:
                    logger.info(f"Upload completed successfully: {file_path}")
                    return True
                else:
                    logger.warning(f"Upload attempt {attempt + 1} failed, retrying...")
                    
            except Exception as e:
                logger.error(f"Upload attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    logger.error(f"All {max_retries} attempts failed for {file_path}")
                    return False
        
        return False

    def generate_presigned_url(self, bucket, key, expiration=3600):
        """Generate presigned URL for uploaded file"""
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket, 'Key': key},
                ExpiresIn=expiration
            )
            return url
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            return None

def upload_folder_recursive(uploader, folder_path, bucket, prefix=""):
    """Upload all files in folder recursively"""
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, folder_path)
            s3_key = os.path.join(prefix, relative_path).replace("\\", "/")
            
            uploader.upload_file(file_path, bucket, s3_key)

def main():
    parser = argparse.ArgumentParser(description='Upload files to S3 with multipart support')
    parser.add_argument('--file', required=True, help='Path to file to upload')
    parser.add_argument('--bucket', required=True, help='S3 bucket name')
    parser.add_argument('--key', help='S3 object key (optional)')
    parser.add_argument('--profile', help='AWS CLI profile name (optional)')
    parser.add_argument('--presigned-url', action='store_true', help='Generate presigned URL after upload')
    parser.add_argument('--recursive', action='store_true', help='Upload all files in folder recursively')
    
    args = parser.parse_args()
    
    # Initialize uploader
    uploader = S3Uploader(args.profile)
    
    # Check if path is file or directory
    if args.recursive and os.path.isdir(args.file):
        logger.info(f"Recursive upload of folder: {args.file}")
        upload_folder_recursive(uploader, args.file, args.bucket, args.key or "")
    else:
        # Single file upload
        success = uploader.upload_file(args.file, args.bucket, args.key)
        
        if success and args.presigned_url and not args.recursive:
            key = args.key or os.path.basename(args.file)
            url = uploader.generate_presigned_url(args.bucket, key)
            if url:
                logger.info(f"Presigned URL (expires in 1 hour): {url}")
    
    logger.info("Upload process completed")

if __name__ == "__main__":
    main()