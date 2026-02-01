variable "project_id" {
  description = "GCP project id where the OAuth client will be created"
  type        = string
}

variable "support_email" {
  description = "Support email to show on OAuth consent screen (must be a real user or group email)"
  type        = string
}

variable "application_title" {
  description = "Application title to display on the consent screen"
  type        = string
  default     = "Geneamatique OAuth Client"
}

variable "client_display_name" {
  description = "Human-friendly name for the OAuth client"
  type        = string
  default     = "Geneamatique web client"
}
