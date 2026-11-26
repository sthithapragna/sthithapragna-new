output "site_bucket" {
  value = aws_s3_bucket.site.bucket
}

output "distribution_id" {
  value = aws_cloudfront_distribution.storefront.id
}

output "name_servers" {
  description = "Must match the registered domain's name servers (episode 06)"
  value       = aws_route53_zone.main.name_servers
}
