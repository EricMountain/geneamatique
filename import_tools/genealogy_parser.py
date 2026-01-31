import os
import sqlite3
import re
import warnings
from datetime import datetime
from odf.opendocument import load
from odf.text import P
from odf.table import Table, TableRow, TableCell

# Handle both package and direct import
try:
    from .calendar.util import republican_to_gregorian
except ImportError:
    from calendar.util import republican_to_gregorian

# Global accumulator for date inconsistency warnings
_date_warnings = []


def create_database(db_name='data/genealogy.db'):
    """Create the SQLite database with proper schema."""
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Drop existing tables to start fresh
    cursor.execute('DROP TABLE IF EXISTS relationships')
    cursor.execute('DROP TABLE IF EXISTS individual_sources')
    cursor.execute('DROP TABLE IF EXISTS individual_tree_instances')
    cursor.execute('DROP TABLE IF EXISTS individuals')

    # Canonical individuals table - one entry per unique person
    cursor.execute('''
    CREATE TABLE individuals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        canonical_name TEXT NOT NULL,
        name_comment TEXT,
        date_of_birth TEXT,
        birth_location TEXT,
        birth_comment TEXT,
        date_of_death TEXT,
        death_location TEXT,
        death_comment TEXT,
        profession TEXT,
        marriage_date TEXT,
        marriage_location TEXT,
        marriage_comment TEXT
    )
    ''')

    # Track each appearance of an individual in different family trees
    cursor.execute('''
    CREATE TABLE individual_tree_instances (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        individual_id INTEGER NOT NULL,
        family_tree TEXT NOT NULL,
        old_id INTEGER NOT NULL,
        name_variant TEXT,
        source_file TEXT,
        UNIQUE(family_tree, old_id),
        FOREIGN KEY (individual_id) REFERENCES individuals(id)
    )
    ''')

    # Track which source files mention each individual
    cursor.execute('''
    CREATE TABLE individual_sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        individual_id INTEGER,
        source_file TEXT,
        FOREIGN KEY (individual_id) REFERENCES individuals(id),
        UNIQUE(individual_id, source_file)
    )
    ''')

    # Relationships reference the canonical individual_id
    # and are scoped to specific tree contexts via tree_instances
    cursor.execute('''
    CREATE TABLE relationships (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        parent_id INTEGER,
        child_id INTEGER,
        relationship_type TEXT,
        family_tree TEXT NOT NULL,
        FOREIGN KEY (parent_id) REFERENCES individuals(id),
        FOREIGN KEY (child_id) REFERENCES individuals(id),
        UNIQUE(parent_id, child_id, relationship_type, family_tree)
    )
    ''')
    conn.commit()
    conn.close()


def get_cell_text(cell):
    """Extract all text from a table cell, recursively getting text from all child nodes including spans."""
    from odf import text as odf_text

    def get_text_recursive(element):
        """Recursively extract all text from an element and its children."""
        text_content = []
        for node in element.childNodes:
            if hasattr(node, 'data'):
                # Direct text node
                text_content.append(str(node.data))
            elif hasattr(node, 'childNodes'):
                # Element with children (like text:span) - recurse into it
                text_content.append(get_text_recursive(node))
        return ''.join(text_content)

    paragraphs = cell.getElementsByType(P)
    text_parts = []
    for p in paragraphs:
        try:
            text = get_text_recursive(p)
            if text.strip():
                text_parts.append(text.strip())
        except Exception as e:
            pass
    return '\n'.join(text_parts)


def normalize_location_name(location):
    """Normalize location names by title-casing all-uppercase names.

    Args:
        location: Location string to normalize

    Returns:
        Normalized location string
    """
    if not location:
        return location

    # If the location is all uppercase (and contains at least one letter), title-case it
    if location.isupper() and any(c.isalpha() for c in location):
        return location.title()

    return location


def parse_event_details(text_after_marker, event_type='birth', source_file=None, person_name=None):
    """Parse event details (date, location, comment) from text after a marker.

    Args:
        text_after_marker: Text after ° (birth), + (death), or X (marriage) marker
        event_type: Type of event for better error messages
        source_file: Source ODT filename for warning messages
        person_name: Name of the person for warning messages

    Returns:
        dict with 'date', 'location', 'comment' keys (all ISO8601 format for dates)
    """
    if not text_after_marker:
        return {'date': None, 'location': None, 'comment': None}

    text = text_after_marker.strip()
    date_iso = None
    location = None
    comment = None

    # Track original date strings for warning messages
    original_gregorian = None
    original_revolutionary = None

    # Skip common event type prefixes that might appear in the text
    event_prefixes = [
        r'^(naissance|birth|baptême|baptism)\s+',
        r'^(décès|death|décédé|mort|décédée|morte)\s+',
        r'^(mariage|marriage|marié|mariée)\s+',
        r'^(divorce|divorcé|divorcée)\s+',
        r'^(inhumation|burial|enterrement)\s+',
        r'^(émigration|immigration)\s+'
    ]

    for prefix_pattern in event_prefixes:
        match = re.match(prefix_pattern, text, re.IGNORECASE)
        if match:
            text = text[match.end():].strip()
            break  # Only remove one prefix

    # French Revolutionary calendar month names
    fr_months = ['vendémiaire', 'brumaire', 'frimaire', 'nivôse', 'pluviôse', 'ventôse',
                 'germinal', 'floréal', 'prairial', 'messidor', 'thermidor', 'fructidor']

    # Try to match a date at the beginning
    # Gregorian date patterns: "4 Jan 1952", "04/01/1952", "1952-01-04", "04.01.1952", "4 Jan1952", "1er juillet 1788", "26avril 1831"
    gregorian_patterns = [
        r'^(1er|\d{1,2})(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+(\d{4})',
        r'^(1er|\d{1,2})(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)(\d{4})',
        r'^(1er|\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+(\d{4})',
        r'^(1er|\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)(\d{4})',
        r'^(\d{1,2})/(\d{1,2})/(\d{4})',
        r'^(\d{1,2})\.(\d{1,2})\.(\d{4})',
        r'^(\d{4})-(\d{1,2})-(\d{1,2})'
    ]

    # Try to match French Revolutionary date at the beginning (not in parentheses)
    fr_pattern = r'^(\d{1,2})\s+(' + '|'.join(fr_months) + \
        r')\s+(?:an\s+)?(\w+)'
    fr_match = re.match(fr_pattern, text, re.IGNORECASE)

    gregorian_date = None
    revolutionary_date_first = None
    remaining_text = text

    if fr_match:
        # Found French Revolutionary date at start
        revolutionary_date_first = fr_match.group(0)
        try:
            date_iso = parse_french_revolutionary_date(
                revolutionary_date_first)
            remaining_text = text[fr_match.end():].strip()
        except Exception as e:
            # If FR date parsing fails, treat as comment
            return {'date': None, 'location': None, 'comment': text}
    else:
        # Try Gregorian date patterns
        for pattern in gregorian_patterns:
            match = re.match(pattern, text, re.IGNORECASE)
            if match:
                gregorian_date = match.group(0)
                original_gregorian = gregorian_date  # Store original for warning
                remaining_text = text[match.end():].strip()
                # Convert to ISO8601
                try:
                    date_iso = parse_date_to_iso(gregorian_date)
                except:
                    # If conversion fails, store as-is in comment
                    comment = text
                    return {'date': None, 'location': None, 'comment': comment}
                break

    # Check for French Revolutionary date in parentheses (for dual date format)
    fr_date_match = re.search(r'\(([^)]+)\)', remaining_text)
    if fr_date_match:
        potential_fr_date = fr_date_match.group(1).strip()
        # Check if it looks like a French Revolutionary date
        is_fr_date = any(month in potential_fr_date.lower()
                         for month in fr_months)

        if is_fr_date:
            try:
                original_revolutionary = potential_fr_date  # Store original for warning
                fr_date_iso = parse_french_revolutionary_date(
                    potential_fr_date)

                # Check if we already have a date from the start
                if date_iso:
                    # We have a date already - check what type it was
                    if gregorian_date:
                        # Gregorian + Revolutionary in parens - check consistency
                        if fr_date_iso != date_iso:
                            warning_msg = (
                                f"Date inconsistency in {event_type}:\n"
                                f"  File: {source_file or 'unknown'}\n"
                                f"  Person: {person_name or 'unknown'}\n"
                                f"  Gregorian date: '{original_gregorian}' (ISO: {date_iso})\n"
                                f"  Revolutionary date: '{original_revolutionary}' (ISO: {fr_date_iso})\n"
                                f"  Using Gregorian date."
                            )
                            warnings.warn(warning_msg)
                            # Accumulate warning for end-of-run summary
                            _date_warnings.append({
                                'event_type': event_type,
                                'file': source_file,
                                'person': person_name,
                                'gregorian_original': original_gregorian,
                                'gregorian_iso': date_iso,
                                'revolutionary_original': original_revolutionary,
                                'revolutionary_iso': fr_date_iso
                            })
                    elif revolutionary_date_first:
                        # Revolutionary + Revolutionary in parens - check consistency
                        if fr_date_iso != date_iso:
                            warning_msg = (
                                f"Date inconsistency in {event_type}:\n"
                                f"  File: {source_file or 'unknown'}\n"
                                f"  Person: {person_name or 'unknown'}\n"
                                f"  First Revolutionary date: '{revolutionary_date_first}' (ISO: {date_iso})\n"
                                f"  Second Revolutionary date: '{original_revolutionary}' (ISO: {fr_date_iso})\n"
                                f"  Using first date."
                            )
                            warnings.warn(warning_msg)
                            # Accumulate warning for end-of-run summary
                            _date_warnings.append({
                                'event_type': event_type,
                                'file': source_file,
                                'person': person_name,
                                'gregorian_original': revolutionary_date_first,
                                'gregorian_iso': date_iso,
                                'revolutionary_original': original_revolutionary,
                                'revolutionary_iso': fr_date_iso
                            })
                else:
                    # Only Revolutionary date in parentheses, no date at start
                    date_iso = fr_date_iso

                # Remove the French Revolutionary date from remaining text
                remaining_text = remaining_text[:fr_date_match.start(
                )] + remaining_text[fr_date_match.end():]
                remaining_text = remaining_text.strip()
            except Exception as e:
                # If FR date parsing fails, just ignore it
                pass

    if not date_iso:
        # No date found - entire text becomes comment
        return {'date': None, 'location': None, 'comment': text}

    # Extract location and comment
    if remaining_text:
        # First, try the traditional "à"/"au" pattern
        location_match = re.match(
            r'^(?:à|au)\s+(.+)', remaining_text, re.IGNORECASE)
        if location_match:
            potential_location = location_match.group(1).strip()
            # Check if there's a comment in parentheses at the end
            paren_match = re.search(r'\s*\(([^)]+)\)$', potential_location)
            if paren_match:
                # Check if the content in parentheses is a department number (just digits)
                paren_content = paren_match.group(1).strip()
                if paren_content.isdigit():
                    # Department number - keep it as part of location
                    location = normalize_location_name(potential_location)
                else:
                    # Comment - split it
                    location = normalize_location_name(
                        potential_location[:paren_match.start()].strip())
                    comment = paren_content
            else:
                location = normalize_location_name(potential_location)
        else:
            # No "à"/"au" - assume remaining text is location unless it's entirely in parentheses
            if remaining_text.startswith('(') and remaining_text.endswith(')'):
                paren_content = remaining_text[1:-1].strip()
                if paren_content.isdigit():
                    # Department number in parentheses - treat as location
                    location = normalize_location_name(remaining_text)
                else:
                    # Comment in parentheses
                    comment = paren_content
            else:
                # Check for comment in parentheses
                paren_match = re.search(r'\s*\(([^)]+)\)', remaining_text)
                if paren_match:
                    # Check if the parentheses contain only a department number
                    paren_content = paren_match.group(1).strip()
                    if paren_content.isdigit() and paren_match.start() > 0:
                        # There's text before the parentheses, and parentheses contain department number
                        # Keep it all as location
                        location = normalize_location_name(remaining_text)
                    else:
                        # Split: text before parentheses is location, content is comment
                        location = normalize_location_name(
                            remaining_text[:paren_match.start()].strip())
                        comment = paren_content
                else:
                    # No parentheses - entire remaining text is location
                    location = normalize_location_name(remaining_text)

    return {'date': date_iso, 'location': clean_location(location), 'comment': comment}


def clean_location(location):
    """Clean up location strings by removing leading/trailing whitespace and punctuation."""
    if not location:
        return location

    # Strip leading/trailing whitespace
    location = location.strip()

    # Remove leading commas, semicolons, and other punctuation
    location = re.sub(r'^[,;:.\s]+', '', location)

    # Remove trailing punctuation
    location = re.sub(r'[,;:.\s]+$', '', location)

    return location


def parse_date_to_iso(date_str):
    """Convert various date formats to ISO8601 (YYYY-MM-DD)."""
    date_str = date_str.strip()

    # Map month names to numbers
    month_map_en = {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12}
    month_map_fr = {'janvier': 1, 'février': 2, 'mars': 3, 'avril': 4, 'mai': 5, 'juin': 6,
                    'juillet': 7, 'août': 8, 'septembre': 9, 'octobre': 10, 'novembre': 11, 'décembre': 12}

    # Try "26avril 1831" format (no space between day and month)
    match = re.match(
        r'^(1er|\d{1,2})(\w+)\s+(\d{4})$', date_str, re.IGNORECASE)
    if match:
        day_str = match.group(1)
        day = 1 if day_str == '1er' else int(day_str)
        month_str = match.group(2).lower()[:3]
        year = int(match.group(3))
        month = month_map_en.get(month_str) or month_map_fr.get(
            match.group(2).lower())
        if month:
            return f"{year:04d}-{month:02d}-{day:02d}"

    # Try "26avril1831" format (no space between day and month, no space before year)
    match = re.match(r'^(1er|\d{1,2})(\w+)(\d{4})$', date_str, re.IGNORECASE)
    if match:
        day_str = match.group(1)
        day = 1 if day_str == '1er' else int(day_str)
        month_str = match.group(2).lower()[:3]
        year = int(match.group(3))
        month = month_map_en.get(month_str) or month_map_fr.get(
            match.group(2).lower())
        if month:
            return f"{year:04d}-{month:02d}-{day:02d}"

    # Try "4 Jan 1952" format or "1er juillet 1788"
    match = re.match(
        r'^(1er|\d{1,2})\s+(\w+)\s+(\d{4})$', date_str, re.IGNORECASE)
    if match:
        day_str = match.group(1)
        day = 1 if day_str == '1er' else int(day_str)
        month_str = match.group(2).lower()[:3]
        year = int(match.group(3))
        month = month_map_en.get(month_str) or month_map_fr.get(
            match.group(2).lower())
        if month:
            return f"{year:04d}-{month:02d}-{day:02d}"

    # Try "4 Jan1952" format (no space before year) or "1er juillet1788"
    match = re.match(
        r'^(1er|\d{1,2})\s+(\w+)(\d{4})$', date_str, re.IGNORECASE)
    if match:
        day_str = match.group(1)
        day = 1 if day_str == '1er' else int(day_str)
        month_str = match.group(2).lower()[:3]
        year = int(match.group(3))
        month = month_map_en.get(month_str) or month_map_fr.get(
            match.group(2).lower())
        if month:
            return f"{year:04d}-{month:02d}-{day:02d}"

    # Try "04/01/1952" format (DD/MM/YYYY)
    match = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', date_str)
    if match:
        day = int(match.group(1))
        month = int(match.group(2))
        year = int(match.group(3))
        return f"{year:04d}-{month:02d}-{day:02d}"

    # Try "04.01.1952" format (DD.MM.YYYY)
    match = re.match(r'^(\d{1,2})\.(\d{1,2})\.(\d{4})$', date_str)
    if match:
        day = int(match.group(1))
        month = int(match.group(2))
        year = int(match.group(3))
        return f"{year:04d}-{month:02d}-{day:02d}"

    # Try "1952-01-04" format (already ISO8601)
    match = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})$', date_str)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))
        return f"{year:04d}-{month:02d}-{day:02d}"

    raise ValueError(f"Could not parse date: {date_str}")


def parse_french_revolutionary_date(fr_date_str):
    """Parse French Revolutionary calendar date and convert to ISO8601.

    Example: "8 thermidor an II" -> converts to Gregorian ISO8601
    """
    fr_months = {
        'vendémiaire': 1, 'brumaire': 2, 'frimaire': 3,
        'nivôse': 4, 'pluviôse': 5, 'ventôse': 6,
        'germinal': 7, 'floréal': 8, 'prairial': 9,
        'messidor': 10, 'thermidor': 11, 'fructidor': 12
    }

    # Pattern: "8 thermidor an II" or "8 thermidor II"
    match = re.match(r'(\d{1,2})\s+(\w+)\s+(?:an\s+)?(\w+)',
                     fr_date_str, re.IGNORECASE)
    if not match:
        raise ValueError(
            f"Could not parse French Revolutionary date: {fr_date_str}")

    day = int(match.group(1))
    month_name = match.group(2).lower()
    year_str = match.group(3)

    # Convert Roman numerals to integers
    roman_map = {'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5, 'VI': 6, 'VII': 7,
                 'VIII': 8, 'IX': 9, 'X': 10, 'XI': 11, 'XII': 12, 'XIII': 13, 'XIV': 14}
    year = roman_map.get(year_str.upper())
    if not year:
        try:
            year = int(year_str)
        except:
            raise ValueError(f"Could not parse year: {year_str}")

    month = fr_months.get(month_name)
    if not month:
        raise ValueError(f"Unknown French Revolutionary month: {month_name}")

    # Convert to Gregorian
    greg_year, greg_month, greg_day = republican_to_gregorian(year, month, day)
    return f"{greg_year:04d}-{greg_month:02d}-{greg_day:02d}"


def parse_individual_data(cell_text, source_file=None, family_tree=None):
    """Parse individual data from cell text.

    Format examples (anonymized):
    Multi-line format:
    2. PERSON_A Sample Name
    ° 4 Jan 1952 à City A
    + 15 Oct 2007 au City B (accident)
    PR Technician
    X 28 Jul 1973 à City C

    Single-line format:
    5. PERSON_B Sample Name° 18 Feb 1917 à City D+ 2 Jul 2015PR Tailor

    With French Revolutionary calendar:
    6. PERSON_C
    ° 8 thermidor an II (26 Jul 1794)

    Args:
        cell_text: Text content from the table cell
        source_file: Source ODT filename for warning messages
        family_tree: Family tree identifier (subdirectory name)
    """
    if not cell_text or not cell_text.strip():
        return None

    # First, normalize the text by inserting newlines before special markers if they're on the same line
    # This handles cases where all data is concatenated without proper line breaks
    text = cell_text.strip()
    # Insert newlines before °, +, PR markers when they appear mid-line
    text = re.sub(r'([^\n])°', r'\1\n°', text)
    text = re.sub(r'([^\n])\+', r'\1\n+', text)
    text = re.sub(r'([^\n])PR', r'\1\nPR', text)
    # Note: X marker is NOT normalized here because it always starts on a new line in source data
    # This prevents incorrectly splitting names that end with X (like "CALBRIX") or contain "X"
    # as a middle initial/part (like "DUPONT X")

    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if not lines:
        return None

    # Extract ID and name from first line
    first_line = lines[0]
    match = re.match(r'^(\d+)\.\s*(.+)$', first_line)
    if not match:
        # Try without dot after number
        match = re.match(r'^(\d+)\s+(.+)$', first_line)
        if not match:
            return None

    old_id = int(match.group(1))
    full_name = match.group(2).strip()

    # Extract additional name information from "dite", "né", "née", "mais" patterns and parenthetical comments
    name_comment_parts = []
    name = full_name

    # First, extract "dite", "né", "née", "mais" information
    dite_match = re.search(
        r'\s+(dit|dite|né|née|mais)\s+(.+)$', name, re.IGNORECASE)
    if dite_match:
        additional_name = dite_match.group(2).strip()
        name_comment_parts.append(f"{dite_match.group(1)} {additional_name}")
        name = name[:dite_match.start()].strip()

    # Then extract parenthetical comments
    paren_match = re.search(r'\s*\(([^)]+)\)$', name)
    if paren_match:
        name_comment_parts.append(paren_match.group(1).strip())
        name = name[:paren_match.start()].strip()

    # Combine all name comment parts
    name_comment = '; '.join(
        name_comment_parts) if name_comment_parts else None

    # Parse other fields
    birth_details = {'date': None, 'location': None, 'comment': None}
    death_details = {'date': None, 'location': None, 'comment': None}
    marriage_details = {'date': None, 'location': None, 'comment': None}
    profession = None

    for line in lines[1:]:
        if line.startswith('°'):
            birth_details = parse_event_details(
                line[1:].strip(), 'birth', source_file, name)
        elif line.startswith('+'):
            death_details = parse_event_details(
                line[1:].strip(), 'death', source_file, name)
        elif line.startswith('PR'):
            profession = line[2:].strip()
        elif line.startswith('X'):
            marriage_details = parse_event_details(
                line[1:].strip(), 'marriage', source_file, name)

    return {
        'old_id': old_id,
        'family_tree': family_tree,
        'name': name,
        'name_comment': name_comment,
        'date_of_birth': birth_details['date'],
        'birth_location': birth_details['location'],
        'birth_comment': birth_details['comment'],
        'date_of_death': death_details['date'],
        'death_location': death_details['location'],
        'death_comment': death_details['comment'],
        'profession': profession,
        'marriage_date': marriage_details['date'],
        'marriage_location': marriage_details['location'],
        'marriage_comment': marriage_details['comment']
    }


def parse_document(filepath, base_path=None):
    """Parse a single ODT document and extract all individuals.

    Args:
        filepath: Full path to the ODT file
        base_path: Base folder path to extract family tree name from
    """
    individuals = []
    # Use relative path for source file reference
    if base_path:
        source_filename = os.path.relpath(filepath, base_path)
    else:
        source_filename = os.path.basename(filepath)

    # Extract family tree name (first subdirectory under base_path)
    family_tree = 'unknown'
    if base_path:
        rel_path = os.path.relpath(filepath, base_path)
        parts = rel_path.split(os.sep)
        if len(parts) > 0:
            family_tree = parts[0]

    try:
        doc = load(filepath)
        tables = doc.getElementsByType(Table)

        for table in tables:
            rows = table.getElementsByType(TableRow)
            for row in rows:
                cells = row.getElementsByType(TableCell)
                for cell in cells:
                    cell_text = get_cell_text(cell)
                    individual = parse_individual_data(
                        cell_text, source_filename, family_tree)
                    if individual:
                        individual['source_file'] = source_filename
                        individuals.append(individual)
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")

    return individuals


def parse_documents(folder_path, ignore_patterns=None):
    """Parse all ODT documents in the folder and subfolders.

    Args:
        folder_path: Root directory to search for ODT files
        ignore_patterns: Set of file/directory patterns to skip during parsing
                        Patterns can be filenames, directory names, or relative paths
    """
    all_individuals = []

    if ignore_patterns is None:
        ignore_patterns = set()

    if not os.path.exists(folder_path):
        print(f"Folder not found: {folder_path}")
        return all_individuals

    for root, dirs, files in os.walk(folder_path):
        # Check if current directory should be ignored
        rel_root = os.path.relpath(root, folder_path)
        if rel_root != '.' and any(pattern in rel_root for pattern in ignore_patterns):
            print(
                f"\033[1;33mSkipping\033[0m directory \033[1;36m\"{rel_root}\"\033[0m (\033[38;5;208mignored\033[0m)")
            dirs[:] = []  # Don't recurse into this directory
            continue

        for filename in sorted(files):
            if filename.endswith('.odt') and not filename.startswith('tableau vide'):
                # Check if file should be ignored
                rel_path = os.path.relpath(
                    os.path.join(root, filename), folder_path)

                # Check for exact filename match or path match
                should_ignore = False
                for pattern in ignore_patterns:
                    if pattern in rel_path or pattern == filename:
                        should_ignore = True
                        break

                if should_ignore:
                    print(
                        f"\033[1;33mSkipping\033[0m \033[1;36m\"{rel_path}\"\033[0m (\033[38;5;208mignored\033[0m)")
                    continue

                filepath = os.path.join(root, filename)
                individuals = parse_document(filepath, folder_path)
                all_individuals.extend(individuals)
                print(
                    f"\033[1;33mParsing\033[0m \033[1;36m\"{rel_path}\"\033[0m... found \033[1;33m{len(individuals)} individuals\033[0m")

    return all_individuals


def infer_relationships(individuals_dict, tree_instance_map):
    """Infer parent-child relationships based on old_id numbering.

    In genealogy numbering:
    - Each person has an ID
    - Their parents have IDs that are 2*ID and 2*ID+1
    - Even IDs are typically male, odd IDs are female

    Relationships are scoped to family trees and use canonical individual_ids.
    Within a tree, (family_tree, old_id) uniquely identifies an individual.

    Args:
        individuals_dict: dict mapping (family_tree, old_id) -> individual data
        tree_instance_map: dict mapping (family_tree, old_id) -> canonical individual_id
    """
    relationships = []
    processed_children = set()  # Track (family_tree, child_id) to avoid duplicates

    # Find parent-child relationships within each tree
    for tree_key, individual_data in individuals_dict.items():
        old_id = individual_data['old_id']
        family_tree = individual_data['family_tree']
        child_individual_id = individual_data['individual_id']

        # Skip if we've already processed relationships for this child in this tree
        child_key = (family_tree, child_individual_id)
        if child_key in processed_children:
            continue

        processed_children.add(child_key)

        # Parents would have IDs of 2*old_id and 2*old_id+1 in the SAME family tree
        father_id = 2 * old_id
        mother_id = 2 * old_id + 1

        father_key = (family_tree, father_id)
        mother_key = (family_tree, mother_id)

        if father_key in tree_instance_map:
            parent_individual_id = tree_instance_map[father_key]
            relationships.append({
                'parent_id': parent_individual_id,
                'child_id': child_individual_id,
                'relationship_type': 'father',
                'family_tree': family_tree
            })

        if mother_key in tree_instance_map:
            parent_individual_id = tree_instance_map[mother_key]
            relationships.append({
                'parent_id': parent_individual_id,
                'child_id': child_individual_id,
                'relationship_type': 'mother',
                'family_tree': family_tree
            })

    return relationships


def get_date_warnings():
    """Get accumulated date inconsistency warnings."""
    return _date_warnings.copy()


def clear_date_warnings():
    """Clear accumulated date inconsistency warnings."""
    global _date_warnings
    _date_warnings = []


def normalize_name(name):
    """Normalize a name for matching across trees."""
    import re
    # Remove extra whitespace, convert to uppercase for comparison
    normalized = ' '.join(name.upper().split())
    # Remove common variations
    normalized = re.sub(r'\s*\([^)]*\)', '',
                        normalized)  # Remove parentheses content
    return normalized


def find_matching_individual(cursor, individual):
    """Find existing individual that matches by name and birth date.

    Matching criteria:
    1. Exact normalized name match
    2. Birth date must match (if both have birth dates)
    3. If either is missing birth date, no match (to avoid false positives)
    """
    normalized_name = normalize_name(individual['name'])

    # Require birth date for matching across trees
    if not individual['date_of_birth']:
        return None

    # First try exact name match
    cursor.execute('''
        SELECT id, canonical_name, date_of_birth, date_of_death
        FROM individuals
        WHERE UPPER(REPLACE(canonical_name, '  ', ' ')) = ?
    ''', (normalized_name,))

    candidates = cursor.fetchall()

    for candidate in candidates:
        candidate_id, candidate_name, candidate_dob, candidate_dod = candidate

        # Require birth date match
        if not candidate_dob:
            continue

        if individual['date_of_birth'] != candidate_dob:
            continue

        # Check death date compatibility if both present
        if individual['date_of_death'] and candidate_dod:
            if individual['date_of_death'] != candidate_dod:
                continue

        return candidate_id

    return None


def store_data(individuals, db_name='data/genealogy.db'):
    """Store parsed individuals and inferred relationships in the database.

    Creates canonical individuals and tracks their appearances in different trees.
    Matches individuals across trees by normalized name and compatible dates.
    """
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Map (family_tree, old_id) -> canonical individual_id
    tree_instance_map = {}

    # Track individuals_dict for relationship inference: individual_id -> individual data
    individuals_dict = {}

    # Track merged individuals (appearing in multiple trees)
    merged_individuals = []

    # Track number of conflict warnings
    warning_count = 0

    for individual in individuals:
        try:
            family_tree = individual['family_tree']
            old_id = individual['old_id']
            tree_key = (family_tree, old_id)

            # Check if this tree instance already exists
            cursor.execute('''
                SELECT individual_id, name_variant, source_file
                FROM individual_tree_instances
                WHERE family_tree = ? AND old_id = ?
            ''', (family_tree, old_id))
            existing_instance = cursor.fetchone()

            if existing_instance:
                # Tree instance exists - check if it's the same person
                individual_id = existing_instance[0]
                existing_variant = existing_instance[1]
                # Get the existing source file
                existing_source_file = existing_instance[2]

                # Get the canonical name of the existing individual
                cursor.execute('''
                    SELECT canonical_name FROM individuals WHERE id = ?
                ''', (individual_id,))
                existing_canonical_name = cursor.fetchone()[0]

                # Check if names match (normalize both for comparison)
                if normalize_name(individual['name']) != normalize_name(existing_canonical_name):
                    # CONFLICT: Same (family_tree, old_id) but different people!
                    warning_count += 1
                    print(
                        f"\033[1;33mWARNING\033[0m: Data conflict in '{family_tree}', old_id {old_id}, keeping existing entry.")
                    print(
                        f"  \033[1mExisting:\033[0m \033[32m{existing_canonical_name}\033[0m (from \033[36m\"{existing_source_file}\"\033[0m)")
                    print(
                        f"  \033[1mNew:\033[0m      \033[31m{individual['name']}\033[0m (from \033[36m\"{individual['source_file']}\"\033[0m)")
                    continue  # Skip this conflicting entry

                # Same person - prefer longer/more complete name variant
                if len(individual['name']) > len(existing_variant or ''):
                    cursor.execute('''
                        UPDATE individual_tree_instances
                        SET name_variant = ?
                        WHERE family_tree = ? AND old_id = ?
                    ''', (individual['name'], family_tree, old_id))

                # Merge data into canonical individual
                cursor.execute('''
                    SELECT canonical_name, date_of_birth, birth_location, birth_comment,
                           date_of_death, death_location, death_comment, profession,
                           marriage_date, marriage_location, marriage_comment
                    FROM individuals WHERE id = ?
                ''', (individual_id,))
                existing_data = cursor.fetchone()

                if existing_data:
                    updates = []
                    params = []

                    # Update only empty fields
                    if individual['date_of_birth'] and not existing_data[1]:
                        updates.append('date_of_birth = ?')
                        params.append(individual['date_of_birth'])
                    if individual['birth_location'] and not existing_data[2]:
                        updates.append('birth_location = ?')
                        params.append(individual['birth_location'])
                    if individual['birth_comment'] and not existing_data[3]:
                        updates.append('birth_comment = ?')
                        params.append(individual['birth_comment'])
                    if individual['date_of_death'] and not existing_data[4]:
                        updates.append('date_of_death = ?')
                        params.append(individual['date_of_death'])
                    if individual['death_location'] and not existing_data[5]:
                        updates.append('death_location = ?')
                        params.append(individual['death_location'])
                    if individual['death_comment'] and not existing_data[6]:
                        updates.append('death_comment = ?')
                        params.append(individual['death_comment'])
                    if individual['profession'] and not existing_data[7]:
                        updates.append('profession = ?')
                        params.append(individual['profession'])
                    if individual['marriage_date'] and not existing_data[8]:
                        updates.append('marriage_date = ?')
                        params.append(individual['marriage_date'])
                    if individual['marriage_location'] and not existing_data[9]:
                        updates.append('marriage_location = ?')
                        params.append(individual['marriage_location'])
                    if individual['marriage_comment'] and not existing_data[10]:
                        updates.append('marriage_comment = ?')
                        params.append(individual['marriage_comment'])

                    if updates:
                        params.append(individual_id)
                        cursor.execute(f'''
                            UPDATE individuals
                            SET {', '.join(updates)}
                            WHERE id = ?
                        ''', params)

            else:
                # New tree instance - try to find matching canonical individual
                individual_id = find_matching_individual(cursor, individual)

                if individual_id is None:
                    # No match found - create new canonical individual
                    cursor.execute('''
                        INSERT INTO individuals
                        (canonical_name, name_comment, date_of_birth, birth_location, birth_comment,
                         date_of_death, death_location, death_comment, profession,
                         marriage_date, marriage_location, marriage_comment)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        individual['name'],
                        individual.get('name_comment'),
                        individual.get('date_of_birth'),
                        individual.get('birth_location'),
                        individual.get('birth_comment'),
                        individual.get('date_of_death'),
                        individual.get('death_location'),
                        individual.get('death_comment'),
                        individual.get('profession'),
                        individual.get('marriage_date'),
                        individual.get('marriage_location'),
                        individual.get('marriage_comment')
                    ))
                    individual_id = cursor.lastrowid
                else:
                    # Found matching individual - merge data and track it
                    merged_individuals.append({
                        'individual_id': individual_id,
                        'name': individual['name'],
                        'family_tree': family_tree,
                        'old_id': old_id
                    })

                    cursor.execute('''
                        SELECT canonical_name FROM individuals WHERE id = ?
                    ''', (individual_id,))
                    existing_name = cursor.fetchone()[0]

                    # Prefer longer name
                    if len(individual['name']) > len(existing_name):
                        cursor.execute('''
                            UPDATE individuals SET canonical_name = ? WHERE id = ?
                        ''', (individual['name'], individual_id))

                # Create tree instance
                cursor.execute('''
                    INSERT INTO individual_tree_instances
                    (individual_id, family_tree, old_id, name_variant, source_file)
                    VALUES (?, ?, ?, ?, ?)
                ''', (individual_id, family_tree, old_id, individual['name'], individual['source_file']))

            # Record the source file for canonical individual
            cursor.execute('''
                INSERT OR IGNORE INTO individual_sources (individual_id, source_file)
                VALUES (?, ?)
            ''', (individual_id, individual['source_file']))

            # Track mapping for relationship inference
            tree_instance_map[tree_key] = individual_id
            individuals_dict[tree_key] = {
                'individual_id': individual_id,
                'old_id': old_id,
                'family_tree': family_tree,
                **individual
            }

        except Exception as e:
            print(f"Error processing individual {individual.get('name')}: {e}")
            import traceback
            traceback.print_exc()

    conn.commit()

    # Infer and store relationships
    relationships = infer_relationships(individuals_dict, tree_instance_map)
    print(f"\nInferred {len(relationships)} relationships")

    for rel in relationships:
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO relationships (parent_id, child_id, relationship_type, family_tree)
                VALUES (?, ?, ?, ?)
            ''', (rel['parent_id'], rel['child_id'], rel['relationship_type'], rel['family_tree']))
        except Exception as e:
            print(f"Error inserting relationship: {e}")

    conn.commit()

    # Get count of unique canonical individuals
    cursor.execute('SELECT COUNT(*) FROM individuals')
    num_individuals = cursor.fetchone()[0]

    # Get count of tree instances
    cursor.execute('SELECT COUNT(*) FROM individual_tree_instances')
    num_instances = cursor.fetchone()[0]

    conn.close()

    return num_individuals, num_instances, len(relationships), merged_individuals, warning_count


if __name__ == "__main__":
    folder_path = os.environ.get('GENEALOGY_DATA_DIR', 'data/sources')
    db_name = 'data/genealogy.db'

    print("Creating database...")
    create_database(db_name)

    print(f"\nParsing documents from {folder_path}...")
    clear_date_warnings()  # Clear any previous warnings
    individuals = parse_documents(folder_path)

    print(f"\nTotal individuals found: {len(individuals)}")

    print("\nStoring data in database...")
    num_individuals, num_relationships = store_data(individuals, db_name)

    print(f"\nComplete!")
    print(f"  Stored {num_individuals} unique individuals")
    print(f"  Stored {num_relationships} relationships")

    # Display accumulated date warnings
    warnings_list = get_date_warnings()
    if warnings_list:
        print(f"\n{'='*80}")
        print(
            f"DATE INCONSISTENCY WARNINGS: {len(warnings_list)} issue(s) found")
        print(f"{'='*80}")
        for i, warning in enumerate(warnings_list, 1):
            print(f"\n{i}. {warning['event_type'].upper()} date mismatch:")
            print(f"   File: {warning['file']}")
            print(f"   Person: {warning['person']}")
            print(
                f"   Gregorian: '{warning['gregorian_original']}' → {warning['gregorian_iso']}")
            print(
                f"   Revolutionary: '{warning['revolutionary_original']}' → {warning['revolutionary_iso']}")
            print(f"   Resolution: Using Gregorian date")
        print(f"\n{'='*80}")
