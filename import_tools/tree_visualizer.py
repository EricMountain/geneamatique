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
    GREEN = '\033[92m'     # For birth dates (bright)
    GREEN_DARK = '\033[32m'  # For birth comments (dark green)
    GRAY = '\033[90m'      # For death dates (already dark)
    GRAY_BRIGHT = '\033[37m'  # For death dates (bright white/light gray)
    MAGENTA = '\033[95m'   # For marriage dates (bright)
    MAGENTA_DARK = '\033[35m'  # For marriage comments (dark magenta)
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
            SELECT id, old_id, name, date_of_birth, birth_location, birth_comment,
                   date_of_death, death_location, death_comment,
                   marriage_date, marriage_location, marriage_comment
            FROM individuals
            WHERE old_id = ?
        """, (old_id,))
    except ValueError:
        # Search by name
        cursor.execute("""
            SELECT id, old_id, name, date_of_birth, birth_location, birth_comment,
                   date_of_death, death_location, death_comment,
                   marriage_date, marriage_location, marriage_comment
            FROM individuals
            WHERE name LIKE ?
        """, (f"%{search_term}%",))

    results = cursor.fetchall()
    return results


def get_parents(conn, individual_id):
    """Get parents of an individual."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT i.id, i.old_id, i.name, i.date_of_birth, i.birth_location, i.birth_comment,
               i.date_of_death, i.death_location, i.death_comment,
               i.marriage_date, i.marriage_location, i.marriage_comment, r.relationship_type
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
        SELECT DISTINCT i.id, i.old_id, i.name, i.date_of_birth, i.birth_location, i.birth_comment,
               i.date_of_death, i.death_location, i.death_comment,
               i.marriage_date, i.marriage_location, i.marriage_comment
        FROM relationships r
        JOIN individuals i ON r.child_id = i.id
        WHERE r.parent_id = ?
        ORDER BY i.old_id
    """, (individual_id,))
    return cursor.fetchall()


def get_spouses(conn, individual_id):
    """Get spouses of an individual based on shared children."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT i.id, i.old_id, i.name, i.date_of_birth, i.birth_location, i.birth_comment,
               i.date_of_death, i.death_location, i.death_comment,
               i.marriage_date, i.marriage_location, i.marriage_comment
        FROM relationships r
        JOIN relationships r2 ON r.child_id = r2.child_id
        JOIN individuals i ON r2.parent_id = i.id
        WHERE r.parent_id = ? AND r2.parent_id != r.parent_id
        ORDER BY i.old_id
    """, (individual_id,))
    return cursor.fetchall()


def format_person(old_id, name, dob=None, birth_loc=None, birth_comment=None,
                  dod=None, death_loc=None, death_comment=None,
                  marriage=None, marriage_loc=None, marriage_comment=None,
                  marriage_partner_names=None):
    """Format person information for display with colors.

    Colors:
    - Cyan for men (even old_id)
    - Yellow for women (odd old_id)
    - Green (bright) for birth dates, dark green for birth comments
    - Gray bright for death dates, dark gray for death comments
    - Magenta (bright) for marriage dates, dark magenta for marriage comments

    Comments are displayed in braces.
    """
    # Determine gender color based on old_id (even=father/male, odd=mother/female)
    gender_color = Colors.CYAN if old_id % 2 == 0 else Colors.YELLOW

    info = f"{colorize(name, gender_color)}"
    dates = []

    # Birth information
    if dob or birth_loc or birth_comment:
        birth_text = "°"
        if dob:
            birth_text += colorize(dob, Colors.GREEN)
            if birth_loc:
                birth_text += colorize(f" à {birth_loc}", Colors.GREEN)
        if birth_comment:
            birth_text += colorize(f" {{{birth_comment}}}", Colors.GREEN_DARK)
        if not dob and (birth_loc or birth_comment):
            # No date, just comment/location
            comment_text = birth_loc if birth_loc else birth_comment
            birth_text += colorize(f"{comment_text}", Colors.GREEN_DARK)
        dates.append(birth_text)

    # Death information
    if dod or death_loc or death_comment:
        death_text = "+"
        if dod:
            death_text += colorize(dod, Colors.GRAY_BRIGHT)
            if death_loc:
                death_text += colorize(f" à {death_loc}", Colors.GRAY_BRIGHT)
        if death_comment:
            death_text += colorize(f" {{{death_comment}}}", Colors.GRAY)
        if not dod and (death_loc or death_comment):
            # No date, just comment/location
            comment_text = death_loc if death_loc else death_comment
            death_text += colorize(f"{comment_text}", Colors.GRAY)
        dates.append(death_text)

    # Marriage information
    if marriage or marriage_loc or marriage_comment or marriage_partner_names:
        marriage_text = "X"
        if marriage:
            marriage_text += colorize(marriage, Colors.MAGENTA)
            if marriage_loc:
                marriage_text += colorize(f" à {marriage_loc}", Colors.MAGENTA)
        if marriage_comment:
            marriage_text += colorize(f" {{{marriage_comment}}}",
                                      Colors.MAGENTA_DARK)
        if marriage_partner_names:
            marriage_text += f" {marriage_partner_names}"
        if not marriage and (marriage_loc or marriage_comment) and not marriage_partner_names:
            # No date, just comment/location
            comment_text = marriage_loc if marriage_loc else marriage_comment
            marriage_text += colorize(f"{comment_text}", Colors.MAGENTA_DARK)
        dates.append(marriage_text)

    if dates:
        info += f" {', '.join(dates)}"
    return info


def draw_ancestor_tree(conn, individual_id, active_bars=None, is_last=True, visited=None, sosa_number=1, depth=0):
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
    if active_bars is None:
        active_bars = set()

    # Prevent infinite loops
    if individual_id in visited:
        return
    visited.add(individual_id)

    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, old_id, name, date_of_birth, birth_location, birth_comment,
               date_of_death, death_location, death_comment,
               marriage_date, marriage_location, marriage_comment
        FROM individuals
        WHERE id = ?
    """, (individual_id,))

    result = cursor.fetchone()
    if not result:
        return

    db_id, old_id, name, dob, birth_loc, birth_comment, dod, death_loc, death_comment, marriage, marriage_loc, marriage_comment = result

    # Print current person with Sosa number
    # Connector aligns under parent's rightmost sosa digit
    # Formula: connector_col = 3 + 6*(depth-1) for depth >= 1
    if depth == 0:
        # Root: sosa number right-aligned in 4 chars + space + name
        print(f"{sosa_number:>4} {format_person(old_id, name, dob, birth_loc, birth_comment, dod, death_loc, death_comment, marriage, marriage_loc, marriage_comment)}")
    else:
        connector_col = 3 + 6 * (depth - 1)
        connector = "└──" if is_last else "├──"

        # Build prefix with vertical bars at active positions
        prefix = ""
        for i in range(connector_col):
            if i in active_bars:
                prefix += "│"
            else:
                prefix += " "

        # Sosa right-aligned in 4 chars after connector (3 chars)
        print(f"{prefix}{connector}{sosa_number:>4} {format_person(old_id, name, dob, birth_loc, birth_comment, dod, death_loc, death_comment, marriage, marriage_loc, marriage_comment)}")

        # Update active bars for children
        if is_last:
            active_bars.discard(connector_col)
        else:
            active_bars.add(connector_col)

    # Get parents
    parents = get_parents(conn, individual_id)

    if parents:
        # Draw each parent with Sosa-Stradonitz numbering
        # Father is 2N, Mother is 2N+1
        father = None
        mother = None

        for parent in parents:
            parent_id, parent_old_id, parent_name, parent_dob, parent_birth_loc, parent_birth_comment, parent_dod, parent_death_loc, parent_death_comment, parent_marriage, parent_marriage_loc, parent_marriage_comment, rel_type = parent
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

            draw_ancestor_tree(conn, parent_id, active_bars.copy(),
                               is_last_parent, visited, parent_sosa, depth + 1)


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
        SELECT id, old_id, name, date_of_birth, birth_location, birth_comment,
               date_of_death, death_location, death_comment,
               marriage_date, marriage_location, marriage_comment
        FROM individuals
        WHERE id = ?
    """, (individual_id,))

    result = cursor.fetchone()
    if not result:
        return

    db_id, old_id, name, dob, birth_loc, birth_comment, dod, death_loc, death_comment, marriage, marriage_loc, marriage_comment = result

    # Print current person with generation number
    if depth == 0:
        connector = ""
    else:
        connector = "└── " if is_last else "├── "
    spouses = get_spouses(conn, individual_id)
    spouse_names = ", ".join([spouse[2]
                             for spouse in spouses]) if spouses else None

    print(f"{prefix}{connector}{format_person(old_id, name, dob, birth_loc, birth_comment, dod, death_loc, death_comment, marriage, marriage_loc, marriage_comment, marriage_partner_names=spouse_names)}")

    # Get children
    children = get_children(conn, individual_id)

    if children:
        # Prepare new prefix for children
        if depth == 0:
            new_prefix = prefix
        else:
            new_prefix = prefix + ("    " if is_last else "│   ")

        # Draw each child
        for idx, child in enumerate(children):
            child_id, child_old_id, child_name, child_dob, child_birth_loc, child_birth_comment, child_dod, child_death_loc, child_death_comment, child_marriage, child_marriage_loc, child_marriage_comment = child
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
        db_id, old_id, name, dob, birth_loc, birth_comment, dod, death_loc, death_comment, marriage, marriage_loc, marriage_comment = results[
            0]

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
            draw_ancestor_tree(conn, db_id, None, True)

        print()  # Add blank line at end

    finally:
        conn.close()


if __name__ == "__main__":
    main()
