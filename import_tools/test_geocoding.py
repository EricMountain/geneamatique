#!/usr/bin/env python3
"""Unit tests for the geocoding system."""

import unittest
import os
import tempfile
from geocode_cache import GeocodeCache
from geocoder import NominatimGeocoder


class TestGeocodeCache(unittest.TestCase):
    """Test cases for GeocodeCache."""

    def setUp(self):
        """Create a temporary cache database for testing."""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        self.cache = GeocodeCache(self.temp_db.name)

    def tearDown(self):
        """Clean up temporary database."""
        try:
            os.unlink(self.temp_db.name)
        except:
            pass

    def test_cache_initialization(self):
        """Test that cache database is created properly."""
        self.assertTrue(os.path.exists(self.temp_db.name))
        stats = self.cache.get_stats()
        self.assertEqual(stats['total_entries'], 0)

    def test_cache_put_and_get(self):
        """Test storing and retrieving coordinates."""
        self.cache.put("Paris", 48.8566, 2.3522, "France")
        result = self.cache.get("Paris")
        self.assertIsNotNone(result)
        lat, lon, country = result
        self.assertAlmostEqual(lat, 48.8566, places=4)
        self.assertAlmostEqual(lon, 2.3522, places=4)
        self.assertEqual(country, "France")

    def test_cache_miss(self):
        """Test that non-existent location returns None."""
        result = self.cache.get("NonexistentPlace12345")
        self.assertIsNone(result)

    def test_cache_update(self):
        """Test that updating an existing entry works."""
        self.cache.put("TestCity", 10.0, 20.0, "TestCountry")
        self.cache.put("TestCity", 11.0, 21.0, "UpdatedCountry")
        result = self.cache.get("TestCity")
        lat, lon, country = result
        self.assertAlmostEqual(lat, 11.0)
        self.assertAlmostEqual(lon, 21.0)
        self.assertEqual(country, "UpdatedCountry")

    def test_cache_failed_geocoding(self):
        """Test storing failed geocoding attempts."""
        self.cache.put("InvalidLocation", None, None, None)
        result = self.cache.get("InvalidLocation")
        self.assertIsNone(result)  # Failed geocoding returns None
        
        # But it should be in the database
        stats = self.cache.get_stats()
        self.assertEqual(stats['total_entries'], 1)
        self.assertEqual(stats['failed'], 1)

    def test_cache_stats(self):
        """Test cache statistics."""
        self.cache.put("Place1", 1.0, 2.0, "Country1")
        self.cache.put("Place2", 3.0, 4.0, "Country1")
        self.cache.put("Place3", 5.0, 6.0, "Country2")
        self.cache.put("Place4", None, None, None)  # Failed
        
        stats = self.cache.get_stats()
        self.assertEqual(stats['total_entries'], 4)
        self.assertEqual(stats['geocoded'], 3)
        self.assertEqual(stats['failed'], 1)
        self.assertEqual(stats['by_country']['Country1'], 2)
        self.assertEqual(stats['by_country']['Country2'], 1)


class TestNominatimGeocoder(unittest.TestCase):
    """Test cases for NominatimGeocoder."""

    def setUp(self):
        """Initialize geocoder."""
        self.geocoder = NominatimGeocoder()

    def test_strip_department_code(self):
        """Test stripping French department codes."""
        cleaned, dept = self.geocoder._strip_department_code("Paris (75)")
        self.assertEqual(cleaned, "Paris")
        self.assertEqual(dept, "75")

        cleaned, dept = self.geocoder._strip_department_code("London")
        self.assertEqual(cleaned, "London")
        self.assertIsNone(dept)

    def test_prefer_french_result(self):
        """Test preferring French results from multiple matches."""
        results = [
            {'address': {'country_code': 'us'}},
            {'address': {'country_code': 'fr'}},
            {'address': {'country_code': 'de'}},
        ]
        best = self.geocoder._prefer_french_or_uk_result(results)
        self.assertEqual(best['address']['country_code'], 'fr')

    def test_prefer_uk_result(self):
        """Test preferring UK results from multiple matches."""
        results = [
            {'address': {'country_code': 'us'}},
            {'address': {'country_code': 'gb'}},
            {'address': {'country_code': 'de'}},
        ]
        best = self.geocoder._prefer_french_or_uk_result(results)
        self.assertEqual(best['address']['country_code'], 'gb')

    def test_empty_results(self):
        """Test handling empty results."""
        best = self.geocoder._prefer_french_or_uk_result([])
        self.assertIsNone(best)

    def test_country_extraction_from_display_name(self):
        """Test extracting country from display_name field."""
        # Mock a Nominatim result with display_name
        import unittest.mock as mock
        import json
        import io
        
        # Test case 1: Paris, France
        mock_response_data = [{
            'lat': '48.8566',
            'lon': '2.3522',
            'display_name': 'Paris, Île-de-France, France',
            'address': {'country': 'France', 'country_code': 'fr'}
        }]
        
        mock_response = io.BytesIO(json.dumps(mock_response_data).encode('utf-8'))
        mock_response.read = lambda: json.dumps(mock_response_data).encode('utf-8')
        
        with mock.patch.object(self.geocoder, '_enforce_rate_limit'):
            with mock.patch('urllib.request.urlopen', return_value=mock_response):
                result = self.geocoder._query_nominatim('Paris')
                self.assertIsNotNone(result)
                lat, lon, country = result
                self.assertEqual(country, 'France')
        
        # Test case 2: London with multiple commas
        mock_response_data2 = [{
            'lat': '51.5074',
            'lon': '-0.1278',
            'display_name': 'London, Greater London, England, SW1A 2DX, United Kingdom',
            'address': {'country': 'United Kingdom', 'country_code': 'gb'}
        }]
        
        mock_response2 = io.BytesIO(json.dumps(mock_response_data2).encode('utf-8'))
        mock_response2.read = lambda: json.dumps(mock_response_data2).encode('utf-8')
        
        with mock.patch.object(self.geocoder, '_enforce_rate_limit'):
            with mock.patch('urllib.request.urlopen', return_value=mock_response2):
                result = self.geocoder._query_nominatim('London')
                self.assertIsNotNone(result)
                lat, lon, country = result
                self.assertEqual(country, 'United Kingdom')

    # Note: Actual API tests are skipped to avoid hitting rate limits during testing
    # Use tmp/test_geocoding.py for end-to-end API testing


if __name__ == '__main__':
    unittest.main()
