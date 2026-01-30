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
    WHITE_DIM = '\033[37m'  # For name comments (dim white)
    RESET = '\033[0m'      # Reset to default
    BOLD = '\033[1m'       # Bold text


def colorize(text, color):
    """Wrap text in ANSI color codes."""
    return f"{color}{text}{Colors.RESET}"


def find_individual(conn, search_term, family_tree=None):
    """Find an individual by name or old_id.

    Returns list of tuples: (individual_id, family_tree, old_id, canonical_name, ...)
    Deduplicates multiple instances with same (individual_id, family_tree, old_id) from different source files.
    """
    cursor = conn.cursor()

    # Try as old_id first
    try:
        old_id = int(search_term)
        query = """
            SELECT DISTINCT i.id, iti.family_tree, iti.old_id, i.canonical_name, 
                   i.date_of_birth, i.birth_location, i.birth_comment,
                   i.date_of_death, i.death_location, i.death_comment,
                   i.marriage_date, i.marriage_location, i.marriage_comment
            FROM individuals i
            JOIN individual_tree_instances iti ON i.id = iti.individual_id
            WHERE iti.old_id = ?
        """
        params = [old_id]
        if family_tree:
            query += " AND iti.family_tree = ?"
            params.append(family_tree)
        query += " ORDER BY iti.family_tree, iti.old_id"
        cursor.execute(query, params)
    except ValueError:
        # Search by name
        query = """
            SELECT DISTINCT i.id, iti.family_tree, iti.old_id, i.canonical_name,
                   i.date_of_birth, i.birth_location, i.birth_comment,
                   i.date_of_death, i.death_location, i.death_comment,
                   i.marriage_date, i.marriage_location, i.marriage_comment
            FROM individuals i
            JOIN individual_tree_instances iti ON i.id = iti.individual_id
            WHERE i.canonical_name LIKE ?
        """
        params = [f"%{search_term}%"]
        if family_tree:
            query += " AND iti.family_tree = ?"
            params.append(family_tree)
        query += " ORDER BY iti.family_tree, iti.old_id"
        cursor.execute(query, params)

    results = cursor.fetchall()
    return results


def get_parents(conn, individual_id, family_tree=None):
    """Get parents of an individual, optionally within a specific family tree.
    
    If family_tree is provided, first try to find relationship in that tree.
    If not found, look across all trees (for cross-tree relationships).
    
    When a parent appears in multiple source files with the same (family_tree, old_id),
    we use the instance with the lowest old_id (or first alphabetically by source if same old_id).
    """
    cursor = conn.cursor()
    
    # First try within the specified family_tree
    if family_tree:
        cursor.execute("""
            SELECT i.id, iti.old_id, i.canonical_name, 
                   i.date_of_birth, i.birth_location, i.birth_comment,
                   i.date_of_death, i.death_location, i.death_comment,
                   i.marriage_date, i.marriage_location, i.marriage_comment, r.relationship_type, iti.family_tree
            FROM relationships r
            JOIN individuals i ON r.parent_id = i.id
            JOIN individual_tree_instances iti ON i.id = iti.individual_id
            WHERE r.child_id = ? AND r.family_tree = ?
            GROUP BY i.id, r.relationship_type
            ORDER BY r.relationship_type DESC
        """, (individual_id, family_tree))
        results = cursor.fetchall()
        if results:
            return results
        
        # Not found in specified tree, try any tree where this individual appears
        cursor.execute("""
            SELECT i.id, iti.old_id, i.canonical_name, 
                   i.date_of_birth, i.birth_location, i.birth_comment,
                   i.date_of_death, i.death_location, i.death_comment,
                   i.marriage_date, i.marriage_location, i.marriage_comment, r.relationship_type, r.family_tree
            FROM relationships r
            JOIN individuals i ON r.parent_id = i.id
            JOIN individual_tree_instances iti ON i.id = iti.individual_id
            WHERE r.child_id = ?
            GROUP BY i.id, r.relationship_type
            ORDER BY r.relationship_type DESC
        """, (individual_id,))
    else:
        # No family tree specified, look in all trees
        cursor.execute("""
            SELECT i.id, iti.old_id, i.canonical_name, 
                   i.date_of_birth, i.birth_location, i.birth_comment,
                   i.date_of_death, i.death_location, i.death_comment,
                   i.marriage_date, i.marriage_location, i.marriage_comment, r.relationship_type, r.family_tree
            FROM relationships r
            JOIN individuals i ON r.parent_id = i.id
            JOIN individual_tree_instances iti ON i.id = iti.individual_id
            WHERE r.child_id = ?
            GROUP BY i.id, r.relationship_type
            ORDER BY r.relationship_type DESC
        """, (individual_id,))
    
    return cursor.fetchall()


def get_children(conn, individual_id, family_tree=None):
    """Get children of an individual, optionally within a specific family tree.
    
    If family_tree is provided, first try to find relationships in that tree.
    If not found, look across all trees (for cross-tree relationships).
    """
    cursor = conn.cursor()
    
    # First try within the specified family_tree
    if family_tree:
        cursor.execute("""
            SELECT DISTINCT i.id, iti.old_id, i.canonical_name,
                   i.date_of_birth, i.birth_location, i.birth_comment,
                   i.date_of_death, i.death_location, i.death_comment,
                   i.marriage_date, i.marriage_location, i.marriage_comment, r.family_tree
            FROM relationships r
            JOIN individuals i ON r.child_id = i.id
            JOIN individual_tree_instances iti ON i.id = iti.individual_id AND iti.family_tree = ?
            WHERE r.parent_id = ? AND r.family_tree = ?
            ORDER BY iti.old_id
        """, (family_tree, individual_id, family_tree))
        results = cursor.fetchall()
        if results:
            return results
        
        # Not found in specified tree, try any tree where this individual appears
        cursor.execute("""
            SELECT DISTINCT i.id, iti.old_id, i.canonical_name,
                   i.date_of_birth, i.birth_location, i.birth_comment,
                   i.date_of_death, i.death_location, i.death_comment,
                   i.marriage_date, i.marriage_location, i.marriage_comment, r.family_tree
            FROM relationships r
            JOIN individuals i ON r.child_id = i.id
            JOIN individual_tree_instances iti ON i.id = iti.individual_id
            WHERE r.parent_id = ?
            ORDER BY iti.old_id
        """, (individual_id,))
    else:
        # No family tree specified, look in all trees
        cursor.execute("""
            SELECT DISTINCT i.id, iti.old_id, i.canonical_name,
                   i.date_of_birth, i.birth_location, i.birth_comment,
                   i.date_of_death, i.death_location, i.death_comment,
                   i.marriage_date, i.marriage_location, i.marriage_comment, r.family_tree
            FROM relationships r
            JOIN individuals i ON r.child_id = i.id
            JOIN individual_tree_instances iti ON i.id = iti.individual_id
            WHERE r.parent_id = ?
            ORDER BY iti.old_id
        """, (individual_id,))
    
    return cursor.fetchall()


def get_spouses(conn, individual_id, family_tree):
    """Get spouses of an individual based on shared children within a tree."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT i.id, iti.old_id, i.canonical_name,
               i.date_of_birth, i.birth_location, i.birth_comment,
               i.date_of_death, i.death_location, i.death_comment,
               i.marriage_date, i.marriage_location, i.marriage_comment
        FROM relationships r
        JOIN relationships r2 ON r.child_id = r2.child_id AND r.family_tree = r2.family_tree
        JOIN individuals i ON r2.parent_id = i.id
        JOIN individual_tree_instances iti ON i.id = iti.individual_id AND iti.family_tree = ?
        WHERE r.parent_id = ? AND r2.parent_id != r.parent_id AND r.family_tree = ?
        ORDER BY iti.old_id
    """, (family_tree, individual_id, family_tree))
    return cursor.fetchall()


def format_person(old_id, name, dob=None, birth_loc=None, birth_comment=None,
                  dod=None, death_loc=None, death_comment=None,
                  marriage=None, marriage_loc=None, marriage_comment=None,
                  marriage_partner_names=None, db_id=None, name_comment=None):
    """Format person information for display with colors.

    Colors:
    - Cyan for men (even old_id)
    - Yellow for women (odd old_id)
    - Green (bright) for birth dates, dark green for birth comments
    - Gray bright for death dates, dark gray for death comments
    - Magenta (bright) for marriage dates, dark magenta for marriage comments
    - White dim for name comments

    Comments are displayed in braces.
    """
    # Determine gender color based on old_id (even=father/male, odd=mother/female)
    gender_color = Colors.CYAN if old_id % 2 == 0 else Colors.YELLOW

    info = f"{colorize(name, gender_color)}"
    if name_comment:
        info += colorize(f" {{{name_comment}}}", Colors.WHITE_DIM)
    dates = []

    # Birth information
    if dob:
        birth_text = "°"
        birth_text += colorize(dob, Colors.GREEN)
        if birth_loc:
            birth_text += colorize(f" à {birth_loc}", Colors.GREEN)
        if birth_comment:
            birth_text += colorize(f" {{{birth_comment}}}", Colors.GREEN_DARK)
        dates.append(birth_text)

    # Death information
    if dod:
        death_text = "+"
        death_text += colorize(dod, Colors.GRAY_BRIGHT)
        if death_loc:
            death_text += colorize(f" à {death_loc}", Colors.GRAY_BRIGHT)
        if death_comment:
            death_text += colorize(f" {{{death_comment}}}", Colors.GRAY)
        dates.append(death_text)

    # Marriage information
    if marriage:
        marriage_text = "X"
        marriage_text += colorize(marriage, Colors.MAGENTA)
        if marriage_loc:
            marriage_text += colorize(f" à {marriage_loc}", Colors.MAGENTA)
        if marriage_comment:
            marriage_text += colorize(f" {{{marriage_comment}}}",
                                      Colors.MAGENTA_DARK)
        if marriage_partner_names:
            marriage_text += f" {marriage_partner_names}"
        dates.append(marriage_text)

    if dates:
        info += f" {', '.join(dates)}"
    
    # Add database ID in square brackets if provided
    if db_id is not None:
        info += f" [{db_id}]"
    
    return info


def draw_ancestor_tree(conn, individual_id, family_tree, active_bars=None, is_last=True, visited=None, sosa_number=1, depth=0):
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
        SELECT i.id, iti.old_id, i.canonical_name, i.name_comment,
               i.date_of_birth, i.birth_location, i.birth_comment,
               i.date_of_death, i.death_location, i.death_comment,
               i.marriage_date, i.marriage_location, i.marriage_comment
        FROM individuals i
        JOIN individual_tree_instances iti ON i.id = iti.individual_id
        WHERE i.id = ? AND iti.family_tree = ?
    """, (individual_id, family_tree))

    result = cursor.fetchone()
    if not result:
        return

    db_id, old_id, name, name_comment, dob, birth_loc, birth_comment, dod, death_loc, death_comment, marriage, marriage_loc, marriage_comment = result

    # Print current person with Sosa number
    # Connector aligns under parent's rightmost sosa digit
    # Formula: connector_col = 3 + 6*(depth-1) for depth >= 1
    if depth == 0:
        # Root: sosa number right-aligned in 4 chars + space + name
        print(f"{sosa_number:>4} {format_person(old_id, name, dob, birth_loc, birth_comment, dod, death_loc, death_comment, marriage, marriage_loc, marriage_comment, db_id=db_id, name_comment=name_comment)}")
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
        print(f"{prefix}{connector}{sosa_number:>4} {format_person(old_id, name, dob, birth_loc, birth_comment, dod, death_loc, death_comment, marriage, marriage_loc, marriage_comment, db_id=db_id, name_comment=name_comment)}")

        # Update active bars for children
        if is_last:
            active_bars.discard(connector_col)
        else:
            active_bars.add(connector_col)

    # Get parents
    parents = get_parents(conn, individual_id, family_tree)

    # If no parents found in current tree, look for the same person in other trees
    # (handles case where person exists as multiple canonical individuals across trees)
    if not parents and dob:
        # Find other instances of this person in different trees
        cursor.execute("""
            SELECT DISTINCT i.id, iti.family_tree
            FROM individuals i
            JOIN individual_tree_instances iti ON i.id = iti.individual_id
            WHERE i.canonical_name = ? AND i.date_of_birth = ? AND i.id != ?
        """, (name, dob, individual_id))
        other_instances = cursor.fetchall()
        
        # Try to find parents for any of these other instances
        for other_id, other_tree in other_instances:
            parents = get_parents(conn, other_id, other_tree)
            if parents:
                # Found parents in another tree, use that individual_id for recursion
                individual_id = other_id
                break

    if parents:
        # Draw each parent with Sosa-Stradonitz numbering
        # Father is 2N, Mother is 2N+1
        father = None
        mother = None

        for parent in parents:
            parent_id, parent_old_id, parent_name, parent_dob, parent_birth_loc, parent_birth_comment, parent_dod, parent_death_loc, parent_death_comment, parent_marriage, parent_marriage_loc, parent_marriage_comment, rel_type, parent_family_tree = parent
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
            parent_family_tree = parent[13]  # Last element is family_tree
            is_last_parent = (idx == len(parents_to_draw) - 1)

            draw_ancestor_tree(conn, parent_id, parent_family_tree, active_bars.copy(),
                               is_last_parent, visited, parent_sosa, depth + 1)


def draw_descendant_tree(conn, individual_id, family_tree, prefix="", is_last=True, visited=None, depth=0, max_depth=10, generation_number=1):
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
        SELECT i.id, iti.old_id, i.canonical_name, i.name_comment,
               i.date_of_birth, i.birth_location, i.birth_comment,
               i.date_of_death, i.death_location, i.death_comment,
               i.marriage_date, i.marriage_location, i.marriage_comment
        FROM individuals i
        JOIN individual_tree_instances iti ON i.id = iti.individual_id
        WHERE i.id = ? AND iti.family_tree = ?
    """, (individual_id, family_tree))

    result = cursor.fetchone()
    if not result:
        return

    db_id, old_id, name, name_comment, dob, birth_loc, birth_comment, dod, death_loc, death_comment, marriage, marriage_loc, marriage_comment = result

    # Print current person with generation number
    if depth == 0:
        connector = ""
    else:
        connector = "└── " if is_last else "├── "
    spouses = get_spouses(conn, individual_id, family_tree)
    spouse_names = ", ".join([spouse[2]
                             for spouse in spouses]) if spouses else None

    print(f"{prefix}{connector}{format_person(old_id, name, dob, birth_loc, birth_comment, dod, death_loc, death_comment, marriage, marriage_loc, marriage_comment, marriage_partner_names=spouse_names, db_id=db_id, name_comment=name_comment)}")

    # Get children
    children = get_children(conn, individual_id, family_tree)

    # If no children found in current tree, look for the same person in other trees
    # (handles case where person exists as multiple canonical individuals across trees)
    if not children and dob:
        # Find other instances of this person in different trees
        cursor.execute("""
            SELECT DISTINCT i.id, iti.family_tree
            FROM individuals i
            JOIN individual_tree_instances iti ON i.id = iti.individual_id
            WHERE i.canonical_name = ? AND i.date_of_birth = ? AND i.id != ?
        """, (name, dob, individual_id))
        other_instances = cursor.fetchall()
        
        # Try to find children for any of these other instances
        for other_id, other_tree in other_instances:
            children = get_children(conn, other_id, other_tree)
            if children:
                # Found children in another tree
                break

    if children:
        # Prepare new prefix for children
        if depth == 0:
            new_prefix = prefix
        else:
            new_prefix = prefix + ("    " if is_last else "│   ")

        # Draw each child
        for idx, child in enumerate(children):
            child_id, child_old_id, child_name, child_dob, child_birth_loc, child_birth_comment, child_dod, child_death_loc, child_death_comment, child_marriage, child_marriage_loc, child_marriage_comment, child_family_tree = child
            is_last_child = (idx == len(children) - 1)

            # For descendants, we use generation.child_index numbering
            # e.g., 1 -> 1.1, 1.2, 1.3 (but displayed as simple integers)
            # For simplicity, use sequential numbering based on depth
            child_number = generation_number * 10 + idx + 1

            draw_descendant_tree(conn, child_id, child_family_tree, new_prefix, is_last_child,
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
    parser.add_argument('--family-tree',
                        help='Specify family tree when multiple matches exist')
    parser.add_argument('--db',
                        default='data/genealogy.db',
                        help='Path to genealogy database (default: data/genealogy.db)')

    args = parser.parse_args()

    conn = sqlite3.connect(args.db)

    try:
        results = find_individual(conn, args.name, args.family_tree)

        if not results:
            print(
                f"No individuals found matching: {args.name}", file=sys.stderr)
            sys.exit(1)

        if len(results) > 1:
            print(f"Multiple individuals found matching '{args.name}':")
            print("=" * 80)
            for individual in results:
                # individual: individual_id, family_tree, old_id, canonical_name, ...
                print(
                    f"  {individual[2]:4d}  [{individual[1]:<30}]  {individual[3]}")
            print("=" * 80)
            print(
                "\nPlease specify the ID number or use --family-tree to select a specific tree.")
            sys.exit(1)

        # Single result - show the tree
        # Format: individual_id, family_tree, old_id, canonical_name, dob, birth_loc, birth_comment, dod, death_loc, death_comment, marriage, marriage_loc, marriage_comment
        individual_id, family_tree, old_id, name, dob, birth_loc, birth_comment, dod, death_loc, death_comment, marriage, marriage_loc, marriage_comment = results[
            0]

        if args.descendants:
            print(f"\n{'='*80}")
            print(
                f"DESCENDANT TREE FOR: {name} (Sosa {old_id}, Family: {family_tree})")
            print(f"{'='*80}\n")
            draw_descendant_tree(conn, individual_id, family_tree, "", True,
                                 max_depth=args.max_depth)
        else:
            print(f"\n{'='*80}")
            print(
                f"ANCESTOR TREE FOR: {name} (Sosa {old_id}, Family: {family_tree})")
            print(f"{'='*80}\n")
            draw_ancestor_tree(conn, individual_id, family_tree, None, True)

        print()  # Add blank line at end

    finally:
        conn.close()


if __name__ == "__main__":
    main()
