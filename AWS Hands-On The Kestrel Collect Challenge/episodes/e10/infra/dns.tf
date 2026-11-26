locals {
  site_names = toset([var.domain_name, "www.${var.domain_name}"])

  validation = {
    for o in aws_acm_certificate.site.domain_validation_options : o.domain_name => o
  }
}

# Episode 06's second zone, the one the registered domain points at.
resource "aws_route53_zone" "main" {
  name    = var.domain_name
  comment = ""
}

# Episode 07: made by CloudFront, in us-east-1 (the provider's region).
resource "aws_acm_certificate" "site" {
  domain_name               = var.domain_name
  subject_alternative_names = ["www.${var.domain_name}"]
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

# ACM checks these at every renewal, so they stay for good.
resource "aws_route53_record" "validation" {
  for_each = local.site_names

  zone_id = aws_route53_zone.main.zone_id
  name    = local.validation[each.key].resource_record_name
  type    = local.validation[each.key].resource_record_type
  ttl     = 300
  records = [local.validation[each.key].resource_record_value]
}

# Episode 07's "Route domain to CloudFront": IPv4 and IPv6, both names.
resource "aws_route53_record" "site_a" {
  for_each = local.site_names

  zone_id = aws_route53_zone.main.zone_id
  name    = each.key
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.storefront.domain_name
    zone_id                = aws_cloudfront_distribution.storefront.hosted_zone_id
    evaluate_target_health = false
  }
}

resource "aws_route53_record" "site_aaaa" {
  for_each = local.site_names

  zone_id = aws_route53_zone.main.zone_id
  name    = each.key
  type    = "AAAA"

  alias {
    name                   = aws_cloudfront_distribution.storefront.domain_name
    zone_id                = aws_cloudfront_distribution.storefront.hosted_zone_id
    evaluate_target_health = false
  }
}
