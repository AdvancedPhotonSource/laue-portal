import dash
from dash import html, dcc, callback, Input, Output, set_props
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

dash.register_page(__name__, path='/')

layout = html.Div([
        ui_shared.navbar,
        dcc.Location(id='url', refresh=False),
        dbc.Row(
            [
                dash_table.DataTable(
                    id='recon-table',
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
                dbc.ModalBody(ui_shared.recon_form),
            ],
            id="modal-details",
            size="xl",
            is_open=False,
        ),
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("Header"), id="modal-results-header"),
                dbc.ModalBody(html.H1("TODO: Results Display")),
                dbc.ModalBody(html.H1("TODO2: Results Display")),
                # Define Plotly Charts for Results Display
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
def _get_recons():
    with Session(db_utils.ENGINE) as session:
        recons = pd.read_sql(session.query(*VISIBLE_COLS ).statement, session.bind)

    cols = [{'name': str(col), 'id': str(col)} for col in recons.columns]
    cols.append({'name': 'Parameters', 'id': 'Parameters', 'presentation': 'markdown'})
    cols.append({'name': 'Results', 'id': 'Results', 'presentation': 'markdown'})

    recons['id'] = recons['recon_id']

    recons['Parameters'] = '**Parameters**'
    recons['Results'] = '**Results**'
    
    return cols, recons.to_dict('records')



@dash.callback(
    Output('recon-table', 'columns', allow_duplicate=True),
    Output('recon-table', 'data', allow_duplicate=True),
    Input('upload-config', 'contents'),
    prevent_initial_call=True,
)
def upload_config(contents):
    try:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        config = yaml.safe_load(decoded)
        recon_row = db_utils.import_recon_row(config)
        recon_row.date = datetime.datetime.now()
        recon_row.commit_id = 'TEST'
        recon_row.calib_id = 'TEST'
        recon_row.runtime = 'TEST'
        recon_row.computer_name = 'TEST'
        recon_row.dataset_id = 0
        recon_row.notes = 'TEST'

        with Session(db_utils.ENGINE) as session:
            session.add(recon_row)
            session.commit()

    except Exception as e:
        print('Unable to parse config')
        print(e)
    
    cols, recons = _get_recons()
    return cols, recons




VISIBLE_COLS = [
    db_schema.Recon.recon_id,
    db_schema.Recon.date,
    db_schema.Recon.calib_id,
    db_schema.Recon.dataset_id,
    db_schema.Recon.notes,
]


@dash.callback(
    Output('recon-table', 'columns', allow_duplicate=True),
    Output('recon-table', 'data', allow_duplicate=True),
    Input('url','pathname'),
    prevent_initial_call=True,
)
def get_recons(path):
       if path == '/':
            cols, recons = _get_recons()
            return cols, recons
       else:
            raise PreventUpdate


@dash.callback(
    Input("recon-table", "active_cell"),
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
            recon = session.query(db_schema.Recon).filter(db_schema.Recon.recon_id == row_id).first()
        
        set_props("modal-details", {'is_open':True})
        set_props("modal-details-header", {'children':dbc.ModalTitle(f"Details for Recon {row_id} (Read Only)")})
        
        ui_shared.set_form_props(recon, read_only=True)


    
    elif col == 6:
        set_props("modal-results", {'is_open':True})
        set_props("modal-results-header", {'children':dbc.ModalTitle(f"Results for Recon {row_id}")})

        # Load sample data here
        # Graph the data
        # Ouptput to display
         
    print(f"Row {row} and Column {col} was clicked")
    

