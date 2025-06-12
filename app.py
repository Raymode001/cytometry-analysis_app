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

# Import your custom modules
import database
import analysis
import visualization # Although we'll mostly use Plotly directly here

# --- Database Initialization and Data Loading ---
# This part ensures the database is ready when the app starts
# It's good practice to ensure the database file exists and is populated
# before the Dash app attempts to read from it.
# You might want to remove the existing DB file on startup for a clean run if you iterate on data.
if os.path.exists(database.db_name):
    os.remove(database.db_name)
    print(f"Existing database '{database.db_name}' removed for a clean start.")
database.init_database()
database.load_data_from_csv('cell-count.csv')
print("Database initialized and data loaded successfully for Dash app.")


# --- Helper Function to Fetch Data ---
def get_all_data_for_display():
    """Fetches all necessary data from DB and calculates relative frequencies."""
    conn = sqlite3.connect(database.db_name)
    # Fetch all raw data joined from the database
    # This query is similar to what fetch_all_data() would return, but tailored for `analysis.get_relative_frequencies`
    query = """
    SELECT
        s.sample_id,
        s.subject_id,
        s.condition,
        s.treatment,
        s.response,
        s.sample_type,
        s.time_from_treatment_start,
        s.age, # Include age and sex for subject demographics later
        s.sex,
        p.project_id,
        cc.population,
        cc.count
    FROM
        samples s
    JOIN
        cell_counts cc ON s.sample_id = cc.sample_id
    JOIN
        subjects subj ON s.subject_id = subj.subject_id
    JOIN
        projects p ON subj.project_id = p.project_id
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        return pd.DataFrame(), pd.DataFrame()

    # Calculate total count for each sample
    total_counts = df.groupby('sample_id')['count'].sum().reset_index()
    total_counts.rename(columns={'count': 'total_count'}, inplace=True)

    # Merge total counts back to the main DataFrame
    df = pd.merge(df, total_counts, on='sample_id')

    # Calculate percentage
    df['percentage'] = (df['count'] / df['total_count']) * 100

    # Ensure response column is string type, handle NaN for filtering
    df['response'] = df['response'].astype(str)

    return df, df[['sample_id', 'total_count', 'population', 'count', 'percentage']].drop_duplicates()


# --- Initialize the Dash app ---
app = dash.Dash(__name__,
                 external_stylesheets=['https://cdn.tailwindcss.com']) # Use Tailwind for styling

# --- Define the app layout ---
app.layout = html.Div(className='container mx-auto p-6 bg-gray-50 min-h-screen font-sans', children=[
    html.H1("Loblaw Bio: Cytometry Data Analysis Dashboard", className='text-4xl font-bold text-center text-gray-800 mb-8'),

    # --- Data Management Section ---
    html.Div(className='bg-white p-6 rounded-lg shadow-md mb-8', children=[
        html.H2("Data Management (Add/Remove Samples)", className='text-2xl font-semibold text-gray-700 mb-4'),
        html.Div(className='flex flex-wrap items-center gap-4 mb-4', children=[
            html.Div(className='flex-grow', children=[
                html.Label("Sample ID:", className='block text-gray-600 text-sm font-medium mb-1'),
                dcc.Input(id='add-sample-id', type='text', placeholder='e.g., s18', className='w-full p-2 border border-gray-300 rounded-md')
            ]),
            html.Div(className='flex-grow', children=[
                html.Label("Subject ID:", className='block text-gray-600 text-sm font-medium mb-1'),
                dcc.Input(id='add-subject-id', type='text', placeholder='e.g., sbj14', className='w-full p-2 border border-gray-300 rounded-md')
            ]),
            html.Div(className='flex-grow', children=[
                html.Label("Project ID:", className='block text-gray-600 text-sm font-medium mb-1'),
                dcc.Input(id='add-project-id', type='text', placeholder='e.g., prj3', className='w-full p-2 border border-gray-300 rounded-md')
            ]),
            html.Div(className='flex-grow', children=[
                html.Label("Condition:", className='block text-gray-600 text-sm font-medium mb-1'),
                dcc.Input(id='add-condition', type='text', placeholder='e.g., melanoma', className='w-full p-2 border border-gray-300 rounded-md')
            ]),
            html.Div(className='flex-grow', children=[
                html.Label("Treatment:", className='block text-gray-600 text-sm font-medium mb-1'),
                dcc.Input(id='add-treatment', type='text', placeholder='e.g., tr1', className='w-full p-2 border border-gray-300 rounded-md')
            ]),
            html.Div(className='flex-grow', children=[
                html.Label("Response (y/n):", className='block text-gray-600 text-sm font-medium mb-1'),
                dcc.Input(id='add-response', type='text', placeholder='y or n', className='w-full p-2 border border-gray-300 rounded-md')
            ]),
            html.Div(className='flex-grow', children=[
                html.Label("Sample Type:", className='block text-gray-600 text-sm font-medium mb-1'),
                dcc.Input(id='add-sample-type', type='text', placeholder='e.g., PBMC', className='w-full p-2 border border-gray-300 rounded-md')
            ]),
            html.Div(className='flex-grow', children=[
                html.Label("Time from Treatment Start:", className='block text-gray-600 text-sm font-medium mb-1'),
                dcc.Input(id='add-time', type='number', placeholder='e.g., 0', className='w-full p-2 border border-gray-300 rounded-md')
            ]),
            html.Div(className='flex-grow', children=[
                html.Label("Age:", className='block text-gray-600 text-sm font-medium mb-1'),
                dcc.Input(id='add-age', type='number', placeholder='e.g., 50', className='w-full p-2 border border-gray-300 rounded-md')
            ]),
            html.Div(className='flex-grow', children=[
                html.Label("Sex:", className='block text-gray-600 text-sm font-medium mb-1'),
                dcc.Input(id='add-sex', type='text', placeholder='M or F', className='w-full p-2 border border-gray-300 rounded-md')
            ]),
            html.Div(className='flex-grow', children=[
                html.Label("B_cell Count:", className='block text-gray-600 text-sm font-medium mb-1'),
                dcc.Input(id='add-b-cell', type='number', placeholder='e.g., 10000', className='w-full p-2 border border-gray-300 rounded-md')
            ]),
            html.Div(className='flex-grow', children=[
                html.Label("CD8_t_cell Count:", className='block text-gray-600 text-sm font-medium mb-1'),
                dcc.Input(id='add-cd8-t-cell', type='number', placeholder='e.g., 5000', className='w-full p-2 border border-gray-300 rounded-md')
            ]),
            html.Div(className='flex-grow', children=[
                html.Label("CD4_t_cell Count:", className='block text-gray-600 text-sm font-medium mb-1'),
                dcc.Input(id='add-cd4-t-cell', type='number', placeholder='e.g., 15000', className='w-full p-2 border border-gray-300 rounded-md')
            ]),
            html.Div(className='flex-grow', children=[
                html.Label("NK_cell Count:", className='block text-gray-600 text-sm font-medium mb-1'),
                dcc.Input(id='add-nk-cell', type='number', placeholder='e.g., 2000', className='w-full p-2 border border-gray-300 rounded-md')
            ]),
            html.Div(className='flex-grow', children=[
                html.Label("Monocyte Count:", className='block text-gray-600 text-sm font-medium mb-1'),
                dcc.Input(id='add-monocyte', type='number', placeholder='e.g., 3000', className='w-full p-2 border border-gray-300 rounded-md')
            ]),
        ]),
        html.Button('Add Sample', id='add-sample-button', n_clicks=0, className='bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded-md shadow-md transition duration-300 ease-in-out mr-2'),
        html.Div(className='flex items-center gap-2 mt-4', children=[
            dcc.Input(id='remove-sample-id', type='text', placeholder='Sample ID to remove (e.g., s1)', className='p-2 border border-gray-300 rounded-md flex-grow'),
            html.Button('Remove Sample', id='remove-sample-button', n_clicks=0, className='bg-red-500 hover:bg-red-700 text-white font-bold py-2 px-4 rounded-md shadow-md transition duration-300 ease-in-out')
        ]),
        html.Div(id='data-management-output', className='mt-4 text-sm font-medium text-gray-700')
    ]),

    # --- Relative Frequencies Table ---
    html.Div(className='bg-white p-6 rounded-lg shadow-md mb-8', children=[
        html.H2("Relative Frequencies Summary", className='text-2xl font-semibold text-gray-700 mb-4'),
        html.Button('Refresh Data', id='refresh-data-button', n_clicks=0, className='bg-green-500 hover:bg-green-700 text-white font-bold py-2 px-4 rounded-md shadow-md transition duration-300 ease-in-out mb-4'),
        dash_table.DataTable(
            id='relative-frequencies-table',
            columns=[{"name": i, "id": i} for i in ['sample_id', 'total_count', 'population', 'count', 'percentage']],
            data=get_all_data_for_display()[1].to_dict('records'), # Initial data load
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
            children=html.Div(dcc.Graph(id='response-boxplot-graph'))
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

# Callback for Add/Remove Sample
@app.callback(
    Output('data-management-output', 'children'),
    Input('add-sample-button', 'n_clicks'),
    Input('remove-sample-button', 'n_clicks'),
    State('add-sample-id', 'value'),
    State('add-subject-id', 'value'),
    State('add-project-id', 'value'),
    State('add-condition', 'value'),
    State('add-treatment', 'value'),
    State('add-response', 'value'),
    State('add-sample-type', 'value'),
    State('add-time', 'value'),
    State('add-age', 'value'),
    State('add-sex', 'value'),
    State('add-b-cell', 'value'),
    State('add-cd8-t-cell', 'value'),
    State('add-cd4-t-cell', 'value'),
    State('add-nk-cell', 'value'),
    State('add-monocyte', 'value'),
    State('remove-sample-id', 'value')
)
def manage_data(add_n, remove_n,
                sample_id, subject_id, project_id, condition, treatment, response, sample_type, time, age, sex,
                b_cell, cd8_t_cell, cd4_t_cell, nk_cell, monocyte,
                remove_id):
    ctx = dash.callback_context

    if not ctx.triggered:
        return ""

    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    message = ""

    if button_id == 'add-sample-button' and add_n > 0:
        if all([sample_id, subject_id, project_id, condition, treatment, sample_type, time is not None, age is not None, sex,
                b_cell is not None, cd8_t_cell is not None, cd4_t_cell is not None, nk_cell is not None, monocyte is not None]):
            sample_data = {
                'project': project_id, 'subject': subject_id, 'condition': condition,
                'age': age, 'sex': sex, 'treatment': treatment, 'response': response,
                'sample': sample_id, 'sample_type': sample_type, 'time_from_treatment_start': time,
                'b_cell': b_cell, 'cd8_t_cell': cd8_t_cell, 'cd4_t_cell': cd4_t_cell,
                'nk_cell': nk_cell, 'monocyte': monocyte
            }
            try:
                database.add_sample(sample_data)
                message = html.Div(f"Successfully added sample: {sample_id}", className='text-green-600')
            except sqlite3.IntegrityError:
                message = html.Div(f"Error: Sample ID '{sample_id}' already exists or invalid input.", className='text-red-600')
            except Exception as e:
                message = html.Div(f"An unexpected error occurred: {e}", className='text-red-600')
        else:
            message = html.Div("Please fill all fields to add a sample.", className='text-yellow-600')
    elif button_id == 'remove-sample-button' and remove_n > 0:
        if remove_id:
            try:
                database.remove_sample(remove_id)
                message = html.Div(f"Successfully removed sample: {remove_id}", className='text-green-600')
            except Exception as e:
                message = html.Div(f"Error removing sample: {e}", className='text-red-600')
        else:
            message = html.Div("Please enter a Sample ID to remove.", className='text-yellow-600')

    return message

# Callback to refresh the relative frequencies table
@app.callback(
    Output('relative-frequencies-table', 'data'),
    Input('refresh-data-button', 'n_clicks'),
    Input('data-management-output', 'children') # Trigger refresh after add/remove ops
)
def refresh_table_data(refresh_n, data_mgmt_output):
    """Refreshes the data in the relative frequencies table."""
    _all_data_df, rel_freq_df = get_all_data_for_display()
    return rel_freq_df.to_dict('records')

# Callback for Response Comparison Analysis
@app.callback(
    Output('response-analysis-output', 'children'),
    Output('response-boxplot-graph', 'figure'),
    Input('run-response-analysis-button', 'n_clicks'),
    Input('refresh-data-button', 'n_clicks') # Also refresh analysis on data refresh
)
def run_response_analysis(n_clicks, refresh_n_clicks):
    if n_clicks is None and refresh_n_clicks is None:
        # Initial load, return empty or default state
        return html.Div("Click 'Run Response Comparison' to analyze.", className='text-gray-500'), go.Figure()

    _all_data_df, rel_freq_df = get_all_data_for_display()

    if rel_freq_df.empty:
        return html.Div("No data available for response comparison.", className='text-red-500'), go.Figure()

    filtered_df, stats_results = analysis.analyze_melanoma_tr1_response(_all_data_df)

    # Generate the boxplots
    figures = []
    if not filtered_df.empty:
        cell_populations = ['b_cell', 'cd8_t_cell', 'cd4_t_cell', 'nk_cell', 'monocyte']
        for pop in cell_populations:
            pop_data = filtered_df[filtered_df['population'] == pop]
            if not pop_data.empty:
                fig = px.box(
                    pop_data,
                    x='response',
                    y='percentage',
                    color='response', # Use color for better visual separation
                    title=f'{pop} Relative Frequency',
                    labels={'response': 'Treatment Response', 'percentage': 'Relative Frequency (%)'},
                    color_discrete_map={'y': '#3B82F6', 'n': '#EF4444'} # Blue for Y, Red for N
                )
                fig.update_layout(
                    title_x=0.5,
                    font_family="Inter",
                    margin=dict(l=20, r=20, t=50, b=20),
                    height=300, # Adjust height as needed
                    showlegend=False
                )
                figures.append(dcc.Graph(figure=fig, className='w-full lg:w-1/5 xl:w-1/5 p-2'))
    
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
    
    return html.Div(stat_output_elements), html.Div(figures, className='flex flex-wrap justify-center gap-4')


# Callback for Baseline Sample Queries
@app.callback(
    Output('baseline-queries-output', 'children'),
    Input('run-baseline-queries-button', 'n_clicks'),
    Input('refresh-data-button', 'n_clicks') # Also refresh analysis on data refresh
)
def run_baseline_queries(n_clicks, refresh_n_clicks):
    if n_clicks is None and refresh_n_clicks is None:
        return html.Div("Click 'Run Baseline Queries' to analyze.", className='text-gray-500')

    _all_data_df, rel_freq_df = get_all_data_for_display()

    if _all_data_df.empty:
        return html.Div("No data available for baseline queries.", className='text-red-500')

    # Pass the full DataFrame with subject info for the query
    baseline_samples_df, aggregated_counts = analysis.query_baseline_melanoma_tr1_samples(_all_data_df)

    if baseline_samples_df.empty:
        return html.Div("No baseline melanoma PBMC samples with tr1 treatment found.", className='text-red-500')
    
    output_elements = [html.H3("Baseline Melanoma TR1 Sample Breakdown:", className='text-lg font-semibold text-gray-800 mb-2')]
    output_elements.append(html.P(f"Total unique baseline samples: {baseline_samples_df['sample_id'].nunique()}", className='text-gray-700 mb-2'))

    output_elements.append(html.H4("Samples per Project:", className='font-medium text-gray-700 mt-4'))
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

# This line exposes the underlying Flask server to Gunicorn for deployment
server = app.server

if __name__ == '__main__':
    app.run_server(debug=True)