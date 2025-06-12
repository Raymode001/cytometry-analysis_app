# main.py (for CLI)
import database
import analysis
import visualization
import pandas as pd # For creating sample data for add_sample

def main():
    """Main function to run the data analysis pipeline."""

    # Task 1: Design and Initialize Database, Load Data
    print("--- Task 1: Database Initialization and Data Loading ---")
    database.init_database()
    database.load_data_from_csv('cell-count.csv')

    # Example: Add a new sample (Demonstrates functionality)
    print("\n--- Demonstrating Add/Remove Sample ---")
    new_sample_data = {
        'project': 'prj_new', 'subject': 'sbj_new', 'condition': 'new_condition',
        'age': 40, 'sex': 'F', 'treatment': 'tr_new', 'response': 'y',
        'sample': 's_new', 'sample_type': 'PBMC', 'time_from_treatment_start': 0,
        'b_cell': 10000, 'cd8_t_cell': 5000, 'cd4_t_cell': 15000,
        'nk_cell': 2000, 'monocyte': 3000
    }
    database.add_sample(new_sample_data)

    # Example: Remove a sample (Demonstrates functionality)
    database.remove_sample('s_new') # Remove the sample we just added

    # Task 2: Calculate Relative Frequencies
    print("\n--- Task 2: Calculating Relative Frequencies ---")
    relative_frequencies_df = analysis.get_relative_frequency()
    if not relative_frequencies_df.empty:
        print("\nRelative Frequencies Summary (first 5 rows):")
        print(relative_frequencies_df.head().to_string())
        # Save to CSV for Bob
        relative_frequencies_df.to_csv('relative_frequencies_summary.csv', index=False)
        print("\nRelative frequencies summary saved to 'relative_frequencies_summary.csv'")
    
    # Task 3: Compare Responders vs. Non-Responders and Visualize
    print("\n--- Task 3: Analyzing Responders vs. Non-Responders ---")
    if not relative_frequencies_df.empty:
        # Pass the relative frequencies DataFrame to the analysis function
        responder_nonresponder_df, stats_results = analysis.analyze_melanoma_tr1_response(relative_frequencies_df)
        if not responder_nonresponder_df.empty:
            visualization.plot_relative_frequencies_boxplot(responder_nonresponder_df, "melanoma_tr1_response_boxplots.png")
    else:
        print("Cannot perform responder vs. non-responder analysis: relative frequencies not calculated.")

    # Task 4: Explore Specific Subsets (Baseline Melanoma Samples)
    print("\n--- Task 4: Exploring Baseline Melanoma Samples ---")
    # Fetch relevant sample and subject info from DB for this query
    all_sample_subject_data = database.fetch_samples_with_subject_info() 
    if not all_sample_subject_data.empty:
        baseline_melanoma_samples_df, aggregated_counts = analysis.query_baseline_melanoma_tr1_samples(all_sample_subject_data)
        if not baseline_melanoma_samples_df.empty:
            print("\nBaseline Melanoma PBMC Samples (Treatment tr1) - First 5 rows:")
            print(baseline_melanoma_samples_df.head().to_string())
    else:
        print("Cannot explore baseline samples: no sample/subject data available.")

if __name__ == "__main__":
    main()
    