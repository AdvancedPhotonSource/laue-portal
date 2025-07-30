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
            # Initialize duration column
            subjobs['duration'] = None
            subjobs['duration_display'] = None
            
            # Calculate durations for completed subjobs
            completed_mask = subjobs['start_time'].notna() & subjobs['finish_time'].notna()
            subjobs.loc[completed_mask, 'duration'] = subjobs.loc[completed_mask, 'finish_time'] - subjobs.loc[completed_mask, 'start_time']
            subjobs.loc[completed_mask, 'duration_display'] = subjobs.loc[completed_mask, 'duration'].astype(str)
            
            # Calculate durations for running subjobs
            running_mask = subjobs['start_time'].notna() & subjobs['finish_time'].isna()
            subjobs.loc[running_mask, 'duration'] = current_time - subjobs.loc[running_mask, 'start_time']
            subjobs.loc[running_mask, 'duration_display'] = subjobs.loc[running_mask, 'duration'].astype(str) + ' (running)'
        
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
        # Skip internal columns
        if field_key in ['row_type', 'parent_job_id', '_subjobs', 'completed_subjobs', 'failed_subjobs', 'running_subjobs', 'queued_subjobs', 'duration'] + [col.key for col in REFERENCE_COLS]:
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
        elif field_key == 'dataset_id':
            col_def['cellRenderer'] = 'DatasetIdScanLinkRenderer'
        elif field_key == 'scanNumber':
            col_def['cellRenderer'] = 'ScanLinkRenderer'  # Use the custom JS renderer
        elif field_key in ['submit_time', 'start_time', 'finish_time']:
            col_def['cellRenderer'] = 'DateFormatter'  # Use the date formatter for datetime fields
        elif field_key == 'status':
            col_def['cellRenderer'] = 'StatusRenderer'  # Use custom status renderer
        elif field_key == 'total_subjobs':
            col_def['headerName'] = 'SubJobs Progress'
            col_def['cellRenderer'] = 'SubJobProgressRenderer'
            col_def['width'] = 200
        
        cols.append(col_def)

    # Add the custom actions column
    cols.append({
        'headerName': 'Actions',
        'field': 'actions',  # This field doesn't need to exist in the data
        # 'cellRenderer': 'ActionButtonsRenderer',
        'sortable': False,
        'filter': False,
        'resizable': True, # Or False, depending on preference
        'suppressMenu': True, # Or False
        'width': 200 # Adjusted width for DBC buttons
    })

    # Add combined fields columns
    col_def = {
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
        'resizable': True, # Or False, depending on preference
        'suppressMenu': True, # Or False
        'width': 200 # Adjusted width for DBC buttons
    }
    
    col_def.update({
        'filter': True, 
        'sortable': True, 
        'resizable': True,
        'suppressMenuHide': True
    })
    cols.insert(1,col_def)
    
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
