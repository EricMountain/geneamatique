#!/usr/bin/env python3
"""Module to manage the persistent geocode cache database."""

import sqlite3
import os
from datetime import datetime
from typing import Optional, Tuple


class GeocodeCache:
    """Manages a persistent cache of location-to-coordinates mappings."""

    def __init__(self, cache_db_path='data/geocode_cache.db'):
        """Initialize the geocode cache.
        
        Args:
            cache_db_path: Path to the cache database file
        """
        self.cache_db_path = cache_db_path
        self._ensure_database()

    def _ensure_database(self):
        """Create the cache database and schema if it doesn't exist."""
        # Create directory if needed
        os.makedirs(os.path.dirname(self.cache_db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.cache_db_path)
        cursor = conn.cursor()

        # Create table if it doesn't exist (don't drop - we want to preserve cache)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS location_coordinates (
            location_text TEXT PRIMARY KEY,
            latitude REAL,
            longitude REAL,
            country TEXT,
            geocode_source TEXT,
            geocoded_at TEXT,
            confidence_score REAL
        )
        ''')

        # Create index for faster country-based queries
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_location_country 
        ON location_coordinates(country)
        ''')

        conn.commit()
        conn.close()

    def get(self, location_text: str) -> Optional[Tuple[float, float, str]]:
        """Look up coordinates for a location in the cache.
        
        Args:
            location_text: The location string to look up
            
        Returns:
            Tuple of (latitude, longitude, country) if found, None otherwise
        """
        if not location_text or not location_text.strip():
            return None

        conn = sqlite3.connect(self.cache_db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT latitude, longitude, country 
            FROM location_coordinates 
            WHERE location_text = ?
        ''', (location_text.strip(),))

        result = cursor.fetchone()
        conn.close()

        if result and result[0] is not None and result[1] is not None:
            return (result[0], result[1], result[2])
        return None

    def put(self, location_text: str, latitude: Optional[float], 
            longitude: Optional[float], country: Optional[str] = None,
            geocode_source: str = 'nominatim', confidence_score: float = 1.0):
        """Store coordinates for a location in the cache.
        
        Args:
            location_text: The location string
            latitude: Latitude coordinate (or None if geocoding failed)
            longitude: Longitude coordinate (or None if geocoding failed)
            country: Country code or name
            geocode_source: Source of the geocoding (e.g., 'nominatim')
            confidence_score: Confidence in the result (0.0 to 1.0)
        """
        if not location_text or not location_text.strip():
            return

        conn = sqlite3.connect(self.cache_db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO location_coordinates 
            (location_text, latitude, longitude, country, geocode_source, 
             geocoded_at, confidence_score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (location_text.strip(), latitude, longitude, country, 
              geocode_source, datetime.utcnow().isoformat(), confidence_score))

        conn.commit()
        conn.close()

    def get_stats(self) -> dict:
        """Get statistics about the cache.
        
        Returns:
            Dictionary with cache statistics
        """
        conn = sqlite3.connect(self.cache_db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM location_coordinates')
        total = cursor.fetchone()[0]

        cursor.execute('''
            SELECT COUNT(*) FROM location_coordinates 
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        ''')
        geocoded = cursor.fetchone()[0]

        cursor.execute('''
            SELECT country, COUNT(*) 
            FROM location_coordinates 
            WHERE country IS NOT NULL
            GROUP BY country
            ORDER BY COUNT(*) DESC
        ''')
        by_country = cursor.fetchall()

        conn.close()

        return {
            'total_entries': total,
            'geocoded': geocoded,
            'failed': total - geocoded,
            'by_country': dict(by_country)
        }
