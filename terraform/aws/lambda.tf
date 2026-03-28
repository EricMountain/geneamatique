# Package Lambda from local source
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../../lambda"
  output_path = "${path.module}/lambda.zip"
}

# IAM role and policies
resource "aws_iam_role" "lambda" {
  name               = "${var.lambda_name}-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy" "lambda_logs" {
  name   = "${var.lambda_name}-logs"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.lambda_logs.json
}

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

data "aws_iam_policy_document" "lambda_logs" {
  statement {
    effect    = "Allow"
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:*:*:*"]
  }
}

# Logging
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.lambda_name}"
  retention_in_days = var.log_retention_days
}

# DynamoDB table name prefix: use explicit var if provided, otherwise fall back to lambda_name
locals {
  dynamodb_table_prefix = var.dynamodb_table_prefix != "" ? var.dynamodb_table_prefix : var.lambda_name

  # Helper to compute a safe origin domain name for CloudFront derived from the
  # Lambda Function URL (strip https:// and any trailing slash).
  lambda_origin_raw    = replace(aws_lambda_function_url.genealogy.function_url, "https://", "")
  lambda_origin_domain = endswith(local.lambda_origin_raw, "/") ? substr(local.lambda_origin_raw, 0, length(local.lambda_origin_raw) - 1) : local.lambda_origin_raw
}

# DynamoDB table to hold API keys for simple authentication
resource "aws_dynamodb_table" "api_keys" {
  name         = "${local.dynamodb_table_prefix}-api-keys"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "api_key"

  attribute {
    name = "api_key"
    type = "S"
  }
}

# DynamoDB table to hold allowed Google user emails (partition key: email)
resource "aws_dynamodb_table" "allowed_users" {
  name         = "${local.dynamodb_table_prefix}-allowed-users"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "email"

  attribute {
    name = "email"
    type = "S"
  }
}

# Allow lambda role to read the tables (GetItem/Query/Scan)
resource "aws_iam_role_policy" "lambda_dynamodb" {
  name   = "${var.lambda_name}-dynamodb"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.lambda_dynamodb.json
}

data "aws_iam_policy_document" "lambda_dynamodb" {
  statement {
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:Query",
      "dynamodb:Scan"
    ]

    resources = [
      aws_dynamodb_table.api_keys.arn,
      "${aws_dynamodb_table.api_keys.arn}/*",
      aws_dynamodb_table.allowed_users.arn,
      "${aws_dynamodb_table.allowed_users.arn}/*"
    ]
  }
}

# SSM SecureString parameter to store the Google OAuth client secret.
# The Lambda reads this at cold-start instead of receiving the secret via
# a plain-text environment variable (which would be visible in the console,
# Terraform state, and CloudWatch).

# If the caller does not supply a value we still want to manage the existing
# parameter and *not* destroy it.  The `data.aws_ssm_parameter.maybe` block
# will succeed when the parameter already exists, allowing the count
# expressions below to stay at 1 even when the incoming var is empty.
#
# We also add lifecycle rules so that once created the value is ignored and
# the resource cannot be destroyed accidentally.

data "aws_ssm_parameter" "maybe" {
  count           = var.google_client_secret == "" ? 1 : 0
  name            = "/${var.lambda_name}/google-client-secret"
  with_decryption = true
}

resource "aws_ssm_parameter" "google_client_secret" {
  count = (var.google_client_secret != "" || length(data.aws_ssm_parameter.maybe) > 0) ? 1 : 0

  name        = "/${var.lambda_name}/google-client-secret"
  description = "Google OAuth client secret for server-side code exchange"
  type        = "SecureString"

  value = var.google_client_secret != "" ? var.google_client_secret : data.aws_ssm_parameter.maybe[0].value

  # prevent_destroy stops accidental removal when the var is later omitted.
  lifecycle {
    prevent_destroy = true
    # once created we do not want Terraform to overwrite the secret with a
    # blank value if the variable later becomes empty.
    ignore_changes = [value]
  }

  # Uses the free AWS-managed aws/ssm KMS key by default.
  # To use a custom CMK, set: key_id = aws_kms_key.my_key.arn
}

# Allow the Lambda role to read the SSM parameter and decrypt with the
# default aws/ssm KMS key (both free-tier).  Policy is retained even if the
# client secret is later removed from the Terraform command line.
resource "aws_iam_role_policy" "lambda_ssm" {
  count  = (var.google_client_secret != "" || length(data.aws_ssm_parameter.maybe) > 0) ? 1 : 0
  name   = "${var.lambda_name}-ssm"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.lambda_ssm[0].json

  lifecycle {
    prevent_destroy = true
  }
}

data "aws_iam_policy_document" "lambda_ssm" {
  count = (var.google_client_secret != "" || length(data.aws_ssm_parameter.maybe) > 0) ? 1 : 0

  statement {
    effect    = "Allow"
    actions   = ["ssm:GetParameter"]
    resources = [aws_ssm_parameter.google_client_secret[0].arn]
  }
}

# Lambda function and URL
resource "aws_lambda_function" "genealogy" {
  function_name    = var.lambda_name
  role             = aws_iam_role.lambda.arn
  handler          = "handler.handler"
  runtime          = "nodejs22.x"
  architectures    = [var.lambda_architecture]
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  publish          = true
  timeout          = 15
  environment {
    variables = {
      API_KEYS_TABLE      = aws_dynamodb_table.api_keys.name
      ALLOWED_USERS_TABLE = aws_dynamodb_table.allowed_users.name
      GOOGLE_CLIENT_ID    = var.google_client_id
      # The secret is stored in SSM SecureString; the Lambda reads it at cold start.
      # Pass the SSM parameter name so the handler knows where to look.
      GOOGLE_CLIENT_SECRET_SSM = var.google_client_secret != "" ? aws_ssm_parameter.google_client_secret[0].name : (length(data.aws_ssm_parameter.maybe) > 0 ? data.aws_ssm_parameter.maybe[0].name : "")
    }
  }
}

resource "aws_lambda_function_url" "genealogy" {
  function_name      = aws_lambda_function.genealogy.arn
  authorization_type = "NONE"

  cors {
    allow_credentials = true
    allow_headers     = ["content-type", "x-api-key", "authorization"]
    allow_methods     = ["GET", "POST"]
    allow_origins     = ["*"]
  }
}

output "function_url" {
  value = aws_lambda_function_url.genealogy.function_url
}

# CloudFront distribution in front of the Lambda Function URL (optional)
# Origin request policy to forward Host header, Authorization, cookies and query strings to the origin
resource "aws_cloudfront_origin_request_policy" "forward_host" {
  count   = var.cloudfront_enabled ? 1 : 0
  name    = "${var.lambda_name}-forward-host"
  comment = "Forward Host, Authorization and cookies to the origin"

  cookies_config {
    cookie_behavior = "all"
  }

  headers_config {
    # Forward all viewer-supplied headers except `Host` so Authorization and
    # X-Forwarded-* are sent to the origin, but Host remains the origin domain
    # which Lambda Function URLs require.
    header_behavior = "allExcept"
    headers {
      items = ["Host"]
    }
  }

  query_strings_config {
    query_string_behavior = "all"
  }
}

# A simple cache policy that disables caching. Required because attaching an
# origin request policy necessitates a separate cache or response policy.
resource "aws_cloudfront_cache_policy" "no_cache" {
  count   = var.cloudfront_enabled ? 1 : 0
  name    = "${var.lambda_name}-no-cache"
  comment = "Cache policy that disables caching and forwards viewer headers/cookies/queries"

  # Use a minimal (1s) default TTL. AWS does not allow header/cookie
  # forwarding to be configured when caching is disabled (all TTLs=0), so we
  # keep a tiny TTL to permit forwarding settings while effectively disabling
  # caching for our use-case.
  default_ttl = 1
  max_ttl     = 1
  min_ttl     = 0

  parameters_in_cache_key_and_forwarded_to_origin {
    cookies_config {
      cookie_behavior = "all"
    }

    headers_config {
      header_behavior = "none"
    }

    query_strings_config {
      query_string_behavior = "all"
    }
    enable_accept_encoding_gzip   = false
    enable_accept_encoding_brotli = false
  }
}

resource "aws_cloudfront_distribution" "cdn" {
  count = var.cloudfront_enabled ? 1 : 0

  enabled     = true
  price_class = var.cloudfront_price_class

  origin {
    # Strip the https:// prefix and any trailing slash so the origin domain is a
    # bare domain name (CloudFront rejects values that contain a trailing '/').
    domain_name = local.lambda_origin_domain
    origin_id   = "lambda-function-url-origin"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }

    # CloudFront replaces the viewer's Host header with the origin domain, so
    # the Lambda cannot tell which public hostname was used. Inject the custom
    # domain as X-Forwarded-Host so the handler can reconstruct correct OAuth
    # redirect URIs and other host-dependent URLs.
    dynamic "custom_header" {
      for_each = length(var.cloudfront_alternate_domain_names) > 0 && var.cloudfront_alternate_domain_names[0] != "" ? [var.cloudfront_alternate_domain_names[0]] : []
      content {
        name  = "X-Forwarded-Host"
        value = custom_header.value
      }
    }
  }

  default_cache_behavior {
    allowed_methods = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods  = ["GET", "HEAD"]

    target_origin_id         = "lambda-function-url-origin"
    origin_request_policy_id = aws_cloudfront_origin_request_policy.forward_host[0].id
    cache_policy_id          = aws_cloudfront_cache_policy.no_cache[0].id

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 0
    max_ttl                = 0
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  dynamic "viewer_certificate" {
    for_each = var.cloudfront_acm_certificate_arn != "" ? [1] : (length(aws_acm_certificate.cloudfront) > 0 ? [1] : [])
    content {
      acm_certificate_arn      = var.cloudfront_acm_certificate_arn != "" ? var.cloudfront_acm_certificate_arn : aws_acm_certificate.cloudfront[0].arn
      ssl_support_method       = "sni-only"
      minimum_protocol_version = "TLSv1.2_2019"
    }
  }

  aliases = var.cloudfront_alternate_domain_names

  # Basic logging (off by default — can be enabled later)
  # price_class etc already set above
}

output "cloudfront_domain_name" {
  value       = var.cloudfront_enabled ? aws_cloudfront_distribution.cdn[0].domain_name : ""
  description = "The CloudFront distribution domain name (useful when not using a custom domain)"
}

output "lambda_name" {
  value = aws_lambda_function.genealogy.function_name
}

output "role_name" {
  value = aws_iam_role.lambda.name
}
