import dash_bootstrap_components as dbc
from dash import html, Input, State, set_props, ALL
import dash
import laue_portal.pages.ui_shared as ui_shared
from dash import dcc
import base64
import yaml
import laue_portal.database.db_utils as db_utils
import datetime
import laue_portal.database.db_schema as db_schema
from sqlalchemy.orm import Session
from laue_portal.database.db_schema import Scan
import laue_portal.components.navbar as navbar

dash.register_page(__name__)

layout = dbc.Container(
    [html.Div([
        navbar.navbar,
        dbc.Alert(
            "Hello! I am an alert",
            id="alert-upload",
            dismissable=True,
            is_open=False,
        ),
        dbc.Alert(
            "Hello! I am an alert",
            id="alert-submit",
            dismissable=True,
            is_open=False,
        ),
        html.Hr(),
        html.Center(
            html.Div(
                [
                    html.Div([
                        dbc.Button('Copy From Existing (TODO)', id='copy-existing', className='mr-2'),
                    ], style={'display':'inline-block'}),
                    html.Div([
                            dcc.Upload(dbc.Button('Upload Log'), id='upload-metadata-log'),
                    ], style={'display':'inline-block'}),
                ],
            )
        ),
        # html.Hr(),
        # html.Center(
        #     dbc.Button('Submit', id='submit_metadata', color='primary'),
        # ),
        # html.Hr(),
        ui_shared.metadata_form,
    ],
    )
    ],
    className='dbc', 
    fluid=True
)

"""
=======================
Callbacks
=======================
"""
@dash.callback(
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
            scan_card = ui_shared.make_scan_card(i)
            scan_cards.append(scan_card)
            scan_row = db_utils.import_scan_row(scan)
            scan_rows.append(scan_row)
        set_props("scan_cards", {'children': scan_cards})
        
        metadata_row.date = datetime.datetime.now()
        metadata_row.commit_id = ''
        metadata_row.calib_id = ''
        metadata_row.runtime = ''
        metadata_row.computer_name = ''
        metadata_row.dataset_id = 0
        metadata_row.notes = ''

        set_props("alert-upload", {'is_open': True, 
                                    'children': 'Log uploaded successfully',
                                    'color': 'success'})
        ui_shared.set_metadata_form_props(metadata_row,scan_rows)

        # Add to database
        with Session(db_utils.ENGINE) as session:
            session.add(metadata_row)
            scan_row_count = session.query(Scan).count()
            for id,scan_row in enumerate(scan_rows):
                scan_row.id = scan_row_count + id
                session.add(scan_row)
                print(scan_row.id)
            
            session.commit()
        
        set_props("alert-submit", {'is_open': True, 
                                    'children': 'Log Added to Database',
                                    'color': 'success'})
        #

    except Exception as e:
        set_props("alert-upload", {'is_open': True, 
                                    'children': f'Upload Failed! Error: {e}',
                                    'color': 'danger'})
