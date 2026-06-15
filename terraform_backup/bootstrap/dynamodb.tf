# ─────────────────────────────────────────────────────────────────────────────
# DynamoDB table for Terraform state locking. Shared across bootstrap
# and app layers; key-level isolation is provided by the S3 state key
# since Terraform's state-locking is keyed on the state file path.
#
# PAY_PER_REQUEST keeps cost near zero for low-frequency state locks.
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_dynamodb_table" "terraform_locks" {
  name         = var.dynamodb_lock_table
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Name = "Terraform Lock Table"
    Tier = "shared"
  }
}
