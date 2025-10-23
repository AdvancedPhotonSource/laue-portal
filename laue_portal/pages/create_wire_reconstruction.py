import datetime
import glob
import logging
import os
import urllib.parse
import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, State, set_props
from dash.exceptions import PreventUpdate
from sqlalchemy.orm import Session
import laue_portal.database.db_utils as db_utils
import laue_portal.database.db_schema as db_schema
import laue_portal.components.navbar as navbar
from laue_portal.database.db_utils import get_catalog_data, remove_root_path_prefix, parse_parameter
from laue_portal.components.wire_recon_form import wire_recon_form, set_wire_recon_form_props
from laue_portal.components.form_base import _field
from laue_portal.components.validation_alerts import validation_alerts
from laue_portal.processing.redis_utils import enqueue_wire_reconstruction, STATUS_REVERSE_MAPPING
from laue_portal.config import DEFAULT_VARIABLES
from laue_portal.pages.validation_helpers import (
    apply_validation_highlights,
    update_validation_alerts,
    safe_float,
    validate_numeric_range,
    validate_file_exists,
    validate_directory_exists
)
from laue_portal.pages.callback_registrars import (
    register_update_path_fields_callback,
    register_load_file_indices_callback,
    register_check_filenames_callback
)
from srange import srange
import laue_portal.database.session_utils as session_utils
import re
from difflib import SequenceMatcher
from itertools import combinations

logger = logging.getLogger(__name__)

JOB_DEFAULTS = {
    "computer_name": 'example_computer',
    "status": 0, #pending, running, finished, stopped
    "priority": 0,
    "submit_time": datetime.datetime.now(),
    "start_time": datetime.datetime.now(),
    "finish_time": datetime.datetime.now(),
}

WIRERECON_DEFAULTS = {
    "scanNumber": 276994,
    "geoFile": "Run1/geofiles/geoN_2023-04-06_03-07-11_cor6.xml",
    "percent_brightest": 100,
    "depth_start": -50,
    "depth_end": 150,
    "depth_resolution": 1,
    "outputFolder": "analysis/scan_%d/rec_%d/data",#"wire_recons",
    "scanPoints": "7",#"1",  # String field for srange parsing
    "wire_edges": "leading",
}

CATALOG_DEFAULTS = {
    "filefolder": "tests/data/gdata",
    "filenamePrefix": "HAs_long_laue1_",
}

# DEFAULT_VARIABLES = {
#     "author": "",
#     "notes": "",
#     "root_path": "/net/s34data/export/s34data1/LauePortal/portal_workspace/",
#     "num_threads": 35,
#     "memory_limit_mb": 50000,
#     "verbose": 1,
# }

dash.register_page(__name__)

layout = dbc.Container(
    [html.Div([
        navbar.navbar,
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
        html.Hr(),
        dbc.Row(
                [
                    dbc.Col(
                        html.H3(id="wirerecon-title", children="New Wire Reconstruction"),
                        width="auto",   # shrink to content
                    ),
                    dbc.Col(
                        dbc.Button(
                            "Validate",
                            id="validate-btn",
                            color="secondary",
                            style={"minWidth": 150, "maxWidth": "150px", "width": "100%"},
                        ),
                        width="auto",
                        className="ms-3",  # small gap from title
                    ),
                    dbc.Col(
                        dbc.Button(
                            "Submit",
                            id="submit_wire",
                            color="primary",
                            style={"minWidth": 150, "maxWidth": "150px", "width": "100%"},
                        ),
                        width="auto",
                        className="ms-2",
                    ),
                ],
                className="g-2",     # gutter between cols
                justify="center",     # CENTER horizontally
                align="center",       # CENTER vertically
            ),
        html.Hr(),
        validation_alerts,
        dbc.Row([
                dbc.Col(
                    dbc.Button(
                        "Set from ...",
                        id="upload-wireconfig",
                        color="secondary",
                        style={"minWidth": 150, "maxWidth": "150px", "width": "100%"},
                    ),
                    width="auto",
                ),
                dbc.Col(
                    _field("Author", "author", kwargs={"type": "text", "placeholder": "Required! Enter author or Tag for the reconstruction"}),
                    width="auto",
                    style={"minWidth": "300px", "flexGrow": 1},
                ),
            ],
            justify="start",
            className="mb-0",
        ),
        # html.Hr(),
        wire_recon_form,
        # dcc.Store(id="next-wire-recon-id"),
        dcc.Store(id="wirerecon-data-loaded-trigger"),
    ],
    )
    ],
    className='dbc', 
    fluid=True
)

def validate_wire_reconstruction_inputs(ctx):
    """
    Validate specified wire reconstruction inputs using callback context.
    
    Parameters:
    - ctx: dash.callback_context containing states_list with field IDs and values
    
    Returns:
        validation_result (dict): {
            'errors': dict mapping param_name to list of error messages,
            'warnings': dict mapping param_name to list of warning messages,
            'successes': dict mapping param_name to empty string (for params that passed)
        }
    """
    errors = {}
    warnings = {}
    successes = {}
    # Dictionary to store parsed parameter lists
    parsed_params = {}
    
    # Hard-coded list of field IDs to validate (excludes 'notes')
    all_field_ids = [
        'data_path',
        'filenamePrefix',
        'scanPoints',
        'geoFile',
        'depth_start',
        'depth_end',
        'depth_resolution',
        'percent_brightest',
        'outputFolder',
        'root_path',
        'scanNumber',
        'author',
    ]
    
    # Create database session for catalog validation
    session = Session(session_utils.get_engine())
    
    # Extract parameters from callback context using the hard-coded field list
    # ctx.states is a dict with format {'component_id.prop_name': value}
    all_params = {}
    for key, value in ctx.states.items():
        # Extract component_id from 'component_id.prop_name'
        component_id = key.split('.')[0]
        # Only include fields in our validation list
        if component_id in all_field_ids:
            all_params[component_id] = value
    
    # Extract individual parameter values
    root_path = all_params.get('root_path', '')
    data_path = all_params.get('data_path')
    # filenamePrefix = all_params.get('filenamePrefix')
    # scanPoints = all_params.get('scanPoints')
    # geoFile = all_params.get('geoFile')
    # depth_start = all_params.get('depth_start')
    # depth_end = all_params.get('depth_end')
    # depth_resolution = all_params.get('depth_resolution')
    # percent_brightest = all_params.get('percent_brightest')
    # outputFolder = all_params.get('outputFolder')
    # scanNumber = all_params.get('scanNumber')
    
    # Validate root_path directory exists
    if not root_path:
        errors.setdefault('root_path', []).append("Root path is required")
    elif not os.path.exists(root_path):
        errors.setdefault('root_path', []).append(f"Root path directory does not exist: {root_path}")
    else: #Added to pass over in later loop over all_params
        parsed_params['root_path'] = root_path
        successes['root_path'] = ''
    
    # Parse data_path first to determine number of scans
    try:
        data_path_list = parse_parameter(data_path)
        num_inputs = len(data_path_list)
        parsed_params['data_path'] = data_path_list
    except ValueError as e:
        errors.setdefault('data_path', []).append(f"Data path parsing error: {str(e)}")
        # Close session before early return
        session.close()
        # Return early since we can't validate other parameters without knowing num_inputs
        validation_result = {
            'errors': errors,
            'warnings': warnings,
            'successes': successes
        }
        return validation_result
    
    # Check data_path separately since we already parsed it
    if not data_path:
        errors.setdefault('data_path', []).append("Data path is required")
    else:
        successes['data_path'] = ''
    
    # Validate all other parameters by iterating over all_params    
    for param_name, param_value in all_params.items():
        # Skip already handled parameters
        if param_name in parsed_params: #{'root_path', 'data_path'}
            continue
        # Check 1: Is it missing/empty?
        is_missing = False
        if param_name in ['depth_start', 'depth_end', 'depth_resolution', 'percent_brightest']:
            # Numeric fields: check for None or empty string (0 is valid)
            if param_value is None or param_value == '':
                is_missing = True
        else:
            # Other fields: check for falsy values
            if not param_value:
                is_missing = True
        
        if is_missing:
            # Special case for scanNumber: only warning, not error
            if param_name == 'scanNumber':
                warnings.setdefault(param_name, []).append("Scan Number is missing") #warnings.append(f"{param_name.replace('_', ' ').title()} is missing")
                continue  # Skip parsing
            else:
                errors.setdefault(param_name, []).append(f"{param_name.replace('_', ' ').title()} is required")
                continue  # Skip parsing if missing
        
        # Check 2: Parse the parameter
        try:
            parsed_list = parse_parameter(param_value, num_inputs)
        except ValueError as e:
            # Special case for scanNumber: only warning, not error
            if param_name == 'scanNumber':
                warnings.setdefault(param_name, []).append(f"{param_name} parsing error: {str(e)}")
                continue  # Skip length check
            else:
                errors.setdefault(param_name, []).append(f"{param_name} parsing error: {str(e)}")
                continue  # Skip length check if parsing failed
        
        # Check 3: Verify length matches num_inputs
        if len(parsed_list) != num_inputs:
            # Special case for scanNumber: only warning, not error
            if param_name == 'scanNumber':
                warnings.setdefault(param_name, []).append(f"{param_name} count ({len(parsed_list)}) does not match number of inputs ({num_inputs})")
            else:
                errors.setdefault(param_name, []).append(f"{param_name} count ({len(parsed_list)}) does not match number of inputs ({num_inputs})")
        
        # Store the parsed list in the dictionary
        parsed_params[param_name] = parsed_list
    
    # Validate each input, skipping fields that failed global validation
    for i in range(num_inputs):
        input_prefix = f"Input {i+1}: " if num_inputs > 1 else ""
        
        # Initialize depth_span as None (will be calculated if both start and end are valid)
        depth_span = None
        
        # 1. Validate depth parameters for this input
        # Check if depth_start is None (only needs depth_start to be valid)
        if 'depth_start' not in errors:
            current_depth_start = parsed_params['depth_start'][i]
            if not current_depth_start:
                errors.setdefault('depth_start', []).append(f"{input_prefix}Depth start is required")
            depth_start_val = safe_float(current_depth_start)
            if depth_start_val is None:  # Failed conversion (not just empty)
                errors.setdefault('depth_start', []).append(f"{input_prefix}Depth start must be a valid number")
        
        # Check if depth_end is None (only needs depth_end to be valid)
        if 'depth_end' not in errors:
            current_depth_end = parsed_params['depth_end'][i]
            if not current_depth_end:
                errors.setdefault('depth_end', []).append(f"{input_prefix}Depth end is required")
            depth_end_val = safe_float(current_depth_end)
            if depth_end_val is None:  # Failed conversion (not just empty)
                errors.setdefault('depth_end', []).append(f"{input_prefix}Depth end must be a valid number")
        
        # Check if depth_resolution is None (only needs depth_resolution to be valid)
        if 'depth_resolution' not in errors:
            current_depth_resolution = parsed_params['depth_resolution'][i]
            if not current_depth_resolution:
                errors.setdefault('depth_resolution', []).append(f"{input_prefix}Depth resolution is required")
            depth_resolution_val = safe_float(current_depth_resolution)
            if depth_resolution_val is None:  # Failed conversion (not just empty)
                errors.setdefault('depth_resolution', []).append(f"{input_prefix}Depth resolution must be a valid number")
        
        # Check start < end (needs BOTH depth_start AND depth_end to be valid)
        if 'depth_start' not in errors and 'depth_end' not in errors:
            if depth_start_val is not None and depth_end_val is not None:
                if depth_start_val >= depth_end_val:
                    errors.setdefault('depth_start', []).append(f"{input_prefix}Depth Start must be less than Depth End")
                    errors.setdefault('depth_end', []).append(f"{input_prefix}Depth Start must be less than Depth End")
                
                # Calculate depth_span once (used in multiple checks below)
                depth_span = depth_end_val - depth_start_val
                
                # Warning: large depth range (only needs depth_start and depth_end)
                if depth_span > 500:
                    if 'depth_start' not in errors:
                        warnings.setdefault('depth_start', []).append(f"{input_prefix}Total depth range ({depth_span} µm) is large (> 500 µm)")
                    if 'depth_end' not in errors:
                        warnings.setdefault('depth_end', []).append(f"{input_prefix}Total depth range ({depth_span} µm) is large (> 500 µm)")
        
        # Check resolution value (only needs depth_resolution to be valid)
        if 'depth_resolution' not in errors:
            if depth_resolution_val is not None:
                # Error: resolution must be positive
                if depth_resolution_val <= 0:
                    errors.setdefault('depth_resolution', []).append(f"{input_prefix}Depth Resolution must be positive")
                # Warning: resolution too small
                elif depth_resolution_val < 0.1:
                    warnings.setdefault('depth_resolution', []).append(f"{input_prefix}Depth Resolution ({depth_resolution_val} µm) is very small (< 0.1 µm)")
        
        # Check resolution < range (needs ALL THREE to be valid)
        if depth_span is not None:
            if 'depth_resolution' not in errors and depth_resolution_val is not None:
                # Check if resolution is less than range
                if depth_resolution_val > abs(depth_span):
                    errors.setdefault('depth_start', []).append(f"{input_prefix}Depth Resolution ({depth_resolution_val} µm) must be less than or equal to depth range ({abs(depth_span)} µm)")
                    errors.setdefault('depth_end', []).append(f"{input_prefix}Depth Resolution ({depth_resolution_val} µm) must be less than or equal to depth range ({abs(depth_span)} µm)")
                    errors.setdefault('depth_resolution', []).append(f"{input_prefix}Depth Resolution ({depth_resolution_val} µm) must be less than or equal to depth range ({abs(depth_span)} µm)")
        
        # 2. Validate percent_brightest for this input
        if 'percent_brightest' not in errors:
            current_percent = parsed_params['percent_brightest'][i]
            if not current_percent:
                errors.setdefault('percent_brightest', []).append(f"{input_prefix}Intensity percentile is required")
            percent_val = safe_float(current_percent)
            if percent_val is not None:
                if percent_val <= 0 or percent_val > 100:
                    errors.setdefault('percent_brightest', []).append(f"{input_prefix}Intensity percentile must be between 0 and 100")
        
        # 3. Check if geometry file exists for this input (skip if root_path invalid)
        if 'root_path' not in errors and 'geoFile' not in errors:
            current_geoFile = parsed_params['geoFile'][i]
            if not current_geoFile:
                errors.setdefault('geoFile', []).append(f"{input_prefix}Geometry file is required")
            else:
                full_geo_path = os.path.join(root_path, current_geoFile.lstrip('/'))
                if not os.path.exists(full_geo_path):
                    errors.setdefault('geoFile', []).append(f"{input_prefix}Geometry file not found: {current_geoFile}")
        
        # 4. Check if output folder already exists for this input (skip if root_path invalid)
        # Note: We cannot validate this properly if outputFolder contains %d placeholders
        # because we don't know the scan number or wirerecon_id at validation time.
        # This check is skipped if %d is present in the path.
        if 'root_path' not in errors and 'outputFolder' not in errors:
            current_outputFolder = parsed_params['outputFolder'][i]
            if not current_outputFolder:
                errors.setdefault('outputFolder', []).append(f"{input_prefix}Output folder is required")
            elif root_path and '%d' not in current_outputFolder:
                full_output_path = os.path.join(root_path, current_outputFolder.lstrip('/'))
                if os.path.exists(full_output_path):
                    if 'outputFolder' not in errors:
                        warnings.setdefault('outputFolder', []).append(f"{input_prefix}Output folder already exists: {current_outputFolder}")
        
        # 5. Check if data files exist for this input (skip if root_path invalid)
        if 'root_path' not in errors and 'data_path' not in errors:
            current_data_path = parsed_params['data_path'][i]
            current_full_data_path = os.path.join(root_path, current_data_path.lstrip('/'))
            
            # Check if directory exists
            if not os.path.exists(current_full_data_path):
                errors.setdefault('data_path', []).append(f"{input_prefix}Data directory not found: {current_data_path}")
            else:
                # Validate scanNumber against Catalog table (after confirming directory exists)
                if 'scanNumber' not in errors and all_params.get('scanNumber') and 'scanNumber' in parsed_params:
                    try:
                        scan_num_int = int(parsed_params['scanNumber'][i])
                        
                        # Get catalog data for this scan
                        catalog_data = get_catalog_data(session, scan_num_int, root_path, CATALOG_DEFAULTS)
                        
                        if catalog_data and catalog_data.get('data_path'):
                            catalog_full_data_path = os.path.join(root_path, catalog_data['data_path'].lstrip('/'))
                            if catalog_full_data_path != current_full_data_path:
                                warnings.setdefault('data_path', []).append(
                                    f"{input_prefix}Catalog entry for scan {scan_num_int} has path ({catalog_data['data_path']}) "
                                    f"that differs from specified data path ({current_data_path})"
                                )
                        else:
                            # No catalog entry found for this scan number
                            warnings.setdefault('scanNumber', []).append(
                                f"{input_prefix}No catalog entry found for scan {scan_num_int}"
                            )
                    except (ValueError, TypeError, IndexError):
                        pass  # Already handled in scanNumber validation
                
                # Check if directory contains any files
                all_files = [f for f in os.listdir(current_full_data_path) if os.path.isfile(os.path.join(current_full_data_path, f))]
                if not all_files:
                    errors.setdefault('data_path', []).append(f"{input_prefix}Data directory contains no files: {current_data_path}")
                else:
                    # Only check filename prefix if it passed global validation
                    if 'filenamePrefix' not in errors:
                        # Parse filename prefix
                        current_filename_prefix_str = parsed_params['filenamePrefix'][i]
                        current_filename_prefix = [s.strip() for s in current_filename_prefix_str.split(',')] if current_filename_prefix_str else []
                        
                        # Check for actual files using glob - pinpoint which field has the error
                        for current_filename_prefix_i in current_filename_prefix:
                            # Check if ANY files match this prefix pattern (without scan point substitution)
                            prefix_pattern = os.path.join(current_full_data_path, current_filename_prefix_i.replace('%d', '*'))
                            prefix_matches = glob.glob(prefix_pattern + '*')
                            
                            if not prefix_matches:
                                errors.setdefault('filenamePrefix', []).append(f"{input_prefix}No files match prefix pattern: {current_filename_prefix_i}")
                            else:
                                # Check specific scan points (only if scanPoints passed global validation)
                                if 'scanPoints' not in errors:
                                    current_scanPoints = parsed_params['scanPoints'][i]
                                    
                                    try:
                                        scanPoints_srange = srange(current_scanPoints)
                                        scanPoint_nums = scanPoints_srange.list()
                                    except Exception as e:
                                        errors.setdefault('scanPoints', []).append(f"{input_prefix}Invalid scan points format: {current_scanPoints}")
                                        continue
                                    
                                    # Collect missing scan points for this prefix
                                    missing_scanpoints = []
                                    for scanPoint_num in scanPoint_nums:
                                        file_str = current_filename_prefix_i % scanPoint_num if '%d' in current_filename_prefix_i else current_filename_prefix_i
                                        scanpoint_pattern = os.path.join(current_full_data_path, file_str)
                                        scanpoint_matches = glob.glob(scanpoint_pattern + '*')
                                        
                                        if not scanpoint_matches:
                                            missing_scanpoints.append(str(scanPoint_num))
                                    
                                    # If there are missing scan points, add a single error message for this prefix
                                    if missing_scanpoints:
                                        # Limit the number of scan points shown
                                        if len(missing_scanpoints) <= 5:
                                            scanpoints_str = ", ".join(missing_scanpoints)
                                        else:
                                            scanpoints_str = ", ".join(missing_scanpoints[:5]) + f", ... and {len(missing_scanpoints) - 5} more"
                                        
                                        errors.setdefault('scanPoints', []).append(
                                            f"{input_prefix}Missing files for {current_filename_prefix_i} (scan points: {scanpoints_str})"
                                        )
        
        # 6. Validate scanNumber: check that entry is a valid integer
        if 'scanNumber' not in errors and 'scanNumber' in parsed_params:
            current_scanNumber = parsed_params['scanNumber'][i]
            try:
                current_scanNumber.isdigit()
            except (ValueError, TypeError):
                if 'scanNumber' not in errors:
                    warnings.setdefault('scanNumber', []).append(f"{input_prefix}Scan number is not a valid integer: {current_scanNumber}")
    
    # Add successes for parameters that passed all validations
    # Only add to successes if the parameter has neither errors nor warnings
    for param_name in all_field_ids:
        if param_name not in errors and param_name not in warnings:
            successes[param_name] = ''
    
    # Close database session
    session.close()
    
    validation_result = {
        'errors': errors,
        'warnings': warnings,
        'successes': successes
    }
    return validation_result


"""
=======================
Callbacks
=======================
"""
@dash.callback(
    Input('validate-btn', 'n_clicks'),
    State('data_path', 'value'),
    State('filenamePrefix', 'value'),
    State('scanPoints', 'value'),
    State('geoFile', 'value'),
    State('depth_start', 'value'),
    State('depth_end', 'value'),
    State('depth_resolution', 'value'),
    State('percent_brightest', 'value'),
    State('outputFolder', 'value'),
    State('root_path', 'value'),
    State('scanNumber', 'value'),
    State('author', 'value'),
    prevent_initial_call=True,
)
def validate_inputs(
    n_clicks,
    data_path,
    filenamePrefix,
    scanPoints,
    geoFile,
    depth_start,
    depth_end,
    depth_resolution,
    percent_brightest,
    outputFolder,
    root_path,
    scanNumber,
    author,
):
    """Handle Validate button click"""
    
    # Get callback context
    ctx = dash.callback_context
    
    # Run validation using ctx
    validation_result = validate_wire_reconstruction_inputs(ctx)
    
    # Apply field highlights using helper function
    apply_validation_highlights(validation_result)
    
    # Update validation alerts using helper function
    update_validation_alerts(validation_result)


@dash.callback(
    Input('submit_wire', 'n_clicks'),
    
    State('scanNumber', 'value'),
    
    # User text
    State('author', 'value'),
    State('notes', 'value'),
    
    # Recon constraints
    State('geoFile', 'value'),
    State('percent_brightest', 'value'),
    State('wire_edges', 'value'),
    
    # Depth parameters
    State('depth_start', 'value'),
    State('depth_end', 'value'),
    State('depth_resolution', 'value'),
    
    # Files
    State('scanPoints', 'value'),
    State('data_path', 'value'),
    State('filenamePrefix', 'value'),
    
    # Output
    State('outputFolder', 'value'),
    
    prevent_initial_call=True,
)
def submit_parameters(n,
    scanNumber,
    
    # User text
    author,
    notes,

    # Recon constraints
    geometry_file,
    percent_brightest,
    wire_edges,

    # Depth parameters
    depth_start,
    depth_end,
    depth_resolution,
    
    # Files
    scanPoints,
    data_path,
    filenamePrefix,
    
    # Output
    output_folder,
):
    """
    Submit parameters for wire reconstruction job(s).
    Handles both single scan and pooled scan submissions.
    """
    # Get callback context
    ctx = dash.callback_context
    
    # Run validation before submission using ctx
    validation_result = validate_wire_reconstruction_inputs(ctx)
    
    # Apply field highlights for all cases (error, warning, success)
    apply_validation_highlights(validation_result)
    
    # Update validation alerts using helper function
    update_validation_alerts(validation_result)
    
    # Extract to local variables for cleaner code
    errors = validation_result['errors']
    # warnings = validation_result['warnings']
    
    # Block submission if there are errors
    if errors:
        set_props("alert-submit", {
            'is_open': True,
            'children': 'Submission blocked due to validation errors. Please fix the errors and try again.',
            'color': 'danger'
        })
        return
    
    # Parse data_path first to get the number of inputs
    data_path_list = parse_parameter(data_path)
    num_inputs = len(data_path_list)
    
    # Parse all other parameters with num_inputs
    try:
        scanNumber_list = parse_parameter(scanNumber, num_inputs)
        author_list = parse_parameter(author, num_inputs)
        notes_list = parse_parameter(notes, num_inputs)
        geoFile_list = parse_parameter(geometry_file, num_inputs)
        percent_brightest_list = parse_parameter(percent_brightest, num_inputs)
        wire_edges_list = parse_parameter(wire_edges, num_inputs)
        depth_start_list = parse_parameter(depth_start, num_inputs)
        depth_end_list = parse_parameter(depth_end, num_inputs)
        depth_resolution_list = parse_parameter(depth_resolution, num_inputs)
        scanPoints_list = parse_parameter(scanPoints, num_inputs)
        data_path_list = parse_parameter(data_path, num_inputs)
        filenamePrefix_list = parse_parameter(filenamePrefix, num_inputs)
        outputFolder_list = parse_parameter(output_folder, num_inputs)
    except ValueError as e:
        # Error: mismatched lengths
        set_props("alert-submit", {
            'is_open': True, 
            'children': str(e),
            'color': 'danger'
        })
        return
    
    root_path = DEFAULT_VARIABLES["root_path"]
    num_threads = DEFAULT_VARIABLES["num_threads"]
    memory_limit_mb = DEFAULT_VARIABLES["memory_limit_mb"]
    verbose = DEFAULT_VARIABLES["verbose"]
    
    wirerecons_to_enqueue = []

    # First loop: Create all database entries for each listed scanNumber
    with Session(session_utils.get_engine()) as session:
        try:
            for i in range(num_inputs):
                # Extract values for this scan
                current_scanNumber = scanNumber_list[i]
                current_output_folder = outputFolder_list[i]
                current_geo_file = geoFile_list[i]
                current_scanPoints = scanPoints_list[i]

                # Convert relative paths to full paths
                full_geometry_file = os.path.join(root_path, current_geo_file.lstrip('/'))

                next_wirerecon_id = db_utils.get_next_id(session, db_schema.WireRecon)
                # Now that we have the ID, format the output folder path
                try:
                    if '%d' in current_output_folder:
                        formatted_output_folder = current_output_folder % (current_scanNumber, next_wirerecon_id)
                    else:
                        formatted_output_folder = current_output_folder
                except TypeError:
                    formatted_output_folder = current_output_folder # Fallback if formatting fails
                
                full_output_folder = os.path.join(root_path, formatted_output_folder.lstrip('/'))
                
                # Create output directory if it doesn't exist
                try:
                    os.makedirs(full_output_folder, exist_ok=True)
                    logger.info(f"Output directory: {full_output_folder}")
                except Exception as e:
                    logger.error(f"Failed to create output directory {full_output_folder}: {e}")
                    set_props("alert-submit", {'is_open': True, 
                                               'children': f'Failed to create output directory: {str(e)}',
                                               'color': 'danger'})
                    continue

                JOB_DEFAULTS.update({'submit_time':datetime.datetime.now()})
                JOB_DEFAULTS.update({'start_time':datetime.datetime.now()})
                JOB_DEFAULTS.update({'finish_time':datetime.datetime.now()})

                job = db_schema.Job(
                    computer_name=JOB_DEFAULTS['computer_name'],
                    status=JOB_DEFAULTS['status'],
                    priority=JOB_DEFAULTS['priority'],
                    submit_time=JOB_DEFAULTS['submit_time'],
                    start_time=JOB_DEFAULTS['start_time'],
                    finish_time=JOB_DEFAULTS['finish_time'],
                )
                session.add(job)
                session.flush()  # Get job_id without committing
                job_id = job.job_id

                # Create subjobs for parallel processing
                # Parse scanPoints string using srange
                scanPoints_srange = srange(current_scanPoints)
                scanPointslen = scanPoints_srange.len()
                
                for _ in range(scanPointslen):
                    subjob = db_schema.SubJob(
                        job_id=job_id,
                        computer_name=JOB_DEFAULTS['computer_name'],
                        status=STATUS_REVERSE_MAPPING["Queued"],
                        priority=JOB_DEFAULTS['priority']
                    )
                    session.add(subjob)

                # Get filefolder and filenamePrefix
                current_data_path = data_path_list[i]
                current_filename_prefix_str = filenamePrefix_list[i]
                current_filename_prefix = [s.strip() for s in current_filename_prefix_str.split(',')] if current_filename_prefix_str else []
                # Build full path
                current_full_data_path=os.path.join(root_path, current_data_path.lstrip('/'))

                wirerecon = db_schema.WireRecon(
                    scanNumber=current_scanNumber,
                    job_id=job_id,
                    filefolder=current_full_data_path,
                    filenamePrefix=current_filename_prefix,
                    
                    # User text
                    author=author_list[i],
                    notes=notes_list[i],
                    
                    # Recon constraints
                    geoFile=full_geometry_file,  # Store full path in database
                    percent_brightest=percent_brightest_list[i],
                    wire_edges=wire_edges_list[i],
                    
                    # Depth parameters
                    depth_start=depth_start_list[i],
                    depth_end=depth_end_list[i],
                    depth_resolution=depth_resolution_list[i],
                    
                    # Compute parameters
                    num_threads=num_threads,
                    memory_limit_mb=memory_limit_mb,
                    
                    # Files
                    scanPoints=current_scanPoints,
                    scanPointslen=scanPointslen,
                    
                    # Output
                    outputFolder=full_output_folder,  # Store full path in database
                    verbose=verbose,
                )
                # config_dict = db_utils.create_config_obj(wirerecon)
                session.add(wirerecon)
                
                wirerecons_to_enqueue.append({
                    "job_id": job_id,
                    "scanPoints": current_scanPoints,
                    "filefolder": current_full_data_path,
                    "filenamePrefix": current_filename_prefix,
                    "outputFolder": full_output_folder,
                    "geoFile": full_geometry_file,
                    "depth_start": depth_start_list[i],
                    "depth_end": depth_end_list[i],
                    "depth_resolution": depth_resolution_list[i],
                    "percent_brightest": percent_brightest_list[i],
                    "wire_edges": wire_edges_list[i],
                    "memory_limit_mb": memory_limit_mb,
                    "num_threads": num_threads,
                    "verbose": verbose,
                    "scanNumber": current_scanNumber,
                })

            session.commit()
            set_props("alert-submit", {'is_open': True,
                                       'children': 'Entries Added to Database',
                                       'color': 'success'})
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to create database entries: {e}")
            set_props("alert-submit", {'is_open': True,
                                       'children': f'Failed to create database entries: {str(e)}',
                                       'color': 'danger'})
            return

    # Second loop: Enqueue jobs to Redis
    for i, spec in enumerate(wirerecons_to_enqueue):
        try:
            # Extract values for this scan
            full_data_path = spec["filefolder"]
            current_filename_prefix = spec["filenamePrefix"]
            
            scanPoints_srange = srange(spec["scanPoints"])
            scanPoint_nums = scanPoints_srange.list()
            
            # Prepare lists of input and output files for all subjobs
            input_files = []
            
            for current_filename_prefix_i in current_filename_prefix:
                for scanPoint_num in scanPoint_nums:
                    # Apply %d formatting with scanPoint_num if prefix contains %d placeholder
                    file_str = current_filename_prefix_i % scanPoint_num if '%d' in current_filename_prefix_i else current_filename_prefix_i
                    input_file_pattern = os.path.join(full_data_path, file_str)
                    
                    # Use glob to find matching files
                    matched_files = glob.glob(input_file_pattern + '*')
                    
                    if not matched_files:
                        raise ValueError(f"No files found matching pattern: {input_file_pattern}")
                    
                    input_files.extend(matched_files)
            
            # Build output_files from input_files
            output_files = [
                os.path.join(spec["outputFolder"], os.path.splitext(os.path.basename(file))[0] + "_")
                for file in input_files
            ]
            
            # Enqueue the batch job with all files
            depth_range = (spec["depth_start"], spec["depth_end"])
            rq_job_id = enqueue_wire_reconstruction(
                job_id=spec["job_id"],
                input_files=input_files,
                output_files=output_files,
                geometry_file=spec["geoFile"],  # Use full path
                depth_range=depth_range,
                resolution=spec["depth_resolution"],
                percent_brightest=spec["percent_brightest"], #percent_to_process
                wire_edge=spec["wire_edges"],  # Note: form uses 'wire_edges', function expects 'wire_edge'
                memory_limit_mb=spec["memory_limit_mb"],
                num_threads=spec["num_threads"],
                verbose=spec["verbose"],
                detector_number=0  # Default detector number
            )
            
            logger.info(f"Wire reconstruction batch job {spec['job_id']} enqueued with RQ ID: {rq_job_id} for {len(input_files)} files")
            set_props("alert-submit", {'is_open': True,
                                       'children': f'Job {spec["job_id"]} submitted to queue with {len(input_files)} file(s)',
                                       'color': 'info'})
        except Exception as e:
            # Provide more context to help diagnose format issues and input parsing
            logger.error(
                f"Failed to enqueue job {spec['job_id']}: {e}. "
                f"filenamePrefix='{current_filename_prefix_str}', "
                f"parsed prefixes={current_filename_prefix}, "
                f"scanPoints='{spec['scanPoints']}', data_path='{current_data_path}'"
            )
            set_props("alert-submit", {
                'is_open': True,
                'children': f'Failed to queue job {spec["job_id"]}: {str(e)}. '
                            f'filenamePrefix={current_filename_prefix_str}, '
                            f'scanPoints={spec["scanPoints"]}',
                'color': 'danger'
            })


# Register shared callbacks
register_update_path_fields_callback(
    button_id='wirerecon-update-path-fields-btn',
    scan_number_id='scanNumber',
    root_path_id='root_path',
    data_path_id='data_path',
    filename_prefix_id='filenamePrefix',
    alert_id='alert-scan-loaded',
    catalog_defaults=CATALOG_DEFAULTS
)

register_load_file_indices_callback(
    button_id='wirerecon-load-file-indices-btn',
    data_loaded_trigger_id='wirerecon-data-loaded-trigger',
    data_path_id='data_path',
    filename_prefix_id='filenamePrefix',
    scan_points_id='scanPoints',
    depth_range_id=None,  # Wire recon doesn't use depth range
    alert_id='alert-scan-loaded',
    num_indices=1
)

register_check_filenames_callback(
    check_button_id='wirerecon-check-filenames-btn',
    update_button_id='wirerecon-update-path-fields-btn',
    data_loaded_trigger_id='wirerecon-data-loaded-trigger',
    data_path_id='data_path',
    filename_prefix_id='filenamePrefix',
    filename_templates_id='wirerecon-filename-templates',
    num_indices=1
)

# @dash.callback(
#     Input('url-create-wirerecon','pathname'),
#     prevent_initial_call=True,
# )
# def get_wirerecons(path):
#     root_path = DEFAULT_VARIABLES["root_path"]
#     if path == '/create-wire-reconstruction':
#         # Create a WireRecon object with form defaults (not for database insertion)
#         wirerecon_form_data = db_schema.WireRecon(
#             scanNumber=WIRERECON_DEFAULTS["scanNumber"],
            
#             # User text
#             author=DEFAULT_VARIABLES["author"],
#             notes=DEFAULT_VARIABLES["notes"],
            
#             # Recon constraints
#             geoFile=WIRERECON_DEFAULTS["geoFile"],
#             percent_brightest=WIRERECON_DEFAULTS["percent_brightest"],
#             wire_edges=WIRERECON_DEFAULTS["wire_edges"],
            
#             # Depth parameters
#             depth_start=WIRERECON_DEFAULTS["depth_start"],
#             depth_end=WIRERECON_DEFAULTS["depth_end"],
#             depth_resolution=WIRERECON_DEFAULTS["depth_resolution"],
            
#             # Compute parameters
#             num_threads=DEFAULT_VARIABLES["num_threads"],
#             memory_limit_mb=DEFAULT_VARIABLES["memory_limit_mb"],
            
#             # Files
#             scanPoints=WIRERECON_DEFAULTS["scanPoints"],
#             scanPointslen=srange(WIRERECON_DEFAULTS["scanPoints"]).len(),
            
#             # Output
#             outputFolder=WIRERECON_DEFAULTS["outputFolder"],
#             verbose=DEFAULT_VARIABLES["verbose"],
#         )
#         # Add root_path from DEFAULT_VARIABLES
#         wirerecon_form_data.root_path = root_path
#         with Session(session_utils.get_engine()) as session:
#             # # Get next wirerecon_id
#             # next_wirerecon_id = db_utils.get_next_id(session, db_schema.WireRecon)
#             # # Store next_wirerecon_id and update title
#             # set_props('next-wire-recon-id', {'value': next_wirerecon_id})
#             # set_props('wirerecon-title', {'children': f"New wire recon {next_wirerecon_id}"})
            
#             # Retrieve data_path and filenamePrefix from catalog data
#             catalog_data = get_catalog_data(session, WIRERECON_DEFAULTS["scanNumber"], root_path, CATALOG_DEFAULTS)
#         wirerecon_form_data.data_path = catalog_data["data_path"]
#         wirerecon_form_data.filenamePrefix = catalog_data["filenamePrefix"]
            
#         set_wire_recon_form_props(wirerecon_form_data)
#     else:
#         raise PreventUpdate


@dash.callback(
    Output('wirerecon-data-loaded-trigger', 'data'),
    Input('url-create-wirerecon', 'href'),
    prevent_initial_call=True,
)
def load_scan_data_from_url(href):
    """
    Load scan data and optionally existing wirerecon data when provided in URL query parameters
    URL format: /create-wire-reconstruction?scan_id={scan_id}
    Pooled URL format: /create-wire-reconstruction?scan_id={scan_ids}
    With wirerecon_id: /create-wire-reconstruction?scan_id={scan_id}&wirerecon_id={wirerecon_id}
    Pooled with wirerecon_id: /create-wire-reconstruction?scan_id={scan_ids}&wirerecon_id={wirerecon_ids}
    """
    if not href:
        raise PreventUpdate

    parsed_url = urllib.parse.urlparse(href)
    query_params = urllib.parse.parse_qs(parsed_url.query)
    
    scan_id_str = query_params.get('scan_id', [None])[0]
    wirerecon_id_str = query_params.get('wirerecon_id', [None])[0]

    root_path = DEFAULT_VARIABLES.get("root_path", "")

    if scan_id_str:
        with Session(session_utils.get_engine()) as session:
            # # Get next wirerecon_id
            # next_wirerecon_id = db_utils.get_next_id(session, db_schema.WireRecon)
            # # Store next_wirerecon_id and update title
            # set_props('next-wire-recon-id', {'value': next_wirerecon_id})
            # set_props('wirerecon-title', {'children': f"New wire recon {next_wirerecon_id}"})
            
            try:
                # This section handles both single and multiple/pooled scan numbers
                scan_ids = [int(sid) if sid and sid.lower() != 'none' else None for sid in (scan_id_str.split(',') if scan_id_str else [])]
                
                # Handle pooled wirerecon IDs
                wirerecon_ids = [int(wid) if wid and wid.lower() != 'none' else None for wid in (wirerecon_id_str.split(',') if wirerecon_id_str else [])]
                
                # Validate that lists have matching lengths
                if wirerecon_ids and len(wirerecon_ids) != len(scan_ids):
                    raise ValueError(f"Mismatch: {len(scan_ids)} scan IDs but {len(wirerecon_ids)} wirerecon IDs")
                
                # If no wirerecon IDs provided, fill with None
                if not wirerecon_ids:
                    wirerecon_ids = [None] * len(scan_ids)
                
                # Collect data paths and filename prefixes for each scan
                wirerecon_form_data_list = []
                found_items = []
                not_found_items = []
                for i, current_scan_id in enumerate(scan_ids):
                    current_wirerecon_id = wirerecon_ids[i]
                    
                    # Query metadata for current scan
                    metadata_data = session.query(db_schema.Metadata).filter(db_schema.Metadata.scanNumber == current_scan_id).first()
                    # scan_data = session.query(db_schema.Scan).filter(db_schema.Scan.scanNumber == scan_id).all()
                    
                    if metadata_data:
                        if current_wirerecon_id:
                            found_items.append(f"wire reconstruction {current_wirerecon_id}")
                        else:
                            found_items.append(f"scan {current_scan_id}")
                        
                        output_folder = WIRERECON_DEFAULTS["outputFolder"]
                        
                        # # Format output folder with scan number and wirerecon_id
                        # try:
                        #     output_folder = output_folder % (current_scan_id, next_wirerecon_id)
                        # except:
                        #     # If formatting fails, use the original string
                        #     pass
                        # next_wirerecon_id += 1
                        
                        # If wirerecon_id is provided, load existing wirerecon data
                        if current_wirerecon_id:
                            try:
                                wirerecon_data = session.query(db_schema.WireRecon).filter(db_schema.WireRecon.wirerecon_id == current_wirerecon_id).first()
                                if wirerecon_data:
                                    # Use existing wirerecon data as the base
                                    wirerecon_form_data = wirerecon_data
                                    # Update only the necessary fields
                                    wirerecon_form_data.outputFolder = output_folder
                                    # Convert file paths to relative paths
                                    wirerecon_form_data.geoFile = remove_root_path_prefix(wirerecon_data.geoFile, root_path)
                                    if wirerecon_data.filefolder:
                                        wirerecon_form_data.data_path = remove_root_path_prefix(wirerecon_data.filefolder, root_path)
                                    if wirerecon_data.filenamePrefix:
                                        wirerecon_form_data.filenamePrefix = wirerecon_data.filenamePrefix
                            
                            except (ValueError, Exception):
                                # If wirerecon_id is not valid or not found, create defaults
                                current_wirerecon_id = None
                        
                        # Create defaults if no wirerecon_id or if loading failed
                        else: #if not current_wirerecon_id:
                            # Create a WireRecon object with populated defaults from metadata/scan
                            wirerecon_form_data = db_schema.WireRecon(
                                scanNumber=current_scan_id,
                                outputFolder=output_folder,
                                **{k: v for k, v in WIRERECON_DEFAULTS.items() if k not in ['scanNumber', 'outputFolder']}
                            )
                        
                        # Add root_path from DEFAULT_VARIABLES
                        wirerecon_form_data.root_path = root_path
                        
                        if not all([hasattr(wirerecon_form_data, 'data_path'), getattr(wirerecon_form_data, 'filenamePrefix')]):
                            # Retrieve data_path and filenamePrefix from catalog data
                            catalog_data = get_catalog_data(session, current_scan_id, root_path, CATALOG_DEFAULTS)
                        if not hasattr(wirerecon_form_data, 'data_path'):
                            wirerecon_form_data.data_path = catalog_data.get('data_path', '')
                        if not getattr(wirerecon_form_data, 'filenamePrefix'):
                            # wirerecon_form_data.filenamePrefix = catalog_data.get('filenamePrefix', '')
                            wirerecon_form_data.filenamePrefix = catalog_data.get('filenamePrefix', [])

                        wirerecon_form_data_list.append(wirerecon_form_data)
                    else:
                        if current_wirerecon_id:
                            not_found_items.append(f"wire reconstruction {current_wirerecon_id}")
                        else:
                            not_found_items.append(f"scan {current_scan_id}")

                # Create pooled wirerecon_form_data by combining values from all scans
                if wirerecon_form_data_list:
                    pooled_wirerecon_form_data = db_schema.WireRecon()
                    
                    # Pool all attributes - both database columns and extra attributes
                    all_attrs = list(db_schema.WireRecon.__table__.columns.keys()) + ['root_path', 'data_path', 'filenamePrefix']
                    
                    for attr in all_attrs:
                        if attr == 'wirerecon_id': continue
                        
                        values = []
                        for d in wirerecon_form_data_list:
                            if hasattr(d, attr):
                                values.append(getattr(d, attr))
                        
                        if values:
                            if all(v == values[0] for v in values):
                                setattr(pooled_wirerecon_form_data, attr, values[0])
                            else:
                                setattr(pooled_wirerecon_form_data, attr, "; ".join(map(str, values)))
                    
                    # User text
                    pooled_wirerecon_form_data.author = DEFAULT_VARIABLES['author']
                    pooled_wirerecon_form_data.notes = DEFAULT_VARIABLES['notes']
                    # # Add root_path from DEFAULT_VARIABLES
                    # pooled_wirerecon_form_data.root_path = root_path
                    # Populate the form with the defaults
                    set_wire_recon_form_props(pooled_wirerecon_form_data)

                    # Set alert based on what was found
                    if not_found_items:
                        # Partial success
                        set_props("alert-scan-loaded", {
                            'is_open': True,
                            'children': f"Loaded data for {len(found_items)} items. Could not find: {', '.join(not_found_items)}.",
                            'color': 'warning'
                        })
                    else:
                        # Full success
                        set_props("alert-scan-loaded", {
                            'is_open': True,
                            'children': f"Successfully loaded and merged data from {len(found_items)} items into the form.",
                            'color': 'success'
                        })
                else:
                    # Fallback if no valid scans found
                    if not_found_items:
                        set_props("alert-scan-loaded", {
                            'is_open': True,
                            'children': f"Could not find any of the requested items: {', '.join(not_found_items)}. Displaying default values.",
                            'color': 'danger'
                        })

                    wirerecon_form_data = db_schema.WireRecon(
                        scanNumber=str(scan_id_str).replace(',','; '),
                        
                        # User text
                        author=DEFAULT_VARIABLES["author"],
                        notes=DEFAULT_VARIABLES["notes"],
                        
                        # Recon constraints
                        geoFile=WIRERECON_DEFAULTS["geoFile"],
                        percent_brightest=WIRERECON_DEFAULTS["percent_brightest"],
                        wire_edges=WIRERECON_DEFAULTS["wire_edges"],
                        
                        # Depth parameters
                        depth_start=WIRERECON_DEFAULTS["depth_start"],
                        depth_end=WIRERECON_DEFAULTS["depth_end"],
                        depth_resolution=WIRERECON_DEFAULTS["depth_resolution"],
                        
                        # Compute parameters
                        num_threads=DEFAULT_VARIABLES["num_threads"],
                        memory_limit_mb=DEFAULT_VARIABLES["memory_limit_mb"],
                        
                        # Files
                        scanPoints=WIRERECON_DEFAULTS["scanPoints"],
                        scanPointslen=srange(WIRERECON_DEFAULTS["scanPoints"]).len(),
                        
                        # Output
                        outputFolder=WIRERECON_DEFAULTS["outputFolder"],
                        verbose=DEFAULT_VARIABLES["verbose"],
                    )
                    
                    # Set root_path
                    wirerecon_form_data.root_path = root_path
                    wirerecon_form_data.data_path = ""
                    wirerecon_form_data.filenamePrefix = ""
                    
                    # Populate the form with the defaults
                    set_wire_recon_form_props(wirerecon_form_data)
                
            except Exception as e:
                set_props("alert-scan-loaded", {
                    'is_open': True, 
                    'children': f'Error loading scan data: {str(e)}',
                    'color': 'danger'
                })
    
    # Return timestamp to trigger downstream callbacks
    return datetime.datetime.now().isoformat()
