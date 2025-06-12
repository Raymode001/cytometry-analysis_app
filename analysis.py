# analysis.py
import pandas as pd
from scipy import stats
import sqlite3
from database import db_name # Assuming database.py is in the same directory

def get_relative_frequency():
    """
    Calculates the relative frequency of each cell type for each sample
    and returns a DataFrame.
    """
    conn = sqlite3.connect(db_name)
    # Fetch all cell counts and sample metadata
    query = """
    SELECT
        s.sample_id,
        s.subject_id,
        s.condition,
        s.treatment,
        s.response,
        s.sample_type,
        s.time_from_treatment_start,
        cc.population,
        cc.count
    FROM
        samples s
    JOIN
        cell_counts cc ON s.sample_id = cc.sample_id
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        print("No data available to calculate relative frequencies.")
        return pd.DataFrame()

    # Calculate total count for each sample
    total_counts = df.groupby('sample_id')['count'].sum().reset_index()
    total_counts.rename(columns={'count': 'total_count'}, inplace=True)

    # Merge total counts back to the main DataFrame
    df = pd.merge(df, total_counts, on='sample_id')

    # Calculate percentage
    df['percentage'] = (df['count'] / df['total_count']) * 100

    # Reorder columns as required
    df = df[['sample_id', 'total_count', 'population', 'count', 'percentage',
             'subject_id', 'condition', 'treatment', 'response', 'sample_type', 'time_from_treatment_start']]
    
    return df

def analyze_melanoma_tr1_response(data_df):
    """
    Compares cell population relative frequencies between responders and non-responders
    for melanoma patients receiving tr1 (PBMC samples only).
    Performs statistical tests.
    
    Args:
        data_df (pd.DataFrame): DataFrame containing relative frequencies and sample info.

    Returns:
        tuple: A tuple containing:
            - pd.DataFrame: Filtered data for responders vs. non-responders.
            - dict: Dictionary of statistical test results.
    """
    
    # Filter data for melanoma, tr1, PBMC samples with a response
    filtered_df = data_df[
        (data_df['condition'] == 'melanoma') &
        (data_df['treatment'] == 'tr1') &
        (data_df['sample_type'] == 'PBMC') &
        (data_df['response'].isin(['y', 'n'])) # Ensure response is 'y' or 'n' 
    ].copy()

    if filtered_df.empty:
        print("No data found for melanoma patients receiving tr1 (PBMC samples) with defined response.")
        return pd.DataFrame(), {}

    # Separate responders and non-responders
    responders = filtered_df[filtered_df['response'] == 'y']
    non_responders = filtered_df[filtered_df['response'] == 'n']

    cell_populations = ['b_cell', 'cd8_t_cell', 'cd4_t_cell', 'nk_cell', 'monocyte']
    statistical_results = {}

    print("\n--- Statistical Comparison (Responders vs. Non-Responders) ---")
    for pop in cell_populations:
        responder_values = responders[responders['population'] == pop]['percentage'].dropna()
        non_responder_values = non_responders[non_responders['population'] == pop]['percentage'].dropna()

        if len(responder_values) > 1 and len(non_responder_values) > 1: # Need at least 2 samples for statistics
            # Mann-Whitney U test (non-parametric)
            # Alternative: t-test (parametric) if relative frequency is normally distributed: stats.ttest_ind(responder_values, non_responder_values)
            statistic, p_value = stats.mannwhitneyu(responder_values, non_responder_values, alternative='two-sided')
            
            statistical_results[pop] = {
                'statistic': statistic,
                'p_value': p_value,
                'significant': p_value < 0.05
            }
            print(f"Population: {pop}")
            print(f"  Responder mean: {responder_values.mean():.2f}%")
            print(f"  Non-Responder mean: {non_responder_values.mean():.2f}%")
            print(f"  Mann-Whitney U statistic: {statistic:.2f}, P-value: {p_value:.4f}")
            if p_value < 0.05:
                print(f"  -> Significant difference (p < 0.05) ")
            else:
                print(f"  -> No significant difference (p >= 0.05) ")
        else:
            statistical_results[pop] = {
                'statistic': None,
                'p_value': None,
                'significant': False
            }
            print(f"Population: {pop} - Not enough data for statistical test.")
            
    return filtered_df, statistical_results

def query_baseline_melanoma_tr1_samples(data_df):
    """
    Identifies melanoma PBMC samples at baseline time_from_treatment_start = 0
    from patients with treatment tr1 and compute frequencies of project, response, and sex.
    
    Args:
        data_df (pd.DataFrame): DataFrame containing sample information.

    Returns:
        tuple: A tuple containing:
            - pd.DataFrame: Filtered baseline samples.
            - dict: Dictionary of aggregated counts.
    """
    
    # Filter for melanoma, PBMC, baseline, tr1 samples
    baseline_samples = data_df[
        (data_df['condition'] == 'melanoma') &
        (data_df['sample_type'] == 'PBMC') &
        (data_df['time_from_treatment_start'] == 0) & # Baseline 
        (data_df['treatment'] == 'tr1') # Treatment tr1 
    ].copy()

    if baseline_samples.empty:
        print("No baseline melanoma PBMC samples with tr1 treatment found.")
        return pd.DataFrame(), {}
    
    # Ensure unique subjects for counting
    unique_subjects_baseline = baseline_samples.drop_duplicates(subset=['subject_id'])

    # How many samples from each project
    samples_per_project = baseline_samples.groupby('project_id')['sample_id'].nunique().reset_index()
    samples_per_project.rename(columns={'sample_id': 'num_samples'}, inplace=True)

    # How many subjects were responders/non-responders
    # Only consider subjects with a 'y' or 'n' response
    num_subject_response = unique_subjects_baseline[
        unique_subjects_baseline['response'].isin(['y', 'n'])
    ]['response'].value_counts().reset_index()
    num_subject_response.columns = ['response', 'num_subjects']

    # How many subjects were males/females
    num_subject_sex = unique_subjects_baseline['sex'].value_counts().reset_index()
    num_subject_sex.columns = ['sex', 'num_subjects']

    aggregated_counts = {
        'samples_per_project': samples_per_project,
        'subject_response_counts': num_subject_response,
        'subject_sex_counts': num_subject_sex
    }

    print("\n--- Baseline Melanoma PBMC Samples (Treatment tr1) ---")
    print(f"Total unique baseline samples: {baseline_samples['sample_id'].nunique()}")
    print("\nSamples per Project:")
    print(samples_per_project.to_string(index=False))
    print("\nSubjects by Response:")
    print(num_subject_response.to_string(index=False))
    print("\nSubjects by Sex:")
    print(num_subject_sex.to_string(index=False))

    return baseline_samples, aggregated_counts