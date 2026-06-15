resource "aws_kms_key" "uniops" {
  description             = "KMS key for UniOps dev environment encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  policy = data.aws_iam_policy_document.kms.json

  tags = {
    Name = "uniops-dev-key"
  }
}

resource "aws_kms_alias" "uniops" {
  name          = "alias/uniops-dev-key"
  target_key_id = aws_kms_key.uniops.key_id
}
