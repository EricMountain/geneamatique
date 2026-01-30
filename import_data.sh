#!/usr/bin/env bash
# Script to import data into the genealogy database

set -euo pipefail

rm -f data/genealogy.db
.venv/bin/python import_tools/run_parser.py
