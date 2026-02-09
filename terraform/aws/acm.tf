provider "aws" {
  alias   = "us_east_1"
  region  = "us-east-1"
  profile = "eric"
}

# Derive a likely Route53 hosted zone name from the first alternate domain
# (simple heuristic: take the last two labels, e.g. "genealogy.example.com" -> "example.com").
locals {
  first_alias        = length(var.cloudfront_alternate_domain_names) > 0 ? var.cloudfront_alternate_domain_names[0] : ""
  first_alias_labels = split(".", local.first_alias)
  root_zone_guess    = length(local.first_alias_labels) >= 2 ? join(".", slice(local.first_alias_labels, length(local.first_alias_labels) - 2, length(local.first_alias_labels))) : local.first_alias
}

# If the user hasn't supplied an explicit hosted zone id, attempt to look up a
# Route53 hosted zone for the derived root zone so we can perform DNS validation.
# This only runs when auto-provisioning is enabled and a domain is provided.
data "aws_route53_zone" "selected" {
  count        = (var.cloudfront_auto_provision_cert && var.cloudfront_hosted_zone_id == "" && local.root_zone_guess != "") ? 1 : 0
  name         = "${local.root_zone_guess}."
  private_zone = false
}

# Auto-provision a public ACM certificate in us-east-1 when requested. The
# certificate will be created when auto-provision is enabled and either an
# explicit hosted zone id is provided, or the derived zone was found.
resource "aws_acm_certificate" "cloudfront" {
  provider = aws.us_east_1
  count    = (var.cloudfront_auto_provision_cert && length(var.cloudfront_alternate_domain_names) > 0 && (var.cloudfront_hosted_zone_id != "" || length(data.aws_route53_zone.selected) > 0)) ? 1 : 0

  domain_name               = var.cloudfront_alternate_domain_names[0]
  subject_alternative_names = length(var.cloudfront_alternate_domain_names) > 1 ? slice(var.cloudfront_alternate_domain_names, 1, length(var.cloudfront_alternate_domain_names)) : []
  validation_method         = "DNS"
  lifecycle {
    create_before_destroy = true
  }
}

# Compute the hosted zone id we'll use (either the explicit variable or the discovered zone)
locals {
  used_cloudfront_hosted_zone_id = var.cloudfront_hosted_zone_id != "" ? var.cloudfront_hosted_zone_id : (length(data.aws_route53_zone.selected) > 0 ? data.aws_route53_zone.selected[0].zone_id : "")
}

# Create Route53 validation records for each domain validation option
resource "aws_route53_record" "cert_validation" {
  # domain_validation_options is a set; iterate using for_each to safely access elements
  for_each = aws_acm_certificate.cloudfront.*.domain_validation_options != [] ? { for dvo in aws_acm_certificate.cloudfront[0].domain_validation_options : dvo.domain_name => dvo } : {}

  zone_id = local.used_cloudfront_hosted_zone_id

  name    = each.value.resource_record_name
  type    = each.value.resource_record_type
  records = [each.value.resource_record_value]
  ttl     = 60
}

# Wait for certificate validation
resource "aws_acm_certificate_validation" "cloudfront" {
  provider = aws.us_east_1
  count    = aws_acm_certificate.cloudfront.*.arn != [] ? 1 : 0

  certificate_arn         = aws_acm_certificate.cloudfront[0].arn
  validation_record_fqdns = [for r in values(aws_route53_record.cert_validation) : r.fqdn]
}

output "provisioned_acm_certificate_arn" {
  value       = aws_acm_certificate.cloudfront.*.arn
  description = "The ARN of the provisioned ACM certificate in us-east-1 (if auto-provisioned)"
}

resource "aws_route53_record" "cloudfront_alias" {
  count = (var.cloudfront_enabled && length(var.cloudfront_alternate_domain_names) > 0 && local.used_cloudfront_hosted_zone_id != "") ? 1 : 0

  zone_id = local.used_cloudfront_hosted_zone_id
  name    = var.cloudfront_alternate_domain_names[0]
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.cdn[0].domain_name
    zone_id                = aws_cloudfront_distribution.cdn[0].hosted_zone_id
    evaluate_target_health = false
  }

  # Ensure CloudFront distribution exists before creating alias
  depends_on = [aws_cloudfront_distribution.cdn]
}

output "used_cloudfront_hosted_zone_id" {
  value       = local.used_cloudfront_hosted_zone_id
  description = "The Route53 hosted zone id used for ACM validation (empty if none was used or found)"
}
