terraform {
  # 1.11 is the first version where S3 state locking is generally available.
  required_version = ">= 1.11"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}
