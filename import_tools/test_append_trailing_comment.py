import os
import sqlite3
import unittest

from .genealogy_parser import create_database, store_data


class TestAppendTrailingComment(unittest.TestCase):
    def setUp(self):
        self.db_name = 'test_trailing.db'
        if os.path.exists(self.db_name):
            os.remove(self.db_name)
        create_database(self.db_name)

    def tearDown(self):
        if os.path.exists(self.db_name):
            os.remove(self.db_name)

    def test_append_text_after_id_to_name_comment(self):
        # First occurrence defines the individual
        ind1 = {
            'old_id': 5,
            'family_tree': 'TreeA',
            'name': 'Smith, John',
            'name_comment': None,
            'date_of_birth': '1900-01-01',
            'birth_location': None,
            'birth_comment': None,
            'date_of_death': None,
            'death_location': None,
            'death_comment': None,
            'profession': None,
            'marriage_date': None,
            'marriage_location': None,
            'marriage_comment': None,
            'source_file': 'file1.odt'
        }

        # Second occurrence has no event markers but contains trailing text
        ind2 = {
            'old_id': 5,
            'family_tree': 'TreeA',
            'name': 'Smith, John',
            'name_comment': None,
            'date_of_birth': None,
            'birth_location': None,
            'birth_comment': None,
            'date_of_death': None,
            'death_location': None,
            'death_comment': None,
            'profession': None,
            'marriage_date': None,
            'marriage_location': None,
            'marriage_comment': None,
            # This simulates the raw text that followed the ID in the cell
            'text_after_id': 'note: served in 14-18 war',
            'source_file': 'file2.odt'
        }

        num_individuals, num_instances, num_relationships, merged_individuals, warning_count = store_data([ind1, ind2], db_name=self.db_name)

        conn = sqlite3.connect(self.db_name)
        cur = conn.cursor()
        cur.execute("SELECT name_comment FROM individuals WHERE canonical_name = ?", ('Smith, John',))
        row = cur.fetchone()
        conn.close()

        # There should be no conflict warnings for the trailing-text-only entry
        self.assertEqual(warning_count, 0)

        self.assertIsNotNone(row, "Canonical individual not found")
        name_comment = row[0]
        self.assertIsNotNone(name_comment)
        self.assertIn('served in 14-18', name_comment)

    def test_trailing_text_does_not_cause_conflict(self):
        # Set up existing canonical individual
        ind1 = {
            'old_id': 85,
            'family_tree': 'Généalogie d\'Eric',
            'name': 'AYRAL Julie',
            'name_comment': None,
            'date_of_birth': None,
            'birth_location': None,
            'birth_comment': None,
            'date_of_death': None,
            'death_location': None,
            'death_comment': None,
            'profession': None,
            'marriage_date': None,
            'marriage_location': None,
            'marriage_comment': None,
            'source_file': 'file1.odt'
        }

        # Conflicting-looking second entry with no event markers (should not be treated as conflict)
        ind2 = {
            'old_id': 85,
            'family_tree': 'Généalogie d\'Eric',
            'name': "fille Antoine Ayral mort à Mauressargue le 27 septembre 1811 et d'Elisabeth Bourdori ou Boudoin",
            'name_comment': None,
            'date_of_birth': None,
            'birth_location': None,
            'birth_comment': None,
            'date_of_death': None,
            'death_location': None,
            'death_comment': None,
            'profession': None,
            'marriage_date': None,
            'marriage_location': None,
            'marriage_comment': None,
            'text_after_id': "fille Antoine Ayral mort à Mauressargue le 27 septembre 1811 et d'Elisabeth Bourdori ou Boudoin",
            'source_file': 'file2.odt'
        }

        num_individuals, num_instances, num_relationships, merged_individuals, warning_count = store_data([ind1, ind2], db_name=self.db_name)

        # No conflict should be raised; trailing text should be appended to name_comment
        self.assertEqual(warning_count, 0)

        conn = sqlite3.connect(self.db_name)
        cur = conn.cursor()
        cur.execute("SELECT name_comment FROM individuals WHERE canonical_name = ?", ('AYRAL Julie',))
        row = cur.fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertIn('Mauressargue', row[0])

    def test_similar_text_triggers_conflict(self):
        ind1 = {
            'old_id': 200,
            'family_tree': 'TreeA',
            'name': 'SMITH John',
            'name_comment': None,
            'date_of_birth': None,
            'birth_location': None,
            'birth_comment': None,
            'date_of_death': None,
            'death_location': None,
            'death_comment': None,
            'profession': None,
            'marriage_date': None,
            'marriage_location': None,
            'marriage_comment': None,
            'source_file': 'file1.odt'
        }

        # Second entry has trailing text that is essentially the canonical name
        ind2 = {
            'old_id': 200,
            'family_tree': 'TreeA',
            'name': 'Different description that looks like an alternate person',
            'name_comment': None,
            'date_of_birth': None,
            'birth_location': None,
            'birth_comment': None,
            'date_of_death': None,
            'death_location': None,
            'death_comment': None,
            'profession': None,
            'marriage_date': None,
            'marriage_location': None,
            'marriage_comment': None,
            'text_after_id': 'SMITH John',
            'source_file': 'file2.odt'
        }

        num_individuals, num_instances, num_relationships, merged_individuals, warning_count = store_data([ind1, ind2], db_name=self.db_name)

        # A conflict should be raised because the trailing text looks like the canonical name
        self.assertGreater(warning_count, 0)

        conn = sqlite3.connect(self.db_name)
        cur = conn.cursor()
        cur.execute("SELECT name_comment FROM individuals WHERE canonical_name = ?", ('SMITH John',))
        row = cur.fetchone()
        conn.close()

        # Name comment should not have the trailing text appended
        if row:
            self.assertTrue(row[0] is None or 'SMITH John' not in row[0])


if __name__ == '__main__':
    unittest.main()
