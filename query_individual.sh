#!/usr/bin/env bash
# Script to import data into the genealogy database

set -euo pipefail

.venv/bin/python import_tools/query_genealogy.py "$@"
