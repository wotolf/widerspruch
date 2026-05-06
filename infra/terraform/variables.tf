variable "aws_region" {
  type        = string
  default     = "eu-central-1"
  description = "AWS Region für alle Ressourcen"
}

variable "environment" {
  type        = string
  default     = "dev"
  description = "Deployment-Umgebung"
}

variable "project_name" {
  type        = string
  default     = "widerspruch"
  description = "Wird als Prefix für Resource-Namen genutzt"
}
