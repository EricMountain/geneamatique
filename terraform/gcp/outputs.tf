output "client_id" {
  description = "OAuth2 Client ID (use as GOOGLE_CLIENT_ID in AWS Lambda)"
  value       = google_iap_client.client.client_id
}

output "client_secret" {
  description = "Client secret (sensitive) - store in Secret Manager or your secure store"
  value       = google_iap_client.client.secret
  sensitive   = true
}
