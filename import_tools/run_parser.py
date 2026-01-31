#!/usr/bin/env python3
"""Script to run the genealogy parser on all ODT files in the directory."""

from genealogy_parser import create_database, parse_documents, store_data, get_date_warnings, clear_date_warnings
import sys
import os
import argparse
import sqlite3

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

    # Display cross-tree matches
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT i.canonical_name, COUNT(DISTINCT iti.family_tree) as tree_count
        FROM individuals i
        JOIN individual_tree_instances iti ON i.id = iti.individual_id
        GROUP BY i.canonical_name
        HAVING tree_count > 1
        ORDER BY tree_count DESC, i.canonical_name
    ''')
    cross_tree_results = cursor.fetchall()
    
    if cross_tree_results:
        print(f"\n{'='*80}")
        print(
            f"CROSS-TREE MATCHES: {len(cross_tree_results)} individual(s) found in multiple trees")
        print(f"{'='*80}")

        for name, tree_count in cross_tree_results:
            # Get the trees for this individual
            cursor.execute('''
                SELECT DISTINCT iti.family_tree 
                FROM individuals i
                JOIN individual_tree_instances iti ON i.id = iti.individual_id
                WHERE i.canonical_name = ?
                ORDER BY iti.family_tree
            ''', (name,))
            trees = [row[0] for row in cursor.fetchall()]
            print(f"\n  {name}")
            print(f"    Found in {tree_count} tree(s): {', '.join(trees)}")
    
    conn.close()

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
