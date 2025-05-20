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

dash.register_page(__name__, path='/')

layout = html.Div([
        ui_shared.navbar,
        dcc.Location(id='url', refresh=False),
        dbc.Row(
            [
                dash_table.DataTable(
                    id='metadata-table',
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
                dbc.ModalBody(ui_shared.metadata_form),
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
def _get_metadatas():
    with Session(db_utils.ENGINE) as session:
        metadatas = pd.read_sql(session.query(*VISIBLE_COLS).statement, session.bind)

    cols = [{'name': str(col), 'id': str(col)} for col in metadatas.columns]
    cols.append({'name': 'Parameters', 'id': 'Parameters', 'presentation': 'markdown'})
    cols.append({'name': 'Results', 'id': 'Results', 'presentation': 'markdown'})

    metadatas['id'] = metadatas['scanNumber']

    metadatas['Parameters'] = '**Parameters**'
    metadatas['Results'] = '**Results**'
    
    return cols, metadatas.to_dict('records')



@dash.callback(
    Output('metadata-table', 'columns', allow_duplicate=True),
    Output('metadata-table', 'data', allow_duplicate=True),
    Input('upload-metadata-log', 'contents'),
    prevent_initial_call=True,
)
def upload_log(contents):
    try:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        log, scans = db_utils.parse_metadata(decoded) #yaml.safe_load(decoded)
        metadata_row = db_utils.import_metadata_row(log)
        scan_cards = []; scan_rows = []
        for i,scan in enumerate(scans):
            scan_cards.append(ui_shared.make_scan_card(i))
            scan_rows.append(db_utils.import_scan_row(scan))
        set_props("scan_cards", {'children': scan_cards})
        
        metadata_row.date = datetime.datetime.now()
        metadata_row.commit_id = ''
        metadata_row.calib_id = ''
        metadata_row.runtime = ''
        metadata_row.computer_name = ''
        metadata_row.dataset_id = 0
        metadata_row.notes = ''

        with Session(db_utils.ENGINE) as session:
            session.add(metadata_row)
            session.commit()
            for scan_row in scan_rows:
                session.add(scan_row)
                session.commit()

    except Exception as e:
        print('Unable to parse log')
        print(e)
    
    cols, metadatas = _get_metadatas()
    return cols, metadatas



VISIBLE_COLS = [
    db_schema.Metadata.scanNumber,
    
    db_schema.Metadata.date,
    db_schema.Metadata.calib_id,
    db_schema.Metadata.dataset_id,
    db_schema.Metadata.notes,
]


@dash.callback(
    Output('metadata-table', 'columns', allow_duplicate=True),
    Output('metadata-table', 'data', allow_duplicate=True),
    Input('url','pathname'),
    prevent_initial_call=True,
)
def get_metadatas(path):
       if path == '/':
            cols, metadatas = _get_metadatas()
            return cols, metadatas
       else:
            raise PreventUpdate


@dash.callback(
    Input("metadata-table", "active_cell"),
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
            metadata = session.query(db_schema.Metadata).filter(db_schema.Metadata.scanNumber == row_id).first()
            scans = session.query(db_schema.Scan).filter(db_schema.Scan.scanNumber == row_id)

        set_props("modal-details", {'is_open':True})
        set_props("modal-details-header", {'children':dbc.ModalTitle(f"Details for Peak Index {row_id} (Read Only)")})
        
        ui_shared.set_metadata_form_props(metadata, scans, read_only=True)


    
    elif col == 6:
        with Session(db_utils.ENGINE) as session:
            metadata = session.query(db_schema.Metadata).filter(db_schema.Metadata.scanNumber == row_id).first()

        set_props("modal-results", {'is_open':True})
        set_props("modal-results-header", {'children':dbc.ModalTitle(f"Results for Peak Index {row_id}")})
        
        #file_output = metadata.file_output
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