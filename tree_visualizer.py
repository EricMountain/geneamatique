#!/usr/bin/env python3
"""
Visualize genealogy trees in ASCII art format (like git log --graph).
"""

import sqlite3
import sys
import argparse
from typing import List, Tuple, Optional

# ANSI color codes


class Colors:
    CYAN = '\033[96m'      # For men
    YELLOW = '\033[93m'    # For women
    GREEN = '\033[92m'     # For birth dates
    GRAY = '\033[90m'      # For death dates
    MAGENTA = '\033[95m'   # For marriage dates
    RESET = '\033[0m'      # Reset to default
    BOLD = '\033[1m'       # Bold text


def colorize(text, color):
    """Wrap text in ANSI color codes."""
    return f"{color}{text}{Colors.RESET}"


def find_individual(conn, search_term):
    """Find an individual by name or ID."""
    cursor = conn.cursor()

    # Try as ID first
    try:
        old_id = int(search_term)
        cursor.execute("""
            SELECT id, old_id, name, date_of_birth, date_of_death, marriage_date
            FROM individuals
            WHERE old_id = ?
        """, (old_id,))
    except ValueError:
        # Search by name
        cursor.execute("""
            SELECT id, old_id, name, date_of_birth, date_of_death, marriage_date
            FROM individuals
            WHERE name LIKE ?
        """, (f"%{search_term}%",))

    results = cursor.fetchall()
    return results


def get_parents(conn, individual_id):
    """Get parents of an individual."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT i.id, i.old_id, i.name, i.date_of_birth, i.date_of_death, i.marriage_date, r.relationship_type
        FROM relationships r
        JOIN individuals i ON r.parent_id = i.id
        WHERE r.child_id = ?
        ORDER BY r.relationship_type DESC
    """, (individual_id,))
    return cursor.fetchall()


def get_children(conn, individual_id):
    """Get children of an individual."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT i.id, i.old_id, i.name, i.date_of_birth, i.date_of_death, i.marriage_date
        FROM relationships r
        JOIN individuals i ON r.child_id = i.id
        WHERE r.parent_id = ?
        ORDER BY i.old_id
    """, (individual_id,))
    return cursor.fetchall()


def format_person(sosa_number, old_id, name, dob, dod, marriage):
    """Format person information for display with colors.

    Colors:
    - Cyan for men (even old_id)
    - Yellow for women (odd old_id)
    - Green for birth dates
    - Gray for death dates
    - Magenta for marriage dates
    """
    # Determine gender color based on old_id (even=father/male, odd=mother/female)
    gender_color = Colors.CYAN if old_id % 2 == 0 else Colors.YELLOW

    info = f"{sosa_number:4d} {colorize(name, gender_color)}"
    dates = []
    if dob:
        dates.append(colorize(f"°{dob}", Colors.GREEN))
    if dod:
        dates.append(colorize(f"+{dod}", Colors.GRAY))
    if marriage:
        dates.append(colorize(f"X{marriage}", Colors.MAGENTA))
    if dates:
        info += f" {', '.join(dates)}"
    return info


def draw_ancestor_tree(conn, individual_id, prefix="", is_last=True, visited=None, sosa_number=1):
    """
    Draw an ASCII tree of ancestors working backwards from the individual.

    Uses Sosa-Stradonitz numbering where:
    - The root person is 1
    - For any person N, their father is 2N and mother is 2N+1

    Uses box-drawing characters to create a tree structure:
    ├── for branches
    └── for last branch
    │   for vertical lines
    """
    if visited is None:
        visited = set()

    # Prevent infinite loops
    if individual_id in visited:
        return
    visited.add(individual_id)

    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, old_id, name, date_of_birth, date_of_death, marriage_date
        FROM individuals
        WHERE id = ?
    """, (individual_id,))

    result = cursor.fetchone()
    if not result:
        return

    db_id, old_id, name, dob, dod, marriage = result

    # Print current person with Sosa number
    connector = "└── " if is_last else "├── "
    print(f"{prefix}{connector}{format_person(sosa_number, old_id, name, dob, dod, marriage)}")

    # Get parents
    parents = get_parents(conn, individual_id)

    if parents:
        # Prepare new prefix for children
        new_prefix = prefix + ("    " if is_last else "│   ")

        # Draw each parent with Sosa-Stradonitz numbering
        # Father is 2N, Mother is 2N+1
        father = None
        mother = None

        for parent in parents:
            parent_id, parent_old_id, parent_name, parent_dob, parent_dod, parent_marriage, rel_type = parent
            if rel_type == 'father':
                father = parent
            else:
                mother = parent

        # Draw in order: mother first (odd number), then father (even number)
        # This keeps the visual order consistent
        parents_to_draw = []
        if mother:
            parents_to_draw.append((mother, sosa_number * 2 + 1))
        if father:
            parents_to_draw.append((father, sosa_number * 2))

        for idx, (parent, parent_sosa) in enumerate(parents_to_draw):
            parent_id = parent[0]
            is_last_parent = (idx == len(parents_to_draw) - 1)

            draw_ancestor_tree(conn, parent_id, new_prefix,
                               is_last_parent, visited, parent_sosa)


def draw_descendant_tree(conn, individual_id, prefix="", is_last=True, visited=None, depth=0, max_depth=10, generation_number=1):
    """
    Draw an ASCII tree of descendants working forward from the individual.

    For descendants, we use a simple sequential numbering within each generation.

    Uses box-drawing characters to create a tree structure.
    """
    if visited is None:
        visited = set()

    # Prevent infinite loops and limit depth
    if individual_id in visited or depth > max_depth:
        return
    visited.add(individual_id)

    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, old_id, name, date_of_birth, date_of_death, marriage_date
        FROM individuals
        WHERE id = ?
    """, (individual_id,))

    result = cursor.fetchone()
    if not result:
        return

    db_id, old_id, name, dob, dod, marriage = result

    # Print current person with generation number
    connector = "└── " if is_last else "├── "
    print(f"{prefix}{connector}{format_person(generation_number, old_id, name, dob, dod, marriage)}")

    # Get children
    children = get_children(conn, individual_id)

    if children:
        # Prepare new prefix for children
        new_prefix = prefix + ("    " if is_last else "│   ")

        # Draw each child
        for idx, child in enumerate(children):
            child_id, child_old_id, child_name, child_dob, child_dod = child
            is_last_child = (idx == len(children) - 1)

            # For descendants, we use generation.child_index numbering
            # e.g., 1 -> 1.1, 1.2, 1.3 (but displayed as simple integers)
            # For simplicity, use sequential numbering based on depth
            child_number = generation_number * 10 + idx + 1

            draw_descendant_tree(conn, child_id, new_prefix, is_last_child,
                                 visited, depth + 1, max_depth, child_number)


def main():
    parser = argparse.ArgumentParser(
        description='Visualize genealogy trees in ASCII art format (like git log --graph)',
        epilog='''
Examples:
    %(prog)s "Sample Person"               # Show ancestors
    %(prog)s 2                               # Show ancestors by ID
    %(prog)s --descendants "Sample Person"  # Show descendants
    %(prog)s -d --max-depth 5 2              # Show descendants, max 5 generations
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('name',
                        help='Name or ID of the individual')
    parser.add_argument('-d', '--descendants',
                        action='store_true',
                        help='Show descendants instead of ancestors')
    parser.add_argument('--max-depth',
                        type=int,
                        default=10,
                        help='Maximum depth for descendant tree (default: 10)')
    parser.add_argument('--db',
                        default='data/genealogy.db',
                        help='Path to genealogy database (default: data/genealogy.db)')

    args = parser.parse_args()

    conn = sqlite3.connect(args.db)

    try:
        results = find_individual(conn, args.name)

        if not results:
            print(
                f"No individuals found matching: {args.name}", file=sys.stderr)
            sys.exit(1)

        if len(results) > 1:
            print(f"Multiple individuals found matching '{args.name}':")
            print("=" * 80)
            for individual in results:
                print(f"  {individual[1]:4d}  {individual[2]}")
            print("=" * 80)
            print("\nPlease specify the ID number to see the tree for a specific person.")
            sys.exit(1)

        # Single result - show the tree
        db_id, old_id, name, dob, dod, marriage = results[0]

        if args.descendants:
            print(f"\n{'='*80}")
            print(f"DESCENDANT TREE FOR: {name} (ID {old_id})")
            print(f"{'='*80}\n")
            draw_descendant_tree(conn, db_id, "", True,
                                 max_depth=args.max_depth)
        else:
            print(f"\n{'='*80}")
            print(f"ANCESTOR TREE FOR: {name} (ID {old_id})")
            print(f"{'='*80}\n")
            draw_ancestor_tree(conn, db_id, "", True)

        print()  # Add blank line at end

    finally:
        conn.close()


if __name__ == "__main__":
    main()
