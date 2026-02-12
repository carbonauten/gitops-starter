// Minimal Terraform scaffold — customize provider and backend as needed

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 4.0"
    }
  }

  # Example S3 remote state backend (uncomment and configure)
  # backend "s3" {
  #   bucket = "<your-terraform-state-bucket>"
  #   key    = "gitops-starter/terraform.tfstate"
  #   region = "eu-central-1"
  # }
}

provider "aws" {
  region = var.aws_region
}

# Example: create an EKS cluster (optional — use a module in production)
# module "eks" {
#   source          = "terraform-aws-modules/eks/aws"
#   cluster_name    = "gitops-starter-eks"
#   cluster_version = "1.27"
#   subnets         = []
#   vpc_id          = "<vpc-id>"
# }

output "placeholder" {
  value = "Customize infra/terraform/main.tf"
}
