# Security Group for Monitoring
resource "aws_security_group" "monitoring" {
  name        = "monitoring-sg"
  description = "Security group for Monitoring (Prometheus/Grafana)"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 9090
    to_port     = 9090
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
    description = "Prometheus from VPC"
  }

  ingress {
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
    description = "Grafana from VPC"
  }

  ingress {
    from_port       = 22
    to_port         = 22
    protocol        = "tcp"
    security_groups = [var.bastion_sg_id]
    description     = "SSH from Bastion"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-monitoring-sg"
  }
}

# Data source for Amazon Linux 2 AMI
data "aws_ami" "amazon_linux_2" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }
}

# Monitoring Instance (Private Subnet 2a)
resource "aws_instance" "monitoring" {
  ami                    = data.aws_ami.amazon_linux_2.id
  instance_type          = "t3.micro"
  subnet_id              = var.private_subnets[0]
  iam_instance_profile   = aws_iam_instance_profile.monitoring.name
  vpc_security_group_ids = [aws_security_group.monitoring.id]
  key_name               = var.key_name

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
  }

  user_data = <<-EOF
              #!/bin/bash
              yum update -y
              amazon-linux-extras install docker -y
              service docker start
              usermod -a -G docker ec2-user
              chkconfig docker on
              curl -L "https://github.com/docker/compose/releases/download/v2.20.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
              chmod +x /usr/local/bin/docker-compose
              EOF

  tags = {
    Name = "uniops-monitoring-dev"
    Role = "monitoring"
  }
}

# Security Group for SonarQube
resource "aws_security_group" "sonarqube" {
  name        = "sonarqube-sg"
  description = "Security group for SonarQube"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 9000
    to_port     = 9000
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
    description = "SonarQube web from VPC"
  }

  ingress {
    from_port       = 22
    to_port         = 22
    protocol        = "tcp"
    security_groups = [var.bastion_sg_id]
    description     = "SSH from Bastion"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-sonarqube-sg"
  }
}

# SonarQube Instance (Private Subnet 2b)
resource "aws_instance" "sonarqube" {
  ami                    = data.aws_ami.amazon_linux_2.id
  instance_type          = "t3.micro"
  subnet_id              = var.private_subnets[1]
  iam_instance_profile   = aws_iam_instance_profile.sonarqube.name
  vpc_security_group_ids = [aws_security_group.sonarqube.id]
  key_name               = var.key_name

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
  }

  user_data = file("${path.module}/../../scripts/sonarqube-docker-compose.sh")

  tags = {
    Name = "uniops-sonarqube-dev"
    Role = "code-quality"
  }
}
