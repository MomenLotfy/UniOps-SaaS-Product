# ─────────────────────────────────────────────────────────────────────────────
# Production environment — high availability config
# ─────────────────────────────────────────────────────────────────────────────

environment        = "prod"
aws_region         = "us-east-1"
node_instance_type = "t3.medium"
db_instance_class  = "db.t3.small"
redis_node_type    = "cache.t3.small"
