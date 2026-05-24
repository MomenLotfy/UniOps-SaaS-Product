# ─────────────────────────────────────────────────────────────────────────────
# Dev environment — أرخص config للتطوير
# ─────────────────────────────────────────────────────────────────────────────
# استخدام:
#   terraform apply -var-file=envs/dev.tfvars
# ─────────────────────────────────────────────────────────────────────────────

environment        = "dev"
aws_region         = "us-east-1"
node_instance_type = "t3.small"
db_instance_class  = "db.t3.micro"
redis_node_type    = "cache.t3.micro"
