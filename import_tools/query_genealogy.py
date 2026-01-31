#!/usr/bin/env python3
"""Query tool for exploring genealogy data."""

import sqlite3
import sys


def find_individual(conn, search_term):
    """Find individuals by name or ID."""
    cursor = conn.cursor()

    # Try as ID first
    try:
        individual_id = int(search_term)
        cursor.execute("""
            SELECT i.id, iti.old_id, iti.family_tree, i.canonical_name, i.date_of_birth, i.birth_location, i.birth_comment,
                   i.date_of_death, i.death_location, i.death_comment, i.profession,
                   i.marriage_date, i.marriage_location, i.marriage_comment
            FROM individuals i
            LEFT JOIN individual_tree_instances iti ON i.id = iti.individual_id
            WHERE i.id = ?
            LIMIT 1
        """, (individual_id,))
    except ValueError:
        # Search by name
        cursor.execute("""
            SELECT i.id, iti.old_id, iti.family_tree, i.canonical_name, i.date_of_birth, i.birth_location, i.birth_comment,
                   i.date_of_death, i.death_location, i.death_comment, i.profession,
                   i.marriage_date, i.marriage_location, i.marriage_comment
            FROM individuals i
            LEFT JOIN individual_tree_instances iti ON i.id = iti.individual_id
            WHERE i.canonical_name LIKE ?
            ORDER BY i.id
        """, (f"%{search_term}%",))

    results = cursor.fetchall()
    return results


def get_parents(conn, individual_id):
    """Get parents of an individual."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT i.id, i.canonical_name, r.relationship_type
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
        SELECT DISTINCT i.id, i.canonical_name
        FROM relationships r
        JOIN individuals i ON r.child_id = i.id
        WHERE r.parent_id = ?
        ORDER BY i.id
    """, (individual_id,))
    return cursor.fetchall()


def get_spouses(conn, individual_id, family_tree=None):
    """Get spouses of an individual by finding other parents who share children.

    If `family_tree` is provided first try to find spouses within that same tree.
    If none are found, fall back to searching across all trees where a shared child exists.
    """
    cursor = conn.cursor()

    if family_tree:
        cursor.execute("""
            SELECT DISTINCT i.id, iti.old_id, i.canonical_name,
                   i.marriage_date, i.marriage_location, i.marriage_comment
            FROM relationships r
            JOIN relationships r2 ON r.child_id = r2.child_id AND r.family_tree = r2.family_tree
            JOIN individuals i ON r2.parent_id = i.id
            JOIN individual_tree_instances iti ON i.id = iti.individual_id AND iti.family_tree = ?
            WHERE r.parent_id = ? AND r2.parent_id != r.parent_id AND r.family_tree = ?
            ORDER BY iti.old_id
        """, (family_tree, individual_id, family_tree))
        results = cursor.fetchall()
        if results:
            return results

    # Fallback: search across all trees where a shared child exists
    cursor.execute("""
        SELECT DISTINCT i.id, iti.old_id, i.canonical_name,
               i.marriage_date, i.marriage_location, i.marriage_comment
        FROM relationships r
        JOIN relationships r2 ON r.child_id = r2.child_id AND r.family_tree = r2.family_tree
        JOIN individuals i ON r2.parent_id = i.id
        JOIN individual_tree_instances iti ON i.id = iti.individual_id
        WHERE r.parent_id = ? AND r2.parent_id != r.parent_id
        ORDER BY iti.old_id
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
    db_id, old_id, family_tree, name, dob, birth_loc, birth_comment, dod, death_loc, death_comment, profession, marriage, marriage_loc, marriage_comment = individual

    print(f"\n{'='*80}")
    print(f"{name}")
    print(f"{'='*80}")
    print(f"Database ID: {db_id} (Old ID: {old_id})")
    print(f"Family Tree: {family_tree}")
    if dob or birth_loc or birth_comment:
        birth_info = "Born:"
        if dob:
            birth_info += f" {dob}"
        if birth_loc:
            birth_info += f" à {birth_loc}"
        if birth_comment:
            birth_info += f" ({birth_comment})"
        print(birth_info)
    elif birth_comment:
        print(f"Birth: {birth_comment}")

    if dod or death_loc or death_comment:
        death_info = "Died:"
        if dod:
            death_info += f" {dod}"
        if death_loc:
            death_info += f" à {death_loc}"
        if death_comment:
            death_info += f" ({death_comment})"
        print(death_info)
    elif death_comment:
        print(f"Death: {death_comment}")

    if profession:
        print(f"Profession: {profession}")

    if marriage or marriage_loc or marriage_comment:
        marriage_info = "Married:"
        if marriage:
            marriage_info += f" {marriage}"
        if marriage_loc:
            marriage_info += f" à {marriage_loc}"
        if marriage_comment:
            marriage_info += f" ({marriage_comment})"
        print(marriage_info)
    elif marriage_comment:
        print(f"Marriage: {marriage_comment}")

    # Spouses (inferred from shared children)
    spouses = get_spouses(conn, db_id, family_tree)
    if spouses:
        print(f"\nSpouse(s):")
        for sp in spouses:
            sp_id, sp_old_id, sp_name, sp_marriage, sp_marriage_loc, sp_marriage_comment = sp
            spouse_line = f"  - {sp_name} (Database ID {sp_id})"
            # Show spouse's marriage info if available
            if sp_marriage or sp_marriage_loc or sp_marriage_comment:
                minfo = ""
                if sp_marriage:
                    minfo += f" {sp_marriage}"
                if sp_marriage_loc:
                    minfo += f" à {sp_marriage_loc}"
                if sp_marriage_comment:
                    minfo += f" ({sp_marriage_comment})"
                spouse_line += f" — married:{minfo}"
            print(spouse_line)

    # Parents
    parents = get_parents(conn, db_id)
    if parents:
        print(f"\nParents:")
        for parent in parents:
            parent_type = "Father" if parent[2] == "father" else "Mother"
            print(f"  {parent_type}: {parent[1]} (Database ID {parent[0]})")

    # Children
    children = get_children(conn, db_id)
    if children:
        print(f"\nChildren ({len(children)}):")
        for child in children:
            print(f"  - {child[1]} (Database ID {child[0]})")

    # Sources
    sources = get_sources(conn, db_id)
    if sources:
        print(f"\nMentioned in {len(sources)} document(s):")
        for source in sources:
            print(f"  - {source}")


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

        # Group by individual id to avoid duplicates
        seen_ids = set()
        unique_results = []
        for result in results:
            if result[0] not in seen_ids:  # result[0] is the database id
                seen_ids.add(result[0])
                unique_results.append(result)

        if len(unique_results) == 1:
            # Exactly one unique individual found. Perform an ID-based lookup
            person = unique_results[0]
            person_id = person[0]
            print(
                f"Single match found: {person[3]} (Database ID {person_id}). Showing details...")
            # Re-run the query using the ID path to ensure we get the canonical ID-based result
            id_results = find_individual(conn, str(person_id))
            if id_results:
                display_individual(conn, id_results[0])
            else:
                # Fallback to the original row if the ID-based lookup unexpectedly failed
                display_individual(conn, person)
        else:
            print(f"\nFound {len(unique_results)} matching individuals:")
            print("-" * 100)
            for individual in unique_results:
                # individual: id, old_id, family_tree, name, ...
                print(
                    f"{individual[0]:4d}  [{individual[2] or 'N/A':<30}]  {individual[3]}")
            print("-" * 100)
            print("\nUse the database ID number to see details for a specific person.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
