# ─────────────────────────────────────────────────────────────────────────────
# Bootstrap input variables
# ─────────────────────────────────────────────────────────────────────────────

variable "aws_region" {
  description = "AWS region for bootstrap resources (must match the live app region)"
  type        = string
  default     = "us-east-2"
}

variable "state_bucket_name" {
  description = "Name of the S3 bucket that stores Terraform state (shared with app layer)"
  type        = string
  default     = "uniops-terraform-state"
}

variable "dynamodb_lock_table" {
  description = "Name of the DynamoDB table used for Terraform state locking"
  type        = string
  default     = "uniops-terraform-locks"
}

variable "ecr_repositories" {
  description = "Names of the ECR repositories the application layer pushes images to"
  type        = list(string)
  default     = ["uniops-backend", "uniops-frontend"]
}
