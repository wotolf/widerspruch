variable "aws_region" {
  type        = string
  default     = "eu-central-1"
  description = "AWS Region für alle Ressourcen"
}

variable "environment" {
  type        = string
  default     = "dev"
  description = "Deployment-Umgebung (dev / prod)"
}

variable "project_name" {
  type        = string
  default     = "widerspruch"
  description = "Prefix für alle Resource-Namen"
}

variable "db_password" {
  type        = string
  sensitive   = true
  description = "Passwort für die RDS-Instanz — via TF_VAR_db_password oder terraform.tfvars setzen"
}
