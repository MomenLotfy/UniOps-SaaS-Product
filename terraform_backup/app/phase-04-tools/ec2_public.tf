# Security Group for Public EC2
resource "aws_security_group" "public_ec2" {
  name        = "public-ec2-sg"
  description = "Security group for Public EC2 instances"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 80
    to_port         = 80
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
    description     = "HTTP from ALB"
  }

  ingress {
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
    description     = "HTTPS from ALB"
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
    Name = "${var.project_name}-public-ec2-sg"
  }
}

# Public EC2 Instance 1 (Public Subnet 2a)
resource "aws_instance" "public_1" {
  ami                         = data.aws_ami.amazon_linux_2.id
  instance_type               = "t3.micro"
  subnet_id                   = var.public_subnets[0]
  iam_instance_profile        = aws_iam_instance_profile.public_ec2.name
  vpc_security_group_ids      = [aws_security_group.public_ec2.id]
  key_name                    = var.key_name
  associate_public_ip_address = true

  user_data = <<-EOF
              #!/bin/bash
              yum update -y
              amazon-linux-extras install docker -y
              service docker start
              usermod -a -G docker ec2-user
              chkconfig docker on
              docker run -d -p 80:80 nginx
              EOF

  tags = {
    Name = "uniops-public-1-dev"
    Role = "public-compute"
  }
}

# Public EC2 Instance 2 (Public Subnet 2b)
resource "aws_instance" "public_2" {
  ami                         = data.aws_ami.amazon_linux_2.id
  instance_type               = "t3.micro"
  subnet_id                   = var.public_subnets[1]
  iam_instance_profile        = aws_iam_instance_profile.public_ec2.name
  vpc_security_group_ids      = [aws_security_group.public_ec2.id]
  key_name                    = var.key_name
  associate_public_ip_address = true

  user_data = <<-EOF
              #!/bin/bash
              yum update -y
              amazon-linux-extras install docker -y
              service docker start
              usermod -a -G docker ec2-user
              chkconfig docker on
              docker run -d -p 80:80 nginx
              EOF

  tags = {
    Name = "uniops-public-2-dev"
    Role = "public-compute"
  }
}
