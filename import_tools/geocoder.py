#!/usr/bin/env python3
"""Module to geocode locations using the Nominatim API."""

import urllib.request
import urllib.parse
import json
import time
import re
from typing import Optional, Tuple


class NominatimGeocoder:
    """Geocoder using the Nominatim (OpenStreetMap) API."""

    def __init__(self, user_agent='genealogy-parser/1.0'):
        """Initialize the geocoder.
        
        Args:
            user_agent: User agent string for API requests (required by Nominatim)
        """
        self.user_agent = user_agent
        self.base_url = 'https://nominatim.openstreetmap.org/search'
        self.last_request_time = 0

    def _enforce_rate_limit(self):
        """Ensure we don't exceed 1 request per second (Nominatim's limit)."""
        elapsed = time.time() - self.last_request_time
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        self.last_request_time = time.time()

    def _strip_department_code(self, location: str) -> Tuple[str, Optional[str]]:
        """Strip French department codes like (75) or (92) from location.
        
        Args:
            location: Original location string
            
        Returns:
            Tuple of (cleaned_location, department_code)
        """
        # Match pattern like "(75)" or "(92)" at the end or in the middle
        match = re.search(r'\((\d{2,3})\)', location)
        if match:
            dept_code = match.group(1)
            cleaned = location.replace(match.group(0), '').strip()
            return cleaned, dept_code
        return location, None

    def _prefer_french_or_uk_result(self, results: list) -> Optional[dict]:
        """Select the best result, preferring France or UK locations.
        
        Args:
            results: List of geocoding results from Nominatim
            
        Returns:
            Best result dict, or None if no suitable result found
        """
        if not results:
            return None

        # First pass: look for France or UK
        for result in results:
            country_code = result.get('address', {}).get('country_code', '').lower()
            if country_code in ['fr', 'gb']:
                return result

        # Second pass: if no France/UK found, prefer any European result
        for result in results:
            country_code = result.get('address', {}).get('country_code', '').lower()
            # Common European country codes
            if country_code in ['de', 'es', 'it', 'be', 'ch', 'nl', 'pt', 'at']:
                return result

        # Fall back to first result
        return results[0] if results else None

    def geocode(self, location: str, try_without_department: bool = True) -> Optional[Tuple[float, float, str]]:
        """Geocode a location string to coordinates.
        
        Args:
            location: Location string to geocode
            try_without_department: If True, try geocoding with department code stripped
            
        Returns:
            Tuple of (latitude, longitude, country) if successful, None otherwise
        """
        if not location or not location.strip():
            return None

        location = location.strip()
        
        # Try with original location first
        result = self._query_nominatim(location)
        
        # If no result and department code present, try without it
        if not result and try_without_department:
            cleaned_location, dept_code = self._strip_department_code(location)
            if dept_code:
                result = self._query_nominatim(cleaned_location)

        return result

    def _query_nominatim(self, location: str) -> Optional[Tuple[float, float, str]]:
        """Query Nominatim API for a specific location string.
        
        Args:
            location: Location string to query
            
        Returns:
            Tuple of (latitude, longitude, country) if successful, None otherwise
        """
        self._enforce_rate_limit()

        # Build query parameters with France/UK bias
        params = {
            'q': location,
            'format': 'json',
            'limit': 5,  # Get multiple results to choose from
            'countrycodes': 'fr,gb',  # Prefer France and UK
            'accept-language': 'fr,en',  # Prefer French and English names
        }

        url = f"{self.base_url}?{urllib.parse.urlencode(params)}"
        
        try:
            request = urllib.request.Request(url, headers={
                'User-Agent': self.user_agent
            })
            
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                
                # Select best result preferring France/UK
                best_result = self._prefer_french_or_uk_result(data)
                
                if best_result:
                    lat = float(best_result['lat'])
                    lon = float(best_result['lon'])
                    
                    # Extract country from display_name (last element after splitting by comma)
                    # e.g., "Paris, Île-de-France, France" -> "France"
                    display_name = best_result.get('display_name', '')
                    if display_name:
                        country = display_name.split(',')[-1].strip()
                    else:
                        # Fallback to address.country if display_name is not available
                        country = best_result.get('address', {}).get('country', 'Unknown')
                    
                    return (lat, lon, country)
                    
        except Exception as e:
            print(f"   ⚠ Geocoding error for '{location}': {e}")
            
        return None

    def batch_geocode(self, locations: list) -> dict:
        """Geocode multiple locations in sequence.
        
        Args:
            locations: List of location strings
            
        Returns:
            Dictionary mapping location -> (lat, lon, country) or None
        """
        results = {}
        total = len(locations)
        
        for i, location in enumerate(locations, 1):
            print(f"   Geocoding {i}/{total}: {location}")
            result = self.geocode(location)
            results[location] = result
            
        return results
