# Widerspruch — AWS-Infrastruktur
# Wird ab Phase 3 angefasst. Hier nur ein Skelett damit du weißt wo's hingeht.

terraform {
  required_version = ">= 1.7"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Backend für State — empfohlen S3 + DynamoDB Lock
  # backend "s3" {
  #   bucket         = "widerspruch-tfstate-DEINSUFFIX"
  #   key            = "main.tfstate"
  #   region         = "eu-central-1"
  #   dynamodb_table = "widerspruch-tflock"
  # }
}

provider "aws" {
  region = var.aws_region
}

# TODO Phase 3:
# - VPC + Subnets
# - RDS Postgres (db.t4g.micro reicht für Solo-Dev)
# - ECS Fargate für den Bot
# - Lambda + EventBridge für Real-Time-Threats
# - S3 Bucket für Evidence Storage
# - Secrets Manager für Tokens
