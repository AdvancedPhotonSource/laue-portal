import dash_bootstrap_components as dbc
from dash import html, dcc, Input, State, set_props
import dash
import base64
import yaml
import laue_portal.database.db_utils as db_utils
import datetime
import laue_portal.database.db_schema as db_schema
from sqlalchemy.orm import Session
from laue_portal.database.db_schema import Scan
import laue_portal.components.navbar as navbar
from laue_portal.components.metadata_form import metadata_form, set_metadata_form_props, make_scan_accordion
from laue_portal.components.catalog_form import catalog_form, set_catalog_form_props

CATALOG_DEFAULTS = {#temporary
    # 'scanNumber':log['scanNumber'],
    'filefolder':'example/file/folder',
    'filenamePrefix':'example_filename_prefix',
    'outputFolder':'example/output/folder',
    'geoFile':'example_geo_file',

    'aperture':'wire',
    'sample_name':'Si',
}

dash.register_page(__name__)

layout = dbc.Container(
    [
        # Store for uploaded XML data
        dcc.Store(id='uploaded-xml-data'),
        html.Div([
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
                            dcc.Upload(dbc.Button('Upload Log'), id='upload-metadata-log'),
                    ], style={'display':'inline-block'}),
                ],
            )
        ),
        html.Hr(),
        html.Center(
            dbc.Button('Submit to Catalog', id='submit_catalog', color='primary'),
        ),
        html.Hr(),
        catalog_form,
        html.Hr(),
        metadata_form,
        
        # Modal for scan selection
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("Select Scan")),
                dbc.ModalBody([
                    html.P("Select which scan to import from the uploaded file:"),
                    dcc.Dropdown(
                        id='scan-selection-dropdown',
                        placeholder="Select a scan...",
                        searchable=True,
                        options=[],
                        value=None
                    ),
                ]),
                dbc.ModalFooter([
                    dbc.Button("Cancel", id="scan-modal-cancel", className="ms-auto", n_clicks=0),
                    dbc.Button("Select", id="scan-modal-select", className="ms-2", color="primary", n_clicks=0),
                ]),
            ],
            id="scan-selection-modal",
            is_open=False,
            size="lg",
        ),
    ],
    )
    ],
    className='dbc', 
    fluid=True
)

"""
=======================
Helper Functions
=======================
"""
def get_scan_elements(xml_data):
    """
    Parse XML data and return available scan options for dropdown
    
    Args:
        xml_data: Decoded XML data
        
    Returns:
        List of dictionaries with 'label' and 'value' keys for dropdown options
    """
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml_data)
    
    # Get all scan elements and create dropdown options
    scan_options = []
    for i, scan_elem in enumerate(root):
        if scan_elem.tag.endswith('Scan'):
            scan_number = scan_elem.get('scanNumber', f'Scan {i+1}')
            scan_options.append({'label': f'{scan_number}', 'value': i})
    
    return scan_options

"""
=======================
Callbacks
=======================
"""
@dash.callback(
    [dash.Output('scan-selection-modal', 'is_open'),
     dash.Output('scan-selection-dropdown', 'options'),
     dash.Output('alert-upload', 'is_open'),
     dash.Output('alert-upload', 'children'),
     dash.Output('alert-upload', 'color'),
     dash.Output('upload-metadata-log', 'contents'),
     dash.Output('uploaded-xml-data', 'data')],
    Input('upload-metadata-log', 'contents'),
    prevent_initial_call=True,
)
def upload_log(contents):
    try:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        
        # Get available scan options
        scan_options = get_scan_elements(decoded)
        
        # If no scans found, show error
        if not scan_options:
            return False, [], True, 'No scans found in uploaded file', 'danger', None, None
        
        # Show modal with scan options, clear upload contents to allow re-upload, store XML data
        return True, scan_options, True, 'File uploaded successfully. Please select a scan.', 'info', None, decoded.decode('utf-8')

    except Exception as e:
        return False, [], True, f'Upload Failed! Error: {e}', 'danger', None, None


@dash.callback(
    [dash.Output('scan-selection-modal', 'is_open', allow_duplicate=True),
     dash.Output('alert-submit', 'is_open'),
     dash.Output('alert-submit', 'children'),
     dash.Output('alert-submit', 'color')],
    [Input('scan-modal-cancel', 'n_clicks'),
     Input('scan-modal-select', 'n_clicks')],
    [State('scan-selection-dropdown', 'value'),
     State('uploaded-xml-data', 'data')],
    prevent_initial_call=True,
)
def handle_modal_actions(cancel_clicks, select_clicks, selected_scan_index, xml_data):
    ctx = dash.callback_context
    if not ctx.triggered:
        return False, False, '', 'info'
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    if button_id == 'scan-modal-cancel':
        # Just close modal on cancel
        return False, False, '', 'info'
    
    elif button_id == 'scan-modal-select':
        if selected_scan_index is None:
            # No scan selected, show error but keep modal open
            return True, True, 'Please select a scan before submitting.', 'warning'
        
        if xml_data is None:
            # No XML data available, show error
            return True, True, 'No XML data available. Please upload a file first.', 'danger'
        
        try:
            # Convert stored string back to bytes for processing
            uploaded_xml_data = xml_data.encode('utf-8')
            
            # Process the selected scan
            log, scans = db_utils.parse_metadata(uploaded_xml_data, scan_no=selected_scan_index)
            metadata_row = db_utils.import_metadata_row(log)
            
            CATALOG_DEFAULTS.update({'scanNumber':log['scanNumber']})
            catalog_row = db_utils.import_catalog_row(CATALOG_DEFAULTS)
            
            set_catalog_form_props(catalog_row)

            scan_cards = []; scan_rows = []
            for i, scan in enumerate(scans):
                #scan_card = ui_shared.make_scan_card(i)
                #scan_cards.append(scan_card)
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
            
            set_metadata_form_props(metadata_row, scan_rows)
            
            # Add to database
            with Session(db_utils.ENGINE) as session:
                session.add(metadata_row)
                # session.add(catalog_row)
                scan_row_count = session.query(Scan).count()
                for id, scan_row in enumerate(scan_rows):
                    scan_row.id = scan_row_count + id
                    session.add(scan_row)
                
                session.commit()
            
            # Close modal and show success
            return False, True, 'Scan imported to database successfully!', 'success'
            
        except Exception as e:
            # Close modal and show error
            return False, True, f'Import failed! Error: {e}', 'danger'
    
    # Default case
    return False, False, '', 'info'


@dash.callback(
    Input('submit_catalog', 'n_clicks'),

    State('scanNumber', 'value'),
    
    State('filefolder', 'value'),
    State('filenamePrefix', 'value'),
    State('outputFolder', 'value'),
    State('geoFile', 'value'),

    State('aperture', 'value'),
    State('sample_name', 'value'),

    prevent_initial_call=True,
)
def submit_catalog(n,
    scanNumber,

    filefolder,
    filenamePrefix,
    outputFolder,
    geoFile,

    aperture,
    sample_name,
    
):
    # TODO: Input validation and reponse
    
    catalog = db_schema.Catalog(
        scanNumber=scanNumber,

        filefolder=filefolder,
        filenamePrefix=filenamePrefix,
        outputFolder=outputFolder,
        geoFile=geoFile,

        aperture=aperture,
        sample_name=sample_name,
    
    )

    with Session(db_utils.ENGINE) as session:
        session.add(catalog)
        # config_dict = db_utils.create_config_obj(wirerecon)

        session.commit()
    
    set_props("alert-submit", {'is_open': True, 
                                'children': 'Catalog Entry Added to Database',
                                'color': 'success'})
