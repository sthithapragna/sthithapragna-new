# Credentials come from the environment: AWS_PROFILE on your computer,
# the pipeline's role in episode 11. Nothing secret lives in this folder.
provider "aws" {
  region = "us-east-1"

  # Added to every resource this configuration creates or adopts.
  default_tags {
    tags = {
      Project   = "kestrel-collect"
      ManagedBy = "terraform"
    }
  }
}
