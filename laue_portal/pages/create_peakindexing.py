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
from laue_portal.components.peakindex_form import peakindex_form, set_peakindex_form_props
from laue_portal.components.validation_alerts import (
    apply_validation_highlights,
    update_validation_alerts,
    validation_alerts,
)
from laue_portal.config import DEFAULT_VARIABLES, PEAKINDEX_DEFAULTS
from laue_portal.database.db_utils import (
    parse_parameter,
    remove_root_path_prefix,
    resolve_path_with_root,
)
from laue_portal.pages.callback_registrars import (
    _merge_field_values,
    register_check_filenames_callback,
    register_find_indices_callback,
    register_update_path_fields_callback,
)
from laue_portal.processing.queue.enqueue import enqueue_indexing
from laue_portal.services.validation import (
    PEAKINDEX_FIELD_IDS,
    effective_data_path,
    get_num_inputs_from_fields,
    validate_peakindexing,
)
from laue_portal.utilities.hkl_parse import str2hkl
from laue_portal.workflows.identity import parse_workflow_identities
from laue_portal.workflows.indexing import LaueGoIndexingRequest, create_indexing, get_indexing
from laue_portal.workflows.reconstruction import get_reconstruction

logger = logging.getLogger(__name__)


def build_output_folder_template(scan_num_int, data_path, reconstruction_id_int=None):
    """
    Build output folder template based on available IDs from database chain.
    Only the final action ID remains as %d.

    Parameters:
    - scan_num_int: scanNumber (int or None)
    - data_path: data path to use if scanNumber unknown
    - root_path: root path
    - reconstruction_id_int: parent reconstruction ID (int or None)

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

    if reconstruction_id_int is not None:
        path_parts.append(f"rec_{reconstruction_id_int}")

    # Add final action placeholder for peakindexing
    path_parts.append("index_%d")

    return os.path.join(*path_parts)


def create_default_peakindex(overrides=None):
    """Return form data using canonical indexing field names."""
    defaults = {
        "id": None,
        "scan_number": None,
        "reconstruction_id": None,
        "root_path": DEFAULT_VARIABLES.get("root_path", ""),
        "data_path": "",
        "input_path": "",
        "filename_prefixes": [],
        "author": DEFAULT_VARIABLES.get("author", ""),
        "notes": DEFAULT_VARIABLES.get("notes", ""),
        "threshold": PEAKINDEX_DEFAULTS.get("threshold"),
        "threshold_ratio": PEAKINDEX_DEFAULTS.get("thresholdRatio"),
        "max_rfactor": PEAKINDEX_DEFAULTS.get("maxRfactor"),
        "box_size": PEAKINDEX_DEFAULTS.get("boxsize"),
        "max_number": PEAKINDEX_DEFAULTS.get("max_number"),
        "min_separation": PEAKINDEX_DEFAULTS.get("min_separation"),
        "peak_shape": PEAKINDEX_DEFAULTS.get("peakShape"),
        "min_size": PEAKINDEX_DEFAULTS.get("min_size"),
        "max_peaks": PEAKINDEX_DEFAULTS.get("max_peaks"),
        "smooth": PEAKINDEX_DEFAULTS.get("smooth"),
        "cosmic_filter": PEAKINDEX_DEFAULTS.get("cosmicFilter"),
        "mask_file": PEAKINDEX_DEFAULTS.get("maskFile"),
        "index_kev_max_calc": PEAKINDEX_DEFAULTS.get("indexKeVmaxCalc"),
        "index_kev_max_test": PEAKINDEX_DEFAULTS.get("indexKeVmaxTest"),
        "index_angle_tolerance": PEAKINDEX_DEFAULTS.get("indexAngleTolerance"),
        "index_h": PEAKINDEX_DEFAULTS.get("indexH"),
        "index_k": PEAKINDEX_DEFAULTS.get("indexK"),
        "index_l": PEAKINDEX_DEFAULTS.get("indexL"),
        "index_cone": PEAKINDEX_DEFAULTS.get("indexCone"),
        "detector_crop_x1": PEAKINDEX_DEFAULTS.get("detectorCropX1"),
        "detector_crop_x2": PEAKINDEX_DEFAULTS.get("detectorCropX2"),
        "detector_crop_y1": PEAKINDEX_DEFAULTS.get("detectorCropY1"),
        "detector_crop_y2": PEAKINDEX_DEFAULTS.get("detectorCropY2"),
        "energy_unit": PEAKINDEX_DEFAULTS.get("energyUnit"),
        "exposure_unit": PEAKINDEX_DEFAULTS.get("exposureUnit"),
        "reciprocal_lattice_unit": PEAKINDEX_DEFAULTS.get("recipLatticeUnit"),
        "lattice_parameters_unit": PEAKINDEX_DEFAULTS.get("latticeParametersUnit"),
        "output_path_template": build_output_folder_template(None, None),
        "output_xml": PEAKINDEX_DEFAULTS.get("outputXML", "output.xml"),
        "geometry_file": PEAKINDEX_DEFAULTS.get("geoFile"),
        "crystal_file": PEAKINDEX_DEFAULTS.get("crystFile"),
        "beamline": PEAKINDEX_DEFAULTS.get("beamline"),
        "depth": PEAKINDEX_DEFAULTS.get("depth"),
        "scan_points": PEAKINDEX_DEFAULTS.get("scanPoints", ""),
        "depth_range": PEAKINDEX_DEFAULTS.get("depthRange", ""),
    }
    if overrides:
        defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _copy_indexing_for_form(run, root_path):
    parameters = run.lauego_parameters
    if parameters is None:
        raise ValueError(f"Indexing I{run.id} has no LaueGo parameters")
    values = {
        "id": run.id,
        "scan_number": run.scan_number,
        "reconstruction_id": run.reconstruction_id,
        "root_path": root_path,
        "data_path": remove_root_path_prefix(run.input_path, root_path),
        "input_path": run.input_path,
        "output_path_template": build_output_folder_template(run.scan_number, run.input_path, run.reconstruction_id),
        "author": DEFAULT_VARIABLES.get("author", ""),
        "notes": DEFAULT_VARIABLES.get("notes", ""),
    }
    for field in (
        "filename_prefixes",
        "threshold",
        "threshold_ratio",
        "max_rfactor",
        "box_size",
        "max_number",
        "min_separation",
        "peak_shape",
        "scan_points",
        "depth_range",
        "detector_crop_x1",
        "detector_crop_x2",
        "detector_crop_y1",
        "detector_crop_y2",
        "min_size",
        "max_peaks",
        "smooth",
        "mask_file",
        "index_kev_max_calc",
        "index_kev_max_test",
        "index_angle_tolerance",
        "index_h",
        "index_k",
        "index_l",
        "index_cone",
        "energy_unit",
        "exposure_unit",
        "cosmic_filter",
        "reciprocal_lattice_unit",
        "lattice_parameters_unit",
        "output_xml",
        "geometry_file",
        "crystal_file",
        "depth",
        "beamline",
    ):
        values[field] = getattr(parameters, field)
    values["geometry_file"] = remove_root_path_prefix(values["geometry_file"], root_path)
    values["crystal_file"] = remove_root_path_prefix(values["crystal_file"], root_path)
    if values["mask_file"]:
        values["mask_file"] = remove_root_path_prefix(values["mask_file"], root_path)
    return create_default_peakindex(values)


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
                html.Div(
                    className="lp-form-masthead",
                    children=[
                        html.Div(
                            [
                                html.Div("Indexations / New", className="lp-form-breadcrumb"),
                                html.H2(id="peakindex-title", children="New Peak Indexing"),
                            ]
                        ),
                        html.Div(
                            className="lp-form-actions",
                            children=[
                                dbc.Button(
                                    [html.I(className="bi bi-check2-circle me-1"), "Validate"],
                                    id="peakindex-validate-btn",
                                    color="primary",
                                    outline=True,
                                ),
                                dbc.Button(
                                    [html.I(className="bi bi-send me-1"), "Submit"],
                                    id="submit_peakindexing",
                                    color="success",
                                ),
                            ],
                        ),
                    ],
                ),
                html.Div(validation_alerts, className="lp-form-validation"),
                peakindex_form,
                dcc.Store(id="peakindex-data-loaded-signal"),
            ],
        )
    ],
    className="dbc px-0",
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


def _as_bool(value):
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


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
    """Create and enqueue each pooled LaueGo indexing run independently."""

    ctx = dash.callback_context
    validation_result = validate_peakindexing_inputs(ctx)
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
        fields = {
            "author": parse_parameter(author, num_inputs),
            "notes": parse_parameter(notes, num_inputs),
            "threshold": parse_parameter(threshold, num_inputs),
            "threshold_ratio": parse_parameter(thresholdRatio, num_inputs),
            "max_rfactor": parse_parameter(maxRfactor, num_inputs),
            "box_size": parse_parameter(boxsize, num_inputs),
            "max_number": parse_parameter(max_number, num_inputs),
            "min_separation": parse_parameter(min_separation, num_inputs),
            "peak_shape": parse_parameter(peakShape, num_inputs),
            "scan_points": parse_parameter(scanPoints, num_inputs),
            "depth_range": parse_parameter(depthRange, num_inputs),
            "min_size": parse_parameter(min_size, num_inputs),
            "max_peaks": parse_parameter(max_peaks or PEAKINDEX_DEFAULTS["max_peaks"], num_inputs),
            "smooth": parse_parameter(False if smooth is None else smooth, num_inputs),
            "mask_file": parse_parameter(maskFile, num_inputs),
            "index_kev_max_calc": parse_parameter(indexKeVmaxCalc, num_inputs),
            "index_kev_max_test": parse_parameter(indexKeVmaxTest, num_inputs),
            "index_angle_tolerance": parse_parameter(indexAngleTolerance, num_inputs),
            "index_hkl": parse_parameter(indexHKL, num_inputs),
            "index_cone": parse_parameter(indexCone, num_inputs),
            "cosmic_filter": parse_parameter(False if cosmicFilter is None else cosmicFilter, num_inputs),
            "data_path": parse_parameter(data_path, num_inputs),
            "filename_prefixes": parse_parameter(filenamePrefix, num_inputs),
            "output_path_template": parse_parameter(outputFolder, num_inputs),
            "geometry_file": parse_parameter(geometry_file, num_inputs),
            "crystal_file": parse_parameter(crystal_file, num_inputs),
            "depth": parse_parameter(depth, num_inputs),
            "output_xml": parse_parameter(outputXML or PEAKINDEX_DEFAULTS["outputXML"], num_inputs),
        }
    except ValueError as error:
        set_props("alert-submit", {"is_open": True, "children": str(error), "color": "danger"})
        return

    submitted = []
    failures = []
    for index, identity in enumerate(identities):
        run = None
        try:
            hkl = str2hkl(str(fields["index_hkl"][index]), Nmin=3, Nmax=3)
            prefixes = [value.strip() for value in str(fields["filename_prefixes"][index]).split(",") if value.strip()]
            mask_file = fields["mask_file"][index]
            if mask_file is not None and str(mask_file).strip().lower() in ("", "none"):
                mask_file = None
            request = LaueGoIndexingRequest(
                scan_number=identity.scan_number,
                reconstruction_id=identity.reconstruction_id,
                input_path=effective_data_path(fields["data_path"][index], root_path),
                output_path_template=resolve_path_with_root(fields["output_path_template"][index], root_path),
                filename_prefixes=prefixes,
                threshold=int(fields["threshold"][index]) if fields["threshold"][index] not in (None, "") else None,
                threshold_ratio=(
                    int(fields["threshold_ratio"][index])
                    if fields["threshold_ratio"][index] not in (None, "")
                    else None
                ),
                max_rfactor=float(fields["max_rfactor"][index]),
                box_size=int(fields["box_size"][index]),
                max_number=int(fields["max_number"][index]),
                min_separation=int(fields["min_separation"][index]),
                peak_shape=str(fields["peak_shape"][index]),
                scan_points=str(fields["scan_points"][index]),
                depth_range=str(fields["depth_range"][index]) if fields["depth_range"][index] else None,
                detector_crop_x1=int(PEAKINDEX_DEFAULTS["detectorCropX1"]),
                detector_crop_x2=int(PEAKINDEX_DEFAULTS["detectorCropX2"]),
                detector_crop_y1=int(PEAKINDEX_DEFAULTS["detectorCropY1"]),
                detector_crop_y2=int(PEAKINDEX_DEFAULTS["detectorCropY2"]),
                min_size=float(fields["min_size"][index]),
                max_peaks=int(fields["max_peaks"][index]),
                smooth=_as_bool(fields["smooth"][index]),
                mask_file=resolve_path_with_root(mask_file, root_path) if mask_file else None,
                index_kev_max_calc=float(fields["index_kev_max_calc"][index]),
                index_kev_max_test=float(fields["index_kev_max_test"][index]),
                index_angle_tolerance=float(fields["index_angle_tolerance"][index]),
                index_h=int(hkl[0]),
                index_k=int(hkl[1]),
                index_l=int(hkl[2]),
                index_cone=float(fields["index_cone"][index]),
                energy_unit=PEAKINDEX_DEFAULTS["energyUnit"],
                exposure_unit=PEAKINDEX_DEFAULTS["exposureUnit"],
                cosmic_filter=_as_bool(fields["cosmic_filter"][index]),
                reciprocal_lattice_unit=PEAKINDEX_DEFAULTS["recipLatticeUnit"],
                lattice_parameters_unit=PEAKINDEX_DEFAULTS["latticeParametersUnit"],
                output_xml=fields["output_xml"][index],
                geometry_file=resolve_path_with_root(fields["geometry_file"][index], root_path),
                crystal_file=resolve_path_with_root(fields["crystal_file"][index], root_path),
                depth=fields["depth"][index],
                beamline=PEAKINDEX_DEFAULTS["beamline"],
                author=fields["author"][index],
                notes=fields["notes"][index],
            )
            run = create_indexing(request)
            enqueue_indexing(run.id)
            submitted.append(f"I{run.id}")
        except Exception as error:
            label = f"I{run.id}" if run is not None else (f"input {index + 1}" if num_inputs > 1 else "submission")
            logger.exception("LaueGo indexing %s failed", label)
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
    Output("boxsize", "value"),
    Output("maxRfactor", "value"),
    Output("threshold", "value"),
    Output("thresholdRatio", "value"),
    Output("min_size", "value"),
    Output("min_separation", "value"),
    Output("max_number", "value"),
    Output("peakShape", "value"),
    Output("smooth", "value"),
    Output("cosmicFilter", "value"),
    Input("peakindex-set-default-peak-search-btn", "n_clicks"),
    prevent_initial_call=True,
)
def set_peak_search_defaults(n_clicks):
    if not n_clicks:
        raise PreventUpdate
    return (
        PEAKINDEX_DEFAULTS.get("boxsize"),
        PEAKINDEX_DEFAULTS.get("maxRfactor"),
        PEAKINDEX_DEFAULTS.get("threshold"),
        PEAKINDEX_DEFAULTS.get("thresholdRatio"),
        PEAKINDEX_DEFAULTS.get("min_size"),
        PEAKINDEX_DEFAULTS.get("min_separation"),
        PEAKINDEX_DEFAULTS.get("max_number"),
        PEAKINDEX_DEFAULTS.get("peakShape"),
        PEAKINDEX_DEFAULTS.get("smooth"),
        PEAKINDEX_DEFAULTS.get("cosmicFilter"),
    )


@dash.callback(
    Output("indexKeVmaxCalc", "value"),
    Output("indexKeVmaxTest", "value"),
    Output("indexAngleTolerance", "value"),
    Output("indexHKL", "value"),
    Output("indexCone", "value"),
    Output("max_peaks", "value"),
    Output("depth", "value"),
    Input("peakindex-set-default-indexing-btn", "n_clicks"),
    prevent_initial_call=True,
)
def set_indexing_defaults(n_clicks):
    if not n_clicks:
        raise PreventUpdate
    return (
        PEAKINDEX_DEFAULTS.get("indexKeVmaxCalc"),
        PEAKINDEX_DEFAULTS.get("indexKeVmaxTest"),
        PEAKINDEX_DEFAULTS.get("indexAngleTolerance"),
        "".join(
            str(value)
            for value in [
                PEAKINDEX_DEFAULTS.get("indexH"),
                PEAKINDEX_DEFAULTS.get("indexK"),
                PEAKINDEX_DEFAULTS.get("indexL"),
            ]
            if value is not None
        ),
        PEAKINDEX_DEFAULTS.get("indexCone"),
        PEAKINDEX_DEFAULTS.get("max_peaks"),
        PEAKINDEX_DEFAULTS.get("depth"),
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

register_find_indices_callback(
    button_id="peakindex-find-indices-btn",
    data_path_id="data_path",
    filename_prefix_id="filenamePrefix",
    scan_points_id="scanPoints",
    root_path_id="root_path",
    num_indices=2,
    depth_range_id="depthRange",
)


def _query_id_list(raw_value):
    if raw_value is None:
        return []
    return [int(value) if value and value.lower() != "none" else None for value in raw_value.split(",")]


def _identity_label(scan_number=None, reconstruction_id=None, indexing_id=None):
    parts = []
    if scan_number is not None:
        parts.append(f"SN{scan_number}")
    if reconstruction_id is not None:
        parts.append(f"R{reconstruction_id}")
    if indexing_id is not None:
        parts.append(f"I{indexing_id}")
    return " | ".join(parts)


@dash.callback(
    Output("peakindex-data-loaded-signal", "data"),
    Input("url-create-peakindexing", "href"),
    prevent_initial_call=True,
)
def load_scan_data_from_url(href):
    """Load scan, reconstruction, or indexing source values into the form."""

    if not href:
        raise PreventUpdate

    query = urllib.parse.parse_qs(urllib.parse.urlparse(href).query, keep_blank_values=True)
    scan_ids = _query_id_list(query.get("scan_id", [None])[0])
    reconstruction_ids = _query_id_list(query.get("reconstruction_id", [None])[0])
    indexing_ids = _query_id_list(query.get("indexing_id", [None])[0])
    item_count = max(len(scan_ids), len(reconstruction_ids), len(indexing_ids), 1)

    values = [scan_ids, reconstruction_ids, indexing_ids]
    for ids in values:
        if ids and len(ids) not in (1, item_count):
            raise ValueError("Scan, reconstruction, and indexing URL counts do not match")
        if len(ids) == 1 and item_count > 1:
            ids *= item_count
    scan_ids = scan_ids or [None] * item_count
    reconstruction_ids = reconstruction_ids or [None] * item_count
    indexing_ids = indexing_ids or [None] * item_count

    root_path = DEFAULT_VARIABLES.get("root_path", "")
    form_rows = []
    labels = []
    failures = []

    with Session(session_utils.get_engine()) as session:
        for scan_number, reconstruction_id, indexing_id in zip(scan_ids, reconstruction_ids, indexing_ids, strict=True):
            try:
                if indexing_id is not None:
                    indexing = get_indexing(indexing_id)
                    if indexing is None or indexing.method != "lauego":
                        raise ValueError(f"LaueGo indexing I{indexing_id} was not found")
                    if (
                        scan_number is not None
                        and indexing.scan_number is not None
                        and scan_number != indexing.scan_number
                    ):
                        raise ValueError(f"SN{scan_number} does not match indexing I{indexing_id}")
                    if (
                        reconstruction_id is not None
                        and indexing.reconstruction_id is not None
                        and reconstruction_id != indexing.reconstruction_id
                    ):
                        raise ValueError(f"R{reconstruction_id} does not match indexing I{indexing_id}")
                    form_data = _copy_indexing_for_form(indexing, root_path)
                    scan_number = scan_number if scan_number is not None else indexing.scan_number
                    reconstruction_id = (
                        reconstruction_id if reconstruction_id is not None else indexing.reconstruction_id
                    )
                    form_data.scan_number = scan_number
                    form_data.reconstruction_id = reconstruction_id
                else:
                    form_data = create_default_peakindex(
                        {
                            "scan_number": scan_number,
                            "reconstruction_id": reconstruction_id,
                            "output_path_template": build_output_folder_template(scan_number, None, reconstruction_id),
                        }
                    )
                    metadata = session.get(db_schema.Metadata, scan_number) if scan_number is not None else None
                    if scan_number is not None and metadata is None:
                        raise ValueError(f"Scan SN{scan_number} was not found")
                    if metadata is not None:
                        if metadata.source_energy is not None:
                            form_data.index_kev_max_calc = metadata.source_energy
                            form_data.index_kev_max_test = metadata.source_energy
                        if metadata.source_energy_unit:
                            form_data.energy_unit = metadata.source_energy_unit

                    if reconstruction_id is not None:
                        reconstruction = get_reconstruction(reconstruction_id)
                        if reconstruction is None:
                            raise ValueError(f"Reconstruction R{reconstruction_id} was not found")
                        if (
                            scan_number is not None
                            and reconstruction.scan_number is not None
                            and scan_number != reconstruction.scan_number
                        ):
                            raise ValueError(f"SN{scan_number} does not match reconstruction R{reconstruction_id}")
                        scan_number = scan_number if scan_number is not None else reconstruction.scan_number
                        form_data.scan_number = scan_number
                        form_data.input_path = reconstruction.output_path
                        form_data.data_path = remove_root_path_prefix(reconstruction.output_path, root_path)
                        parameters = reconstruction.wire_parameters
                        if parameters is not None:
                            form_data.filename_prefixes = parameters.filename_prefixes
                            form_data.scan_points = parameters.scan_points
                            form_data.geometry_file = remove_root_path_prefix(parameters.geometry_file, root_path)
                        form_data.output_path_template = build_output_folder_template(
                            scan_number, reconstruction.output_path, reconstruction_id
                        )
                    elif scan_number is not None:
                        catalog = session.get(db_schema.Catalog, scan_number)
                        if catalog is not None:
                            form_data.input_path = catalog.filefolder
                            form_data.data_path = remove_root_path_prefix(catalog.filefolder, root_path)
                            form_data.filename_prefixes = catalog.filenamePrefix

                form_data.identity_value = _identity_label(scan_number, reconstruction_id, indexing_id)
                form_rows.append(form_data)
                labels.append(form_data.identity_value or "unlinked input")
            except Exception as error:
                failures.append(str(error))

    if not form_rows:
        set_peakindex_form_props(create_default_peakindex())
        if failures:
            set_props(
                "alert-scan-loaded",
                {"is_open": True, "children": "; ".join(failures), "color": "danger"},
            )
        return datetime.datetime.now().isoformat()

    if len(form_rows) == 1:
        pooled = form_rows[0]
    else:
        pooled = create_default_peakindex()
        merge_fields = [field for field in vars(pooled) if field not in {"id", "scan_number", "reconstruction_id"}]
        for field in merge_fields:
            setattr(pooled, field, _merge_field_values([getattr(row, field) for row in form_rows]))
        pooled.identity_value = "; ".join(row.identity_value for row in form_rows)

    pooled.author = DEFAULT_VARIABLES.get("author", "")
    pooled.notes = DEFAULT_VARIABLES.get("notes", "")
    set_peakindex_form_props(pooled)
    color = "warning" if failures else "success"
    message = f"Loaded {', '.join(labels)}."
    if failures:
        message += f" Could not load: {'; '.join(failures)}"
    set_props("alert-scan-loaded", {"is_open": True, "children": message, "color": color})
    return datetime.datetime.now().isoformat()
