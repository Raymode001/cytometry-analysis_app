# app.py
import dash
from dash import dcc, html, Input, Output, State, dash_table
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
import os
import io
import base64
import math # Import math for ceil function


# Import your custom modules (ensure these files are in the same directory)
import database
import analysis
# import visualization # Removed as plotting is handled by Plotly directly in app.py


# --- Database Initialization and Data Loading ---
# This part ensures the database is ready when the app starts.
# It will remove any existing DB file for a clean start on each app launch (useful for development).
# For production, you might want a more sophisticated DB management strategy (e.g., migrations).
if os.path.exists(database.db_name):
    os.remove(database.db_name)
    print(f"Existing database '{database.db_name}' removed for a clean start.")
database.init_database()
database.load_data_from_csv('cell-count.csv')
print("Database initialized and data loaded successfully for Dash app.")


# --- Helper Function to Fetch All Data in Wide Format for DataTable ---
# This function is crucial as it provides the raw data in a wide format
# for the 'full-dataset-table' and as input for analysis functions.
def get_all_data_for_display():
    """
    Fetches all data from DB, pivots cell counts to columns, and returns a wide-format DataFrame.
    This structure is suitable for `dash_table.DataTable` and as input for analysis functions.
    Columns are renamed to match the original CSV headers for display consistency.
    The data is ordered by sample_id in a natural (alphanumeric then numeric) ascending order.
    """
    conn = database.get_db_connection()
    try:
        # Query to get all sample details and pivot cell counts into columns
        # ORDER BY is now using a natural sort for alphanumeric sample_ids
        query = """
        SELECT
            p.project_id AS project,
            s.subject_id AS subject,
            s.age,
            s.sex,
            samp.sample_id AS sample,
            samp.condition,
            samp.treatment,
            samp.response,
            samp.sample_type,
            samp.time_from_treatment_start,
            SUM(CASE WHEN cc.population = 'b_cell' THEN cc.count ELSE 0 END) AS b_cell,
            SUM(CASE WHEN cc.population = 'cd8_t_cell' THEN cc.count ELSE 0 END) AS cd8_t_cell,
            SUM(CASE WHEN cc.population = 'cd4_t_cell' THEN cc.count ELSE 0 END) AS cd4_t_cell,
            SUM(CASE WHEN cc.population = 'nk_cell' THEN cc.count ELSE 0 END) AS nk_cell,
            SUM(CASE WHEN cc.population = 'monocyte' THEN cc.count ELSE 0 END) AS monocyte
        FROM projects p
        JOIN subjects s ON p.project_id = s.project_id
        JOIN samples samp ON s.subject_id = samp.subject_id
        LEFT JOIN cell_counts cc ON samp.sample_id = cc.sample_id
        GROUP BY p.project_id, s.subject_id, s.age, s.sex, samp.sample_id, samp.condition,
                 samp.treatment, samp.response, samp.sample_type, samp.time_from_treatment_start
        ORDER BY
            SUBSTR(samp.sample_id, 1, 1) ASC,          -- Sorts by the prefix character (e.g., 's')
            CAST(SUBSTR(samp.sample_id, 2) AS INTEGER) ASC; -- Then by the numeric part as an integer
        """
        df = pd.read_sql_query(query, conn)
    except Exception as e:
        print(f"Error fetching data for display: {e}")
        return pd.DataFrame()
    finally:
        conn.close()
    return df

# --- Helper Function for Initial DataTable Columns ---
# This helper now ensures the 'sample' column is editable for user input.
def get_initial_table_columns():
    """
    Generates the initial column structure for the full-dataset-table,
    including editable properties and data types. 'sample' is now editable.
    """
    df = get_all_data_for_display() # Get current data to infer columns
    columns = []
    if not df.empty:
        for col in df.columns:
            col_type = 'text'
            if pd.api.types.is_numeric_dtype(df[col]):
                col_type = 'numeric'
            
            col_dict = {"name": col, "id": col, "editable": True, "type": col_type}
            # The 'sample' column is intentionally left as editable: True here
            columns.append(col_dict)
    else: # Fallback if DB is completely empty (e.g., first run before any data is loaded)
        columns = [
            {"name": "project", "id": "project", "editable": True},
            {"name": "subject", "id": "subject", "editable": True},
            {"name": "age", "id": "age", "editable": True, "type": "numeric"},
            {"name": "sex", "id": "sex", "editable": True},
            {"name": "sample", "id": "sample", "editable": True}, # NOW EDITABLE for new rows
            {"name": "condition", "id": "condition", "editable": True},
            {"name": "treatment", "id": "treatment", "editable": True},
            {"name": "response", "id": "response", "editable": True},
            {"name": "sample_type", "id": "sample_type", "editable": True},
            {"name": "time_from_treatment_start", "id": "time_from_treatment_start", "editable": True, "type": "numeric"},
            {"name": "b_cell", "id": "b_cell", "editable": True, "type": "numeric"},
            {"name": "cd8_t_cell", "id": "cd8_t_cell", "editable": True, "type": "numeric"},
            {"name": "cd4_t_cell", "id": "cd4_t_cell", "editable": True, "type": "numeric"},
            {"name": "nk_cell", "id": "nk_cell", "editable": True, "type": "numeric"},
            {"name": "monocyte", "id": "monocyte", "editable": True, "type": "numeric"},
        ]
    return columns


# --- Initialize the Dash app ---
app = dash.Dash(__name__,
                external_stylesheets=['https://cdn.tailwindcss.com']) # Use Tailwind for styling

# This line exposes the underlying Flask server to WSGI servers (like Gunicorn) for production deployment.
server = app.server

# --- Define the app layout ---
app.layout = html.Div(className='container mx-auto p-6 bg-gray-50 min-h-screen font-sans', children=[
    html.H1("Loblaw Bio: Cytometry Data Analysis Dashboard", className='text-4xl font-bold text-center text-gray-800 mb-8'),

    # --- Data Management Section ---
    html.Div(className='bg-white p-6 rounded-lg shadow-md mb-8', children=[
        html.H2("Data Management (Add/Remove/View Samples)", className='text-2xl font-semibold text-gray-700 mb-4'),

        # Section for adding multiple samples via CSV upload
        html.H3("Add Samples via CSV Upload", className='text-lg font-semibold text-gray-800 mt-4 mb-2'),
        dcc.Upload(
            id='upload-data',
            children=html.Div([
                'Drag and Drop or ',
                html.A('Select a CSV file')
            ]),
            style={
                'width': '100%', 'height': '60px', 'lineHeight': '60px',
                'borderWidth': '1px', 'borderStyle': 'dashed',
                'borderRadius': '5px', 'textAlign': 'center', 'margin': '10px 0'
            },
            multiple=False # Allow only one file at a time
        ),
        html.Div(id='output-upload-status', className='text-sm text-gray-600 mb-4'), # Status for CSV upload

        # Section for deleting samples (enhanced for multi-select)
        html.H3("Delete Samples", className='text-lg font-semibold text-gray-800 mt-6 mb-2'),
        # NEW LINE ADDED HERE for explicit instruction
        html.P("To delete samples by ID, enter one or more IDs separated by commas (e.g., s1, s2, s3).", className='text-sm text-gray-600 mb-2'),
        html.Div(className='flex items-center gap-2 mb-4', children=[
            dcc.Input(
                id='delete-sample-ids', # For comma-separated deletion
                type='text',
                placeholder='Enter sample IDs here', # Shorter placeholder now instruction is separate
                className='p-2 border border-gray-300 rounded-md flex-1'
            ),
            html.Button('Delete Samples by ID', id='delete-samples-by-id-button', n_clicks=0, # Specific button for ID deletion
                        className='bg-red-500 hover:bg-red-700 text-white font-bold py-2 px-4 rounded-md shadow-md transition duration-300 ease-in-out')
        ]),
        html.Div(id='output-delete-status', className='text-sm text-gray-600 mb-4'), # Status for delete operation

        # Section for viewing and editing the full dataset table (now also for single adds)
        html.H3("View/Edit Current Dataset", className='text-lg font-semibold text-gray-800 mt-6 mb-2'),
        html.Div(className='flex items-center gap-2 mb-4', children=[
            html.Button('Add New Row (Edit Below)', id='add-new-table-row-button', n_clicks=0,
                        className='bg-green-500 hover:bg-green-700 text-white font-bold py-2 px-4 rounded-md shadow-md transition duration-300 ease-in-out'),
            html.Button('Save Changes to Database', id='save-changes-button', n_clicks=0, # NEW SAVE BUTTON
                        className='bg-indigo-600 hover:bg-indigo-800 text-white font-bold py-2 px-4 rounded-md shadow-md transition duration-300 ease-in-out'),
            html.Button('Refresh Data Table', id='refresh-data-table-button', n_clicks=0,
                        className='bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded-md shadow-md transition duration-300 ease-in-out'),
            html.Button('Delete Selected Rows', id='delete-selected-rows-button', n_clicks=0,
                        className='bg-red-500 hover:bg-red-700 text-white font-bold py-2 px-4 rounded-md shadow-md transition duration-300 ease-in-out')
        ]),
        # UPDATED NOTE FOR REFRESH BEHAVIOR
        html.P("Note: Edit cells directly. Click 'Save Changes' to commit data to the database. 'Refresh Data Table' reloads from the database, discarding unsaved changes.", className='text-sm text-yellow-600 mb-4'),

        html.Div(id='data-table-container', children=[
            dash_table.DataTable(
                id='full-dataset-table',
                # SET INITIAL DATA AND COLUMNS HERE for automatic display on load:
                data=get_all_data_for_display().to_dict('records'), # Initial data from DB
                columns=get_initial_table_columns(), # Initial columns setup (now sample is editable)
                page_size=10, # Display 10 rows per page
                style_table={'overflowX': 'auto'}, # Allow horizontal scrolling
                style_cell={'textAlign': 'left', 'padding': '5px'},
                style_header={
                    'backgroundColor': 'rgb(230, 230, 230)',
                    'fontWeight': 'bold'
                },
                editable=True, # Allow direct in-table editing (all cells are editable by default per column def)
                row_deletable=True, # Allow deleting rows directly from the table UI (small X icon)
                row_selectable='multi', # Enable checkboxes for multi-row selection
                selected_rows=[], # Initial state for selected rows
            )
        ]),
        html.Div(id='output-table-edit-status', className='text-sm text-gray-600 mt-4 mb-4'), # Status for table edits/deletions via checkboxes

    ]),

    # --- Relative Frequencies Table ---
    html.Div(className='bg-white p-6 rounded-lg shadow-md mb-8', children=[
        html.H2("Relative Frequencies Summary", className='text-2xl font-semibold text-gray-700 mb-4'),
        html.Button('Refresh Relative Frequencies', id='refresh-data-button', n_clicks=0, className='bg-green-500 hover:bg-green-700 text-white font-bold py-2 px-4 rounded-md shadow-md transition duration-300 ease-in-out mb-4'),
        dash_table.DataTable(
            id='relative-frequencies-table',
            columns=[{"name": i, "id": i} for i in ['sample', 'total_count', 'population', 'count', 'percentage']], # Columns for long format
            # Initial data load: Get wide data, then pass to analysis.get_relative_frequency
            data=analysis.get_relative_frequency(get_all_data_for_display()).to_dict('records'),
            filter_action="native",
            sort_action="native",
            page_action="native",
            page_size=10,
            style_table={'overflowX': 'auto'},
            style_header={
                'backgroundColor': 'rgb(230, 230, 230)',
                'fontWeight': 'bold',
                'borderBottom': '3px solid #3B82F6',
                'textAlign': 'left',
                'padding': '12px 8px'
            },
            style_cell={
                'textAlign': 'left',
                'padding': '8px',
                'fontSize': '0.9rem',
                'fontFamily': 'Inter, sans-serif',
                'minWidth': '80px', 'width': '120px', 'maxWidth': '180px',
                'border': '1px solid #E5E7EB'
            },
            style_data_conditional=[
                {
                    'if': {'row_index': 'odd'},
                    'backgroundColor': 'rgb(248, 248, 248)'
                }
            ]
        )
    ]),

    # --- Response Comparison Analysis ---
    html.Div(className='bg-white p-6 rounded-lg shadow-md mb-8', children=[
        html.H2("Melanoma TR1 Response Analysis (PBMC)", className='text-2xl font-semibold text-gray-700 mb-4'),
        html.Button('Run Response Comparison', id='run-response-analysis-button', n_clicks=0, className='bg-indigo-500 hover:bg-indigo-700 text-white font-bold py-2 px-4 rounded-md shadow-md transition duration-300 ease-in-out mb-4'),
        html.Div(id='response-analysis-output', className='mt-4'),
        dcc.Loading(
            id="loading-response-plot",
            type="circle",
            children=html.Div(id='response-boxplot-container', className='flex flex-wrap justify-center gap-4')
        )
    ]),

    # --- Baseline Sample Queries ---
    html.Div(className='bg-white p-6 rounded-lg shadow-md mb-8', children=[
        html.H2("Baseline Melanoma TR1 Sample Queries", className='text-2xl font-semibold text-gray-700 mb-4'),
        html.Button('Run Baseline Queries', id='run-baseline-queries-button', n_clicks=0, className='bg-purple-500 hover:bg-purple-700 text-white font-bold py-2 px-4 rounded-md shadow-md transition duration-300 ease-in-out mb-4'),
        html.Div(id='baseline-queries-output', className='mt-4 text-sm font-medium text-gray-700')
    ])
])


# --- Callbacks ---

# Callback for Adding Multiple Samples via CSV Upload
@app.callback(
    Output('output-upload-status', 'children'), # Output to dedicated Div
    Input('upload-data', 'contents'),
    State('upload-data', 'filename'),
    State('upload-data', 'last_modified'),
    prevent_initial_call=True # Prevents callback from firing on app load
)
def upload_data(contents, filename, last_modified):
    if contents is None:
        return ""

    try:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)

        if 'csv' in filename:
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
        elif 'xls' in filename or 'xlsx' in filename: # Added Excel support
            df = pd.read_excel(io.BytesIO(decoded))
        else:
            return html.Div('Please upload a .csv or .xlsx file.', className='text-red-600')

        # --- Data Validation (IMPORTANT!) ---
        required_cols = ['project', 'subject', 'condition', 'age', 'sex', 'treatment',
                         'response', 'sample', 'sample_type', 'time_from_treatment_start',
                         'b_cell', 'cd8_t_cell', 'cd4_t_cell', 'nk_cell', 'monocyte']
        if not all(col in df.columns for col in required_cols):
            missing = [col for col in required_cols if col not in df.columns]
            return html.Div(f'Error: Missing required columns in uploaded file: {", ".join(missing)}', className='text-red-600')

        # Basic type conversion and validation for critical columns
        for col in ['age', 'time_from_treatment_start'] + [c for c in required_cols if c in ['b_cell', 'cd8_t_cell', 'cd4_t_cell', 'nk_cell', 'monocyte']]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                # Allow NaNs for age/time_from_treatment_start/response, but not for cell counts
                if df[col].isnull().any() and col not in ['age', 'time_from_treatment_start', 'response']:
                    return html.Div(f'Error: Numeric values required in column "{col}".', className='text-red-600')
                # Fill NaN with 0 for counts/time/age and convert to int
                df[col] = df[col].fillna(0).astype(int) 

        if 'response' in df.columns:
            df['response'] = df['response'].astype(str).str.lower().str.strip()
            df['response'] = df['response'].replace({'none': None, 'nan': None, '': None}) # Treat 'none' or 'nan' string as actual None
            if not df['response'].fillna('valid').isin(['y', 'n', 'valid']).all():
                return html.Div('Error: "response" column contains invalid values. Must be "y", "n", or empty/blank.', className='text-red-600')

        conn = database.get_db_connection()
        try:
            database.bulk_add_data(conn, df)
            return html.Div(f'{len(df)} samples from "{filename}" successfully added to the database.', className='text-green-600')
        except sqlite3.IntegrityError as e:
            return html.Div(f'Database Error: {e}. Check for duplicate sample IDs or other integrity constraints (e.g., existing sample ID, subject ID).', className='text-red-600')
        except Exception as e:
            print(f"Error in upload_data callback: {e}") # Log the error to console
            return html.Div(f'Error adding data to database: {e}', className='text-red-600')
        finally:
            conn.close()

    except Exception as e:
        print(f"Error in upload_data callback processing file: {e}") # Log parsing error
        return html.Div(f'There was an error processing this file: {e}', className='text-red-600')


# Callback for Deleting Samples by ID (Comma-separated list)
@app.callback(
    Output('output-delete-status', 'children'), # Output to the dedicated Div
    Input('delete-samples-by-id-button', 'n_clicks'), # Button for ID deletion
    State('delete-sample-ids', 'value'), # Input for comma-separated IDs
    prevent_initial_call=True
)
def delete_samples_by_id(n_clicks, sample_ids_str):
    if n_clicks is None or n_clicks == 0:
        return ""

    if not sample_ids_str:
        return html.Div("Please enter sample IDs to delete.", className='text-yellow-600')

    sample_ids = [s.strip() for s in sample_ids_str.split(',') if s.strip()]
    if not sample_ids:
        return html.Div("Invalid input. Please enter valid comma-separated sample IDs.", className='text-red-600')

    conn = database.get_db_connection()
    try:
        deleted_count = database.bulk_delete_samples(conn, sample_ids)
        if deleted_count > 0:
            message = html.Div(f"Successfully deleted {deleted_count} samples.", className='text-green-600')
        else:
            message = html.Div(f"No samples found with the provided IDs: {', '.join(sample_ids)}.", className='text-yellow-600')
    except Exception as e:
        print(f"Error in delete_samples_by_id callback: {e}") # Log the error
        message = html.Div(f"Error deleting samples: {e}", className='text-red-600')
    finally:
        conn.close()

    return message


# Callback for Adding a New Row to the Full Dataset Table
@app.callback(
    Output('full-dataset-table', 'data', allow_duplicate=True),
    Output('full-dataset-table', 'columns', allow_duplicate=True),
    Output('full-dataset-table', 'page_current', allow_duplicate=True), # ADDED output for page_current
    Input('add-new-table-row-button', 'n_clicks'),
    State('full-dataset-table', 'data'), # Get current data
    State('full-dataset-table', 'page_size'), # Get page size to calculate last page
    prevent_initial_call=True
)
def add_row_to_table(n_clicks, current_table_data, page_size):
    if n_clicks is None or n_clicks == 0:
        return dash.no_update, dash.no_update, dash.no_update

    # Get current columns (now sample is editable)
    columns_info = get_initial_table_columns() # Use the helper function

    # Initialize rows if it's the first add or table was empty
    if current_table_data is None:
        rows = []
    else:
        rows = list(current_table_data) # Create a mutable list from current data

    # Create an empty dictionary for a new row
    new_row = {col_dict['id']: None for col_dict in columns_info}

    rows.append(new_row)
    
    # Calculate the page number for the newly added row
    # page_current is 0-indexed, page_size is the number of rows per page
    new_page_current = math.ceil(len(rows) / page_size) - 1
    new_page_current = max(0, new_page_current) # Ensure it's not negative if table is empty

    return rows, columns_info, new_page_current


# Callback for Deleting Selected Rows from the Table (using checkboxes)
@app.callback(
    Output('output-table-edit-status', 'children', allow_duplicate=True), # Status for table operations
    Output('full-dataset-table', 'data', allow_duplicate=True), # Update table data without full refresh
    Input('delete-selected-rows-button', 'n_clicks'),
    State('full-dataset-table', 'data'),
    State('full-dataset-table', 'selected_rows'),
    prevent_initial_call=True
)
def delete_selected_rows_from_table(n_clicks, current_table_data, selected_rows):
    if n_clicks is None or n_clicks == 0:
        return "", dash.no_update

    if not selected_rows:
        return html.Div("No rows selected for deletion.", className='text-yellow-600'), dash.no_update

    # Extract sample IDs from the selected rows
    # Filter out None/empty sample IDs, which might come from newly added empty rows
    samples_to_delete = [current_table_data[i]['sample'] for i in selected_rows if current_table_data[i]['sample'] is not None and str(current_table_data[i]['sample']).strip() != '']
    
    if not samples_to_delete:
        return html.Div("Selected rows do not have valid Sample IDs for deletion.", className='text-yellow-600'), dash.no_update


    conn = database.get_db_connection()
    try:
        deleted_count = database.bulk_delete_samples(conn, samples_to_delete)
        if deleted_count > 0:
            # Filter out the deleted rows from the current table data
            # Use original index of selected_rows to remove them correctly
            updated_table_data = [row for i, row in enumerate(current_table_data) if i not in selected_rows]
            message = html.Div(f"Successfully deleted {deleted_count} selected samples.", className='text-green-600')
            return message, updated_table_data
        else:
            message = html.Div(f"Could not find selected samples in the database to delete.", className='text-yellow-600')
            return message, dash.no_update
    except Exception as e:
        print(f"Error in delete_selected_rows_from_table callback: {e}")
        message = html.Div(f"Error deleting selected samples: {e}", className='text-red-600')
        return message, dash.no_update
    finally:
        conn.close()

# Callback for Client-Side Validation on Table Edits
@app.callback(
    Output('output-table-edit-status', 'children'), # Output for status messages
    Input('full-dataset-table', 'data'),
    State('full-dataset-table', 'data_previous'),
    prevent_initial_call=True
)
def handle_table_edits(data, data_previous):
    # This callback is primarily for client-side validation and managing the UI state.
    # It does NOT write to the database. Database writes are handled by the 'Save Changes' button.
    
    if data_previous is None:
        return "" # No initial message

    df_current = pd.DataFrame(data)
    # Ensure df_previous is a DataFrame, even if data_previous is None, to avoid errors in comparisons
    df_previous = pd.DataFrame(data_previous) if data_previous else pd.DataFrame(columns=df_current.columns)

    message_list = [] # Collect all validation messages

    # Perform client-side validation for all rows (new and existing)
    for idx, row in df_current.iterrows():
        # Robustly get sample ID for messages, default to 'New Row' and strip whitespace
        current_sample_id_for_msg = str(row.get('sample', 'New Row')).strip()
        if not current_sample_id_for_msg: # If it's empty after strip, use a placeholder for message
            current_sample_id_for_msg = 'New Row (ID missing)'

        # Determine if it's a new row by checking if its 'sample' ID exists in the previous data.
        is_new_row = True
        if 'sample' in df_previous.columns and not df_previous.empty:
            # Convert previous IDs to string for robust comparison
            previous_sample_ids_str_series = df_previous['sample'].dropna().astype(str)
            if current_sample_id_for_msg in previous_sample_ids_str_series.values:
                is_new_row = False

        # Validation for required fields
        required_str_cols = ['sample', 'subject', 'project', 'condition', 'treatment', 'sample_type', 'sex']
        required_num_cols = ['b_cell', 'cd8_t_cell', 'cd4_t_cell', 'nk_cell', 'monocyte']
        optional_num_cols = ['age', 'time_from_treatment_start']

        # Ensure sample ID is not empty for new rows (this is a critical check for saving later)
        if is_new_row and (pd.isna(row.get('sample')) or current_sample_id_for_msg == 'New Row (ID missing)'):
            message_list.append(str((f"Warning: Sample '{current_sample_id_for_msg}' - 'sample' ID cannot be empty for a new row. Please provide a unique ID.")))
        
        # Check for empty strings in required string fields
        for col in required_str_cols:
            if col in row: # Ensure the column exists in the row dictionary
                # Explicitly convert to string and strip whitespace for emptiness check
                val_str = str(row.get(col, '')).strip() 
                if val_str == '':
                    message_list.append(str(f"Warning: Sample '{current_sample_id_for_msg}' - '{col}' cannot be empty."))
        
        # Check for numeric types in required numeric fields (cell counts)
        for col in required_num_cols:
            val = row.get(col)
            # Coerce to numeric; if it becomes NaN, it's not a valid number
            coerced_val = pd.to_numeric(val, errors='coerce')
            if pd.isna(coerced_val):
                # Robustly convert original value to string for message
                # Using repr() for values that might be complex objects (like pd.NA) to get a safe string representation
                original_val_str = repr(val) if pd.isna(val) else str(val) 
                message_list.append(str(f"Warning: Sample '{current_sample_id_for_msg}' - '{col}' ('{original_val_str}') must be a numeric value."))

        # Check for numeric types in optional numeric fields if values are present
        for col in optional_num_cols:
            val = row.get(col)
            if pd.notna(val): # Only validate if not NaN
                coerced_val = pd.to_numeric(val, errors='coerce')
                if pd.isna(coerced_val): # If it couldn't be coerced to numeric, it's an error
                    original_val_str = repr(val) if pd.isna(val) else str(val) # Robust conversion
                    message_list.append(str(f"Warning: Sample '{current_sample_id_for_msg}' - '{col}' ('{original_val_str}') must be a numeric value if provided."))

        # Specific validation for 'response' column
        if 'response' in row: # Ensure the column exists
            # Robustly convert value to string for comparison and message
            response_val_raw = row.get('response')
            response_val_display = str(response_val_raw).lower().strip() if pd.notna(response_val_raw) else ''
            
            if response_val_display not in ['y', 'n', ''] and pd.notna(response_val_raw):
                message_list.append(str(f"Warning: Sample '{current_sample_id_for_msg}' - 'response' ('{response_val_display}') must be 'y', 'n', or empty."))
        
        # Check for duplicate sample IDs within the current UI table (before saving to DB)
        # Only check if the sample ID is not empty, as empty IDs are often temporary for new rows
        if current_sample_id_for_msg and current_sample_id_for_msg != 'New Row (ID missing)' and 'sample' in df_current.columns:
            # Create a Series of string-converted sample IDs for robust duplication check
            sample_ids_as_str_series = df_current['sample'].dropna().astype(str)
            # Count occurrences of the current ID
            if (sample_ids_as_str_series == current_sample_id_for_msg).sum() > 1:
                message_list.append(str(f"Warning: Sample ID '{current_sample_id_for_msg}' is duplicated in the table. It must be unique to save."))

    # Use set() to remove duplicate messages, then convert to list of html.Li components.
    # Sorting ensures consistent order of messages displayed in the UI.
    # CRITICAL FIX: Explicitly cast 'msg' to str to guarantee React compatibility.
    for msg in message_list:
        if not isinstance(msg, str):
            print("Non-string in message_list:", msg, type(msg))

    final_message_div_content = html.Ul([html.Li(str(msg)) for msg in sorted(list(set(message_list)))]) if message_list else ""
    
    # Only return the validation message div, not the data
    return html.Div(final_message_div_content, className='text-yellow-600' if message_list else '')

# CALLBACK: To Save All Changes from the Table to the Database
@app.callback(
    Output('output-table-edit-status', 'children', allow_duplicate=True), # Status message
    Output('full-dataset-table', 'data', allow_duplicate=True),         # Trigger refresh of table data
    Input('save-changes-button', 'n_clicks'),
    State('full-dataset-table', 'data'), # Get the current state of the table data
    State('full-dataset-table', 'data_previous'), # Get the previous state to detect changes
    prevent_initial_call=True
)
def save_table_changes(n_clicks, current_table_data, previous_table_data):
    if n_clicks is None or n_clicks == 0:
        return "", dash.no_update # No update if button not clicked

    if not current_table_data:
        return html.Div("No data in table to save.", className='text-yellow-600'), dash.no_update

    df_current = pd.DataFrame(current_table_data)
    df_previous = pd.DataFrame(previous_table_data) if previous_table_data else pd.DataFrame(columns=df_current.columns) # Handle empty previous state

    conn = database.get_db_connection()
    message_list = []
    db_write_occurred = False

    try:
        # --- Handle New Rows ---
        # Find rows that are in current_table_data but not in previous_table_data (based on 'sample' ID)
        new_sample_ids = df_current[~df_current['sample'].isin(df_previous['sample'])]['sample'].dropna().tolist()
        
        if new_sample_ids:
            new_rows_to_add_df = df_current[df_current['sample'].isin(new_sample_ids)].copy()
            if not new_rows_to_add_df.empty:
                try:
                    # Perform server-side validation for new rows before adding
                    for idx, row in new_rows_to_add_df.iterrows():
                        required_str_cols = ['sample', 'subject', 'project', 'condition', 'treatment', 'sample_type', 'sex']
                        required_num_cols = ['b_cell', 'cd8_t_cell', 'cd4_t_cell', 'nk_cell', 'monocyte']
                        optional_num_cols = ['age', 'time_from_treatment_start']

                        for col in required_str_cols:
                            if pd.isna(row.get(col)) or str(row.get(col, '')).strip() == '':
                                raise ValueError(f"Missing required text field '{col}' for new sample '{row.get('sample', 'N/A')}'.")
                        for col in required_num_cols:
                             if pd.isna(row.get(col)) or not pd.api.types.is_numeric_dtype(pd.to_numeric(row.get(col), errors='coerce')):
                                raise ValueError(f"Missing or invalid numeric value for '{col}' for new sample '{row.get('sample', 'N/A')}'.")
                        for col in optional_num_cols:
                            if pd.notna(row.get(col)) and not pd.api.types.is_numeric_dtype(pd.to_numeric(row.get(col), errors='coerce')):
                                raise ValueError(f"Invalid numeric value for optional field '{col}' for new sample '{row.get('sample', 'N/A')}'.")
                        response_val = str(row.get('response', '')).lower().strip()
                        if response_val not in ['y', 'n', ''] and pd.notna(row.get('response')):
                            raise ValueError(f"Invalid value for 'response' for new sample '{row.get('sample', 'N/A')}'. Must be 'y', 'n', or empty.")
                    
                    database.bulk_add_data(conn, new_rows_to_add_df)
                    message_list.append(f"Successfully added {len(new_rows_to_add_df)} new sample(s).")
                    db_write_occurred = True
                except sqlite3.IntegrityError as e:
                    message_list.append(f"Database Error adding new sample(s): {e}. Ensure Sample IDs are unique and valid foreign keys exist.")
                    conn.rollback()
                except ValueError as e:
                    message_list.append(f"Validation Error adding new sample(s): {e}.")
                    conn.rollback()
                except Exception as e:
                    message_list.append(f"Unexpected error adding new sample(s): {e}.")
                    conn.rollback()


        # --- Handle Edited Existing Rows ---
        # Iterate over samples that existed in the previous state
        for previous_sample_id in df_previous['sample'].unique():
            if previous_sample_id in df_current['sample'].values:
                # This sample still exists in the current UI data
                current_row = df_current[df_current['sample'] == previous_sample_id].iloc[0]
                previous_row = df_previous[df_previous['sample'] == previous_sample_id].iloc[0]

                updates_needed = False
                for col in df_current.columns:
                    current_val = current_row[col]
                    previous_val = previous_row[col]

                    # Robust comparison, especially for NaNs and types
                    if pd.isna(current_val) and pd.isna(previous_val):
                        continue # No change if both are NaN
                    elif str(current_val) != str(previous_val):
                        updates_needed = True
                        break # Changes detected

                if updates_needed:
                    try:
                        # If the sample ID itself was changed for an existing row:
                        # This scenario means the user edited the 'sample' column for an existing record.
                        # We treat this as a delete of the old record and insert of the new one.
                        if str(current_row['sample']) != str(previous_row['sample']):
                            old_id = previous_row['sample']
                            new_id = current_row['sample']
                            
                            # Validate the new ID before trying to delete/add
                            if pd.isna(new_id) or str(new_id).strip() == '':
                                raise ValueError(f"Cannot change sample ID from '{old_id}' to empty. New ID must be provided.")

                            # Delete the old record
                            database.bulk_delete_samples(conn, [old_id])
                            message_list.append(f"Info: Old sample '{old_id}' deleted during ID change to '{new_id}'.")
                            
                            # Add the new record (this will handle samples, subjects, projects, cell_counts)
                            database.bulk_add_data(conn, pd.DataFrame([current_row.to_dict()]))
                            message_list.append(f"Successfully re-added sample with new ID '{new_id}'.")
                            db_write_occurred = True

                        else: # Sample ID itself was NOT changed, just other fields
                            # Pass the entire row to bulk_add_data.
                            # bulk_add_data uses INSERT OR REPLACE for samples, which will update existing records.
                            # It also uses INSERT OR IGNORE for projects/subjects for consistency.
                            database.bulk_add_data(conn, pd.DataFrame([current_row.to_dict()]))
                            message_list.append(f"Successfully updated sample '{current_row['sample']}'.")
                            db_write_occurred = True
                        
                    except sqlite3.IntegrityError as e:
                        message_list.append(f"Database Error updating sample '{current_row['sample']}': {e}. Ensure Sample IDs are unique and foreign keys are valid.")
                        conn.rollback()
                    except ValueError as e:
                        message_list.append(f"Validation Error updating sample '{current_row['sample']}': {e}.")
                        conn.rollback()
                    except Exception as e:
                        message_list.append(f"Unexpected error updating sample '{current_row['sample']}': {e}.")
                        conn.rollback()

        # --- Handle Deleted Rows (from UI, not explicit Delete button) ---
        # These are rows in previous_table_data but not in current_table_data
        deleted_sample_ids_ui = [
            s_id for s_id in df_previous['sample'].unique()
            if s_id not in df_current['sample'].values and pd.notna(s_id)
        ]
        
        if deleted_sample_ids_ui:
            try:
                deleted_count = database.bulk_delete_samples(conn, deleted_sample_ids_ui)
                if deleted_count > 0:
                    message_list.append(f"Successfully deleted {deleted_count} sample(s) that were removed from the table.")
                    db_write_occurred = True
            except Exception as e:
                message_list.append(f"Error deleting samples removed from UI: {e}")
                conn.rollback()

    except Exception as e:
        print(f"Unhandled error in save_table_changes outer try-catch: {e}")
        conn.rollback()
        return html.Div(f"An unhandled error occurred during saving: {e}", className='text-red-600'), dash.no_update
    finally:
        conn.close()

    final_message_div_content = html.Ul([html.Li(str(msg)) for msg in message_list]) if message_list else ""

    # Always trigger a refresh of the table data from the database after saving
    # This ensures the table reflects the true saved state and all validations.
    # It also handles re-sorting.
    updated_df_from_db = get_all_data_for_display()
    
    return html.Div(final_message_div_content, className='text-green-600' if db_write_occurred and not any("Error" in msg for msg in message_list) else 'text-red-600'), updated_df_from_db.to_dict('records')


# Callback to Refresh the Full Dataset Table (manually via button click)
@app.callback(
    Output('full-dataset-table', 'data', allow_duplicate=True),
    Output('full-dataset-table', 'columns', allow_duplicate=True),
    Input('refresh-data-table-button', 'n_clicks'), # ONLY trigger by this button
    prevent_initial_call=True # Only runs when the button is clicked, not on app load
)
def refresh_full_dataset_table(n_clicks_refresh): # Function now correctly expects only 1 argument
    # This callback ensures the table always shows the latest data from the DB.
    # It is explicitly triggered by the 'Refresh Data Table' button.
    
    if n_clicks_refresh is None or n_clicks_refresh == 0:
        return dash.no_update, dash.no_update
    
    updated_df = get_all_data_for_display() # This will get the data sorted by sample_id ASC
    
    # Use the helper function to get columns, ensuring sample is editable
    columns = get_initial_table_columns() 
    
    return updated_df.to_dict('records'), columns

# Callback to refresh the Relative Frequencies Summary Table
@app.callback(
    Output('relative-frequencies-table', 'data', allow_duplicate=True),
    Input('refresh-data-button', 'n_clicks'), # Keep its own refresh button
    Input('refresh-data-table-button', 'n_clicks'), # Trigger when main data table is refreshed
    prevent_initial_call=True # Only runs when a button is clicked
)
def refresh_relative_frequencies_table_data(refresh_n_rel_freq, refresh_n_main_table): # Update function signature
    """Refreshes the data in the relative frequencies table using analysis.get_relative_frequency."""
    # This callback is explicitly triggered by the 'Refresh Relative Frequencies' button
    # or by the 'Refresh Data Table' button in the data management section.

    # Check which input triggered the callback
    ctx = dash.callback_context
    if not ctx.triggered: # Should be prevented by prevent_initial_call=True
        return dash.no_update

    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    # If it's the initial (0 or None) click for either button, don't update unless explicitly clicked later
    if (trigger_id == 'refresh-data-button' and (refresh_n_rel_freq is None or refresh_n_rel_freq == 0)) or \
       (trigger_id == 'refresh-data-table-button' and (refresh_n_main_table is None or refresh_n_main_table == 0)):
        return dash.no_update

    all_data_df_wide = get_all_data_for_display() # Get latest wide-format data
    rel_freq_df = analysis.get_relative_frequency(all_data_df_wide) # Use analysis.get_relative_frequency
    
    if rel_freq_df.empty:
        return []
    
    return rel_freq_df.to_dict('records')


# Callback for Response Comparison Analysis
@app.callback(
    Output('response-analysis-output', 'children'),
    Output('response-boxplot-container', 'children'), # This targets the CONTAINER's children
    Input('run-response-analysis-button', 'n_clicks'), # Keep its own run button
    Input('refresh-data-table-button', 'n_clicks'), # Trigger when main data table is refreshed
    prevent_initial_call=True # Only runs when a button is clicked
)
def run_response_analysis(n_clicks_run, n_clicks_refresh_main_table): # Update function signature
    # This callback performs statistical analysis and generates plots for response comparison.
    # It is explicitly triggered by the 'Run Response Comparison' button
    # or by the 'Refresh Data Table' button in the data management section.

    ctx = dash.callback_context
    if not ctx.triggered:
        return html.Div("Click 'Run Response Comparison' to analyze.", className='text-gray-500'), html.Div()

    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    # If it's the initial (0 or None) click for either button, don't update unless explicitly clicked later
    if (trigger_id == 'run-response-analysis-button' and (n_clicks_run is None or n_clicks_run == 0)) or \
       (trigger_id == 'refresh-data-table-button' and (n_clicks_refresh_main_table is None or n_clicks_refresh_main_table == 0)):
        return html.Div("Click 'Run Response Comparison' to analyze.", className='text-gray-500'), html.Div()

    # Get the latest data for analysis (wide format)
    all_data_df_wide = get_all_data_for_display()
    
    # Convert to the long format with relative frequencies using analysis.get_relative_frequency
    all_data_df_long = analysis.get_relative_frequency(all_data_df_wide)

    if all_data_df_long.empty:
        return html.Div("No data available for response comparison.", className='text-red-500'), html.Div()

    filtered_df, stats_results = analysis.analyze_melanoma_tr1_response(all_data_df_long)

    # Generate the list of dcc.Graph components
    figures_list = []
    if not filtered_df.empty:
        # These population names must match what's in your 'population' column after melting
        cell_populations = ['b_cell', 'cd8_t_cell', 'cd4_t_cell', 'nk_cell', 'monocyte']
        for pop in cell_populations:
            pop_data = filtered_df[filtered_df['population'] == pop]
            # Only generate plot if there's sufficient data for the population
            # (e.g., at least one responder and one non-responder value, or more than 1 overall point for visual)
            if not pop_data.empty and pop_data['response'].nunique() > 1 and len(pop_data['percentage'].dropna()) >= 2 :
                fig = px.box(
                    pop_data,
                    x='response',
                    y='percentage',
                    color='response',
                    title=f'{pop} Relative Frequency',
                    labels={'response': 'Treatment Response', 'percentage': 'Relative Frequency (%)'},
                    color_discrete_map={'y': '#3B82F6', 'n': '#EF4444'}
                )
                fig.update_layout(
                    title_x=0.5,
                    font_family="Inter",
                    margin=dict(l=20, r=20, t=50, b=20),
                    height=300,
                    showlegend=False
                )
                figures_list.append(dcc.Graph(figure=fig, className='w-full lg:w-1/5 xl:w-1/5 p-2'))
            else:
                figures_list.append(html.Div(f"Insufficient data for {pop} boxplot (need at least 2 data points for different responses).", className='text-gray-500 p-2'))
    
    # Generate statistical results display
    stat_output_elements = []
    if stats_results:
        stat_output_elements.append(html.H3("Statistical Significance Report:", className='text-lg font-semibold text-gray-800 mt-4 mb-2'))
        for pop, result in stats_results.items():
            if result['p_value'] is not None:
                significance_text = "Significant difference (p < 0.05)" if result['significant'] else "No significant difference (p >= 0.05)"
                stat_output_elements.append(
                    html.P(f"Population: {pop} | P-value: {result['p_value']:.4f} | Conclusion: {significance_text}",
                           className='text-sm text-gray-700')
                )
            else:
                stat_output_elements.append(
                    html.P(f"Population: {pop} - Not enough data for statistical test.", className='text-sm text-gray-700')
                )
    
    return html.Div(stat_output_elements), figures_list


# Callback for Baseline Sample Queries
@app.callback(
    Output('baseline-queries-output', 'children'),
    Input('run-baseline-queries-button', 'n_clicks'), # Keep its own run button
    Input('refresh-data-table-button', 'n_clicks'), # Trigger when main data table is refreshed
    prevent_initial_call=True # Only runs when a button is clicked
)
def run_baseline_queries(n_clicks_run, n_clicks_refresh_main_table): # Update function signature
    # This callback performs queries on baseline samples.
    # It is explicitly triggered by the 'Run Baseline Queries' button
    # or by the 'Refresh Data Table' button in the data management section.

    ctx = dash.callback_context
    if not ctx.triggered:
        return html.Div("Click 'Run Baseline Queries' to analyze.", className='text-gray-500')
    
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if (trigger_id == 'run-baseline-queries-button' and (n_clicks_run is None or n_clicks_run == 0)) or \
       (trigger_id == 'refresh-data-table-button' and (n_clicks_refresh_main_table is None or n_clicks_refresh_main_table == 0)):
        return html.Div("Click 'Run Baseline Queries' to analyze.", className='text-gray-500')

    # Get the latest data in wide format
    all_data_df_wide = get_all_data_for_display()

    if all_data_df_wide.empty:
        return html.Div("No data available for baseline queries.", className='text-red-500')

    # Pass the wide format DataFrame to analysis.query_baseline_melanoma_tr1_samples
    baseline_samples_df, aggregated_counts = analysis.query_baseline_melanoma_tr1_samples(all_data_df_wide)

    if baseline_samples_df.empty:
        return html.Div("No baseline melanoma PBMC samples with tr1 treatment found.", className='text-red-500')
    
    output_elements = [html.H3("Baseline Melanoma TR1 Sample Breakdown:", className='text-lg font-semibold text-gray-800 mb-2')]
    output_elements.append(html.P(f"Total unique baseline samples: {baseline_samples_df['sample'].nunique()}", className='text-gray-700 mb-2'))

    output_elements.append(dash_table.DataTable(
        columns=[{"name": i, "id": i} for i in aggregated_counts['samples_per_project'].columns],
        data=aggregated_counts['samples_per_project'].to_dict('records'),
        style_table={'width': 'fit-content'},
        style_header={'backgroundColor': 'rgb(240, 240, 240)', 'fontWeight': 'bold'},
        style_cell={'textAlign': 'left', 'padding': '8px'}
    ))

    output_elements.append(html.H4("Subjects by Response:", className='font-medium text-gray-700 mt-4'))
    output_elements.append(dash_table.DataTable(
        columns=[{"name": i, "id": i} for i in aggregated_counts['subject_response_counts'].columns],
        data=aggregated_counts['subject_response_counts'].to_dict('records'),
        style_table={'width': 'fit-content'},
        style_header={'backgroundColor': 'rgb(240, 240, 240)', 'fontWeight': 'bold'},
        style_cell={'textAlign': 'left', 'padding': '8px'}
    ))

    output_elements.append(html.H4("Subjects by Sex:", className='font-medium text-gray-700 mt-4'))
    output_elements.append(dash_table.DataTable(
        columns=[{"name": i, "id": i} for i in aggregated_counts['subject_sex_counts'].columns],
        data=aggregated_counts['subject_sex_counts'].to_dict('records'),
        style_table={'width': 'fit-content'},
        style_header={'backgroundColor': 'rgb(240, 240, 240)', 'fontWeight': 'bold'},
        style_cell={'textAlign': 'left', 'padding': '8px'}
    ))

    return html.Div(output_elements)

# ... (main execution block) ...
if __name__ == '__main__':
    app.run(debug=True)