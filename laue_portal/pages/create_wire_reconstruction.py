import dash_bootstrap_components as dbc
from dash import html, dcc, Input, set_props, State
import dash
import laue_portal.database.db_utils as db_utils
import datetime
import laue_portal.database.db_schema as db_schema
import laue_portal.components.navbar as navbar
from sqlalchemy.orm import Session
from laue_portal.components.wire_recon_form import wire_recon_form, set_wire_recon_form_props
import urllib.parse
from dash.exceptions import PreventUpdate
import logging
logger = logging.getLogger(__name__)

try:
    import laue_portal.recon.analysis_wire_recon as analysis_wire_recon
    _ANALYSIS_LIB_AVAILABLE = True
except ImportError:
    analysis_wire_recon = None
    _ANALYSIS_LIB_AVAILABLE = False
    logger.warning("Wire Reconstruction libraries not installed. Analysis will be skipped.")

WIRERECON_DEFAULTS = {
    'scanNumber': 276994,
    "depth_start": -50,
    "depth_end": 150,
    "depth_resolution": 1,
}

dash.register_page(__name__)

layout = dbc.Container(
    [html.Div([
        navbar.navbar,
        dbc.Alert(
            "Wire Reconstruction libraries not installed. Dry runs only.",
            id="alert-lib-warning",
            dismissable=True,
            is_open=not _ANALYSIS_LIB_AVAILABLE,
            color="warning",
        ),
        dcc.Location(id='url-create-wirerecon', refresh=False),
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
        dbc.Alert(
            "Scan data loaded successfully",
            id="alert-scan-loaded",
            dismissable=True,
            is_open=False,
            color="success",
        ),
        # html.Hr(),
        # html.Center(
        #     html.Div(
        #         [
        #             html.Div([
        #                     dcc.Upload(dbc.Button('Upload Config'), id='upload-wireconfig'),
        #             ], style={'display':'inline-block'}),
        #         ],
        #     )
        # ),
        html.Hr(),
        html.Center(
            dbc.Button('Submit', id='submit_wire', color='primary'),
        ),
        html.Hr(),
        wire_recon_form,
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
# @dash.callback(
#     Input('upload-wireconfig', 'contents'),
#     prevent_initial_call=True,
# )
# def upload_config(contents):
#     try:
#         content_type, content_string = contents.split(',')
#         decoded = base64.b64decode(content_string)
#         config = yaml.safe_load(decoded)
#         recon_row = db_utils.import_wire_recon_row(config)
#         recon_row.date = datetime.datetime.now()
#         recon_row.commit_id = ''
#         recon_row.calib_id = ''
#         recon_row.runtime = ''
#         recon_row.computer_name = ''
#         recon_row.dataset_id = 0
#         recon_row.notes = ''

#         set_props("alert-upload", {'is_open': True, 
#                                     'children': 'Config uploaded successfully',
#                                     'color': 'success'})
#         set_wire_recon_form_props(recon_row)

#     except Exception as e:
#         set_props("alert-upload", {'is_open': True, 
#                                     'children': f'Upload Failed! Error: {e}',
#                                     'color': 'danger'})


@dash.callback(
    Input('submit_wire', 'n_clicks'),

    State('scanNumber', 'value'),
    
    State('depth_start', 'value'),
    State('depth_end', 'value'),
    State('depth_resolution', 'value'), #depth_step

    prevent_initial_call=True,
)
def submit_config(n,
    scanNumber,
    
    depth_start,
    depth_end,
    depth_resolution, #depth_step
    
):
    # TODO: Input validation and reponse
    
    wirerecon = db_schema.WireRecon(
        date=datetime.datetime.now(),
        commit_id='TEST',
        calib_id='TEST',
        runtime='TEST',
        computer_name='TEST',
        dataset_id=0,
        notes='TODO', 

        scanNumber=scanNumber,
        
        depth_start=depth_start,
        depth_end=depth_end,
        depth_resolution=depth_resolution, #depth_step
    )

    with Session(db_utils.ENGINE) as session:
        session.add(wirerecon)
        # config_dict = db_utils.create_config_obj(wirerecon)

        session.commit()
    
    set_props("alert-submit", {'is_open': True, 
                                'children': 'Config Added to Database',
                                'color': 'success'})

    if _ANALYSIS_LIB_AVAILABLE:
        pass
        # analysis_wire_recon.run_analysis(config_dict)
    else:
        logger.warning("Skipping reconstruction analysis; libraries not available")

@dash.callback(
    Input('url-create-wirerecon','pathname'),
    prevent_initial_call=True,
)
def get_peakindexs(path):
       if path == '/create-wire-reconstruction':
            wirerecon_defaults = db_schema.WireRecon(
                scanNumber=WIRERECON_DEFAULTS["scanNumber"],
                # Depth range
                depth_start=WIRERECON_DEFAULTS["depth_start"],
                depth_end=WIRERECON_DEFAULTS["depth_end"],
                depth_resolution=WIRERECON_DEFAULTS["depth_resolution"],
            )
            set_wire_recon_form_props(wirerecon_defaults)
       else:
            raise PreventUpdate

@dash.callback(
    Input('url-create-wirerecon', 'href'),
    prevent_initial_call=True,
)
def load_scan_data_from_url(href):
    """
    Load scan data when scan_id is provided in URL query parameter
    URL format: /create-indexpeaks?scan_id={scan_id}
    """
    if not href:
        raise PreventUpdate

    parsed_url = urllib.parse.urlparse(href)
    query_params = urllib.parse.parse_qs(parsed_url.query)
    
    scan_id = query_params.get('scan_id', [None])[0]

    if scan_id:
        try:
            scan_id = int(scan_id)
            with Session(db_utils.ENGINE) as session:
                # Query metadata and scan data
                metadata = session.query(db_schema.Metadata).filter(
                    db_schema.Metadata.scanNumber == scan_id
                ).first()
                
                scans = session.query(db_schema.Scan).filter(
                    db_schema.Scan.scanNumber == scan_id
                ).all()

                if metadata:
                    # Create a PeakIndex object with populated defaults from metadata/scan
                    wirerecon_defaults = db_schema.WireRecon(
                        scanNumber=scan_id,
                        # Depth range
                        depth_start=WIRERECON_DEFAULTS["depth_start"],
                        depth_end=WIRERECON_DEFAULTS["depth_end"],
                        depth_resolution=WIRERECON_DEFAULTS["depth_resolution"],
                    )
                    
                    # Populate the form with the defaults
                    set_wire_recon_form_props(wirerecon_defaults,read_only=True)
                    
                    # Show success message
                    set_props("alert-scan-loaded", {
                        'is_open': True, 
                        'children': f'Scan {scan_id} data loaded successfully. Dataset ID: {metadata.dataset_id}, Energy: {metadata.source_energy} {metadata.source_energy_unit}',
                        'color': 'success'
                    })
                else:
                    # Show error if scan not found
                    set_props("alert-scan-loaded", {
                        'is_open': True, 
                        'children': f'Scan {scan_id} not found in database',
                        'color': 'warning'
                    })
                    
        except Exception as e:
            set_props("alert-scan-loaded", {
                'is_open': True, 
                'children': f'Error loading scan data: {str(e)}',
                'color': 'danger'
            })
