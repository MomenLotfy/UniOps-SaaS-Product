# ─────────────────────────────────────────────────────────────────────────────
# UniOps — Terraform Outputs
# بعد `terraform apply` الـ values دي بتتحفظ وتتستخدم في Ansible
# ─────────────────────────────────────────────────────────────────────────────

output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "eks_cluster_name" {
  description = "EKS cluster name — استخدمه في kubectl config"
  value       = module.eks.cluster_name
}

output "eks_cluster_endpoint" {
  description = "EKS API server endpoint"
  value       = module.eks.cluster_endpoint
}

output "database_host" {
  description = "RDS endpoint — يتحط في DATABASE_URL"
  value       = module.rds.db_instance_address
  sensitive   = true
}

output "redis_host" {
  description = "ElastiCache primary endpoint — يتحط في REDIS_URL"
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
  sensitive   = true
}

output "ecr_backend_url" {
  description = "ECR backend image URL — يتستخدم في docker push"
  value       = aws_ecr_repository.backend.repository_url
}

output "ecr_frontend_url" {
  description = "ECR frontend image URL"
  value       = aws_ecr_repository.frontend.repository_url
}

output "backups_bucket" {
  description = "S3 bucket name للـ backups"
  value       = aws_s3_bucket.backups.bucket
}

# ── Connection strings جاهزة للـ .env ────────────────────────────────────────
output "database_url" {
  description = "DATABASE_URL جاهزة للـ backend .env"
  value = "postgresql+asyncpg://uniops:PASSWORD@${module.rds.db_instance_address}:5432/uniops_db"
  sensitive = true
}

output "redis_url" {
  description = "REDIS_URL جاهزة للـ backend .env"
  value = "rediss://${aws_elasticache_replication_group.redis.primary_endpoint_address}:6379/0"
  sensitive = true
}

# ── kubectl config command ────────────────────────────────────────────────────
output "kubectl_config_command" {
  description = "أمر إعداد kubectl للـ cluster الجديد"
  value = "aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks.cluster_name}"
}
