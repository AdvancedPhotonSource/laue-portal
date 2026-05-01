import datetime
import glob
import logging
import os
import urllib.parse

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, dcc, html, set_props
from dash.exceptions import PreventUpdate
from sqlalchemy.orm import Session

import laue_portal.components.navbar as navbar
import laue_portal.database.db_schema as db_schema
import laue_portal.database.db_utils as db_utils
import laue_portal.database.session_utils as session_utils
from laue_portal.components.form_base import _field
from laue_portal.components.peakindex_form import peakindex_form, set_peakindex_form_props
from laue_portal.components.validation_alerts import (
    apply_validation_highlights,
    update_validation_alerts,
    validation_alerts,
)
from laue_portal.config import DEFAULT_VARIABLES, PEAKINDEX_DEFAULTS
from laue_portal.database.db_utils import (
    get_data_from_id,
    parse_IDnumber,
    parse_parameter,
    remove_root_path_prefix,
    resolve_path_with_root,
)
from laue_portal.pages.callback_registrars import (
    _merge_field_values,
    register_check_filenames_callback,
    register_load_file_indices_callback,
    register_update_path_fields_callback,
)
from laue_portal.processing.queue.core import STATUS_REVERSE_MAPPING
from laue_portal.processing.queue.enqueue import enqueue_peakindexing
from laue_portal.services.validation import PEAKINDEX_FIELD_IDS, get_num_inputs_from_fields, validate_peakindexing
from laue_portal.utilities.hkl_parse import str2hkl
from laue_portal.utilities.srange import srange

logger = logging.getLogger(__name__)


def build_output_folder_template(scan_num_int, data_path, wirerecon_id_int=None, recon_id_int=None):
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
            clean_data_path = data_path.strip("/")
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
    "computer_name": "example_computer",
    "status": 0,
    "priority": 0,
    "submit_time": datetime.datetime.now(),
    "start_time": datetime.datetime.now(),
    "finish_time": datetime.datetime.now(),
}


def create_default_peakindex(overrides=None):
    """
    Create a PeakIndex object populated with defaults from config.

    This is the single source of truth for default PeakIndex creation.
    All defaults come from PEAKINDEX_DEFAULTS (config.yaml) and DEFAULT_VARIABLES.

    Args:
        overrides: Dict of values to override defaults (e.g., from metadata or URL params).
                   Keys should match PeakIndex model field names.

    Returns:
        db_schema.PeakIndex with all defaults set, plus extra attributes:
        - root_path: from DEFAULT_VARIABLES
        - data_path: empty string (to be populated later)
        - filenamePrefix: empty string (to be populated later)
    """
    # Start with config defaults
    defaults = {
        # User text from DEFAULT_VARIABLES
        "author": DEFAULT_VARIABLES.get("author", ""),
        "notes": DEFAULT_VARIABLES.get("notes", ""),
        # All processing parameters from PEAKINDEX_DEFAULTS
        "threshold": PEAKINDEX_DEFAULTS.get("threshold"),
        "thresholdRatio": PEAKINDEX_DEFAULTS.get("thresholdRatio"),
        "maxRfactor": PEAKINDEX_DEFAULTS.get("maxRfactor"),
        "boxsize": PEAKINDEX_DEFAULTS.get("boxsize"),
        "max_number": PEAKINDEX_DEFAULTS.get("max_number"),
        "min_separation": PEAKINDEX_DEFAULTS.get("min_separation"),
        "peakShape": PEAKINDEX_DEFAULTS.get("peakShape"),
        "min_size": PEAKINDEX_DEFAULTS.get("min_size"),
        "max_peaks": PEAKINDEX_DEFAULTS.get("max_peaks"),
        "smooth": PEAKINDEX_DEFAULTS.get("smooth"),
        "cosmicFilter": PEAKINDEX_DEFAULTS.get("cosmicFilter"),
        "maskFile": PEAKINDEX_DEFAULTS.get("maskFile"),
        # Indexing parameters
        "indexKeVmaxCalc": PEAKINDEX_DEFAULTS.get("indexKeVmaxCalc"),
        "indexKeVmaxTest": PEAKINDEX_DEFAULTS.get("indexKeVmaxTest"),
        "indexAngleTolerance": PEAKINDEX_DEFAULTS.get("indexAngleTolerance"),
        "indexH": PEAKINDEX_DEFAULTS.get("indexH"),
        "indexK": PEAKINDEX_DEFAULTS.get("indexK"),
        "indexL": PEAKINDEX_DEFAULTS.get("indexL"),
        "indexCone": PEAKINDEX_DEFAULTS.get("indexCone"),
        # Detector crop
        "detectorCropX1": PEAKINDEX_DEFAULTS.get("detectorCropX1"),
        "detectorCropX2": PEAKINDEX_DEFAULTS.get("detectorCropX2"),
        "detectorCropY1": PEAKINDEX_DEFAULTS.get("detectorCropY1"),
        "detectorCropY2": PEAKINDEX_DEFAULTS.get("detectorCropY2"),
        # Units
        "energyUnit": PEAKINDEX_DEFAULTS.get("energyUnit"),
        "exposureUnit": PEAKINDEX_DEFAULTS.get("exposureUnit"),
        "recipLatticeUnit": PEAKINDEX_DEFAULTS.get("recipLatticeUnit"),
        "latticeParametersUnit": PEAKINDEX_DEFAULTS.get("latticeParametersUnit"),
        # File paths
        "outputFolder": PEAKINDEX_DEFAULTS.get("outputFolder"),
        "geoFile": PEAKINDEX_DEFAULTS.get("geoFile"),
        "crystFile": PEAKINDEX_DEFAULTS.get("crystFile"),
        # Other
        "beamline": PEAKINDEX_DEFAULTS.get("beamline"),
        "depth": PEAKINDEX_DEFAULTS.get("depth"),
        # Scan/depth ranges (typically empty, user provides)
        "scanPoints": PEAKINDEX_DEFAULTS.get("scanPoints", ""),
        "depthRange": PEAKINDEX_DEFAULTS.get("depthRange", ""),
    }

    # Apply overrides
    if overrides:
        defaults.update(overrides)

    # Calculate srange lengths
    scanPoints_str = defaults.get("scanPoints", "") or ""
    depthRange_str = defaults.get("depthRange", "") or ""
    defaults["scanPointslen"] = srange(scanPoints_str).len() if scanPoints_str else 0
    defaults["depthRangelen"] = srange(depthRange_str).len() if depthRange_str else 0

    # Create PeakIndex object
    peakindex = db_schema.PeakIndex(**defaults)

    # Add extra attributes for form display (not in database model)
    peakindex.root_path = DEFAULT_VARIABLES.get("root_path", "")
    peakindex.data_path = ""
    peakindex.filenamePrefix = ""
    # Output XML: If absolute path, saves to that path directly.
    # If relative path or just filename, saves to the peakindexing output folder.
    peakindex.outputXML = PEAKINDEX_DEFAULTS.get("outputXML", "output.xml")

    return peakindex


CATALOG_DEFAULTS = {
    "filefolder": "tests/data/gdata",
    "filenamePrefix": "HAs_long_laue1_",
}

dash.register_page(__name__)

layout = dbc.Container(
    [
        html.Div(
            [
                navbar.navbar,
                dcc.Location(id="url-create-peakindexing", refresh=False),
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
                            width="auto",  # shrink to content
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
                    className="g-2",  # gutter between cols
                    justify="center",  # CENTER horizontally
                    align="center",  # CENTER vertically
                ),
                html.Hr(),
                validation_alerts,
                dbc.Row(
                    [
                        dbc.Col(
                            _field(
                                "Author",
                                "author",
                                kwargs={
                                    "type": "text",
                                    "placeholder": "Required! Enter author or Tag for the reconstruction",
                                },
                            ),
                            md=12,
                            xs=12,  # full row on small, wide on medium+
                            width="auto",
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
    className="dbc",
    fluid=True,
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
    num_placeholders = filename_prefix.count("%d")

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
            raise ValueError(f"Filename prefix '{filename_prefix}' has 2 %d placeholders but no Depth Range specified")
    else:
        raise ValueError(
            f"Filename prefix '{filename_prefix}' has {num_placeholders} %d placeholders (max 2 supported)"
        )

    return file_str


def validate_peakindexing_inputs(ctx):
    """Validate peak indexing inputs from Dash callback context."""
    fields = {}
    for key, value in ctx.states.items():
        component_id = key.split(".")[0]
        if component_id in PEAKINDEX_FIELD_IDS:
            fields[component_id] = value

    return validate_peakindexing(fields, catalog_defaults=CATALOG_DEFAULTS)


@dash.callback(
    Input("peakindex-validate-btn", "n_clicks"),
    State("data_path", "value"),
    State("filenamePrefix", "value"),
    State("scanPoints", "value"),
    State("depthRange", "value"),
    State("geoFile", "value"),
    State("crystFile", "value"),
    State("outputFolder", "value"),
    State("root_path", "value"),
    State("IDnumber", "value"),
    State("author", "value"),
    State("threshold", "value"),
    State("thresholdRatio", "value"),
    State("maxRfactor", "value"),
    State("boxsize", "value"),
    State("max_number", "value"),
    State("min_separation", "value"),
    State("min_size", "value"),
    State("max_peaks", "value"),
    State("indexKeVmaxCalc", "value"),
    State("indexKeVmaxTest", "value"),
    State("indexAngleTolerance", "value"),
    State("indexCone", "value"),
    State("indexHKL", "value"),
    running=[
        (Output("peakindex-validate-btn", "disabled"), True, False),
        (
            Output("peakindex-validate-btn", "children"),
            [dbc.Spinner(size="sm", spinner_class_name="me-2"), "Validating..."],
            "Validate",
        ),
        (Output("submit_peakindexing", "disabled"), True, False),
    ],
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
    IDnumber,
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
    Input("submit_peakindexing", "n_clicks"),
    State("root_path", "value"),
    State("IDnumber", "value"),
    State("author", "value"),
    State("notes", "value"),
    State("threshold", "value"),
    State("thresholdRatio", "value"),
    State("maxRfactor", "value"),
    State("boxsize", "value"),
    State("max_number", "value"),
    State("min_separation", "value"),
    State("peakShape", "value"),
    State("scanPoints", "value"),
    State("depthRange", "value"),
    State("min_size", "value"),
    State("max_peaks", "value"),
    State("smooth", "value"),
    State("maskFile", "value"),
    State("indexKeVmaxCalc", "value"),
    State("indexKeVmaxTest", "value"),
    State("indexAngleTolerance", "value"),
    State("indexHKL", "value"),
    State("indexCone", "value"),
    State("cosmicFilter", "value"),
    State("data_path", "value"),
    State("filenamePrefix", "value"),
    State("outputFolder", "value"),
    State("geoFile", "value"),
    State("crystFile", "value"),
    State("depth", "value"),
    State("outputXML", "value"),
    running=[
        (Output("submit_peakindexing", "disabled"), True, False),
        (
            Output("submit_peakindexing", "children"),
            [dbc.Spinner(size="sm", spinner_class_name="me-2"), "Submitting..."],
            "Submit",
        ),
        (Output("peakindex-validate-btn", "disabled"), True, False),
    ],
    prevent_initial_call=True,
)
def submit_parameters(
    n,
    root_path,
    IDnumber,
    author,
    notes,
    threshold,
    thresholdRatio,
    maxRfactor,
    boxsize,
    max_number,
    min_separation,
    peakShape,
    scanPoints,
    depthRange,
    min_size,
    max_peaks,
    smooth,
    maskFile,
    indexKeVmaxCalc,
    indexKeVmaxTest,
    indexAngleTolerance,
    indexHKL,
    indexCone,
    cosmicFilter,
    data_path,
    filenamePrefix,
    outputFolder,
    geometry_file,
    crystal_file,
    depth,
    outputXML,
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
    errors = validation_result["errors"]
    # warnings = validation_result['warnings']

    # Block submission if there are errors
    if errors:
        set_props(
            "alert-submit",
            {
                "is_open": True,
                "children": "Submission blocked due to validation errors. Please fix the errors and try again.",
                "color": "danger",
            },
        )
        return

    # Parse IDnumber to get individual IDs
    with Session(session_utils.get_engine()) as temp_session:
        try:
            id_dict = parse_IDnumber(IDnumber, temp_session)
            scanNumber = id_dict.get("scanNumber")
            wirerecon_id = id_dict.get("wirerecon_id")
            recon_id = id_dict.get("recon_id")
            # peakindex_id = id_dict.get('peakindex_id')
        except ValueError as e:
            set_props("alert-submit", {"is_open": True, "children": f"Invalid ID Number: {str(e)}", "color": "danger"})
            return

    # Build all_submit_params from ctx.states (consistent with validation approach)
    all_submit_params = {}
    for key, value in ctx.states.items():
        component_id = key.split(".")[0]
        all_submit_params[component_id] = value

    # Add parsed IDs to the params dict
    all_submit_params["scanNumber"] = scanNumber
    all_submit_params["wirerecon_id"] = wirerecon_id
    all_submit_params["recon_id"] = recon_id

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
        # Auto-fill max_peaks with default value of 200 if empty
        if not max_peaks or max_peaks == "":
            max_peaks = str(PEAKINDEX_DEFAULTS["max_peaks"])
        max_peaks_list = parse_parameter(max_peaks, num_inputs)
        # Default checkbox values to False if None (never interacted with)
        if smooth is None:
            smooth = False
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
        # Default checkbox values to False if None (never interacted with)
        if cosmicFilter is None:
            cosmicFilter = False
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
        set_props("alert-submit", {"is_open": True, "children": str(e), "color": "danger"})
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
                        set_props(
                            "alert-submit",
                            {
                                "is_open": True,
                                "children": f"Invalid scan number: {current_scanNumber}",
                                "color": "danger",
                            },
                        )

                # Convert wirerecon_id to integer if present
                wirerecon_id_int = None
                if current_wirerecon_id:
                    try:
                        wirerecon_id_int = int(current_wirerecon_id)
                    except (ValueError, TypeError) as e:
                        logger.error(f"Failed to convert wirerecon_id '{current_wirerecon_id}' to integer: {e}")
                        set_props(
                            "alert-submit",
                            {
                                "is_open": True,
                                "children": f"Invalid wire reconstruction ID: {current_wirerecon_id}",
                                "color": "danger",
                            },
                        )

                # Convert recon_id to integer if present
                recon_id_int = None
                if current_recon_id:
                    try:
                        recon_id_int = int(current_recon_id)
                    except (ValueError, TypeError) as e:
                        logger.error(f"Failed to convert recon_id '{current_recon_id}' to integer: {e}")
                        set_props(
                            "alert-submit",
                            {
                                "is_open": True,
                                "children": f"Invalid reconstruction ID: {current_recon_id}",
                                "color": "danger",
                            },
                        )

                # Convert relative paths to full paths, but respect absolute paths
                full_geometry_file = resolve_path_with_root(current_geo_file, root_path)
                full_crystal_file = resolve_path_with_root(current_crystal_file, root_path)

                # Get next ID for this action
                next_peakindex_id = db_utils.get_next_id(session, db_schema.PeakIndex)
                # Now that we have the ID, format the output folder path by replacement of the final %d in the template
                try:
                    if "%d" in current_output_folder:
                        formatted_output_folder = current_output_folder % next_peakindex_id
                    else:
                        formatted_output_folder = current_output_folder
                except (TypeError, ValueError) as e:
                    logger.error(f"Failed to format output folder '{current_output_folder}': {e}")
                    formatted_output_folder = current_output_folder  # Fallback if formatting fails

                # Use resolve_path_with_root to allow absolute paths to override root_path
                full_output_folder = resolve_path_with_root(formatted_output_folder, root_path)

                # Create output directory if it doesn't exist
                try:
                    os.makedirs(full_output_folder, exist_ok=True)
                    logger.info(f"Output directory: {full_output_folder}")
                except Exception as e:
                    logger.error(f"Failed to create output directory {full_output_folder}: {e}")
                    set_props(
                        "alert-submit",
                        {
                            "is_open": True,
                            "children": f"Failed to create output directory: {str(e)}",
                            "color": "danger",
                        },
                    )
                    continue

                JOB_DEFAULTS.update({"submit_time": datetime.datetime.now()})
                JOB_DEFAULTS.update({"start_time": datetime.datetime.now()})
                JOB_DEFAULTS.update({"finish_time": datetime.datetime.now()})

                job = db_schema.Job(
                    computer_name=JOB_DEFAULTS["computer_name"],
                    status=JOB_DEFAULTS["status"],
                    priority=JOB_DEFAULTS["priority"],
                    submit_time=JOB_DEFAULTS["submit_time"],
                    start_time=JOB_DEFAULTS["start_time"],
                    finish_time=JOB_DEFAULTS["finish_time"],
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
                    depthRange_srange = srange("")
                    depthRange_nums = [None]  # No reconstruction indices

                # Create subjobs for each combination of scan point and depth
                subjob_count = 0
                for _scanPoint_num in scanPoint_nums:
                    for _depthRange_num in depthRange_nums:
                        subjob = db_schema.SubJob(
                            job_id=job_id,
                            computer_name=JOB_DEFAULTS["computer_name"],
                            status=STATUS_REVERSE_MAPPING["Queued"],
                            priority=JOB_DEFAULTS["priority"],
                        )
                        session.add(subjob)
                        subjob_count += 1

                # Extract HKL values from indexHKL parameter using str2hkl
                current_indexHKL_str = str(indexHKL_list[i])
                try:
                    hkl_values = str2hkl(current_indexHKL_str, Nmin=3, Nmax=3)
                    # hkl_values is a list of 3 integers or floats [h, k, l]
                except (TypeError, ValueError) as e:
                    logger.error(f"Failed to parse HKL '{current_indexHKL_str}': {e}")
                    set_props(
                        "alert-submit",
                        {"is_open": True, "children": f"Invalid HKL value: {current_indexHKL_str}", "color": "danger"},
                    )
                    continue

                # Get filefolder and filenamePrefix
                current_data_path = data_path_list[i]
                current_filename_prefix_str = filenamePrefix_list[i]
                current_filename_prefix = (
                    [s.strip() for s in current_filename_prefix_str.split(",")] if current_filename_prefix_str else []
                )
                # Build full path
                current_full_data_path = resolve_path_with_root(current_data_path, root_path)

                # Determine outputXML value, using default if not provided
                current_outputXML = outputXML or PEAKINDEX_DEFAULTS.get("outputXML", "output.xml")

                peakindex = db_schema.PeakIndex(
                    scanNumber=scan_num_int,
                    job_id=job_id,
                    author=author_list[i],
                    notes=notes_list[i],
                    recon_id=recon_id_int,
                    wirerecon_id=wirerecon_id_int,
                    filefolder=current_full_data_path,
                    filenamePrefix=current_filename_prefix,
                    threshold=threshold_list[i],
                    thresholdRatio=thresholdRatio_list[i],
                    maxRfactor=maxRfactor_list[i],
                    boxsize=boxsize_list[i],
                    max_number=max_number_list[i],
                    min_separation=min_separation_list[i],
                    peakShape=peakShape_list[i],
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
                    indexH=int(hkl_values[0]),
                    indexK=int(hkl_values[1]),
                    indexL=int(hkl_values[2]),
                    indexCone=indexCone_list[i],
                    energyUnit=energyUnit_list[i],
                    exposureUnit=exposureUnit_list[i],
                    cosmicFilter=cosmicFilter_list[i],
                    recipLatticeUnit=recipLatticeUnit_list[i],
                    latticeParametersUnit=latticeParametersUnit_list[i],
                    outputFolder=full_output_folder,
                    outputXML=current_outputXML,
                    geoFile=full_geometry_file,
                    crystFile=full_crystal_file,
                    depth=depth_list[i],
                    beamline=beamline_list[i],
                )
                session.add(peakindex)
                peakindexes_to_enqueue.append(
                    {
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
                        "indexH": int(hkl_values[0]),
                        "indexK": int(hkl_values[1]),
                        "indexL": int(hkl_values[2]),
                        "outputXML": outputXML or PEAKINDEX_DEFAULTS.get("outputXML", "output.xml"),
                    }
                )

            session.commit()
            set_props("alert-submit", {"is_open": True, "children": "Entries Added to Database", "color": "success"})
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to create database entries: {e}")
            set_props(
                "alert-submit",
                {"is_open": True, "children": f"Failed to create database entries: {str(e)}", "color": "danger"},
            )
            return

    # Second loop: Enqueue jobs to Redis
    for _, spec in enumerate(peakindexes_to_enqueue):
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
                            current_filename_prefix_i, scanPoint_num, depthRange_num
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
                index_l=spec["indexL"],
                output_xml=spec["outputXML"],
            )

            logger.info(
                f"Peakindexing batch job {spec['job_id']} enqueued with RQ ID: {rq_job_id} for {len(input_files)} files"
            )

            set_props(
                "alert-submit",
                {
                    "is_open": True,
                    "children": f"Job {spec['job_id']} submitted to queue with {len(input_files)} file(s)",
                    "color": "info",
                },
            )
        except Exception as e:
            # Provide more context to help diagnose format issues and input parsing
            logger.error(
                f"Failed to enqueue job {spec['job_id']}: {e}. "
                f"filenamePrefix='{current_filename_prefix_str}', "
                f"parsed prefixes={current_filename_prefix}, "
                f"scanPoints='{spec['scanPoints']}', depthRange='{spec['depthRange']}', data_path='{current_data_path}'"
            )
            set_props(
                "alert-submit",
                {
                    "is_open": True,
                    "children": f"Failed to queue job {spec['job_id']}: {str(e)}. "
                    f"filenamePrefix={current_filename_prefix_str}, "
                    f"scanPoints={spec['scanPoints']}, depthRange={spec['depthRange']}",
                    "color": "danger",
                },
            )


# Register shared callbacks
register_update_path_fields_callback(
    update_paths_id="peakindex-update-path-fields-btn",
    # scan_number_id='scanNumber',
    id_number_id="IDnumber",
    root_path_id="root_path",
    data_path_id="data_path",
    filename_prefix_id="filenamePrefix",
    alert_id="alert-scan-loaded",
    catalog_defaults=CATALOG_DEFAULTS,
    output_folder_id="outputFolder",
    build_template_func=build_output_folder_template,
    context="peakindex",
)

register_load_file_indices_callback(
    button_id="peakindex-load-file-indices-btn",
    data_loaded_signal_id="peakindex-data-loaded-signal",
    data_path_id="data_path",
    filename_prefix_id="filenamePrefix",
    scan_points_id="scanPoints",
    depth_range_id="depthRange",  # Peak indexing uses depth range
    alert_id="alert-scan-loaded",
    num_indices=2,
)

register_check_filenames_callback(
    find_filenames_id="peakindex-check-filenames-btn",
    data_path_id="data_path",
    filename_prefix_id="filenamePrefix",
    filename_templates_id="peakindex-filename-templates",
    root_path_id="root_path",
    num_indices=2,
    scan_points_id="scanPoints",
    depth_range_id="depthRange",
)


@dash.callback(
    Output("peakindex-data-loaded-signal", "data"),
    Input("url-create-peakindexing", "href"),
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
    With peakindex_id only (unlinked): /create-peakindexing?peakindex_id={peakindex_id}
    With both recon_id and peakindex_id: /create-peakindexing?scan_id={scan_id}&recon_id={recon_id}&peakindex_id={peakindex_id}
    """
    if not href:
        raise PreventUpdate

    parsed_url = urllib.parse.urlparse(href)
    query_params = urllib.parse.parse_qs(parsed_url.query)

    scan_id_str = query_params.get("scan_id", [None])[0]

    recon_id_str = query_params.get("recon_id", [None])[0]
    wirerecon_id_str = query_params.get("wirerecon_id", [None])[0]
    peakindex_id_str = query_params.get("peakindex_id", [None])[0]

    root_path = DEFAULT_VARIABLES.get("root_path", "")

    # Handle case where no query parameters are provided - load defaults
    if not scan_id_str and not peakindex_id_str:
        # Use factory function to create default PeakIndex
        peakindex_form_data = create_default_peakindex()
        set_peakindex_form_props(peakindex_form_data)
        return datetime.datetime.now().isoformat()

    # Handle case where only peakindex_id is provided (unlinked peakindex)
    if not scan_id_str and peakindex_id_str:
        with Session(session_utils.get_engine()) as session:
            try:
                peakindex_ids = [
                    int(pid) if pid and pid.lower() != "none" else None
                    for pid in (peakindex_id_str.split(",") if peakindex_id_str else [])
                ]

                peakindex_form_data_list = []
                found_items = []
                not_found_items = []

                for current_peakindex_id in peakindex_ids:
                    if not current_peakindex_id:
                        continue

                    # Query peakindex data directly
                    peakindex_data = (
                        session.query(db_schema.PeakIndex)
                        .filter(db_schema.PeakIndex.peakindex_id == current_peakindex_id)
                        .first()
                    )

                    if peakindex_data:
                        found_items.append(f"peak index {current_peakindex_id}")

                        # Use existing peakindex data as the base
                        peakindex_form_data = peakindex_data

                        # Get the scan/recon IDs from the peakindex if they exist
                        current_scan_id = peakindex_data.scanNumber
                        current_wirerecon_id = peakindex_data.wirerecon_id
                        current_recon_id = peakindex_data.recon_id

                        # Build output folder template
                        outputFolder = build_output_folder_template(
                            scan_num_int=current_scan_id,
                            data_path=None,
                            wirerecon_id_int=current_wirerecon_id,
                            recon_id_int=current_recon_id,
                        )

                        # Clear peakindex_id since we're creating a NEW peakindex
                        peakindex_form_data.peakindex_id = None
                        peakindex_form_data.outputFolder = outputFolder

                        # Convert file paths to relative paths
                        peakindex_form_data.geoFile = remove_root_path_prefix(peakindex_data.geoFile, root_path)
                        peakindex_form_data.crystFile = remove_root_path_prefix(peakindex_data.crystFile, root_path)
                        if peakindex_data.filefolder:
                            peakindex_form_data.data_path = remove_root_path_prefix(
                                peakindex_data.filefolder, root_path
                            )
                        if peakindex_data.filenamePrefix:
                            peakindex_form_data.filenamePrefix = peakindex_data.filenamePrefix

                        # Add root_path
                        peakindex_form_data.root_path = root_path

                        peakindex_form_data_list.append(peakindex_form_data)
                    else:
                        not_found_items.append(f"peak index {current_peakindex_id}")

                # Create pooled peakindex_form_data by combining values from all peakindexes
                if peakindex_form_data_list:
                    pooled_peakindex_form_data = db_schema.PeakIndex()

                    # Pool all attributes
                    all_attrs = list(db_schema.PeakIndex.__table__.columns.keys()) + [
                        "root_path",
                        "data_path",
                        "filenamePrefix",
                    ]

                    for attr in all_attrs:
                        values = []
                        for d in peakindex_form_data_list:
                            if hasattr(d, attr):
                                values.append(getattr(d, attr))

                        if values:
                            pooled_value = _merge_field_values(values)
                            setattr(pooled_peakindex_form_data, attr, pooled_value)

                    # User text
                    pooled_peakindex_form_data.author = DEFAULT_VARIABLES["author"]
                    pooled_peakindex_form_data.notes = DEFAULT_VARIABLES["notes"]

                    # Populate the form
                    set_peakindex_form_props(pooled_peakindex_form_data)

                    # Set alert based on what was found
                    if not_found_items:
                        set_props(
                            "alert-scan-loaded",
                            {
                                "is_open": True,
                                "children": f"Loaded data for {len(found_items)} items. Could not find: {', '.join(not_found_items)}.",
                                "color": "warning",
                            },
                        )
                    else:
                        set_props(
                            "alert-scan-loaded",
                            {
                                "is_open": True,
                                "children": f"Successfully loaded and merged data from {len(found_items)} items into the form.",
                                "color": "success",
                            },
                        )
                else:
                    # No valid peakindexes found
                    set_props(
                        "alert-scan-loaded",
                        {
                            "is_open": True,
                            "children": f"Could not find any of the requested items: {', '.join(not_found_items)}. Displaying default values.",
                            "color": "danger",
                        },
                    )

                    # Show defaults using factory function
                    peakindex_form_data = create_default_peakindex()
                    set_peakindex_form_props(peakindex_form_data)

            except Exception as e:
                set_props(
                    "alert-scan-loaded",
                    {"is_open": True, "children": f"Error loading peakindex data: {str(e)}", "color": "danger"},
                )

        return datetime.datetime.now().isoformat()

    # Original behavior: scan_id is provided
    if scan_id_str:
        with Session(session_utils.get_engine()) as session:
            try:
                # This section handles both single and multiple/pooled scan numbers
                scan_ids = [
                    int(sid) if sid and sid.lower() != "none" else None
                    for sid in (scan_id_str.split(",") if scan_id_str else [])
                ]

                # Handle pooled reconstruction IDs
                wirerecon_ids = [
                    int(wid) if wid and wid.lower() != "none" else None
                    for wid in (wirerecon_id_str.split(",") if wirerecon_id_str else [])
                ]
                recon_ids = [
                    int(rid) if rid and rid.lower() != "none" else None
                    for rid in (recon_id_str.split(",") if recon_id_str else [])
                ]
                peakindex_ids = [
                    int(pid) if pid and pid.lower() != "none" else None
                    for pid in (peakindex_id_str.split(",") if peakindex_id_str else [])
                ]

                # Validate that lists have matching lengths
                if wirerecon_ids and len(wirerecon_ids) != len(scan_ids):
                    raise ValueError(f"Mismatch: {len(scan_ids)} scan IDs but {len(wirerecon_ids)} wirerecon IDs")
                if recon_ids and len(recon_ids) != len(scan_ids):
                    raise ValueError(f"Mismatch: {len(scan_ids)} scan IDs but {len(recon_ids)} recon IDs")
                if peakindex_ids and len(peakindex_ids) != len(scan_ids):
                    raise ValueError(f"Mismatch: {len(scan_ids)} scan IDs but {len(peakindex_ids)} peakindex IDs")

                # If no reconstruction IDs provided, fill with None
                if not wirerecon_ids:
                    wirerecon_ids = [None] * len(scan_ids)
                if not recon_ids:
                    recon_ids = [None] * len(scan_ids)
                if not peakindex_ids:
                    peakindex_ids = [None] * len(scan_ids)

                peakindex_form_data_list = []
                found_items = []
                not_found_items = []
                for i, current_scan_id in enumerate(scan_ids):
                    current_wirerecon_id = wirerecon_ids[i]
                    current_recon_id = recon_ids[i]
                    current_peakindex_id = peakindex_ids[i]

                    # Query metadata and scan data
                    metadata_data = (
                        session.query(db_schema.Metadata)
                        .filter(db_schema.Metadata.scanNumber == current_scan_id)
                        .first()
                    )
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

                        # Build output folder template based on available IDs
                        outputFolder = build_output_folder_template(
                            scan_num_int=current_scan_id,
                            data_path=None,  # Will be set later from id_data
                            wirerecon_id_int=current_wirerecon_id,
                            recon_id_int=current_recon_id,
                        )

                        # If peakindex_id is provided, load existing peakindex data
                        if current_peakindex_id:
                            try:
                                peakindex_data = (
                                    session.query(db_schema.PeakIndex)
                                    .filter(db_schema.PeakIndex.peakindex_id == current_peakindex_id)
                                    .first()
                                )
                                if peakindex_data:
                                    # Use existing peakindex data as the base
                                    peakindex_form_data = peakindex_data
                                    # Update only the necessary fields
                                    # Override the scan/recon IDs with what was passed in the URL
                                    # This ensures the ID Number field shows the underlying scan, not the peakindex
                                    peakindex_form_data.scanNumber = current_scan_id
                                    peakindex_form_data.recon_id = current_recon_id
                                    peakindex_form_data.wirerecon_id = current_wirerecon_id
                                    # Clear peakindex_id since we're creating a NEW peakindex, not editing the existing one
                                    peakindex_form_data.peakindex_id = None
                                    peakindex_form_data.outputFolder = outputFolder
                                    # Convert file paths to relative paths
                                    peakindex_form_data.geoFile = remove_root_path_prefix(
                                        peakindex_data.geoFile, root_path
                                    )
                                    peakindex_form_data.crystFile = remove_root_path_prefix(
                                        peakindex_data.crystFile, root_path
                                    )
                                    if peakindex_data.filefolder:
                                        peakindex_form_data.data_path = remove_root_path_prefix(
                                            peakindex_data.filefolder, root_path
                                        )
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
                                indexKeVmaxCalc=metadata_data.source_energy
                                if (metadata_data and metadata_data.source_energy is not None)
                                else PEAKINDEX_DEFAULTS["indexKeVmaxCalc"],
                                indexKeVmaxTest=metadata_data.source_energy
                                if (metadata_data and metadata_data.source_energy is not None)
                                else PEAKINDEX_DEFAULTS["indexKeVmaxTest"],
                                energyUnit=metadata_data.source_energy_unit
                                if (metadata_data and metadata_data.source_energy_unit is not None)
                                else PEAKINDEX_DEFAULTS["energyUnit"],
                                outputFolder=outputFolder,
                                **{
                                    k: v
                                    for k, v in PEAKINDEX_DEFAULTS.items()
                                    if k
                                    not in [
                                        "scanNumber",
                                        "outputFolder",
                                        "indexKeVmaxCalc",
                                        "indexKeVmaxTest",
                                        "energyUnit",
                                    ]
                                },
                            )

                        # Add root_path from DEFAULT_VARIABLES
                        peakindex_form_data.root_path = root_path

                        # Only query database if data_path or filenamePrefix are not already populated
                        if not all(
                            [
                                hasattr(peakindex_form_data, "data_path") and peakindex_form_data.data_path,
                                hasattr(peakindex_form_data, "filenamePrefix") and peakindex_form_data.filenamePrefix,
                            ]
                        ):
                            # Build id_dict for this scan
                            id_dict = {
                                "scanNumber": current_scan_id,
                                "wirerecon_id": current_wirerecon_id,
                                "recon_id": current_recon_id,
                                "peakindex_id": current_peakindex_id,
                            }

                            # Get data from appropriate table (WireRecon, Recon, or Catalog)
                            id_data = get_data_from_id(session, id_dict, root_path, "peakindex", CATALOG_DEFAULTS)

                            # Set missing fields from the query result
                            if id_data:
                                if not (hasattr(peakindex_form_data, "data_path") and peakindex_form_data.data_path):
                                    peakindex_form_data.data_path = id_data.get("data_path", "")
                                if not (
                                    hasattr(peakindex_form_data, "filenamePrefix")
                                    and peakindex_form_data.filenamePrefix
                                ):
                                    peakindex_form_data.filenamePrefix = id_data.get("filenamePrefix", [])

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
                    all_attrs = list(db_schema.PeakIndex.__table__.columns.keys()) + [
                        "root_path",
                        "data_path",
                        "filenamePrefix",
                    ]

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
                    pooled_peakindex_form_data.author = DEFAULT_VARIABLES["author"]
                    pooled_peakindex_form_data.notes = DEFAULT_VARIABLES["notes"]
                    # # Add root_path from DEFAULT_VARIABLES
                    # pooled_peakindex_form_data.root_path = root_path
                    # Populate the form with the defaults
                    set_peakindex_form_props(pooled_peakindex_form_data)

                    # Set alert based on what was found
                    if not_found_items:
                        # Partial success
                        set_props(
                            "alert-scan-loaded",
                            {
                                "is_open": True,
                                "children": f"Loaded data for {len(found_items)} items. Could not find: {', '.join(not_found_items)}.",
                                "color": "warning",
                            },
                        )
                    else:
                        # Full success
                        set_props(
                            "alert-scan-loaded",
                            {
                                "is_open": True,
                                "children": f"Successfully loaded and merged data from {len(found_items)} items into the form.",
                                "color": "success",
                            },
                        )
                else:
                    # Fallback if no valid scans found
                    if not_found_items:
                        set_props(
                            "alert-scan-loaded",
                            {
                                "is_open": True,
                                "children": f"Could not find any of the requested items: {', '.join(not_found_items)}. Displaying default values.",
                                "color": "danger",
                            },
                        )

                    # Use factory function for fallback defaults
                    peakindex_form_data = create_default_peakindex(
                        overrides={"scanNumber": str(scan_id_str).replace(",", "; ")}
                    )
                    set_peakindex_form_props(peakindex_form_data)

            except Exception as e:
                set_props(
                    "alert-scan-loaded",
                    {"is_open": True, "children": f"Error loading scan data: {str(e)}", "color": "danger"},
                )

    # Return timestamp to trigger downstream callbacks
    return datetime.datetime.now().isoformat()
