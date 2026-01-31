import sqlite3
import unittest

from import_tools import query_genealogy


class TestQueryGenealogy(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect('data/genealogy.db')

    def tearDown(self):
        self.conn.close()

    def test_get_spouses_for_19(self):
        spouses = query_genealogy.get_spouses(
            self.conn, 19, "Généalogie d'Eric")
        # Expect at least one spouse with ID 352 (MANOURY Natacha Brigitte)
        self.assertTrue(any(sp[0] == 352 for sp in spouses),
                        f"Spouses found: {spouses}")


if __name__ == '__main__':
    unittest.main()
