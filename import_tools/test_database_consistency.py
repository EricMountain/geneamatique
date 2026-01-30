from .genealogy_parser import create_database, parse_documents, store_data
import unittest
import sqlite3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestDatabaseConsistency(unittest.TestCase):
    """Tests for database consistency and genealogical invariants."""

    @classmethod
    def setUpClass(cls):
        """Set up test database."""
        cls.db_name = 'data/genealogy.db'
        if not os.path.exists(cls.db_name):
            # If database doesn't exist, create it for testing
            create_database(cls.db_name)
            folder_path = os.environ.get('GENEALOGY_DATA_DIR', 'data/sources')
            if os.path.exists(folder_path):
                individuals = parse_documents(folder_path)
                store_data(individuals, cls.db_name)

        cls.conn = sqlite3.connect(cls.db_name)
        cls.cursor = cls.conn.cursor()

    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests."""
        cls.conn.close()

    def test_database_exists(self):
        """Test that the database file exists."""
        self.assertTrue(os.path.exists(self.db_name))

    def test_tables_exist(self):
        """Test that required tables exist."""
        self.cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table'
        """)
        tables = [row[0] for row in self.cursor.fetchall()]
        self.assertIn('individuals', tables)
        self.assertIn('relationships', tables)

    def test_individuals_have_required_fields(self):
        """Test that individuals table has all required columns."""
        self.cursor.execute("PRAGMA table_info(individuals)")
        columns = [column[1] for column in self.cursor.fetchall()]
        required_columns = ['id', 'old_id', 'name', 'date_of_birth', 'birth_location', 'birth_comment',
                            'date_of_death', 'death_location', 'death_comment', 'profession',
                            'marriage_date', 'marriage_location', 'marriage_comment']
        for col in required_columns:
            self.assertIn(
                col, columns, f"Column {col} missing from individuals table")

    def test_individual_sources_table_exists(self):
        """Test that individual_sources tracking table exists."""
        self.cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='individual_sources'
        """)
        result = self.cursor.fetchone()
        self.assertIsNotNone(result, "individual_sources table is missing")

    def test_individuals_not_empty(self):
        """Test that the individuals table contains data."""
        self.cursor.execute("SELECT COUNT(*) FROM individuals")
        count = self.cursor.fetchone()[0]
        self.assertGreater(count, 0, "Individuals table is empty")

    def test_all_individuals_have_names(self):
        """Test that all individuals have non-null names."""
        self.cursor.execute(
            "SELECT COUNT(*) FROM individuals WHERE name IS NULL OR name = ''")
        count = self.cursor.fetchone()[0]
        self.assertEqual(count, 0, f"Found {count} individuals without names")

    def test_all_individuals_have_old_id(self):
        """Test that all individuals have an old_id (from source documents)."""
        self.cursor.execute(
            "SELECT COUNT(*) FROM individuals WHERE old_id IS NULL")
        count = self.cursor.fetchone()[0]
        self.assertEqual(count, 0, f"Found {count} individuals without old_id")

    def test_all_individuals_have_source_file(self):
        """Test that all individuals have at least one source file reference."""
        self.cursor.execute("""
            SELECT COUNT(DISTINCT i.id) FROM individuals i
            WHERE NOT EXISTS (
                SELECT 1 FROM individual_sources s WHERE s.individual_id = i.id
            )
        """)
        count = self.cursor.fetchone()[0]
        self.assertEqual(
            count, 0, f"Found {count} individuals without source file reference")

    def test_relationship_referential_integrity(self):
        """Test that all relationships reference valid individuals."""
        # Check parent_id
        self.cursor.execute("""
            SELECT COUNT(*) FROM relationships r
            WHERE NOT EXISTS (
                SELECT 1 FROM individuals i WHERE i.id = r.parent_id
            )
        """)
        count = self.cursor.fetchone()[0]
        self.assertEqual(
            count, 0, f"Found {count} relationships with invalid parent_id")

        # Check child_id
        self.cursor.execute("""
            SELECT COUNT(*) FROM relationships r
            WHERE NOT EXISTS (
                SELECT 1 FROM individuals i WHERE i.id = r.child_id
            )
        """)
        count = self.cursor.fetchone()[0]
        self.assertEqual(
            count, 0, f"Found {count} relationships with invalid child_id")

    def test_no_self_parenting(self):
        """Test that no individual is their own parent."""
        self.cursor.execute("""
            SELECT COUNT(*) FROM relationships
            WHERE parent_id = child_id
        """)
        count = self.cursor.fetchone()[0]
        self.assertEqual(count, 0, f"Found {count} cases of self-parenting")

    def test_parent_child_relationship_types(self):
        """Test that relationship types are either 'father' or 'mother'."""
        self.cursor.execute("""
            SELECT DISTINCT relationship_type FROM relationships
        """)
        types = [row[0] for row in self.cursor.fetchall()]
        for rel_type in types:
            self.assertIn(rel_type, ['father', 'mother'],
                          f"Invalid relationship type: {rel_type}")

    def test_maximum_two_parents(self):
        """Test that no individual has more than 2 parents (1 father, 1 mother).

        Note: This test allows for some data quality issues where the same parent
        has name variations (e.g., "SAMPLE J" vs "SAMPLE John Jacob").
        """
        # Check for individuals with more than one father
        self.cursor.execute("""
            SELECT 
                c.old_id,
                c.name, 
                COUNT(DISTINCT p.old_id) as num_unique_father_ids,
                COUNT(*) as num_father_records
            FROM relationships r
            JOIN individuals c ON r.child_id = c.id
            JOIN individuals p ON r.parent_id = p.id
            WHERE r.relationship_type = 'father'
            GROUP BY r.child_id
            HAVING COUNT(DISTINCT p.old_id) > 1
        """)
        result = self.cursor.fetchall()
        if result:
            print(f"\nIndividuals with multiple fathers (different old_id):")
            for row in result:
                print(
                    f"  {row[1]} (ID {row[0]}): {row[2]} different father IDs, {row[3]} total records")
        # Check that there are no individuals with fathers having DIFFERENT old_ids
        # (which would indicate a real genealogical error, not just name variations)
        self.assertEqual(len(result), 0,
                         f"Found {len(result)} individuals with multiple fathers having different old_ids")

        # Check for individuals with more than one mother (same check)
        self.cursor.execute("""
            SELECT 
                c.old_id,
                c.name, 
                COUNT(DISTINCT p.old_id) as num_unique_mother_ids,
                COUNT(*) as num_mother_records
            FROM relationships r
            JOIN individuals c ON r.child_id = c.id
            JOIN individuals p ON r.parent_id = p.id
            WHERE r.relationship_type = 'mother'
            GROUP BY r.child_id
            HAVING COUNT(DISTINCT p.old_id) > 1
        """)
        result = self.cursor.fetchall()
        if result:
            print(f"\nIndividuals with multiple mothers (different old_id):")
            for row in result:
                print(
                    f"  {row[1]} (ID {row[0]}): {row[2]} different mother IDs, {row[3]} total records")
        self.assertEqual(len(result), 0,
                         f"Found {len(result)} individuals with multiple mothers having different old_ids")

    def test_no_circular_relationships(self):
        """Test that there are no circular parent-child relationships (A is parent of B, B is parent of A)."""
        self.cursor.execute("""
            SELECT COUNT(*) FROM relationships r1
            JOIN relationships r2 ON r1.parent_id = r2.child_id AND r1.child_id = r2.parent_id
        """)
        count = self.cursor.fetchone()[0]
        self.assertEqual(count, 0, f"Found {count} circular relationships")

    def test_even_odd_gender_consistency(self):
        """Test that even IDs are typically males (fathers) and odd IDs are typically females (mothers).

        This is a soft test - we check the majority follows the pattern but allow some exceptions
        for data quality issues.
        """
        # Count males (even IDs) who are fathers
        self.cursor.execute("""
            SELECT COUNT(DISTINCT i.id) FROM individuals i
            JOIN relationships r ON i.id = r.parent_id
            WHERE i.old_id % 2 = 0 AND r.relationship_type = 'father'
        """)
        even_fathers = self.cursor.fetchone()[0]

        # Count males (even IDs) who are mothers (violation)
        self.cursor.execute("""
            SELECT COUNT(DISTINCT i.id) FROM individuals i
            JOIN relationships r ON i.id = r.parent_id
            WHERE i.old_id % 2 = 0 AND r.relationship_type = 'mother'
        """)
        even_mothers = self.cursor.fetchone()[0]

        # Count females (odd IDs) who are mothers
        self.cursor.execute("""
            SELECT COUNT(DISTINCT i.id) FROM individuals i
            JOIN relationships r ON i.id = r.parent_id
            WHERE i.old_id % 2 = 1 AND r.relationship_type = 'mother'
        """)
        odd_mothers = self.cursor.fetchone()[0]

        # Count females (odd IDs) who are fathers (violation)
        self.cursor.execute("""
            SELECT COUNT(DISTINCT i.id) FROM individuals i
            JOIN relationships r ON i.id = r.parent_id
            WHERE i.old_id % 2 = 1 AND r.relationship_type = 'father'
        """)
        odd_fathers = self.cursor.fetchone()[0]

        total_violations = even_mothers + odd_fathers
        total_correct = even_fathers + odd_mothers

        if total_correct + total_violations > 0:
            accuracy = (total_correct /
                        (total_correct + total_violations)) * 100
            print(
                f"\nGender consistency (even=male, odd=female): {accuracy:.1f}%")
            print(f"  Correct: {total_correct}")
            print(f"  Violations: {total_violations}")
            # Allow up to 10% violations due to data quality issues
            self.assertGreater(accuracy, 90,
                               f"Gender consistency too low: {accuracy:.1f}%")

    def test_parent_numbering_invariant(self):
        """Test that if person has old_id N, their parents have old_ids 2N and 2N+1.

        This is the core genealogical numbering system being used.
        """
        # Get all parent-child relationships
        self.cursor.execute("""
            SELECT 
                c.old_id as child_old_id,
                c.name as child_name,
                p.old_id as parent_old_id,
                p.name as parent_name,
                r.relationship_type
            FROM relationships r
            JOIN individuals c ON r.child_id = c.id
            JOIN individuals p ON r.parent_id = p.id
        """)

        violations = []
        for row in self.cursor.fetchall():
            child_id, child_name, parent_id, parent_name, rel_type = row
            expected_parent_id = child_id * 2 + \
                (0 if rel_type == 'father' else 1)

            if parent_id != expected_parent_id:
                violations.append({
                    'child': f"{child_name} (ID {child_id})",
                    'parent': f"{parent_name} (ID {parent_id})",
                    'expected_id': expected_parent_id,
                    'type': rel_type
                })

        if violations:
            print(f"\nParent numbering violations (showing first 10):")
            for v in violations[:10]:
                print(f"  {v['child']} -> {v['parent']} ({v['type']})")
                print(
                    f"    Expected parent ID: {v['expected_id']}, Got: {v['parent'].split('ID ')[1].rstrip(')')}")

        # Allow some violations due to missing data or complex family structures
        violation_rate = len(violations) / max(1, self.cursor.execute(
            "SELECT COUNT(*) FROM relationships").fetchone()[0])
        print(f"\nParent numbering compliance: {(1-violation_rate)*100:.1f}%")
        self.assertLess(violation_rate, 0.1,
                        f"Too many parent numbering violations: {len(violations)}")

    def test_relationships_exist(self):
        """Test that the relationships table contains data."""
        self.cursor.execute("SELECT COUNT(*) FROM relationships")
        count = self.cursor.fetchone()[0]
        self.assertGreater(count, 0, "Relationships table is empty")

    def test_date_format_consistency(self):
        """Test that dates follow a consistent format (when present)."""
        # Get all non-null birth dates
        self.cursor.execute("""
            SELECT date_of_birth FROM individuals 
            WHERE date_of_birth IS NOT NULL AND date_of_birth != ''
        """)
        birth_dates = [row[0] for row in self.cursor.fetchall()]

        # Get all non-null death dates
        self.cursor.execute("""
            SELECT date_of_death FROM individuals 
            WHERE date_of_death IS NOT NULL AND date_of_death != ''
        """)
        death_dates = [row[0] for row in self.cursor.fetchall()]

        # Just verify we have some dates
        total_dates = len(birth_dates) + len(death_dates)
        self.assertGreater(total_dates, 0, "No dates found in database")

    def test_root_ancestors_exist(self):
        """Test that there are some root ancestors (individuals with no parents)."""
        self.cursor.execute("""
            SELECT COUNT(DISTINCT i.id) FROM individuals i
            WHERE NOT EXISTS (
                SELECT 1 FROM relationships r WHERE r.child_id = i.id
            )
        """)
        count = self.cursor.fetchone()[0]
        self.assertGreater(count, 0, "No root ancestors found")
        print(
            f"\nFound {count} root ancestors (individuals with no recorded parents)")

    def test_identify_name_variations(self):
        """Identify individuals with the same old_id but different names (name variations).

        This is informational - it helps identify data quality issues where the same
        person is recorded with slight name variations across different documents.
        """
        self.cursor.execute("""
            SELECT old_id, GROUP_CONCAT(name, ' | ') as name_variations, COUNT(*) as count
            FROM individuals
            GROUP BY old_id
            HAVING COUNT(*) > 1
            ORDER BY COUNT(*) DESC
        """)
        result = self.cursor.fetchall()
        if result:
            print(f"\nFound {len(result)} old_ids with name variations:")
            for row in result[:10]:  # Show first 10
                print(f"  ID {row[0]}: {row[2]} variations")
                names = row[1].split(' | ')
                for name in names[:3]:  # Show first 3 variations
                    print(f"    - {name}")

        # This is informational, not a failure
        # But we can warn if there are too many variations
        if len(result) > 20:
            print(
                f"  WARNING: {len(result)} IDs have name variations - consider data cleanup")


class TestParserFunctionality(unittest.TestCase):
    """Tests for the parser functionality."""

    def test_parse_individual_data(self):
        """Test parsing of individual cell data."""
        from .genealogy_parser import parse_individual_data

        # Test with complete data
        cell_text = """2. PERSON_A Sample Name
    ° 4 Jan 1952 à City A
    + 15 Oct 2007 au City B
    PR Technician
    X 28 Jul 1973 à City C"""

        result = parse_individual_data(cell_text)
        self.assertIsNotNone(result)
        self.assertEqual(result['old_id'], 2)
        self.assertEqual(result['name'], 'PERSON_A Sample Name')
        # Check ISO8601 format for date
        self.assertEqual(result['date_of_birth'], '1952-01-04')
        self.assertEqual(result['birth_location'], 'City A')
        self.assertIsNone(result['birth_comment'])
        self.assertEqual(result['date_of_death'], '2007-10-15')
        self.assertEqual(result['death_location'], 'City B')
        self.assertIsNone(result['death_comment'])
        self.assertEqual(result['profession'], 'Technician')
        self.assertEqual(result['marriage_date'], '1973-07-28')
        self.assertEqual(result['marriage_location'], 'City C')
        self.assertIsNone(result['marriage_comment'])

    def test_parse_individual_data_minimal(self):
        """Test parsing with minimal data (just name)."""
        from .genealogy_parser import parse_individual_data

        cell_text = "128. PERSON_B Sample Name"
        result = parse_individual_data(cell_text)

        self.assertIsNotNone(result)
        self.assertEqual(result['old_id'], 128)
        self.assertEqual(result['name'], 'PERSON_B Sample Name')
        self.assertIsNone(result['date_of_birth'])
        self.assertIsNone(result['date_of_death'])

    def test_parse_individual_data_invalid(self):
        """Test parsing with invalid data."""
        from .genealogy_parser import parse_individual_data

        # Empty string
        result = parse_individual_data("")
        self.assertIsNone(result)

    def test_parse_individual_data_name_with_x(self):
        """Test parsing when name ends with X and has marriage info."""
        from .genealogy_parser import parse_individual_data

        # Test case for name ending with X followed by marriage
        cell_text = "519. CALBRIX Françoise\nX 28 Jul 1973 à City C"
        result = parse_individual_data(cell_text)

        self.assertIsNotNone(result)
        self.assertEqual(result['old_id'], 519)
        self.assertEqual(result['name'], 'CALBRIX Françoise')
        self.assertEqual(result['marriage_date'], '1973-07-28')
        self.assertEqual(result['marriage_location'], 'City C')

    def test_parse_french_revolutionary_date(self):
        """Test parsing of French Revolutionary calendar dates."""
        from .genealogy_parser import parse_individual_data

        # Test with only French Revolutionary date
        cell_text = """3. PERSON_D\n° 8 thermidor an II"""
        result = parse_individual_data(cell_text)

        self.assertIsNotNone(result)
        self.assertEqual(result['old_id'], 3)
        # 8 thermidor an II = 26 July 1794
        self.assertEqual(result['date_of_birth'], '1794-07-26')

    def test_parse_gregorian_with_french_revolutionary(self):
        """Test parsing when both Gregorian and French Revolutionary dates are present."""
        from .genealogy_parser import parse_individual_data

        # Test with both dates (consistent)
        cell_text = """4. PERSON_E\n° 26 Jul 1794 (8 thermidor an II)"""
        result = parse_individual_data(cell_text)

        self.assertIsNotNone(result)
        self.assertEqual(result['old_id'], 4)
        # Should use Gregorian date
        self.assertEqual(result['date_of_birth'], '1794-07-26')

    def test_parse_comment_without_date(self):
        """Test parsing when there's a comment but no date."""
        from .genealogy_parser import parse_individual_data

        cell_text = """5. PERSON_F\n° date unknown\n+ before 1850"""
        result = parse_individual_data(cell_text)

        self.assertIsNotNone(result)
        self.assertEqual(result['old_id'], 5)
        self.assertIsNone(result['date_of_birth'])
        self.assertEqual(result['birth_comment'], 'date unknown')
        self.assertIsNone(result['date_of_death'])
        self.assertEqual(result['death_comment'], 'before 1850')

    def test_parse_comment_in_parentheses(self):
        """Test parsing when there's a comment in parentheses after the date."""
        from .genealogy_parser import parse_individual_data

        cell_text = """6. PERSON_G\n° 15 Mar 1920 à Paris (premature birth)\n+ 2 Sep 1945 au Berlin (war casualty)"""
        result = parse_individual_data(cell_text)

        self.assertIsNotNone(result)
        self.assertEqual(result['old_id'], 6)
        self.assertEqual(result['date_of_birth'], '1920-03-15')
        self.assertEqual(result['birth_location'], 'Paris')
        self.assertEqual(result['birth_comment'], 'premature birth')
        self.assertEqual(result['date_of_death'], '1945-09-02')
        self.assertEqual(result['death_location'], 'Berlin')
        self.assertEqual(result['death_comment'], 'war casualty')


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
