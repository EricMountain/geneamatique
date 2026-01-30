# Date Parsing and Display Implementation

## Summary of Changes

This implementation adds comprehensive date parsing, French Revolutionary calendar support, and enhanced display formatting to the genealogy database system.

## Features Implemented

### 1. Date Parsing and Storage
- **ISO8601 Format**: All dates are now stored in ISO8601 format (YYYY-MM-DD) for consistency and sorting
- **Multiple Date Formats Supported**:
  - "4 Jan 1952" (day month year with 3-letter abbreviation)
  - "04/01/1952" (DD/MM/YYYY)
  - "1952-01-04" (ISO8601)
  - French month names (janvier, février, etc.)

### 2. French Revolutionary Calendar
- **Automatic Conversion**: Revolutionary calendar dates are automatically converted to Gregorian
- **Format**: Supports "8 thermidor an II" or "8 thermidor II"
- **Dual Date Validation**: When both Gregorian and Revolutionary dates are present (e.g., "26 Jul 1794 (8 thermidor an II)"), the system:
  - Checks consistency between both dates
  - Issues a warning if dates don't match (with full context)
  - Stores only the Gregorian date
  - Drops the Revolutionary date after validation
- **Enhanced Warning System**:
  - Warnings include: source file name, person name, and original date strings
  - Warnings are issued synchronously during parsing
  - Warnings are accumulated and displayed as a summary at the end of the run
  - Warning format example:
    ```
    Date inconsistency in birth:
      File: 17bis Quentin Victoria.odt
      Person: VARANNE Pierre François
      Gregorian date: '20 janvier 1803' (ISO: 1803-01-20)
      Revolutionary date: '30 ventôse an 11' (ISO: 1803-03-21)
      Using Gregorian date.
    ```

### 3. Location Extraction
- **Pattern Recognition**: Searches for "à" or "au" after dates
- **Storage**: Each event type (birth, death, marriage) has its own location column
- **Example**: "15 Mar 1920 à Paris" → Date: 1920-03-15, Location: "Paris"

### 4. Comment Extraction
- **Two Scenarios**:
  1. **No Date Found**: Entire text after marker becomes a comment
  2. **Comment in Parentheses**: Text in parentheses after date/location is extracted as comment
- **Storage**: Separate comment column per event type
- **Examples**:
  - "date unknown" → stored as birth_comment
  - "15 Mar 1920 (premature birth)" → Date and comment both stored

### 5. Enhanced Database Schema
New columns added to `individuals` table:
- `date_of_birth` (ISO8601)
- `birth_location`
- `birth_comment`
- `date_of_death` (ISO8601)
- `death_location`
- `death_comment`
- `marriage_date` (ISO8601)
- `marriage_location`
- `marriage_comment`

### 6. Tree Visualizer Display
- **Bright Colors for Dates**:
  - Green for birth dates
  - Light gray for death dates
  - Magenta for marriage dates
- **Dark Colors for Comments**:
  - Dark green for birth comments (in braces)
  - Dark gray for death comments (in braces)
  - Dark magenta for marriage comments (in braces)
- **Format**: `°1920-03-15 à Paris {premature birth}`

## Files Modified

### Core Parser
- `import_tools/genealogy_parser.py`:
  - Added `parse_event_details()` function
  - Added `parse_date_to_iso()` function
  - Added `parse_french_revolutionary_date()` function
  - Updated `parse_individual_data()` to use new parsing
  - Updated `create_database()` with new schema
  - Updated `store_data()` to handle new columns

### Visualization
- `import_tools/tree_visualizer.py`:
  - Added dark color variants for comments
  - Updated `format_person()` to display dates, locations, and comments
  - Updated all database queries to fetch new columns
  - Updated `draw_ancestor_tree()` and `draw_descendant_tree()`

### Query Tool
- `import_tools/query_genealogy.py`:
  - Updated queries to fetch new columns
  - Updated `display_individual()` to show locations and comments

### Database Inspector
- `import_tools/inspect_database.py`:
  - Updated to display new columns in sample output

### Tests
- `import_tools/test_database_consistency.py`:
  - Updated schema tests for new columns
  - Added tests for French Revolutionary calendar parsing
  - Added tests for comment extraction
  - Added tests for location extraction
  - All 27 tests pass successfully

## Usage Examples

### Parsing Examples
```
Input: "° 8 thermidor an II"
Output: date_of_birth = "1794-07-26"

Input: "° 26 Jul 1794 (8 thermidor an II)"
Output: date_of_birth = "1794-07-26" (validated)

Input: "° 15 Mar 1920 à Paris (premature birth)"
Output: date_of_birth = "1920-03-15"
        birth_location = "Paris"
        birth_comment = "premature birth"

Input: "° date unknown"
Output: birth_comment = "date unknown"
```

### Display Example
```
MANOURY Bernard François René
°1973-02-15 à Londres {27}
+2007-10-15 à St Aubin lès Elbeuf {76}
X1973-07-28 à Caudebec lès Elbeuf {juillet 2002, Magagnosc}
```

## Testing

Run comprehensive test suite:
```bash
python -m unittest import_tools.test_database_consistency -v
```

All 27 tests pass, including:
- Schema validation
- Date parsing (Gregorian and Revolutionary)
- Location extraction
- Comment extraction
- Database consistency checks

## Demonstration

Run the demonstration script:
```bash
python tmp/demo_date_parsing.py
```

This demonstrates all parsing features with example inputs and outputs.

## Backward Compatibility

The implementation maintains backward compatibility:
- Import system handles both package and direct imports
- Old data format is still parsed correctly
- New columns accept NULL values for existing records
