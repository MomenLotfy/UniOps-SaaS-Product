# ─────────────────────────────────────────────────────────────────────────────
# ECR repositories for the application container images.
#
# The repos are imported (not recreated) with their CURRENT configuration:
#   - image_tag_mutability = MUTABLE
#   - scan_on_push         = false
#
# Any tightening (IMMUTABLE / scan-on-push=true) must be a separate,
# reviewed plan — it is intentionally NOT included here.
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_ecr_repository" "backend" {
  name                 = "uniops-backend"
  image_tag_mutability = "MUTABLE"
  image_scanning_configuration {
    scan_on_push = false
  }

  tags = {
    Component = "backend"
    Owner     = "uniops-app"
  }
}

resource "aws_ecr_repository" "frontend" {
  name                 = "uniops-frontend"
  image_tag_mutability = "MUTABLE"
  image_scanning_configuration {
    scan_on_push = false
  }

  tags = {
    Component = "frontend"
    Owner     = "uniops-app"
  }
}
