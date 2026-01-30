import unittest
from .util import gregorian_to_republican, republican_to_gregorian


class TestCalendarConversions(unittest.TestCase):

    def test_start_date_conversion(self):
        """Test the start of the Republican calendar."""
        self.assertEqual(gregorian_to_republican(1792, 9, 22), (1, 1, 1))
        self.assertEqual(republican_to_gregorian(1, 1, 1), (1792, 9, 22))

    def test_end_of_year_1(self):
        """Test the end of Republican year 1."""
        # Year 1 ends on September 21, 1793
        self.assertEqual(gregorian_to_republican(1793, 9, 21), (1, 13, 5))
        self.assertEqual(republican_to_gregorian(1, 13, 5), (1793, 9, 21))

    def test_start_of_year_2(self):
        """Test the start of Republican year 2."""
        self.assertEqual(gregorian_to_republican(1793, 9, 22), (2, 1, 1))
        self.assertEqual(republican_to_gregorian(2, 1, 1), (1793, 9, 22))

    def test_leap_year_complementary_days(self):
        """Test complementary days in a leap year (year 3)."""
        # Year 3 is leap, has 6 complementary days
        # Complementary day 6 of year 3 corresponds to September 22, 1795
        self.assertEqual(republican_to_gregorian(3, 13, 6), (1795, 9, 22))
        self.assertEqual(gregorian_to_republican(1795, 9, 22), (3, 13, 6))

    def test_non_leap_year_complementary_days(self):
        """Test complementary days in a non-leap year (year 2)."""
        # Year 2 is non-leap, has 5 complementary days
        # Last day of year 2: September 21, 1794
        self.assertEqual(gregorian_to_republican(1794, 9, 21), (2, 13, 5))
        self.assertEqual(republican_to_gregorian(2, 13, 5), (1794, 9, 21))

    def test_mid_year_conversion(self):
        """Test a mid-year date."""
        # January 1, 1793 -> Republican year 1, month 4, day 12
        self.assertEqual(gregorian_to_republican(1793, 1, 1), (1, 4, 12))
        self.assertEqual(republican_to_gregorian(1, 4, 12), (1793, 1, 1))

    def test_random_date_conversion(self):
        """Test conversion of a random date."""
        # May 15, 1794 -> Republican year 2, month 9, day 25
        self.assertEqual(gregorian_to_republican(1794, 5, 15), (2, 8, 26))
        self.assertEqual(republican_to_gregorian(2, 8, 26), (1794, 5, 15))
        self.assertEqual(gregorian_to_republican(1799, 12, 31), (8, 4, 10))
        self.assertEqual(republican_to_gregorian(8, 4, 10), (1799, 12, 31))

    def test_round_trip(self):
        """Test round-trip conversion for various dates."""
        test_dates = [
            (1792, 9, 22),
            (1793, 1, 1),
            (1794, 9, 21),
            (1795, 9, 21),
            (1800, 1, 1),
        ]
        for g_year, g_month, g_day in test_dates:
            r_year, r_month, r_day = gregorian_to_republican(
                g_year, g_month, g_day)
            back_g_year, back_g_month, back_g_day = republican_to_gregorian(
                r_year, r_month, r_day)
            self.assertEqual((back_g_year, back_g_month,
                             back_g_day), (g_year, g_month, g_day))

    def test_invalid_gregorian_date_before_start(self):
        """Test error for dates before the Republican calendar start."""
        with self.assertRaises(ValueError):
            gregorian_to_republican(1792, 9, 21)

    def test_invalid_republican_year(self):
        """Test error for invalid Republican year."""
        with self.assertRaises(ValueError):
            republican_to_gregorian(0, 1, 1)

    def test_invalid_republican_month(self):
        """Test error for invalid Republican month."""
        with self.assertRaises(ValueError):
            republican_to_gregorian(1, 0, 1)
        with self.assertRaises(ValueError):
            republican_to_gregorian(1, 14, 1)

    def test_invalid_republican_day_regular_month(self):
        """Test error for invalid day in regular months."""
        with self.assertRaises(ValueError):
            republican_to_gregorian(1, 1, 0)
        with self.assertRaises(ValueError):
            republican_to_gregorian(1, 1, 31)

    def test_invalid_republican_day_complementary_non_leap(self):
        """Test error for invalid day in complementary days for non-leap year."""
        with self.assertRaises(ValueError):
            republican_to_gregorian(2, 13, 6)  # Year 2 is non-leap, max 5

    def test_invalid_republican_day_complementary_leap(self):
        """Test error for invalid day in complementary days for leap year."""
        with self.assertRaises(ValueError):
            republican_to_gregorian(3, 13, 7)  # Year 3 is leap, max 6


if __name__ == '__main__':
    unittest.main()
