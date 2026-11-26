# GitHub's token issuer. One per account, shared by every workflow.
resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

# Who may assume the role: a token from GitHub, for our repositories.
data "aws_iam_policy_document" "github_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_owner}/*"]
    }
  }
}

resource "aws_iam_role" "github_plan" {
  name                 = "collect-github-plan"
  description          = "Assumed by GitHub Actions in ${var.github_owner}/${var.github_repo}"
  assume_role_policy   = data.aws_iam_policy_document.github_trust.json
  max_session_duration = 3600
}

# For now the pipeline only plans, so reading is enough.
resource "aws_iam_role_policy_attachment" "github_read" {
  role       = aws_iam_role.github_plan.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

data "aws_caller_identity" "current" {}

# Plan takes the state lock, so it writes and deletes the lock file.
resource "aws_iam_role_policy" "github_state_lock" {
  name = "terraform-state-lock"
  role = aws_iam_role.github_plan.id

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:PutObject", "s3:DeleteObject"]
      Resource = "arn:aws:s3:::collect-tfstate-${data.aws_caller_identity.current.account_id}-us-east-1-an/collect/terraform.tfstate.tflock"
    }]
  })
}
