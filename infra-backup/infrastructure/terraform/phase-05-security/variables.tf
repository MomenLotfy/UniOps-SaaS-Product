variable "enable_aws_config" {
  description = "Enable AWS Config recorder and rules"
  type        = bool
  default     = false
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-2"
}

variable "project_name" {
  description = "Project name"
  type        = string
}

variable "environment" {
  description = "Environment (dev/prod)"
  type        = string
}

variable "tags" {
  description = "Common tags for resources"
  type        = map(string)
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "alb_arn" {
  description = "ALB ARN"
  type        = string
}

variable "eks_cluster_name" {
  description = "EKS Cluster Name"
  type        = string
}

variable "rds_instance_id" {
  description = "RDS Instance ID"
  type        = string
}

variable "rds_instance_arn" {
  description = "RDS Instance ARN"
  type        = string
}

variable "efs_id" {
  description = "EFS ID"
  type        = string
}

variable "efs_arn" {
  description = "EFS ARN"
  type        = string
}
