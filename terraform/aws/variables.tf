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
  description = "(optional) Google OAuth client secret to allow server-side code exchange for ID tokens"
  type        = string
  default     = ""
  sensitive   = true
}
