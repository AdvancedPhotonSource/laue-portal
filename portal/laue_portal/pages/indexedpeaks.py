import dash
from dash import html, dcc, callback, Input, Output, State, set_props, ctx
import dash_bootstrap_components as dbc
import laue_portal.pages.ui_shared as ui_shared
from dash import dcc, ctx, dash_table
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

dash.register_page(__name__)

layout = html.Div([
        ui_shared.navbar,
        dcc.Location(id='url', refresh=False),
        dbc.Row(
            [
                dash_table.DataTable(
                    id='peakindex-table',
                    filter_action="native",
                    sort_action="native",
                    sort_mode="multi",
                    page_action="native",
                    page_current= 0,
                    page_size= 20,
                )
            ],
            style={'width': '100%', 'overflow-x': 'auto'}
        ),
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("Header"), id="modal-details-header"),
                dbc.ModalBody(ui_shared.peakindex_form),
            ],
            id="modal-details",
            size="xl",
            is_open=False,
        ),
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("Header"), id="modal-results-header"),
                #dbc.ModalBody(html.H1("TODO: Results Display")),
                # html.Div(children=[
                    
                # ])
            ],
            id="modal-results",
            size="xl",
            is_open=False,
        ),
    ],
)

"""
=======================
Callbacks
=======================
"""
def _get_peakindexs():
    with Session(db_utils.ENGINE) as session:
        peakindexs = pd.read_sql(session.query(*VISIBLE_COLS).statement, session.bind)

    cols = [{'name': str(col), 'id': str(col)} for col in peakindexs.columns]
    cols.append({'name': 'Parameters', 'id': 'Parameters', 'presentation': 'markdown'})
    cols.append({'name': 'Results', 'id': 'Results', 'presentation': 'markdown'})

    peakindexs['id'] = peakindexs['peakindex_id']

    peakindexs['Parameters'] = '**Parameters**'
    peakindexs['Results'] = '**Results**'
    
    return cols, peakindexs.to_dict('records')



@dash.callback(
    Output('peakindex-table', 'columns', allow_duplicate=True),
    Output('peakindex-table', 'data', allow_duplicate=True),
    Input('upload-peakindex-config', 'contents'),
    prevent_initial_call=True,
)
def upload_config(contents):
    try:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        config = yaml.safe_load(decoded)
        peakindex_row = db_utils.import_peakindex_row(config)
        peakindex_row.date = datetime.datetime.now()
        peakindex_row.commit_id = 'TEST'
        peakindex_row.calib_id = 'TEST'
        peakindex_row.runtime = 'TEST'
        peakindex_row.computer_name = 'TEST'
        peakindex_row.dataset_id = 0
        peakindex_row.notes = 'TEST'

        with Session(db_utils.ENGINE) as session:
            session.add(peakindex_row)
            session.commit()

    except Exception as e:
        print('Unable to parse config')
        print(e)
    
    cols, peakindexs = _get_peakindexs()
    return cols, peakindexs



VISIBLE_COLS = [
    db_schema.PeakIndex.peakindex_id,
    db_schema.PeakIndex.date,
    db_schema.PeakIndex.calib_id,
    db_schema.PeakIndex.dataset_id,
    db_schema.PeakIndex.notes,
]


@dash.callback(
    Output('peakindex-table', 'columns', allow_duplicate=True),
    Output('peakindex-table', 'data', allow_duplicate=True),
    Input('url','pathname'),
    prevent_initial_call=True,
)
def get_peakindexs(path):
       if path == '/indexedpeaks':
            cols, peakindexs = _get_peakindexs()
            return cols, peakindexs
       else:
            raise PreventUpdate


@dash.callback(
    Input("peakindex-table", "active_cell"),
)
def cell_clicked(active_cell):
    if active_cell is None:
        return dash.no_update

    print(active_cell)
    row = active_cell["row"]
    row_id = active_cell["row_id"]
    col = active_cell["column"]

    if col == 5:
        with Session(db_utils.ENGINE) as session:
            peakindex = session.query(db_schema.PeakIndex).filter(db_schema.PeakIndex.peakindex_id == row_id).first()
        
        set_props("modal-details", {'is_open':True})
        set_props("modal-details-header", {'children':dbc.ModalTitle(f"Details for Peak Index {row_id} (Read Only)")})
        
        ui_shared.set_peakindex_form_props(peakindex, read_only=True)


    
    elif col == 6:
        with Session(db_utils.ENGINE) as session:
            peakindex = session.query(db_schema.PeakIndex).filter(db_schema.PeakIndex.peakindex_id == row_id).first()

        set_props("modal-results", {'is_open':True})
        set_props("modal-results-header", {'children':dbc.ModalTitle(f"Results for Peak Index {row_id}")})
        
        #file_output = peakindex.file_output
        #set_props("results-path", {"value":file_output})

    print(f"Row {row} and Column {col} was clicked")
    

"""
=======================
Helper Functions
=======================
"""

# def loahdh5(path, key, slice=None, results_filename = "results.h5"):
#     results_file = Path(path)/results_filename
#     f = h5py.File(results_file, 'r')
#     if slice is None:
#         value = f[key][:]
#     else:
#         value = f[key][slice]
#     #logging.info("Loaded: " + str(file))
#     return value

# def loadnpy(path, results_filename = 'img' + 'results' + '.npy'):
#     results_file = Path(path)/results_filename
#     value = np.zeros((2**11,2**11))
#     if results_file.exists():
#         value = np.load(results_file)
#     return value