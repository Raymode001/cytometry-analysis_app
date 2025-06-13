# database.py
import sqlite3
import pandas as pd
import os

db_name = 'cell_counts.db'

def get_db_connection():
    """Establishes and returns a connection to the SQLite database."""
    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row # Allows accessing columns by name
    return conn

def init_database():
    # remove database if it already exists in folder
    if os.path.exists(db_name):
        os.remove(db_name)
        print(f"Existing database '{db_name}' removed.")

    """Initializes the SQLite database with the defined schema."""
    conn = get_db_connection()
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
            FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
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
            FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE
        )
    ''')

    # Create cell_counts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cell_counts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sample_id TEXT NOT NULL,
            population TEXT NOT NULL,
            count INTEGER NOT NULL,
            FOREIGN KEY (sample_id) REFERENCES samples(sample_id) ON DELETE CASCADE,
            UNIQUE (sample_id, population) -- Ensure one entry per population per sample
        )
    ''')

    conn.commit()
    conn.close()
    print(f"Database '{db_name}' initialized successfully.")

# New: Generic bulk add function to replace load_data_from_csv and add_sample
def bulk_add_data(conn, df: pd.DataFrame):
    """
    Adds/updates data from a DataFrame into the database.
    Handles inserting projects, subjects, samples, and cell counts.
    Uses INSERT OR IGNORE for projects and subjects to avoid duplicates.
    Uses INSERT OR REPLACE for samples and cell_counts to handle updates to existing
    samples or new sample additions with existing IDs.
    """
    cursor = conn.cursor()

    # List of cell population columns
    cell_cols = ['b_cell', 'cd8_t_cell', 'cd4_t_cell', 'nk_cell', 'monocyte']

    # Handle potential None/NaN values for integer columns before iterrows
    for col in ['age', 'time_from_treatment_start'] + cell_cols:
        if col in df.columns:
            # Ensure numeric conversion and fill NaNs with 0, then convert to int
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int) 

    # Ensure 'response' column handles None properly (if it's not a mandatory field)
    if 'response' in df.columns:
        df['response'] = df['response'].astype(str).replace({'None': None, 'nan': None, '': None})


    for index, row in df.iterrows():
        try:
            # Insert into projects (INSERT OR IGNORE to handle duplicates)
            cursor.execute("INSERT OR IGNORE INTO projects (project_id) VALUES (?)", (row['project'],))

            # Insert into subjects (INSERT OR IGNORE to handle duplicates)
            # Ensure project_id is correctly mapped from 'project' column
            cursor.execute("INSERT OR IGNORE INTO subjects (subject_id, project_id, age, sex) VALUES (?, ?, ?, ?)",
                           (row['subject'], row['project'], row['age'], row['sex']))

            # Insert into samples (INSERT OR REPLACE to update if sample_id exists)
            # This handles both new sample insertion and updates if sample_id is provided in the new data
            cursor.execute("""
                INSERT OR REPLACE INTO samples
                (sample_id, subject_id, condition, treatment, response, sample_type, time_from_treatment_start)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (row['sample'], row['subject'], row['condition'], row['treatment'],
                  row['response'], row['sample_type'], row['time_from_treatment_start']))

            # Insert into cell_counts for each cell population (INSERT OR REPLACE)
            # This handles both new cell counts and updates to existing ones for a given sample_id and population
            for col in cell_cols:
                # Ensure count is not None or NaN before insertion
                count_val = row[col] if pd.notna(row[col]) else 0
                cursor.execute("""
                    INSERT OR REPLACE INTO cell_counts
                    (sample_id, population, count)
                    VALUES (?, ?, ?)
                """, (row['sample'], col, count_val))
            conn.commit() # Commit each row to make transaction smaller or commit at the end of the loop if preferred for performance
        except sqlite3.IntegrityError as e:
            # This will catch issues like non-existent project_id or subject_id if not handled by INSERT OR IGNORE
            print(f"Integrity Error for row {row.get('sample', 'N/A')}: {e}")
            conn.rollback() # Rollback the current transaction for this row
            raise # Re-raise to let the app callback handle the error
        except Exception as e:
            print(f"Error processing row {row.get('sample', 'N/A')}: {e}")
            conn.rollback()
            raise


# New: Bulk delete function
def bulk_delete_samples(conn, sample_ids: list):
    """
    Removes multiple samples and their associated cell counts from the database.
    Returns the number of samples successfully deleted.
    """
    cursor = conn.cursor()
    deleted_count = 0
    try:
        for sample_id in sample_ids:
            # Delete cell counts first due to foreign key constraint
            cursor.execute("DELETE FROM cell_counts WHERE sample_id = ?", (sample_id,))
            # Then delete the sample itself
            cursor.execute("DELETE FROM samples WHERE sample_id = ?", (sample_id,))
            if cursor.rowcount > 0:
                deleted_count += 1
        conn.commit()
        return deleted_count
    except sqlite3.Error as e:
        print(f"Error removing samples: {e}")
        conn.rollback()
        raise # Re-raise to let the app callback handle the error


# New: Helper to get subject_id from sample_id
def get_subject_id_from_sample_id(conn, sample_id):
    cursor = conn.cursor()
    cursor.execute("SELECT subject_id FROM samples WHERE sample_id = ?", (sample_id,))
    result = cursor.fetchone()
    return result[0] if result else None


# New: Update functions for in-table editing
def update_subject_fields(conn, subject_id, updates_dict):
    """
    Updates fields in the subjects table for a given subject_id.
    Handles mapping 'project' from updates_dict to 'project_id' in the DB.
    """
    if not updates_dict:
        return
    
    set_clauses = []
    values = []
    
    # Process project_id separately as its column name in DB is 'project_id', not 'project'
    if 'project' in updates_dict:
        new_project_id = updates_dict['project']
        set_clauses.append("project_id = ?")
        values.append(new_project_id)
        # Ensure the new project_id exists in the projects table
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO projects (project_id) VALUES (?)", (new_project_id,))

    # Process other fields relevant to the subjects table
    subject_table_cols = ['age', 'sex'] # These map directly
    for k, v in updates_dict.items():
        if k in subject_table_cols:
            set_clauses.append(f"{k} = ?")
            values.append(v)
    
    if not set_clauses: # No valid updates for this table
        return

    values.append(subject_id) # Add subject_id for the WHERE clause

    query = f"UPDATE subjects SET {', '.join(set_clauses)} WHERE subject_id = ?"
    cursor = conn.cursor()
    cursor.execute(query, values)
    # No commit here, will commit in the calling app callback after all updates for a sample are done

def update_sample_fields(conn, sample_id, updates_dict):
    """Updates fields in the samples table for a given sample_id."""
    if not updates_dict:
        return
    
    # Filter for fields relevant to the samples table
    sample_table_cols = ['condition', 'treatment', 'response', 'sample_type', 'time_from_treatment_start']
    valid_updates = {k: v for k, v in updates_dict.items() if k in sample_table_cols}

    if not valid_updates:
        return

    set_clauses = [f"{k} = ?" for k in valid_updates.keys()]
    values = list(valid_updates.values())
    values.append(sample_id) # Add sample_id for the WHERE clause

    query = f"UPDATE samples SET {', '.join(set_clauses)} WHERE sample_id = ?"
    cursor = conn.cursor()
    cursor.execute(query, values)
    # No commit here

def update_cell_count(conn, sample_id, population_name, new_count):
    """Updates a specific cell population count for a given sample_id."""
    # Ensure new_count is an integer. Handle non-numeric input gracefully.
    try:
        new_count = int(float(new_count)) # Convert to float first to handle string numbers, then to int
    except (ValueError, TypeError):
        new_count = 0 # Default to 0 or handle error differently

    query = """
        INSERT OR REPLACE INTO cell_counts (sample_id, population, count)
        VALUES (?, ?, ?)
    """
    cursor = conn.cursor()
    cursor.execute(query, (sample_id, population_name, new_count))
    # No commit here


# The original `load_data_from_csv` is now effectively a wrapper around `bulk_add_data`.
def load_data_from_csv(csv_filepath):
    """Initializes DB and loads data from a CSV file into the database."""
    init_database() # Ensure database is initialized and clear
    conn = get_db_connection()
    try:
        df = pd.read_csv(csv_filepath)
        bulk_add_data(conn, df) # Use the new bulk_add_data function
        print(f"Data from '{csv_filepath}' loaded successfully into '{db_name}'.")
    except Exception as e:
        print(f"Error loading data from CSV: {e}")
    finally:
        conn.close()


# Original functions (kept for reference, might not be directly used by new app.py callbacks)
def fetch_all_data():
    """Fetches all raw data joined from the database."""
    conn = get_db_connection()
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
    conn = get_db_connection()
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
    conn = get_db_connection()
    query = "SELECT sample_id, population, count FROM cell_counts"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# Example usage (for testing database.py directly if needed)
if __name__ == '__main__':
    # Initialize the database (this will remove existing cell_counts.db)
    init_database()

    # Load data from a dummy CSV (replace 'your_data.csv' with an actual path if testing)
    try:
        load_data_from_csv('cell-count.csv') # Use your actual CSV here for initial load
    except FileNotFoundError:
        print("cell-count.csv not found. Skipping initial data loading.")
    except Exception as e:
        print(f"Error during initial data load: {e}")

    # Example of adding data using bulk_add_data
    conn = get_db_connection()
    try:
        dummy_df_add = pd.DataFrame([{
            'project': 'PTest', 'subject': 'STest1', 'condition': 'test_cond_add',
            'age': 30, 'sex': 'M', 'treatment': 'test_tr_add', 'response': 'y',
            'sample': 'S_TEST_001_NEW', 'sample_type': 'test_type_add', 'time_from_treatment_start': 0,
            'b_cell': 100, 'cd8_t_cell': 200, 'cd4_t_cell': 300, 'nk_cell': 400, 'monocyte': 500
        }])
        bulk_add_data(conn, dummy_df_add)
        print("Dummy data added via bulk_add_data.")
    except Exception as e:
        print(f"Error adding dummy data: {e}")
    finally:
        conn.close()

    # Example of updating data using the new update functions
    # Using an existing sample from cell-count.csv, e.g., 's1'
    conn = get_db_connection()
    try:
        # Get subject_id for sample 's1'
        subject_id_s1 = get_subject_id_from_sample_id(conn, 's1')
        if subject_id_s1:
            print(f"Updating data for sample 's1' (Subject ID: {subject_id_s1})...")
            update_subject_fields(conn, subject_id_s1, {'age': 71, 'sex': 'M', 'project': 'prj1_updated'}) # Update age, sex, and project
            update_sample_fields(conn, 's1', {'condition': 'melanoma_updated', 'response': 'n'}) # Update sample details
            update_cell_count(conn, 's1', 'b_cell', 37000) # Update a cell count
            conn.commit() # Commit at the end of a series of updates for one logical operation
            print("Sample 's1' data updated.")
        else:
            print("Sample 's1' not found for update example.")
    except Exception as e:
        print(f"Error updating sample 's1': {e}")
    finally:
        conn.close()


    # Example of deleting data using bulk_delete_samples
    conn = get_db_connection()
    try:
        # Delete the newly added dummy sample
        deleted_count = bulk_delete_samples(conn, ['S_TEST_001_NEW'])
        print(f"Deleted {deleted_count} dummy samples.")
    except Exception as e:
        print(f"Error deleting dummy data: {e}")
    finally:
        conn.close()

    # Fetch and display all data to verify
    print("\nAll data after operations:")
    all_data_df_verify = get_all_data_for_display() # Use the app's helper for wide data
    if not all_data_df_verify.empty:
        print(all_data_df_verify.head().to_markdown(index=False))
    else:
        print("No data in database.")