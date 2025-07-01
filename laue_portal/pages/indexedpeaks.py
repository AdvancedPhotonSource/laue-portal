import dash
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
from dash.exceptions import PreventUpdate
import laue_portal.database.db_utils as db_utils
import laue_portal.database.db_schema as db_schema
from sqlalchemy import select
from sqlalchemy.orm import Session
import pandas as pd
import laue_portal.components.navbar as navbar

dash.register_page(__name__)

layout = html.Div([
        navbar.navbar,
        dcc.Location(id='url', refresh=False),
        dbc.Container(fluid=True, className="p-0", children=[
            dag.AgGrid(
                id='peakindex-table',
                columnSize="responsiveSizeToFit",
                dashGridOptions={"pagination": True, "paginationPageSize": 20, "domLayout": 'autoHeight'},
                style={'height': 'calc(100vh - 150px)', 'width': '100%'},
                className="ag-theme-alpine"
            )
        ])
    ],
)

"""
=======================
Callbacks
=======================
"""
VISIBLE_COLS = [
    db_schema.PeakIndex.peakindex_id,
    # db_schema.PeakIndex.dataset_id,
    db_schema.PeakIndex.scanNumber,
    db_schema.PeakIndex.recon_id,
    db_schema.PeakIndex.wirerecon_id,
    # db_schema.PeakIndexResults.structure,
    db_schema.PeakIndex.boxsize,
    db_schema.PeakIndex.threshold,
    db_schema.Job.submit_time,
    db_schema.Job.start_time,
    db_schema.Job.finish_time,
    db_schema.Job.status,
    db_schema.Job.author,
    db_schema.Job.notes,
]

CUSTOM_HEADER_NAMES = {
    'peakindex_id': 'Peak Index ID',
    'scanNumber': 'Scan ID',
    'recon_id': 'Recon ID', #'ReconID',
    'wirerecon_id': 'Wire Recon ID', #'ReconID',
        #'': 'Points',
    'boxsize': 'Box',
    'submit_time,': 'Date',
}

def _get_peakindexs():
    with Session(db_utils.ENGINE) as session:
        peakindexs = pd.read_sql(session.query(*VISIBLE_COLS)
            .join(db_schema.Job, db_schema.PeakIndex.job_id == db_schema.Job.job_id)
            .statement, session.bind)

    cols = []
    for col in VISIBLE_COLS:
        field_key = col.key
        header_name = CUSTOM_HEADER_NAMES.get(field_key, field_key.replace('_', ' ').title())
        
        col_def = {
            'headerName': header_name,
            'field': field_key,
            'filter': True, 
            'sortable': True, 
            'resizable': True,
            'floatingFilter': True,
            'unSortIcon': True,
        }
        if field_key == 'peakindex_id':
            col_def['cellRenderer'] = 'PeakIndexLinkRenderer'
        elif field_key == 'recon_id':
            col_def['cellRenderer'] = 'ReconLinkRenderer'
        elif field_key == 'wirerecon_id':
            col_def['cellRenderer'] = 'WireReconLinkRenderer'
        elif field_key == 'dataset_id':
            col_def['cellRenderer'] = 'DatasetIdScanLinkRenderer'
        elif field_key == 'scanNumber':
            col_def['cellRenderer'] = 'ScanLinkRenderer'  # Use the custom JS renderer
        cols.append(col_def)

    return cols, peakindexs.to_dict('records')

@dash.callback(
    Output('peakindex-table', 'columnDefs'),
    Output('peakindex-table', 'rowData'),
    Input('url','pathname'),
    prevent_initial_call=True,
)
def get_peakindexs(path):
       if path == '/indexedpeaks':
            cols, peakindexs_records = _get_peakindexs()
            return cols, peakindexs_records
       else:
            raise PreventUpdate
