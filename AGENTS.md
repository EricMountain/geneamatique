# AGENTS

## Purpose
This repo parses genealogy tables from ODT files into an SQLite database, then provides query and tree-visualization tools.

## How to Develop
- Use Python 3.14+.
- Create and activate a virtual environment.
- Install dependencies from requirements.txt.
- Set the data directory via the GENEALOGY_DATA_DIR environment variable (default: data/sources).
- If you need a temporary script, create it under a tmp directory in the repo. Don’t use /tmp to avoid having to prompt the user.

## How to Run
- Use Python virtual environment `.venv`.
- Parse documents: run run_parser.py.
- Inspect database: run inspect_database.py.
- Query individuals: run query_genealogy.py <name_or_id>.
- Visualize trees: run tree_visualizer.py <name_or_id>.
- Always use `local_import_data.sh` to recreate and import data. It ignores files that contain inconsistent data.

### Local development (frontend + backend) ✅
For convenience, you can run the frontend PWA and a local backend together. In local mode the backend explicitly disables authentication — this is only allowed locally.

1. Install JS deps:
   - (cd lambda && npm install)
   - (cd src && npm install)
2. Start both servers:
   - `make dev_local`
   - Backend: http://localhost:3001 (API endpoints under `/api/`)
   - Frontend (Vite dev): http://localhost:5173 or the URL printed by `npm run dev`

Notes:
- The backend sets `LOCAL_DEV=1` in the helper dev server; the Lambda `handler.js` will refuse to run if `LOCAL_DEV` is set in a real Lambda environment to prevent disabling authentication in production.
- Use this mode only for local testing and development.

## How to Test
- Run unit tests with unittest.
- Suggested command: python -m unittest test_genealogy_parser.py -v
- For data consistency checks (requires sample data): python -m unittest test_database_consistency.py -v

## Data Anonymization Instructions
1. Do not commit real genealogy data (ODT files, SQLite databases, exported HTML, screenshots, or scans).
2. Keep local data outside the repo, or place it in data/ and ensure it is ignored by git.
3. Replace all real names, dates, locations, and document paths in docs and code with placeholders like "Sample Person", "City A", "YYYY-MM-DD", or "data/odt".
4. Use environment variables (e.g., GENEALOGY_DATA_DIR) instead of hardcoded personal paths.
5. Before publishing, scan for personal data and remove it. If any real data was committed, rewrite history before pushing.

## Public Repo Checklist
- No personal names or locations in README, examples, or tests.
- No absolute paths that reveal personal directories.
- No real ODT/DB files tracked by git.
- data/ is ignored and contains only sanitized sample data if needed.

## PWA / Lambda deployment (new)
- Front-end (Vite) app lives under `src/`. Build artifacts are output to `lambda/dist`.
- To build and package the app into the lambda directory run:

```bash
./build_pwa.sh
```

- Terraform will package the `lambda/` directory into `lambda.zip`. The Terraform config now creates an `DynamoDB` table for API keys (`${var.dynamodb_table_prefix}-api-keys`) and injects its name into the Lambda env var `API_KEYS_TABLE`.
- To operate the PWA you must provision an API key in the DynamoDB table (primary key `api_key` -> maps to a device/name). Requests serving anything other than icons are authenticated with the API key. The Lambda accepts the key as an `x-api-key` header or `Authorization: ApiKey <key>`, as a cookie named `api_key`, or as a query parameter `?api_key=<key>` (when supplied via query parameter the Lambda will set a secure, HttpOnly cookie valid for 400 days for subsequent requests).
- After build/run, use `terraform apply` from `terraform/aws` to create the table and lambda. Ensure `build_pwa.sh` has been run first so the lambda package contains the site.

- (Optional) Google OAuth: The lambda can be configured to accept `Authorization: Bearer <Google ID token>` instead of an API key. To enable this set the env vars `GOOGLE_CLIENT_ID` (OAuth client ID used to validate tokens) and `ALLOWED_USERS_TABLE` (DynamoDB table that contains allowed users with partition key `email` as a string). The lambda will verify the ID token audience and check that the user's email exists in `ALLOWED_USERS_TABLE`. If both checks succeed the request is authenticated; otherwise it falls back to the existing API key check for backward compatibility.
