#!/usr/bin/env python3
"""Export a family tree (ancestor or descendant) to a JSON file.

Usage examples:
    python -m import_tools.tree_to_json "John Doe" --out ui/tree.json
    python -m import_tools.tree_to_json 12 --descendants --out ui/tree.json
"""
import argparse
import json
import sqlite3
import sys
from . import tree_utils


def choose_individual(conn, search_term, family_tree=None):
    results = tree_utils.find_individual(conn, search_term, family_tree)
    if not results:
        print(f"No individuals found matching: {search_term}", file=sys.stderr)
        sys.exit(1)
    if len(results) > 1:
        # If all are same canonical individual, pick first
        individual_ids = set(result[0] for result in results)
        if len(individual_ids) == 1:
            return results[0]
        print(f"Multiple individuals found matching '{search_term}':", file=sys.stderr)
        for individual in results:
            print(f"  {individual[2]:4d}  [{individual[1]:<30}]  {individual[3]}", file=sys.stderr)
        print("Specify an ID or use --family-tree to disambiguate.", file=sys.stderr)
        sys.exit(2)
    return results[0]


def main():
    parser = argparse.ArgumentParser(description='Export family tree to JSON')
    parser.add_argument('name', help='Name or ID of individual')
    parser.add_argument('--descendants', action='store_true', help='Export descendants (default: ancestors)')
    parser.add_argument('--family-tree', help='Family tree name to disambiguate')
    parser.add_argument('--db', default='data/genealogy.db', help='Path to DB')
    parser.add_argument('--out', default='-', help='Output JSON file (default: stdout)')
    parser.add_argument('--pretty', action='store_true', help='Pretty-print JSON')

    args = parser.parse_args()

    conn = sqlite3.connect(args.db)

    try:
        individual = choose_individual(conn, args.name, args.family_tree)
        individual_id, family_tree, old_id, name = individual[0], individual[1], individual[2], individual[3]

        if args.descendants:
            tree = tree_utils.build_descendant_tree(conn, individual_id, family_tree)
        else:
            tree = tree_utils.build_ancestor_tree(conn, individual_id, family_tree)

        if tree is None:
            print("No tree could be built for the specified individual.", file=sys.stderr)
            sys.exit(1)

        out_str = json.dumps(tree, indent=2 if args.pretty else None)
        if args.out == '-':
            print(out_str)
        else:
            with open(args.out, 'w', encoding='utf-8') as fh:
                fh.write(out_str)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
