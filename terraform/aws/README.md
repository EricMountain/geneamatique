# Terraform: AWS helpers for Lambda + CloudFront

This folder contains Terraform code to provision the Lambda function (packaged from the `lambda/` directory), its DynamoDB tables, and optional CloudFront distribution in front of the Function URL.

## CloudFront usage

- Enable the CloudFront distribution by setting `cloudfront_enabled = true` and provide your domain name(s) in `cloudfront_alternate_domain_names`.
- Provide an ACM certificate ARN in `cloudfront_acm_certificate_arn` (must be in `us-east-1` for CloudFront), OR enable automatic provisioning with:
  - `cloudfront_auto_provision_cert = true`
  - `cloudfront_hosted_zone_id = <your route53 hosted zone id>`

## Notes

- CloudFront requires the certificate to be in `us-east-1` when used with edge distributions.
- If you use CloudFront with a custom domain, add the custom origin (`https://<your-domain>`) to your Google OAuth client as an "Authorized JavaScript origin" and add `https://<your-domain>/oauth2callback` as an "Authorized redirect URI".
- For a custom domain, ensure the proxy forwards the public host header in `X-Forwarded-Host` so the Lambda can construct correct redirect URIs.

## Advanced CloudFront & ACM behavior

- Automatic ACM provisioning: when `cloudfront_auto_provision_cert = true` Terraform will attempt to create an ACM certificate in `us-east-1` and validate it via DNS. If you do not provide `cloudfront_hosted_zone_id` the module will try to auto-detect a Route53 hosted zone using the apex of the first entry in `cloudfront_alternate_domain_names` (simple heuristic: take the last two labels, e.g. `genealogy.example.com` -> `example.com`). The auto-discovery only searches the current AWS account and credentials; if the zone is in a different account you must set `cloudfront_hosted_zone_id` manually.

- Output: the Terraform output `used_cloudfront_hosted_zone_id` reports the hosted zone id that was used (empty if none was found/used).

- Host header handling: Lambda Function URLs require the Host header to match the function URL hostname. The CloudFront setup is configured to *not* forward the viewer `Host` header (we exclude `Host`) but does forward `X-Forwarded-Host` and other viewer headers (including `Authorization`) so the Lambda can build correct redirects while still receiving a Host acceptable to the Function URL.

- Cache policy: CloudFront requires a cache policy when an origin request policy is attached. AWS disallows certain forwarding options when caching is completely disabled (TTLs = 0), so we use a very small TTL (1s) to effectively disable caching while permitting header/cookie forwarding.

- Troubleshooting & tips:
  - If users see a cached 403 after configuration changes, invalidate CloudFront (e.g., `aws cloudfront create-invalidation --distribution-id <id> --paths '/*'`).
  - If automatic hosted-zone discovery fails, set `cloudfront_hosted_zone_id = "Z..."` in `terraform.tfvars` and re-run plan/apply so the Route53 validation records and the A/ALIAS entry are created.
  - Ensure your Google OAuth client has both the CloudFront origin (`https://<your-domain>`) set as an Authorized JavaScript origin and `https://<your-domain>/oauth2callback` as an Authorized redirect URI.

## OAuth2

The `/oauth2callback` in `handler.js` needs both the `GOOGLE_CLIENT_ID` (public) and the `GOOGLE_CLIENT_SECRET` (private…). This will be stored in SSM for retrieval by the lambda on cold start:

```shell
cd terraform/aws && terraform apply -var='google_client_secret=YOUR_SECRET'
```

The helper `scripts/terraform_with_op.sh` provides a safe wrapper that obtains the secret from 1Password and avoids it ending up in shell history.
