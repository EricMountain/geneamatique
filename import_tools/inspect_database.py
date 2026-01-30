#!/usr/bin/env python3
"""Script to inspect the contents of the genealogy database."""

import sqlite3


def inspect_database(db_name='data/genealogy.db'):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    print("="*80)
    print("DATABASE INSPECTION")
    print("="*80)

    # Count individuals
    cursor.execute("SELECT COUNT(*) FROM individuals")
    total_individuals = cursor.fetchone()[0]
    print(f"\nTotal individuals: {total_individuals}")

    # Count relationships
    cursor.execute("SELECT COUNT(*) FROM relationships")
    total_relationships = cursor.fetchone()[0]
    print(f"Total relationships: {total_relationships}")

    # Show sample individuals
    print("\n" + "-"*80)
    print("SAMPLE INDIVIDUALS (first 10):")
    print("-"*80)
    cursor.execute("""
        SELECT id, old_id, name, date_of_birth, date_of_death, profession 
        FROM individuals 
        LIMIT 10
    """)
    for row in cursor.fetchall():
        print(f"\nID: {row[0]} (old_id: {row[1]})")
        print(f"  Name: {row[2]}")
        print(f"  Born: {row[3] or 'Unknown'}")
        print(f"  Died: {row[4] or 'Unknown'}")
        print(f"  Profession: {row[5] or 'Unknown'}")

        # Get source files
        cursor.execute(
            "SELECT source_file FROM individual_sources WHERE individual_id = ?", (row[0],))
        sources = [s[0] for s in cursor.fetchall()]
        print(f"  Sources: {', '.join(sources) if sources else 'None'}")

    # Show relationships statistics
    print("\n" + "-"*80)
    print("RELATIONSHIP STATISTICS:")
    print("-"*80)
    cursor.execute("""
        SELECT relationship_type, COUNT(*) 
        FROM relationships 
        GROUP BY relationship_type
    """)
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]}")

    # Show sample relationships
    print("\n" + "-"*80)
    print("SAMPLE RELATIONSHIPS (first 5 father relationships):")
    print("-"*80)
    cursor.execute("""
        SELECT 
            p.name as parent_name, 
            c.name as child_name, 
            r.relationship_type
        FROM relationships r
        JOIN individuals p ON r.parent_id = p.id
        JOIN individuals c ON r.child_id = c.id
        WHERE r.relationship_type = 'father'
        LIMIT 5
    """)
    for row in cursor.fetchall():
        print(f"  {row[0]} -> {row[1]} ({row[2]})")

    # Check for individuals with no parents
    print("\n" + "-"*80)
    print("INDIVIDUALS WITH NO PARENTS (root ancestors):")
    print("-"*80)
    cursor.execute("""
        SELECT i.old_id, i.name, i.date_of_birth
        FROM individuals i
        WHERE NOT EXISTS (
            SELECT 1 FROM relationships r 
            WHERE r.child_id = i.id
        )
        ORDER BY i.old_id
        LIMIT 10
    """)
    count = 0
    for row in cursor.fetchall():
        count += 1
        print(f"  {row[0]}: {row[1]} (born: {row[2] or 'Unknown'})")
    print(f"  Total: {count} individuals with no parents")

    # Check for individuals with children
    print("\n" + "-"*80)
    print("INDIVIDUALS WITH MOST CHILDREN:")
    print("-"*80)
    cursor.execute("""
        SELECT 
            i.old_id,
            i.name, 
            COUNT(r.child_id) as num_children
        FROM individuals i
        JOIN relationships r ON i.id = r.parent_id
        GROUP BY i.id, i.name
        ORDER BY num_children DESC
        LIMIT 10
    """)
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} - {row[2]} children")

    conn.close()


if __name__ == "__main__":
    inspect_database()
