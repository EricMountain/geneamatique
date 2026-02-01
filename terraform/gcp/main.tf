provider "google" {
  project = var.project_id
}

# enable the IAP API (required to create brands/clients)
resource "google_project_service" "iap" {
  project = var.project_id
  service = "iap.googleapis.com"
}

# Create an OAuth consent "Brand" used by IAP OAuth clients.
# NOTE: creating an external brand programmatically may not be possible in all orgs.
resource "google_iap_brand" "brand" {
  support_email     = var.support_email
  application_title = var.application_title
  project           = google_project_service.iap.project
}

# Create an IAP OAuth client which provides a client_id and secret.
resource "google_iap_client" "client" {
  display_name = var.client_display_name
  brand        = google_iap_brand.brand.name
  depends_on   = [google_iap_brand.brand]
}

output "google_client_id" {
  value       = google_iap_client.client.client_id
  description = "OAuth Client ID (use as GOOGLE_CLIENT_ID in the Lambda)"
}

output "google_client_secret" {
  value       = google_iap_client.client.secret
  description = "OAuth Client secret (sensitive). Store securely."
  sensitive   = true
}
