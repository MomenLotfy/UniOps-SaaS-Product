# ─────────────────────────────────────────────────────────────────────────────
# Outputs consumed by the application Terraform layer via remote_state.
# ─────────────────────────────────────────────────────────────────────────────

output "state_bucket_name" {
  description = "S3 bucket that stores Terraform state for both layers"
  value       = aws_s3_bucket.terraform_state.id
}

output "state_bucket_arn" {
  description = "ARN of the S3 state bucket"
  value       = aws_s3_bucket.terraform_state.arn
}

output "state_bucket_versioning_enabled" {
  description = "Whether versioning is enabled on the state bucket"
  value       = aws_s3_bucket_versioning.terraform_state.versioning_configuration[0].status
}

output "dynamodb_lock_table_name" {
  description = "DynamoDB table used for state locking"
  value       = aws_dynamodb_table.terraform_locks.name
}

output "dynamodb_lock_table_arn" {
  description = "ARN of the DynamoDB lock table"
  value       = aws_dynamodb_table.terraform_locks.arn
}

output "ecr_backend_repository_url" {
  description = "Fully-qualified URL of the backend ECR repository"
  value       = aws_ecr_repository.backend.repository_url
}

output "ecr_frontend_repository_url" {
  description = "Fully-qualified URL of the frontend ECR repository"
  value       = aws_ecr_repository.frontend.repository_url
}

output "ecr_backend_repository_arn" {
  description = "ARN of the backend ECR repository"
  value       = aws_ecr_repository.backend.arn
}

output "ecr_frontend_repository_arn" {
  description = "ARN of the frontend ECR repository"
  value       = aws_ecr_repository.frontend.arn
}
