import unittest
import sqlite3
import os


class TestGenealogyParser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_name = 'genealogy_test.db'
        cls.conn = sqlite3.connect(cls.db_name)
        cls.cursor = cls.conn.cursor()
        cls.cursor.execute('''
        CREATE TABLE IF NOT EXISTS individuals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            date_of_birth TEXT,
            date_of_death TEXT,
            profession TEXT,
            marriage TEXT
        )
        ''')

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        os.remove(cls.db_name)

    def test_insert_individual(self):
        self.cursor.execute('''
        INSERT INTO individuals (name, date_of_birth, date_of_death, profession, marriage)
        VALUES (?, ?, ?, ?, ?)
        ''', ('John Doe', '1980-01-01', '2020-01-01', 'Engineer', 'Married'))
        self.conn.commit()

        self.cursor.execute(
            'SELECT * FROM individuals WHERE name = ?', ('John Doe',))
        individual = self.cursor.fetchone()
        self.assertIsNotNone(individual)
        self.assertEqual(individual[1], 'John Doe')

    def test_database_schema(self):
        self.cursor.execute("PRAGMA table_info(individuals)")
        columns = [column[1] for column in self.cursor.fetchall()]
        expected_columns = ['id', 'name', 'date_of_birth',
                            'date_of_death', 'profession', 'marriage']
        self.assertListEqual(columns, expected_columns)


if __name__ == '__main__':
    unittest.main()
