import dash
from dash import html, dcc, Input, Output, State, set_props, ctx
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
from dash.exceptions import PreventUpdate
import laue_portal.database.db_utils as db_utils
import laue_portal.database.db_schema as db_schema
from sqlalchemy import select
from sqlalchemy.orm import Session
import pandas as pd
import base64
import yaml
import datetime
import laue_portal.components.navbar as navbar

dash.register_page(__name__, path='/')

layout = html.Div([
        navbar.navbar,
        dcc.Location(id='url', refresh=False),
        dbc.Container(fluid=True, className="p-0", children=[ 
            dag.AgGrid(
                id='metadata-table',
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

CUSTOM_HEADER_NAMES = {
    'scanNumber': 'Scan ID',
    'calib_id': 'Calibration ID',
    'dataset_id': 'Dataset ID',
    # Add more custom names here as needed, e.g.:
    # 'date': 'Date of Scan',
}

def _get_metadatas():
    with Session(db_utils.ENGINE) as session:
        metadatas = pd.read_sql(session.query(*VISIBLE_COLS).statement, session.bind)

    # Format columns for ag-grid
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
            'suppressMenuHide': True
        }

        if field_key == 'scanNumber':
            col_def['cellRenderer'] = 'ScanLinkRenderer'  # Use the custom JS renderer
        
        cols.append(col_def)

    # Add the custom actions column
    cols.append({
        'headerName': 'Actions',
        'field': 'actions',  # This field doesn't need to exist in the data
        'cellRenderer': 'ActionButtonsRenderer',
        'sortable': False,
        'filter': False,
        'resizable': True, # Or False, depending on preference
        'suppressMenu': True, # Or False
        'width': 200 # Adjusted width for DBC buttons
    })
    # metadatas['id'] = metadatas['scanNumber'] # This was for dash_table and is not directly used by ag-grid unless getRowId is configured

    return cols, metadatas.to_dict('records')



VISIBLE_COLS = [
    db_schema.Metadata.scanNumber,
    db_schema.Metadata.date,
    db_schema.Metadata.calib_id,
    db_schema.Metadata.dataset_id,
    db_schema.Metadata.notes,
]


@dash.callback(
    Output('metadata-table', 'columnDefs', allow_duplicate=True),
    Output('metadata-table', 'rowData', allow_duplicate=True),
    Input('url','pathname'),
    prevent_initial_call=True,
)
def get_metadatas(path):
       if path == '/':
            cols, metadatas_records = _get_metadatas()
            return cols, metadatas_records
       else:
            raise PreventUpdate
