# ─────────────────────────────────────────────────────────────────────────────
# Bootstrap-only IAM resources.
#
# No IAM roles currently exist in the account with "bootstrap" or "tf"
# in their name (verified by `aws iam list-roles`). The application
# Terraform is currently run interactively from a developer machine
# with full admin credentials, so no bootstrap-time IAM is needed.
#
# When CI/CD is added, the following will be created here:
#   - aws_iam_role.tf_ci           (GitHub Actions / GitLab CI role)
#   - aws_iam_role_policy_attachment for S3 state + DynamoDB lock
#   - aws_iam_user.tf_bootstrap    (break-glass admin, optional)
#
# This file is intentionally left as comments so the directory remains
# a valid Terraform project.
# ─────────────────────────────────────────────────────────────────────────────
