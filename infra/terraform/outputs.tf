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
