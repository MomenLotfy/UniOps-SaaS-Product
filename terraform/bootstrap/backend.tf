# ─────────────────────────────────────────────────────────────────────────────
# Terraform Bootstrap — backend for THIS layer's state
#
# State lives in the same S3 bucket as the app layer but under a
# different key. Locking is provided by the same DynamoDB table; the
# state key acts as the natural lock domain because Terraform's
# state-locking is keyed on the state file path.
#
# ── BOOTSTRAP PROCEDURE (chicken-and-egg resolution) ─────────────────────
# The S3 bucket this layer creates cannot host its own state file
# during the first apply. The standard resolution is:
#
#   1. Comment out the `backend "s3" {}` block (or set it to local).
#   2. `terraform init -backend=false` to install providers only.
#   3. `terraform apply` to create the S3 bucket + DynamoDB table +
#      ECR repos.
#   4. `terraform init -migrate-state` to move local state into S3.
#   5. Verify with `terraform plan` (must show 0 changes).
#
# The S3 backend config below is the FINAL form (post-migration).
# During step 1, the `backend` block is replaced with:
#
#   # backend "s3" { ... }
#
# and the file is saved as `backend.tf.bak`. After migration, rename
# it back.
# ─────────────────────────────────────────────────────────────────────────────

terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # ── FINAL form (post-migration) ─────────────────────────────────────
  # S3 backend with DynamoDB locking. The local-backend block that was
  # used during first-apply has been removed and state migrated to S3.
  # See backend.tf.bak for the local-backend temporary form.
  backend "s3" {
    bucket         = "uniops-663476173962-tfstate"
    key            = "bootstrap/terraform.tfstate"
    region         = "us-east-2"
    dynamodb_table = "uniops-terraform-locks"
    encrypt        = true
  }
}
