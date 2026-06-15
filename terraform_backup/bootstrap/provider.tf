# ─────────────────────────────────────────────────────────────────────────────
# AWS provider — pinned to us-east-2, matching the region of all live
# resources (EKS, RDS, Redis, ECR). The app layer's existing
# infrastructure/terraform/main.tf references us-east-1 for the state
# backend, which is a pre-existing misconfiguration out of scope here.
# ─────────────────────────────────────────────────────────────────────────────

provider "aws" {
  region = "us-east-2"

  default_tags {
    tags = {
      Project     = "UniOps"
      Layer       = "bootstrap"
      ManagedBy   = "Terraform"
      Environment = "shared"
    }
  }
}
