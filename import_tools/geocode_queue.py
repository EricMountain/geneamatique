#!/usr/bin/env python3
"""Thread-based queue system for asynchronous geocoding with rate limiting."""

import threading
import queue
import time
from typing import Callable, Optional, Tuple

# Handle both package and direct import
try:
    from .geocode_cache import GeocodeCache
    from .geocoder import NominatimGeocoder
except ImportError:
    from geocode_cache import GeocodeCache
    from geocoder import NominatimGeocoder


class GeocodeRequest:
    """Represents a single geocoding request."""
    
    def __init__(self, location: str, callback: Optional[Callable] = None):
        """Initialize a geocode request.
        
        Args:
            location: Location string to geocode
            callback: Function to call with results (lat, lon, country) or None
        """
        self.location = location
        self.callback = callback


class GeocodeQueue:
    """Thread-safe queue for asynchronous geocoding with rate limiting."""

    def __init__(self, cache: GeocodeCache, geocoder: NominatimGeocoder):
        """Initialize the geocoding queue.
        
        Args:
            cache: GeocodeCache instance for caching results
            geocoder: NominatimGeocoder instance for API calls
        """
        self.cache = cache
        self.geocoder = geocoder
        self.request_queue = queue.Queue()
        self.worker_thread = None
        self.stop_event = threading.Event()
        self.active = False
        self.stats = {
            'queued': 0,
            'cache_hits': 0,
            'api_calls': 0,
            'successes': 0,
            'failures': 0
        }
        self.stats_lock = threading.Lock()

    def start(self):
        """Start the worker thread."""
        if self.active:
            return
        
        self.active = True
        self.stop_event.clear()
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()

    def stop(self, timeout: Optional[float] = None):
        """Stop the worker thread and wait for it to finish.
        
        Args:
            timeout: Maximum time to wait for thread to finish (None = wait forever)
        """
        if not self.active:
            return
        
        self.stop_event.set()
        if self.worker_thread:
            self.worker_thread.join(timeout=timeout)
        self.active = False

    def enqueue(self, location: str, callback: Optional[Callable] = None) -> bool:
        """Add a location to the geocoding queue.
        
        Args:
            location: Location string to geocode
            callback: Function to call with results (lat, lon, country) or None
            
        Returns:
            True if added to queue, False if already in cache
        """
        if not location or not location.strip():
            return False

        # Check cache first
        cached_result = self.cache.get(location)
        if cached_result is not None:
            with self.stats_lock:
                self.stats['cache_hits'] += 1
            
            # Call callback immediately with cached result
            if callback:
                callback(location, *cached_result)
            return False

        # Add to queue
        self.request_queue.put(GeocodeRequest(location, callback))
        with self.stats_lock:
            self.stats['queued'] += 1
        return True

    def _worker(self):
        """Worker thread that processes geocoding requests at 1 req/sec max."""
        while not self.stop_event.is_set():
            try:
                # Get request with timeout so we can check stop_event periodically
                try:
                    request = self.request_queue.get(timeout=0.5)
                except queue.Empty:
                    continue

                # Check cache again (in case it was added while queued)
                cached_result = self.cache.get(request.location)
                if cached_result is not None:
                    with self.stats_lock:
                        self.stats['cache_hits'] += 1
                    
                    if request.callback:
                        request.callback(request.location, *cached_result)
                    continue

                # Geocode via API (rate limiting is enforced inside geocoder)
                with self.stats_lock:
                    self.stats['api_calls'] += 1
                
                result = self.geocoder.geocode(request.location)
                
                if result:
                    lat, lon, country = result
                    self.cache.put(request.location, lat, lon, country)
                    
                    with self.stats_lock:
                        self.stats['successes'] += 1
                    
                    if request.callback:
                        request.callback(request.location, lat, lon, country)
                else:
                    # Store failure in cache to avoid retrying
                    self.cache.put(request.location, None, None, None)
                    
                    with self.stats_lock:
                        self.stats['failures'] += 1
                    
                    if request.callback:
                        request.callback(request.location, None, None, None)

            except Exception as e:
                print(f"   ⚠ Error in geocoding worker: {e}")

    def flush(self, show_progress: bool = True):
        """Wait for all queued requests to complete.
        
        Args:
            show_progress: If True, print progress updates
        """
        if not self.active:
            return

        if show_progress:
            print("\n   Waiting for geocoding to complete...")

        while not self.request_queue.empty():
            remaining = self.request_queue.qsize()
            if show_progress and remaining > 0:
                print(f"   {remaining} locations remaining in queue...", end='\r')
            time.sleep(0.5)

        if show_progress:
            print("   ✓ All geocoding requests completed" + " " * 30)

    def get_stats(self) -> dict:
        """Get current statistics about the queue.
        
        Returns:
            Dictionary with statistics
        """
        with self.stats_lock:
            return self.stats.copy()
