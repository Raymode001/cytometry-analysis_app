# Cytometry Data Analysis Dashboard

A comprehensive web application for analyzing and visualizing cytometry data, built with Dash and Python.

## Features

- **Data Management**
  - Upload data via CSV files
  - Interactive data table with editing capabilities
  - Add/remove samples
  - Export data to CSV format

- **Analysis Tools**
  - Relative frequency calculations
  - Response analysis with statistical testing
  - Baseline sample queries
  - Interactive visualizations

- **Visualization**
  - Box plots for response analysis
  - Interactive tables with sorting and filtering
  - Export plots as PNG files

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd cytometry_analysis
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Start the application:
```bash
python app.py
```

2. Open your web browser and navigate to:
```
http://localhost:8050
```

### Data Management

- **Upload Data**: Use the CSV upload section to add new samples
- **Edit Data**: Modify values directly in the interactive table
- **Delete Samples**: Remove samples using the delete functionality
- **Export Data**: Download the current dataset as a CSV file

### Analysis

1. **Relative Frequencies**
   - View cell population percentages
   - Sort and filter the data
   - Export results

2. **Response Analysis**
   - Run statistical comparisons
   - View box plots for different cell populations
   - Export plots as PNG files

3. **Baseline Queries**
   - Analyze baseline samples
   - View subject demographics
   - Export analysis results

## Data Format

The application expects CSV files with the following columns:
- project
- subject
- age
- sex
- sample
- condition
- treatment
- response
- sample_type
- time_from_treatment_start
- b_cell
- cd8_t_cell
- cd4_t_cell
- nk_cell
- monocyte

## Development

### Project Structure
```
cytometry_analysis/
├── app.py              # Main application file
├── analysis.py         # Analysis functions
├── database.py         # Database operations
├── data_loader.py      # Data loading utilities
├── schema.py           # Database schema
├── requirements.txt    # Python dependencies
├── runtime.txt         # Python runtime version
└── Procfile           # Deployment configuration
```

### Dependencies

Key Python packages:
- dash
- pandas
- plotly
- sqlite3

See `requirements.txt` for the complete list.

## Deployment

The application is configured for deployment with:
- `Procfile` for process management
- `runtime.txt` for Python version specification
- Database persistence configuration

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request
