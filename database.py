# database.py
import sqlite3
import pandas as pd
import os

db_name = 'cell_counts.db'

def init_database():
    # remove database if it already exists in folder
    if os.path.exists(db_name):
        os.remove(db_name)
        print(f"Existing database '{db_name}' removed.")

    """Initializes the SQLite database with the defined schema."""
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Create projects table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            project_id TEXT PRIMARY KEY
        )
    ''')

    # Create subjects table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subjects (
            subject_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            age INTEGER,
            sex TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        )
    ''')

    # Create samples table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS samples (
            sample_id TEXT PRIMARY KEY,
            subject_id TEXT NOT NULL,
            condition TEXT,
            treatment TEXT,
            response TEXT,
            sample_type TEXT,
            time_from_treatment_start INTEGER,
            FOREIGN KEY (subject_id) REFERENCES subjects(subject_id)
        )
    ''')

    # Create cell_counts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cell_counts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sample_id TEXT NOT NULL,
            population TEXT NOT NULL,
            count INTEGER NOT NULL,
            FOREIGN KEY (sample_id) REFERENCES samples(sample_id),
            UNIQUE (sample_id, population) -- Ensure one entry per population per sample
        )
    ''')

    conn.commit()
    conn.close()
    print(f"Database '{db_name}' initialized successfully.")

def load_data_from_csv(csv_filepath):
    """Loads data from a CSV file into the database."""
    init_database() # Ensure database is initialized
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    df = pd.read_csv(csv_filepath)

    # List of cell population columns
    cell_cols = ['b_cell', 'cd8_t_cell', 'cd4_t_cell', 'nk_cell', 'monocyte']

    for index, row in df.iterrows():
        # Insert into projects (INSERT OR IGNORE to handle duplicates)
        cursor.execute("INSERT OR IGNORE INTO projects (project_id) VALUES (?)", (row['project'],))

        # Insert into subjects (INSERT OR IGNORE to handle duplicates)
        cursor.execute("INSERT OR IGNORE INTO subjects (subject_id, project_id, age, sex) VALUES (?, ?, ?, ?)",
                       (row['subject'], row['project'], row['age'], row['sex']))

        # Insert into samples
        cursor.execute("INSERT INTO samples (sample_id, subject_id, condition, treatment, response, sample_type, time_from_treatment_start) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (row['sample'], row['subject'], row['condition'], row['treatment'], row['response'], row['sample_type'], row['time_from_treatment_start']))

        # Insert into cell_counts for each cell population
        for col in cell_cols:
            cursor.execute("INSERT INTO cell_counts (sample_id, population, count) VALUES (?, ?, ?)",
                           (row['sample'], col, row[col]))

    conn.commit()
    conn.close()
    print(f"Data from '{csv_filepath}' loaded successfully into '{db_name}'.")

def add_sample(sample_data):
    """Adds a single sample and its cell counts to the database.
    sample_data should be a dictionary matching the CSV row structure."""
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Extract common data
    project = sample_data['project']
    subject = sample_data['subject']
    sample = sample_data['sample']
    condition = sample_data['condition']
    treatment = sample_data['treatment']
    response = sample_data['response']
    sample_type = sample_data['sample_type']
    time_from_treatment_start = sample_data['time_from_treatment_start']
    age = sample_data['age']
    sex = sample_data['sex']

    population = ['b_cell', 'cd8_t_cell', 'cd4_t_cell', 'nk_cell', 'monocyte']

    try:
        cursor.execute("INSERT OR IGNORE INTO projects (project_id) VALUES (?)", (project,))
        cursor.execute("INSERT OR IGNORE INTO subjects (subject_id, project_id, age, sex) VALUES (?, ?, ?, ?)",
                       (subject, project, age, sex))
        cursor.execute("INSERT INTO samples (sample_id, subject_id, condition, treatment, response, sample_type, time_from_treatment_start) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (sample, subject, condition, treatment, response, sample_type, time_from_treatment_start))

        for col in population:
            cursor.execute("INSERT INTO cell_counts (sample_id, population, count) VALUES (?, ?, ?)",
                           (sample, col, sample_data[col]))
        conn.commit()
        print(f"Sample '{sample}' added successfully.")
    except sqlite3.IntegrityError as e:
        print(f"Error adding sample '{sample}': {e}. It might already exist or there's a foreign key violation.")
        conn.rollback()
    finally:
        conn.close()

def remove_sample(sample_id):
    """Removes a sample and its associated cell counts from the database."""
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    try:
        # Delete cell counts first due to foreign key constraint
        cursor.execute("DELETE FROM cell_counts WHERE sample_id = ?", (sample_id,))
        # Then delete the sample itself
        cursor.execute("DELETE FROM samples WHERE sample_id = ?", (sample_id,))
        conn.commit()
        if cursor.rowcount > 0:
            print(f"Sample '{sample_id}' and its cell counts removed successfully.")
        else:
            print(f"Sample '{sample_id}' not found.")
    except sqlite3.Error as e:
        print(f"Error removing sample '{sample_id}': {e}")
        conn.rollback()
    finally:
        conn.close()

def fetch_all_data():
    """Fetches all raw data joined from the database."""
    conn = sqlite3.connect(db_name)
    query = """
    SELECT
        p.project_id,
        s.subject_id,
        s.age,
        s.sex,
        sam.sample_id,
        sam.condition,
        sam.treatment,
        sam.response,
        sam.sample_type,
        sam.time_from_treatment_start,
        cc.population,
        cc.count
    FROM
        projects p
    JOIN
        subjects s ON p.project_id = s.project_id
    JOIN
        samples sam ON s.subject_id = sam.subject_id
    JOIN
        cell_counts cc ON sam.sample_id = cc.sample_id
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def fetch_samples_with_subject_info():
    """Fetches sample and subject information for analysis."""
    conn = sqlite3.connect(db_name)
    query = """
    SELECT
        sam.sample_id,
        sam.condition,
        sam.treatment,
        sam.response,
        sam.sample_type,
        sam.time_from_treatment_start,
        s.subject_id,
        s.age,
        s.sex,
        p.project_id
    FROM
        samples sam
    JOIN
        subjects s ON sam.subject_id = s.subject_id
    JOIN
        projects p ON s.project_id = p.project_id
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def fetch_cell_counts():
    """Fetches all cell counts."""
    conn = sqlite3.connect(db_name)
    query = "SELECT sample_id, population, count FROM cell_counts"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df