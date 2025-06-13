'''# analysis.py
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

    return baseline_samples, aggregated_counts'''

    # analysis.py
import pandas as pd
from scipy import stats
# Removed sqlite3 import as this file no longer directly queries the database.

def get_relative_frequency(data_df_wide: pd.DataFrame):
    """
    Calculates the relative frequency of each cell type for each sample
    from a wide-format DataFrame and returns a long-format DataFrame.
    
    Args:
        data_df_wide (pd.DataFrame): DataFrame containing sample details and cell counts
                                     in wide format (e.g., 'b_cell', 'cd8_t_cell' as columns).
                                     This is typically the output of get_all_data_for_display() from app.py.

    Returns:
        pd.DataFrame: A DataFrame where each row represents one population from one sample
                      with columns: sample, total_count, population, count, percentage,
                      and other sample metadata.
    """
    if data_df_wide.empty:
        print("No data available to calculate relative frequencies.")
        return pd.DataFrame()

    cell_populations_list = ['b_cell', 'cd8_t_cell', 'cd4_t_cell', 'nk_cell', 'monocyte']

    # Identify columns that are not cell counts for melting (these are metadata)
    id_vars = [col for col in data_df_wide.columns if col not in cell_populations_list]

    # Melt the DataFrame to long format for cell counts
    # 'sample' is used as the sample ID column name from the wide_df
    df_long = data_df_wide.melt(
        id_vars=id_vars,
        var_name='population',
        value_name='count'
    )

    # Ensure 'count' is numeric and handle potential non-numeric/NaN values
    df_long['count'] = pd.to_numeric(df_long['count'], errors='coerce').fillna(0)

    # Calculate total count for each sample
    # Group by the actual sample ID column name used in the wide_df ('sample')
    total_counts = df_long.groupby('sample')['count'].sum().reset_index()
    total_counts.rename(columns={'count': 'total_count'}, inplace=True)

    # Merge total counts back to the main DataFrame
    df_long = pd.merge(df_long, total_counts, on='sample')

    # Calculate percentage
    df_long['percentage'] = (df_long['count'] / df_long['total_count']) * 100
    
    # Ensure 'response' column is string type and handle None/NaN for consistent filtering
    if 'response' in df_long.columns:
        df_long['response'] = df_long['response'].astype(str).replace({'nan': None, '': None})

    # Reorder columns as required by the prompt, including original metadata
    # The prompt requested 'sample_id', 'population', 'count', 'total_count', and 'relative_frequency'.
    # We use 'sample' for 'sample_id' and 'percentage' for 'relative_frequency'.
    required_cols_order = [
        'sample', 'total_count', 'population', 'count', 'percentage',
        'project', 'subject', 'condition', 'age', 'sex', 'treatment',
        'response', 'sample_type', 'time_from_treatment_start'
    ]
    
    # Filter and reorder only columns that exist in df_long after melting
    final_df = df_long[[col for col in required_cols_order if col in df_long.columns]]

    return final_df

def analyze_melanoma_tr1_response(data_df):
    """
    Compares cell population relative frequencies between responders and non-responders
    for melanoma patients receiving tr1 (PBMC samples only).
    Performs statistical tests.
    
    Args:
        data_df (pd.DataFrame): DataFrame containing relative frequencies and sample info.
                                 Expected to be the output of `get_relative_frequency`.

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

    # print("\n--- Statistical Comparison (Responders vs. Non-Responders) ---") # Removed print for app context
    for pop in cell_populations:
        responder_values = responders[responders['population'] == pop]['percentage'].dropna()
        non_responder_values = non_responders[non_responders['population'] == pop]['percentage'].dropna()

        if len(responder_values) > 1 and len(non_responder_values) > 1: # Need at least 2 samples for statistics
            # Mann-Whitney U test (non-parametric)
            statistic, p_value = stats.mannwhitneyu(responder_values, non_responder_values, alternative='two-sided')
            
            statistical_results[pop] = {
                'statistic': statistic,
                'p_value': p_value,
                'significant': p_value < 0.05
            }
            # Add back for local testing if needed, but suppressed for app console
            # print(f"Population: {pop}")
            # print(f"  Responder mean: {responder_values.mean():.2f}%")
            # print(f"  Non-Responder mean: {non_responder_values.mean():.2f}%")
            # print(f"  Mann-Whitney U statistic: {statistic:.2f}, P-value: {p_value:.4f}")
            # if p_value < 0.05:
            #     print(f"  -> Significant difference (p < 0.05) ")
            # else:
            #     print(f"  -> No significant difference (p >= 0.05) ")
        else:
            statistical_results[pop] = {
                'statistic': None,
                'p_value': None,
                'significant': False
            }
            # print(f"Population: {pop} - Not enough data for statistical test.")
            
    return filtered_df, statistical_results

def query_baseline_melanoma_tr1_samples(data_df):
    """
    Identifies melanoma PBMC samples at baseline time_from_treatment_start = 0
    from patients with treatment tr1 and compute frequencies of project, response, and sex.
    
    Args:
        data_df (pd.DataFrame): DataFrame containing sample information in wide format.
                                 This should be the *wide-format* DataFrame
                                 from `get_all_data_for_display` in app.py.

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
    
    # Ensure unique subjects for counting, using the 'subject' column name
    unique_subjects_baseline = baseline_samples.drop_duplicates(subset=['subject'])

    # How many samples from each project, using 'project' and 'sample' column names
    samples_per_project = baseline_samples.groupby('project')['sample'].nunique().reset_index()
    samples_per_project.rename(columns={'sample': 'num_samples'}, inplace=True)

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

    # Removed print statements for cleaner console output in app context
    # print("\n--- Baseline Melanoma PBMC Samples (Treatment tr1) ---")
    # print(f"Total unique baseline samples: {baseline_samples['sample'].nunique()}") # Using 'sample'
    # print("\nSamples per Project:")
    # print(samples_per_project.to_string(index=False))
    # print("\nSubjects by Response:")
    # print(num_subject_response.to_string(index=False))
    # print("\nSubjects by Sex:")
    # print(num_subject_sex.to_string(index=False))

    return baseline_samples, aggregated_counts

import pandas as pd
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Tuple, List

class CytometryAnalysis:
    def __init__(self, data_loader):
        self.data_loader = data_loader
    
    def analyze_cell_frequencies(self) -> pd.DataFrame:
        """Get cell frequency analysis for all samples."""
        return self.data_loader.get_cell_frequencies()
    
    def analyze_response_comparison(self) -> Tuple[pd.DataFrame, List[str]]:
        """Analyze differences between responders and non-responders."""
        df = self.data_loader.get_response_comparison()
        
        # Perform statistical analysis for each population
        significant_populations = []
        for population in df['population'].unique():
            responder_data = df[
                (df['population'] == population) & 
                (df['response'] == 'y')
            ]['percentage']
            non_responder_data = df[
                (df['population'] == population) & 
                (df['response'] == 'n')
            ]['percentage']
            
            # Perform Mann-Whitney U test
            statistic, p_value = stats.mannwhitneyu(
                responder_data, 
                non_responder_data, 
                alternative='two-sided'
            )
            
            if p_value < 0.05:
                significant_populations.append(population)
        
        return df, significant_populations
    
    def plot_response_comparison(self, save_path: str = None):
        """Create boxplots comparing responders vs non-responders."""
        df, significant_populations = self.analyze_response_comparison()
        
        # Set up the plot
        plt.figure(figsize=(12, 6))
        sns.set_style("whitegrid")
        
        # Create boxplot
        ax = sns.boxplot(
            data=df,
            x='population',
            y='percentage',
            hue='response',
            palette={'y': 'green', 'n': 'red'}
        )
        
        # Customize the plot
        plt.title('Cell Population Frequencies: Responders vs Non-responders')
        plt.xlabel('Cell Population')
        plt.ylabel('Relative Frequency (%)')
        plt.xticks(rotation=45)
        plt.legend(title='Response', labels=['Responder', 'Non-responder'])
        
        # Highlight significant populations
        for i, population in enumerate(df['population'].unique()):
            if population in significant_populations:
                ax.text(i, ax.get_ylim()[1], '*', 
                       horizontalalignment='center', 
                       verticalalignment='top',
                       fontsize=15)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path)
        else:
            plt.show()
    
    def analyze_baseline_melanoma_tr1(self) -> pd.DataFrame:
        """Analyze baseline melanoma tr1 samples."""
        return self.data_loader.get_baseline_melanoma_tr1()
    
    def generate_summary_report(self, output_path: str = None):
        """Generate a comprehensive summary report."""
        # Get all analyses
        cell_freq = self.analyze_cell_frequencies()
        response_comp, sig_pops = self.analyze_response_comparison()
        baseline = self.analyze_baseline_melanoma_tr1()
        
        # Create summary text
        summary = []
        summary.append("Cytometry Analysis Summary Report")
        summary.append("=" * 40)
        
        # Cell frequency summary
        summary.append("\nCell Population Frequencies:")
        summary.append("-" * 30)
        summary.append(f"Total samples analyzed: {len(cell_freq['sample_id'].unique())}")
        summary.append(f"Total cell populations: {len(cell_freq['population'].unique())}")
        
        # Response comparison summary
        summary.append("\nResponse Comparison Analysis:")
        summary.append("-" * 30)
        summary.append(f"Significant differences found in {len(sig_pops)} populations:")
        for pop in sig_pops:
            summary.append(f"- {pop}")
        
        # Baseline analysis summary
        summary.append("\nBaseline Melanoma TR1 Analysis:")
        summary.append("-" * 30)
        for _, row in baseline.iterrows():
            summary.append(
                f"Project {row['project_id']}: "
                f"{row['sample_count']} samples from {row['subject_count']} subjects "
                f"({row['sex']}, {row['response']})"
            )
        
        # Write to file if path provided
        if output_path:
            with open(output_path, 'w') as f:
                f.write('\n'.join(summary))
        
        return '\n'.join(summary)