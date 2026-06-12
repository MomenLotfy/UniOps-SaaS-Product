# Redis Security Group
resource "aws_security_group" "redis" {
  name        = "uniops-redis-sg-dev"
  description = "Security group for ElastiCache Redis"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [var.eks_nodes_sg_id]
    description     = "Redis from EKS nodes"
  }

  ingress {
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
    description = "Redis from VPC CIDR"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-redis-sg"
  }
}

# Redis Subnet Group
resource "aws_elasticache_subnet_group" "main" {
  name       = "uniops-redis-subnet-group"
  subnet_ids = var.private_subnets
}

# Redis Parameter Group
resource "aws_elasticache_parameter_group" "main" {
  family = "redis7"
  name   = "uniops-redis-params"

  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }

  parameter {
    name  = "notify-keyspace-events"
    value = "Ex"
  }
}

# Redis Auth Token
resource "random_password" "redis_token" {
  length  = 32
  special = false # Redis auth token constraints
}

# Redis Replication Group (Cluster Mode Disabled)
resource "aws_elasticache_replication_group" "main" {
  replication_group_id       = "uniops-redis-dev"
  description                = "UniOps Redis cluster"
  node_type                  = "cache.t3.micro"
  port                       = 6379
  parameter_group_name       = aws_elasticache_parameter_group.main.name
  subnet_group_name          = aws_elasticache_subnet_group.main.name
  security_group_ids         = [aws_security_group.redis.id]
  engine                     = "redis"
  engine_version             = "7.1"
  num_cache_clusters         = 1
  automatic_failover_enabled = false

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  kms_key_id                 = var.kms_key_arn
  auth_token                 = random_password.redis_token.result

  tags = {
    Name = "uniops-redis-dev"
  }
}

# Secrets Manager for Redis
resource "aws_secretsmanager_secret" "redis_credentials" {
  name = "uniops/redis-credentials-dev"
}

resource "aws_secretsmanager_secret_version" "redis_credentials" {
  secret_id = aws_secretsmanager_secret.redis_credentials.id
  secret_string = jsonencode({
    host       = aws_elasticache_replication_group.main.primary_endpoint_address
    port       = 6379
    auth_token = random_password.redis_token.result
  })
}
