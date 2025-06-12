# visualization.py
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

def plot_relative_frequencies_boxplot(data_df, output_filename="response_comparison_boxplots.png"):
    """
    Generates boxplots of relative frequencies comparing responders vs. non-responders.
    
    Args:
        data_df (pd.DataFrame): Filtered DataFrame from analyze_melanoma_tr1_response.
        output_filename (str): Name for the output image file.
    """
    if data_df.empty:
        print("No data to plot for relative frequencies boxplot.")
        return

    cell_populations = ['b_cell', 'cd8_t_cell', 'cd4_t_cell', 'nk_cell', 'monocyte']

    plt.figure(figsize=(15, 8))
    sns.set_style("whitegrid")

    for i, pop in enumerate(cell_populations):
        plt.subplot(1, len(cell_populations), i + 1)
        sns.boxplot(data=data_df[data_df['population'] == pop], x='response', y='percentage', hue='response',palette='viridis',legend=False)
        plt.title(f'{pop} Relative Frequency')
        plt.xlabel('Treatment Response')
        plt.ylabel('Relative Frequency (%)')
        plt.xticks(ticks=[0, 1], labels=['Non-Responder (n)', 'Responder (y)']) # Explicitly set labels for clarity

    plt.tight_layout()
    plt.suptitle("Relative Frequencies by Treatment Response (Melanoma, tr1, PBMC)", y=1.02, fontsize=16)
    plt.savefig(output_filename, dpi=300, bbox_inches='tight')
    print(f"Boxplots saved to {output_filename}")
    plt.show()