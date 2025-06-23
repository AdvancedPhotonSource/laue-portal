import dash
from dash import html, dcc, ctx, callback, Input, Output, State, set_props
import dash_bootstrap_components as dbc
import laue_portal.database.db_utils as db_utils
import laue_portal.database.db_schema as db_schema
from sqlalchemy import select
from sqlalchemy.orm import Session
import laue_portal.components.navbar as navbar
from dash.exceptions import PreventUpdate
from sqlalchemy import asc # Import asc for ordering
from laue_portal.components.wire_recon_form import wire_recon_form, set_wire_recon_form_props
import urllib.parse
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import h5py

dash.register_page(__name__, path="/wire_reconstruction")

layout = html.Div([
        navbar.navbar,
        dcc.Location(id='url-wire-recon-page', refresh=False),
        dbc.Container(id='wire-recon-content-container', fluid=True, className="mt-4",
                  children=[
                        wire_recon_form
                  ]),
        # html.Div(children=[
        #             dbc.Select(
        #                 placeholder="Select Detector Pixel",
        #                 id="pixels",
        #             ),
        #             dcc.Graph(
        #                 #style={'height': 300},
        #                 style={'display': 'inline-block'},
        #                 id="lineout-graph",
        #             ),
        #             dcc.Graph(
        #                 #style={'height': 300},
        #                 style={'display': 'inline-block', 'height': 300},
        #                 id="detector-graph",
        #             ),
        #             dcc.Store(id='zoom_info'),
        #             dcc.Store(id='index_pointer'),
        #             dbc.Alert(
        #                 "No data found here",
        #                 is_open=False,
        #                 duration=2400,
        #                 color="warning",
        #                 id="alert-auto-no-data",
        #             ),
        #             dbc.Alert(
        #                 "Updating depth-profile plot",
        #                 is_open=False,
        #                 duration=2400,
        #                 color="success",
        #                 id="alert-auto-update-plot",
        #             ),
        #             dcc.Store(
        #                 id="results-path",
        #             ),
        #             dcc.Store(
        #                 id="integrated-lau",
        #             ),
        #         ]),
    ],
)

"""
=======================
Callbacks
=======================
"""
# @dash.callback(
#     Output('recon-table', 'columns', allow_duplicate=True),
#     Output('recon-table', 'data', allow_duplicate=True),
#     Input('upload-config', 'contents'),
#     prevent_initial_call=True,
# )
# def upload_config(contents):
#     try:
#         content_type, content_string = contents.split(',')
#         decoded = base64.b64decode(content_string)
#         config = yaml.safe_load(decoded)
#         recon_row = db_utils.import_recon_row(config)
#         recon_row.date = datetime.datetime.now()
#         recon_row.commit_id = 'TEST'
#         recon_row.calib_id = 'TEST'
#         recon_row.runtime = 'TEST'
#         recon_row.computer_name = 'TEST'
#         recon_row.dataset_id = 0
#         recon_row.notes = 'TEST'

#         with Session(db_utils.ENGINE) as session:
#             session.add(recon_row)
#             session.commit()

#     except Exception as e:
#         print('Unable to parse config')
#         print(e)
    
#     cols, recons = _get_recons()
#     return cols, recons


@callback(
    Input('url-wire-recon-page', 'href'),
    prevent_initial_call=True
)
def load_wire_recon_data(href):
    if not href:
        raise PreventUpdate

    parsed_url = urllib.parse.urlparse(href)
    query_params = urllib.parse.parse_qs(parsed_url.query)
    print(query_params)
    
    wirerecon_id = query_params.get('wirereconid', [None])[0]

    if wirerecon_id:
        try:
            wirerecon_id = int(wirerecon_id)
            with Session(db_utils.ENGINE) as session:
                wirerecon_data = session.query(db_schema.WireRecon).filter(db_schema.WireRecon.wirerecon_id == wirerecon_id).first()
                if wirerecon_data:
                    set_wire_recon_form_props(wirerecon_data, read_only=True)

        except Exception as e:
            print(f"Error loading wire reconstruction data: {e}")
    