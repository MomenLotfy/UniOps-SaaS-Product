# RDS Security Group
resource "aws_security_group" "rds" {
  name        = "rds-sg"
  description = "Security group for RDS PostgreSQL"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [var.eks_nodes_sg_id]
    description     = "PostgreSQL from EKS nodes"
  }

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
    description = "PostgreSQL from VPC CIDR"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-rds-sg"
  }
}

# RDS Subnet Group
resource "aws_db_subnet_group" "main" {
  name       = "uniops-rds-subnet-group"
  subnet_ids = var.private_subnets

  tags = {
    Name = "UniOps RDS Subnet Group"
  }
}

# DB Password
resource "random_password" "db_password" {
  length           = 16
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# RDS Instance
resource "aws_db_instance" "main" {
  identifier             = "uniops-postgres-dev"
  engine                 = "postgres"
  engine_version         = "15"
  instance_class         = "db.t3.micro"
  allocated_storage      = 20
  storage_type           = "gp2"
  storage_encrypted       = true
  kms_key_id             = var.kms_key_arn
  db_name                = "uniops"
  username               = "uniops_admin"
  password               = random_password.db_password.result
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  publicly_accessible     = false
  multi_az                = false # Cost saving for dev
  backup_retention_period = 0
  deletion_protection     = false
  skip_final_snapshot     = true

  tags = {
    Name = "uniops-postgres-dev"
  }
}

# Secrets Manager for RDS
resource "aws_secretsmanager_secret" "db_credentials" {
  name       = "uniops/db-credentials-dev"
  kms_key_id = var.kms_key_arn
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = aws_db_instance.main.username
    password = random_password.db_password.result
    host     = aws_db_instance.main.address
    port     = aws_db_instance.main.port
    db_name  = aws_db_instance.main.db_name
  })
}
