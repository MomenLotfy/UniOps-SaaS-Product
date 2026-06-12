# ─────────────────────────────────────────────────────────────────────────────
# S3 bucket for Terraform state (shared with the app layer under a
# different key). Versioning + AES-256 encryption + public-access
# block. The bucket is `prevent_destroy` because losing it would mean
# losing all Terraform state for the project.
#
# All three sub-resources (versioning, encryption, public-access-block)
# are tracked separately because the AWS provider does not support
# nested arguments on aws_s3_bucket.
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_s3_bucket" "terraform_state" {
  bucket = var.state_bucket_name

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Name = "Terraform State"
    Tier = "shared"
  }
}

resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "terraform_state" {
  bucket                  = aws_s3_bucket.terraform_state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
