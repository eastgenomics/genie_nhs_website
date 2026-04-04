terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "804761969039-genie-terraform-state"
    key            = "genie-nhs-website/terraform.tfstate"
    region         = "eu-west-2"
    dynamodb_table = "terraform-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "nhs-genie"
      Environment = local.env
      ManagedBy   = "terraform"
    }
  }
}

locals {
  env       = terraform.workspace
  is_prod   = terraform.workspace == "prod"
  name      = "nhs-genie-${local.env}"
  fqdn      = local.is_prod ? var.domain : "${local.env}.${var.domain}"
  ec2_type  = local.is_prod ? "t3.large" : "t3.medium"
  ebs_gb    = local.is_prod ? 30 : 20
}
