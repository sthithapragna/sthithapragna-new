# State lives in S3, so everyone and the pipeline share it.
# The bucket name comes from backend.hcl, which git ignores:
#   terraform init -backend-config=backend.hcl
terraform {
  backend "s3" {
    key          = "collect/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}
