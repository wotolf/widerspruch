output "rds_endpoint" {
  description = "RDS Endpoint (Hostname)"
  value       = aws_db_instance.main.address
}

output "rds_port" {
  description = "RDS Port"
  value       = aws_db_instance.main.port
}

output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

output "ecs_cluster_name" {
  description = "ECS Cluster Name"
  value       = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  description = "ECS Service Name"
  value       = aws_ecs_service.bot.name
}

output "cloudwatch_log_group" {
  description = "CloudWatch Log Group für Bot-Logs"
  value       = aws_cloudwatch_log_group.bot.name
}
