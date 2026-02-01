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

# Lambda function and URL
resource "aws_lambda_function" "genealogy" {
  function_name    = var.lambda_name
  role             = aws_iam_role.lambda.arn
  handler          = "handler.handler"
  runtime          = "nodejs22.x"
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  publish          = true
  timeout          = 15
  environment {
    variables = {
      API_KEYS_TABLE     = aws_dynamodb_table.api_keys.name
      ALLOWED_USERS_TABLE = aws_dynamodb_table.allowed_users.name
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

output "lambda_name" {
  value = aws_lambda_function.genealogy.function_name
}

output "role_name" {
  value = aws_iam_role.lambda.name
}
