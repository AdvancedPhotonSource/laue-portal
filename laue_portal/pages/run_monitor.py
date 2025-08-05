import dash
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
from dash.exceptions import PreventUpdate
import laue_portal.database.db_utils as db_utils
import laue_portal.database.db_schema as db_schema
from laue_portal.processing.redis_utils import STATUS_MAPPING, STATUS_REVERSE_MAPPING
from sqlalchemy import select, func, case
from sqlalchemy.orm import Session
import pandas as pd 
import laue_portal.components.navbar as navbar
from datetime import datetime

dash.register_page(__name__)

layout = html.Div([
        navbar.navbar,
        dcc.Location(id='url', refresh=False),
        dbc.Container(fluid=True, className="p-0", children=[
            dag.AgGrid(
                id='job-table',
                columnSize="responsiveSizeToFit",
                dashGridOptions={
                    "pagination": True, 
                    "paginationPageSize": 20, 
                    "domLayout": 'autoHeight', 
                    "rowHeight": 32,
                    "animateRows": True,
                    # Custom row styling for subjobs
                    "getRowClass": {"function": "params => params.data.row_type === 'subjob' ? 'subjob-row' : ''"}
                },
                style={'height': 'calc(100vh - 150px)', 'width': '100%'},
                className="ag-theme-alpine"
            )
        ]),
    ],
)

"""
=======================
Callbacks
=======================
"""
REFERENCE_COLS = [
    db_schema.Calib.calib_id,
    db_schema.Recon.recon_id,
    db_schema.WireRecon.wirerecon_id,
    db_schema.PeakIndex.peakindex_id,
]

CUSTOM_HEADER_NAMES = {
    'wirerecon_id': 'Recon ID (Wire)', #'Wire Recon ID', #'ReconID',
    'scanNumber': 'Scan ID',
    'calib_id': 'Calibration ID',
    #'pxl_recon': 'Pixels'
    'submit_time': 'Date',
    'subjob_id': 'SubJob ID',
    'duration_display': 'Duration',
}

def calculate_duration_display(start_time, finish_time, current_time):
    """Calculate duration display string for jobs/subjobs"""
    if pd.notna(start_time):
        if pd.notna(finish_time):
            # Completed
            duration = finish_time - start_time
        else:
            # Running
            duration = current_time - start_time
        
        # Convert to total seconds and format as HH:MM:SS
        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        formatted = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        if pd.isna(finish_time):
            formatted += " (running)"
            
        return formatted
    return None

def _get_jobs():
    with Session(db_utils.ENGINE) as session:
        # Query all subjobs once
        subjobs = pd.read_sql(
            session.query(db_schema.SubJob)
            .order_by(db_schema.SubJob.subjob_id)
            .statement, session.bind
        )
        
        subjob_columns = ['total_subjobs', 'completed_subjobs', 'failed_subjobs', 'running_subjobs', 'queued_subjobs']

        # Calculate subjob statistics from the single query
        subjob_stats_df = pd.DataFrame()
        if not subjobs.empty:
            # Calculate statistics using pandas
            grouped_subjobs = subjobs.groupby('job_id')
            
            # Create the stats dataframe manually to avoid MultiIndex issues
            subjob_stats_df = pd.DataFrame({
                'job_id': list(grouped_subjobs.groups.keys()),
                'total_subjobs': grouped_subjobs.size().values,
                'completed_subjobs': grouped_subjobs['status'].apply(lambda x: (x == STATUS_REVERSE_MAPPING["Finished"]).sum()).values,
                'failed_subjobs': grouped_subjobs['status'].apply(lambda x: (x == STATUS_REVERSE_MAPPING["Failed"]).sum()).values,
                'running_subjobs': grouped_subjobs['status'].apply(lambda x: (x == STATUS_REVERSE_MAPPING["Running"]).sum()).values,
                'queued_subjobs': grouped_subjobs['status'].apply(lambda x: (x == STATUS_REVERSE_MAPPING["Queued"]).sum()).values
            })
        
        # Main query for jobs with related entities
        jobs = pd.read_sql(session.query(
                db_schema.Job,
                *REFERENCE_COLS
            )
            .outerjoin(db_schema.Calib, db_schema.Job.job_id == db_schema.Calib.job_id)
            .outerjoin(db_schema.Recon, db_schema.Job.job_id == db_schema.Recon.job_id)
            .outerjoin(db_schema.WireRecon, db_schema.Job.job_id == db_schema.WireRecon.job_id)
            .outerjoin(db_schema.PeakIndex, db_schema.Job.job_id == db_schema.PeakIndex.job_id)
            .order_by(db_schema.Job.job_id.desc())
            .statement, session.bind)
        
        # Merge subjob statistics with jobs
        if not subjob_stats_df.empty:
            jobs = jobs.merge(subjob_stats_df, on='job_id', how='left')
            # Fill NaN values with 0 for jobs without subjobs
            jobs[subjob_columns] = jobs[subjob_columns].fillna(0).astype(int)
        else:
            # Add empty columns if no subjobs exist
            jobs[subjob_columns] = 0
        
        # Pre-calculate durations for all subjobs to avoid time drift
        current_time = datetime.now()
        if not subjobs.empty:
            # Calculate duration display for all subjobs
            subjobs['duration_display'] = subjobs.apply(
                lambda row: calculate_duration_display(row['start_time'], row['finish_time'], current_time),
                axis=1
            )
        
        # Create a combined dataframe - initially only with jobs
        all_rows = []
        
        # Store all subjobs in a global variable for JavaScript access
        subjobs_dict = {}
        if not subjobs.empty:
            for job_id in jobs['job_id'].unique():
                job_subjobs = subjobs[subjobs['job_id'] == job_id]
                if not job_subjobs.empty:
                    subjobs_list = []
                    for _, subjob in job_subjobs.iterrows():
                        subjob_row = subjob.to_dict()
                        subjob_row['row_type'] = 'subjob'
                        subjob_row['parent_job_id'] = job_id
                        subjobs_list.append(subjob_row)
                    subjobs_dict[str(job_id)] = subjobs_list
        
        # Add job rows only (subjobs will be added dynamically)
        for _, job in jobs.iterrows():
            job_row = job.to_dict()
            job_row['row_type'] = 'job'
            # Store subjobs data in the job row for JavaScript access
            job_row['_subjobs'] = subjobs_dict.get(str(job_row['job_id']), [])
            # Add flag for auto-expansion if job has running subjobs
            job_row['_should_auto_expand'] = job_row.get('running_subjobs', 0) > 0
            # Calculate duration for job rows
            job_row['duration_display'] = calculate_duration_display(
                job_row.get('start_time'), 
                job_row.get('finish_time'), 
                current_time
            )
            all_rows.append(job_row)
        
        # Convert to DataFrame
        combined_df = pd.DataFrame(all_rows)

    # Format columns for ag-grid
    cols = []
    
    # Add expand/collapse column as the first column
    cols.append({
        'headerName': '',
        'field': 'expand',
        'width': 50,
        'resizable': False,
        'sortable': False,
        'filter': False,
        'suppressMenu': True,
        'cellRenderer': 'ExpandCollapseRenderer',
        'suppressSizeToFit': True,
        'cellStyle': {'overflow': 'visible'},
        'autoHeight': False
    })
    
    # Get all unique columns from combined dataframe
    all_columns = combined_df.columns.tolist()
    
    for field_key in all_columns:
        # Skip internal columns and special columns we'll add at specific positions
        if field_key in ['row_type', 'parent_job_id', '_subjobs', '_should_auto_expand', 'completed_subjobs', 'failed_subjobs', 'running_subjobs', 'queued_subjobs', 'duration', 'total_subjobs', 'finish_time', 'submit_time', 'duration_display'] + [col.key for col in REFERENCE_COLS]:
            continue
            
        header_name = CUSTOM_HEADER_NAMES.get(field_key, field_key.replace('_', ' ').title())
        
        col_def = {
            'headerName': header_name,
            'field': field_key,
            'filter': True, 
            'sortable': True, 
            'resizable': True,
            'suppressMenuHide': True
        }

        if field_key == 'job_id':
            col_def['cellRenderer'] = 'JobIdLinkRenderer'
            col_def['width'] = 175
        elif field_key == 'dataset_id':
            col_def['cellRenderer'] = 'DatasetIdScanLinkRenderer'
        elif field_key == 'scanNumber':
            col_def['cellRenderer'] = 'ScanLinkRenderer'  # Use the custom JS renderer
        elif field_key in ['submit_time', 'start_time', 'finish_time']:
            col_def['cellRenderer'] = 'DateFormatter'  # Use the date formatter for datetime fields
        elif field_key == 'status':
            col_def['cellRenderer'] = 'StatusRenderer'  # Use custom status renderer
        
        cols.append(col_def)

    # Create Job Reference column
    job_reference_col = {
        'headerName': 'Job Reference',
        'valueGetter': {"function": """ [
                    'calib_id',
                    'recon_id',
                    'wirerecon_id',
                    'peakindex_id'
        ];"""},
        'cellRenderer': 'JobRefsRenderer',
        'sortable': False,
        'filter': False,
        'resizable': True,
        'suppressMenu': True,
        'width': 250,
        'filter': True, 
        'sortable': True, 
        'resizable': True,
        'suppressMenuHide': True
    }
    
    # Create SubJobs Progress column
    subjobs_progress_col = None
    if 'total_subjobs' in all_columns:
        subjobs_progress_col = {
            'headerName': 'SubJobs Progress',
            'field': 'total_subjobs',
            'cellRenderer': 'SubJobProgressRenderer',
            'width': 200,
            'filter': True, 
            'sortable': True, 
            'resizable': True,
            'suppressMenuHide': True
        }

    # Insert Job Reference at position 2 (after expand column)
    cols.insert(2, job_reference_col)
    
    # Insert SubJobs Progress at position 5
    if subjobs_progress_col:
        cols.insert(5, subjobs_progress_col)
    
    # Create Duration column
    duration_col = {
        'headerName': 'Duration',
        'field': 'duration_display',
        'filter': True,
        'sortable': True,
        'resizable': True,
        'suppressMenuHide': True,
        'width': 200
    }
    
    # Insert Duration at position 8
    cols.insert(8, duration_col)

    # Add the custom actions column at the end
    cols.append({
        'headerName': 'Actions',
        'field': 'actions',  # This field doesn't need to exist in the data
        # 'cellRenderer': 'ActionButtonsRenderer',
        'sortable': False,
        'filter': False,
        'resizable': True,
        'suppressMenu': True,
        'width': 200
    })
    
    return cols, combined_df.to_dict('records')

@dash.callback(
    Output('job-table', 'columnDefs'),
    Output('job-table', 'rowData'),
    Input('url','pathname'),
    prevent_initial_call=True,
)
def get_jobs(path):
    if path == '/run-monitor':
        cols, jobs = _get_jobs()
        return cols, jobs
    else:
        raise PreventUpdate
