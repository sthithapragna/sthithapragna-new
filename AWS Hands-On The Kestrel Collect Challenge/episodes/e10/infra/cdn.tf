# Managed policies: AWS owns them, we only refer to them.
data "aws_cloudfront_cache_policy" "optimized" {
  name = "Managed-CachingOptimized"
}

data "aws_cloudfront_response_headers_policy" "security" {
  name = "Managed-SecurityHeadersPolicy"
}

# Made by the Free plan in episode 05. The plan owns it, so we only refer to it.
data "aws_wafv2_web_acl" "free_plan" {
  name  = var.web_acl_name
  scope = "CLOUDFRONT"
}

locals {
  origin_id = "storefront-s3"
}

resource "aws_cloudfront_origin_access_control" "site" {
  name                              = "collect-storefront-oac"
  description                       = "CloudFront signs its requests to the site bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# Episodes 05 and 07: deep links, and www to the bare domain.
resource "aws_cloudfront_function" "routing" {
  name    = "collect-spa-routing"
  runtime = "cloudfront-js-2.0"
  publish = true

  # Git on Windows can add carriage returns. The deployed code has none.
  code = replace(file("${path.module}/edge/viewer-request.js"), "\r\n", "\n")
}

resource "aws_cloudfront_distribution" "storefront" {
  enabled             = true
  comment             = "Kestrel Collect storefront"
  aliases             = [var.domain_name, "www.${var.domain_name}"]
  default_root_object = "index.html"
  is_ipv6_enabled     = true
  http_version        = "http2and3"
  price_class         = "PriceClass_All"
  web_acl_id          = data.aws_wafv2_web_acl.free_plan.arn

  origin {
    origin_id                = local.origin_id
    domain_name              = aws_s3_bucket.site.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.site.id
  }

  default_cache_behavior {
    target_origin_id           = local.origin_id
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD"]
    cached_methods             = ["GET", "HEAD"]
    compress                   = true
    cache_policy_id            = data.aws_cloudfront_cache_policy.optimized.id
    response_headers_policy_id = data.aws_cloudfront_response_headers_policy.security.id

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.routing.arn
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate.site.arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  # The console shows this as the distribution's name.
  tags = {
    Name = "collect-storefront"
  }
}
