import dash_bootstrap_components as dbc
from dash import html, dcc, Input, State, set_props, ALL
import dash
import base64
import laue_portal.database.db_utils as db_utils
import laue_portal.database.db_schema as db_schema
from sqlalchemy.orm import Session
import laue_portal.components.navbar as navbar
from laue_portal.components.metadata_form import metadata_form, set_metadata_form_props, set_scan_accordions
from laue_portal.components.catalog_form import catalog_form, set_catalog_form_props

CATALOG_DEFAULTS = {#temporary
    # 'scanNumber':log['scanNumber'],
    'filefolder':'/net/s34data/export/s34data1/LauePortal/portal_workspace/Run1/data/scan_1', #'example/file/folder',
    # 'filenamePrefix': 'Si-wire_%d', #'example_filename_prefix',
    'filenamePrefix': ['Si-wire_%d'],

    'aperture':{'options':'wire'},
    'sample_name':'Si',
    'notes':'',
}

dash.register_page(__name__)

layout = dbc.Container(
    [
        # Store for uploaded XML data
        dcc.Store(id='uploaded-xml-data'),
        html.Div([
        navbar.navbar,
        dbc.Alert(
            id="alert-upload",
            dismissable=True,
            duration=4000,
            is_open=False,
        ),
        dbc.Alert(
            id="alert-submit",
            dismissable=True,
            duration=4000,
            is_open=False,
        ),
        dbc.Alert(
            id="alert-catalog-submit",
            dismissable=True,
            duration=4000,
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
            dbc.Button('Submit to Database', id='submit_catalog_and_metadata', color='primary'),
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

            scan_rows = [db_utils.import_scan_row(scan) for scan in scans]
            
            # Create and add scan accordions to the form with pre-populated data
            set_scan_accordions(scan_rows, read_only=True)
            
            # Set the form properties, including scan data
            set_metadata_form_props(metadata_row, scan_rows, read_only=True)
            
            # # Add to database
            # with Session(db_utils.ENGINE) as session:
            #     session.add(metadata_row)
            #     # session.add(catalog_row)
            #     scan_row_count = session.query(Scan).count()
            #     for id, scan_row in enumerate(scan_rows):
            #         scan_row.id = scan_row_count + id
            #         session.add(scan_row)
            #
            #     session.commit()
            
            # Close modal and show success
            return False, True, 'Scan data loaded successfully! Please review the forms and click "Submit to Database" to save.', 'success'
            
        except Exception as e:
            # Close modal and show error
            if "UNIQUE constraint failed: metadata.scanNumber" in f'{e}':
                return False, True, f"Import failed! Scan {log['scanNumber']} already exists.", 'danger'
            else:
                return False, True, f'Import failed! Error: {e}', 'danger'
    
    # Default case
    return False, False, '', 'info'


@dash.callback(
    Input('submit_catalog_and_metadata', 'n_clicks'),

    # Catalog form fields
    State('filefolder', 'value'),
    State('filenamePrefix', 'value'),
    State('aperture', 'value'),
    State('sample_name', 'value'),
    State('notes', 'value'),
    
    # Metadata form fields
    State('scanNumber', 'value'),
    State('time_epoch', 'value'),
    State('time', 'value'),
    State('user_name', 'value'),
    State('source_beamBad', 'value'),
    State('source_CCDshutter', 'value'),
    State('source_monoTransStatus', 'value'),
    State('source_energy_unit', 'value'),
    State('source_energy', 'value'),
    State('source_IDgap_unit', 'value'),
    State('source_IDgap', 'value'),
    State('source_IDtaper_unit', 'value'),
    State('source_IDtaper', 'value'),
    State('source_ringCurrent_unit', 'value'),
    State('source_ringCurrent', 'value'),
    State('sample_XYZ_unit', 'value'),
    State('sample_XYZ_desc', 'value'),
    State('sample_XYZ', 'value'),
    State('knife-edge_XYZ_unit', 'value'),
    State('knife-edge_XYZ_desc', 'value'),
    State('knife-edge_XYZ', 'value'),
    State('knife-edge_knifeScan_unit', 'value'),
    State('knife-edge_knifeScan', 'value'),
    State('mda_file', 'value'),
    State('scanEnd_abort', 'value'),
    State('scanEnd_time_epoch', 'value'),
    State('scanEnd_time', 'value'),
    State('scanEnd_scanDuration_unit', 'value'),
    State('scanEnd_scanDuration', 'value'),
    State('scanEnd_source_beamBad', 'value'),
    State('scanEnd_source_ringCurrent_unit', 'value'),
    State('scanEnd_source_ringCurrent', 'value'),
    
    # Scan form fields using ALL pattern with hidden_ prefix
    State({"type": "hidden_scan_dim", "index": ALL}, 'value'),
    State({"type": "hidden_scan_npts", "index": ALL}, 'value'),
    State({"type": "hidden_scan_after", "index": ALL}, 'value'),
    State({"type": "hidden_scan_positioner1_PV", "index": ALL}, 'value'),
    State({"type": "hidden_scan_positioner1_ar", "index": ALL}, 'value'),
    State({"type": "hidden_scan_positioner1_mode", "index": ALL}, 'value'),
    State({"type": "hidden_scan_positioner1", "index": ALL}, 'value'),
    State({"type": "hidden_scan_positioner2_PV", "index": ALL}, 'value'),
    State({"type": "hidden_scan_positioner2_ar", "index": ALL}, 'value'),
    State({"type": "hidden_scan_positioner2_mode", "index": ALL}, 'value'),
    State({"type": "hidden_scan_positioner2", "index": ALL}, 'value'),
    State({"type": "hidden_scan_positioner3_PV", "index": ALL}, 'value'),
    State({"type": "hidden_scan_positioner3_ar", "index": ALL}, 'value'),
    State({"type": "hidden_scan_positioner3_mode", "index": ALL}, 'value'),
    State({"type": "hidden_scan_positioner3", "index": ALL}, 'value'),
    State({"type": "hidden_scan_positioner4_PV", "index": ALL}, 'value'),
    State({"type": "hidden_scan_positioner4_ar", "index": ALL}, 'value'),
    State({"type": "hidden_scan_positioner4_mode", "index": ALL}, 'value'),
    State({"type": "hidden_scan_positioner4", "index": ALL}, 'value'),
    State({"type": "hidden_scan_detectorTrig1_PV", "index": ALL}, 'value'),
    State({"type": "hidden_scan_detectorTrig1_VAL", "index": ALL}, 'value'),
    State({"type": "hidden_scan_detectorTrig2_PV", "index": ALL}, 'value'),
    State({"type": "hidden_scan_detectorTrig2_VAL", "index": ALL}, 'value'),
    State({"type": "hidden_scan_detectorTrig3_PV", "index": ALL}, 'value'),
    State({"type": "hidden_scan_detectorTrig3_VAL", "index": ALL}, 'value'),
    State({"type": "hidden_scan_detectorTrig4_PV", "index": ALL}, 'value'),
    State({"type": "hidden_scan_detectorTrig4_VAL", "index": ALL}, 'value'),
    State({"type": "hidden_scan_cpt", "index": ALL}, 'value'),

    prevent_initial_call=True,
)
def submit_catalog_and_metadata(n,
    # Catalog parameters
    filefolder,
    filenamePrefix,
    aperture,
    sample_name,
    notes,
    
    # Metadata parameters
    scanNumber,
    time_epoch,
    time,
    user_name,
    source_beamBad,
    source_CCDshutter,
    source_monoTransStatus,
    source_energy_unit,
    source_energy,
    source_IDgap_unit,
    source_IDgap,
    source_IDtaper_unit,
    source_IDtaper,
    source_ringCurrent_unit,
    source_ringCurrent,
    sample_XYZ_unit,
    sample_XYZ_desc,
    sample_XYZ,
    knifeEdge_XYZ_unit,
    knifeEdge_XYZ_desc,
    knifeEdge_XYZ,
    knifeEdge_knifeScan_unit,
    knifeEdge_knifeScan,
    mda_file,
    scanEnd_abort,
    scanEnd_time_epoch,
    scanEnd_time,
    scanEnd_scanDuration_unit,
    scanEnd_scanDuration,
    scanEnd_source_beamBad,
    scanEnd_source_ringCurrent_unit,
    scanEnd_source_ringCurrent,
    
    # Scan parameters (ALL pattern returns lists)
    scan_dims,
    scan_npts_list,
    scan_afters,
    scan_positioner1_PVs,
    scan_positioner1_ars,
    scan_positioner1_modes,
    scan_positioner1s,
    scan_positioner2_PVs,
    scan_positioner2_ars,
    scan_positioner2_modes,
    scan_positioner2s,
    scan_positioner3_PVs,
    scan_positioner3_ars,
    scan_positioner3_modes,
    scan_positioner3s,
    scan_positioner4_PVs,
    scan_positioner4_ars,
    scan_positioner4_modes,
    scan_positioner4s,
    scan_detectorTrig1_PVs,
    scan_detectorTrig1_VALs,
    scan_detectorTrig2_PVs,
    scan_detectorTrig2_VALs,
    scan_detectorTrig3_PVs,
    scan_detectorTrig3_VALs,
    scan_detectorTrig4_PVs,
    scan_detectorTrig4_VALs,
    scan_cpts,
):
    # TODO: Input validation and response
    
    try:
        # Convert scanNumber to int if it's a string
        if isinstance(scanNumber, str):
            scanNumber = int(scanNumber)
        
        with Session(db_utils.ENGINE) as session:
            try:
                # Check if metadata record exists for this scanNumber
                metadata_data = session.query(db_schema.Metadata).filter(
                    db_schema.Metadata.scanNumber == scanNumber
                ).first()
                
                if metadata_data:
                    set_props("alert-submit", {'is_open': True, 
                                                'children': f'Error: Scan {scanNumber} already exists in the database.',
                                                'color': 'danger'})
                else:
                    # Create new metadata entry
                    metadata = db_schema.Metadata(
                        scanNumber=scanNumber,
                        time_epoch=time_epoch,
                        time=db_utils.convert_time_string_to_datetime(time) if time else None,
                        user_name=user_name,
                        source_beamBad=source_beamBad,
                        source_CCDshutter=source_CCDshutter,
                        source_monoTransStatus=source_monoTransStatus,
                        source_energy_unit=source_energy_unit,
                        source_energy=source_energy,
                        source_IDgap_unit=source_IDgap_unit,
                        source_IDgap=source_IDgap,
                        source_IDtaper_unit=source_IDtaper_unit,
                        source_IDtaper=source_IDtaper,
                        source_ringCurrent_unit=source_ringCurrent_unit,
                        source_ringCurrent=source_ringCurrent,
                        sample_XYZ_unit=sample_XYZ_unit,
                        sample_XYZ_desc=sample_XYZ_desc,
                        sample_XYZ=sample_XYZ,
                        knifeEdge_XYZ_unit=knifeEdge_XYZ_unit,
                        knifeEdge_XYZ_desc=knifeEdge_XYZ_desc,
                        knifeEdge_XYZ=knifeEdge_XYZ,
                        knifeEdge_knifeScan_unit=knifeEdge_knifeScan_unit,
                        knifeEdge_knifeScan=knifeEdge_knifeScan,
                        mda_file=mda_file,
                        scanEnd_abort=scanEnd_abort,
                        scanEnd_time_epoch=scanEnd_time_epoch,
                        scanEnd_time=db_utils.convert_time_string_to_datetime(scanEnd_time) if scanEnd_time else None,
                        scanEnd_scanDuration_unit=scanEnd_scanDuration_unit,
                        scanEnd_scanDuration=scanEnd_scanDuration,
                        scanEnd_source_beamBad=scanEnd_source_beamBad,
                        scanEnd_source_ringCurrent_unit=scanEnd_source_ringCurrent_unit,
                        scanEnd_source_ringCurrent=scanEnd_source_ringCurrent,
                    )
                    
                    # Add scan rows from the form data
                    if scan_dims and len(scan_dims) > 0:
                        motor_group_totals = {}
                        # Reconstruct scan objects from form values
                        for i in range(len(scan_dims)):
                            # Check if all required fields have values (not None)
                            if all(field is not None for field in 
                                   [
                                    scan_afters[i],
                                    scan_positioner1_PVs[i], scan_positioner1_ars[i],
                                    scan_positioner1_modes[i], scan_positioner1s[i],
                                    scan_positioner2_PVs[i], scan_positioner2_ars[i],
                                    scan_positioner2_modes[i], scan_positioner2s[i],
                                    scan_positioner3_PVs[i], scan_positioner3_ars[i],
                                    scan_positioner3_modes[i], scan_positioner3s[i],
                                    scan_positioner4_PVs[i], scan_positioner4_ars[i],
                                    scan_positioner4_modes[i], scan_positioner4s[i],
                                    scan_detectorTrig1_PVs[i],scan_detectorTrig1_VALs[i],
                                    scan_detectorTrig2_PVs[i], scan_detectorTrig2_VALs[i],
                                    scan_detectorTrig3_PVs[i], scan_detectorTrig3_VALs[i],
                                    scan_detectorTrig4_PVs[i], scan_detectorTrig4_VALs[i],
                                    ]
                            ):
                                scan = db_schema.Scan(
                                    scanNumber=scanNumber,
                                    scan_dim=scan_dims[i],
                                    scan_npts=scan_npts_list[i],
                                    scan_after=scan_afters[i],
                                    scan_positioner1_PV=scan_positioner1_PVs[i],
                                    scan_positioner1_ar=scan_positioner1_ars[i],
                                    scan_positioner1_mode=scan_positioner1_modes[i],
                                    scan_positioner1=scan_positioner1s[i],
                                    scan_positioner2_PV=scan_positioner2_PVs[i],
                                    scan_positioner2_ar=scan_positioner2_ars[i],
                                    scan_positioner2_mode=scan_positioner2_modes[i],
                                    scan_positioner2=scan_positioner2s[i],
                                    scan_positioner3_PV=scan_positioner3_PVs[i],
                                    scan_positioner3_ar=scan_positioner3_ars[i],
                                    scan_positioner3_mode=scan_positioner3_modes[i],
                                    scan_positioner3=scan_positioner3s[i],
                                    scan_positioner4_PV=scan_positioner4_PVs[i],
                                    scan_positioner4_ar=scan_positioner4_ars[i],
                                    scan_positioner4_mode=scan_positioner4_modes[i],
                                    scan_positioner4=scan_positioner4s[i],
                                    scan_detectorTrig1_PV=scan_detectorTrig1_PVs[i],
                                    scan_detectorTrig1_VAL=scan_detectorTrig1_VALs[i],
                                    scan_detectorTrig2_PV=scan_detectorTrig2_PVs[i],
                                    scan_detectorTrig2_VAL=scan_detectorTrig2_VALs[i],
                                    scan_detectorTrig3_PV=scan_detectorTrig3_PVs[i],
                                    scan_detectorTrig3_VAL=scan_detectorTrig3_VALs[i],
                                    scan_detectorTrig4_PV=scan_detectorTrig4_PVs[i],
                                    scan_detectorTrig4_VAL=scan_detectorTrig4_VALs[i],
                                    scan_cpt=scan_cpts[i],
                                )
                                session.add(scan)
                                motor_group_totals = db_utils.update_motor_group_totals(motor_group_totals, scan)
                        
                        # Fallback value of 1 for 'sample' and 'depth' completed points if any motor has completed points
                        if motor_group_totals:
                            for specific_motor_group in ['sample', 'depth']:
                                if specific_motor_group not in motor_group_totals:
                                    if any(group.get('completed', 0) for group in motor_group_totals.values()):
                                        motor_group_totals[specific_motor_group] = {'points': 0, 'completed': 1}

                        for motor_group, totals in motor_group_totals.items():
                            setattr(metadata, f'motorGroup_{motor_group}_npts_total', totals['points'])
                            setattr(metadata, f'motorGroup_{motor_group}_cpt_total', totals['completed'])
                    
                    session.add(metadata)
                    
                    set_props("alert-submit", {'is_open': True, 
                                                'children': f'Metadata Entry Added to Database for scan {scanNumber}',
                                                'color': 'success'})
            except Exception as e:
                set_props("alert-submit", {'is_open': True, 
                                            'children': f'Error creating metadata entry: {str(e)}',
                                            'color': 'danger'})
                return

            try:
                # Check if catalog entry already exists
                catalog_data = session.query(db_schema.Catalog).filter(
                    db_schema.Catalog.scanNumber == scanNumber
                ).first()
                
                filenamePrefix = [s.strip() for s in filenamePrefix.split(',')] if filenamePrefix else []
                if catalog_data:
                    # Update existing catalog entry
                    catalog_data.filefolder = filefolder
                    catalog_data.filenamePrefix = filenamePrefix
                    catalog_data.aperture = aperture
                    catalog_data.sample_name = sample_name
                    catalog_data.notes = notes
                    
                    set_props("alert-catalog-submit", {'is_open': True, 
                                                'children': f'Catalog Entry Updated for scan {scanNumber}',
                                                'color': 'success'})
                else:
                    # Create new catalog entry
                    catalog = db_schema.Catalog(
                        scanNumber=scanNumber,
                        filefolder=filefolder,
                        filenamePrefix=filenamePrefix,
                        aperture=aperture,
                        sample_name=sample_name,
                        notes=notes,
                    )
                    
                    session.add(catalog)
                    
                    set_props("alert-catalog-submit", {'is_open': True, 
                                                'children': f'Catalog Entry Added to Database for scan {scanNumber}',
                                                'color': 'success'})
            except Exception as e:
                set_props("alert-catalog-submit", {'is_open': True, 
                                            'children': f'Error creating catalog entry: {str(e)}',
                                            'color': 'danger'})
                return
            
            # Commit all changes
            session.commit()
                                            
    except ValueError as e:
        set_props("alert-submit", {'is_open': True, 
                                    'children': f'Error: Invalid scan number format. Please enter a valid integer.',
                                    'color': 'danger'})
