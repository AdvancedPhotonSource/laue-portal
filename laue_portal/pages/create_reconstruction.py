import base64
import datetime
import logging
import math
import urllib.parse

import dash
import dash_bootstrap_components as dbc
import yaml
from dash import Input, State, dcc, html, set_props
from dash.exceptions import PreventUpdate
from sqlalchemy.orm import Session

import laue_portal.database.db_schema as db_schema
import laue_portal.database.db_utils as db_utils

logger = logging.getLogger(__name__)
import laue_portal.components.navbar as navbar
import laue_portal.database.session_utils as session_utils
from laue_portal.components.recon_form import recon_form, set_recon_form_props
from laue_portal.config import DEFAULT_VARIABLES
from laue_portal.database.db_utils import remove_root_path_prefix, resolve_path_with_root
from laue_portal.processing.queue.core import STATUS_REVERSE_MAPPING
from laue_portal.processing.queue.enqueue import enqueue_reconstruction
from laue_portal.services.scan_import import find_motor_group

JOB_DEFAULTS = {
    "computer_name": "example_computer",
    "status": 0,
    "priority": 0,
    "submit_time": datetime.datetime.now(),
    "start_time": datetime.datetime.now(),
    "finish_time": datetime.datetime.now(),
}

RECON_DEFAULTS = {
    "calib_id": 0,
}

RECON_SCAN_REQUIRED_INPUTS = {
    "compute settings",
    "input filename and HDF layout",
    "mask geometry",
    "detector geometry",
    "reconstruction depth grid",
    "algorithm parameters",
}


def _completed_frame_count(metadata, scans):
    """Return the number of completed sample/depth frames recorded for a scan."""
    completed_counts = []
    for field_name in ("motorGroup_sample_cpt_total", "motorGroup_depth_cpt_total"):
        value = getattr(metadata, field_name, None)
        if value is not None and int(value) > 0:
            completed_counts.append(int(value))

    scan_counts = [int(scan.scan_cpt) for scan in scans if scan.scan_cpt is not None and int(scan.scan_cpt) > 0]
    recorded_total = math.prod(completed_counts) if completed_counts else None
    scan_total = max(scan_counts, default=None)

    # Scan import uses 1 as a neutral fallback for an absent sample/depth group.
    # Prefer an actual completed dimension count when both group totals are only
    # those neutral fallback values.
    if recorded_total == 1 and scan_total and scan_total > 1:
        return scan_total
    return recorded_total or scan_total


def _depth_scan_step(scans):
    """Find the first coded-aperture/depth positioner step stored on the scan."""
    for scan in scans:
        for positioner_index in range(1, 5):
            pv = getattr(scan, f"scan_positioner{positioner_index}_PV", None)
            positioner = getattr(scan, f"scan_positioner{positioner_index}", None)
            if find_motor_group(pv) != "depth" or not positioner:
                continue

            try:
                _start, _stop, step = str(positioner).split()[:3]
                return abs(float(step))
            except (TypeError, ValueError):
                continue
    return None


def _build_recon_scan_updates(session, scan_id, root_path):
    """Build form updates from scan-related database records."""
    metadata = session.query(db_schema.Metadata).filter(db_schema.Metadata.scanNumber == scan_id).first()
    if metadata is None:
        return None, {f"scan {scan_id}"}

    catalog = session.query(db_schema.Catalog).filter(db_schema.Catalog.scanNumber == scan_id).first()
    scans = session.query(db_schema.Scan).filter(db_schema.Scan.scanNumber == scan_id).all()
    default_author = DEFAULT_VARIABLES.get("author") or metadata.user_name or ""
    default_notes = DEFAULT_VARIABLES.get("notes") or (catalog.notes if catalog else "") or ""
    frame_count = _completed_frame_count(metadata, scans)
    scanner_step = _depth_scan_step(scans)

    updates = {
        "scanNumber": scan_id,
        "file_output": f"analysis/scan_{scan_id}/rec_%d",
        "author": default_author,
        "notes": default_notes,
    }
    missing = set(RECON_SCAN_REQUIRED_INPUTS)

    if catalog and catalog.filefolder:
        updates["file_path"] = remove_root_path_prefix(catalog.filefolder, root_path)
    else:
        missing.add("input path")

    if frame_count is not None:
        updates.update({"frame_start": 0, "frame_end": frame_count})
    else:
        missing.add("frame range")

    if scanner_step is not None:
        updates["step"] = scanner_step

    # Calib.scanNumber is the calibration source scan, not a relationship from
    # an arbitrary data scan to the calibration it should use.  Without an
    # existing recon_id there is no safe calibration to select automatically.
    missing.add("calibration/focus geometry")

    return updates, missing


def _merge_recon_scan_updates(scan_updates):
    """Merge per-scan values for the pooled form convention used by create pages."""
    merged = {"scanNumber": ",".join(str(updates["scanNumber"]) for updates in scan_updates)}
    field_names = set().union(*(updates.keys() for updates in scan_updates)) - {"scanNumber"}

    for field_name in field_names:
        values = [updates.get(field_name) for updates in scan_updates]
        if all(value == values[0] for value in values):
            merged[field_name] = values[0]
        else:
            merged[field_name] = "; ".join("" if value is None else str(value) for value in values)
    return merged


def _parse_pooled_value(value, count, converter=None):
    """Expand a common value or parse one semicolon-delimited value per scan."""
    if isinstance(value, str) and ";" in value:
        values = [part.strip() or None for part in value.split(";")]
        if len(values) != count:
            raise ValueError(f"Expected {count} pooled values, received {len(values)}")
    else:
        values = [value] * count

    if converter:
        values = [converter(item) if item is not None else None for item in values]
    return values

dash.register_page(__name__)

layout = dbc.Container(
    [
        html.Div(
            [
                navbar.navbar,
                dcc.Location(id="url-create-recon", refresh=False),
                dbc.Alert(
                    id="alert-upload",
                    dismissable=True,
                    is_open=False,
                ),
                dbc.Alert(
                    id="alert-submit",
                    dismissable=True,
                    is_open=False,
                ),
                dbc.Alert(
                    id="alert-submit-job",
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
                html.Center(
                    html.Div(
                        [
                            html.Div(
                                [
                                    dcc.Upload(dbc.Button("Upload Config"), id="upload-config"),
                                ],
                                style={"display": "inline-block"},
                            ),
                        ],
                    )
                ),
                html.Hr(),
                html.Center(
                    dbc.Button("Submit", id="submit_recon", color="primary"),
                ),
                html.Hr(),
                recon_form,
            ],
        )
    ],
    className="dbc",
    fluid=True,
)


@dash.callback(
    Input("upload-config", "contents"),
    prevent_initial_call=True,
)
def upload_config(contents):
    try:
        content_type, content_string = contents.split(",")
        decoded = base64.b64decode(content_string)
        config = yaml.safe_load(decoded)
        recon_row = db_utils.import_recon_row(config)

        set_props("alert-upload", {"is_open": True, "children": "Config uploaded successfully", "color": "success"})
        set_recon_form_props(recon_row)

    except Exception as e:
        set_props("alert-upload", {"is_open": True, "children": f"Upload Failed! Error: {e}", "color": "danger"})


@dash.callback(
    Input("submit_recon", "n_clicks"),
    State("scanNumber", "value"),
    State("frame_start", "value"),
    State("frame_end", "value"),
    State("x_start", "value"),
    State("x_end", "value"),
    State("y_start", "value"),
    State("y_end", "value"),
    State("depth_start", "value"),
    State("depth_end", "value"),
    State("depth_resolution", "value"),
    State("recon_name", "value"),
    State("calib_id", "value"),
    State("file_path", "value"),
    State("file_output", "value"),
    State("data_stacked", "value"),
    State("h5_key", "value"),
    State("cenx", "value"),
    State("ceny", "value"),
    State("cenz", "value"),
    State("anglex", "value"),
    State("angley", "value"),
    State("anglez", "value"),
    State("shift", "value"),
    State("mask_path", "value"),
    State("reversed", "value"),
    State("bitsize_0", "value"),
    State("bitsize_1", "value"),
    State("thickness", "value"),
    State("resolution", "value"),
    State("smoothness", "value"),
    State("widening", "value"),
    State("pad", "value"),
    State("stretch", "value"),
    State("step", "value"),
    State("mot_rot_a", "value"),
    State("mot_rot_b", "value"),
    State("mot_rot_c", "value"),
    State("mot_axis_x", "value"),
    State("mot_axis_y", "value"),
    State("mot_axis_z", "value"),
    State("pixels_x", "value"),
    State("pixels_y", "value"),
    State("size_x", "value"),
    State("size_y", "value"),
    State("det_rot_a", "value"),
    State("det_rot_b", "value"),
    State("det_rot_c", "value"),
    State("det_pos_x", "value"),
    State("det_pos_y", "value"),
    State("det_pos_z", "value"),
    State("source_offset", "value"),
    State("iters", "value"),
    State("pos_method", "value"),
    State("pos_regpar", "value"),
    State("pos_init", "value"),
    State("recon_sig", "value"),
    State("sig_method", "value"),
    State("sig_order", "value"),
    State("sig_scale", "value"),
    State("sig_maxsize", "value"),
    State("sig_avgsize", "value"),
    State("sig_atol", "value"),
    State("recon_ene", "value"),
    State("exact_ene", "value"),
    State("ene_method", "value"),
    State("ene_min", "value"),
    State("ene_max", "value"),
    State("ene_step", "value"),
    State("author", "value"),
    State("notes", "value"),
    prevent_initial_call=True,
)
def submit_config(
    n,
    scanNumbers,
    frame_start,
    frame_end,
    x_start,
    x_end,
    y_start,
    y_end,
    depth_start,
    depth_end,
    depth_resolution,
    recon_name,
    calib_id,
    file_path,
    file_output,
    data_stacked,
    h5_key,
    cenx,
    ceny,
    cenz,
    anglex,
    angley,
    anglez,
    shift,
    mask_path,
    mask_reversed,
    bitsize_0,
    bitsize_1,
    thickness,
    resolution,
    smoothness,
    widening,
    pad,
    stretch,
    step,
    mot_rot_a,
    mot_rot_b,
    mot_rot_c,
    mot_axis_x,
    mot_axis_y,
    mot_axis_z,
    pixels_x,
    pixels_y,
    size_x,
    size_y,
    det_rot_a,
    det_rot_b,
    det_rot_c,
    det_pos_x,
    det_pos_y,
    det_pos_z,
    source_offset,
    iters,
    pos_method,
    pos_regpar,
    pos_init,
    recon_sig,
    sig_method,
    sig_order,
    sig_scale,
    sig_maxsize,
    sig_avgsize,
    sig_atol,
    recon_ene,
    exact_ene,
    ene_method,
    ene_min,
    ene_max,
    ene_step,
    author,
    notes,
):
    scan_numbers = [scan_number.strip() for scan_number in str(scanNumbers).split(",")]
    num_scans = len(scan_numbers)
    file_paths = _parse_pooled_value(file_path, num_scans)
    file_outputs = _parse_pooled_value(file_output, num_scans)
    frame_starts = _parse_pooled_value(frame_start, num_scans, lambda value: int(float(value)))
    frame_ends = _parse_pooled_value(frame_end, num_scans, lambda value: int(float(value)))
    scanner_steps = _parse_pooled_value(step, num_scans, float)
    authors = _parse_pooled_value(author, num_scans)
    notes_list = _parse_pooled_value(notes, num_scans)

    for scan_index, scanNumber in enumerate(scan_numbers):
        now = datetime.datetime.now()

        job = db_schema.Job(
            computer_name=JOB_DEFAULTS["computer_name"],
            status=JOB_DEFAULTS["status"],
            priority=JOB_DEFAULTS["priority"],
            submit_time=now,
            start_time=now,
            finish_time=now,
        )

        with Session(session_utils.get_engine()) as session:
            session.add(job)
            session.flush()
            job_id = job.job_id
            selected_calib_id = calib_id if calib_id is not None else RECON_DEFAULTS["calib_id"]
            calibration = (
                session.query(db_schema.Calib).filter(db_schema.Calib.calib_id == selected_calib_id).first()
                if selected_calib_id is not None
                else None
            )

            for _ in range(6):
                subjob = db_schema.SubJob(
                    job_id=job_id,
                    computer_name=JOB_DEFAULTS["computer_name"],
                    status=STATUS_REVERSE_MAPPING["Queued"],
                    priority=JOB_DEFAULTS["priority"],
                )
                session.add(subjob)

            recon = db_schema.Recon(
                scanNumber=scanNumber,
                calib_id=selected_calib_id,
                job_id=job_id,
                author=authors[scan_index],
                notes=notes_list[scan_index],
                file_path=resolve_path_with_root(file_paths[scan_index], DEFAULT_VARIABLES.get("root_path", "")),
                file_output=file_outputs[scan_index],
                file_stacked=data_stacked,
                file_range=[frame_starts[scan_index], frame_ends[scan_index]],
                file_threshold=0,
                file_frame=[x_start, x_end, y_start, y_end],
                file_ext="h5",
                file_h5_key=h5_key,
                comp_server="TODO",
                comp_workers=0,
                comp_usegpu=True,
                comp_batch_size=0,
                geo_mask_path=resolve_path_with_root(mask_path, DEFAULT_VARIABLES.get("root_path", "")),
                geo_mask_reversed=mask_reversed,
                geo_mask_bitsizes=[bitsize_0, bitsize_1],
                geo_mask_thickness=thickness,
                geo_mask_resolution=resolution,
                geo_mask_smoothness=smoothness,
                geo_mask_alpha=0,
                geo_mask_widening=widening,
                geo_mask_pad=pad,
                geo_mask_stretch=stretch,
                geo_mask_shift=shift,
                geo_mask_focus_cenx=cenx,
                geo_mask_focus_dist=ceny,
                geo_mask_focus_anglez=anglez,
                geo_mask_focus_angley=angley,
                geo_mask_focus_anglex=anglex,
                geo_mask_focus_cenz=cenz,
                geo_mask_cal_id=selected_calib_id,
                geo_mask_cal_path=calibration.calib_config if calibration else "",
                geo_scanner_step=scanner_steps[scan_index],
                geo_scanner_rot=[mot_rot_a, mot_rot_b, mot_rot_c],
                geo_scanner_axis=[mot_axis_x, mot_axis_y, mot_axis_z],
                geo_detector_shape=[pixels_x, pixels_y],
                geo_detector_size=[size_x, size_y],
                geo_detector_rot=[det_rot_a, det_rot_b, det_rot_c],
                geo_detector_pos=[det_pos_x, det_pos_y, det_pos_z],
                geo_source_offset=source_offset,
                geo_source_grid=[depth_start, depth_end, depth_resolution],
                algo_iter=iters,
                algo_pos_method=pos_method,
                algo_pos_regpar=pos_regpar,
                algo_pos_init=pos_init,
                algo_sig_recon=recon_sig,
                algo_sig_method=sig_method,
                algo_sig_order=sig_order,
                algo_sig_scale=sig_scale,
                algo_sig_init_maxsize=sig_maxsize,
                algo_sig_init_avgsize=sig_avgsize,
                algo_sig_init_atol=sig_atol,
                algo_ene_recon=recon_ene,
                algo_ene_exact=exact_ene,
                algo_ene_method=ene_method,
                algo_ene_range=[ene_min, ene_max, ene_step],
            )

            session.add(recon)
            session.flush()
            if recon.file_output and "%d" in recon.file_output:
                recon.file_output = recon.file_output % recon.recon_id
            recon.file_output = resolve_path_with_root(recon.file_output, DEFAULT_VARIABLES.get("root_path", ""))
            config_dict = db_utils.create_config_obj(recon)

            session.commit()

            set_props("alert-submit", {"is_open": True, "children": "Config Added to Database", "color": "success"})

            try:
                rq_job_id = enqueue_reconstruction(job_id, config_dict)
                logger.info(f"Job {job_id} enqueued with RQ ID: {rq_job_id}")

                set_props(
                    "alert-submit-job",
                    {"is_open": True, "children": f"Job {job_id} submitted to queue", "color": "info"},
                )
            except Exception as e:
                logger.error(f"Failed to enqueue job: {e}")
                set_props(
                    "alert-submit-job",
                    {"is_open": True, "children": f"Failed to queue job: {str(e)}", "color": "danger"},
                )


@dash.callback(
    Input("url-create-recon", "href"),
    prevent_initial_call=True,
)
def load_scan_data_from_url(href):
    """Load scan data and optionally existing recon data from URL query parameters."""
    if not href:
        raise PreventUpdate

    parsed_url = urllib.parse.urlparse(href)
    query_params = urllib.parse.parse_qs(parsed_url.query)

    scan_id_str = query_params.get("scan_id", [None])[0]
    recon_id_str = query_params.get("recon_id", [None])[0]
    root_path = DEFAULT_VARIABLES.get("root_path", "")

    if not scan_id_str:
        return

    try:
        scan_ids = [int(scan_id) for scan_id in scan_id_str.split(",")]
    except (TypeError, ValueError):
        set_props(
            "alert-scan-loaded",
            {"is_open": True, "children": f"Invalid scan ID: {scan_id_str}", "color": "danger"},
        )
        return

    if recon_id_str and len(scan_ids) == 1:
        try:
            recon_id = int(recon_id_str)
            with Session(session_utils.get_engine()) as session:
                recon_data = session.query(db_schema.Recon).filter(db_schema.Recon.recon_id == recon_id).first()

                if recon_data:
                    recon_data.file_path = (
                        remove_root_path_prefix(recon_data.file_path, root_path) if recon_data.file_path else ""
                    )
                    recon_data.file_output = (
                        remove_root_path_prefix(recon_data.file_output, root_path) if recon_data.file_output else ""
                    )
                    recon_data.geo_mask_path = (
                        remove_root_path_prefix(recon_data.geo_mask_path, root_path) if recon_data.geo_mask_path else ""
                    )

                    set_recon_form_props(recon_data)
                    set_props(
                        "alert-scan-loaded",
                        {
                            "is_open": True,
                            "children": f"Loaded existing reconstruction {recon_id} data for scan {scan_ids[0]}",
                            "color": "success",
                        },
                    )
                    return
        except (TypeError, ValueError) as e:
            logger.warning(f"Failed to load recon {recon_id_str}: {e}")
        except Exception as e:
            logger.error(f"Error loading reconstruction {recon_id_str}: {e}")
            set_props(
                "alert-scan-loaded",
                {"is_open": True, "children": f"Error loading data: {str(e)}", "color": "danger"},
            )
            return

    try:
        scan_updates = []
        missing_inputs = set()
        not_found = set()
        with Session(session_utils.get_engine()) as session:
            for scan_id in scan_ids:
                updates, missing = _build_recon_scan_updates(session, scan_id, root_path)
                if updates is None:
                    not_found.update(missing)
                    continue
                scan_updates.append(updates)
                missing_inputs.update(missing)

        if not scan_updates:
            set_props(
                "alert-scan-loaded",
                {
                    "is_open": True,
                    "children": f"Could not find: {', '.join(sorted(not_found))}",
                    "color": "danger",
                },
            )
            return

        for component_id, value in _merge_recon_scan_updates(scan_updates).items():
            set_props(component_id, {"value": value})

        loaded_ids = ",".join(str(updates["scanNumber"]) for updates in scan_updates)
        message = f"Loaded database values for scan {loaded_ids}."
        if not_found:
            message += f" Could not find: {', '.join(sorted(not_found))}."
        if missing_inputs:
            message += f" Still required: {', '.join(sorted(missing_inputs))}."

        set_props(
            "alert-scan-loaded",
            {
                "is_open": True,
                "children": message,
                "color": "warning" if missing_inputs or not_found else "success",
            },
        )
    except Exception as e:
        logger.error(f"Error loading scan data: {e}")
        set_props(
            "alert-scan-loaded",
            {"is_open": True, "children": f"Error loading scan data: {str(e)}", "color": "danger"},
        )
