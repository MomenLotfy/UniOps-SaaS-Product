resource "aws_backup_vault" "main" {
  name        = "uniops-backup-vault-dev"
  kms_key_arn = aws_kms_key.uniops.arn
}

resource "aws_backup_plan" "main" {
  name = "uniops-backup-plan-dev"

  rule {
    rule_name         = "daily-backup"
    target_vault_name = aws_backup_vault.main.name
    schedule          = "cron(0 5 * * ? *)" # Daily at 5AM UTC

    lifecycle {
      delete_after = 35
    }
  }
}

resource "aws_backup_selection" "main" {
  iam_role_arn = aws_iam_role.backup.arn
  name         = "uniops-backup-selection"
  plan_id      = aws_backup_plan.main.id

  resources = [
    var.rds_instance_arn,
    var.efs_arn
  ]
}

resource "aws_iam_role" "backup" {
  name = "uniops-backup-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "backup.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "backup" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup"
  role       = aws_iam_role.backup.name
}

resource "aws_iam_role_policy_attachment" "backup_restores" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForRestores"
  role       = aws_iam_role.backup.name
}
