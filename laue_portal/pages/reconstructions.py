import dash
from dash import html, dcc, ctx, Input, Output, State, set_props, ctx
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
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import h5py
import laue_portal.components.navbar as navbar
from laue_portal.components.recon_form import recon_form, set_recon_form_props

dash.register_page(__name__)

CUSTOM_HEADER_NAMES = {
    'scanNumber': 'Scan ID',
    'calib_id': 'Calibration ID',
    'dataset_id': 'Dataset ID',
    'recon_id': 'Recon ID',
    # Add more custom names here as needed, e.g.:
    # 'date': 'Date of Scan',
}

layout = html.Div([
        navbar.navbar,
        dcc.Location(id='url', refresh=False),
        dbc.Container(fluid=True, className="p-0", children=[
            dag.AgGrid(
                id='recon-table',
                columnSize="responsiveSizeToFit",
                dashGridOptions={"pagination": True, "paginationPageSize": 20, "domLayout": 'autoHeight'},
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
def _get_recons():
    with Session(db_utils.ENGINE) as session:
        recons = pd.read_sql(session.query(*VISIBLE_COLS).statement, session.bind)

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

        if field_key == 'recon_id':
            col_def['cellRenderer'] = 'ReconLinkRenderer'
        elif field_key == 'dataset_id':
            col_def['cellRenderer'] = 'DatasetIdScanLinkRenderer'
        elif field_key == 'scanNumber':
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
    # recons['id'] = recons['scanNumber'] # This was for dash_table and is not directly used by ag-grid unless getRowId is configured
    
    return cols, recons.to_dict('records')


VISIBLE_COLS = [
    db_schema.Recon.recon_id,
    db_schema.Recon.date,
    db_schema.Recon.calib_id,
    db_schema.Recon.dataset_id,
    #db_schema.Recon.scanNumber,
    db_schema.Recon.notes,
]


@dash.callback(
    Output('recon-table', 'columnDefs', allow_duplicate=True),
    Output('recon-table', 'rowData', allow_duplicate=True),
    Input('url','pathname'),
    prevent_initial_call=True,
)
def get_recons(path):
       if path == '/reconstructions':
            cols, recons = _get_recons()
            return cols, recons
       else:
            raise PreventUpdate