import datetime
import glob
import logging
import os
import urllib.parse
import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, set_props, State
from dash.exceptions import PreventUpdate
from sqlalchemy.orm import Session
import laue_portal.database.db_utils as db_utils
import laue_portal.database.db_schema as db_schema
import laue_portal.components.navbar as navbar
from laue_portal.database.db_utils import get_data_from_id, remove_root_path_prefix, parse_parameter, parse_IDnumber
from laue_portal.components.peakindex_form import peakindex_form, set_peakindex_form_props
from laue_portal.components.form_base import _field
from laue_portal.components.validation_alerts import validation_alerts
from laue_portal.processing.redis_utils import enqueue_peakindexing, STATUS_REVERSE_MAPPING
from laue_portal.config import DEFAULT_VARIABLES
from laue_portal.pages.validation_helpers import (
    apply_validation_highlights,
    update_validation_alerts,
    add_validation_message,
    safe_float,
    safe_int,
    validate_field_value,
    validate_numeric_range,
    validate_file_exists,
    validate_directory_exists,
    get_num_inputs_from_fields
)
from laue_portal.pages.callback_registrars import (
    register_update_path_fields_callback,
    register_load_file_indices_callback,
    register_check_filenames_callback,
    _merge_field_values
)
from srange import srange
import laue_portal.database.session_utils as session_utils

logger = logging.getLogger(__name__)


def build_output_folder_template(scan_num_int, data_path, 
                                 wirerecon_id_int=None, recon_id_int=None):
    """
    Build output folder template based on available IDs from database chain.
    Only the final action ID remains as %d.
    
    Parameters:
    - scan_num_int: scanNumber (int or None)
    - data_path: data path to use if scanNumber unknown
    - root_path: root path
    - wirerecon_id_int: wirerecon_id (int or None) - for peakindexing only
    - recon_id_int: recon_id (int or None) - for peakindexing only
    
    Returns:
    - Output folder template path (relative, without root_path prefix)
    """
    path_parts = ["analysis"]
    
    # Add scan directory only if scanNumber is known
    if scan_num_int is not None:
        path_parts.append(f"scan_{scan_num_int}")
    else:
        # If scanNumber is unknown, use data_path for context
        if data_path:
            clean_data_path = data_path.strip('/')
            path_parts.append(clean_data_path)
    
    # For peakindexing: add rec directory if wirerecon_id OR recon_id is known
    if wirerecon_id_int is not None:
        path_parts.append(f"rec_{wirerecon_id_int}")
    elif recon_id_int is not None:
        path_parts.append(f"rec_{recon_id_int}")
    
    # Add final action placeholder for peakindexing
    path_parts.append("index_%d")
    
    return os.path.join(*path_parts)


JOB_DEFAULTS = {
    "computer_name": 'example_computer',
    "status": 0, #pending, running, finished, stopped
    "priority": 0,
    "submit_time": datetime.datetime.now(),
    "start_time": datetime.datetime.now(),
    "finish_time": datetime.datetime.now(),
}

PEAKINDEX_DEFAULTS = {
    "scanNumber": 276994,
    # "peakProgram": "peaksearch",
    "threshold": "", #250
    "thresholdRatio": "",
    "maxRfactor": 0.5, #0.5
    "boxsize": 18, #18
    "max_number": 300,
    "min_separation": 20, #40
    "peakShape": "L", #"Lorentzian"
    # "scanPointStart": 1,
    # "scanPointEnd": 2,
    "scanPoints": "",#"1-2",  # String field for srange parsing
    "depthRange": "",  # Empty string for no depth range
    "detectorCropX1": 0,
    "detectorCropX2": 2047,
    "detectorCropY1": 0,
    "detectorCropY2": 2047,
    "min_size": 3, #1.13
    "max_peaks": 50,
    "smooth": False, #0
    "maskFile": "None", 
    "indexKeVmaxCalc": 17.2, #17.2
    "indexKeVmaxTest": 35.0, #30.0
    "indexAngleTolerance": 0.1, #0.1
    "indexH": 0, #1
    "indexK": 0, #1
    "indexL": 1,
    "indexCone": 72.0,
    "energyUnit": "keV",
    "exposureUnit": "sec",
    "cosmicFilter": True,  # Assuming the last occurrence in YAML is the one to use
    "recipLatticeUnit": "1/nm",
    "latticeParametersUnit": "nm",
    # "peaksearchPath": None,
    # "p2qPath": None,
    # "indexingPath": None,
    "outputFolder": "analysis/scan_%d/index_%d",# "analysis/scan_%d/rec_%d/index_%d",
    # "filefolder": "tests/data/gdata",
    # "filenamePrefix": "HAs_long_laue1_",
    "geoFile": "tests/data/geo/geoN_2022-03-29_14-15-05.xml",
    "crystFile": "tests/data/crystal/Al.xtal",
    "depth": float('nan'), # Representing YAML nan
    "beamline": "34ID-E"
}

CATALOG_DEFAULTS = {
    "filefolder": "tests/data/gdata",
    "filenamePrefix": "HAs_long_laue1_",
}

# DEFAULT_VARIABLES = {
#     "author": "",
#     "notes": "",
# }

dash.register_page(__name__)

layout = dbc.Container(
    [html.Div([
        navbar.navbar,
        dcc.Location(id='url-create-peakindexing', refresh=False),
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
                        html.H3(id="peakindex-title", children="New Peak Indexing"),
                        width="auto",   # shrink to content
                    ),
                    dbc.Col(
                        dbc.Button(
                            "Set from ...",
                            id="upload-peakindexing-config",
                            color="secondary",
                            style={"minWidth": 150, "maxWidth": "150px", "width": "100%"},
                        ),
                        width="auto",
                        className="ms-3",  # small gap from title
                    ),
                    dbc.Col(
                        dbc.Button(
                            "Validate",
                            id="peakindex-validate-btn",
                            color="secondary",
                            style={"minWidth": 150, "maxWidth": "150px", "width": "100%"},
                        ),
                        width="auto",
                        className="ms-3",  # small gap from title
                    ),
                    dbc.Col(
                        dbc.Button(
                            "Submit",
                            id="submit_peakindexing",
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
                    _field("Author", "author",
                            kwargs={
                                "type": "text",
                                "placeholder": "Required! Enter author or Tag for the reconstruction",
                            }),
                    md=12, xs=12,   # full row on small, wide on medium+
                    width = "auto",
                    style={"minWidth": "300px"},
                ),
            ],
            justify="center",
            className="mb-3",
            align="center",
        ),
        peakindex_form,
        dcc.Store(id="peakindex-data-loaded-signal"),
    ],
    )
    ],
    className='dbc', 
    fluid=True
)

def format_filename_with_indices(filename_prefix, scanPoint_num, depthRange_num=None):
    """
    Format a filename prefix with scan point and optional depth range indices.
    
    Supports three patterns:
    1. No placeholders: "file.tif" -> "file.tif"
    2. One %d placeholder: "file_%d.tif" -> "file_001.tif" (or "file_001_5.tif" if depth provided)
    3. Two %d placeholders: "file_%d_%d.tif" -> "file_001_005.tif"
    
    Args:
        filename_prefix: String that may contain 0, 1, or 2 %d placeholders
        scanPoint_num: Scan point index (int)
        depthRange_num: Optional depth range index (int or None)
    
    Returns:
        Formatted filename string
    
    Raises:
        ValueError: If format string has >2 placeholders or incompatible with depth
    """
    num_placeholders = filename_prefix.count('%d')
    
    if num_placeholders == 0:
        # No formatting needed
        file_str = filename_prefix
    elif num_placeholders == 1:
        # Format with either scan point OR depth range (exactly one must be provided)
        if scanPoint_num is not None and depthRange_num is None:
            file_str = filename_prefix % scanPoint_num
        elif depthRange_num is not None and scanPoint_num is None:
            file_str = filename_prefix % depthRange_num
        elif scanPoint_num is not None and depthRange_num is not None:
            raise ValueError(
                f"Filename prefix '{filename_prefix}' has 1 %d placeholder "
                f"but both Scan Points and Depth Range were provided (only one allowed)"
            )
        else:  # both are None
            raise ValueError(
                f"Filename prefix '{filename_prefix}' has 1 %d placeholder "
                f"but neither Scan Points nor Depth Range was provided"
            )
    elif num_placeholders == 2:
        # Format with both scan point and depth
        if depthRange_num is not None:
            file_str = filename_prefix % (scanPoint_num, depthRange_num)
        else:
            raise ValueError(
                f"Filename prefix '{filename_prefix}' has 2 %d placeholders "
                f"but no Depth Range specified"
            )
    else:
        raise ValueError(
            f"Filename prefix '{filename_prefix}' has {num_placeholders} %d placeholders "
            f"(max 2 supported)"
        )
    
    return file_str

def validate_peakindexing_inputs(ctx):
    """
    Validate specified peak indexing inputs using callback context.
    
    Parameters:
    - ctx: dash.callback_context containing states_list with field IDs and values
    
    Returns:
        validation_result (dict): {
            'errors': dict mapping field_name to list of error messages,
            'warnings': dict mapping field_name to list of warning messages,
            'successes': dict mapping field_name to empty string (for fields that passed)
        }
    """
    # Initialize validation result dict
    validation_result = {
        'errors': {},
        'warnings': {},
        'successes': {}
    }
    # Dictionary to store parsed field value lists
    parsed_fields = {}
    
    # Hard-coded list of field IDs to validate (excludes 'notes')
    all_field_ids = [
        'data_path',
        'filenamePrefix',
        'scanPoints',
        'depthRange',
        'geoFile',
        'crystFile',
        'outputFolder',
        'root_path',
        'IDnumber',  # Replaced scanNumber with IDnumber
        # 'scanNumber',  # Now parsed from IDnumber
        'author',
        'threshold',
        'thresholdRatio',
        'maxRfactor',
        'boxsize',
        'max_number',
        'min_separation',
        'min_size',
        'max_peaks',
        'indexKeVmaxCalc',
        'indexKeVmaxTest',
        'indexAngleTolerance',
        'indexCone',
        'indexHKL',
        'detectorCropX1',
        'detectorCropX2',
        'detectorCropY1',
        'detectorCropY2',
    ]
    
    # Optional parameters list - these fields are not required
    optional_params = [
        'scanPoints',
        'depthRange',
        'threshold',
        'thresholdRatio',
        'scanNumber',
        'wirerecon_id',
        'recon_id',
        ]

    # Create database session for catalog validation
    session = Session(session_utils.get_engine())
    
    # Extract field values from callback context using the hard-coded field list
    # ctx.states is a dict with format {'component_id.prop_name': value}
    all_fields = {}
    for key, value in ctx.states.items():
        # Extract component_id from 'component_id.prop_name'
        component_id = key.split('.')[0]
        # Only include fields in our validation list
        if component_id in all_field_ids:
            all_fields[component_id] = value
    
    # Determine num_inputs from longest semicolon-separated list across all fields
    num_inputs = get_num_inputs_from_fields(all_fields)
    
    # Extract individual field values
    root_path = all_fields.get('root_path', '')
    IDnumber = all_fields.get('IDnumber', '')
    # Old individual ID fields (now parsed from IDnumber):
    # scanNumber = all_params.get('scanNumber')
    # recon_id = all_params.get('recon_id')
    # wirerecon_id = all_params.get('wirerecon_id')
    # peakindex_id = all_params.get('peakindex_id')
    
    # Other parameters (kept as comments for reference):
    # data_path = all_params.get('data_path')
    # filenamePrefix = all_params.get('filenamePrefix')
    # scanPoints = all_params.get('scanPoints')
    # depthRange = all_params.get('depthRange')
    # geoFile = all_params.get('geoFile')
    # crystFile = all_params.get('crystFile')
    # outputFolder = all_params.get('outputFolder')
    # threshold = all_params.get('threshold')
    # thresholdRatio = all_params.get('thresholdRatio')
    # maxRfactor = all_params.get('maxRfactor')
    # boxsize = all_params.get('boxsize')
    # max_number = all_params.get('max_number')
    # min_separation = all_params.get('min_separation')
    # min_size = all_params.get('min_size')
    # max_peaks = all_params.get('max_peaks')
    # indexKeVmaxCalc = all_params.get('indexKeVmaxCalc')
    # indexKeVmaxTest = all_params.get('indexKeVmaxTest')
    # indexAngleTolerance = all_params.get('indexAngleTolerance')
    # indexCone = all_params.get('indexCone')
    # indexHKL = all_params.get('indexHKL')
    # detectorCropX1 = all_params.get('detectorCropX1')
    # detectorCropX2 = all_params.get('detectorCropX2')
    # detectorCropY1 = all_params.get('detectorCropY1')
    # detectorCropY2 = all_params.get('detectorCropY2')
    
    # Validate root_path directory exists
    if not root_path:
        add_validation_message(validation_result, 'errors', 'root_path')
    elif not os.path.exists(root_path):
        add_validation_message(validation_result, 'errors', 'root_path', 
                              custom_message="Root Path does not exist")
    else: #Added to pass over in later loop over all_fields
        parsed_fields['root_path'] = root_path
        add_validation_message(validation_result, 'successes', 'root_path')
    
    # Parse IDnumber to get scanNumber, wirerecon_id, recon_id, peakindex_id
    if IDnumber:
        try:
            id_dict = parse_IDnumber(IDnumber, session)
            # Add parsed IDs to parsed_fields for use in validation
            for key, value in id_dict.items():
                if value is not None:
                    parsed_fields[key] = parse_parameter(value, num_inputs)
            add_validation_message(validation_result, 'successes', 'IDnumber')
        except ValueError as e:
            add_validation_message(validation_result, 'errors', 'IDnumber', 
                                  custom_message=f"ID Number parsing error: {str(e)}")
    else:
        # IDnumber is optional - if not provided, just skip
        pass
    
    # Validate all other fields by iterating over all_fields    
    for field_name, field_value in all_fields.items():
        # Skip already handled fields
        if field_name in parsed_fields: #{'root_path', 'data_path'}
            continue
        # Check 1: Is it missing/empty?
        is_missing = False
        if field_name in ['threshold', 'thresholdRatio', 'maxRfactor', 'boxsize', 'max_number', 
                          'min_separation', 'min_size', 'max_peaks', 'indexKeVmaxCalc', 
                          'indexKeVmaxTest', 'indexAngleTolerance', 'indexCone',
                          'detectorCropX1', 'detectorCropX2', 'detectorCropY1', 'detectorCropY2']:
            # Numeric fields: check for None or empty string (0 is valid)
            if field_value is None or field_value == '':
                is_missing = True
        else:
            # Other fields: check for falsy values
            if not field_value:
                is_missing = True
        
        if is_missing:
            # Special case for scanNumber: only warning, not error
            if field_name == 'scanNumber':
                add_validation_message(validation_result, 'warnings', field_name, display_name="Scan Number")
                continue  # Skip parsing
            # Special case for depthRange: optional parameter
            elif field_name in optional_params:#field_name == 'depthRange':
                continue  # Skip - this is optional
            else:
                add_validation_message(validation_result, 'errors', field_name)
                continue  # Skip parsing if missing
        
        # Check 2: Parse the field value
        try:
            parsed_list = parse_parameter(field_value, num_inputs)
        except ValueError as e:
            # Special case for scanNumber: only warning, not error
            if field_name == 'scanNumber':
                add_validation_message(validation_result, 'warnings', field_name, 
                                     custom_message=f"Scan Number parsing error: {str(e)}")
                continue  # Skip length check
            else:
                add_validation_message(validation_result, 'errors', field_name, 
                                     custom_message=f"%s parsing error: {str(e)}")
                continue  # Skip length check if parsing failed
        
        # Check 3: Verify length matches num_inputs
        if len(parsed_list) != num_inputs:
            # Special case for scanNumber: only warning, not error
            if field_name == 'scanNumber':
                add_validation_message(validation_result, 'warnings', field_name, 
                                     custom_message=f"Scan Number count ({len(parsed_list)}) does not match number of inputs ({num_inputs})")
            else:
                add_validation_message(validation_result, 'errors', field_name, 
                                     custom_message=f"%s count ({len(parsed_list)}) does not match number of inputs ({num_inputs})")
        
        # Store the parsed list in the dictionary
        parsed_fields[field_name] = parsed_list
    
    # Create outer wrapper with common parameters before the loop
    def make_field_validator(validation_result, parsed_fields, optional_params):
        """Create a field validator with pre-filled common parameters"""
        def validate_for_input(field_name, index, input_prefix, **kwargs):
            return validate_field_value(
                validation_result,
                parsed_fields,
                field_name,
                index,
                input_prefix,
                optional_params=optional_params,
                **kwargs
            )
        return validate_for_input
    
    # Create the validator once before the loop
    validate_for_input = make_field_validator(validation_result, parsed_fields, optional_params)
    
    # Validate each input, skipping fields that failed global validation
    for i in range(num_inputs):
        input_prefix = f"Input {i+1}: " if num_inputs > 1 else ""
        
        # Inner wrapper for this specific input
        def validate_field(field_name, **kwargs):
            return validate_for_input(field_name, i, input_prefix, **kwargs)
        
        # 1. Validate ID integers (scanNumber, wirerecon_id, recon_id)
        # Convert scanNumber to integer if present
        scan_num_int = None
        if 'scanNumber' in parsed_fields:
            current_scanNumber = validate_field('scanNumber', required=False, display_name="Scan Number")
            if current_scanNumber:
                try:
                    scan_num_int = int(current_scanNumber)
                except (ValueError, TypeError):
                    add_validation_message(
                        validation_result, 'warnings', 'IDnumber', input_prefix,
                        custom_message="Scan Number is not a valid integer"
                    )
        
        # Convert wirerecon_id to integer if present
        wirerecon_id_int = None
        if 'wirerecon_id' in parsed_fields:
            wirerecon_val = validate_field('wirerecon_id', required=False, display_name="Wire Recon ID")
            if wirerecon_val:
                try:
                    wirerecon_id_int = int(wirerecon_val)
                except (ValueError, TypeError):
                    add_validation_message(
                        validation_result, 'warnings', 'IDnumber', input_prefix,
                        custom_message="Wire Recon ID is not a valid integer"
                    )
        
        # Convert recon_id to integer if present
        recon_id_int = None
        if 'recon_id' in parsed_fields:
            recon_val = validate_field('recon_id', required=False, display_name="Recon ID")
            if recon_val:
                try:
                    recon_id_int = int(recon_val)
                except (ValueError, TypeError):
                    add_validation_message(
                        validation_result, 'warnings', 'IDnumber', input_prefix,
                        custom_message="Recon ID is not a valid integer"
                    )
        
        # 2. Check if data files exist for this input (skip if root_path or data_path invalid)
        if 'root_path' not in validation_result['errors'] and 'data_path' not in validation_result['errors']:
            current_data_path = validate_field('data_path')
            if current_data_path is not None:
                current_full_data_path = os.path.join(root_path, current_data_path.lstrip('/'))
                
                # Check if directory exists
                if not os.path.exists(current_full_data_path):
                    add_validation_message(validation_result, 'errors', 'data_path', input_prefix, 
                                         custom_message="Data Path directory not found")
                else:
                    # Validate against database if we have any ID (uses IDs validated above)
                    if any([scan_num_int, wirerecon_id_int, recon_id_int]):
                        id_dict = {
                            'scanNumber': scan_num_int,
                            'wirerecon_id': wirerecon_id_int,
                            'recon_id': recon_id_int,
                        }
                        
                        # Get data from appropriate table based on ID priority
                        id_data = get_data_from_id(session, id_dict, root_path, 'peakindex', CATALOG_DEFAULTS)
                        
                        if id_data and id_data.get('data_path'):
                            id_full_data_path = os.path.join(root_path, id_data['data_path'].lstrip('/'))
                            if id_full_data_path != current_full_data_path:
                                add_validation_message(
                                    validation_result, 'warnings', 'data_path', input_prefix,
                                    custom_message=f"{id_data['source']} database entry has different path ({id_data['data_path']})"
                                )
                        else:
                            # No entry found for this ID
                            add_validation_message(
                                validation_result, 'warnings', 'IDnumber', input_prefix,
                                custom_message=f"{id_data.get('source', 'Data')} database entry not found"
                            )
                    
                    # Check if directory contains any files
                    all_files = [f for f in os.listdir(current_full_data_path) if os.path.isfile(os.path.join(current_full_data_path, f))]
                    if not all_files:
                        add_validation_message(validation_result, 'errors', 'data_path', input_prefix, 
                                             custom_message="Data Path directory contains no files")
                    else:
                        # Get filename prefix
                        current_filename_prefix_str = validate_field('filenamePrefix', display_name="Filename Prefix")
                        if current_filename_prefix_str is not None:
                            current_filename_prefix = [s.strip() for s in current_filename_prefix_str.split(',')] if current_filename_prefix_str else []
                            
                            # Check for actual files using glob - pinpoint which field has the error
                            for current_filename_prefix_i in current_filename_prefix:
                                # Check if ANY files match this prefix pattern (without scan point substitution)
                                prefix_pattern = os.path.join(current_full_data_path, current_filename_prefix_i.replace('%d', '*'))
                                prefix_matches = glob.glob(prefix_pattern + '*')
                                
                                if not prefix_matches:
                                    add_validation_message(validation_result, 'errors', 'filenamePrefix', input_prefix, 
                                                         custom_message=f"No files match Filename prefix pattern '{current_filename_prefix_i}'")
                                else:
                                    # Count %d placeholders to determine if scanPoints/depthRange are needed
                                    num_placeholders = current_filename_prefix_i.count('%d')
                                    
                                    # If no placeholders, scanPoints is not needed - skip detailed validation
                                    if num_placeholders == 0:
                                        continue  # File exists, no placeholders needed, move to next prefix
                                    
                                    # For 1 placeholder: either scanPoints OR depthRange (but not both)
                                    # For 2 placeholders: both scanPoints AND depthRange required
                                    
                                    if num_placeholders == 1:
                                        # Get both fields to check which one is provided
                                        current_scanPoints = validate_field('scanPoints', required=False, display_name="Scan Points")
                                        current_depthRange = validate_field('depthRange', required=False, display_name="Depth Range")
                                        
                                        # Check that exactly one is provided
                                        has_scanPoints = current_scanPoints is not None
                                        has_depthRange = current_depthRange is not None
                                        
                                        if has_scanPoints and has_depthRange:
                                            error_msg = f"Filename prefix '{current_filename_prefix_i}' has 1 %d placeholder but both Scan Points and Depth Range were provided (only one allowed)"
                                            add_validation_message(validation_result, 'errors', 'filenamePrefix', input_prefix, custom_message=error_msg)
                                            add_validation_message(validation_result, 'errors', 'scanPoints', input_prefix, custom_message=error_msg)
                                            add_validation_message(validation_result, 'errors', 'depthRange', input_prefix, custom_message=error_msg)
                                            continue
                                        elif not has_scanPoints and not has_depthRange:
                                            error_msg = f"Filename prefix '{current_filename_prefix_i}' has 1 %d placeholder but neither Scan Points nor Depth Range was provided"
                                            add_validation_message(validation_result, 'errors', 'filenamePrefix', input_prefix, custom_message=error_msg)
                                            add_validation_message(validation_result, 'errors', 'scanPoints', input_prefix, custom_message=error_msg)
                                            add_validation_message(validation_result, 'errors', 'depthRange', input_prefix, custom_message=error_msg)
                                            continue
                                        
                                        # Parse whichever one is provided
                                        if has_scanPoints:
                                            try:
                                                scanPoints_srange = srange(current_scanPoints)
                                                scanPoint_nums = scanPoints_srange.list()
                                                if not scanPoint_nums:
                                                    add_validation_message(validation_result, 'errors', 'scanPoints', input_prefix, 
                                                                         custom_message="Scan Points range is empty")
                                                    continue
                                                depthRange_nums = [None]
                                            except Exception as e:
                                                add_validation_message(validation_result, 'errors', 'scanPoints', input_prefix, 
                                                                     custom_message="Scan Points entry has invalid format")
                                                continue
                                        else:  # has_depthRange
                                            try:
                                                depthRange_srange = srange(current_depthRange)
                                                depthRange_nums = depthRange_srange.list()
                                                if not depthRange_nums:
                                                    add_validation_message(validation_result, 'errors', 'depthRange', input_prefix, 
                                                                         custom_message="Depth Range is empty")
                                                    continue
                                                scanPoint_nums = [None]
                                            except Exception as e:
                                                add_validation_message(validation_result, 'errors', 'depthRange', input_prefix, 
                                                                     custom_message="Depth Range entry has invalid format")
                                                continue
                                    
                                    elif num_placeholders == 2:
                                        # Both scanPoints and depthRange are required
                                        current_scanPoints = validate_field('scanPoints', display_name="Scan Points")
                                        current_depthRange = validate_field('depthRange', display_name="Depth Range")
                                        
                                        if current_scanPoints is None or current_depthRange is None:
                                            # Required field missing, error already added by validate_field_value
                                            continue
                                        
                                        try:
                                            scanPoints_srange = srange(current_scanPoints)
                                            scanPoint_nums = scanPoints_srange.list()
                                            if not scanPoint_nums:
                                                add_validation_message(validation_result, 'errors', 'scanPoints', input_prefix, 
                                                                     custom_message="Scan Points range is empty")
                                                continue
                                        except Exception as e:
                                            add_validation_message(validation_result, 'errors', 'scanPoints', input_prefix, 
                                                                 custom_message="Scan Points entry has invalid format")
                                            continue
                                        
                                        try:
                                            depthRange_srange = srange(current_depthRange)
                                            depthRange_nums = depthRange_srange.list()
                                            if not depthRange_nums:
                                                add_validation_message(validation_result, 'errors', 'depthRange', input_prefix, 
                                                                     custom_message="Depth Range is empty")
                                                continue
                                        except Exception as e:
                                            add_validation_message(validation_result, 'errors', 'depthRange', input_prefix, 
                                                                 custom_message="Depth Range entry has invalid format")
                                            continue
                                    
                                    else:
                                        # num_placeholders > 2 - already handled by format_filename_with_indices
                                        continue
                                    
                                    # Collect missing files for this prefix
                                    missing_files = []
                                    for scanPoint_num in scanPoint_nums:
                                        for depthRange_num in depthRange_nums:
                                            # Format filename using helper function
                                            try:
                                                file_str = format_filename_with_indices(
                                                    current_filename_prefix_i,
                                                    scanPoint_num,
                                                    depthRange_num
                                                )
                                            except ValueError as e:
                                                add_validation_message(
                                                    validation_result, 'errors', 'filenamePrefix',
                                                    input_prefix, custom_message=str(e)
                                                )
                                                break
                                            
                                            scanpoint_pattern = os.path.join(current_full_data_path, file_str)
                                            scanpoint_matches = glob.glob(scanpoint_pattern + '*')
                                            
                                            if not scanpoint_matches:
                                                if depthRange_num is not None:
                                                    missing_files.append(f"{scanPoint_num}_{depthRange_num}")
                                                else:
                                                    missing_files.append(str(scanPoint_num))
                                    
                                    # If there are missing files, add a single error message for this prefix
                                    if missing_files:
                                        # Limit the number of files shown
                                        if len(missing_files) <= 5:
                                            files_str = ", ".join(missing_files)
                                        else:
                                            files_str = ", ".join(missing_files[:5]) + f", ... and {len(missing_files) - 5} more"
                                        
                                        add_validation_message(
                                            validation_result, 'errors', 'scanPoints', input_prefix,
                                            custom_message=f"Missing files for Filename prefix '{current_filename_prefix_i}' (indices: {files_str})"
                                        )
        
        # 3. Check if output folder already exists for this input (skip if root_path invalid)
        # Note: We cannot validate this properly if outputFolder contains %d placeholders
        # because we don't know the scan number or peakindex_id at validation time.
        # This check is skipped if %d is present in the path.
        current_outputFolder = validate_field('outputFolder', display_name="Output Folder")
        if current_outputFolder is not None:
            if 'root_path' not in validation_result['errors']:
                if '%d' not in current_outputFolder:
                    full_output_path = os.path.join(root_path, current_outputFolder.lstrip('/'))
                    if os.path.exists(full_output_path):
                        add_validation_message(validation_result, 'warnings', 'outputFolder', input_prefix, 
                                             custom_message="Output Folder already exists")
        
        # 4. Check if geometry file exists for this input (skip if root_path invalid)
        current_geoFile = validate_field('geoFile', display_name="Geometry File")
        if current_geoFile is not None:
            if 'root_path' not in validation_result['errors']:
                full_geo_path = os.path.join(root_path, current_geoFile.lstrip('/'))
                if not os.path.exists(full_geo_path):
                    add_validation_message(validation_result, 'errors', 'geoFile', input_prefix, 
                                         custom_message="Geometry File not found")
        
        # 5. Check if crystal file exists for this input (skip if root_path invalid)
        current_crystFile = validate_field('crystFile', display_name="Crystal File")
        if current_crystFile is not None:
            if 'root_path' not in validation_result['errors']:
                full_cryst_path = os.path.join(root_path, current_crystFile.lstrip('/'))
                if not os.path.exists(full_cryst_path):
                    add_validation_message(validation_result, 'errors', 'crystFile', input_prefix, 
                                         custom_message="Crystal File not found")
        
        # 6. Validate detector crop parameters for this input
        x1_val = validate_field('detectorCropX1', converter=safe_int)
        
        x2_val = validate_field('detectorCropX2', converter=safe_int)
        
        y1_val = validate_field('detectorCropY1', converter=safe_int)
        
        y2_val = validate_field('detectorCropY2', converter=safe_int)
        
        # Check X1 < X2 (only if both values are valid)
        if x1_val is not None and x2_val is not None and x1_val >= x2_val:
            add_validation_message(validation_result, 'errors', 'detectorCropX1', input_prefix, 
                                 custom_message="Detector Crop X1 must be less than X2")
            add_validation_message(validation_result, 'errors', 'detectorCropX2', input_prefix, 
                                 custom_message="Detector Crop X1 must be less than X2")
        
        # Check Y1 < Y2 (only if both values are valid)
        if y1_val is not None and y2_val is not None and y1_val >= y2_val:
            add_validation_message(validation_result, 'errors', 'detectorCropY1', input_prefix, 
                                 custom_message="Detector Crop Y1 must be less than Y2")
            add_validation_message(validation_result, 'errors', 'detectorCropY2', input_prefix, 
                                 custom_message="Detector Crop Y1 must be less than Y2")
        
        # 7. Validate numeric parameters for this input
        threshold_val = validate_field('threshold', converter=safe_int)
        if threshold_val is not None:
            if threshold_val < 0:
                add_validation_message(validation_result, 'errors', 'threshold', input_prefix, 
                                     custom_message="Threshold must be non-negative")
        
        thresholdRatio_val = validate_field('thresholdRatio', converter=safe_int)
        if thresholdRatio_val is not None:
            if thresholdRatio_val < 0:
                add_validation_message(validation_result, 'errors', 'thresholdRatio', input_prefix, 
                                     custom_message="Threshold Ratio must be non-negative")
        
        maxRfactor_val = validate_field('maxRfactor', converter=safe_float)
        if maxRfactor_val is not None:
            if maxRfactor_val < 0 or maxRfactor_val > 1:
                add_validation_message(validation_result, 'errors', 'maxRfactor', input_prefix, 
                                     custom_message="Max Rfactor must be between 0 and 1")
        
        boxsize_val = validate_field('boxsize', converter=safe_int)
        if boxsize_val is not None:
            if boxsize_val <= 0:
                add_validation_message(validation_result, 'errors', 'boxsize', input_prefix, 
                                     custom_message="Boxsize must be positive")
        
        max_number_val = validate_field('max_number', converter=safe_int)
        if max_number_val is not None:
            if max_number_val <= 0:
                add_validation_message(validation_result, 'errors', 'max_number', input_prefix, 
                                     custom_message="Max Number must be positive")
        
        min_separation_val = validate_field('min_separation', converter=safe_float)
        if min_separation_val is not None:
            if min_separation_val < 0:
                add_validation_message(validation_result, 'errors', 'min_separation', input_prefix, 
                                     custom_message="Min Separation must be non-negative")
        
        min_size_val = validate_field('min_size', converter=safe_float)
        if min_size_val is not None:
            if min_size_val < 0:
                add_validation_message(validation_result, 'errors', 'min_size', input_prefix, 
                                     custom_message="Min Size must be non-negative")
        
        max_peaks_val = validate_field('max_peaks', converter=safe_int)
        if max_peaks_val is not None:
            if max_peaks_val <= 0:
                add_validation_message(validation_result, 'errors', 'max_peaks', input_prefix, 
                                     custom_message="Max Peaks must be positive")
        
        indexKeVmaxCalc_val = validate_field('indexKeVmaxCalc', converter=safe_float)
        if indexKeVmaxCalc_val is not None:
            if indexKeVmaxCalc_val <= 0:
                add_validation_message(validation_result, 'errors', 'indexKeVmaxCalc', input_prefix, 
                                     custom_message="Index Ke Vmax Calc must be positive")
        
        indexKeVmaxTest_val = validate_field('indexKeVmaxTest', converter=safe_float)
        if indexKeVmaxTest_val is not None:
            if indexKeVmaxTest_val <= 0:
                add_validation_message(validation_result, 'errors', 'indexKeVmaxTest', input_prefix, 
                                     custom_message="Index Ke Vmax Test must be positive")
        
        indexAngleTolerance_val = validate_field('indexAngleTolerance', converter=safe_float)
        if indexAngleTolerance_val is not None:
            if indexAngleTolerance_val < 0:
                add_validation_message(validation_result, 'errors', 'indexAngleTolerance', input_prefix, 
                                     custom_message="Index Angle Tolerance must be non-negative")
        
        indexCone_val = validate_field('indexCone', converter=safe_float)
        if indexCone_val is not None:
            if indexCone_val < 0 or indexCone_val > 180:
                add_validation_message(validation_result, 'errors', 'indexCone', input_prefix, 
                                     custom_message="Index Cone must be between 0 and 180 degrees")
        
        # 8. Validate indexHKL for this input
        if 'indexHKL' not in validation_result['errors']:
            current_indexHKL = str(parsed_fields['indexHKL'][i])
            if len(current_indexHKL) != 3:
                add_validation_message(validation_result, 'errors', 'indexHKL', input_prefix, 
                                     custom_message="Index HKL must be 3 digits (e.g., '001')")
            else:
                try:
                    int(current_indexHKL[0])
                    int(current_indexHKL[1])
                    int(current_indexHKL[2])
                except ValueError:
                    add_validation_message(validation_result, 'errors', 'indexHKL', input_prefix, 
                                         custom_message="Index HKL must contain only digits")
        
    
    # Add successes for fields that passed all validations
    # Only add to successes if the field has neither errors nor warnings
    for field_name in all_field_ids:
        if field_name not in validation_result['errors'] and field_name not in validation_result['warnings']:
            add_validation_message(validation_result, 'successes', field_name)
    
    # Close database session
    session.close()
    
    return validation_result


"""
=======================
Callbacks
=======================
"""
@dash.callback(
    Input('peakindex-validate-btn', 'n_clicks'),
    State('data_path', 'value'),
    State('filenamePrefix', 'value'),
    State('scanPoints', 'value'),
    State('depthRange', 'value'),
    State('geoFile', 'value'),
    State('crystFile', 'value'),
    State('outputFolder', 'value'),
    State('root_path', 'value'),
    State('IDnumber', 'value'),  # Replaced scanNumber with IDnumber
    # State('scanNumber', 'value'),  # Old - now parsed from IDnumber
    State('author', 'value'),
    State('threshold', 'value'),
    State('thresholdRatio', 'value'),
    State('maxRfactor', 'value'),
    State('boxsize', 'value'),
    State('max_number', 'value'),
    State('min_separation', 'value'),
    State('min_size', 'value'),
    State('max_peaks', 'value'),
    State('indexKeVmaxCalc', 'value'),
    State('indexKeVmaxTest', 'value'),
    State('indexAngleTolerance', 'value'),
    State('indexCone', 'value'),
    State('indexHKL', 'value'),
    # State('detectorCropX1', 'value'),  # Not in layout - validated from ctx
    # State('detectorCropX2', 'value'),  # Not in layout - validated from ctx
    # State('detectorCropY1', 'value'),  # Not in layout - validated from ctx
    # State('detectorCropY2', 'value'),  # Not in layout - validated from ctx
    prevent_initial_call=True,
)
def validate_inputs(
    n_clicks,
    data_path,
    filenamePrefix,
    scanPoints,
    depthRange,
    geoFile,
    crystFile,
    outputFolder,
    root_path,
    IDnumber,  # Replaced scanNumber with IDnumber
    # scanNumber,  # Old - now parsed from IDnumber
    author,
    threshold,
    thresholdRatio,
    maxRfactor,
    boxsize,
    max_number,
    min_separation,
    min_size,
    max_peaks,
    indexKeVmaxCalc,
    indexKeVmaxTest,
    indexAngleTolerance,
    indexCone,
    indexHKL,
    # detectorCropX1,  # Not in layout - validated from ctx
    # detectorCropX2,  # Not in layout - validated from ctx
    # detectorCropY1,  # Not in layout - validated from ctx
    # detectorCropY2,  # Not in layout - validated from ctx
):
    """Handle Validate button click"""
    
    # Get callback context
    ctx = dash.callback_context
    
    # Run validation using ctx
    validation_result = validate_peakindexing_inputs(ctx)
    
    # Apply field highlights using helper function
    apply_validation_highlights(validation_result)
    
    # Update validation alerts using helper function
    update_validation_alerts(validation_result)


@dash.callback(
    Input('submit_peakindexing', 'n_clicks'),
    
    State('root_path', 'value'),
    State('IDnumber', 'value'),  # Replaced individual ID fields with IDnumber
    # State('scanNumber', 'value'),  # Old - now parsed from IDnumber
    State('author', 'value'),
    State('notes', 'value'),
    # State('recon_id', 'value'),  # Old - now parsed from IDnumber
    # State('wirerecon_id', 'value'),  # Old - now parsed from IDnumber
    # State('peakProgram', 'value'),
    State('threshold', 'value'),
    State('thresholdRatio', 'value'),
    State('maxRfactor', 'value'),
    State('boxsize', 'value'),
    State('max_number', 'value'),
    State('min_separation', 'value'),
    State('peakShape', 'value'),
    # State('scanPointStart', 'value'),
    # State('scanPointEnd', 'value'),
    # State('depthRangeStart', 'value'),
    # State('depthRangeEnd', 'value'),
    State('scanPoints', 'value'),
    State('depthRange', 'value'),
    # State('detectorCropX1', 'value'),  # Not in form - using PEAKINDEX_DEFAULTS
    # State('detectorCropX2', 'value'),  # Not in form - using PEAKINDEX_DEFAULTS
    # State('detectorCropY1', 'value'),  # Not in form - using PEAKINDEX_DEFAULTS
    # State('detectorCropY2', 'value'),  # Not in form - using PEAKINDEX_DEFAULTS
    State('min_size', 'value'),
    State('max_peaks', 'value'),
    State('smooth', 'value'),
    State('maskFile', 'value'),
    State('indexKeVmaxCalc', 'value'),
    State('indexKeVmaxTest', 'value'),
    State('indexAngleTolerance', 'value'),
    State('indexHKL', 'value'),
    # State('indexH', 'value'),
    # State('indexK', 'value'),
    # State('indexL', 'value'),
    State('indexCone', 'value'),
    # State('energyUnit', 'value'),  # Not in form - using PEAKINDEX_DEFAULTS
    # State('exposureUnit', 'value'),  # Not in form - using PEAKINDEX_DEFAULTS
    State('cosmicFilter', 'value'),
    # State('recipLatticeUnit', 'value'),  # Not in form - using PEAKINDEX_DEFAULTS
    # State('latticeParametersUnit', 'value'),  # Not in form - using PEAKINDEX_DEFAULTS
    # State('peaksearchPath', 'value'),
    # State('p2qPath', 'value'),
    # State('indexingPath', 'value'),
    State('data_path', 'value'),
    # State('filefolder', 'value'),
    State('filenamePrefix', 'value'),
    State('outputFolder', 'value'),
    State('geoFile', 'value'),
    State('crystFile', 'value'),
    State('depth', 'value'),
    # State('beamline', 'value'),  # Not in form - using PEAKINDEX_DEFAULTS
    
    prevent_initial_call=True,
)
def submit_parameters(n,
    root_path,
    IDnumber,  # Replaced individual ID fields with IDnumber
    # scanNumber,  # Old - now parsed from IDnumber
    author,
    notes,
    # recon_id,  # Old - now parsed from IDnumber
    # wirerecon_id,  # Old - now parsed from IDnumber
    # peakProgram,
    threshold,
    thresholdRatio,
    maxRfactor,
    boxsize,
    max_number,
    min_separation,
    peakShape,
    # scanPointStart,
    # scanPointEnd,
    # depthRangeStart,
    # depthRangeEnd,
    scanPoints,
    depthRange,
    # detectorCropX1,  # Not in form - using PEAKINDEX_DEFAULTS
    # detectorCropX2,  # Not in form - using PEAKINDEX_DEFAULTS
    # detectorCropY1,  # Not in form - using PEAKINDEX_DEFAULTS
    # detectorCropY2,  # Not in form - using PEAKINDEX_DEFAULTS
    min_size,
    max_peaks,
    smooth,
    maskFile,
    indexKeVmaxCalc,
    indexKeVmaxTest,
    indexAngleTolerance,
    indexHKL,
    # indexH,
    # indexK,
    # indexL,
    indexCone,
    # energyUnit,  # Not in form - using PEAKINDEX_DEFAULTS
    # exposureUnit,  # Not in form - using PEAKINDEX_DEFAULTS
    cosmicFilter,
    # recipLatticeUnit,  # Not in form - using PEAKINDEX_DEFAULTS
    # latticeParametersUnit,  # Not in form - using PEAKINDEX_DEFAULTS
    # peaksearchPath,
    # p2qPath,
    # indexingPath,
    data_path,
    # filefolder,
    filenamePrefix,
    outputFolder,
    geometry_file,
    crystal_file,
    depth,
    # beamline,  # Not in form - using PEAKINDEX_DEFAULTS
    
):
    """
    Submit parameters for peak indexing job(s).
    Handles both single scan and pooled scan submissions.
    """
    # Get callback context
    ctx = dash.callback_context
    
    # Run validation before submission using ctx
    validation_result = validate_peakindexing_inputs(ctx)
    
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
    
    # Parse IDnumber to get individual IDs
    with Session(session_utils.get_engine()) as temp_session:
        try:
            id_dict = parse_IDnumber(IDnumber, temp_session)
            scanNumber = id_dict.get('scanNumber')
            wirerecon_id = id_dict.get('wirerecon_id')
            recon_id = id_dict.get('recon_id')
            # peakindex_id = id_dict.get('peakindex_id')
        except ValueError as e:
            set_props("alert-submit", {
                'is_open': True,
                'children': f'Invalid ID Number: {str(e)}',
                'color': 'danger'
            })
            return
    
    # Build all_submit_params from ctx.states (consistent with validation approach)
    all_submit_params = {}
    for key, value in ctx.states.items():
        component_id = key.split('.')[0]
        all_submit_params[component_id] = value
    
    # Add parsed IDs to the params dict
    all_submit_params['scanNumber'] = scanNumber
    all_submit_params['wirerecon_id'] = wirerecon_id
    all_submit_params['recon_id'] = recon_id
    
    # Determine num_inputs from longest semicolon-separated list across all fields
    num_inputs = get_num_inputs_from_fields(all_submit_params)
    
    # Parse all other parameters with num_inputs
    try:
        scanNumber_list = parse_parameter(scanNumber, num_inputs)
        author_list = parse_parameter(author, num_inputs)
        notes_list = parse_parameter(notes, num_inputs)
        recon_id_list = parse_parameter(recon_id, num_inputs)
        wirerecon_id_list = parse_parameter(wirerecon_id, num_inputs)
        threshold_list = parse_parameter(threshold, num_inputs)
        thresholdRatio_list = parse_parameter(thresholdRatio, num_inputs)
        maxRfactor_list = parse_parameter(maxRfactor, num_inputs)
        boxsize_list = parse_parameter(boxsize, num_inputs)
        max_number_list = parse_parameter(max_number, num_inputs)
        min_separation_list = parse_parameter(min_separation, num_inputs)
        peakShape_list = parse_parameter(peakShape, num_inputs)
        scanPoints_list = parse_parameter(scanPoints, num_inputs)
        depthRange_list = parse_parameter(depthRange, num_inputs)
        # Detector crop parameters are not in the form, so use defaults from PEAKINDEX_DEFAULTS
        detectorCropX1_list = parse_parameter(PEAKINDEX_DEFAULTS["detectorCropX1"], num_inputs)
        detectorCropX2_list = parse_parameter(PEAKINDEX_DEFAULTS["detectorCropX2"], num_inputs)
        detectorCropY1_list = parse_parameter(PEAKINDEX_DEFAULTS["detectorCropY1"], num_inputs)
        detectorCropY2_list = parse_parameter(PEAKINDEX_DEFAULTS["detectorCropY2"], num_inputs)
        min_size_list = parse_parameter(min_size, num_inputs)
        max_peaks_list = parse_parameter(max_peaks, num_inputs)
        smooth_list = parse_parameter(smooth, num_inputs)
        maskFile_list = parse_parameter(maskFile, num_inputs)
        indexKeVmaxCalc_list = parse_parameter(indexKeVmaxCalc, num_inputs)
        indexKeVmaxTest_list = parse_parameter(indexKeVmaxTest, num_inputs)
        indexAngleTolerance_list = parse_parameter(indexAngleTolerance, num_inputs)
        indexHKL_list = parse_parameter(indexHKL, num_inputs)
        indexCone_list = parse_parameter(indexCone, num_inputs)
        # Beam units are not in the form, so use defaults from PEAKINDEX_DEFAULTS
        energyUnit_list = parse_parameter(PEAKINDEX_DEFAULTS["energyUnit"], num_inputs)
        exposureUnit_list = parse_parameter(PEAKINDEX_DEFAULTS["exposureUnit"], num_inputs)
        cosmicFilter_list = parse_parameter(cosmicFilter, num_inputs)
        # Lattice units are not in the form, so use defaults from PEAKINDEX_DEFAULTS
        recipLatticeUnit_list = parse_parameter(PEAKINDEX_DEFAULTS["recipLatticeUnit"], num_inputs)
        latticeParametersUnit_list = parse_parameter(PEAKINDEX_DEFAULTS["latticeParametersUnit"], num_inputs)
        data_path_list = parse_parameter(data_path, num_inputs)
        filenamePrefix_list = parse_parameter(filenamePrefix, num_inputs)
        outputFolder_list = parse_parameter(outputFolder, num_inputs)
        geoFile_list = parse_parameter(geometry_file, num_inputs)
        crystFile_list = parse_parameter(crystal_file, num_inputs)
        depth_list = parse_parameter(depth, num_inputs)
        # beamline name is not in the form, so use default from PEAKINDEX_DEFAULTS
        beamline_list = parse_parameter(PEAKINDEX_DEFAULTS["beamline"], num_inputs)
    except ValueError as e:
        # Error: mismatched lengths
        set_props("alert-submit", {
            'is_open': True, 
            'children': str(e),
            'color': 'danger'
        })
        return
    
    peakindexes_to_enqueue = []

    # First loop: Create all database entries for each listed scanNumber
    with Session(session_utils.get_engine()) as session:
        try:
            for i in range(num_inputs):
                # Extract values for this scan
                current_scanNumber = scanNumber_list[i]
                current_recon_id = recon_id_list[i]
                current_wirerecon_id = wirerecon_id_list[i]
                current_output_folder = outputFolder_list[i]
                current_geo_file = geoFile_list[i]
                current_crystal_file = crystFile_list[i]
                current_scanPoints = scanPoints_list[i]
                current_depthRange = depthRange_list[i]

                # Convert scanNumber to integer if present
                scan_num_int = None
                if current_scanNumber:
                    try:
                        scan_num_int = int(current_scanNumber)
                    except (ValueError, TypeError) as e:
                        logger.error(f"Failed to convert scanNumber '{current_scanNumber}' to integer: {e}")
                        set_props("alert-submit", {
                            'is_open': True,
                            'children': f'Invalid scan number: {current_scanNumber}',
                            'color': 'danger'
                        })

                # Convert wirerecon_id to integer if present
                wirerecon_id_int = None
                if current_wirerecon_id:
                    try:
                        wirerecon_id_int = int(current_wirerecon_id)
                    except (ValueError, TypeError) as e:
                        logger.error(f"Failed to convert wirerecon_id '{current_wirerecon_id}' to integer: {e}")
                        set_props("alert-submit", {
                            'is_open': True,
                            'children': f'Invalid wire reconstruction ID: {current_wirerecon_id}',
                            'color': 'danger'
                        })

                # Convert recon_id to integer if present
                recon_id_int = None
                if current_recon_id:
                    try:
                        recon_id_int = int(current_recon_id)
                    except (ValueError, TypeError) as e:
                        logger.error(f"Failed to convert recon_id '{current_recon_id}' to integer: {e}")
                        set_props("alert-submit", {
                            'is_open': True,
                            'children': f'Invalid reconstruction ID: {current_recon_id}',
                            'color': 'danger'
                        })

                # Convert relative paths to full paths
                full_geometry_file = os.path.join(root_path, current_geo_file.lstrip('/'))
                full_crystal_file = os.path.join(root_path, current_crystal_file.lstrip('/'))

                # Get next ID for this action
                next_peakindex_id = db_utils.get_next_id(session, db_schema.PeakIndex)
                # Now that we have the ID, format the output folder path by replacement of the final %d in the template
                try:
                    if '%d' in current_output_folder:
                        formatted_output_folder = current_output_folder % next_peakindex_id
                    else:
                        formatted_output_folder = current_output_folder
                except (TypeError, ValueError) as e:
                    logger.error(f"Failed to format output folder '{current_output_folder}': {e}")
                    formatted_output_folder = current_output_folder  # Fallback if formatting fails
                
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
                # Parse scanPoints using srange
                scanPoints_srange = srange(current_scanPoints)
                scanPoint_nums = scanPoints_srange.list()
                
                # Parse depthRange if provided using srange
                if current_depthRange and current_depthRange.strip():
                    depthRange_srange = srange(current_depthRange)
                    depthRange_nums = depthRange_srange.list()
                else:
                    depthRange_srange = srange('')
                    depthRange_nums = [None]  # No reconstruction indices
                
                # Create subjobs for each combination of scan point and depth
                subjob_count = 0
                for scanPoint_num in scanPoint_nums:
                    for depthRange_num in depthRange_nums:
                        subjob = db_schema.SubJob(
                            job_id=job_id,
                            computer_name=JOB_DEFAULTS['computer_name'],
                            status=STATUS_REVERSE_MAPPING["Queued"],
                            priority=JOB_DEFAULTS['priority']
                        )
                        session.add(subjob)
                        subjob_count += 1
        
                # Extract HKL values from indexHKL parameter
                current_indexHKL = str(indexHKL_list[i])
                
                # Get filefolder and filenamePrefix
                current_data_path = data_path_list[i]
                current_filename_prefix_str = filenamePrefix_list[i]
                current_filename_prefix = [s.strip() for s in current_filename_prefix_str.split(',')] if current_filename_prefix_str else []
                # Build full path
                current_full_data_path=os.path.join(root_path, current_data_path.lstrip('/'))
                
                peakindex = db_schema.PeakIndex(
                    scanNumber = scan_num_int,
                    job_id = job_id,
                    author = author_list[i],
                    notes = notes_list[i],
                    recon_id = recon_id_int,
                    wirerecon_id = wirerecon_id_int,
                    filefolder=current_full_data_path,
                    filenamePrefix=current_filename_prefix,

                    # peakProgram=peakProgram,
                    threshold=threshold_list[i],
                    thresholdRatio=thresholdRatio_list[i],
                    maxRfactor=maxRfactor_list[i],
                    boxsize=boxsize_list[i],
                    max_number=max_number_list[i],
                    min_separation=min_separation_list[i],
                    peakShape=peakShape_list[i],
                    # scanPointStart=scanPointStart,
                    # scanPointEnd=scanPointEnd,
                    # depthRangeStart=depthRangeStart,
                    # depthRangeEnd=depthRangeEnd,
                    scanPoints=current_scanPoints,
                    scanPointslen=scanPoints_srange.len(),
                    depthRange=current_depthRange,
                    depthRangelen=depthRange_srange.len(),
                    detectorCropX1=detectorCropX1_list[i],
                    detectorCropX2=detectorCropX2_list[i],
                    detectorCropY1=detectorCropY1_list[i],
                    detectorCropY2=detectorCropY2_list[i],
                    min_size=min_size_list[i],
                    max_peaks=max_peaks_list[i],
                    smooth=smooth_list[i],
                    maskFile=maskFile_list[i],
                    indexKeVmaxCalc=indexKeVmaxCalc_list[i],
                    indexKeVmaxTest=indexKeVmaxTest_list[i],
                    indexAngleTolerance=indexAngleTolerance_list[i],
                    indexH=int(current_indexHKL[0]),
                    indexK=int(current_indexHKL[1]),
                    indexL=int(current_indexHKL[2]),
                    indexCone=indexCone_list[i],
                    energyUnit=energyUnit_list[i],
                    exposureUnit=exposureUnit_list[i],
                    cosmicFilter=cosmicFilter_list[i],
                    recipLatticeUnit=recipLatticeUnit_list[i],
                    latticeParametersUnit=latticeParametersUnit_list[i],
                    # peaksearchPath=peaksearchPath,
                    # p2qPath=p2qPath,
                    # indexingPath=indexingPath,
                    outputFolder=full_output_folder,  # Store full path in database
                    geoFile=full_geometry_file,  # Store full path in database
                    crystFile=full_crystal_file,  # Store full path in database
                    depth=depth_list[i],
                    beamline=beamline_list[i],
                )
                session.add(peakindex)
                peakindexes_to_enqueue.append({
                    "job_id": job_id,
                    "scanNumber": current_scanNumber,
                    "filefolder": current_full_data_path,
                    "filenamePrefix": current_filename_prefix,
                    "outputFolder": full_output_folder,
                    "geoFile": full_geometry_file,
                    "crystFile": full_crystal_file,
                    "scanPoints": current_scanPoints,
                    "depthRange": current_depthRange,
                    "boxsize": boxsize_list[i],
                    "maxRfactor": maxRfactor_list[i],
                    "min_size": min_size_list[i],
                    "min_separation": min_separation_list[i],
                    "threshold": threshold_list[i],
                    "peakShape": peakShape_list[i],
                    "max_peaks": max_peaks_list[i],
                    "smooth": smooth_list[i],
                    "indexKeVmaxCalc": indexKeVmaxCalc_list[i],
                    "indexKeVmaxTest": indexKeVmaxTest_list[i],
                    "indexAngleTolerance": indexAngleTolerance_list[i],
                    "indexCone": indexCone_list[i],
                    "indexH": int(current_indexHKL[0]),
                    "indexK": int(current_indexHKL[1]),
                    "indexL": int(current_indexHKL[2]),
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
    for i, spec in enumerate(peakindexes_to_enqueue):
        try:
            # Extract values for this scan
            full_data_path = spec["filefolder"]
            current_filename_prefix = spec["filenamePrefix"]
            
            scanPoints_srange = srange(spec["scanPoints"])
            scanPoint_nums = scanPoints_srange.list()

            if spec["depthRange"] and str(spec["depthRange"]).strip():
                depthRange_srange = srange(spec["depthRange"])
                depthRange_nums = depthRange_srange.list()
            else:
                depthRange_nums = [None]

            # Prepare lists of input and output files for all subjobs
            input_files = []
            
            for current_filename_prefix_i in current_filename_prefix:
                for scanPoint_num in scanPoint_nums:
                    for depthRange_num in depthRange_nums:
                        # Format filename using helper function
                        file_str = format_filename_with_indices(
                            current_filename_prefix_i,
                            scanPoint_num,
                            depthRange_num
                        )
                        
                        input_file_pattern = os.path.join(full_data_path, file_str)
                        
                        # Use glob to find matching files
                        matched_files = glob.glob(input_file_pattern)
                        
                        if not matched_files:
                            raise ValueError(f"No files found matching pattern: {input_file_pattern}")
                        
                        input_files.extend(matched_files)
            
            # Create output directory list matching input_files length
            output_dirs = [spec["outputFolder"] for _ in input_files]
            
            # Enqueue the batch job with all files
            rq_job_id = enqueue_peakindexing(
                job_id=spec["job_id"],
                input_files=input_files,
                output_files=output_dirs,
                geometry_file=spec["geoFile"],
                crystal_file=spec["crystFile"],
                boxsize=spec["boxsize"],
                max_rfactor=spec["maxRfactor"],
                min_size=spec["min_size"],
                min_separation=spec["min_separation"],
                threshold=spec["threshold"],
                peak_shape=spec["peakShape"],
                max_peaks=spec["max_peaks"],
                smooth=spec["smooth"],
                index_kev_max_calc=spec["indexKeVmaxCalc"],
                index_kev_max_test=spec["indexKeVmaxTest"],
                index_angle_tolerance=spec["indexAngleTolerance"],
                index_cone=spec["indexCone"],
                index_h=spec["indexH"],
                index_k=spec["indexK"],
                index_l=spec["indexL"]
            )
            
            logger.info(f"Peakindexing batch job {spec['job_id']} enqueued with RQ ID: {rq_job_id} for {len(input_files)} files")
            
            set_props("alert-submit", {'is_open': True, 
                                        'children': f'Job {spec["job_id"]} submitted to queue with {len(input_files)} file(s)',
                                        'color': 'info'})
        except Exception as e:
            # Provide more context to help diagnose format issues and input parsing
            logger.error(
                f"Failed to enqueue job {spec['job_id']}: {e}. "
                f"filenamePrefix='{current_filename_prefix_str}', "
                f"parsed prefixes={current_filename_prefix}, "
                f"scanPoints='{spec['scanPoints']}', depthRange='{spec['depthRange']}', data_path='{current_data_path}'"
            )
            set_props("alert-submit", {'is_open': True, 
                                        'children': f'Failed to queue job {spec["job_id"]}: {str(e)}. '
                                                    f'filenamePrefix={current_filename_prefix_str}, '
                                                    f'scanPoints={spec["scanPoints"]}, depthRange={spec["depthRange"]}',
                                        'color': 'danger'})


# Register shared callbacks
register_update_path_fields_callback(
    update_paths_id='peakindex-update-path-fields-btn',
    # scan_number_id='scanNumber',
    id_number_id='IDnumber',
    root_path_id='root_path',
    data_path_id='data_path',
    filename_prefix_id='filenamePrefix',
    alert_id='alert-scan-loaded',
    catalog_defaults=CATALOG_DEFAULTS,
    output_folder_id='outputFolder',
    build_template_func=build_output_folder_template,
    context='peakindex'
)

register_load_file_indices_callback(
    button_id='peakindex-load-file-indices-btn',
    data_loaded_signal_id='peakindex-data-loaded-signal',
    data_path_id='data_path',
    filename_prefix_id='filenamePrefix',
    scan_points_id='scanPoints',
    depth_range_id='depthRange',  # Peak indexing uses depth range
    alert_id='alert-scan-loaded',
    num_indices=2
)

register_check_filenames_callback(
    find_filenames_id='peakindex-check-filenames-btn',
    update_paths_id='peakindex-update-path-fields-btn',
    data_loaded_signal_id='peakindex-data-loaded-signal',
    data_path_id='data_path',
    filename_prefix_id='filenamePrefix',
    filename_templates_id='peakindex-filename-templates',
    cached_patterns_store_id='peakindex-cached-patterns',
    num_indices=2
)


# @dash.callback(
#     Input('url-create-peakindexing','pathname'),
#     prevent_initial_call=True,
# )
# def get_peakindexings(path):
#     root_path = DEFAULT_VARIABLES["root_path"]
#     if path == '/create-peakindexing':
#         # Create a PeakIndex object with form defaults (not for database insertion)
#         peakindex_form_data = db_schema.PeakIndex(
#             scanNumber=PEAKINDEX_DEFAULTS.get("scanNumber", 0),
            
#             # User text
#             author=DEFAULT_VARIABLES["author"],
#             notes=DEFAULT_VARIABLES["notes"],
            
#             # Processing parameters
#             # peakProgram=PEAKINDEX_DEFAULTS["peakProgram"],
#             threshold=PEAKINDEX_DEFAULTS["threshold"],
#             thresholdRatio=PEAKINDEX_DEFAULTS["thresholdRatio"],
#             maxRfactor=PEAKINDEX_DEFAULTS["maxRfactor"],
#             boxsize=PEAKINDEX_DEFAULTS["boxsize"],
#             max_number=PEAKINDEX_DEFAULTS["max_peaks"],
#             min_separation=PEAKINDEX_DEFAULTS["min_separation"],
#             peakShape=PEAKINDEX_DEFAULTS["peakShape"],
#             # scanPointStart=PEAKINDEX_DEFAULTS["scanPointStart"],
#             # scanPointEnd=PEAKINDEX_DEFAULTS["scanPointEnd"],
#             # depthRangeStart=PEAKINDEX_DEFAULTS.get("depthRangeStart"),
#             # depthRangeEnd=PEAKINDEX_DEFAULTS.get("depthRangeEnd"),
#             scanPoints=PEAKINDEX_DEFAULTS["scanPoints"],
#             scanPointslen=srange(PEAKINDEX_DEFAULTS["scanPoints"]).len(),
#             depthRange=PEAKINDEX_DEFAULTS["depthRange"],
#             depthRangelen=srange(PEAKINDEX_DEFAULTS["depthRange"]).len(),
#             detectorCropX1=PEAKINDEX_DEFAULTS["detectorCropX1"],
#             detectorCropX2=PEAKINDEX_DEFAULTS["detectorCropX2"],
#             detectorCropY1=PEAKINDEX_DEFAULTS["detectorCropY1"],
#             detectorCropY2=PEAKINDEX_DEFAULTS["detectorCropY2"],
#             min_size=PEAKINDEX_DEFAULTS["min_size"],
#             max_peaks=PEAKINDEX_DEFAULTS["max_peaks"],
#             smooth=PEAKINDEX_DEFAULTS["smooth"],
#             maskFile=PEAKINDEX_DEFAULTS["maskFile"],
#             indexKeVmaxCalc=PEAKINDEX_DEFAULTS["indexKeVmaxCalc"],
#             indexKeVmaxTest=PEAKINDEX_DEFAULTS["indexKeVmaxTest"],
#             indexAngleTolerance=PEAKINDEX_DEFAULTS["indexAngleTolerance"],
#             indexH=PEAKINDEX_DEFAULTS["indexH"],
#             indexK=PEAKINDEX_DEFAULTS["indexK"],
#             indexL=PEAKINDEX_DEFAULTS["indexL"],
#             indexCone=PEAKINDEX_DEFAULTS["indexCone"],
#             energyUnit=PEAKINDEX_DEFAULTS["energyUnit"],
#             exposureUnit=PEAKINDEX_DEFAULTS["exposureUnit"],
#             cosmicFilter=PEAKINDEX_DEFAULTS["cosmicFilter"],
#             recipLatticeUnit=PEAKINDEX_DEFAULTS["recipLatticeUnit"],
#             latticeParametersUnit=PEAKINDEX_DEFAULTS["latticeParametersUnit"],
#             # peaksearchPath=PEAKINDEX_DEFAULTS["peaksearchPath"],
#             # p2qPath=PEAKINDEX_DEFAULTS["p2qPath"],
#             # indexingPath=PEAKINDEX_DEFAULTS["indexingPath"],
            
#             # File paths
#             outputFolder=PEAKINDEX_DEFAULTS["outputFolder"],
#             # filefolder=CATALOG_DEFAULTS["filefolder"],
#             geoFile=PEAKINDEX_DEFAULTS["geoFile"],
#             crystFile=PEAKINDEX_DEFAULTS["crystFile"],
            
#             # Other fields
#             depth=PEAKINDEX_DEFAULTS["depth"],
#             beamline=PEAKINDEX_DEFAULTS["beamline"],
#         )
        
#         # Add root_path from DEFAULT_VARIABLES
#         peakindex_form_data.root_path = root_path
#         with Session(session_utils.get_engine()) as session:
#             # Get next peakindex_id
#             next_peakindex_id = db_utils.get_next_id(session, db_schema.PeakIndex)                                
#             # Store next_peakindex_id and update title
#             set_props('next-peakindex-id', {'value': next_peakindex_id})
#             set_props('peakindex-title', {'children': f"New peak indexing {next_peakindex_id}"})
            
#             # Retrieve data_path and filenamePrefix from catalog data
#             catalog_data = get_catalog_data(session, PEAKINDEX_DEFAULTS["scanNumber"], root_path, CATALOG_DEFAULTS)
#         peakindex_form_data.data_path = catalog_data["data_path"]
#         peakindex_form_data.filenamePrefix = catalog_data["filenamePrefix"]
            
#         # Populate the form with the defaults
#         set_peakindex_form_props(peakindex_form_data)
#     else:
#         raise PreventUpdate

@dash.callback(
    Output('peakindex-data-loaded-signal', 'data'),
    Input('url-create-peakindexing', 'href'),
    prevent_initial_call=True,
)
def load_scan_data_from_url(href):
    """
    Load scan data and optionally existing recon and peakindex data when provided in URL query parameters
    URL format: /create-peakindexing?scan_id={scan_id}
    Pooled URL format: /create-peakindexing?scan_id={scan_ids}
    With recon_id: /create-peakindexing?scan_id={scan_id}&recon_id={recon_id}
    With wirerecon_id: /create-peakindexing?scan_id={scan_id}&wirerecon_id={wirerecon_id}
    With peakindex_id: /create-peakindexing?scan_id={scan_id}&peakindex_id={peakindex_id}
    With both recon_id and peakindex_id: /create-peakindexing?scan_id={scan_id}&recon_id={recon_id}&peakindex_id={peakindex_id}
    """
    if not href:
        raise PreventUpdate

    parsed_url = urllib.parse.urlparse(href)
    query_params = urllib.parse.parse_qs(parsed_url.query)
    
    scan_id_str = query_params.get('scan_id', [None])[0]

    recon_id_str = query_params.get('recon_id', [None])[0]
    wirerecon_id_str = query_params.get('wirerecon_id', [None])[0]
    peakindex_id_str = query_params.get('peakindex_id', [None])[0]

    root_path = DEFAULT_VARIABLES.get("root_path", "")
    
    if scan_id_str:
        with Session(session_utils.get_engine()) as session:
            # # Get next peakindex_id
            # next_peakindex_id = db_utils.get_next_id(session, db_schema.PeakIndex)
            # # Store next_peakindex_id and update title
            # set_props('next-peakindex-id', {'value': next_peakindex_id})
            # set_props('peakindex-title', {'children': f"New peak indexing {next_peakindex_id}"})

            try:
                # This section handles both single and multiple/pooled scan numbers
                scan_ids = [int(sid) if sid and sid.lower() != 'none' else None for sid in (scan_id_str.split(',') if scan_id_str else [])]
                
                # Handle pooled reconstruction IDs
                wirerecon_ids = [int(wid) if wid and wid.lower() != 'none' else None for wid in (wirerecon_id_str.split(',') if wirerecon_id_str else [])]
                recon_ids = [int(rid) if rid and rid.lower() != 'none' else None for rid in (recon_id_str.split(',') if recon_id_str else [])]
                peakindex_ids = [int(pid) if pid and pid.lower() != 'none' else None for pid in (peakindex_id_str.split(',') if peakindex_id_str else [])]

                # Validate that lists have matching lengths
                if wirerecon_ids and len(wirerecon_ids) != len(scan_ids): raise ValueError(f"Mismatch: {len(scan_ids)} scan IDs but {len(wirerecon_ids)} wirerecon IDs")
                if recon_ids and len(recon_ids) != len(scan_ids): raise ValueError(f"Mismatch: {len(scan_ids)} scan IDs but {len(recon_ids)} recon IDs")
                if peakindex_ids and len(peakindex_ids) != len(scan_ids): raise ValueError(f"Mismatch: {len(scan_ids)} scan IDs but {len(peakindex_ids)} peakindex IDs")

                # If no reconstruction IDs provided, fill with None
                if not wirerecon_ids: wirerecon_ids = [None] * len(scan_ids)
                if not recon_ids: recon_ids = [None] * len(scan_ids)
                if not peakindex_ids: peakindex_ids = [None] * len(scan_ids)

                peakindex_form_data_list = []
                found_items = []
                not_found_items = []
                for i, current_scan_id in enumerate(scan_ids):
                    current_wirerecon_id = wirerecon_ids[i]
                    current_recon_id = recon_ids[i]
                    current_peakindex_id = peakindex_ids[i]

                    # Query metadata and scan data
                    metadata_data = session.query(db_schema.Metadata).filter(db_schema.Metadata.scanNumber == current_scan_id).first()
                    # scan_data = session.query(db_schema.Scan).filter(db_schema.Scan.scanNumber == current_scan_id).all()
                    if metadata_data:
                        if current_peakindex_id:
                            found_items.append(f"peak index {current_peakindex_id}")
                        elif current_recon_id:
                            found_items.append(f"reconstruction {current_recon_id}")
                        elif current_wirerecon_id:
                            found_items.append(f"wire reconstruction {current_wirerecon_id}")
                        else:
                            found_items.append(f"scan {current_scan_id}")

                        # Determine output folder format based on if reconstruction ID
                        # outputFolder = PEAKINDEX_DEFAULTS["outputFolder"]
                        # if current_recon_id or current_wirerecon_id:
                        #     outputFolder = outputFolder.replace("index_%d", "rec_%d/index_%d") #"analysis/scan_%d/rec_%d/index_%d"
                        
                        # # Format output folder with scan number and IDs
                        # try:
                        #     if current_wirerecon_id:
                        #         outputFolder = outputFolder % (current_scan_id, current_wirerecon_id, next_peakindex_id)
                        #     elif current_recon_id:
                        #         outputFolder = outputFolder % (current_scan_id, current_recon_id, next_peakindex_id)
                        #     else:
                        #         outputFolder = outputFolder % (current_scan_id, next_peakindex_id)
                        # except:
                        #     # If formatting fails, use the original string
                        #     pass
                        # next_peakindex_id += 1
                        
                        # Build output folder template based on available IDs
                        outputFolder = build_output_folder_template(
                            scan_num_int=current_scan_id,
                            data_path=None,  # Will be set later from id_data
                            wirerecon_id_int=current_wirerecon_id,
                            recon_id_int=current_recon_id
                        )

                        # If peakindex_id is provided, load existing peakindex data
                        if current_peakindex_id:
                            try:
                                peakindex_data = session.query(db_schema.PeakIndex).filter(db_schema.PeakIndex.peakindex_id == current_peakindex_id).first()
                                if peakindex_data:
                                    # Use existing peakindex data as the base
                                    peakindex_form_data = peakindex_data
                                    # Update only the necessary fields
                                    # peakindex_form_data.scanNumber = current_scan_id
                                    # peakindex_form_data.recon_id = current_recon_id
                                    # peakindex_form_data.wirerecon_id = current_wirerecon_id
                                    peakindex_form_data.outputFolder = outputFolder
                                    # Convert file paths to relative paths
                                    peakindex_form_data.geoFile = remove_root_path_prefix(peakindex_data.geoFile, root_path)
                                    peakindex_form_data.crystFile = remove_root_path_prefix(peakindex_data.crystFile, root_path)
                                    if peakindex_data.filefolder:
                                        peakindex_form_data.data_path = remove_root_path_prefix(peakindex_data.filefolder, root_path)
                                    if peakindex_data.filenamePrefix:
                                        peakindex_form_data.filenamePrefix = peakindex_data.filenamePrefix
                            
                            except (ValueError, Exception):
                                # If peakindex_id is not valid or not found, create defaults
                                current_peakindex_id = None

                        # Create defaults if no peakindex_id or if loading failed
                        if not current_peakindex_id:
                            # Create a PeakIndex object with populated defaults from metadata/scan
                            peakindex_form_data = db_schema.PeakIndex(
                                scanNumber=current_scan_id,
                                # Recon ID
                                recon_id=current_recon_id,
                                wirerecon_id=current_wirerecon_id,
                                # Energy-related fields from source
                                indexKeVmaxCalc=metadata_data.source_energy if metadata_data else PEAKINDEX_DEFAULTS["indexKeVmaxCalc"],
                                indexKeVmaxTest=metadata_data.source_energy if metadata_data else PEAKINDEX_DEFAULTS["indexKeVmaxTest"],
                                energyUnit=metadata_data.source_energy_unit if metadata_data else PEAKINDEX_DEFAULTS["energyUnit"],
                                outputFolder=outputFolder,
                                **{k: v for k, v in PEAKINDEX_DEFAULTS.items() if k not in ['scanNumber', 'outputFolder', 'indexKeVmaxCalc', 'indexKeVmaxTest', 'energyUnit']}
                            )

                        # Add root_path from DEFAULT_VARIABLES
                        peakindex_form_data.root_path = root_path

                        # Only query database if data_path or filenamePrefix are not already populated
                        if not all([hasattr(peakindex_form_data, 'data_path') and peakindex_form_data.data_path,
                                    hasattr(peakindex_form_data, 'filenamePrefix') and peakindex_form_data.filenamePrefix]):
                            # Build id_dict for this scan
                            id_dict = {
                                'scanNumber': current_scan_id,
                                'wirerecon_id': current_wirerecon_id,
                                'recon_id': current_recon_id,
                                'peakindex_id': current_peakindex_id
                            }
                            
                            # Get data from appropriate table (WireRecon, Recon, or Catalog)
                            id_data = get_data_from_id(session, id_dict, root_path, 'peakindex', CATALOG_DEFAULTS)
                            
                            # Set missing fields from the query result
                            if id_data:
                                if not (hasattr(peakindex_form_data, 'data_path') and peakindex_form_data.data_path):
                                    peakindex_form_data.data_path = id_data.get('data_path', '')
                                if not (hasattr(peakindex_form_data, 'filenamePrefix') and peakindex_form_data.filenamePrefix):
                                    peakindex_form_data.filenamePrefix = id_data.get('filenamePrefix', [])
                        
                        peakindex_form_data_list.append(peakindex_form_data)
                    else:
                        if current_peakindex_id:
                            not_found_items.append(f"peak index {current_peakindex_id}")
                        elif current_recon_id:
                            not_found_items.append(f"reconstruction {current_recon_id}")
                        elif current_wirerecon_id:
                            not_found_items.append(f"wire reconstruction {current_wirerecon_id}")
                        else:
                            not_found_items.append(f"scan {current_scan_id}")
                    
                # Create pooled peakindex_form_data by combining values from all scans
                if peakindex_form_data_list:
                    pooled_peakindex_form_data = db_schema.PeakIndex()
                    
                    # Pool all attributes - both database columns and extra attributes
                    all_attrs = list(db_schema.PeakIndex.__table__.columns.keys()) + ['root_path', 'data_path', 'filenamePrefix']
                    
                    for attr in all_attrs:
                        # if attr == 'peakindex_id': continue
                        
                        values = []
                        for d in peakindex_form_data_list:
                            if hasattr(d, attr):
                                values.append(getattr(d, attr))
                        
                        if values:
                            pooled_value = _merge_field_values(values)
                            setattr(pooled_peakindex_form_data, attr, pooled_value)
                    
                    # User text
                    pooled_peakindex_form_data.author = DEFAULT_VARIABLES['author']
                    pooled_peakindex_form_data.notes = DEFAULT_VARIABLES['notes']
                    # # Add root_path from DEFAULT_VARIABLES
                    # pooled_peakindex_form_data.root_path = root_path
                    # Populate the form with the defaults
                    set_peakindex_form_props(pooled_peakindex_form_data)

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
                    
                    peakindex_form_data = db_schema.PeakIndex(
                        scanNumber=str(scan_id_str).replace(',','; '),
                        
                        # User text
                        author=DEFAULT_VARIABLES['author'],
                        notes=DEFAULT_VARIABLES['notes'],
                        
                        # Processing parameters
                        threshold=PEAKINDEX_DEFAULTS["threshold"],
                        thresholdRatio=PEAKINDEX_DEFAULTS["thresholdRatio"],
                        maxRfactor=PEAKINDEX_DEFAULTS["maxRfactor"],
                        boxsize=PEAKINDEX_DEFAULTS["boxsize"],
                        max_number=PEAKINDEX_DEFAULTS["max_number"],
                        min_separation=PEAKINDEX_DEFAULTS["min_separation"],
                        peakShape=PEAKINDEX_DEFAULTS["peakShape"],
                        scanPoints=PEAKINDEX_DEFAULTS["scanPoints"],
                        scanPointslen=srange(PEAKINDEX_DEFAULTS["scanPoints"]).len(),
                        depthRange=PEAKINDEX_DEFAULTS["depthRange"],
                        depthRangelen=srange(PEAKINDEX_DEFAULTS["depthRange"]).len(),
                        detectorCropX1=PEAKINDEX_DEFAULTS["detectorCropX1"],
                        detectorCropX2=PEAKINDEX_DEFAULTS["detectorCropX2"],
                        detectorCropY1=PEAKINDEX_DEFAULTS["detectorCropY1"],
                        detectorCropY2=PEAKINDEX_DEFAULTS["detectorCropY2"],
                        min_size=PEAKINDEX_DEFAULTS["min_size"],
                        max_peaks=PEAKINDEX_DEFAULTS["max_peaks"],
                        smooth=PEAKINDEX_DEFAULTS["smooth"],
                        maskFile=PEAKINDEX_DEFAULTS["maskFile"],
                        indexKeVmaxCalc=PEAKINDEX_DEFAULTS["indexKeVmaxCalc"],
                        indexKeVmaxTest=PEAKINDEX_DEFAULTS["indexKeVmaxTest"],
                        indexAngleTolerance=PEAKINDEX_DEFAULTS["indexAngleTolerance"],
                        indexH=PEAKINDEX_DEFAULTS["indexH"],
                        indexK=PEAKINDEX_DEFAULTS["indexK"],
                        indexL=PEAKINDEX_DEFAULTS["indexL"],
                        indexCone=PEAKINDEX_DEFAULTS["indexCone"],
                        energyUnit=PEAKINDEX_DEFAULTS["energyUnit"],
                        exposureUnit=PEAKINDEX_DEFAULTS["exposureUnit"],
                        cosmicFilter=PEAKINDEX_DEFAULTS["cosmicFilter"],
                        recipLatticeUnit=PEAKINDEX_DEFAULTS["recipLatticeUnit"],
                        latticeParametersUnit=PEAKINDEX_DEFAULTS["latticeParametersUnit"],
                        outputFolder=PEAKINDEX_DEFAULTS["outputFolder"],
                        geoFile=PEAKINDEX_DEFAULTS["geoFile"],
                        crystFile=PEAKINDEX_DEFAULTS["crystFile"],
                        depth=PEAKINDEX_DEFAULTS["depth"],
                        beamline=PEAKINDEX_DEFAULTS["beamline"]
                    )
                    
                    # Set root_path
                    peakindex_form_data.root_path = root_path
                    peakindex_form_data.data_path = ""
                    peakindex_form_data.filenamePrefix = ""
                    
                    # Populate the form with the defaults
                    set_peakindex_form_props(peakindex_form_data)

            except Exception as e:
                set_props("alert-scan-loaded", {
                    'is_open': True, 
                    'children': f'Error loading scan data: {str(e)}',
                    'color': 'danger'
                })
    
    # Return timestamp to trigger downstream callbacks
    return datetime.datetime.now().isoformat()
