import sqlite3
import unittest
from import_tools import tree_utils


class TestTreeUtils(unittest.TestCase):
    def setUp(self):
        # In-memory DB with minimal schema for testing
        self.conn = sqlite3.connect(':memory:')
        cur = self.conn.cursor()
        cur.execute('''
            CREATE TABLE individuals (
                id INTEGER PRIMARY KEY,
                canonical_name TEXT,
                name_comment TEXT,
                date_of_birth TEXT,
                birth_location TEXT,
                birth_comment TEXT,
                date_of_death TEXT,
                death_location TEXT,
                death_comment TEXT,
                marriage_date TEXT,
                marriage_location TEXT,
                marriage_comment TEXT
            )
        ''')
        cur.execute('''
            CREATE TABLE individual_tree_instances (
                individual_id INTEGER,
                family_tree TEXT,
                old_id INTEGER
            )
        ''')
        cur.execute('''
            CREATE TABLE relationships (
                parent_id INTEGER,
                child_id INTEGER,
                relationship_type TEXT,
                family_tree TEXT
            )
        ''')
        # Insert sample people: A (1), B father (2), C mother (3), D child (4)
        cur.executemany('INSERT INTO individuals (id, canonical_name, date_of_birth) VALUES (?, ?, ?)', [
            (1, 'A Person', '1900-01-01'),
            (2, 'B Father', '1870-01-01'),
            (3, 'C Mother', '1872-02-02'),
            (4, 'D Child', '1925-03-03')
        ])
        cur.executemany('INSERT INTO individual_tree_instances (individual_id, family_tree, old_id) VALUES (?, ?, ?)', [
            (1, 'T1', 1),
            (2, 'T1', 2),
            (3, 'T1', 3),
            (4, 'T1', 4)
        ])
        # Relationships: 2 father of 1, 3 mother of 1, 1 parent of 4
        cur.executemany('INSERT INTO relationships (parent_id, child_id, relationship_type, family_tree) VALUES (?, ?, ?, ?)', [
            (2, 1, 'father', 'T1'),
            (3, 1, 'mother', 'T1'),
            (1, 4, 'father', 'T1')
        ])
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_find_individual_by_name(self):
        results = tree_utils.find_individual(self.conn, 'A Person')
        self.assertTrue(results)
        self.assertEqual(results[0][3], 'A Person')

    def test_build_ancestor_tree(self):
        tree = tree_utils.build_ancestor_tree(self.conn, 1, 'T1')
        self.assertIsNotNone(tree)
        self.assertEqual(tree['name'], 'A Person')
        # parents should include both B Father and C Mother
        parent_names = {c['name'] for c in tree['children']}
        self.assertEqual(parent_names, {'B Father', 'C Mother'})

    def test_build_descendant_tree(self):
        tree = tree_utils.build_descendant_tree(self.conn, 1, 'T1')
        self.assertIsNotNone(tree)
        self.assertEqual(tree['name'], 'A Person')
        child_names = {c['name'] for c in tree['children']}
        self.assertEqual(child_names, {'D Child'})


if __name__ == '__main__':
    unittest.main()
