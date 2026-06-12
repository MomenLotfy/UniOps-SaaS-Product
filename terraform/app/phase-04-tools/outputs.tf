# Monitoring Outputs
output "monitoring_private_ip" {
  description = "Private IP of the Monitoring instance"
  value       = aws_instance.monitoring.private_ip
}

# SonarQube Outputs
output "sonarqube_private_ip" {
  description = "Private IP of the SonarQube instance"
  value       = aws_instance.sonarqube.private_ip
}

# Public EC2 Outputs
output "public_instance_1_ip" {
  description = "Public IP of public instance 1"
  value       = aws_instance.public_1.public_ip
}

output "public_instance_2_ip" {
  description = "Public IP of public instance 2"
  value       = aws_instance.public_2.public_ip
}

# ALB Outputs
output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = aws_lb.main.dns_name
}

output "alb_target_group_arn" {
  description = "ARN of the main ALB target group"
  value       = aws_lb_target_group.main.arn
}

output "alb_arn" {
  description = "The ARN of the Application Load Balancer"
  value       = aws_lb.main.arn
}
