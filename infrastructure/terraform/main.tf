# ─────────────────────────────────────────────────────────────────────────────
# UniOps — AWS Infrastructure (Terraform)
# ─────────────────────────────────────────────────────────────────────────────
# ما بيعمله:
#   - VPC + subnets + security groups
#   - EKS cluster (Kubernetes managed)
#   - RDS PostgreSQL
#   - ElastiCache Redis
#   - S3 bucket للـ backups
#   - ECR للـ Docker images
# ─────────────────────────────────────────────────────────────────────────────

terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.0"
    }
  }

  # Remote state — مش تحفظ الـ state محلياً
  backend "s3" {
    bucket = "uniops-663476173962-tfstate"
    key    = "prod/terraform.tfstate"
    region = "us-east-1"
    # Locking بـ DynamoDB
    dynamodb_table = "uniops-terraform-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "UniOps"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# ── Data sources ──────────────────────────────────────────────────────────────
data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

# ── Local values ──────────────────────────────────────────────────────────────
locals {
  name   = "uniops-${var.environment}"
  azs    = slice(data.aws_availability_zones.available.names, 0, 3)
}

# ── VPC ───────────────────────────────────────────────────────────────────────
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${local.name}-vpc"
  cidr = var.vpc_cidr

  azs             = local.azs
  private_subnets = var.private_subnets
  public_subnets  = var.public_subnets

  enable_nat_gateway     = true
  single_nat_gateway     = var.environment != "prod"  # prod → multi-AZ NAT
  enable_dns_hostnames   = true
  enable_dns_support     = true

  # EKS بيحتاج tags على الـ subnets
  private_subnet_tags = {
    "kubernetes.io/cluster/${local.name}" = "shared"
    "kubernetes.io/role/internal-elb"     = "1"
  }
  public_subnet_tags = {
    "kubernetes.io/cluster/${local.name}" = "shared"
    "kubernetes.io/role/elb"              = "1"
  }
}

# ── EKS (Kubernetes) ──────────────────────────────────────────────────────────
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = local.name
  cluster_version = "1.29"

  vpc_id                         = module.vpc.vpc_id
  subnet_ids                     = module.vpc.private_subnet_ids
  cluster_endpoint_public_access = true

  # Node groups
  eks_managed_node_groups = {
    # General workload
    general = {
      name           = "general"
      instance_types = [var.node_instance_type]
      min_size       = 2
      max_size       = 10
      desired_size   = var.environment == "prod" ? 3 : 2

      labels = { role = "general" }
    }
  }

  # Add-ons
  cluster_addons = {
    coredns                = { most_recent = true }
    kube-proxy             = { most_recent = true }
    vpc-cni                = { most_recent = true }
    aws-ebs-csi-driver     = { most_recent = true }
  }
}

# ── RDS PostgreSQL ────────────────────────────────────────────────────────────
module "rds" {
  source  = "terraform-aws-modules/rds/aws"
  version = "~> 6.0"

  identifier = "${local.name}-postgres"

  engine               = "postgres"
  engine_version       = "16"
  instance_class       = var.db_instance_class
  allocated_storage    = 20
  max_allocated_storage = 100   # auto-scaling
  storage_encrypted    = true

  db_name  = "uniops_db"
  username = "uniops"
  # Password من AWS Secrets Manager — مش هنا
  manage_master_user_password = true

  vpc_security_group_ids = [aws_security_group.rds.id]
  subnet_ids             = module.vpc.private_subnet_ids
  create_db_subnet_group = true

  # Backups
  backup_retention_period = var.environment == "prod" ? 7 : 1
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"

  # Multi-AZ في prod فقط
  multi_az = var.environment == "prod"

  # Deletion protection في prod
  deletion_protection = var.environment == "prod"

  parameters = [
    { name = "log_connections",          value = "1" },
    { name = "log_disconnections",       value = "1" },
    { name = "log_min_duration_statement", value = "1000" },  # log slow queries > 1s
  ]
}

# ── ElastiCache Redis ─────────────────────────────────────────────────────────
resource "aws_elasticache_replication_group" "redis" {
  replication_group_id = "${local.name}-redis"
  description          = "UniOps Redis cluster"

  node_type            = var.redis_node_type
  port                 = 6379
  parameter_group_name = "default.redis7"

  automatic_failover_enabled = var.environment == "prod"
  num_cache_clusters         = var.environment == "prod" ? 2 : 1

  subnet_group_name  = aws_elasticache_subnet_group.redis.name
  security_group_ids = [aws_security_group.redis.id]

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true

  log_delivery_configuration {
    destination      = aws_cloudwatch_log_group.redis.name
    destination_type = "cloudwatch-logs"
    log_format       = "text"
    log_type         = "slow-log"
  }
}

resource "aws_elasticache_subnet_group" "redis" {
  name       = "${local.name}-redis-subnet"
  subnet_ids = module.vpc.private_subnet_ids
}

# ── ECR — Docker registry ─────────────────────────────────────────────────────
resource "aws_ecr_repository" "backend" {
  name                 = "${local.name}-backend"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true   # Trivy scan عند كل push
  }

  encryption_configuration {
    encryption_type = "KMS"
  }
}

resource "aws_ecr_repository" "frontend" {
  name                 = "${local.name}-frontend"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

# ── S3 — Backups & static ─────────────────────────────────────────────────────
resource "aws_s3_bucket" "backups" {
  bucket = "${local.name}-backups-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_versioning" "backups" {
  bucket = aws_s3_bucket.backups.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id

  rule {
    id     = "delete-old-backups"
    status = "Enabled"
    expiration { days = 30 }
  }
}

# ── Security Groups ───────────────────────────────────────────────────────────
resource "aws_security_group" "rds" {
  name   = "${local.name}-rds-sg"
  vpc_id = module.vpc.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [module.eks.node_security_group_id]
    description     = "PostgreSQL from EKS nodes only"
  }
}

resource "aws_security_group" "redis" {
  name   = "${local.name}-redis-sg"
  vpc_id = module.vpc.vpc_id

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [module.eks.node_security_group_id]
    description     = "Redis from EKS nodes only"
  }
}

# ── CloudWatch Log Groups ─────────────────────────────────────────────────────
resource "aws_cloudwatch_log_group" "redis" {
  name              = "/uniops/${var.environment}/redis"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "backend" {
  name              = "/uniops/${var.environment}/backend"
  retention_in_days = 30
}
