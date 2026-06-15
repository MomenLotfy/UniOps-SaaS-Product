# RDS Outputs
output "rds_endpoint" {
  description = "The connection endpoint for the RDS instance"
  value       = aws_db_instance.main.endpoint
}

output "rds_username" {
  description = "The username for the RDS instance"
  value       = aws_db_instance.main.username
}

output "db_password" {
  description = "The password for the RDS instance"
  value       = random_password.db_password.result
  sensitive   = true
}

output "db_name" {
  description = "The name of the database"
  value       = aws_db_instance.main.db_name
}

output "rds_instance_id" {
  description = "The ID of the RDS instance"
  value       = aws_db_instance.main.id
}

output "rds_instance_arn" {
  description = "The ARN of the RDS instance"
  value       = aws_db_instance.main.arn
}

# Redis Outputs
output "redis_endpoint" {
  description = "The primary endpoint for the Redis replication group"
  value       = aws_elasticache_replication_group.main.primary_endpoint_address
}

output "redis_auth_token" {
  description = "The auth token for Redis"
  value       = random_password.redis_token.result
  sensitive   = true
}

output "redis_secrets_arn" {
  description = "The ARN of the secret containing Redis credentials"
  value       = aws_secretsmanager_secret.redis_credentials.arn
}

# EFS Outputs
output "efs_id" {
  description = "The ID of the EFS file system"
  value       = aws_efs_file_system.main.id
}

output "efs_dns_name" {
  description = "The DNS name of the EFS file system"
  value       = aws_efs_file_system.main.dns_name
}

output "efs_arn" {
  description = "The ARN of the EFS file system"
  value       = aws_efs_file_system.main.arn
}

output "efs_access_point_id" {
  description = "The ID of the EFS access point"
  value       = aws_efs_access_point.main.id
}

# S3 Outputs
output "backup_bucket_name" {
  description = "The name of the backup S3 bucket"
  value       = aws_s3_bucket.backups.id
}

output "logs_bucket_name" {
  description = "The name of the logs S3 bucket"
  value       = aws_s3_bucket.logs.id
}
