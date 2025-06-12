# Melanoma Treatment Response Analysis
### Getting Started

Follow these instructions to set up the project environment and run the analysis.

#### Prerequisites

- Python 3.x installed
- pip (Python package installer)

#### Installation

- Clone the repository (or download and extract the project files): 
```bash
git clone https://github.com/your_username/cytometry_analysis.git # Replace with your repo URL
cd cytometry_analysis # Navigate into the project directory
```

- Create a Python virtual environment (highly recommended to manage dependencies):
```bash
python -m venv venv
```

#### Activate the virtual environment:

- macOS/Linux: 
```bash
source venv/bin/activate
```

- Windows (Command Prompt):
```bash
.\venv\Scripts\activate
```

- Windows (PowerShell): 
```bash
.\venv\Scripts\Activate.ps1 
```
(You'll see `(venv)` appear in your terminal prompt when activated.)

#### Running the Application

- Ensure cell-count.csv is located in the root directory of your project.
- Delete cell_counts.db if it exists from a previous run. This ensures a clean database is created for each execution. (Alternatively, the initialize_db function in database.py can be modified to automatically delete it if it exists.)
- Execute the main script from your terminal (with the virtual environment active):
```bash
python main.py
```

### Expected Outputs:

Upon successful execution, the application will:

- Display extensive logs and results in the console, including:
    - Database initialization messages.
    - Summary of samples and subjects included in the analysis.
    - Head of the calculated relative frequencies DataFrame.
    - Detailed statistical comparison for each immune cell population, showing mean frequencies, U-statistic, P-value, and a conclusion on significance.
- Generate the following files in your project's root directory:
    - `cell_counts.db`: The populated SQLite database file.
    - `relative_frequencies_summary.csv`: A CSV file containing the calculated relative frequencies, total cell counts, and percentages for every cell population in each sample.
    - `melanoma_tr1_response_boxplots.png`: An image file showcasing boxplots that visually compare the relative frequencies of each immune cell population between responders and non-responders.

### Key Findings

Based on the analysis of the provided `cell-count.csv` data for melanoma patients receiving `tr1` treatment (PBMC samples):

- The `cd4_t_cell` population showed a statistically significant difference (P-value < 0.05) in relative frequencies between responders and non-responders. This suggests that the relative abundance of `cd4_t_cells` may serve as a potential biomarker or indicator associated with treatment response.
- The generated boxplots visually support these observed differences, providing an intuitive understanding of the data distribution for each group.


### Relational Database Schema Explanation and Design Rationale

The project utilizes an SQLite relational database (`cell_counts.db`) to store and manage the cytometry data. The schema is designed for clarity, normalization, and efficient querying.

#### Schema Design:

The database is composed of several tables linked by primary and foreign keys:

- `projects` Table:
    - `project_id` (PRIMARY KEY, TEXT): Unique identifier for each research project.
- `subjects` Table:
    - `subject_id` (PRIMARY KEY, TEXT): Unique identifier for each patient/subject.
    - `project_id`(FOREIGN KEY, TEXT): Links to the `projects` table.
    - `age` (INTEGER): Age of the subject.
    - `sex` (TEXT): Sex of the subject.
- `samples` Table:
    - `sample_id` (PRIMARY KEY, TEXT): Unique identifier for each biological sample.
    - `subject_id` (FOREIGN KEY, TEXT): Links to the `subjects` table.
    - `condition` (TEXT): Disease condition (e.g., 'melanoma').
    - `treatment` (TEXT): Treatment received (e.g., 'tr1').
    - `response` (TEXT): Treatment response (`'y'` for responder, `'n'` for non-responder).
    - `sample_type` (TEXT): Type of sample (e.g., 'PBMC').
    - `time_from_treatment_start` (INTEGER): Time point relative to treatment initiation.
- `cell_counts` Table:
    - `id` (PRIMARY KEY, INTEGER): Auto-incrementing unique identifier for each cell count entry.
    - `sample_id` (FOREIGN KEY, TEXT): Links to the `samples` table.
    - `population` (TEXT): Name of the immune cell population (e.g., 'b_cell', 'cd8_t_cell').
    - `count` (INTEGER): The raw cell count for that specific population in the sample.

#### Design Rationale and Scalability:

- Normalization: The design follows principles of database normalization (e.g., 3NF), which reduces data redundancy and improves data integrity.
    - projects, subjects, and samples are separated to avoid repeating project, subject, or sample metadata for each cell count entry.
    - cell_counts is a granular table, storing individual population counts, linking back to the samples table.
    - Clarity and Maintainability: Each table has a clear, singular purpose, making the schema easy to understand and maintain. Changes to subject demographics, for example, only affect the subjects table.
- Query Efficiency:
    - Targeted Queries: Analysts can easily query specific subsets of data without having to process unnecessary information (e.g., fetching only cell_counts or only samples with subjects information). This is evident in the database.py functions like fetch_cell_counts() or fetch_samples_with_subject_info().
    - Indexed Joins: Primary and Foreign Keys naturally support indexing, which significantly speeds up JOIN operations, crucial for combining data from multiple tables for analysis.
- Scalability:
    - Hundreds of Projects/Thousands of Samples: The relational model scales well. Adding new projects, subjects, or samples simply means adding new rows to the respective tables. The relationships (FOREIGN KEYs) ensure that all data remains linked. The database can efficiently handle many-to-one relationships (e.g., one subject can have many samples, one sample can have many cell populations).
    - Various Types of Analytics: The normalized structure provides flexibility for diverse analytical needs:
        - Project-level analysis: Easy to aggregate data by project_id.
        - Subject-level analysis: Easy to group by subject_id to study patient-specific trends.
        - Sample-level analysis: samples table provides metadata for filtering based on condition, treatment, time_from_treatment_start, etc.
        - Cell population-specific analysis: The cell_counts table allows for direct analysis of specific immune cell populations across samples or subjects.
    - Data Integrity: Constraints (like UNIQUE for sample_id in samples and subject_id in subjects) ensure that critical identifiers remain unique, preventing data corruption as the database grows.

### Code Structure and Design Rationale

The project is structured into modular Python files, each with a specific responsibility, promoting separation of concerns, readability, and maintainability.

#### Code Structure:
```bash
cytometry_analysis/
├── main.py
├── database.py
├── analysis.py
├── visualization.py
├── cell-count.csv
├── requirements.txt
└── README.md`
```
#### Design Rationale:

- Modularity and Separation of Concerns:
    - `database.py`: Dedicated solely to interacting with the SQLite database. It handles database initialization, data loading from CSV, and all data retrieval (CRUD operations). This means any changes to the database schema or underlying data storage logic are contained within this file.
    - `analysis.py`: Focuses purely on data processing and statistical analysis. It takes clean data (often returned by database.py) and performs calculations (like relative frequencies) and statistical tests. It doesn't worry about how data is stored or visualized.
    - `visualization.py`: Responsible for generating all plots and charts. It takes processed data and creates visual representations, ensuring consistent plotting styles and saving mechanisms. It doesn't handle data analysis or database interactions.
    - `main.py`: Acts as the orchestrator or entry point of the application. It ties all the other modules together, defining the overall workflow (initialize DB -> load data -> perform analysis -> generate plots -> print summaries). It minimizes core logic and primarily manages the flow.
- Readability and Maintainability: By breaking down the project into smaller, focused modules, the code becomes easier to read, understand, and debug. A developer can quickly locate the relevant section of code for a specific task (e.g., database issues go to database.py).
- Reusability: Functions within each module are designed to be reusable. For instance, database.fetch_samples_with_subject_info() can be used by various analysis functions, not just one specific analysis. Similarly, plotting functions in visualization.py could be adapted for different datasets if needed.
- Testability: The modular design facilitates unit testing. Each function and module can be tested independently, ensuring their correctness before integrating them into the larger system.
- Scalability of Development: If the project grows, new analysis methods or visualization types can be added by creating new functions within existing modules or adding new modules, without significantly altering the core logic of other parts of the system. For example, if a new machine learning prediction model is added, it might go into a new predict.py file, drawing data from database.py and potentially using results from analysis.py.

### Technologies Used

- Python 3.x
- Pandas (for efficient data manipulation and analysis)
- Matplotlib (for creating static, animated, and interactive visualizations)
- Seaborn (for aesthetically pleasing statistical graphics built on Matplotlib)
- SciPy (for scientific computing, including statistical tests)
- SQLite3 (for lightweight, file-based relational database management)