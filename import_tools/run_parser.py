#!/usr/bin/env python3
"""Script to run the genealogy parser on all ODT files in the directory."""

from genealogy_parser import create_database, parse_documents, store_data, get_date_warnings, clear_date_warnings
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    folder_path = os.environ.get('GENEALOGY_DATA_DIR', 'data/sources')
    db_name = 'data/genealogy.db'

    print("="*80)
    print("GENEALOGY PARSER")
    print("="*80)

    print("\n1. Creating database...")
    create_database(db_name)
    print("   ✓ Database created")

    print(f"\n2. Parsing documents from: {folder_path}")
    clear_date_warnings()  # Clear any previous warnings
    individuals = parse_documents(folder_path)
    print(f"   ✓ Found {len(individuals)} individuals across all documents")

    print("\n3. Storing data in database...")
    num_individuals, num_relationships = store_data(individuals, db_name)
    print(f"   ✓ Stored {num_individuals} unique individuals")
    print(f"   ✓ Inferred {num_relationships} parent-child relationships")

    print("\n" + "="*80)
    print("COMPLETE!")
    print("="*80)
    print(f"Database: {db_name}")
    print(f"Total individuals: {num_individuals}")
    print(f"Total relationships: {num_relationships}")

    # Display accumulated date warnings
    warnings_list = get_date_warnings()
    if warnings_list:
        print(f"\n{'='*80}")
        print(
            f"DATE INCONSISTENCY WARNINGS: {len(warnings_list)} issue(s) found")
        print(f"{'='*80}")
        for i, warning in enumerate(warnings_list, 1):
            print(f"\n{i}. {warning['event_type'].upper()} date mismatch:")
            print(f"   File: {warning['file']}")
            print(f"   Person: {warning['person']}")
            print(
                f"   Gregorian: '{warning['gregorian_original']}' → {warning['gregorian_iso']}")
            print(
                f"   Revolutionary: '{warning['revolutionary_original']}' → {warning['revolutionary_iso']}")
            print(f"   Resolution: Using Gregorian date")
        print(f"\n{'='*80}")


if __name__ == "__main__":
    main()
