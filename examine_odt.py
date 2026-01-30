#!/usr/bin/env python3
"""Script to examine the structure of an ODT file to understand the data format."""

from odf.opendocument import load
from odf.text import P
from odf.table import Table, TableRow, TableCell


def get_cell_text(cell):
    """Extract text from a table cell."""
    paragraphs = cell.getElementsByType(P)
    text_parts = []
    for p in paragraphs:
        try:
            text = ''.join(str(node)
                           for node in p.childNodes if hasattr(node, 'data'))
            if text.strip():
                text_parts.append(text.strip())
        except:
            pass
    return '\n'.join(text_parts)


def examine_document(filepath):
    """Examine the structure of an ODT document."""
    doc = load(filepath)

    tables = doc.getElementsByType(Table)
    print(f"\n{'='*80}")
    print(f"File: {filepath}")
    print(f"{'='*80}")
    print(f"Number of tables: {len(tables)}")

    for table_idx, table in enumerate(tables):
        rows = table.getElementsByType(TableRow)
        print(f"\nTable {table_idx + 1} has {len(rows)} rows")

        for row_idx, row in enumerate(rows[:5]):  # Show first 5 rows
            cells = row.getElementsByType(TableCell)
            print(f"\n  Row {row_idx + 1} has {len(cells)} cells:")
            for cell_idx, cell in enumerate(cells):
                text = get_cell_text(cell)
                if text:
                    # First 200 chars
                    print(f"    Cell {cell_idx + 1}: {text[:200]}")


if __name__ == "__main__":
    # Examine a couple of sample files (anonymized placeholders)
    files = [
        "data/sources/2 Sample Person.odt",
        "data/sources/16 Sample Person.odt",
    ]

    for filepath in files:
        try:
            examine_document(filepath)
        except Exception as e:
            print(f"Error examining {filepath}: {e}")
