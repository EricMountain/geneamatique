#!/usr/bin/env python3
"""Script to run the genealogy parser on all ODT files in the directory."""

from genealogy_parser import create_database, parse_documents, store_data, get_date_warnings, clear_date_warnings
import sys
import os
import argparse

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    parser = argparse.ArgumentParser(
        description='Parse genealogy ODT files into SQLite database')
    parser.add_argument('--ignore-files', action='append', default=[],
                        help='Files or directories to ignore during parsing (can be repeated)')
    args = parser.parse_args()

    folder_path = os.environ.get('GENEALOGY_DATA_DIR', 'data/sources')
    db_name = 'data/genealogy.db'

    # Parse ignore list from arguments or environment variable
    ignore_patterns = set()

    # Add patterns from command line arguments
    for pattern in args.ignore_files:
        ignore_patterns.add(pattern.strip())

    # Add patterns from environment variable (comma-separated for backward compatibility)
    if os.environ.get('GENEALOGY_IGNORE_FILES'):
        env_patterns = os.environ.get('GENEALOGY_IGNORE_FILES').split(',')
        for pattern in env_patterns:
            ignore_patterns.add(pattern.strip())

    print("="*80)
    print("GENEALOGY PARSER")
    print("="*80)

    print("\n1. Creating database...")
    create_database(db_name)
    print("   ✓ Database created")

    print(f"\n2. Parsing documents from: {folder_path}")
    if ignore_patterns:
        print(f"   Ignoring patterns: {', '.join(sorted(ignore_patterns))}")
    clear_date_warnings()  # Clear any previous warnings
    individuals = parse_documents(folder_path, ignore_patterns=ignore_patterns)
    print(f"   ✓ Found {len(individuals)} individuals across all documents")

    print("\n3. Storing data in database...")
    num_individuals, num_instances, num_relationships, merged_individuals = store_data(
        individuals, db_name)
    print(f"   ✓ Stored {num_individuals} unique individuals")
    print(f"   ✓ Created {num_instances} tree instance records")
    print(f"   ✓ Inferred {num_relationships} parent-child relationships")

    print("\n" + "="*80)
    print("COMPLETE!")
    print("="*80)
    print(f"Database: {db_name}")
    print(f"Canonical individuals: {num_individuals}")
    print(f"Tree instances: {num_instances}")
    print(f"Total relationships: {num_relationships}")

    # Display merged individuals
    if merged_individuals:
        # Group by individual_id to show all trees per person
        from collections import defaultdict
        merged_by_person = defaultdict(list)
        for merge in merged_individuals:
            merged_by_person[merge['individual_id']].append(merge)

        print(f"\n{'='*80}")
        print(
            f"CROSS-TREE MATCHES: {len(merged_by_person)} individual(s) found in multiple trees")
        print(f"{'='*80}")

        for individual_id, merges in sorted(merged_by_person.items()):
            name = merges[0]['name']
            trees = sorted(set(m['family_tree'] for m in merges))
            print(f"\n  {name}")
            print(f"    Found in {len(trees) + 1} tree(s): {', '.join(trees)}")

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
