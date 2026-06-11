variable "project_name" {
  type        = string
  description = "Name of the project"
  default     = "uniops-saas"
}

variable "environment" {
  type        = string
  description = "Deployment environment (dev, prod, staging)"
  default     = "dev"
}

variable "aws_region" {
  type        = string
  description = "AWS region for deployment"
  default     = "us-east-2"
}

variable "vpc_cidr" {
  type        = string
  description = "CIDR block for the VPC"
  default     = "10.0.0.0/16"
}

variable "cluster_version" {
  type        = string
  description = "K8s version for EKS"
  default     = "1.30"
}
