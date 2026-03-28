#!/usr/bin/env python3
"""Search for individuals by location and list their tree instances and source files."""

import sqlite3
import sys
from typing import List, Tuple


def search_by_location(db_name: str = 'data/genealogy.db', location_search: str = '') -> None:
    """
    Search for all individuals having an event (birth, death, marriage) at a given location.
    Join on individual_id and list the files in individual_tree_instances that contain this individual.
    
    Args:
        db_name: Path to the genealogy database
        location_search: Location string to search for (case-insensitive partial match)
    """
    if not location_search:
        print("Error: no location provided")
        print("Usage: python search_individuals_by_location.py <location_string>")
        sys.exit(1)
    
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    # Build a query that finds individuals with events at the given location
    # and joins with individual_tree_instances to get source files
    query = """
    SELECT 
        i.id,
        i.canonical_name,
        'birth' as event_type,
        i.date_of_birth as event_date,
        i.birth_location as location,
        i.birth_comment as comment,
        iti.family_tree,
        iti.old_id,
        iti.source_file,
        iti.name_variant
    FROM individuals i
    LEFT JOIN individual_tree_instances iti ON i.id = iti.individual_id
    WHERE i.birth_location LIKE ?
    
    UNION ALL
    
    SELECT 
        i.id,
        i.canonical_name,
        'death' as event_type,
        i.date_of_death as event_date,
        i.death_location as location,
        i.death_comment as comment,
        iti.family_tree,
        iti.old_id,
        iti.source_file,
        iti.name_variant
    FROM individuals i
    LEFT JOIN individual_tree_instances iti ON i.id = iti.individual_id
    WHERE i.death_location LIKE ?
    
    UNION ALL
    
    SELECT 
        i.id,
        i.canonical_name,
        'marriage' as event_type,
        i.marriage_date as event_date,
        i.marriage_location as location,
        i.marriage_comment as comment,
        iti.family_tree,
        iti.old_id,
        iti.source_file,
        iti.name_variant
    FROM individuals i
    LEFT JOIN individual_tree_instances iti ON i.id = iti.individual_id
    WHERE i.marriage_location LIKE ?
    
    ORDER BY i.id, event_type, family_tree
    """
    
    # Prepare search pattern for LIKE clause (with wildcards)
    search_pattern = f"%{location_search}%"
    
    try:
        cursor.execute(query, (search_pattern, search_pattern, search_pattern))
        rows = cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        conn.close()
        sys.exit(1)
    
    if not rows:
        print(f"No individuals found with events at location: '{location_search}'")
        conn.close()
        return
    
    # Display results grouped by individual and event type
    print(f"\n{'='*100}")
    print(f"Search Results: Individuals with events at location '{location_search}'")
    print(f"{'='*100}\n")
    
    current_individual_id = None
    current_event_type = None
    event_count = 0
    
    for row in rows:
        individual_id, name, event_type, event_date, location, comment, family_tree, old_id, source_file, name_variant = row
        
        # Print individual header
        if individual_id != current_individual_id:
            if current_individual_id is not None:
                print()  # Blank line between individuals
            current_individual_id = individual_id
            current_event_type = None
            print(f"Individual ID: {individual_id}")
            print(f"  Name: {name}")
            event_count = 0
        
        # Print event type header
        if event_type != current_event_type:
            current_event_type = event_type
            print(f"\n  === {event_type.upper()} EVENT ===")
        
        # Print event details
        event_info = f"    Date: {event_date or 'Unknown'}"
        if location:
            event_info += f" | Location: {location}"
        if comment:
            event_info += f" | {comment}"
        print(event_info)
        
        # Print tree instances for this event
        if family_tree:
            tree_info = f"      Tree: {family_tree} (old_id: {old_id})"
            if name_variant:
                tree_info += f" | Name variant: {name_variant}"
            if source_file:
                tree_info += f" | Source: {source_file}"
            print(tree_info)
            event_count += 1
        else:
            # No tree instances (orphaned individual)
            print(f"      (No tree instances)")
    
    # Print summary statistics
    print(f"\n{'='*100}")
    cursor.execute("""
        SELECT COUNT(DISTINCT i.id) as total_individuals
        FROM individuals i
        WHERE i.birth_location LIKE ?
           OR i.death_location LIKE ?
           OR i.marriage_location LIKE ?
    """, (search_pattern, search_pattern, search_pattern))
    
    total_individuals = cursor.fetchone()[0]
    total_instances = len(rows)
    
    print(f"Total unique individuals: {total_individuals}")
    print(f"Total tree instances: {total_instances}")
    print(f"{'='*100}\n")
    
    conn.close()


def report_locations_with_null_coords(
    db_name: str = 'data/genealogy.db', 
    cache_db_name: str = 'data/geocode_cache.db'
) -> None:
    """
    Find all locations in geocode_cache that have NULL coordinates,
    then report all individuals, events, and files for those locations.
    
    Args:
        db_name: Path to the genealogy database
        cache_db_name: Path to the geocode cache database
    """
    # Connect to both databases
    try:
        conn_genealogy = sqlite3.connect(db_name)
        conn_cache = sqlite3.connect(cache_db_name)
    except sqlite3.Error as e:
        print(f"Database connection error: {e}")
        sys.exit(1)
    
    cursor_cache = conn_cache.cursor()
    
    # Find all locations with NULL coordinates
    try:
        cursor_cache.execute("""
            SELECT location_text 
            FROM location_coordinates 
            WHERE latitude IS NULL OR longitude IS NULL
            ORDER BY location_text
        """)
        null_coord_locations = [row[0] for row in cursor_cache.fetchall()]
    except sqlite3.Error as e:
        print(f"Cache database query error: {e}")
        conn_genealogy.close()
        conn_cache.close()
        sys.exit(1)
    
    if not null_coord_locations:
        print("No locations with NULL coordinates found in geocode_cache.db")
        conn_genealogy.close()
        conn_cache.close()
        return
    
    # Summary header
    print(f"\n{'='*100}")
    print(f"LOCATIONS WITH NULL COORDINATES IN GEOCODE_CACHE")
    print(f"Total locations: {len(null_coord_locations)}")
    print(f"{'='*100}\n")
    
    cursor_genealogy = conn_genealogy.cursor()
    total_instances_all = 0
    total_individuals_all = set()
    locations_with_individuals = 0
    
    # For each location with null coordinates, find individuals
    for location in null_coord_locations:
        # Build a query that finds individuals with events at the given location
        query = """
        SELECT 
            i.id,
            i.canonical_name,
            'birth' as event_type,
            i.date_of_birth as event_date,
            i.birth_location as location,
            i.birth_comment as comment,
            iti.family_tree,
            iti.old_id,
            iti.source_file,
            iti.name_variant
        FROM individuals i
        LEFT JOIN individual_tree_instances iti ON i.id = iti.individual_id
        WHERE i.birth_location = ?
        
        UNION ALL
        
        SELECT 
            i.id,
            i.canonical_name,
            'death' as event_type,
            i.date_of_death as event_date,
            i.death_location as location,
            i.death_comment as comment,
            iti.family_tree,
            iti.old_id,
            iti.source_file,
            iti.name_variant
        FROM individuals i
        LEFT JOIN individual_tree_instances iti ON i.id = iti.individual_id
        WHERE i.death_location = ?
        
        UNION ALL
        
        SELECT 
            i.id,
            i.canonical_name,
            'marriage' as event_type,
            i.marriage_date as event_date,
            i.marriage_location as location,
            i.marriage_comment as comment,
            iti.family_tree,
            iti.old_id,
            iti.source_file,
            iti.name_variant
        FROM individuals i
        LEFT JOIN individual_tree_instances iti ON i.id = iti.individual_id
        WHERE i.marriage_location = ?
        
        ORDER BY i.id, event_type, family_tree
        """
        
        try:
            cursor_genealogy.execute(query, (location, location, location))
            rows = cursor_genealogy.fetchall()
        except sqlite3.Error as e:
            print(f"Genealogy database query error: {e}")
            continue
        
        if not rows:
            continue
        
        locations_with_individuals += 1
        
        # Display location header
        print(f"\nLocation: '{location}'")
        print("-" * 100)
        
        current_individual_id = None
        current_event_type = None
        location_individuals = set()
        location_instances = 0
        
        for row in rows:
            individual_id, name, event_type, event_date, loc, comment, family_tree, old_id, source_file, name_variant = row
            
            location_individuals.add(individual_id)
            location_instances += 1
            total_individuals_all.add(individual_id)
            
            # Print individual header
            if individual_id != current_individual_id:
                if current_individual_id is not None:
                    print()  # Blank line between individuals
                current_individual_id = individual_id
                current_event_type = None
                print(f"  Individual ID: {individual_id}")
                print(f"    Name: {name}")
            
            # Print event type header
            if event_type != current_event_type:
                current_event_type = event_type
                print(f"\n    === {event_type.upper()} ===")
            
            # Print event details
            event_info = f"      Date: {event_date or 'Unknown'}"
            if comment:
                event_info += f" | {comment}"
            print(event_info)
            
            # Print tree instances for this event
            if family_tree:
                tree_info = f"        Tree: {family_tree} (old_id: {old_id})"
                if name_variant:
                    tree_info += f" | {name_variant}"
                if source_file:
                    tree_info += f"\n          File: {source_file}"
                print(tree_info)
            else:
                print(f"        (No tree instances)")
        
        print()  # Blank line after location
        print(f"  Location summary: {len(location_individuals)} individuals, {location_instances} tree instances")
        total_instances_all += location_instances
    
    # Print final summary
    print(f"\n{'='*100}")
    print(f"SUMMARY")
    print(f"{'='*100}")
    print(f"Total locations with NULL coordinates: {len(null_coord_locations)}")
    print(f"Locations with individuals: {locations_with_individuals}")
    print(f"Total unique individuals: {len(total_individuals_all)}")
    print(f"Total tree instances: {total_instances_all}")
    print(f"{'='*100}\n")
    
    conn_genealogy.close()
    conn_cache.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Search for individuals by location")
        print("")
        print("Usage:")
        print("  python search_individuals_by_location.py <location_string>")
        print("  python search_individuals_by_location.py --null-coords")
        print("")
        print("Examples:")
        print("  python search_individuals_by_location.py 'Paris'")
        print("  python search_individuals_by_location.py 'New York'")
        print("  python search_individuals_by_location.py --null-coords")
        sys.exit(1)
    
    arg = sys.argv[1]
    
    if arg == '--null-coords':
        report_locations_with_null_coords()
    else:
        search_by_location(location_search=arg)
