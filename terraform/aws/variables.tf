variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "eu-west-3"
}

variable "lambda_name" {
  description = "Lambda function name"
  type        = string
  default     = "genealogy"
}

variable "lambda_architecture" {
  description = "Lambda CPU architecture (x86_64 or arm64)"
  type        = string
  default     = "x86_64"

  validation {
    condition     = contains(["x86_64", "arm64"], var.lambda_architecture)
    error_message = "lambda_architecture must be one of: x86_64, arm64."
  }
}

variable "dynamodb_table_prefix" {
  description = "Prefix to use for DynamoDB table names. If empty, falls back to lambda_name."
  type        = string
  default     = "genealogy"
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 1
}

variable "google_client_secret" {
  description = "(optional) Google OAuth client secret to allow server-side code exchange for ID tokens."
  # When this variable is an empty string Terraform will *not* destroy an
  # existing SSM parameter; the provider uses a data lookup and a lifecycle
  # rule to keep previously-created parameters and policies in place.
  type      = string
  default   = ""
  sensitive = true
}

variable "google_client_id" {
  description = "(optional) Google OAuth client id (used by the client-side GIS flow)"
  type        = string
  default     = ""
}

variable "cloudfront_enabled" {
  description = "Enable a CloudFront distribution in front of the Lambda Function URL"
  type        = bool
  default     = false
}

variable "cloudfront_alternate_domain_names" {
  description = "List of alternate domain names (CNAMEs) you will use for the CloudFront distribution (e.g., [\"genealogy.example.com\"]). If empty no aliases are configured."
  type        = list(string)
  default     = [""]
}

variable "cloudfront_acm_certificate_arn" {
  description = "(optional) ACM certificate ARN (must be in us-east-1) to attach to CloudFront for custom domains"
  type        = string
  default     = ""
}

variable "cloudfront_price_class" {
  description = "CloudFront price class to use"
  type        = string
  default     = "PriceClass_100"
}

variable "cloudfront_auto_provision_cert" {
  description = "If true and a domain is provided, attempt to provision an ACM certificate in us-east-1 and validate via Route53"
  type        = bool
  default     = false
}

variable "cloudfront_hosted_zone_id" {
  description = "(optional) Route53 hosted zone id to use for DNS validation when auto-provisioning ACM certs"
  type        = string
  default     = ""
}
