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
                    "masterDetail": True,
                    "detailRowHeight": 200,
                    "detailCellRenderer": "SubJobDetailRenderer",
                    "detailCellRendererParams": {
                        "detailGridOptions": {
                            "columnDefs": [
                                {"field": "subjob_id", "headerName": "SubJob ID", "width": 100},
                                {"field": "status", "headerName": "Status", "cellRenderer": "StatusRenderer", "width": 120},
                                {"field": "start_time", "headerName": "Start Time", "cellRenderer": "DateFormatter", "width": 180},
                                {"field": "duration", "headerName": "Duration", "width": 120},
                                {"field": "messages", "headerName": "Messages", "flex": 1}
                            ],
                            "defaultColDef": {
                                "sortable": True,
                                "filter": True,
                                "resizable": True
                            }
                        }
                    },
                    "getDetailRowData": {"function": "params => params.successCallback(params.data.subjobs || [])"},
                    "isRowMaster": {"function": "dataItem => (dataItem.total_subjobs || 0) > 0"}
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
}

def _get_jobs():
    with Session(db_utils.ENGINE) as session:
        # Query all subjobs once
        subjobs = pd.read_sql(
            session.query(db_schema.SubJob)
            .order_by(db_schema.SubJob.subjob_id)
            .statement, session.bind
        )
        
        # Calculate subjob statistics from the single query
        subjob_stats_df = pd.DataFrame()
        if not subjobs.empty:
            # Calculate statistics using pandas
            subjob_stats_df = subjobs.groupby('job_id').agg({
                'subjob_id': 'count',
                'status': [
                    lambda x: (x == STATUS_REVERSE_MAPPING["Finished"]).sum(),
                    lambda x: (x == STATUS_REVERSE_MAPPING["Failed"]).sum(),
                    lambda x: (x == STATUS_REVERSE_MAPPING["Running"]).sum(),
                    lambda x: (x == STATUS_REVERSE_MAPPING["Queued"]).sum()
                ]
            })
            subjob_stats_df.columns = ['total_subjobs', 'completed_subjobs', 'failed_subjobs', 'running_subjobs', 'queued_subjobs']
            subjob_stats_df = subjob_stats_df.reset_index()
        
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
        else:
            # Add empty columns if no subjobs exist
            for col in ['total_subjobs', 'completed_subjobs', 'failed_subjobs', 'running_subjobs', 'queued_subjobs']:
                jobs[col] = 0
        
        # Fill NaN values with 0 for jobs without subjobs
        for col in ['total_subjobs', 'completed_subjobs', 'failed_subjobs', 'running_subjobs', 'queued_subjobs']:
            jobs[col] = jobs[col].fillna(0).astype(int)
        
        # Add subjobs detail to jobs dataframe
        if not subjobs.empty:
            # Calculate duration for each subjob
            subjobs['duration'] = subjobs.apply(
                lambda row: str(row['finish_time'] - row['start_time']) if pd.notna(row['start_time']) and pd.notna(row['finish_time']) else None,
                axis=1
            )
            # Group subjobs by job_id
            subjobs_by_job = subjobs.groupby('job_id').apply(lambda x: x.to_dict('records')).to_dict()
            jobs['subjobs'] = jobs['job_id'].map(subjobs_by_job).fillna([]).apply(list)
        else:
            jobs['subjobs'] = [[] for _ in range(len(jobs))]

    # Format columns for ag-grid
    cols = []
    
    # Add expand/collapse column for master-detail (if there are subjobs)
    if jobs['total_subjobs'].sum() > 0:
        cols.append({
            'field': 'expand',
            'headerName': '',
            'cellRenderer': 'agGroupCellRenderer',
            'width': 50,
            'resizable': False,
            'suppressMenu': True,
            'sortable': False,
            'filter': False
        })
    
    # Get list of reference column names to exclude
    reference_col_names = [col.key for col in REFERENCE_COLS]
    
    for field_key in jobs.columns:
        # Skip subjobs detail and internal subjob stat columns
        if field_key in ['subjobs', 'completed_subjobs', 'failed_subjobs', 'running_subjobs', 'queued_subjobs'] + reference_col_names:
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
    
    return cols, jobs.to_dict('records')

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
