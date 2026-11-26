# The storefront's bucket, made by hand in episode 04.
resource "aws_s3_bucket" "site" {
  # In episode 04 we made the random suffix ourselves. Terraform can do that.
  bucket_prefix = "collect-site-"
}

# Episode 04's fix: nothing in this bucket can be made public.
resource "aws_s3_bucket_public_access_block" "site" {
  bucket = aws_s3_bucket.site.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Episode 05: only our distribution may read the files.
resource "aws_s3_bucket_policy" "site" {
  bucket = aws_s3_bucket.site.id

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [{
      Sid       = "AllowCloudFrontServicePrincipal"
      Effect    = "Allow"
      Principal = { Service = "cloudfront.amazonaws.com" }
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.site.arn}/*"
      Condition = {
        StringEquals = { "AWS:SourceArn" = aws_cloudfront_distribution.storefront.arn }
      }
    }]
  })
}
