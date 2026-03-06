#!/usr/bin/env python3
"""Standalone script to geocode locations in an existing genealogy database.

This script can be run independently to backfill coordinates for locations
that were imported before geocoding was implemented, or to update coordinates
for all locations in the database.
"""

import sqlite3
import sys
import os
from geocode_cache import GeocodeCache
from geocoder import NominatimGeocoder
from geocode_queue import GeocodeQueue


def collect_locations(db_name='data/genealogy.db'):
    """Collect all unique locations from the database.
    
    Args:
        db_name: Path to the genealogy database
        
    Returns:
        Set of unique location strings
    """
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    locations = set()

    # Collect birth locations
    cursor.execute('SELECT DISTINCT birth_location FROM individuals WHERE birth_location IS NOT NULL')
    for row in cursor.fetchall():
        if row[0] and row[0].strip():
            locations.add(row[0].strip())

    # Collect death locations
    cursor.execute('SELECT DISTINCT death_location FROM individuals WHERE death_location IS NOT NULL')
    for row in cursor.fetchall():
        if row[0] and row[0].strip():
            locations.add(row[0].strip())

    # Collect marriage locations
    cursor.execute('SELECT DISTINCT marriage_location FROM individuals WHERE marriage_location IS NOT NULL')
    for row in cursor.fetchall():
        if row[0] and row[0].strip():
            locations.add(row[0].strip())

    conn.close()

    return locations


def main():
    """Main entry point for the geocode backfill script."""
    db_name = 'data/genealogy.db'

    if not os.path.exists(db_name):
        print(f"Error: Database not found at {db_name}")
        print("Please run the parser first to create the database.")
        sys.exit(1)

    print("="*80)
    print("GEOCODE BACKFILL")
    print("="*80)

    # Collect all locations
    print("\n1. Collecting locations from database...")
    locations = collect_locations(db_name)
    print(f"   ✓ Found {len(locations)} unique locations")

    if not locations:
        print("   No locations to geocode.")
        return

    # Initialize geocoding system
    print("\n2. Initializing geocoding system...")
    geocode_cache = GeocodeCache()
    geocoder = NominatimGeocoder()
    geocode_queue = GeocodeQueue(geocode_cache, geocoder)
    geocode_queue.start()

    def update_coordinates_callback(location, lat, lon, country):
        """Callback to update coordinates in database when geocoding completes."""
        if lat is None or lon is None:
            print(f"   ✗ Failed to geocode: {location}")
            return
        
        print(f"   ✓ Geocoded: {location} → ({lat:.4f}, {lon:.4f}) [{country}]")
        
        # Update all individuals with this location
        try:
            conn = sqlite3.connect(db_name)
            cursor = conn.cursor()
            
            # Update birth locations
            cursor.execute('''
                UPDATE individuals 
                SET birth_lat = ?, birth_lon = ?
                WHERE birth_location = ?
            ''', (lat, lon, location))
            birth_count = cursor.rowcount
            
            # Update death locations
            cursor.execute('''
                UPDATE individuals 
                SET death_lat = ?, death_lon = ?
                WHERE death_location = ?
            ''', (lat, lon, location))
            death_count = cursor.rowcount
            
            # Update marriage locations
            cursor.execute('''
                UPDATE individuals 
                SET marriage_lat = ?, marriage_lon = ?
                WHERE marriage_location = ?
            ''', (lat, lon, location))
            marriage_count = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            total = birth_count + death_count + marriage_count
            if total > 0:
                print(f"      Updated {total} records (birth: {birth_count}, death: {death_count}, marriage: {marriage_count})")
        except Exception as e:
            print(f"   ⚠ Error updating coordinates for '{location}': {e}")

    # Enqueue all locations
    print("\n3. Enqueuing locations for geocoding...")
    for location in sorted(locations):
        geocode_queue.enqueue(location, update_coordinates_callback)
    
    geocode_stats = geocode_queue.get_stats()
    print(f"   ✓ Enqueued {geocode_stats['queued']} new locations")
    print(f"   ✓ Found {geocode_stats['cache_hits']} in cache")

    # Wait for completion
    print("\n4. Geocoding locations (this may take a while due to rate limiting)...")
    geocode_queue.flush(show_progress=True)
    geocode_queue.stop(timeout=10.0)

    # Print final statistics
    geocode_stats = geocode_queue.get_stats()
    cache_stats = geocode_cache.get_stats()
    
    print("\n" + "="*80)
    print("COMPLETE!")
    print("="*80)
    print("\nGeocoding Statistics:")
    print(f"  Cache hits: {geocode_stats['cache_hits']}")
    print(f"  API calls: {geocode_stats['api_calls']}")
    print(f"  Successful: {geocode_stats['successes']}")
    print(f"  Failed: {geocode_stats['failures']}")
    print(f"\nCache Statistics:")
    print(f"  Total entries: {cache_stats['total_entries']}")
    print(f"  Geocoded: {cache_stats['geocoded']}")
    print(f"  Failed: {cache_stats['failed']}")
    
    if cache_stats['by_country']:
        print(f"\nLocations by country:")
        for country, count in sorted(cache_stats['by_country'].items(), key=lambda x: x[1], reverse=True):
            print(f"    {country}: {count}")


if __name__ == '__main__':
    main()
