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
- Parse documents: run run_parser.py.
- Inspect database: run inspect_database.py.
- Query individuals: run query_genealogy.py <name_or_id>.
- Visualize trees: run tree_visualizer.py <name_or_id>.

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
