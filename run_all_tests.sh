#!/bin/bash
# Script to run all Python tests in the genealogy project

set -e  # Exit on error

cd "$(dirname "$0")"

echo "========================================"
echo "Running All Python Tests"
echo "========================================"
echo ""

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Run all test modules
echo "1. Running genealogy parser tests..."
python -m unittest import_tools.test_genealogy_parser -v
echo ""

echo "2. Running database consistency tests..."
python -m unittest import_tools.test_database_consistency -v
echo ""

echo "3. Running calendar utility tests..."
python -m unittest import_tools.calendar.test_util -v
echo ""

echo "========================================"
echo "All tests completed successfully!"
echo "========================================"
