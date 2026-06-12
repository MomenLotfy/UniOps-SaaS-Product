# SNS Topic for Alerts
resource "aws_sns_topic" "alerts" {
  name         = "uniops-alerts-dev"
  display_name = "UniOps Dev Alerts"
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = "devops-team@example.com" # Placeholder: update with real email
}
