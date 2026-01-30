# Family Tree Scoping Implementation

## Overview
Implemented support for multiple independent family trees within a single database. This resolves the issue where different family tree directories had overlapping Sosa IDs that previously caused conflicts.

## Changes Made

### 1. Database Schema
- **Added `family_tree` column** to `individuals` table (TEXT NOT NULL)
- **Updated unique constraint** from `UNIQUE(old_id)` to `UNIQUE(old_id, family_tree)`
- Family tree name is extracted from the first subdirectory under the data source path

### 2. Parser Updates (genealogy_parser.py)
- `parse_document()`: Now extracts family tree name from file path relative to base directory
- `parse_individual_data()`: Accepts `family_tree` parameter and includes it in returned dict
- `store_data()`: Queries and inserts using `(old_id, family_tree)` combination
- `infer_relationships()`: Only matches parents within the same family tree

### 3. Query Tools Updates

#### query_genealogy.py
- Includes `family_tree` in all SELECT statements
- Displays family tree name in individual details
- Lists family tree alongside name when showing multiple matches

#### tree_visualizer.py
- Includes `family_tree` in all queries
- Added `--family-tree` CLI argument for disambiguation
- Shows family tree name in headers and multiple match lists
- Properly unpacks family_tree in all result tuples

#### inspect_database.py
- Shows count of distinct family trees
- Lists individuals per family tree
- Displays family tree name in sample individuals

### 4. Test Updates (test_database_consistency.py)
- Added `family_tree` to required columns test
- New test: `test_all_individuals_have_family_tree()`
- New test: `test_old_id_unique_within_family_tree()`

## Current Database Statistics
- **Total individuals**: 363
- **Family trees**: 4
  - Généalogie de Natacha: 238 individuals
  - Généalogie d'Eric: 119 individuals
  - Généalogie de Yelena: 3 individuals
  - Généalogie de Rachel: 3 individuals
- **Total relationships**: 346

## Usage Examples

### Query by ID (now shows all matching trees)
```bash
python import_tools/query_genealogy.py 2
```
Output shows all individuals with old_id=2 across different family trees:
```
   2  [Généalogie d'Eric             ]  MOUNTAIN Eric
   2  [Généalogie de Natacha         ]  MANOURY Bernard François René
   2  [Généalogie de Rachel          ]  MOUNTAIN Eric Stephen
   2  [Généalogie de Yelena          ]  MOUNTAIN Eric Stephen
```

### Visualize tree with disambiguation
```bash
python import_tools/tree_visualizer.py "MOUNTAIN Eric" --family-tree "Généalogie d'Eric"
```

### Inspect database
```bash
python import_tools/inspect_database.py
```
Shows breakdown by family tree.

## Benefits
1. **No more ID conflicts**: Same Sosa ID can exist in different family trees
2. **Correct relationships**: Parent-child matching only within same tree
3. **Clear disambiguation**: Users can identify which tree contains their target individual
4. **Data integrity**: Unique constraint properly scoped to (old_id, family_tree)

## Implementation Notes
- Family tree name comes from the first subdirectory under `data/sources`
- Example: `data/sources/Généalogie d'Eric/Tableaux Eric/file.odt` → family_tree = "Généalogie d'Eric"
- Relationships are never created between different family trees
- All existing tools updated to handle the new schema

## Testing
- All 29 tests pass, including 2 new tests for family tree functionality
- Database successfully re-imported with new schema
- Tree visualization confirmed working with proper scoping
