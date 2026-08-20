import datetime
import logging
import os
import urllib.parse
from types import SimpleNamespace

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, dcc, html, set_props
from dash.exceptions import PreventUpdate
from sqlalchemy.orm import Session

import laue_portal.components.navbar as navbar
import laue_portal.database.db_schema as db_schema
import laue_portal.database.session_utils as session_utils
from laue_portal.components.validation_alerts import (
    apply_validation_highlights,
    update_validation_alerts,
    validation_alerts,
)
from laue_portal.components.wire_recon_form import set_wire_recon_form_props, wire_recon_form
from laue_portal.config import DEFAULT_VARIABLES, WIRERECON_DEFAULTS
from laue_portal.database.db_utils import (
    get_catalog_by_scan_number,
    get_catalog_data,
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
from laue_portal.processing.queue.enqueue import enqueue_reconstruction
from laue_portal.services.validation import (
    add_validation_message,
    all_path_fields_are_absolute,
    get_num_inputs_from_fields,
    safe_float,
    validate_field_value,
)
from laue_portal.utilities.srange import srange
from laue_portal.workflows.identity import merged_identity_value, parse_workflow_identities
from laue_portal.workflows.reconstruction import (
    WireReconstructionRequest,
    create_reconstruction,
    get_reconstruction,
)

logger = logging.getLogger(__name__)


def build_output_folder_template(scan_num_int, data_path, reconstruction_id_int=None):
    """
    Build output folder template based on available IDs from database chain.
    Only the final action ID remains as %d.

    Parameters:
    - scan_num_int: scanNumber (int or None)
    - data_path: data path to use if scanNumber unknown
    - root_path: root path

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

    # Add final action placeholder for wire recon
    path_parts.append("rec_%d")
    path_parts.append("data")

    return os.path.join(*path_parts)


def create_default_wirerecon(overrides=None):
    """Return form data using the canonical reconstruction field names."""
    defaults = {
        "id": None,
        "scan_number": None,
        "root_path": DEFAULT_VARIABLES.get("root_path", ""),
        "data_path": "",
        "input_path": "",
        "filename_prefixes": [],
        "author": DEFAULT_VARIABLES.get("author", ""),
        "notes": DEFAULT_VARIABLES.get("notes", ""),
        "geometry_file": WIRERECON_DEFAULTS.get("geoFile"),
        "percent_brightest": WIRERECON_DEFAULTS.get("percent_brightest"),
        "wire_edges": WIRERECON_DEFAULTS.get("wire_edges"),
        "depth_start": WIRERECON_DEFAULTS.get("depth_start"),
        "depth_end": WIRERECON_DEFAULTS.get("depth_end"),
        "depth_resolution": WIRERECON_DEFAULTS.get("depth_resolution"),
        "num_threads": DEFAULT_VARIABLES.get("num_threads"),
        "memory_limit_mb": DEFAULT_VARIABLES.get("memory_limit_mb"),
        "scan_points": WIRERECON_DEFAULTS.get("scanPoints", ""),
        "output_path_template": build_output_folder_template(None, None),
        "verbose": DEFAULT_VARIABLES.get("verbose"),
    }
    if overrides:
        defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _copy_reconstruction_for_form(run, root_path):
    parameters = run.wire_parameters
    if parameters is None:
        raise ValueError(f"Reconstruction R{run.id} has no wire parameters")
    return create_default_wirerecon(
        {
            "id": run.id,
            "scan_number": run.scan_number,
            "data_path": remove_root_path_prefix(run.input_path, root_path),
            "input_path": run.input_path,
            "filename_prefixes": parameters.filename_prefixes,
            "author": DEFAULT_VARIABLES.get("author", ""),
            "notes": DEFAULT_VARIABLES.get("notes", ""),
            "geometry_file": remove_root_path_prefix(parameters.geometry_file, root_path),
            "percent_brightest": parameters.percent_brightest,
            "wire_edges": parameters.wire_edges,
            "depth_start": parameters.depth_start,
            "depth_end": parameters.depth_end,
            "depth_resolution": parameters.depth_resolution,
            "num_threads": parameters.num_threads,
            "memory_limit_mb": parameters.memory_limit_mb,
            "scan_points": parameters.scan_points,
            "output_path_template": build_output_folder_template(run.scan_number, run.input_path),
            "verbose": parameters.verbose,
        }
    )


CATALOG_DEFAULTS = {
    "filefolder": "tests/data/gdata",
    "filenamePrefix": "HAs_long_laue1_",
}

dash.register_page(__name__)

layout = dbc.Container(
    [
        html.Div(
            className="lp-form-page",
            children=[
                navbar.navbar,
                dcc.Location(id="url-create-wirerecon", refresh=False),
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
                html.Div(
                    className="lp-form-masthead",
                    children=[
                        html.Div(
                            [
                                html.Div("Wire Reconstructions / New", className="lp-form-breadcrumb"),
                                html.H2(id="wirerecon-title", children="New Wire Reconstruction"),
                            ]
                        ),
                        html.Div(
                            className="lp-form-actions",
                            children=[
                                dbc.Button(
                                    [html.I(className="bi bi-check2-circle me-1"), "Validate"],
                                    id="wirerecon-validate-btn",
                                    color="primary",
                                    outline=True,
                                ),
                                dbc.Button(
                                    [html.I(className="bi bi-send me-1"), "Submit"],
                                    id="submit_wire",
                                    color="success",
                                ),
                            ],
                        ),
                    ],
                ),
                html.Div(validation_alerts, className="lp-form-validation"),
                wire_recon_form,
                dcc.Store(id="wirerecon-data-loaded-signal"),
            ],
        )
    ],
    className="dbc px-0",
    fluid=True,
)


def validate_wire_reconstruction_inputs(ctx):
    """
    Validate specified wire reconstruction inputs using callback context.

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
    validation_result = {"errors": {}, "warnings": {}, "successes": {}}
    # Dictionary to store parsed field value lists
    parsed_fields = {}

    # Hard-coded list of field IDs to validate (excludes 'notes')
    all_field_ids = [
        "data_path",
        "filenamePrefix",
        "scanPoints",
        "geoFile",
        "depth_start",
        "depth_end",
        "depth_resolution",
        "percent_brightest",
        "outputFolder",
        "root_path",
        "IDnumber",  # Replaced scanNumber with IDnumber
        "author",
    ]

    # Optional parameters list - these fields are not required
    optional_params = [
        "scanNumber",
    ]

    # Create database session for catalog validation
    session = Session(session_utils.get_engine())

    # Extract field values from callback context using the hard-coded field list
    # ctx.states is a dict with format {'component_id.prop_name': value}
    all_fields = {}
    for key, value in ctx.states.items():
        # Extract component_id from 'component_id.prop_name'
        component_id = key.split(".")[0]
        # Only include fields in our validation list
        if component_id in all_field_ids:
            all_fields[component_id] = value

    # Determine num_inputs from longest semicolon-separated list across all fields
    num_inputs = get_num_inputs_from_fields(all_fields)

    # Extract individual field values
    root_path = all_fields.get("root_path", "")
    IDnumber = all_fields.get("IDnumber", "")

    # Validate root_path directory exists
    # Root path can be blank if ALL path fields (data_path, outputFolder, geoFile)
    # use absolute paths, since resolve_path_with_root ignores root_path for absolute paths.
    root_path_dependent_fields = ["data_path", "outputFolder", "geoFile"]
    if not root_path:
        if all_path_fields_are_absolute(all_fields, root_path_dependent_fields):
            # All path fields are absolute — root_path is not needed
            parsed_fields["root_path"] = root_path
            add_validation_message(
                validation_result,
                "successes",
                "root_path",
                custom_message="Root Path is blank but all path fields are absolute",
            )
        else:
            add_validation_message(
                validation_result,
                "errors",
                "root_path",
                custom_message="Root Path is required when any path field is relative",
            )
            # Add per-field warnings to highlight which fields need absolute paths
            field_display_names = {
                "data_path": "Data Path",
                "outputFolder": "Output Folder",
                "geoFile": "Geometry File",
            }
            for field_name in root_path_dependent_fields:
                raw_value = all_fields.get(field_name, "")
                if not raw_value:
                    continue  # Empty fields will get their own "required" error later
                values = [v.strip() for v in str(raw_value).split(";") if v.strip()]
                for val in values:
                    if not os.path.isabs(val):
                        display = field_display_names.get(field_name, field_name)
                        add_validation_message(
                            validation_result,
                            "warnings",
                            field_name,
                            custom_message=f"{display} is relative but Root Path is blank — use an absolute path",
                        )
                        break  # One warning per field is enough
    elif not os.path.exists(root_path):
        add_validation_message(validation_result, "errors", "root_path", custom_message="Root Path does not exist")
    else:
        parsed_fields["root_path"] = root_path
        add_validation_message(validation_result, "successes", "root_path")

    # Parse the canonical scan/reconstruction provenance shown by the form.
    parsed_fields["IDnumber"] = IDnumber

    if IDnumber:
        try:
            identities = parse_workflow_identities(IDnumber, session)
            scan_number = merged_identity_value(identities, "scan_number")
            if scan_number is not None:
                parsed_fields["scanNumber"] = parse_parameter(scan_number, num_inputs)
            add_validation_message(validation_result, "successes", "IDnumber")
        except ValueError as e:
            add_validation_message(
                validation_result, "errors", "IDnumber", custom_message=f"ID Number parsing error: {e}"
            )
    else:
        # IDnumber is optional - if not provided, show warning about unlinked reconstruction
        add_validation_message(
            validation_result,
            "warnings",
            "IDnumber",
            custom_message="No ID Number provided. This will create an unlinked wire reconstruction.",
        )

    # Validate all other fields by iterating over all_fields
    for field_name, field_value in all_fields.items():
        # Skip already handled fields
        if field_name in parsed_fields:
            continue
        # Check 1: Is it missing/empty?
        is_missing = False
        if field_name in ["depth_start", "depth_end", "depth_resolution", "percent_brightest"]:
            # Numeric fields: check for None or empty string (0 is valid)
            if field_value is None or field_value == "":
                is_missing = True
        else:
            # Other fields: check for falsy values
            if not field_value:
                is_missing = True

        if is_missing:
            # Special case for scanNumber: only warning, not error
            if field_name == "scanNumber":
                add_validation_message(validation_result, "warnings", field_name, display_name="Scan Number")
                continue  # Skip parsing
            else:
                add_validation_message(validation_result, "errors", field_name)
                continue  # Skip parsing if missing

        # Check 2: Parse the field value
        try:
            parsed_list = parse_parameter(field_value, num_inputs)
        except ValueError as e:
            # Special case for scanNumber: only warning, not error
            if field_name == "scanNumber":
                add_validation_message(
                    validation_result, "warnings", field_name, custom_message=f"Scan Number parsing error: {str(e)}"
                )
                continue  # Skip length check
            else:
                add_validation_message(
                    validation_result, "errors", field_name, custom_message=f"%s parsing error: {str(e)}"
                )
                continue  # Skip length check if parsing failed

        # Check 3: Verify length matches num_inputs
        if len(parsed_list) != num_inputs:
            # Special case for scanNumber: only warning, not error
            if field_name == "scanNumber":
                add_validation_message(
                    validation_result,
                    "warnings",
                    field_name,
                    custom_message=f"Scan Number count ({len(parsed_list)}) does not match number of inputs ({num_inputs})",
                )
            else:
                add_validation_message(
                    validation_result,
                    "errors",
                    field_name,
                    custom_message=f"%s count ({len(parsed_list)}) does not match number of inputs ({num_inputs})",
                )

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
                **kwargs,
            )

        return validate_for_input

    # Create the validator once before the loop
    validate_for_input = make_field_validator(validation_result, parsed_fields, optional_params)

    # Validate each input, skipping fields that failed global validation
    for i in range(num_inputs):
        input_prefix = f"Input {i + 1}: " if num_inputs > 1 else ""

        # Inner wrapper for this specific input
        def validate_field(field_name, _i=i, _input_prefix=input_prefix, **kwargs):
            return validate_for_input(field_name, _i, _input_prefix, **kwargs)

        # 1. Validate ID integers (scanNumber)
        # Convert scanNumber to integer if present
        scan_num_int = None
        if "scanNumber" in parsed_fields:
            current_scanNumber = validate_field("scanNumber", required=False, display_name="Scan Number")
            if current_scanNumber is not None:
                try:
                    scan_num_int = int(current_scanNumber)
                except (ValueError, TypeError):
                    add_validation_message(
                        validation_result,
                        "warnings",
                        "scanNumber",
                        input_prefix,
                        custom_message="Scan Number is not a valid integer",
                    )

        # 2. Check if data files exist for this input (skip if root_path or data_path invalid)
        if "root_path" not in validation_result["errors"] and "data_path" not in validation_result["errors"]:
            current_data_path = validate_field("data_path")
            if current_data_path is not None:
                # Warn if absolute path is being used (root_path will be ignored)
                if os.path.isabs(current_data_path):
                    add_validation_message(
                        validation_result,
                        "warnings",
                        "data_path",
                        input_prefix,
                        custom_message="Data Path is absolute - Root Path will be ignored",
                    )

                current_full_data_path = resolve_path_with_root(current_data_path, root_path)

                # Check if directory exists
                if not os.path.exists(current_full_data_path):
                    add_validation_message(
                        validation_result,
                        "errors",
                        "data_path",
                        input_prefix,
                        custom_message="Data Path directory not found",
                    )
                else:
                    # Validate against database if we have a valid scan number (uses ID validated above)
                    if scan_num_int is not None:
                        # Get catalog data for this scan
                        catalog_data = get_catalog_data(session, scan_num_int, root_path, CATALOG_DEFAULTS)

                        if catalog_data and catalog_data.get("data_path"):
                            catalog_full_data_path = resolve_path_with_root(catalog_data["data_path"], root_path)
                            if catalog_full_data_path != current_full_data_path:
                                add_validation_message(
                                    validation_result,
                                    "warnings",
                                    "data_path",
                                    input_prefix,
                                    custom_message=f"Catalog entry for Scan Number {scan_num_int} has different path ({catalog_data['data_path']})",
                                )
                        else:
                            # No catalog entry found for this scan number
                            add_validation_message(
                                validation_result,
                                "warnings",
                                "scanNumber",
                                input_prefix,
                                custom_message=f"Catalog entry not found for Scan Number {scan_num_int}",
                            )

                    with os.scandir(current_full_data_path) as entries:
                        contains_file = any(entry.is_file() for entry in entries)
                    if not contains_file:
                        add_validation_message(
                            validation_result,
                            "errors",
                            "data_path",
                            input_prefix,
                            custom_message="Data Path directory contains no files",
                        )

                    current_filename_prefix_str = validate_field("filenamePrefix", display_name="Filename Prefix")
                    if current_filename_prefix_str is not None:
                        for prefix in (
                            value.strip() for value in str(current_filename_prefix_str).split(",") if value.strip()
                        ):
                            if prefix.count("%d") > 1:
                                add_validation_message(
                                    validation_result,
                                    "errors",
                                    "filenamePrefix",
                                    input_prefix,
                                    custom_message=(f"Filename prefix '{prefix}' has more than one %d placeholder"),
                                )

                    current_scan_points = validate_field("scanPoints", display_name="Scan Points", required=False)
                    if current_scan_points:
                        try:
                            if srange(current_scan_points).len() == 0:
                                raise ValueError
                        except Exception:
                            add_validation_message(
                                validation_result,
                                "errors",
                                "scanPoints",
                                input_prefix,
                                custom_message="Scan Points entry has invalid or empty range",
                            )

        # 3. Check if output folder already exists for this input (skip if root_path invalid)
        # Note: We cannot validate this properly if outputFolder contains %d placeholders
        # because the database-assigned reconstruction ID is not known yet.
        # This check is skipped if %d is present in the path.
        current_outputFolder = validate_field("outputFolder", display_name="Output Folder")
        if current_outputFolder is not None:
            if "root_path" not in validation_result["errors"]:
                # Warn if absolute path is being used (root_path will be ignored)
                if os.path.isabs(current_outputFolder):
                    add_validation_message(
                        validation_result,
                        "warnings",
                        "outputFolder",
                        input_prefix,
                        custom_message="Output Folder is absolute - Root Path will be ignored",
                    )

                if "%d" not in current_outputFolder:
                    full_output_path = resolve_path_with_root(current_outputFolder, root_path)
                    if os.path.exists(full_output_path):
                        add_validation_message(
                            validation_result,
                            "warnings",
                            "outputFolder",
                            input_prefix,
                            custom_message="Output Folder already exists",
                        )

        # 4. Check if geometry file exists for this input (skip if root_path invalid)
        current_geoFile = validate_field("geoFile", display_name="Geometry File")
        if current_geoFile is not None:
            if "root_path" not in validation_result["errors"]:
                # Warn if absolute path is being used (root_path will be ignored)
                if os.path.isabs(current_geoFile):
                    add_validation_message(
                        validation_result,
                        "warnings",
                        "geoFile",
                        input_prefix,
                        custom_message="Geometry File is absolute - Root Path will be ignored",
                    )

                full_geo_path = resolve_path_with_root(current_geoFile, root_path)
                if not os.path.exists(full_geo_path):
                    add_validation_message(
                        validation_result, "errors", "geoFile", input_prefix, custom_message="Geometry File not found"
                    )

        # 5. Validate depth parameters for this input using the universal helper
        depth_start_val = validate_field("depth_start", converter=safe_float)

        depth_end_val = validate_field("depth_end", converter=safe_float)

        depth_resolution_val = validate_field("depth_resolution", converter=safe_float)

        # Initialize depth_span as None (will be calculated if both start and end are valid)
        depth_span = None

        # Check start < end (only if both values are valid)
        if depth_start_val is not None and depth_end_val is not None:
            if depth_start_val >= depth_end_val:
                add_validation_message(
                    validation_result,
                    "errors",
                    "depth_start",
                    input_prefix,
                    custom_message="Depth Start must be less than Depth End",
                )
                add_validation_message(
                    validation_result,
                    "errors",
                    "depth_end",
                    input_prefix,
                    custom_message="Depth Start must be less than Depth End",
                )

            # Calculate depth_span once (used in multiple checks below)
            depth_span = depth_end_val - depth_start_val

            # Warning: large depth range
            if depth_span > 500:
                add_validation_message(
                    validation_result,
                    "warnings",
                    "depth_start",
                    input_prefix,
                    custom_message=f"Total depth range ({depth_span} µm) is large (> 500 µm)",
                )
                add_validation_message(
                    validation_result,
                    "warnings",
                    "depth_end",
                    input_prefix,
                    custom_message=f"Total depth range ({depth_span} µm) is large (> 500 µm)",
                )

        # Check resolution value (only needs depth_resolution to be valid)
        if depth_resolution_val is not None:
            # Error: resolution must be positive
            if depth_resolution_val <= 0:
                add_validation_message(
                    validation_result,
                    "errors",
                    "depth_resolution",
                    input_prefix,
                    custom_message="Depth Resolution must be positive",
                )
            # Warning: resolution too small
            elif depth_resolution_val < 0.1:
                add_validation_message(
                    validation_result,
                    "warnings",
                    "depth_resolution",
                    input_prefix,
                    custom_message=f"Depth Resolution ({depth_resolution_val} µm) is very small (< 0.1 µm)",
                )

            # Check resolution < range (needs ALL THREE to be valid, and no prior errors on depth_resolution)
            if "depth_resolution" not in validation_result["errors"]:
                if depth_span is not None:
                    # Check if resolution is less than range
                    if depth_resolution_val > abs(depth_span):
                        add_validation_message(
                            validation_result,
                            "errors",
                            "depth_start",
                            input_prefix,
                            custom_message=f"Depth Start: resolution ({depth_resolution_val} µm) must be ≤ depth range ({abs(depth_span)} µm)",
                        )
                        add_validation_message(
                            validation_result,
                            "errors",
                            "depth_end",
                            input_prefix,
                            custom_message=f"Depth End: resolution ({depth_resolution_val} µm) must be ≤ depth range ({abs(depth_span)} µm)",
                        )
                        add_validation_message(
                            validation_result,
                            "errors",
                            "depth_resolution",
                            input_prefix,
                            custom_message=f"Depth Resolution ({depth_resolution_val} µm) must be ≤ depth range ({abs(depth_span)} µm)",
                        )

        # 6. Validate percent_brightest for this input
        percent_val = validate_field("percent_brightest", converter=safe_float, display_name="Intensity Percentile")
        if percent_val is not None:
            if percent_val <= 0 or percent_val > 100:
                add_validation_message(
                    validation_result,
                    "errors",
                    "percent_brightest",
                    input_prefix,
                    custom_message="Intensity Percentile must be between 0 and 100",
                )

    # Add successes for fields that passed all validations
    # Only add to successes if the field has neither errors nor warnings
    for field_name in all_field_ids:
        if field_name not in validation_result["errors"] and field_name not in validation_result["warnings"]:
            add_validation_message(validation_result, "successes", field_name)

    # Close database session
    session.close()

    return validation_result


@dash.callback(
    Input("wirerecon-validate-btn", "n_clicks"),
    State("data_path", "value"),
    State("filenamePrefix", "value"),
    State("scanPoints", "value"),
    State("geoFile", "value"),
    State("depth_start", "value"),
    State("depth_end", "value"),
    State("depth_resolution", "value"),
    State("percent_brightest", "value"),
    State("outputFolder", "value"),
    State("root_path", "value"),
    State("IDnumber", "value"),
    State("author", "value"),
    running=[
        (Output("wirerecon-validate-btn", "disabled"), True, False),
        (
            Output("wirerecon-validate-btn", "children"),
            [dbc.Spinner(size="sm", spinner_class_name="me-2"), "Validating..."],
            "Validate",
        ),
        (Output("submit_wire", "disabled"), True, False),
    ],
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
    IDnumber,
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
    Input("submit_wire", "n_clicks"),
    State("root_path", "value"),
    State("IDnumber", "value"),
    # User text
    State("author", "value"),
    State("notes", "value"),
    # Recon constraints
    State("geoFile", "value"),
    State("percent_brightest", "value"),
    State("wire_edges", "value"),
    # Depth parameters
    State("depth_start", "value"),
    State("depth_end", "value"),
    State("depth_resolution", "value"),
    # Files
    State("scanPoints", "value"),
    State("data_path", "value"),
    State("filenamePrefix", "value"),
    # Output
    State("outputFolder", "value"),
    running=[
        (Output("submit_wire", "disabled"), True, False),
        (
            Output("submit_wire", "children"),
            [dbc.Spinner(size="sm", spinner_class_name="me-2"), "Submitting..."],
            "Submit",
        ),
        (Output("wirerecon-validate-btn", "disabled"), True, False),
    ],
    prevent_initial_call=True,
)
def submit_parameters(
    n,
    root_path,
    IDnumber,
    author,
    notes,
    geometry_file,
    percent_brightest,
    wire_edges,
    depth_start,
    depth_end,
    depth_resolution,
    scanPoints,
    data_path,
    filenamePrefix,
    output_folder,
):
    """Create and enqueue each pooled wire reconstruction independently."""

    ctx = dash.callback_context
    validation_result = validate_wire_reconstruction_inputs(ctx)
    apply_validation_highlights(validation_result)
    update_validation_alerts(validation_result)
    if validation_result["errors"]:
        set_props(
            "alert-submit",
            {
                "is_open": True,
                "children": "Submission blocked due to validation errors. Please fix the errors and try again.",
                "color": "danger",
            },
        )
        return

    with Session(session_utils.get_engine()) as session:
        try:
            identities = parse_workflow_identities(IDnumber, session)
        except ValueError as error:
            set_props(
                "alert-submit",
                {"is_open": True, "children": f"Invalid ID Number: {error}", "color": "danger"},
            )
            return

    all_submit_params = {key.split(".")[0]: value for key, value in ctx.states.items()}
    all_submit_params["identity_count"] = ";".join(str(index) for index in range(len(identities)))
    num_inputs = get_num_inputs_from_fields(all_submit_params)
    if len(identities) == 1:
        identities *= num_inputs
    elif len(identities) != num_inputs:
        set_props(
            "alert-submit",
            {
                "is_open": True,
                "children": f"ID Number count ({len(identities)}) does not match pooled input count ({num_inputs}).",
                "color": "danger",
            },
        )
        return

    try:
        author_list = parse_parameter(author, num_inputs)
        notes_list = parse_parameter(notes, num_inputs)
        geometry_files = parse_parameter(geometry_file, num_inputs)
        percent_values = parse_parameter(percent_brightest, num_inputs)
        edge_values = parse_parameter(wire_edges, num_inputs)
        depth_starts = parse_parameter(depth_start, num_inputs)
        depth_ends = parse_parameter(depth_end, num_inputs)
        depth_resolutions = parse_parameter(depth_resolution, num_inputs)
        scan_points = parse_parameter(scanPoints, num_inputs)
        data_paths = parse_parameter(data_path, num_inputs)
        filename_prefixes = parse_parameter(filenamePrefix, num_inputs)
        output_templates = parse_parameter(output_folder, num_inputs)
    except ValueError as error:
        set_props("alert-submit", {"is_open": True, "children": str(error), "color": "danger"})
        return

    submitted = []
    failures = []
    for index, identity in enumerate(identities):
        run = None
        try:
            prefixes = [value.strip() for value in str(filename_prefixes[index]).split(",") if value.strip()]
            request = WireReconstructionRequest(
                scan_number=identity.scan_number,
                input_path=resolve_path_with_root(data_paths[index], root_path),
                output_path_template=resolve_path_with_root(output_templates[index], root_path),
                filename_prefixes=prefixes,
                geometry_file=resolve_path_with_root(geometry_files[index], root_path),
                percent_brightest=float(percent_values[index]),
                wire_edges=str(edge_values[index]),
                depth_start=float(depth_starts[index]),
                depth_end=float(depth_ends[index]),
                depth_resolution=float(depth_resolutions[index]),
                num_threads=int(DEFAULT_VARIABLES["num_threads"]),
                memory_limit_mb=int(DEFAULT_VARIABLES["memory_limit_mb"]),
                scan_points=str(scan_points[index]),
                verbose=int(DEFAULT_VARIABLES["verbose"]),
                author=author_list[index],
                notes=notes_list[index],
            )
            run = create_reconstruction(request)
            enqueue_reconstruction(run.id)
            submitted.append(f"R{run.id}")
        except Exception as error:
            label = f"R{run.id}" if run is not None else (f"input {index + 1}" if num_inputs > 1 else "submission")
            logger.exception("Wire reconstruction %s failed", label)
            failures.append(f"{label}: {error}")

    if submitted and not failures:
        message = f"Submitted {', '.join(submitted)} to the queue."
        color = "success"
    elif submitted:
        message = f"Submitted {', '.join(submitted)}. Failed: {'; '.join(failures)}"
        color = "warning"
    else:
        message = f"Submission failed: {'; '.join(failures)}"
        color = "danger"

    set_props("alert-submit", {"is_open": True, "children": message, "color": color})


@dash.callback(
    Output("depth_start", "value"),
    Output("depth_end", "value"),
    Output("depth_resolution", "value"),
    Output("wire_edges", "value"),
    Output("percent_brightest", "value"),
    Input("wirerecon-set-default-parameters-btn", "n_clicks"),
    prevent_initial_call=True,
)
def set_wire_recon_defaults(n_clicks):
    if not n_clicks:
        raise PreventUpdate
    return (
        WIRERECON_DEFAULTS.get("depth_start"),
        WIRERECON_DEFAULTS.get("depth_end"),
        WIRERECON_DEFAULTS.get("depth_resolution"),
        WIRERECON_DEFAULTS.get("wire_edges"),
        WIRERECON_DEFAULTS.get("percent_brightest"),
    )


# Register shared callbacks
register_update_path_fields_callback(
    update_paths_id="wirerecon-update-path-fields-btn",
    # scan_number_id='scanNumber',
    id_number_id="IDnumber",
    root_path_id="root_path",
    data_path_id="data_path",
    filename_prefix_id="filenamePrefix",
    alert_id="alert-scan-loaded",
    catalog_defaults=CATALOG_DEFAULTS,
    output_folder_id="outputFolder",
    build_template_func=build_output_folder_template,
    context="wire_recon",
)

register_load_file_indices_callback(
    button_id="wirerecon-load-file-indices-btn",
    data_loaded_signal_id="wirerecon-data-loaded-signal",
    data_path_id="data_path",
    filename_prefix_id="filenamePrefix",
    scan_points_id="scanPoints",
    depth_range_id=None,  # Wire recon doesn't use depth range
    alert_id="alert-scan-loaded",
    num_indices=1,
)

register_check_filenames_callback(
    find_filenames_id="wirerecon-check-filenames-btn",
    data_path_id="data_path",
    filename_prefix_id="filenamePrefix",
    filename_templates_id="wirerecon-filename-templates",
    root_path_id="root_path",
    num_indices=1,
    scan_points_id="scanPoints",
)


def _query_id_list(raw_value):
    if raw_value is None:
        return []
    return [int(value) if value and value.lower() != "none" else None for value in raw_value.split(",")]


def _identity_label(scan_number=None, reconstruction_id=None):
    parts = []
    if scan_number is not None:
        parts.append(f"SN{scan_number}")
    if reconstruction_id is not None:
        parts.append(f"R{reconstruction_id}")
    return " | ".join(parts)


@dash.callback(
    Output("wirerecon-data-loaded-signal", "data"),
    Input("url-create-wirerecon", "href"),
    prevent_initial_call=True,
)
def load_scan_data_from_url(href):
    """Load scan or reconstruction source values into the wire create form."""

    if not href:
        raise PreventUpdate

    query = urllib.parse.parse_qs(urllib.parse.urlparse(href).query, keep_blank_values=True)
    scan_ids = _query_id_list(query.get("scan_id", [None])[0])
    reconstruction_ids = _query_id_list(query.get("reconstruction_id", [None])[0])
    item_count = max(len(scan_ids), len(reconstruction_ids), 1)

    if scan_ids and len(scan_ids) not in (1, item_count):
        raise ValueError("Scan and reconstruction URL counts do not match")
    if reconstruction_ids and len(reconstruction_ids) not in (1, item_count):
        raise ValueError("Scan and reconstruction URL counts do not match")
    if len(scan_ids) == 1 and item_count > 1:
        scan_ids *= item_count
    if len(reconstruction_ids) == 1 and item_count > 1:
        reconstruction_ids *= item_count
    scan_ids = scan_ids or [None] * item_count
    reconstruction_ids = reconstruction_ids or [None] * item_count

    root_path = DEFAULT_VARIABLES.get("root_path", "")
    form_rows = []
    labels = []
    failures = []

    with Session(session_utils.get_engine()) as session:
        for scan_number, reconstruction_id in zip(scan_ids, reconstruction_ids, strict=True):
            try:
                if reconstruction_id is not None:
                    run = get_reconstruction(reconstruction_id)
                    if run is None or run.method != "wire":
                        raise ValueError(f"Wire reconstruction R{reconstruction_id} was not found")
                    if scan_number is not None and run.scan_number is not None and scan_number != run.scan_number:
                        raise ValueError(f"SN{scan_number} does not match reconstruction R{reconstruction_id}")
                    form_data = _copy_reconstruction_for_form(run, root_path)
                    scan_number = scan_number if scan_number is not None else run.scan_number
                    form_data.scan_number = scan_number
                else:
                    form_data = create_default_wirerecon(
                        {
                            "scan_number": scan_number,
                            "output_path_template": build_output_folder_template(scan_number, None),
                        }
                    )
                    if scan_number is not None:
                        metadata = session.get(db_schema.Metadata, scan_number)
                        if metadata is None:
                            raise ValueError(f"Scan SN{scan_number} was not found")
                        catalog = get_catalog_by_scan_number(session, scan_number)
                        if catalog is not None:
                            form_data.data_path = remove_root_path_prefix(catalog.filefolder, root_path)
                            form_data.input_path = catalog.filefolder
                            form_data.filename_prefixes = catalog.filenamePrefix

                form_data.identity_value = _identity_label(scan_number, reconstruction_id)
                form_rows.append(form_data)
                labels.append(form_data.identity_value or "unlinked input")
            except Exception as error:
                failures.append(str(error))

    if not form_rows:
        set_wire_recon_form_props(create_default_wirerecon())
        if failures:
            set_props(
                "alert-scan-loaded",
                {"is_open": True, "children": "; ".join(failures), "color": "danger"},
            )
        return datetime.datetime.now().isoformat()

    if len(form_rows) == 1:
        pooled = form_rows[0]
    else:
        merge_fields = [
            "root_path",
            "data_path",
            "filename_prefixes",
            "author",
            "notes",
            "geometry_file",
            "percent_brightest",
            "wire_edges",
            "depth_start",
            "depth_end",
            "depth_resolution",
            "num_threads",
            "memory_limit_mb",
            "scan_points",
            "output_path_template",
            "verbose",
        ]
        pooled = create_default_wirerecon()
        for field in merge_fields:
            setattr(pooled, field, _merge_field_values([getattr(row, field) for row in form_rows]))
        pooled.identity_value = "; ".join(row.identity_value for row in form_rows)

    pooled.author = DEFAULT_VARIABLES.get("author", "")
    pooled.notes = DEFAULT_VARIABLES.get("notes", "")
    set_wire_recon_form_props(pooled)
    color = "warning" if failures else "success"
    message = f"Loaded {', '.join(labels)}."
    if failures:
        message += f" Could not load: {'; '.join(failures)}"
    set_props("alert-scan-loaded", {"is_open": True, "children": message, "color": color})

    if any(reconstruction_id is not None for reconstruction_id in reconstruction_ids):
        return dash.no_update
    return datetime.datetime.now().isoformat()
