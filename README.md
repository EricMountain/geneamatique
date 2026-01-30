# Genealogy Parser

A Python application for parsing OpenOffice Writer (.odt) genealogical tables and storing the data in an SQLite database.

## Overview

This project extracts genealogical information from ODT documents containing family trees structured in tables. Each cell contains details about one family member, including:

- Name with numeric ID
- Date of birth (prefixed with °)
- Date of death (prefixed with +)
- Profession (prefixed with PR)
- Marriage date (prefixed with X)

The parser intelligently handles:
- Duplicate individuals across multiple documents
- Parent-child relationship inference based on genealogical numbering system
- Name variations (same person, different spellings)
- Data consolidation from multiple sources

## Technical Stack

- **Language**: Python 3.14+
- **Document Parsing**: odfpy (for reading OpenOffice documents)
- **Database**: SQLite3 (built-in)
- **Testing**: unittest (built-in)

## Database Schema

### Tables

1. **individuals**
   - `id`: Auto-increment primary key
   - `old_id`: Original ID from source documents
   - `name`: Full name
   - `date_of_birth`: Birth date string
   - `date_of_death`: Death date string
   - `profession`: Occupation
   - `marriage_date`: Marriage date string
   - UNIQUE constraint on (old_id, name)

2. **individual_sources**
   - `id`: Auto-increment primary key
   - `individual_id`: Foreign key to individuals
   - `source_file`: Source document filename
   - Tracks which documents mention each individual

3. **relationships**
   - `id`: Auto-increment primary key
   - `parent_id`: Foreign key to individuals
   - `child_id`: Foreign key to individuals
   - `relationship_type`: 'father' or 'mother'
   - UNIQUE constraint on (parent_id, child_id, relationship_type)

### Relationship Inference

The parser uses the genealogical numbering system to automatically infer parent-child relationships:
- For person with ID N:
  - Father has ID 2N (even)
  - Mother has ID 2N+1 (odd)

This eliminates the need for static numbering when adding new generations to the tree.

## Installation

1. Create a Python virtual environment:
```bash
cd /path/to/geneamatique
python -m venv .venv
source .venv/bin/activate  # On Linux/Mac
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Configure Data Directory

Set the ODT source folder via environment variable (recommended for anonymization):

```bash
export GENEALOGY_DATA_DIR="data/sources"
```

The parser and tests will read from this directory when present.

### Parse All Documents

Run the parser on all ODT files in the genealogy directory:

```bash
python import_tools/run_parser.py
```

This will:
1. Create/recreate the data/genealogy.db database
2. Parse all .odt files in the configured directory
3. Extract individual information
4. Infer parent-child relationships
5. Store everything in the database

### Inspect Database

View database contents and statistics:

```bash
python inspect_database.py
```

### Query Individuals

Look up specific individuals by name or ID:

```bash
python query_genealogy.py <name_or_id>
```

Examples:
```bash
python query_genealogy.py 2                    # Look up by ID
python query_genealogy.py "Sample Person"      # Search by name
python query_genealogy.py SAMPLE               # Partial name search
```

The query tool displays:
- Full individual details (birth, death, profession, marriage)
- Source documents where the person is mentioned
- Parents (father and mother)
- Children

### Visualize Genealogy Trees

Display ASCII art genealogy trees (like `git log --graph`) using **Sosa-Stradonitz numbering**:

```bash
python tree_visualizer.py <name_or_id>
```

Examples:
```bash
python tree_visualizer.py 2                              # Show ancestor tree
python tree_visualizer.py "Sample Person"               # Ancestor tree by name
python tree_visualizer.py --descendants 64               # Show descendant tree
python tree_visualizer.py -d --max-depth 5 "SAMPLE"      # Descendants, max 5 generations
```

Options:
- `-d, --descendants` - Show descendants instead of ancestors
- `--max-depth N` - Limit descendant tree depth (default: 10)
- `--db PATH` - Specify database path

#### Sosa-Stradonitz Numbering System

The tree visualizer uses the **Sosa-Stradonitz** numbering system for ancestor trees:
- The person of interest (root) is **1**
- For any person with number **N**:
  - Their **father** is **2N** (even)
  - Their **mother** is **2N+1** (odd)

This system makes it easy to identify relationships:
- Numbers 2-3: Parents
- Numbers 4-7: Grandparents (4=paternal grandfather, 5=paternal grandmother, 6=maternal grandfather, 7=maternal grandmother)
- Numbers 8-15: Great-grandparents
- And so on...

For descendant trees, a simple generation-based numbering is used (1, 11, 12, 111, 112, etc.).

The tree visualizer uses box-drawing characters to create a visual tree structure showing the genealogical relationships.

Example output (ancestor tree, anonymized):
```
└──    1 PERSON_A Sample Name (°4 Jan 1952, +15 Oct 2007)
   ├──    3 PERSON_B Sample Name
   │   ├──    7 PERSON_C Sample Name (+12 Mar 1965)
   │   │   ├──   15 PERSON_D Sample Name
   │   │   │   ├──   31 PERSON_E Sample Name
   │   │   │   └──   30 PERSON_F Sample Name
   │   │   └──   14 PERSON_G Sample Name
   │   └──    6 PERSON_H Sample Name
   └──    2 PERSON_I Sample Name (+19 Nov 1990)
      ├──    5 PERSON_J Sample Name (+17 Sep 1972)
      └──    4 PERSON_K Sample Name (+15 Mar 168)
```

Note: Numbers follow Sosa-Stradonitz system (1=person, 2=father, 3=mother, 4-5=paternal grandparents, 6-7=maternal grandparents)

### Run Tests

Execute comprehensive database consistency tests:

```bash
python -m unittest test_database_consistency.py -v
```

## Test Coverage

The test suite includes 22 tests covering:

### Database Structure
- Table existence and schema validation
- Required fields presence
- Referential integrity

### Data Quality
- All individuals have names and IDs
- All individuals reference source files
- Date format consistency
- No null values in critical fields

### Genealogical Invariants
- No self-parenting
- No circular relationships
- Maximum two parents per individual (one father, one mother)
- Parent numbering system compliance
- Gender consistency (even IDs = fathers, odd IDs = mothers)

### Data Analysis
- Root ancestor identification
- Name variation detection
- Relationship type validation

## Sample Results (Anonymized)

Results will vary by dataset. For public repos, use sanitized or synthetic data.

## Files

- `genealogy_parser.py` - Core parser implementation
- `run_parser.py` - Main execution script
- `query_genealogy.py` - Query tool for exploring individuals
- `tree_visualizer.py` - ASCII art genealogy tree visualizer
- `test_database_consistency.py` - Comprehensive test suite
- `test_genealogy_parser.py` - Basic unit tests
- `inspect_database.py` - Database inspection utility
- `examine_odt.py` - ODT structure examination tool
- `data/genealogy.db` - SQLite database (generated)
- `requirements.txt` - Python dependencies
- `README.md` - This file

## Future Enhancements

Potential improvements:
1. Name normalization to merge name variations automatically
2. Date parsing and validation
3. Export to GEDCOM format
4. Web interface for browsing the family tree
5. Visualization of relationships
6. Data conflict resolution when same individual has different data across sources
7. Support for additional relationship types (siblings, spouses, etc.)
