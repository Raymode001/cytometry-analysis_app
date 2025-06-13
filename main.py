# main.py (for CLI)
import database
import analysis
import visualization # This import is specifically for CLI's static plotting needs
import pandas as pd
import os # To handle DB file for CLI
import argparse
from data_loader import DataLoader
from analysis import CytometryAnalysis


def main():
    parser = argparse.ArgumentParser(description='Cytometry Data Analysis Tool')
    parser.add_argument('--csv', required=True, help='Path to the cell-count.csv file')
    parser.add_argument('--output-dir', default='output', help='Directory for output files')
    args = parser.parse_args()
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Initialize data loader and analysis
    data_loader = DataLoader()
    analysis = CytometryAnalysis(data_loader)
    
    # Load data
    print("Loading data from CSV...")
    data_loader.load_csv(args.csv)
    
    # Generate analyses
    print("\nGenerating analyses...")
    
    # Cell frequencies
    print("Calculating cell frequencies...")
    cell_freq = analysis.analyze_cell_frequencies()
    cell_freq.to_csv(os.path.join(args.output_dir, 'cell_frequencies.csv'), index=False)
    
    # Response comparison
    print("Analyzing response comparison...")
    response_comp, sig_pops = analysis.analyze_response_comparison()
    response_comp.to_csv(os.path.join(args.output_dir, 'response_comparison.csv'), index=False)
    
    # Plot response comparison
    print("Generating response comparison plot...")
    analysis.plot_response_comparison(
        save_path=os.path.join(args.output_dir, 'response_comparison.png')
    )
    
    # Baseline analysis
    print("Analyzing baseline melanoma tr1 samples...")
    baseline = analysis.analyze_baseline_melanoma_tr1()
    baseline.to_csv(os.path.join(args.output_dir, 'baseline_analysis.csv'), index=False)
    
    # Generate summary report
    print("Generating summary report...")
    summary = analysis.generate_summary_report(
        output_path=os.path.join(args.output_dir, 'summary_report.txt')
    )
    
    print("\nAnalysis complete! Output files are in:", args.output_dir)
    print("\nSummary Report:")
    print(summary)


# Helper for CLI to fetch wide data (mimics app.py's get_all_data_for_display)
def _get_all_data_wide_for_cli():
    """
    Fetches all data from DB, pivots cell counts to columns, and returns a wide-format DataFrame.
    This is a copy of the logic in app.py's get_all_data_for_display, for CLI independence.
    """
    conn = database.get_db_connection()
    try:
        query = """
        SELECT
            p.project_id AS project,
            s.subject_id AS subject,
            samp.condition,
            s.age,
            s.sex,
            samp.treatment,
            samp.response,
            samp.sample_id AS sample,
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
        GROUP BY p.project_id, s.subject_id, samp.condition, s.age, s.sex, samp.treatment, samp.response,
                 samp.sample_id, samp.sample_type, samp.time_from_treatment_start
        ORDER BY samp.sample_id;
        """
        df = pd.read_sql_query(query, conn)
    except Exception as e:
        print(f"CLI Data Fetch Error: {e}")
        return pd.DataFrame()
    finally:
        conn.close()
    return df


if __name__ == "__main__":
    main()
    