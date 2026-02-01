Lambda handler serves static files from the `dist/` directory and authenticates requests (except icons) using an API key stored in DynamoDB.

Environment variables:
- `API_KEYS_TABLE` - The DynamoDB table name containing API keys (primary key `api_key`)

Build / deploy steps:
1. From repo root run `./build_pwa.sh` to build the Vite app into `lambda/dist` and install lambda deps.
2. Run `terraform apply` in `terraform/aws` to create the lambda and the `api-keys` DynamoDB table.
3. Provision an API key into DynamoDB (example tool: `node create_api_key.js <key>` with `API_KEYS_TABLE` env set or by using AWS console).

Requests to the site must present the API key via `x-api-key` header or `Authorization: ApiKey <key>`.
