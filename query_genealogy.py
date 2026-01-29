#!/usr/bin/env python3
"""Query tool for exploring genealogy data."""

import sqlite3
import sys


def find_individual(conn, search_term):
    """Find individuals by name or ID."""
    cursor = conn.cursor()

    # Try as ID first
    try:
        old_id = int(search_term)
        cursor.execute("""
            SELECT id, old_id, name, date_of_birth, date_of_death, profession, marriage_date
            FROM individuals
            WHERE old_id = ?
        """, (old_id,))
    except ValueError:
        # Search by name
        cursor.execute("""
            SELECT id, old_id, name, date_of_birth, date_of_death, profession, marriage_date
            FROM individuals
            WHERE name LIKE ?
        """, (f"%{search_term}%",))

    results = cursor.fetchall()
    return results


def get_parents(conn, individual_id):
    """Get parents of an individual."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT i.old_id, i.name, r.relationship_type
        FROM relationships r
        JOIN individuals i ON r.parent_id = i.id
        WHERE r.child_id = ?
        ORDER BY r.relationship_type
    """, (individual_id,))
    return cursor.fetchall()


def get_children(conn, individual_id):
    """Get children of an individual."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT i.old_id, i.name
        FROM relationships r
        JOIN individuals i ON r.child_id = i.id
        WHERE r.parent_id = ?
        ORDER BY i.old_id
    """, (individual_id,))
    return cursor.fetchall()


def get_sources(conn, individual_id):
    """Get source files for an individual."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT source_file
        FROM individual_sources
        WHERE individual_id = ?
        ORDER BY source_file
    """, (individual_id,))
    return [row[0] for row in cursor.fetchall()]


def display_individual(conn, individual):
    """Display detailed information about an individual."""
    db_id, old_id, name, dob, dod, profession, marriage = individual

    print(f"\n{'='*80}")
    print(f"{name}")
    print(f"{'='*80}")
    print(f"ID: {old_id} (Database ID: {db_id})")
    if dob:
        print(f"Born: {dob}")
    if dod:
        print(f"Died: {dod}")
    if profession:
        print(f"Profession: {profession}")
    if marriage:
        print(f"Married: {marriage}")

    # Sources
    sources = get_sources(conn, db_id)
    if sources:
        print(f"\nMentioned in {len(sources)} document(s):")
        for source in sources:
            print(f"  - {source}")

    # Parents
    parents = get_parents(conn, db_id)
    if parents:
        print(f"\nParents:")
        for parent in parents:
            parent_type = "Father" if parent[2] == "father" else "Mother"
            print(f"  {parent_type}: {parent[1]} (ID {parent[0]})")

    # Children
    children = get_children(conn, db_id)
    if children:
        print(f"\nChildren ({len(children)}):")
        for child in children:
            print(f"  - {child[1]} (ID {child[0]})")


def main():
    if len(sys.argv) < 2:
        print("Usage: python query_genealogy.py <name_or_id>")
        print("\nExamples:")
        print("  python query_genealogy.py SAMPLE")
        print("  python query_genealogy.py 2")
        print("  python query_genealogy.py \"Sample Name\"")
        sys.exit(1)

    search_term = " ".join(sys.argv[1:])

    conn = sqlite3.connect('data/genealogy.db')

    try:
        results = find_individual(conn, search_term)

        if not results:
            print(f"No individuals found matching: {search_term}")
            sys.exit(1)

        if len(results) == 1:
            display_individual(conn, results[0])
        else:
            print(f"\nFound {len(results)} matching individuals:")
            print("-" * 80)
            for individual in results:
                print(f"{individual[1]:4d}  {individual[2]}")
            print("-" * 80)
            print("\nUse the ID number to see details for a specific person.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
