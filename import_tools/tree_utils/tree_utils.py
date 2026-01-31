"""Tree-building helpers for genealogy visualizers.

This module provides DB query helpers (extracted from tree_visualizer.py) and
functions to build serializable trees for use by JSON exporters and UI.
"""
from typing import Dict, List, Optional, Set
import sqlite3


def find_individual(conn: sqlite3.Connection, search_term: str, family_tree: Optional[str] = None):
    """Find individuals by old_id or name (same behavior as original function).

    Returns list of tuples matching the original signature used by
    `tree_visualizer.main()` so existing code remains compatible.
    """
    cursor = conn.cursor()

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

    return cursor.fetchall()


def get_parents(conn: sqlite3.Connection, individual_id: int, family_tree: Optional[str] = None):
    """Return parent records for an individual (tuples matching prior code)."""
    cursor = conn.cursor()

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


def get_children(conn: sqlite3.Connection, individual_id: int, family_tree: Optional[str] = None):
    """Return child records for an individual (tuples matching prior code)."""
    cursor = conn.cursor()

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


def get_spouses(conn: sqlite3.Connection, individual_id: int, family_tree: str):
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


def _record_to_node(record: tuple, family_tree: Optional[str] = None) -> Dict:
    """Convert a DB record tuple to a serializable node dict."""
    # record expected form (db_id, old_id, canonical_name, date_of_birth, birth_location, birth_comment, date_of_death, death_location, death_comment, marriage_date, marriage_location, marriage_comment, ...)
    node = {
        'db_id': record[0],
        'old_id': record[1],
        'name': record[2],
        'date_of_birth': record[3],
        'birth_location': record[4],
        'birth_comment': record[5],
        'date_of_death': record[6],
        'death_location': record[7],
        'death_comment': record[8],
        'marriage_date': record[9],
        'marriage_location': record[10],
        'marriage_comment': record[11],
        'family_tree': family_tree,
        'children': []
    }
    return node


def build_ancestor_tree(conn: sqlite3.Connection, individual_id: int, family_tree: Optional[str], max_depth: int = 10, visited: Optional[Set[int]] = None, depth: int = 0) -> Optional[Dict]:
    """Build an ancestor tree (parents are in `children` list) as nested dicts."""
    if visited is None:
        visited = set()
    if individual_id in visited or depth > max_depth:
        return None
    visited.add(individual_id)

    cursor = conn.cursor()
    cursor.execute("""
        SELECT i.id, iti.old_id, i.canonical_name,
               i.date_of_birth, i.birth_location, i.birth_comment,
               i.date_of_death, i.death_location, i.death_comment,
               i.marriage_date, i.marriage_location, i.marriage_comment
        FROM individuals i
        JOIN individual_tree_instances iti ON i.id = iti.individual_id
        WHERE i.id = ? AND iti.family_tree = ?
    """, (individual_id, family_tree))
    result = cursor.fetchone()
    if not result:
        return None

    node = _record_to_node(result, family_tree)

    parents = get_parents(conn, individual_id, family_tree)

    # Cross-tree fallback: try other instances of same (name,dob)
    if not parents and node['date_of_birth'] and node['name']:
        cursor.execute("""
            SELECT DISTINCT i.id, iti.family_tree
            FROM individuals i
            JOIN individual_tree_instances iti ON i.id = iti.individual_id
            WHERE i.canonical_name = ? AND i.date_of_birth = ? AND i.id != ?
        """, (node['name'], node['date_of_birth'], individual_id))
        other_instances = cursor.fetchall()
        for other_id, other_tree in other_instances:
            parents = get_parents(conn, other_id, other_tree)
            if parents:
                # switch to other instance
                node_other = build_ancestor_tree(
                    conn, other_id, other_tree, max_depth, visited, depth)
                return node_other

    if parents:
        # collect mother first then father (matching existing visualization order)
        mother = None
        father = None
        for p in parents:
            rel_type = p[12] if len(p) > 12 else None
            if rel_type == 'father':
                father = p
            else:
                mother = p

        parents_to_add = []
        if mother:
            parents_to_add.append(mother)
        if father:
            parents_to_add.append(father)

        for p in parents_to_add:
            parent_id = p[0]
            parent_tree = p[13] if len(p) > 13 else None
            child_node = build_ancestor_tree(
                conn, parent_id, parent_tree or family_tree, max_depth, visited, depth + 1)
            if child_node:
                node['children'].append(child_node)

    return node


def build_descendant_tree(conn: sqlite3.Connection, individual_id: int, family_tree: Optional[str], max_depth: int = 10, visited: Optional[Set[int]] = None, depth: int = 0) -> Optional[Dict]:
    """Build a descendant tree (children are in `children` list) as nested dicts."""
    if visited is None:
        visited = set()
    if individual_id in visited or depth > max_depth:
        return None
    visited.add(individual_id)

    cursor = conn.cursor()
    cursor.execute("""
        SELECT i.id, iti.old_id, i.canonical_name,
               i.date_of_birth, i.birth_location, i.birth_comment,
               i.date_of_death, i.death_location, i.death_comment,
               i.marriage_date, i.marriage_location, i.marriage_comment
        FROM individuals i
        JOIN individual_tree_instances iti ON i.id = iti.individual_id
        WHERE i.id = ? AND iti.family_tree = ?
    """, (individual_id, family_tree))
    result = cursor.fetchone()
    if not result:
        return None

    node = _record_to_node(result, family_tree)

    children = get_children(conn, individual_id, family_tree)

    if not children and node['date_of_birth'] and node['name']:
        cursor.execute("""
            SELECT DISTINCT i.id, iti.family_tree
            FROM individuals i
            JOIN individual_tree_instances iti ON i.id = iti.individual_id
            WHERE i.canonical_name = ? AND i.date_of_birth = ? AND i.id != ?
        """, (node['name'], node['date_of_birth'], individual_id))
        other_instances = cursor.fetchall()
        for other_id, other_tree in other_instances:
            children = get_children(conn, other_id, other_tree)
            if children:
                break

    if children:
        for child in children:
            child_id = child[0]
            child_tree = child[12] if len(child) > 12 else None
            child_node = build_descendant_tree(
                conn, child_id, child_tree or family_tree, max_depth, visited, depth + 1)
            if child_node:
                node['children'].append(child_node)

    return node
