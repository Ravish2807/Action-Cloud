terraform {
  required_version = ">= 1.9.0"
  required_providers {
    aws    = { source = "hashicorp/aws", version = "~> 6.65" }
    random = { source = "hashicorp/random", version = "~> 3.7" }
  }
}

provider "aws" {
  region = var.aws_region
  default_tags { tags = { Project = "ActionCloud", ManagedBy = "Terraform" } }
}

data "aws_caller_identity" "current" {}
data "aws_availability_zones" "available" { state = "available" }
