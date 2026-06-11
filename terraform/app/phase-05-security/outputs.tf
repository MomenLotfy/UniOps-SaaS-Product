output "kms_key_arn" {
  description = "The ARN of the master KMS key"
  value       = aws_kms_key.uniops.arn
}

output "waf_web_acl_arn" {
  description = "The ARN of the WAF Web ACL"
  value       = aws_wafv2_web_acl.main.arn
}
