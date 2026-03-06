# Geocoding System Documentation

## Overview

The geocoding system automatically converts location names (like "Paris" or "Londres") into GPS coordinates (latitude/longitude) that can be used for map visualization. It consists of:

1. **Persistent cache** (`data/geocode_cache.db`) - Stores location-to-coordinates mappings to avoid redundant API calls
2. **Nominatim geocoder** - Queries OpenStreetMap's free geocoding API with France/UK bias
3. **Asynchronous queue** - Processes geocoding requests at max 1 req/sec (API rate limit) in background thread
4. **Database integration** - Stores coordinates in the `individuals` table alongside location names

## Architecture

### Database Schema

**Cache Database** (`data/geocode_cache.db`):
```sql
CREATE TABLE location_coordinates (
    location_text TEXT PRIMARY KEY,
    latitude REAL,
    longitude REAL,
    country TEXT,
    geocode_source TEXT,
    geocoded_at TEXT,
    confidence_score REAL
)
```

**Genealogy Database** (`data/genealogy.db`):
```sql
-- Extended individuals table with coordinate columns
CREATE TABLE individuals (
    ...,
    birth_location TEXT,
    birth_lat REAL,
    birth_lon REAL,
    death_location TEXT,
    death_lat REAL,
    death_lon REAL,
    marriage_location TEXT,
    marriage_lat REAL,
    marriage_lon REAL,
    ...
)
```

### Components

#### 1. GeocodeCache (`import_tools/geocode_cache.py`)
- Manages persistent cache database
- Methods:
  - `get(location)` - Retrieve cached coordinates
  - `put(location, lat, lon, country)` - Store coordinates
  - `get_stats()` - Cache statistics

#### 2. NominatimGeocoder (`import_tools/geocoder.py`)
#### 2. NominatimGeocoder (`import_tools/geocoder.py`)
- Queries Nominatim API with rate limiting
- Prefers France/UK results for ambiguous locations
- Optionally strips department codes like "(75)" from queries
- Extracts country from `display_name` field (last comma-separated element)
- Methods:
  - `geocode(location)` - Returns `(lat, lon, country)` or None

#### 3. GeocodeQueue (`import_tools/geocode_queue.py`)
- Thread-safe async queue with 1 req/sec worker
- Methods:
  - `start()` - Start worker thread
  - `enqueue(location, callback)` - Add location to queue
  - `flush(show_progress=True)` - Wait for completion
  - `stop()` - Stop worker thread
  - `get_stats()` - Queue statistics

## Usage

### During Import (Automatic)

Geocoding happens automatically when running `run_parser.py`:

```bash
python import_tools/run_parser.py
```

The parser will:
1. Initialize the geocoding queue on startup
2. Check the cache for each location encountered
3. Enqueue cache misses for background geocoding
4. Update the database as coordinates become available
5. Block before completion to ensure all geocoding finishes
6. Print statistics about cache hits/misses and API calls

### Backfill Existing Data

To geocode locations in an existing database without re-parsing:

```bash
python import_tools/geocode_backfill.py
```

This script:
1. Collects all unique locations from `data/genealogy.db`
2. Checks which are already cached
3. Geocodes missing locations via Nominatim
4. Updates coordinates in the database
5. Shows progress and statistics

### Manual Testing

Test the geocoding system:

```bash
python tmp/test_geocoding.py
```

This creates a test cache database and verifies all components work.

## Configuration

### API Rate Limiting

Nominatim enforces **1 request per second**. The geocoder automatically handles this with `time.sleep()` between requests. For large imports, expect ~60 locations per minute.

### Country Bias

The geocoder uses `countrycodes=fr,gb` to prefer French and UK results for ambiguous location names. This can be modified in `geocoder.py`:

```python
params = {
    'countrycodes': 'fr,gb',  # Comma-separated ISO country codes
    ...
}
```

### Department Codes

French locations often include department codes like "Paris (75)". The geocoder:
1. First tries geocoding with the full string
2. If that fails, strips the department code and retries
3. Stores results under the original location string (with department code)

## Cache Persistence

The cache database (`data/geocode_cache.db`) is **never deleted** during imports. This means:
- Locations are geocoded once and reused across all future imports
- The cache grows over time as new locations are encountered
- Failed geocoding attempts are also cached to avoid retrying
- No need to re-geocode locations when re-importing data

## Performance Considerations

### Import Time Impact

Geocoding adds minimal overhead to imports because:
- The queue processes requests asynchronously in a background thread
- Only cache misses trigger API calls
- Parsing continues while geocoding happens in parallel
- Only the final flush blocks (waiting for queue to empty)

Expected timing:
- **Cache hit**: ~1ms (database lookup)
- **Cache miss**: 1+ seconds (API rate limit)
- **100 new locations**: ~100 seconds (blocking during flush)

### Optimization Tips

1. **Run backfill separately**: For large existing databases, run `geocode_backfill.py` once overnight rather than during parsing
2. **Share cache**: Copy `geocode_cache.db` between machines to avoid redundant API calls
3. **Pre-populate cache**: Manually add common locations to the cache database

## API Usage Policy

The system uses [Nominatim](https://nominatim.openstreetmap.org/), OpenStreetMap's free geocoding service. Please respect their [usage policy](https://operations.osmfoundation.org/policies/nominatim/):

- **Rate limit**: Max 1 request per second (enforced by code)
- **User agent**: Identifies requests as `genealogy-parser/1.0`
- **No bulk downloading**: Our usage is compliant (small genealogy datasets)
- **No commercial use**: For personal genealogy projects only

## Troubleshooting

### No coordinates after import

Check geocoding statistics in import output:
```
Geocoding Statistics:
  Cache hits: 45
  API calls: 12
  Successful: 10
  Failed: 2
```

If many failures, locations may be ambiguous or misspelled.

### Slow imports

- **Expected**: First import with many new locations will be slow (~1 location/sec)
- **Solution**: Subsequent imports reuse cache and are fast
- **Alternative**: Run `geocode_backfill.py` separately from import

### Failed geocoding

Common reasons:
- **Invalid location**: "???" or garbled text
- **Historical names**: Place names that no longer exist
- **Ambiguous**: Multiple matches with low confidence
- **Misspelled**: Typos in original genealogy documents

Failed geocoding attempts are cached to avoid retrying. To retry:
```bash
sqlite3 data/geocode_cache.db "DELETE FROM location_coordinates WHERE latitude IS NULL"
```

### Check cache contents

```bash
sqlite3 data/geocode_cache.db "SELECT * FROM location_coordinates LIMIT 10"
```

### Clear entire cache

```bash
rm data/geocode_cache.db
```

## Future Enhancements

Possible improvements:
1. **Manual corrections**: UI to override incorrect geocoding results
2. **Multiple geocoders**: Fall back to Google Maps API for failed Nominatim queries
3. **Historical gazetteers**: Special handling for historical place names
4. **Confidence scores**: Store and display geocoding confidence
5. **Map visualization**: Frontend to display individuals on a map
