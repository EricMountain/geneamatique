import os
import sqlite3
import re
from odf.opendocument import load
from odf.text import P
from odf.table import Table, TableRow, TableCell


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
        date_of_death TEXT,
        profession TEXT,
        marriage_date TEXT
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


def parse_individual_data(cell_text):
    """Parse individual data from cell text.

    Format examples (anonymized):
    Multi-line format:
    2. PERSON_A Sample Name
    ° 4 Jan 1952 in City A
    + 15 Oct 2007 in City B
    PR Technician
    X 28 Jul 1973 in City C
    
    Single-line format:
    5. PERSON_B Sample Name° 18 Feb 1917 in City D+ 2 Jul 2015PR Tailor
    """
    if not cell_text or not cell_text.strip():
        return None

    # First, normalize the text by inserting newlines before special markers if they're on the same line
    # This handles cases where all data is concatenated without proper line breaks
    text = cell_text.strip()
    # Insert newlines before °, +, PR, X markers (but not at the start of string)
    text = re.sub(r'([^\n])°', r'\1\n°', text)
    text = re.sub(r'([^\n])\+', r'\1\n+', text)
    text = re.sub(r'([^\n])PR', r'\1\nPR', text)
    text = re.sub(r'([^\n])X\s', r'\1\nX ', text)

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
    date_of_birth = None
    date_of_death = None
    profession = None
    marriage_date = None

    for line in lines[1:]:
        if line.startswith('°'):
            date_of_birth = line[1:].strip()
        elif line.startswith('+'):
            date_of_death = line[1:].strip()
        elif line.startswith('PR'):
            profession = line[2:].strip()
        elif line.startswith('X'):
            marriage_date = line[1:].strip()

    return {
        'old_id': old_id,
        'name': name,
        'date_of_birth': date_of_birth,
        'date_of_death': date_of_death,
        'profession': profession,
        'marriage_date': marriage_date
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
    """Parse all ODT documents in the folder."""
    all_individuals = []

    if not os.path.exists(folder_path):
        print(f"Folder not found: {folder_path}")
        return all_individuals

    for filename in sorted(os.listdir(folder_path)):
        if filename.endswith('.odt') and not filename.startswith('tableau vide'):
            filepath = os.path.join(folder_path, filename)
            print(f"Parsing {filename}...")
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
            cursor.execute('SELECT id, name, date_of_birth, date_of_death, profession, marriage_date FROM individuals WHERE old_id = ?',
                          (individual['old_id'],))
            existing = cursor.fetchone()
            
            if existing:
                # Person exists - merge data
                db_id = existing[0]
                existing_name = existing[1]
                
                # Prefer the longer/more complete name
                new_name = individual['name']
                if len(new_name) > len(existing_name):
                    cursor.execute('UPDATE individuals SET name = ? WHERE id = ?', (new_name, db_id))
                
                # Update fields with non-null/non-empty values if current value is null or empty
                if individual['date_of_birth']:
                    cursor.execute('UPDATE individuals SET date_of_birth = ? WHERE id = ? AND (date_of_birth IS NULL OR date_of_birth = "")',
                                   (individual['date_of_birth'], db_id))
                if individual['date_of_death']:
                    cursor.execute('UPDATE individuals SET date_of_death = ? WHERE id = ? AND (date_of_death IS NULL OR date_of_death = "")',
                                   (individual['date_of_death'], db_id))
                if individual['profession']:
                    cursor.execute('UPDATE individuals SET profession = ? WHERE id = ? AND (profession IS NULL OR profession = "")',
                                   (individual['profession'], db_id))
                if individual['marriage_date']:
                    cursor.execute('UPDATE individuals SET marriage_date = ? WHERE id = ? AND (marriage_date IS NULL OR marriage_date = "")',
                                   (individual['marriage_date'], db_id))
            else:
                # New person - insert
                cursor.execute('''
                INSERT INTO individuals 
                (old_id, name, date_of_birth, date_of_death, profession, marriage_date)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    individual['old_id'],
                    individual['name'],
                    individual['date_of_birth'],
                    individual['date_of_death'],
                    individual['profession'],
                    individual['marriage_date']
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
    folder_path = os.environ.get('GENEALOGY_DATA_DIR', 'data/odt')
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
