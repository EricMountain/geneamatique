# Ignoring Files During Parsing

The genealogy parser now supports ignoring specific ODT files during parsing. This is useful when you discover data conflicts between source files and need to exclude certain files while you resolve the inconsistencies.

## Usage

### Command-line Option

Run the parser with the `--ignore-files` argument to specify filenames to skip:

```bash
python import_tools/run_parser.py --ignore-files "file1.odt,file2.odt"
```

Multiple files can be ignored by separating them with commas:

```bash
python import_tools/run_parser.py --ignore-files "arbre Nat.odt,conflicting_file.odt"
```

### Environment Variable

Alternatively, set the `GENEALOGY_IGNORE_FILES` environment variable:

```bash
export GENEALOGY_IGNORE_FILES="arbre Nat.odt,conflicting_file.odt"
python import_tools/run_parser.py
```

Or set it inline:

```bash
GENEALOGY_IGNORE_FILES="arbre Nat.odt" python import_tools/run_parser.py
```

## Example: Resolving old_id Conflicts

If you discover that multiple files in the same family tree directory have assigned different people to the same `old_id`, you can temporarily exclude one file while you reconcile the source data.

For example, if "arbre Nat.odt" and "arbre paternel Eric.odt" both assign `old_id 4` to different people:

```bash
python import_tools/run_parser.py --ignore-files "arbre Nat.odt"
```

This will:
- Skip parsing "arbre Nat.odt"
- Use the `old_id` assignments from the remaining files
- Display which files were ignored in the output

## Identifying Conflicts

The parser reports data conflicts in the output:

```
WARNING: Data conflict in 'Généalogie d'Eric', old_id 4:
  Existing: MANOURY André Eugène Léon (from earlier file)
  New: MOUNTAIN William (from arbre paternel Eric.odt)
  Keeping existing entry. Check source files for inconsistencies.
```

When you encounter conflicts:

1. Review the source ODT files to understand the discrepancy
2. Determine which `old_id` assignments are correct
3. Manually edit the source files to correct the inconsistencies
4. Re-run the parser without `--ignore-files` to verify the fix

## Notes

- File matching is by exact filename (e.g., "arbre Nat.odt", not "Nat.odt")
- The parser processes files alphabetically, so the first file to assign an `old_id` "wins"
- Ignoring files is a temporary workaround for resolving source data conflicts
- Always aim to fix the source ODT files rather than relying on `--ignore-files` permanently
