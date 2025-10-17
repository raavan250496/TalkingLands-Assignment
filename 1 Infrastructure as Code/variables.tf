variable "aws_region" {
  type    = string
  default = "ap-south-1"
}

variable "ami_id" {
  type    = string
  default = "ami-02d26659fd82cf299"
}

variable "instance_type" {
  type    = string
  default = "t2.micro"
}

variable "key_name" {
  type    = string
  default = "my-key"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "custom_message" {
  type    = string
  default = "Deployed via Terraform."
}