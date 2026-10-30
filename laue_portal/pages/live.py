"""Configure one live scan; results remain on the existing R/I pages."""

from dataclasses import fields
from pathlib import Path

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, dcc, html

from laue_portal.components import navbar
from laue_portal.components.form_layout import form_field, form_select, section_card
from laue_portal.components.live_form import INDEX_FIELDS, WIRE_FIELDS, parameter_sections
from laue_portal.components.live_header import BUTTONS, build_header, header_view
from laue_portal.components.live_validation import FORM_FIELDS, PARAMETER_IDS, form_errors, show_feedback, with_feedback
from laue_portal.components.request_defaults import create_default_peakindex, create_default_wirerecon
from laue_portal.config import DEFAULT_VARIABLES, LIVE
from laue_portal.processing.bdp.settings import execution_computer
from laue_portal.processing.live_queue import enqueue_live
from laue_portal.services.dm_daq import MANUAL, bind_daq, destination_root, list_daqs
from laue_portal.workflows.indexing import LaueGoIndexingRequest
from laue_portal.workflows.live import create_live, request_action, session_status
from laue_portal.workflows.reconstruction import WireReconstructionRequest

dash.register_page(__name__, path="/live")


def _path(value):
    if not value:
        return ""
    path = Path(str(value)).expanduser()
    if not path.is_absolute():
        path = Path(DEFAULT_VARIABLES.get("root_path", ".")) / path
    return str(path.resolve())


def layout():
    defaults = LIVE.get("defaults", {})
    r, i = vars(create_default_wirerecon()), vars(create_default_peakindex(defaults.get("indexing")))
    selected_daq = defaults.get("daq_id", MANUAL)
    daq_options = [{"label": "Completed-file notifications", "value": MANUAL}]
    if selected_daq != MANUAL:
        daq_options.append({"label": "DM DAQ", "value": selected_daq})
    form = html.Div(
        [
            navbar.navbar,
            dcc.Interval(id="live-poll", interval=3000),
            dcc.Store(id="live-selected"),
            dcc.Store(id="live-daq-records", data=[]),
            dcc.Interval(id="live-daq-poll", interval=15000),
            html.Div(
                [
                    build_header(),
                    dbc.Alert(id="live-message", is_open=False, className="lp-live-message"),
                    section_card(
                        "Scan",
                        html.Div(
                            [
                                form_select("Input source", "live-daq", daq_options, wide=True, value=selected_daq),
                                html.Div(id="live-daq-details", className="lp-live-daq-details lp-form-field-wide"),
                                html.Div(id="live-daq-error", className="text-danger lp-form-field-wide"),
                                form_field(
                                    "Scan number", "live-scan", input_type="number", value=defaults.get("scan_number")
                                ),
                                form_field("Author", "live-author", value=DEFAULT_VARIABLES.get("author", "")),
                                form_field(
                                    "Input folder", "live-input", wide=True, value=defaults.get("input_path", "")
                                ),
                                form_field(
                                    "Filename",
                                    "live-filename",
                                    wide=True,
                                    placeholder="Twin2_wire_%d.h5",
                                    value=defaults.get("filename", ""),
                                ),
                                form_field(
                                    "Output folder",
                                    "live-output",
                                    wide=True,
                                    value=defaults.get("output_path", _path("analysis/live")),
                                ),
                            ],
                            className="lp-form-field-grid",
                        ),
                        accent="teal",
                        icon_class="bi bi-folder2-open",
                    ),
                    section_card(
                        "Reconstruction",
                        html.Div(
                            [
                                dbc.Checkbox(
                                    id="live-recon-enabled",
                                    label="Reconstruct detector stacks",
                                    value=defaults.get("reconstruction_enabled", True),
                                    className="mb-3",
                                ),
                                html.Div(
                                    [
                                        form_field(
                                            "Geometry file",
                                            "live-geometry-r",
                                            wide=True,
                                            value=_path(r["geometry_file"]),
                                        ),
                                        html.Div(parameter_sections("r", r), id="live-r-parameters"),
                                    ],
                                    id="live-recon-settings",
                                ),
                            ]
                        ),
                        accent="purple",
                        icon_class="bi bi-layers",
                    ),
                    section_card(
                        "Indexing",
                        html.Div(
                            [
                                dbc.Checkbox(
                                    id="live-index-enabled",
                                    label="Index completed reconstruction points",
                                    value=defaults.get("indexing_enabled", True),
                                    className="mb-3",
                                ),
                                html.Div(
                                    [
                                        html.Div(
                                            [
                                                form_field(
                                                    "Geometry file",
                                                    "live-geometry-i",
                                                    wide=True,
                                                    value=defaults.get("geometry_file", _path(i["geometry_file"])),
                                                ),
                                                form_field(
                                                    "Crystal file",
                                                    "live-crystal",
                                                    wide=True,
                                                    value=defaults.get("crystal_file", _path(i["crystal_file"])),
                                                ),
                                                html.Div(
                                                    form_field(
                                                        "Depth indices",
                                                        "live-depths",
                                                        placeholder="empty: all reconstructed depths",
                                                        value=i["depth_range"],
                                                    ),
                                                    id="live-depth-settings",
                                                ),
                                            ],
                                            className="lp-form-field-grid",
                                        ),
                                        html.Div(parameter_sections("i", i), id="live-i-parameters"),
                                    ],
                                    id="live-index-settings",
                                ),
                            ]
                        ),
                        accent="rose",
                        icon_class="bi bi-diagram-3",
                    ),
                ],
                className="lp-form-page lp-live-content",
            ),
        ],
        className="lp-live-page",
    )
    return with_feedback(form)


PARAMETER_STATES = [
    State(f"live-{stage}-{key}", "value")
    for stage, mapping in (("r", WIRE_FIELDS), ("i", INDEX_FIELDS))
    for key in mapping
]


def build_live_requests(
    scan, author, source, filename, output, rgeo, igeo, crystal, depths, enabled, reconstruction_enabled, daq, values
):
    """Shared defaults and request validation, with no file enumeration."""
    r, i = vars(create_default_wirerecon()), vars(create_default_peakindex(LIVE.get("defaults", {}).get("indexing")))
    values = iter(values)
    for parameters, mapping in ((r, WIRE_FIELDS), (i, INDEX_FIELDS)):
        for name in mapping.values():
            value = next(values)
            if (parameters is i and not enabled) or (parameters is r and not reconstruction_enabled):
                continue
            if name == "indexHKL":
                hkl = str(value or "0 0 1").replace(",", " ").split()
                if len(hkl) != 3:
                    raise ValueError("Central HKL requires three integers")
                parameters.update(dict(zip(("index_h", "index_k", "index_l"), map(int, hkl), strict=True)))
                continue
            if name not in {"wire_edges", "peak_shape", "mask_file", "smooth", "depth"}:
                if value in (None, "") and name in {"threshold", "threshold_ratio", "max_number", "max_peaks"}:
                    value = None
                else:
                    converter = (
                        int
                        if name
                        in {
                            "frame_skip",
                            "wire_skip",
                            "box_size",
                            "min_separation",
                            "threshold",
                            "threshold_ratio",
                            "max_number",
                            "max_peaks",
                        }
                        else float
                    )
                    value = converter(value)
            parameters[name] = value
    if not author or not source or not output:
        raise ValueError("Author, input folder and output folder are required")
    common = dict(
        scan_number=int(scan) if scan is not None else None,
        author=author,
        input_path=_path(source),
        scan_points=None,
        backend="local",
        computer_name=execution_computer("local"),
        filename_prefixes=[filename.strip()],
    )
    if not enabled and not reconstruction_enabled:
        raise ValueError("Enable reconstruction, indexing, or both")
    r.update(
        common,
        output_path_template=str(Path(_path(output)) / "rec_%d"),
        geometry_file=_path(rgeo),
        num_threads=8,
        memory_limit_mb=DEFAULT_VARIABLES.get("memory_limit_mb") or 8192,
        verbose=0,
    )
    rkeys = {field.name for field in fields(WireReconstructionRequest) if field.init}
    reconstruction = (
        WireReconstructionRequest(**{key: value for key, value in r.items() if key in rkeys})
        if reconstruction_enabled
        else None
    )
    indexing = None
    if enabled:
        i.update(
            common,
            output_path_template=str(Path(_path(output)) / "index_%d"),
            geometry_file=_path(igeo),
            crystal_file=_path(crystal),
            mask_file=_path(i["mask_file"])
            if str(i["mask_file"] or "").strip().lower() not in {"", "none", "null"}
            else None,
            depth_range=(depths or None) if reconstruction_enabled else None,
            output_xml="output.xml",
            cosmic_filter=False,
        )
        ikeys = {field.name for field in fields(LaueGoIndexingRequest) if field.init}
        indexing = LaueGoIndexingRequest(**{key: value for key, value in i.items() if key in ikeys})
    return reconstruction, indexing


@callback(
    Output("live-daq", "options"),
    Output("live-daq-records", "data"),
    Output("live-daq-error", "children"),
    Input("live-daq-poll", "n_intervals"),
    State("live-daq-records", "data"),
)
def refresh_daqs(tick, previous):
    try:
        records = list_daqs()
    except Exception:
        return dash.no_update, dash.no_update, "DAQ list unavailable; check the DM connection."
    options = [{"label": "Completed-file notifications", "value": MANUAL}]
    options.extend(
        {
            "label": f"{r['experimentName']} · {Path(r['dataDirectory']).parent.name}/{Path(r['dataDirectory']).name} ({r['status']})",
            "value": r["id"],
        }
        for r in records
    )
    return options, records if records != previous else dash.no_update, ""


@callback(
    Output("live-daq-details", "children"),
    Input("live-daq", "value"),
    Input("live-daq-records", "data"),
)
def describe_daq(selected, records):
    if not selected or selected == MANUAL:
        return []
    record = next((r for r in records or [] if r["id"] == selected), None)
    if record is None:
        return "Loading DAQ…"
    return [
        html.Div([html.Span("From "), html.Code(record["dataDirectory"])]),
        html.Div([html.Span("To "), html.Code(str(destination_root(record)))]),
    ]


@callback(
    Output("live-input", "value"),
    Input("live-daq", "value"),
    State("live-daq-records", "data"),
    State("live-input", "value"),
    prevent_initial_call=True,
)
def select_daq(selected, records, current):
    record = next((r for r in records or [] if r["id"] == selected), None)
    if record is None:
        return dash.no_update
    destination = destination_root(record)
    return dash.no_update if current and Path(_path(current)).is_relative_to(destination) else str(destination)


@callback(
    Output("live-recon-settings", "style"),
    Output("live-index-settings", "style"),
    Output("live-depth-settings", "style"),
    Output("live-index-enabled", "label"),
    Input("live-recon-enabled", "value"),
    Input("live-index-enabled", "value"),
)
def select_stages(reconstruction, indexing):
    return (
        {} if reconstruction else {"display": "none"},
        {} if indexing else {"display": "none"},
        {} if reconstruction else {"display": "none"},
        "Index completed reconstruction points" if reconstruction else "Index detector frames",
    )


@callback(
    Output("live-message", "children"),
    Output("live-message", "is_open"),
    Output("live-selected", "data"),
    Input("live-start", "n_clicks"),
    Input("live-stop", "n_clicks"),
    Input("live-resume", "n_clicks"),
    Input("live-validate", "n_clicks"),
    State("live-selected", "data"),
    *[State(identity, "value") for identity in FORM_FIELDS],
    *PARAMETER_STATES,
    prevent_initial_call=True,
)
def control_live(start, stop, resume, validate, selected, *values):
    dash.set_props("live-message", {"color": "danger"})
    try:
        action = dash.ctx.triggered_id
        if action in {"live-start", "live-validate"}:
            fields = dict(zip((*FORM_FIELDS, *PARAMETER_IDS), values, strict=True))
            errors = form_errors(fields)
            binding = None
            if not errors:
                try:
                    binding = bind_daq(fields["live-daq"], _path(fields["live-input"]))
                except Exception as error:
                    errors["live-daq"] = str(error)
            show_feedback(errors)
            if errors:
                return "Check the highlighted fields.", True, dash.no_update
            if action == "live-validate":
                dash.set_props("live-message", {"color": "success"})
                return "Form settings are valid.", True, dash.no_update
            field_count = len(FORM_FIELDS)
            r, i = build_live_requests(*values[:field_count], values[field_count:])
            live = create_live(r, i, arrivals=binding)
            enqueue_live(live.id)
            dash.set_props("live-message", {"color": "success"})
            return f"Live session {live.id} queued", True, live.id
        status = session_status(selected)
        if status is None:
            raise ValueError("There is no live session")
        if action == "live-resume":
            enqueue_live(status["id"], resume=True)
        else:
            request_action(status["id"], "stop")
        dash.set_props("live-message", {"color": "info"})
        return "Request saved", True, status["id"]
    except Exception as error:
        return str(error), True, dash.no_update


@callback(
    Output("live-header", "className"),
    Output("live-phase", "children"),
    Output("live-status", "children"),
    Output("live-status", "style"),
    *[Output(f"live-{name}", "disabled") for name in BUTTONS],
    *[Output(f"live-{name}", "style") for name in BUTTONS],
    Output("live-daq", "disabled"),
    Input("live-poll", "n_intervals"),
    Input("live-selected", "data"),
)
def refresh_status(tick, selected):
    view = header_view(session_status(selected))
    return (
        view["className"],
        view["phase"],
        view["details"],
        view["details_style"],
        *view["disabled"],
        *view["styles"],
        view["disabled"][1],
    )
