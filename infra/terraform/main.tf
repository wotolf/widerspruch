terraform {
  required_version = ">= 1.7"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket = "widerspruch-tfstate-794457362356"
    key    = "main.tfstate"
    region = "eu-central-1"
  }
}

provider "aws" {
  region = var.aws_region
}
