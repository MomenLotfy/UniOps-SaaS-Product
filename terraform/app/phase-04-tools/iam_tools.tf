# IAM Role for Monitoring Instance
resource "aws_iam_role" "monitoring" {
  name = "uniops-monitoring-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "monitoring_cloudwatch" {
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
  role       = aws_iam_role.monitoring.name
}

resource "aws_iam_role_policy_attachment" "monitoring_ec2_readonly" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ReadOnlyAccess"
  role       = aws_iam_role.monitoring.name
}

resource "aws_iam_instance_profile" "monitoring" {
  name = "monitoring-profile"
  role = aws_iam_role.monitoring.name
}

# IAM Role for SonarQube Instance
resource "aws_iam_role" "sonarqube" {
  name = "uniops-sonarqube-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_instance_profile" "sonarqube" {
  name = "sonarqube-profile"
  role = aws_iam_role.sonarqube.name
}

# IAM Role for Public EC2 Instances
resource "aws_iam_role" "public_ec2" {
  name = "uniops-public-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_instance_profile" "public_ec2" {
  name = "public-ec2-profile"
  role = aws_iam_role.public_ec2.name
}
