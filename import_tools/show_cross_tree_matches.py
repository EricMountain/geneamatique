#!/usr/bin/env python3
"""Show individuals that appear in multiple family trees."""

import sqlite3
import sys


def show_cross_tree_individuals(db_name='data/genealogy.db'):
    """Display individuals who appear in multiple family trees."""
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Find individuals with multiple tree instances
    cursor.execute('''
        SELECT i.id, i.canonical_name, i.date_of_birth, i.date_of_death,
               COUNT(DISTINCT iti.family_tree) as tree_count
        FROM individuals i
        JOIN individual_tree_instances iti ON i.id = iti.individual_id
        GROUP BY i.id
        HAVING tree_count > 1
        ORDER BY tree_count DESC, i.canonical_name
    ''')

    cross_tree_individuals = cursor.fetchall()

    if not cross_tree_individuals:
        print("No individuals found in multiple family trees.")
        return

    print(f"\n{'='*100}")
    print(
        f"INDIVIDUALS APPEARING IN MULTIPLE FAMILY TREES: {len(cross_tree_individuals)}")
    print(f"{'='*100}\n")

    for individual_id, name, dob, dod, tree_count in cross_tree_individuals:
        print(f"{'─'*100}")
        print(f"\n{name}")
        if dob:
            print(f"  Born: {dob}", end='')
            if dod:
                print(f"  |  Died: {dod}")
            else:
                print()
        elif dod:
            print(f"  Died: {dod}")

        print(f"\n  Appears in {tree_count} family tree(s):")

        # Get tree instances
        cursor.execute('''
            SELECT family_tree, old_id, name_variant, source_file
            FROM individual_tree_instances
            WHERE individual_id = ?
            ORDER BY family_tree
        ''', (individual_id,))

        instances = cursor.fetchall()
        for family_tree, old_id, name_variant, source_file in instances:
            print(f"    • {family_tree}")
            print(f"      Sosa ID: {old_id}")
            if name_variant and name_variant != name:
                print(f"      Name variant: {name_variant}")
            print(f"      Source: {source_file}")

        print()

    print(f"{'='*100}\n")

    conn.close()


def show_statistics(db_name='data/genealogy.db'):
    """Show database statistics about cross-tree matching."""
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Total canonical individuals
    cursor.execute('SELECT COUNT(*) FROM individuals')
    total_individuals = cursor.fetchone()[0]

    # Total tree instances
    cursor.execute('SELECT COUNT(*) FROM individual_tree_instances')
    total_instances = cursor.fetchone()[0]

    # Individuals in multiple trees
    cursor.execute('''
        SELECT COUNT(DISTINCT individual_id)
        FROM individual_tree_instances
        GROUP BY individual_id
        HAVING COUNT(DISTINCT family_tree) > 1
    ''')
    cross_tree_count = len(cursor.fetchall())

    # Tree instance distribution
    cursor.execute('''
        SELECT COUNT(DISTINCT family_tree) as tree_count, COUNT(*) as individual_count
        FROM individual_tree_instances
        GROUP BY individual_id
        ORDER BY tree_count DESC
    ''')
    distribution = cursor.fetchall()

    print(f"\n{'='*80}")
    print("DATABASE STATISTICS")
    print(f"{'='*80}\n")
    print(f"Total canonical individuals: {total_individuals}")
    print(f"Total tree instances: {total_instances}")
    print(
        f"Matched across trees: {cross_tree_count} ({total_instances - total_individuals} duplicate instances merged)")

    print(f"\nDistribution by number of trees:")
    for tree_count, individual_count in distribution:
        if tree_count == 1:
            print(
                f"  {individual_count} individuals in 1 tree (unique to that tree)")
        else:
            print(f"  {individual_count} individuals in {tree_count} trees")

    print()

    conn.close()


def main():
    db_name = 'data/genealogy.db'

    if len(sys.argv) > 1 and sys.argv[1] == '--stats':
        show_statistics(db_name)
    else:
        show_statistics(db_name)
        show_cross_tree_individuals(db_name)


if __name__ == "__main__":
    main()
