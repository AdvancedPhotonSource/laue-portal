import dash
from dash import html, dcc, callback, Input, Output, State, set_props, ctx
import dash_bootstrap_components as dbc
import laue_portal.pages.ui_shared as ui_shared
from dash import dcc, ctx
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

dash.register_page(__name__)

CUSTOM_HEADER_NAMES = {
    'peakindex_id': 'Peak Index ID',
    'dataset_id': 'Scan ID',
}

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
def _get_peakindexs():
    with Session(db_utils.ENGINE) as session:
        peakindexs_df = pd.read_sql(session.query(*VISIBLE_COLS).statement, session.bind)

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
        if field_key == 'peakindex_id':
            col_def['cellRenderer'] = 'PeakIndexLinkRenderer'
        elif field_key == 'dataset_id':
            col_def['cellRenderer'] = 'DatasetIdScanLinkRenderer'
        cols.append(col_def)

    return cols, peakindexs_df.to_dict('records')


VISIBLE_COLS = [
    db_schema.PeakIndex.peakindex_id,
    db_schema.PeakIndex.date,
    db_schema.PeakIndex.dataset_id,
    db_schema.PeakIndex.notes,
]


@dash.callback(
    Output('peakindex-table', 'columnDefs', allow_duplicate=True),
    Output('peakindex-table', 'rowData', allow_duplicate=True),
    Input('url','pathname'),
    prevent_initial_call=True,
)
def get_peakindexs(path):
       if path == '/indexedpeaks':
            cols, peakindexs_records = _get_peakindexs()
            return cols, peakindexs_records
       else:
            raise PreventUpdate