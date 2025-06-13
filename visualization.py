'''# visualization.py
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
    '''

# visualization.py
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd # Ensure pandas is imported if not already

def plot_relative_frequencies_boxplot(data_df, output_filename="response_comparison_boxplots.png"):
    """
    Generates boxplots of relative frequencies comparing responders vs. non-responders
    using Matplotlib/Seaborn and saves them to a file.
    
    Args:
        data_df (pd.DataFrame): Filtered DataFrame from analyze_melanoma_tr1_response.
                                 Expected to be in long format with 'population', 'percentage', 'response' columns.
        output_filename (str): Name for the output image file.
    """
    if data_df.empty:
        print("No data to plot for relative frequencies boxplot.")
        return

    # Ensure 'response' column is treated as categorical for consistent plotting order
    # Also, ensure 'y' and 'n' are the only values, or handle others appropriately
    data_df['response'] = pd.Categorical(data_df['response'], categories=['n', 'y'], ordered=True)

    cell_populations = ['b_cell', 'cd8_t_cell', 'cd4_t_cell', 'nk_cell', 'monocyte']

    # Adjust figure size based on number of plots to prevent squishing
    num_plots = len(cell_populations)
    fig_width = max(10, num_plots * 3) # Min 10, 3 inches per plot
    fig_height = 8 # Height per plot

    plt.figure(figsize=(fig_width, fig_height))
    sns.set_style("whitegrid")

    for i, pop in enumerate(cell_populations):
        # Filter for the current population
        pop_data = data_df[data_df['population'] == pop].copy()
        
        # Ensure there is data for both 'y' and 'n' responses for this population
        if not pop_data.empty and pop_data['response'].nunique() > 1:
            ax = plt.subplot(1, num_plots, i + 1)
            # Use 'hue' only if 'response' is a reliable categorical variable
            sns.boxplot(data=pop_data, x='response', y='percentage', hue='response', palette={'y': '#3B82F6', 'n': '#EF4444'}, ax=ax, legend=False)
            ax.set_title(f'{pop} Relative Frequency')
            ax.set_xlabel('Treatment Response')
            ax.set_ylabel('Relative Frequency (%)')
            ax.set_xticks(ticks=[0, 1])
            ax.set_xticklabels(['Non-Responder (n)', 'Responder (y)'])
        else:
            ax = plt.subplot(1, num_plots, i + 1)
            ax.text(0.5, 0.5, 'Insufficient Data', horizontalalignment='center', verticalalignment='center', transform=ax.transAxes)
            ax.set_title(f'{pop} Relative Frequency')
            ax.set_xlabel('Treatment Response')
            ax.set_ylabel('Relative Frequency (%)')
            ax.set_xticks([]) # Hide ticks if no plot
            ax.set_yticks([])

    plt.tight_layout()
    plt.suptitle("Relative Frequencies by Treatment Response (Melanoma, tr1, PBMC)", y=1.02, fontsize=16)
    plt.savefig(output_filename, dpi=300, bbox_inches='tight')
    print(f"Boxplots saved to {output_filename}")
    # plt.show() # Removed plt.show() for CLI batch processing, uncomment if you want immediate display
    plt.close() # Close figure to free up memory