# Terraform: GCP OAuth client for Google Sign-in

This small Terraform module creates an OAuth brand and an OAuth client (IAP client) in Google Cloud and outputs a `client_id` and `client_secret` you can use as `GOOGLE_CLIENT_ID` for the Lambda.

Usage

1. Configure your Google provider credentials (eg via `gcloud auth application-default login` or a service account JSON and `GOOGLE_APPLICATION_CREDENTIALS` environment variable).
2. From this directory run:

```bash
terraform init
terraform apply -var="project_id=your-project" -var="support_email=you@example.com"
```

3. After apply, note the `client_id` output and copy it into your AWS Terraform or Lambda env var `GOOGLE_CLIENT_ID`.

Caveats & Notes
- The IAP OAuth admin APIs are being deprecated and creation of brands/clients may be restricted or require console/manual steps in some organizations. If `google_iap_brand` or `google_iap_client` fails, create the OAuth client manually in the GCP Console and paste the Client ID into your AWS Lambda configuration.
- The OAuth consent screen for external apps often requires adding test users (or verification) — that is done via the GCP Console UI and may require manual steps.
- Treat the `client_secret` as sensitive. Use Secret Manager or another secure store rather than embedding it in plaintext in other infrastructure code.

How to wire into AWS
- After you have a `client_id` (copy from Terraform output), set the Lambda env var `GOOGLE_CLIENT_ID` (we already added `GOOGLE_CLIENT_ID` in `terraform/aws/lambda.tf`). You can import the value manually or use cross-project automation.

If you want, I can add automation to export this value to an SSM parameter or to render a small script that updates the AWS Terraform variables automatically. Which would you prefer?