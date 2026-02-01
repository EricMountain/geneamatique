Lambda handler serves static files from the `dist/` directory and authenticates requests (except icons) using an API key stored in DynamoDB.

Environment variables:
- `API_KEYS_TABLE` - The DynamoDB table name containing API keys (primary key `api_key`)

Build / deploy steps:
1. From repo root run `./build_pwa.sh` to build the Vite app into `lambda/dist` and install lambda deps.
2. Include your SQLite database in the Lambda package under `dist/data/genealogy.db` (this file is used at runtime to serve API requests). Do NOT commit private data to the repo — keep real DBs out of source control and inject the file at packaging time.
3. Run `terraform apply` in `terraform/aws` to create the lambda and the `api-keys` DynamoDB table.
4. Provision an API key into DynamoDB (example tool: `node create_api_key.js <key>` with `API_KEYS_TABLE` env set or by using AWS console).

Requests to the site must present the API key via `x-api-key` header or `Authorization: ApiKey <key>`.

API endpoints:
- `GET /api/individuals?q=<query>` — search individuals by name (substring) or old_id (numeric). Returns JSON array of matches: `{ id, family_tree, old_id, canonical_name, name_comment, date_of_birth }`.
- `GET /api/tree?id=<db_id>&type=ancestor|descendant&family_tree=<tree>&max_depth=<N>` — generate tree JSON for the chosen individual using the SQLite DB. Returns the nested node structure used by the frontend viewer.

Security: API endpoints are authenticated with the same API key mechanism as static content.
