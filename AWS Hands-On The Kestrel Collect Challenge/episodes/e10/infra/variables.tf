variable "domain_name" {
  description = "Your domain, for example kestrelcollect.com"
  type        = string
}

variable "site_suffix" {
  description = "The random end of the site bucket's name: COLLECT_SUFFIX in .env"
  type        = string
}

variable "web_acl_name" {
  description = "The web ACL that the CloudFront Free plan made in episode 05"
  type        = string
}
