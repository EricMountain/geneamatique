Lambda handler serves static files from the `dist/` directory and authenticates requests (except icons) using an API key stored in DynamoDB.

Environment variables:
- `API_KEYS_TABLE` - The DynamoDB table name containing API keys (primary key `api_key`)
- `ALLOWED_USERS_TABLE` - (optional) The DynamoDB table name containing allowed Google users (primary key `email`)
- `GOOGLE_CLIENT_ID` - (optional) OAuth2 Client ID used to validate Google ID tokens
- `GOOGLE_CLIENT_SECRET` - (optional) OAuth2 client secret used for server-side authorization-code exchanges

**If `ALLOWED_USERS_TABLE` and `GOOGLE_CLIENT_ID` are set**, the Lambda will accept `Authorization: Bearer <Google ID token>` headers. It verifies the ID token audience using `GOOGLE_CLIENT_ID` and then checks that the authenticated user's email exists in `ALLOWED_USERS_TABLE` (partition key `email` as a string). If Google auth fails, the Lambda falls back to the `API_KEYS_TABLE` check for backward compatibility.

Automatic login behavior:
- If a user visits the site without an API key nor an active id_token cookie, the Lambda will redirect the browser to Google's OAuth consent page to start the authorization-code flow (server-side). After the user signs in, Google will redirect back to `https://<function_url>/oauth2callback` which the Lambda handles by exchanging the code for an ID token, verifying it, checking the email in `ALLOWED_USERS_TABLE`, and then setting a secure `id_token` cookie for subsequent requests.

Notes:
- For the server-side flow to work you must also provide `GOOGLE_CLIENT_SECRET` (set via Terraform or manually in the Lambda console) and configure the OAuth client in GCP to include `https://<function_url>/oauth2callback` as an authorized redirect URI.
- If you prefer a client-side-only flow (no server-side `GOOGLE_CLIENT_SECRET`), you can implement client-side sign-in and send the ID token to the Lambda as `Authorization: Bearer <id_token>` instead.
Build / deploy steps:
1. From repo root run `./build_pwa.sh` to build the Vite app into `lambda/dist` and install lambda deps.
2. Include your SQLite database in the Lambda package under `dist/data/genealogy.db` (this file is used at runtime to serve API requests). Do NOT commit private data to the repo — keep real DBs out of source control and inject the file at packaging time.
3. Run `terraform apply` in `terraform/aws` to create the lambda and the `api-keys` DynamoDB table.
4. Provision an API key into DynamoDB (example tool: `node create_api_key.js <key>` with `API_KEYS_TABLE` env set or by using AWS console).

- To add a Google-allowed user, use `node create_allowed_user.js <table> <email>` or set `ALLOWED_USERS_TABLE` and run `node create_allowed_user.js <email>`.

Requests to the site must present the API key via `x-api-key` header or `Authorization: ApiKey <key>`.

API endpoints:
- `GET /api/individuals?q=<query>` — search individuals by name (substring) or old_id (numeric). Returns JSON array of matches: `{ id, canonical_name, name_comment, date_of_birth }`.
- `GET /api/tree?id=<db_id>` — generate an ancestor tree JSON for the chosen individual using the SQLite DB. Returns the nested node structure used by the frontend viewer. (Note: descendant trees and `max_depth` query params are no longer supported.)

Security: API endpoints are authenticated with the same API key mechanism as static content.

### Local development
For local development there's a tiny Express-based dev server that forwards HTTP requests to the Lambda handler and runs with `LOCAL_DEV=1` so authentication is disabled for convenience.

- Install JS deps: `(cd lambda && npm install)`
- Start the local lambda dev server: `(cd lambda && npm run dev)`. Default port: `3001` (override with `PORT=...`).
- To run both frontend and backend at once use `make dev_local` from the repo root — this runs the lambda dev server in background and the Vite frontend in the foreground.

The Lambda handler contains a safety check and will refuse to run if `LOCAL_DEV` is set in an actual Lambda environment to prevent disabling authentication in production.
