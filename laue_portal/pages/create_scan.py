import base64
from datetime import datetime

import dash
import dash_ag_grid as dag
import dash_bootstrap_components as dbc
from dash import Input, Output, State, dcc, html

import laue_portal.components.navbar as navbar
from laue_portal.components.server_path_picker import (
    register_server_path_picker_callbacks,
    server_path_picker,
)
from laue_portal.config import SCAN_LOG_BROWSER
from laue_portal.services import scan_import
from laue_portal.services.filesystem_browser import read_selected_file

dash.register_page(__name__)

SCAN_LOG_DEFAULT_PATH = SCAN_LOG_BROWSER.get("default_path", "")
SCAN_LOG_MAX_FILE_SIZE_MB = SCAN_LOG_BROWSER.get("max_file_size_mb", 100)
SCAN_LOG_EXTENSIONS = [".xml", ".txt"]

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

layout = dbc.Container(
    [
        # Client-side stores
        dcc.Store(id="bulk-scan-source-token", data=None),
        html.Div(
            [
                navbar.navbar,
                # Alerts
                dbc.Alert(id="alert-upload", dismissable=True, duration=4000, is_open=False),
                dbc.Alert(id="alert-import", dismissable=True, is_open=False),
                html.Hr(),
                # ---- Upload Section ----
                html.Center(
                    dbc.Stack(
                        [
                            server_path_picker(
                                "scan-log-picker",
                                SCAN_LOG_DEFAULT_PATH,
                                extensions=SCAN_LOG_EXTENSIONS,
                                max_file_size_mb=SCAN_LOG_MAX_FILE_SIZE_MB,
                                title="Browse Server Logs",
                            ),
                            dcc.Upload(
                                id="upload-metadata-log",
                                children=dbc.Button(
                                    [html.I(className="bi bi-upload me-2"), "Upload from Computer"],
                                    color="primary",
                                    size="lg",
                                ),
                                accept=".xml,.txt,application/xml,text/xml,text/plain",
                                multiple=False,
                            ),
                        ],
                        direction="horizontal",
                        gap=2,
                        className="justify-content-center flex-wrap",
                    ),
                ),
                html.Hr(),
                # ---- Quick Selection Card (collapsed until scans loaded) ----
                dbc.Card(
                    [
                        dbc.CardHeader(html.H5("Choose scans to import", className="mb-0")),
                        dbc.CardBody(
                            [
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            dbc.InputGroup(
                                                [
                                                    dbc.InputGroupText("Scan ID greater than"),
                                                    dbc.Input(
                                                        id="bulk-after-scan-id",
                                                        type="number",
                                                        step=1,
                                                        placeholder="e.g. 276500",
                                                    ),
                                                    dbc.Button(
                                                        "Select", id="btn-select-after-scan-id", color="secondary"
                                                    ),
                                                ]
                                            ),
                                            lg=6,
                                            className="mb-2",
                                        ),
                                        dbc.Col(
                                            dbc.InputGroup(
                                                [
                                                    dbc.InputGroupText("Created at/after"),
                                                    dbc.Input(id="bulk-after-time", type="datetime-local"),
                                                    dbc.Button("Select", id="btn-select-after-time", color="secondary"),
                                                ]
                                            ),
                                            lg=6,
                                            className="mb-2",
                                        ),
                                    ]
                                ),
                                html.Div(id="quick-selection-feedback", className="small text-muted"),
                            ]
                        ),
                    ],
                    id="quick-selection-card",
                    style={"display": "none"},
                    className="mb-3",
                ),
                # ---- Catalog Defaults Card (collapsed until scans loaded) ----
                dbc.Card(
                    [
                        dbc.CardHeader(
                            html.H5("Catalog Defaults (applied to all imported scans)", className="mb-0"),
                        ),
                        dbc.CardBody(
                            [
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            [
                                                dbc.InputGroup(
                                                    [
                                                        dbc.InputGroupText("Aperture"),
                                                        dbc.Select(
                                                            id="bulk-aperture",
                                                            options=[
                                                                {"label": "None", "value": ""},
                                                                {"label": "Wire", "value": "wire"},
                                                                {"label": "Coded Aperture", "value": "mask"},
                                                            ],
                                                            value="wire",
                                                        ),
                                                    ],
                                                    className="mb-2",
                                                ),
                                            ],
                                            md=3,
                                        ),
                                        dbc.Col(
                                            [
                                                dbc.InputGroup(
                                                    [
                                                        dbc.InputGroupText("Sample Name"),
                                                        dbc.Input(
                                                            id="bulk-sample-name", value="", placeholder="e.g. Si"
                                                        ),
                                                    ],
                                                    className="mb-2",
                                                ),
                                            ],
                                            md=3,
                                        ),
                                        dbc.Col(
                                            [
                                                dbc.InputGroup(
                                                    [
                                                        dbc.InputGroupText("Files Path"),
                                                        dbc.Input(
                                                            id="bulk-filefolder", value="", placeholder="/path/to/data"
                                                        ),
                                                    ],
                                                    className="mb-2",
                                                ),
                                            ],
                                            md=3,
                                        ),
                                        dbc.Col(
                                            [
                                                dbc.InputGroup(
                                                    [
                                                        dbc.InputGroupText("Filename Prefix"),
                                                        dbc.Input(
                                                            id="bulk-filename-prefix", value="", placeholder="prefix_%d"
                                                        ),
                                                    ],
                                                    className="mb-2",
                                                ),
                                            ],
                                            md=3,
                                        ),
                                    ]
                                ),
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            [
                                                dbc.InputGroup(
                                                    [
                                                        dbc.InputGroupText("Notes"),
                                                        dbc.Input(
                                                            id="bulk-notes", value="", placeholder="Optional notes"
                                                        ),
                                                    ],
                                                    className="mb-2",
                                                ),
                                            ],
                                            md=12,
                                        ),
                                    ]
                                ),
                            ]
                        ),
                    ],
                    id="catalog-defaults-card",
                    style={"display": "none"},
                    className="mb-3",
                ),
                # ---- Action Bar ----
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dbc.Nav(
                                    [
                                        dbc.Button(
                                            [html.I(className="bi bi-check2-all me-1"), "Import Selected"],
                                            id="btn-import-selected",
                                            color="primary",
                                            className="me-2",
                                            disabled=True,
                                        ),
                                        html.Span(
                                            id="import-summary-text", className="align-self-center text-muted me-2"
                                        ),
                                    ],
                                    className="px-2 py-2 d-flex align-items-center",
                                ),
                            ],
                            width=12,
                        ),
                    ],
                    id="action-bar",
                    className="mb-3 mt-0",
                    style={"display": "none"},
                ),
                # ---- AG Grid Scan Table ----
                html.Div(
                    dbc.Container(
                        fluid=True,
                        className="p-0",
                        children=[
                            dag.AgGrid(
                                id="bulk-scan-table",
                                columnSize="responsiveSizeToFit",
                                columnDefs=[],
                                rowData=[],
                                defaultColDef={
                                    "filter": True,
                                    "sortable": True,
                                    "resizable": True,
                                },
                                dashGridOptions={
                                    "pagination": True,
                                    "paginationPageSize": 50,
                                    "domLayout": "autoHeight",
                                    "rowSelection": "multiple",
                                    "suppressRowClickSelection": True,
                                    "animateRows": False,
                                    "rowHeight": 32,
                                    "isRowSelectable": {"function": "params.data && params.data.status === 'New'"},
                                },
                                style={"width": "100%"},
                                className="ag-theme-alpine",
                                getRowId="params.data.scan_key",
                            ),
                        ],
                    ),
                    id="scan-table-container",
                    style={"display": "none"},
                ),
            ]
        ),
    ],
    className="dbc",
    fluid=True,
)

# ---------------------------------------------------------------------------
# Column definitions for the bulk scan AG Grid
# ---------------------------------------------------------------------------

BULK_SCAN_COLS = [
    {
        "headerName": "",
        "field": "checkbox",
        "checkboxSelection": True,
        "headerCheckboxSelection": True,
        "headerCheckboxSelectionFilteredOnly": True,
        "width": 50,
        "pinned": "left",
        "sortable": False,
        "filter": False,
        "resizable": False,
        "suppressMenu": True,
        "floatingFilter": False,
    },
    {
        "headerName": "Scan ID",
        "field": "scanNumber",
        "filter": "agNumberColumnFilter",
        "width": 110,
    },
    {
        "headerName": "Date / Time",
        "field": "time",
        "sort": "desc",
        "width": 180,
    },
    {
        "headerName": "User",
        "field": "user_name",
        "width": 100,
    },
    {
        "headerName": "Energy",
        "field": "energy_display",
        "width": 120,
    },
    {
        "headerName": "Sample XYZ",
        "field": "sample_XYZ",
        "width": 200,
    },
    {
        "headerName": "Dims",
        "field": "num_dims",
        "width": 70,
        "filter": "agNumberColumnFilter",
    },
    {
        "headerName": "Status",
        "field": "status",
        "cellRenderer": "ScanImportStatusRenderer",
        "width": 110,
        "pinned": "right",
    },
]


# ---------------------------------------------------------------------------
# Callback 1: Select XML -> build lightweight index -> populate table
# ---------------------------------------------------------------------------


register_server_path_picker_callbacks(
    "scan-log-picker",
    SCAN_LOG_DEFAULT_PATH,
    extensions=SCAN_LOG_EXTENSIONS,
    max_file_size_mb=SCAN_LOG_MAX_FILE_SIZE_MB,
)


@dash.callback(
    Output("bulk-scan-table", "columnDefs"),
    Output("bulk-scan-table", "rowData"),
    Output("bulk-scan-source-token", "data"),
    Output("alert-upload", "is_open"),
    Output("alert-upload", "children"),
    Output("alert-upload", "color"),
    Output("upload-metadata-log", "contents"),
    Output("scan-table-container", "style"),
    Output("quick-selection-card", "style"),
    Output("catalog-defaults-card", "style"),
    Output("action-bar", "style"),
    Input("upload-metadata-log", "contents"),
    Input("scan-log-picker-selection", "data"),
    prevent_initial_call=True,
)
def upload_and_parse(contents, server_selection=None):
    """Read an XML log, build its lightweight index, and stage selected imports."""
    if not contents and not server_selection:
        raise dash.exceptions.PreventUpdate

    try:
        if server_selection and not contents:
            xml_bytes = read_selected_file(
                server_selection.get("path"),
                extensions=SCAN_LOG_EXTENSIONS,
                max_file_size_mb=SCAN_LOG_MAX_FILE_SIZE_MB,
            )
        else:
            _, content_string = contents.split(",", 1)
            xml_bytes = base64.b64decode(content_string, validate=True)
            if len(xml_bytes) > SCAN_LOG_MAX_FILE_SIZE_MB * 1024 * 1024:
                raise ValueError(f"The uploaded file exceeds the {SCAN_LOG_MAX_FILE_SIZE_MB} MB limit.")
    except Exception as e:
        return (
            [],
            [],
            None,
            True,
            f"Failed to read XML file: {e}",
            "danger",
            None,
            {"display": "none"},
            {"display": "none"},
            {"display": "none"},
            {"display": "none"},
        )

    # Stage 1: parse only the fields needed for display and selection.
    try:
        scan_index = scan_import.index_scans_from_xml(xml_bytes)
    except Exception as e:
        return (
            [],
            [],
            None,
            True,
            f"Failed to parse XML: {e}",
            "danger",
            None,
            {"display": "none"},
            {"display": "none"},
            {"display": "none"},
            {"display": "none"},
        )

    if not scan_index:
        return (
            [],
            [],
            None,
            True,
            "No scans found in the uploaded file.",
            "warning",
            None,
            {"display": "none"},
            {"display": "none"},
            {"display": "none"},
            {"display": "none"},
        )

    # Check which scan numbers already exist in the DB
    valid_scan_numbers = []
    for entry in scan_index:
        try:
            valid_scan_numbers.append(int(entry["scanNumber"]))
        except (TypeError, ValueError):
            continue
    existing = scan_import.check_existing_scan_numbers(valid_scan_numbers)

    # Build AG Grid row data
    row_data = []
    seen_scan_numbers = set()
    for entry in scan_index:
        sn = entry["scanNumber"]
        energy_str = ""
        if entry.get("energy"):
            energy_str = f"{entry['energy']}"
            if entry.get("energy_unit"):
                energy_str += f" {entry['energy_unit']}"

        try:
            numeric_scan_number = int(sn)
        except (TypeError, ValueError):
            status = "Invalid"
        else:
            if numeric_scan_number in seen_scan_numbers:
                status = "Duplicate"
            elif numeric_scan_number in existing:
                status = "Exists"
            else:
                status = "New"
            seen_scan_numbers.add(numeric_scan_number)

        row_data.append({**entry, "scanNumber": str(sn), "energy_display": energy_str, "status": status})

    try:
        source_token = scan_import.stage_scan_log(xml_bytes)
    except Exception as e:
        return (
            [],
            [],
            None,
            True,
            f"Failed to stage uploaded log: {e}",
            "danger",
            None,
            {"display": "none"},
            {"display": "none"},
            {"display": "none"},
            {"display": "none"},
        )

    num_new = sum(1 for r in row_data if r["status"] == "New")
    num_existing = sum(1 for r in row_data if r["status"] == "Exists")
    num_duplicates = sum(1 for r in row_data if r["status"] == "Duplicate")
    num_invalid = sum(1 for r in row_data if r["status"] == "Invalid")
    details = [f"{num_new} new", f"{num_existing} already in database"]
    if num_duplicates:
        details.append(f"{num_duplicates} duplicate IDs in the log")
    if num_invalid:
        details.append(f"{num_invalid} invalid IDs")
    alert_msg = f"Indexed {len(row_data)} scans: {', '.join(details)}."
    alert_color = "success" if num_new > 0 else "info"

    show = {"display": "block"}
    return (
        BULK_SCAN_COLS,
        row_data,
        source_token,
        True,
        alert_msg,
        alert_color,
        None,  # clear upload contents to allow re-upload
        show,
        show,
        show,
        show,
    )


def _select_new_rows_after_scan_id(row_data, threshold):
    threshold = int(threshold)
    selected = []
    for row in row_data or []:
        if row.get("status") != "New":
            continue
        try:
            if int(row["scanNumber"]) > threshold:
                selected.append(row)
        except (KeyError, TypeError, ValueError):
            continue
    return selected


def _select_new_rows_at_or_after_time(row_data, threshold):
    threshold_time = datetime.fromisoformat(str(threshold))
    selected = []
    for row in row_data or []:
        if row.get("status") != "New":
            continue
        try:
            row_time = scan_import.convert_time_string_to_datetime(row.get("time", ""))
        except ValueError:
            continue
        if row_time is not None and row_time >= threshold_time:
            selected.append(row)
    return selected


@dash.callback(
    Output("bulk-scan-table", "selectedRows", allow_duplicate=True),
    Output("quick-selection-feedback", "children"),
    Input("btn-select-after-scan-id", "n_clicks"),
    Input("btn-select-after-time", "n_clicks"),
    State("bulk-scan-table", "rowData"),
    State("bulk-after-scan-id", "value"),
    State("bulk-after-time", "value"),
    prevent_initial_call=True,
)
def apply_quick_selection(_scan_clicks, _time_clicks, row_data, after_scan_id, after_time):
    trigger = dash.ctx.triggered_id
    try:
        if trigger == "btn-select-after-scan-id":
            if after_scan_id in (None, ""):
                return dash.no_update, "Enter a scan ID threshold first."
            selected = _select_new_rows_after_scan_id(row_data, after_scan_id)
            criterion = f"with scan ID greater than {int(after_scan_id)}"
        elif trigger == "btn-select-after-time":
            if not after_time:
                return dash.no_update, "Enter a creation time threshold first."
            selected = _select_new_rows_at_or_after_time(row_data, after_time)
            criterion = f"created at or after {after_time}"
        else:
            raise dash.exceptions.PreventUpdate
    except (TypeError, ValueError):
        return dash.no_update, "The selection threshold is not valid."

    return selected, f"Selected {len(selected)} new scan{'s' if len(selected) != 1 else ''} {criterion}."


# ---------------------------------------------------------------------------
# Callback 2: Enable/disable the import button based on selection
# ---------------------------------------------------------------------------


@dash.callback(
    Output("btn-import-selected", "disabled"),
    Output("btn-import-selected", "children"),
    Output("import-summary-text", "children"),
    Input("bulk-scan-table", "selectedRows"),
    prevent_initial_call=True,
)
def update_import_button(selected_rows):
    if not selected_rows:
        return True, [html.I(className="bi bi-check2-all me-1"), "Import Selected"], ""

    importable = [r for r in selected_rows if r.get("status") == "New"]
    n = len(importable)
    label = [html.I(className="bi bi-check2-all me-1"), f"Import Selected ({n})"]
    summary = f"{n} new scan{'s' if n != 1 else ''} selected"
    return (n == 0), label, summary


# ---------------------------------------------------------------------------
# Callback 3: Import selected scans
# ---------------------------------------------------------------------------


@dash.callback(
    Output("bulk-scan-table", "rowData", allow_duplicate=True),
    Output("bulk-scan-table", "selectedRows", allow_duplicate=True),
    Output("alert-import", "is_open"),
    Output("alert-import", "children"),
    Output("alert-import", "color"),
    Output("alert-import", "duration"),
    Input("btn-import-selected", "n_clicks"),
    State("bulk-scan-table", "selectedRows"),
    State("bulk-scan-table", "rowData"),
    State("bulk-scan-source-token", "data"),
    # Catalog defaults
    State("bulk-aperture", "value"),
    State("bulk-sample-name", "value"),
    State("bulk-filefolder", "value"),
    State("bulk-filename-prefix", "value"),
    State("bulk-notes", "value"),
    running=[
        (Output("btn-import-selected", "disabled"), True, False),
        (
            Output("btn-import-selected", "children"),
            [dbc.Spinner(size="sm", spinner_class_name="me-2"), "Importing..."],
            [html.I(className="bi bi-check2-all me-1"), "Import Selected"],
        ),
    ],
    prevent_initial_call=True,
)
def import_selected_scans(
    n_clicks,
    selected_rows,
    current_row_data,
    source_token,
    aperture,
    sample_name,
    filefolder,
    filename_prefix,
    notes,
):
    if not n_clicks or not selected_rows or not source_token:
        raise dash.exceptions.PreventUpdate

    selected_new_rows = [row for row in selected_rows if row.get("status") == "New"]
    try:
        selected_indices = list(dict.fromkeys(int(row["scan_index"]) for row in selected_new_rows))
    except (KeyError, TypeError, ValueError):
        return dash.no_update, dash.no_update, True, "The scan selection is invalid; reload the log.", "danger", 8000
    if not selected_indices:
        return (
            dash.no_update,
            dash.no_update,
            True,
            "No new scans selected for import.",
            "warning",
            4000,
        )

    # Stage 2: retrieve the source and fully parse only the selected scan elements.
    try:
        xml_bytes = scan_import.load_staged_scan_log(source_token)
        scans_to_import = scan_import.parse_selected_scans_from_xml(xml_bytes, selected_indices)
    except Exception as e:
        return dash.no_update, dash.no_update, True, f"Failed to load selected scans: {e}", "danger", 8000

    # Build catalog defaults
    prefix_list = [s.strip() for s in filename_prefix.split(",")] if filename_prefix else []
    catalog_defaults = {
        "filefolder": filefolder or "",
        "filenamePrefix": prefix_list,
        "aperture": aperture or "none",
        "sample_name": sample_name or "",
        "notes": notes or "",
    }

    # Do the bulk import
    results = scan_import.bulk_import_scans(scans_to_import, catalog_defaults)

    # Update row data with new statuses
    parsed_indices = {parsed["scan_index"] for parsed in scans_to_import}
    selected_index_set = set(selected_indices)
    updated_rows = []
    for row in current_row_data:
        sn = str(row["scanNumber"])
        scan_index = int(row["scan_index"])
        if scan_index in selected_index_set and scan_index not in parsed_indices:
            row["status"] = "Failed"
        elif scan_index in parsed_indices and sn in results:
            r = results[sn]
            if r["status"] == "success":
                row["status"] = "Imported"
            elif r["status"] == "skipped":
                row["status"] = "Exists"
            elif r["status"] == "failed":
                row["status"] = "Failed"
        updated_rows.append(row)

    # Build summary message
    n_success = sum(1 for r in results.values() if r["status"] == "success")
    n_failed = sum(1 for r in results.values() if r["status"] == "failed")
    n_failed += len(selected_index_set - parsed_indices)
    n_skipped = sum(1 for r in results.values() if r["status"] == "skipped")

    parts = []
    if n_success:
        parts.append(f"{n_success} imported")
    if n_skipped:
        parts.append(f"{n_skipped} skipped (already exist)")
    if n_failed:
        parts.append(f"{n_failed} failed")

    summary = f"Bulk import complete: {', '.join(parts)}."

    if n_failed:
        # Include failure details
        failures = [r["message"] for r in results.values() if r["status"] == "failed"]
        if failures:
            summary += " Errors: " + "; ".join(failures[:5])
            if len(failures) > 5:
                summary += f" ... and {len(failures) - 5} more"
        if selected_index_set - parsed_indices:
            summary += " Some selected scan elements could not be parsed; see the server log for details."

    alert_color = "success" if n_failed == 0 else ("warning" if n_success > 0 else "danger")

    return updated_rows, [], True, summary, alert_color, None
