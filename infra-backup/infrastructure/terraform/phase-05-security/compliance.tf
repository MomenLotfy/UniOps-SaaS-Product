# Config Recorder
resource "aws_config_configuration_recorder" "main" {
  count    = var.enable_aws_config ? 1 : 0
  name     = "uniops-config-recorder"
  role_arn = aws_iam_role.config[0].arn

  recording_group {
    all_supported                 = true
    include_global_resource_types = true
  }
}

resource "aws_config_configuration_recorder_status" "main" {
  count      = var.enable_aws_config ? 1 : 0
  name       = aws_config_configuration_recorder.main[0].name
  is_enabled = true
}

resource "aws_config_delivery_channel" "main" {
  count          = var.enable_aws_config ? 1 : 0
  name           = "uniops-config-delivery"
  s3_bucket_name = aws_s3_bucket.config[0].bucket
}

resource "aws_iam_role" "config" {
  count = var.enable_aws_config ? 1 : 0
  name = "uniops-config-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "config.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "config" {
  count      = var.enable_aws_config ? 1 : 0
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSConfigRole"
  role       = aws_iam_role.config[0].name
}

# Config Rules
resource "aws_config_config_rule" "s3_public_read" {
  count = var.enable_aws_config ? 1 : 0
  name = "s3-bucket-public-read-prohibited"

  source {
    owner             = "AWS"
    source_identifier = "S3_BUCKET_PUBLIC_READ_PROHIBITED"
  }
}

resource "aws_config_config_rule" "restricted_ssh" {
  count = var.enable_aws_config ? 1 : 0
  name = "restricted-ssh"

  source {
    owner             = "AWS"
    source_identifier = "RESTRICTED_INCOMING_TRAFFIC"
  }

  input_parameters = jsonencode({
    blockedPort1 = "22"
  })
}

resource "aws_config_config_rule" "rds_encrypted" {
  count = var.enable_aws_config ? 1 : 0
  name = "rds-storage-encrypted"

  source {
    owner             = "AWS"
    source_identifier = "RDS_STORAGE_ENCRYPTED"
  }
}

resource "aws_config_config_rule" "ebs_encrypted" {
  count = var.enable_aws_config ? 1 : 0
  name = "ebs-encrypted-volumes"

  source {
    owner             = "AWS"
    source_identifier = "ENCRYPTED_VOLUMES"
  }
}

resource "random_string" "suffix" {
  count   = var.enable_aws_config ? 1 : 0
  length  = 8
  special = false
  upper   = false
}

resource "aws_s3_bucket" "config" {
  count  = var.enable_aws_config ? 1 : 0
  bucket = "uniops-config-dev-${random_string.suffix[0].result}"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "config" {
  count  = var.enable_aws_config ? 1 : 0
  bucket = aws_s3_bucket.config[0].id
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.uniops.arn
      sse_algorithm     = "aws:kms"
    }
  }
}
