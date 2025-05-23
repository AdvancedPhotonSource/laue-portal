# Laue Portal

A comprehensive web-based platform for Laue X-ray diffraction data analysis and reconstruction, designed for synchrotron beamline operations at the APS 3DMN beamline: 34-IDE.


Laue Portal is a Dash-based web application that provides an integrated workflow for processing and analyzing Laue diffraction patterns. The platform combines data management, peak indexing, and 3D reconstruction capabilities with an intuitive web interface for researchers working with polychromatic X-ray diffraction data.


### Prerequisites
- Python 3.12
- SQLite
- HDF5 libraries

### Setup
1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd laue-portal
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python lau_dash.py
   ```

4. Access the web interface at `http://localhost:2052`

## Architecture

### Core Components

- **`lau_dash.py`**: Main Dash application entry point
- **`laue_portal/`**: Core application package
  - **`pages/`**: Web interface pages (scans, reconstructions, peak indexing)
  - **`components/`**: Reusable UI components and forms
  - **`database/`**: Database schema and utilities
  - **`recon/`**: Reconstruction algorithms and analysis tools


### Workflow Integration

- **`polaris_workflow/`**: Integration with Argonne's Polaris supercomputer
- **`gladier`**: Workflow orchestration for distributed computing
- **Remote Processing**: Automated data transfer and processing on HPC resources


## Configuration

Key configuration files:
- **`config.py`**: Database and application settings
- **`polaris_workflow/funcx_launch/laue_conf.json`**: HPC workflow configuration
- **`requirements.txt`**: Python dependencies


## Testing

Run the test suite:
```bash
python -m unittest discover -s tests -p 'test_*.py'
```

