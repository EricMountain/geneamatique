#!/bin/bash
# Convenience wrapper to search for individuals by location

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ $# -eq 0 ]; then
    echo "Search for individuals by event location"
    echo ""
    echo "Usage: $0 <location_string>"
    echo "   or: $0 --null-coords"
    echo ""
    echo "Examples:"
    echo "  $0 'Paris'           # Search for individuals with events in Paris"
    echo "  $0 'Londres'         # Search for individuals with events in Londres"
    echo "  $0 'New York'        # Search for individuals with events in New York"
    echo "  $0 --null-coords     # Report individuals with events in uncoded locations"
    exit 1
fi

python3 "$SCRIPT_DIR/import_tools/search_individuals_by_location.py" "$@"
