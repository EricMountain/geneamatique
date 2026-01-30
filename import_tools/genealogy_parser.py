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


def create_database(db_name='data/genealogy.db'):
    """Create the SQLite database with proper schema."""
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Drop existing tables to start fresh
    cursor.execute('DROP TABLE IF EXISTS relationships')
    cursor.execute('DROP TABLE IF EXISTS individual_sources')
    cursor.execute('DROP TABLE IF EXISTS individuals')

    cursor.execute('''
    CREATE TABLE individuals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        old_id INTEGER UNIQUE,
        name TEXT NOT NULL,
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

    cursor.execute('''
    CREATE TABLE relationships (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        parent_id INTEGER,
        child_id INTEGER,
        relationship_type TEXT,
        FOREIGN KEY (parent_id) REFERENCES individuals(id),
        FOREIGN KEY (child_id) REFERENCES individuals(id),
        UNIQUE(parent_id, child_id, relationship_type)
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


def parse_event_details(text_after_marker, event_type='birth'):
    """Parse event details (date, location, comment) from text after a marker.
    
    Args:
        text_after_marker: Text after ° (birth), + (death), or X (marriage) marker
        event_type: Type of event for better error messages
    
    Returns:
        dict with 'date', 'location', 'comment' keys (all ISO8601 format for dates)
    """
    if not text_after_marker:
        return {'date': None, 'location': None, 'comment': None}
    
    text = text_after_marker.strip()
    date_iso = None
    location = None
    comment = None
    
    # French Revolutionary calendar month names
    fr_months = ['vendémiaire', 'brumaire', 'frimaire', 'nivôse', 'pluviôse', 'ventôse',
                 'germinal', 'floréal', 'prairial', 'messidor', 'thermidor', 'fructidor']
    
    # Try to match a date at the beginning
    # Gregorian date patterns: "4 Jan 1952", "04/01/1952", "1952-01-04"
    gregorian_patterns = [
        r'^(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+(\d{4})',
        r'^(\d{1,2})/(\d{1,2})/(\d{4})',
        r'^(\d{4})-(\d{1,2})-(\d{1,2})'
    ]
    
    # Try to match French Revolutionary date at the beginning (not in parentheses)
    fr_pattern = r'^(\d{1,2})\s+(' + '|'.join(fr_months) + r')\s+(?:an\s+)?(\w+)'
    fr_match = re.match(fr_pattern, text, re.IGNORECASE)
    
    gregorian_date = None
    remaining_text = text
    
    if fr_match:
        # Found French Revolutionary date at start
        try:
            date_iso = parse_french_revolutionary_date(fr_match.group(0))
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
        is_fr_date = any(month in potential_fr_date.lower() for month in fr_months)
        
        if is_fr_date:
            try:
                fr_date_iso = parse_french_revolutionary_date(potential_fr_date)
                if gregorian_date and date_iso:
                    # Both dates present - check consistency
                    if fr_date_iso != date_iso:
                        warnings.warn(f"Date inconsistency in {event_type}: Gregorian={date_iso}, Revolutionary={fr_date_iso}. Using Gregorian.")
                elif not date_iso:
                    # Only Revolutionary date present (in parentheses)
                    date_iso = fr_date_iso
                # Remove the French Revolutionary date from remaining text
                remaining_text = remaining_text[:fr_date_match.start()] + remaining_text[fr_date_match.end():]
                remaining_text = remaining_text.strip()
            except Exception as e:
                # If FR date parsing fails, just ignore it
                pass
    
    if not date_iso:
        # No date found - entire text becomes comment
        return {'date': None, 'location': None, 'comment': text}
    
    # Extract location (look for "à" or "au" after date)
    # Use a more careful pattern that doesn't consume the parenthesis
    location_match = re.match(r'^(?:à|au)\s+([^(]+?)(?=\s*\(|$)', remaining_text, re.IGNORECASE)
    if location_match:
        location = location_match.group(1).strip()
        remaining_text = remaining_text[location_match.end():].strip()
    
    # Extract comment in parentheses
    comment_match = re.search(r'\(([^)]+)\)', remaining_text)
    if comment_match:
        comment = comment_match.group(1).strip()
    
    return {'date': date_iso, 'location': location, 'comment': comment}


def parse_date_to_iso(date_str):
    """Convert various date formats to ISO8601 (YYYY-MM-DD)."""
    date_str = date_str.strip()
    
    # Map month names to numbers
    month_map_en = {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12}
    month_map_fr = {'janvier': 1, 'février': 2, 'mars': 3, 'avril': 4, 'mai': 5, 'juin': 6,
                    'juillet': 7, 'août': 8, 'septembre': 9, 'octobre': 10, 'novembre': 11, 'décembre': 12}
    
    # Try "4 Jan 1952" format
    match = re.match(r'^(\d{1,2})\s+(\w+)\s+(\d{4})$', date_str, re.IGNORECASE)
    if match:
        day = int(match.group(1))
        month_str = match.group(2).lower()[:3]
        year = int(match.group(3))
        month = month_map_en.get(month_str) or month_map_fr.get(match.group(2).lower())
        if month:
            return f"{year:04d}-{month:02d}-{day:02d}"
    
    # Try "04/01/1952" format (DD/MM/YYYY)
    match = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', date_str)
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
    match = re.match(r'(\d{1,2})\s+(\w+)\s+(?:an\s+)?(\w+)', fr_date_str, re.IGNORECASE)
    if not match:
        raise ValueError(f"Could not parse French Revolutionary date: {fr_date_str}")
    
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


def parse_individual_data(cell_text):
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
    name = match.group(2).strip()

    # Parse other fields
    birth_details = {'date': None, 'location': None, 'comment': None}
    death_details = {'date': None, 'location': None, 'comment': None}
    marriage_details = {'date': None, 'location': None, 'comment': None}
    profession = None

    for line in lines[1:]:
        if line.startswith('°'):
            birth_details = parse_event_details(line[1:].strip(), 'birth')
        elif line.startswith('+'):
            death_details = parse_event_details(line[1:].strip(), 'death')
        elif line.startswith('PR'):
            profession = line[2:].strip()
        elif line.startswith('X'):
            marriage_details = parse_event_details(line[1:].strip(), 'marriage')

    return {
        'old_id': old_id,
        'name': name,
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


def parse_document(filepath):
    """Parse a single ODT document and extract all individuals."""
    individuals = []

    try:
        doc = load(filepath)
        tables = doc.getElementsByType(Table)

        for table in tables:
            rows = table.getElementsByType(TableRow)
            for row in rows:
                cells = row.getElementsByType(TableCell)
                for cell in cells:
                    cell_text = get_cell_text(cell)
                    individual = parse_individual_data(cell_text)
                    if individual:
                        individual['source_file'] = os.path.basename(filepath)
                        individuals.append(individual)
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")

    return individuals


def parse_documents(folder_path):
    """Parse all ODT documents in the folder and subfolders."""
    all_individuals = []

    if not os.path.exists(folder_path):
        print(f"Folder not found: {folder_path}")
        return all_individuals

    for root, dirs, files in os.walk(folder_path):
        for filename in sorted(files):
            if filename.endswith('.odt') and not filename.startswith('tableau vide'):
                filepath = os.path.join(root, filename)
                print(f"Parsing {os.path.relpath(filepath, folder_path)}...")
                individuals = parse_document(filepath)
                all_individuals.extend(individuals)
                print(f"  Found {len(individuals)} individuals")

    return all_individuals


def infer_relationships(individuals_dict):
    """Infer parent-child relationships based on old_id numbering.

    In genealogy numbering:
    - Each person has an ID
    - Their parents have IDs that are 2*ID and 2*ID+1
    - Even IDs are typically male, odd IDs are female
    """
    relationships = []

    # Create a lookup by old_id
    id_lookup = {}
    for db_id, individual in individuals_dict.items():
        old_id = individual['old_id']
        if old_id not in id_lookup:
            id_lookup[old_id] = []
        id_lookup[old_id].append(db_id)

    # Find parent-child relationships
    for db_id, individual in individuals_dict.items():
        old_id = individual['old_id']

        # Parents would have IDs of 2*old_id and 2*old_id+1
        father_id = 2 * old_id
        mother_id = 2 * old_id + 1

        if father_id in id_lookup:
            for parent_db_id in id_lookup[father_id]:
                relationships.append({
                    'parent_id': parent_db_id,
                    'child_id': db_id,
                    'relationship_type': 'father'
                })

        if mother_id in id_lookup:
            for parent_db_id in id_lookup[mother_id]:
                relationships.append({
                    'parent_id': parent_db_id,
                    'child_id': db_id,
                    'relationship_type': 'mother'
                })

    return relationships


def store_data(individuals, db_name='data/genealogy.db'):
    """Store parsed individuals and inferred relationships in the database.

    Merges individuals by old_id, preferring longer/more complete names and
    accumulating data from all sources.
    """
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Store individuals and keep track of their database IDs
    individuals_dict = {}
    for individual in individuals:
        try:
            # Check if this old_id already exists
            cursor.execute('''SELECT id, name, date_of_birth, birth_location, birth_comment,
                             date_of_death, death_location, death_comment, profession,
                             marriage_date, marriage_location, marriage_comment
                             FROM individuals WHERE old_id = ?''',
                           (individual['old_id'],))
            existing = cursor.fetchone()

            if existing:
                # Person exists - merge data
                db_id = existing[0]
                existing_name = existing[1]

                # Prefer the longer/more complete name
                new_name = individual['name']
                if len(new_name) > len(existing_name):
                    cursor.execute(
                        'UPDATE individuals SET name = ? WHERE id = ?', (new_name, db_id))

                # Update fields with non-null/non-empty values if current value is null or empty
                if individual['date_of_birth']:
                    cursor.execute('UPDATE individuals SET date_of_birth = ? WHERE id = ? AND (date_of_birth IS NULL OR date_of_birth = "")',
                                   (individual['date_of_birth'], db_id))
                if individual['birth_location']:
                    cursor.execute('UPDATE individuals SET birth_location = ? WHERE id = ? AND (birth_location IS NULL OR birth_location = "")',
                                   (individual['birth_location'], db_id))
                if individual['birth_comment']:
                    cursor.execute('UPDATE individuals SET birth_comment = ? WHERE id = ? AND (birth_comment IS NULL OR birth_comment = "")',
                                   (individual['birth_comment'], db_id))
                if individual['date_of_death']:
                    cursor.execute('UPDATE individuals SET date_of_death = ? WHERE id = ? AND (date_of_death IS NULL OR date_of_death = "")',
                                   (individual['date_of_death'], db_id))
                if individual['death_location']:
                    cursor.execute('UPDATE individuals SET death_location = ? WHERE id = ? AND (death_location IS NULL OR death_location = "")',
                                   (individual['death_location'], db_id))
                if individual['death_comment']:
                    cursor.execute('UPDATE individuals SET death_comment = ? WHERE id = ? AND (death_comment IS NULL OR death_comment = "")',
                                   (individual['death_comment'], db_id))
                if individual['profession']:
                    cursor.execute('UPDATE individuals SET profession = ? WHERE id = ? AND (profession IS NULL OR profession = "")',
                                   (individual['profession'], db_id))
                if individual['marriage_date']:
                    cursor.execute('UPDATE individuals SET marriage_date = ? WHERE id = ? AND (marriage_date IS NULL OR marriage_date = "")',
                                   (individual['marriage_date'], db_id))
                if individual['marriage_location']:
                    cursor.execute('UPDATE individuals SET marriage_location = ? WHERE id = ? AND (marriage_location IS NULL OR marriage_location = "")',
                                   (individual['marriage_location'], db_id))
                if individual['marriage_comment']:
                    cursor.execute('UPDATE individuals SET marriage_comment = ? WHERE id = ? AND (marriage_comment IS NULL OR marriage_comment = "")',
                                   (individual['marriage_comment'], db_id))
            else:
                # New person - insert
                cursor.execute('''
                INSERT INTO individuals 
                (old_id, name, date_of_birth, birth_location, birth_comment,
                 date_of_death, death_location, death_comment, profession,
                 marriage_date, marriage_location, marriage_comment)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    individual['old_id'],
                    individual['name'],
                    individual['date_of_birth'],
                    individual['birth_location'],
                    individual['birth_comment'],
                    individual['date_of_death'],
                    individual['death_location'],
                    individual['death_comment'],
                    individual['profession'],
                    individual['marriage_date'],
                    individual['marriage_location'],
                    individual['marriage_comment']
                ))
                db_id = cursor.lastrowid

            # Record the source file
            cursor.execute('''
            INSERT OR IGNORE INTO individual_sources (individual_id, source_file)
            VALUES (?, ?)
            ''', (db_id, individual['source_file']))

            individuals_dict[db_id] = individual

        except Exception as e:
            print(f"Error inserting individual {individual.get('name')}: {e}")

    conn.commit()

    # Infer and store relationships
    relationships = infer_relationships(individuals_dict)
    print(f"\nInferred {len(relationships)} relationships")

    for rel in relationships:
        try:
            cursor.execute('''
            INSERT OR IGNORE INTO relationships (parent_id, child_id, relationship_type)
            VALUES (?, ?, ?)
            ''', (rel['parent_id'], rel['child_id'], rel['relationship_type']))
        except Exception as e:
            print(f"Error inserting relationship: {e}")

    conn.commit()
    conn.close()

    return len(individuals_dict), len(relationships)


if __name__ == "__main__":
    folder_path = os.environ.get('GENEALOGY_DATA_DIR', 'data/sources')
    db_name = 'data/genealogy.db'

    print("Creating database...")
    create_database(db_name)

    print(f"\nParsing documents from {folder_path}...")
    individuals = parse_documents(folder_path)

    print(f"\nTotal individuals found: {len(individuals)}")

    print("\nStoring data in database...")
    num_individuals, num_relationships = store_data(individuals, db_name)

    print(f"\nComplete!")
    print(f"  Stored {num_individuals} unique individuals")
    print(f"  Stored {num_relationships} relationships")
