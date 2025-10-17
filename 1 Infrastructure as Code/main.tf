provider "aws" {
  region = var.aws_region
}

resource "aws_security_group" "nginx_sg" {
  name        = "${var.environment}-nginx-sg"
  description = "Allow SSH and HTTP traffic"

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "nginx_server" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.nginx_sg.id]
  
  user_data = templatefile("${path.module}/scripts/user-data.sh", {
    custom_message = var.custom_message
    environment    = var.environment
  })

  tags = {
    Name        = "${var.environment}-nginx-server"
    Environment = var.environment
  }
}

output "instance_public_ip" {
  value = aws_instance.nginx_server.public_ip
}

output "nginx_url" {
  value = "http://${aws_instance.nginx_server.public_dns}"
}