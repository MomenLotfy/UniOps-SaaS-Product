# IAM Role for Service Account (IRSA)
resource "aws_iam_role" "irsa" {
  name = "uniops-irsa-role-dev"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRoleWithWebIdentity"
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.eks.arn
        }
        Condition = {
          StringEquals = {
            "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:sub" : "system:serviceaccount:uniops:uniops-sa",
            "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:aud" : "sts.amazonaws.com"
          }
        }
      }
    ]
  })

  tags = {
    Name = "uniops-irsa-role-dev"
  }
}

resource "aws_iam_role_policy_attachment" "irsa_s3" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"
  role       = aws_iam_role.irsa.name
}

resource "aws_iam_role_policy_attachment" "irsa_secrets" {
  policy_arn = "arn:aws:iam::aws:policy/SecretsManagerReadWrite"
  role       = aws_iam_role.irsa.name
}

output "irsa_role_arn" {
  value = aws_iam_role.irsa.arn
}
