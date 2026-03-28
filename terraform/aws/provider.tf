terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = ">= 2.4.0"
    }
  }

  backend "s3" {
    bucket  = "terraform-state-geneamatique-705059528575-eu-north-1-an"
    key     = "terraform/aws/terraform.tfstate"
    region  = "eu-north-1"
    profile = "eric"
  }
}

provider "aws" {
  region  = var.aws_region
  profile = "eric"
}
