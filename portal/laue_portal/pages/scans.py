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
                dbc.ModalHeader(dbc.ModalTitle("Header"), id="modal-scan-header"),
                dbc.ModalBody(html.H1("TODO: Scan Display")),
                # html.Div(children=[
                    
                # ])
                dash_table.DataTable(
                    id='scan-table',
                    # columns=[{"name": i, "id": i}
                    #         for i in df.columns],
                    # data=df.to_dict('records'),
                    style_cell=dict(textAlign='left'),
                    #style_header=dict(backgroundColor="paleturquoise"),
                    #style_data=dict(backgroundColor="lavender")
            )
            ],
            id="modal-scan",
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
    cols.append({'name': 'Scan', 'id': 'Scan', 'presentation': 'markdown'})

    metadatas['id'] = metadatas['scanNumber']

    metadatas['Parameters'] = '**Parameters**'
    metadatas['Scan'] = '**Scan**'
    
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
        log, scan = db_utils.parse_metadata(decoded) #yaml.safe_load(decoded)
        metadata_row = db_utils.import_metadata_row(log)
        scan_cards = []; scan_rows = []
        for i,scan in enumerate(scan):
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

VISIBLE_COLS_Scan = [
    db_schema.Scan.scanNumber,

    db_schema.Scan.scan_dim,
    db_schema.Scan.scan_npts,
    db_schema.Scan.scan_after,
    db_schema.Scan.scan_positioner1_PV,
    db_schema.Scan.scan_positioner1_ar,
    db_schema.Scan.scan_positioner1_mode,
    db_schema.Scan.scan_positioner1,
    db_schema.Scan.scan_positioner2_PV,
    db_schema.Scan.scan_positioner2_ar,
    db_schema.Scan.scan_positioner2_mode,
    db_schema.Scan.scan_positioner2,
    db_schema.Scan.scan_positioner3_PV,
    db_schema.Scan.scan_positioner3_ar,
    db_schema.Scan.scan_positioner3_mode,
    db_schema.Scan.scan_positioner3,
    db_schema.Scan.scan_positioner4_PV,
    db_schema.Scan.scan_positioner4_ar,
    db_schema.Scan.scan_positioner4_mode,
    db_schema.Scan.scan_positioner4,
    db_schema.Scan.scan_detectorTrig1_PV,
    db_schema.Scan.scan_detectorTrig1_VAL,
    db_schema.Scan.scan_detectorTrig2_PV,
    db_schema.Scan.scan_detectorTrig2_VAL,
    db_schema.Scan.scan_detectorTrig3_PV,
    db_schema.Scan.scan_detectorTrig3_VAL,
    db_schema.Scan.scan_detectorTrig4_PV,
    db_schema.Scan.scan_detectorTrig4_VAL,
    db_schema.Scan.scan_cpt,
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
            scan = session.query(db_schema.Scan).filter(db_schema.Scan.scanNumber == row_id)

        set_props("modal-details", {'is_open':True})
        set_props("modal-details-header", {'children':dbc.ModalTitle(f"Details for Peak Index {row_id} (Read Only)")})
        
        ui_shared.set_metadata_form_props(metadata, scan, read_only=True)


    
    elif col == 6:
        with Session(db_utils.ENGINE) as session:
            df = pd.read_sql(session.query(*VISIBLE_COLS_Scan).filter(db_schema.Scan.scanNumber == row_id).statement, session.bind)

        set_props("modal-scan", {'is_open':True})
        set_props("modal-scan-header", {'children':dbc.ModalTitle(f"Scan for {row_id}")})

        set_props("scan-table",
                    {
                        'columns':[{"name": i, "id": i} for i in df.columns],
                        'data':df.to_dict('records'),
                    }
        )

    print(f"Row {row} and Column {col} was clicked")
