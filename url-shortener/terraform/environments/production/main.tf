# Production Environment Configuration

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote state configuration
  backend "s3" {
    bucket         = "url-shortener-terraform-state"
    key            = "production/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "url-shortener-terraform-locks"
  }
}

provider "aws" {
  region = var.primary_region

  default_tags {
    tags = {
      Project     = "url-shortener"
      Environment = "production"
      ManagedBy   = "terraform"
    }
  }
}

variable "primary_region" {
  default = "us-east-1"
}

variable "replica_regions" {
  default = ["eu-west-1", "ap-south-1"]
}

# VPC
module "vpc" {
  source = "../../modules/vpc"

  environment = "production"
  region      = var.primary_region
  vpc_cidr    = "10.0.0.0/16"
}

# DynamoDB with Global Tables
module "dynamodb" {
  source = "../../modules/dynamodb"

  environment          = "production"
  enable_global_tables = true
  replica_regions      = var.replica_regions
}

# Outputs
output "vpc_id" {
  value = module.vpc.vpc_id
}

output "urls_table_name" {
  value = module.dynamodb.urls_table_name
}
