from datetime import datetime

import dash
import dash_ag_grid as dag
import dash_bootstrap_components as dbc
import pandas as pd
from dash import Input, Output, State, dcc, html
from dash.exceptions import PreventUpdate
from sqlalchemy import func
from sqlalchemy.orm import Session, aliased

import laue_portal.components.navbar as navbar
import laue_portal.database.db_schema as db_schema
import laue_portal.database.session_utils as session_utils
from laue_portal.components import live_rows
from laue_portal.processing.queue.controls import cancel_run, move_run_to_front
from laue_portal.processing.queue.core import STATUS_REVERSE_MAPPING
from laue_portal.workflows.progress import active_or_changed_since, derived_progress_columns

dash.register_page(__name__)

layout = html.Div(
    [
        navbar.navbar,
        dcc.Location(id="url", refresh=False),
        # Secondary action bar aligned to right
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Nav(
                            [
                                dbc.Button(
                                    "Stop",
                                    id="run-monitor-page-stop-btn",
                                    style={"backgroundColor": "#6c757d", "borderColor": "#6c757d"},
                                    className="me-2",
                                ),
                                dbc.Button(
                                    "Move to Front",
                                    id="run-monitor-page-move-to-front-btn",
                                    style={"backgroundColor": "#6c757d", "borderColor": "#6c757d"},
                                    className="me-2",
                                ),
                                dbc.Button(
                                    "Refresh",
                                    id="run-monitor-page-refresh-btn",
                                    color="success",
                                    className="me-2",
                                ),
                                html.Span(
                                    id="run-monitor-refresh-note",
                                    className="text-muted small align-self-center me-2",
                                ),
                            ],
                            className="bg-light px-2 py-2 d-flex justify-content-end w-100",
                        )
                    ],
                    width=12,
                )
            ],
            className="mb-3 mt-0",
        ),
        # Timed refresh sends only active or newly finalized runs as a row transaction.
        dcc.Interval(id="run-monitor-refresh-interval", interval=live_rows.REFRESH_SECONDS * 1000, n_intervals=0),
        dcc.Store(id="run-monitor-refresh-state"),
        dbc.Container(
            fluid=True,
            className="p-0",
            children=[
                dag.AgGrid(
                    id="job-table",
                    columnSize="responsiveSizeToFit",
                    getRowId="params.data.job_id",
                    defaultColDef={
                        "filter": True,
                    },
                    dashGridOptions={
                        "pagination": True,
                        "paginationPageSize": 20,
                        "domLayout": "autoHeight",
                        "rowHeight": 32,
                        "rowSelection": "multiple",
                        "suppressRowClickSelection": True,
                        "animateRows": True,
                        "enableCellTextSelection": True,  # Enable text selection for copying
                    },
                    style={"height": "calc(100vh - 150px)", "width": "100%"},
                    className="ag-theme-alpine",
                )
            ],
        ),
        # Confirmation modal for Stop action
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("Stop Runs")),
                dbc.ModalBody(id="stop-confirm-body"),
                dbc.ModalFooter(
                    [
                        dbc.Button("Stop Runs", id="stop-confirm-yes-btn", color="danger", className="me-2"),
                        dbc.Button("Go Back", id="stop-confirm-no-btn", color="secondary"),
                    ]
                ),
            ],
            id="stop-confirm-modal",
            is_open=False,
            centered=True,
        ),
        # Toast for cancel result feedback
        dbc.Toast(
            id="stop-result-toast",
            header="Stop Runs",
            is_open=False,
            dismissable=True,
            duration=6000,
            icon="info",
            style={"position": "fixed", "top": 66, "right": 10, "width": 400, "zIndex": 1050},
        ),
        # Confirmation modal for Move to Front action
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("Move to Front")),
                dbc.ModalBody(id="move-front-confirm-body"),
                dbc.ModalFooter(
                    [
                        dbc.Button("Move to Front", id="move-front-confirm-yes-btn", color="primary", className="me-2"),
                        dbc.Button("Go Back", id="move-front-confirm-no-btn", color="secondary"),
                    ]
                ),
            ],
            id="move-front-confirm-modal",
            is_open=False,
            centered=True,
        ),
        # Toast for move-to-front result feedback
        dbc.Toast(
            id="move-front-result-toast",
            header="Move to Front",
            is_open=False,
            dismissable=True,
            duration=6000,
            icon="info",
            style={"position": "fixed", "top": 66, "right": 10, "width": 400, "zIndex": 1050},
        ),
    ],
)

REFERENCE_COLS = [
    db_schema.Calib.calib_id,
    db_schema.ReconstructionRun.id.label("reconstruction_id"),
    db_schema.IndexingRun.id.label("indexing_id"),
]

CUSTOM_HEADER_NAMES = {
    "job_id": "Job ID",
    "reconstruction_id": "Reconstruction ID",
    "indexing_id": "Indexing ID",
    "scan_number": "Scan ID",
    "calib_id": "Calibration ID",
    "submit_time": "Date",
    "duration_display": "Duration",
    "author": "Author",
}


def calculate_duration_display(start_time, finish_time, current_time):
    """Duration text for a run: finished runs show their span, active runs the time so far."""
    if pd.notna(start_time):
        if pd.notna(finish_time):
            # Completed
            duration = finish_time - start_time
        else:
            # Running
            duration = current_time - start_time

        # Convert to total seconds and format as HH:MM:SS
        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        formatted = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        if pd.isna(finish_time):
            formatted += " (running)"

        return formatted
    return None


PROGRESS_FIELDS = ["n_inputs", "n_succeeded", "n_failed", "n_not_run", "n_processed", "n_pending"]
HIDDEN_FIELDS = [
    "row_type",
    "priority",
    "computer_name",
    "author",
    "duration",
    "finish_time",
    "submit_time",
    "duration_display",
    "phase",
    "updated_at",
    "heartbeat_at",
    "cancel_requested_at",
    "queue_job_id",
    "run_directory",
    "manifest_path",
    "manifest_digest",
    "request_path",
    "failure_report_path",
    *PROGRESS_FIELDS,
]


def _job_rows(criterion=None) -> list[dict]:
    """Rows for the run table; ``criterion`` restricts the query for a partial refresh.

    Progress comes from the counters stored on each job; no per-input rows exist.
    """

    with Session(session_utils.get_engine()) as session:
        catalog_calib = aliased(db_schema.Catalog)
        catalog_reconstruction = aliased(db_schema.Catalog)
        catalog_indexing = aliased(db_schema.Catalog)

        query = (
            session.query(
                db_schema.Job,
                *derived_progress_columns(),
                *REFERENCE_COLS,
                db_schema.ReconstructionRun.method.label("reconstruction_method"),
                func.coalesce(
                    db_schema.Calib.scanNumber,
                    db_schema.ReconstructionRun.scan_number,
                    db_schema.IndexingRun.scan_number,
                ).label("scan_number"),
                func.coalesce(
                    catalog_calib.aperture,
                    catalog_reconstruction.aperture,
                    catalog_indexing.aperture,
                ).label("aperture"),
                func.coalesce(
                    db_schema.Calib.author,
                    db_schema.ReconstructionRun.author,
                    db_schema.IndexingRun.author,
                ).label("author"),
            )
            .outerjoin(db_schema.Calib, db_schema.Job.job_id == db_schema.Calib.job_id)
            .outerjoin(db_schema.ReconstructionRun, db_schema.Job.job_id == db_schema.ReconstructionRun.job_id)
            .outerjoin(db_schema.IndexingRun, db_schema.Job.job_id == db_schema.IndexingRun.job_id)
            .outerjoin(catalog_calib, db_schema.Calib.scanNumber == catalog_calib.scanNumber)
            .outerjoin(
                catalog_reconstruction,
                db_schema.ReconstructionRun.scan_number == catalog_reconstruction.scanNumber,
            )
            .outerjoin(catalog_indexing, db_schema.IndexingRun.scan_number == catalog_indexing.scanNumber)
        )
        if criterion is not None:
            query = query.filter(criterion)
        jobs = pd.read_sql(query.order_by(db_schema.Job.job_id.desc()).statement, session.bind)

    jobs[PROGRESS_FIELDS] = jobs[PROGRESS_FIELDS].fillna(0).astype(int)
    current_time = datetime.now()
    rows = []
    for _, job in jobs.iterrows():
        row = job.to_dict()
        row["row_type"] = "job"
        row["duration_display"] = calculate_duration_display(
            row.get("start_time"), row.get("finish_time"), current_time
        )
        rows.append(row)
    return rows


def _column_defs(all_columns: list[str]) -> list[dict]:
    """AG Grid column definitions for the run table."""

    cols = [
        {
            "headerName": "",
            "field": "checkbox",
            "checkboxSelection": True,
            "headerCheckboxSelection": True,
            "width": 60,
            "pinned": "left",
            "sortable": False,
            "filter": False,
            "resizable": False,
            "suppressMenu": True,
            "floatingFilter": False,
            "cellClass": "ag-checkbox-cell",
            "headerClass": "ag-checkbox-header",
        }
    ]

    for field_key in all_columns:
        if field_key in HIDDEN_FIELDS or field_key in {col.key for col in REFERENCE_COLS}:
            continue

        header_name = CUSTOM_HEADER_NAMES.get(field_key, field_key.replace("_", " ").title())
        col_def = {
            "headerName": header_name,
            "field": field_key,
            "filter": True,
            "sortable": True,
            "resizable": True,
            "floatingFilter": True,
            "unSortIcon": True,
        }
        if field_key == "job_id":
            col_def["cellRenderer"] = "JobIdLinkRenderer"
            col_def["width"] = 175
        elif field_key == "dataset_id":
            col_def["cellRenderer"] = "DatasetIdScanLinkRenderer"
        elif field_key == "scan_number":
            col_def["cellRenderer"] = "ScanLinkRenderer"
        elif field_key in ["submit_time", "start_time", "finish_time"]:
            col_def["cellRenderer"] = "DateFormatter"
        elif field_key == "status":
            col_def["cellRenderer"] = "StatusRenderer"
        cols.append(col_def)

    job_reference_col = {
        "headerName": "Job Reference",
        "valueGetter": {
            "function": """ [
                    'calib_id',
                    'reconstruction_id',
                    'indexing_id'
        ];"""
        },
        "cellRenderer": "JobRefsRenderer",
        "width": 250,
        "filter": True,
        "sortable": True,
        "resizable": True,
        "suppressMenuHide": True,
    }
    cols.insert(1, job_reference_col)

    author_col = {
        "headerName": "Author",
        "field": "author",
        "filter": True,
        "sortable": True,
        "resizable": True,
        "floatingFilter": True,
        "unSortIcon": True,
    }
    cols.insert(2, author_col)

    if "n_inputs" in all_columns:
        cols.insert(
            5,
            {
                "headerName": "Run Progress",
                "field": "n_processed",
                "cellRenderer": "RunProgressRenderer",
                "width": 220,
                "filter": "agNumberColumnFilter",
                "sortable": True,
                "resizable": True,
                "suppressMenuHide": True,
            },
        )

    duration_col = {
        "headerName": "Duration",
        "field": "duration_display",
        "filter": True,
        "sortable": True,
        "resizable": True,
        "suppressMenuHide": True,
        "width": 200,
    }
    cols.insert(8, duration_col)
    return cols


def _get_jobs():
    """Full load: column definitions and every run row."""

    rows = _job_rows()
    columns = list(rows[0].keys()) if rows else ["job_id", "status", "start_time", "n_inputs"]
    return _column_defs(columns), rows


def _refresh_note(rows: list[dict], transaction: dict | None) -> str:
    active = sum(1 for row in rows if row.get("status") in (0, 1))
    if not rows:
        return f"Auto-refresh every {live_rows.REFRESH_SECONDS} s; no active runs."
    changed = len(transaction.get("update", [])) + len(transaction.get("add", [])) if transaction else 0
    return f"Auto-refresh every {live_rows.REFRESH_SECONDS} s; {active} active run(s), {changed} row(s) updated."


@dash.callback(
    Output("job-table", "columnDefs"),
    Output("job-table", "rowData"),
    Output("run-monitor-refresh-state", "data"),
    Input("url", "pathname"),
    prevent_initial_call=True,
)
def get_jobs(path):
    if path == "/run-monitor":
        cols, jobs = _get_jobs()
        return cols, jobs, live_rows.initial_state(jobs, "job_id")
    else:
        raise PreventUpdate


@dash.callback(
    Output("job-table", "rowTransaction"),
    Output("run-monitor-refresh-state", "data", allow_duplicate=True),
    Output("run-monitor-refresh-note", "children"),
    Input("run-monitor-refresh-interval", "n_intervals"),
    Input("run-monitor-page-refresh-btn", "n_clicks"),
    State("run-monitor-refresh-state", "data"),
    State("url", "pathname"),
    running=[(Output("run-monitor-refresh-interval", "disabled"), True, False)],
    prevent_initial_call=True,
)
def refresh_jobs(n_intervals, n_clicks, state, path):
    """Send only active or newly finalized runs; the grid keeps its selection, sort, filters, and page."""

    if path != "/run-monitor" or state is None:
        raise PreventUpdate
    rows = _job_rows(active_or_changed_since(live_rows.since_from_state(state)))
    transaction, next_state = live_rows.transaction(rows, "job_id", state)
    return transaction if transaction else dash.no_update, next_state, _refresh_note(rows, transaction)


@dash.callback(
    Output("run-monitor-page-stop-btn", "disabled"),
    Output("run-monitor-page-stop-btn", "style"),
    Output("run-monitor-page-move-to-front-btn", "disabled"),
    Output("run-monitor-page-move-to-front-btn", "style"),
    Input("job-table", "selectedRows"),
    prevent_initial_call=False,
)
def update_button_states(selected_rows):
    enabled_style = {"backgroundColor": "#1abc9c", "borderColor": "#1abc9c"}
    disabled_style = {"backgroundColor": "#6c757d", "borderColor": "#6c757d"}

    has_selection = selected_rows and len(selected_rows) > 0

    has_cancellable = False
    has_queued = False
    if has_selection:
        for row in selected_rows:
            status = row.get("status")
            if status in [STATUS_REVERSE_MAPPING["Queued"], STATUS_REVERSE_MAPPING["Running"]]:
                has_cancellable = True
            if status == STATUS_REVERSE_MAPPING["Queued"]:
                has_queued = True

    return (
        not has_cancellable,
        disabled_style if not has_cancellable else enabled_style,  # Stop
        not has_queued,
        disabled_style if not has_queued else enabled_style,  # Move to Front
    )


@dash.callback(
    Output("stop-confirm-modal", "is_open", allow_duplicate=True),
    Output("stop-confirm-body", "children"),
    Input("run-monitor-page-stop-btn", "n_clicks"),
    State("job-table", "selectedRows"),
    prevent_initial_call=True,
)
def open_stop_confirmation(n_clicks, selected_rows):
    """Open confirmation modal when Stop button is clicked."""
    if not n_clicks or not selected_rows:
        raise PreventUpdate

    # Filter to only cancellable jobs (Queued or Running)
    cancellable = [
        row
        for row in selected_rows
        if row.get("status") in [STATUS_REVERSE_MAPPING["Queued"], STATUS_REVERSE_MAPPING["Running"]]
    ]

    if not cancellable:
        raise PreventUpdate

    job_ids = [row["job_id"] for row in cancellable]
    job_list = ", ".join(str(jid) for jid in job_ids)

    body = html.Div(
        [
            html.P(f"Stop {len(cancellable)} run(s)?"),
            html.P(f"Job IDs: {job_list}", className="text-muted mb-2"),
            html.P(
                [
                    "A queued run is removed from the queue and none of its inputs are processed. ",
                    "A running run stops taking new inputs, finishes the inputs already in flight, keeps every ",
                    "completed result, and is recorded as Cancelled with its unprocessed inputs listed as not run.",
                ],
                className="small text-muted",
            ),
        ]
    )

    return True, body


@dash.callback(
    Output("stop-confirm-modal", "is_open", allow_duplicate=True),
    Input("stop-confirm-no-btn", "n_clicks"),
    prevent_initial_call=True,
)
def close_stop_confirmation(n_clicks):
    """Close the confirmation modal without cancelling."""
    if n_clicks:
        return False
    raise PreventUpdate


@dash.callback(
    Output("stop-confirm-modal", "is_open"),
    Output("stop-result-toast", "children"),
    Output("stop-result-toast", "icon"),
    Output("stop-result-toast", "is_open"),
    Output("job-table", "rowTransaction", allow_duplicate=True),
    Input("stop-confirm-yes-btn", "n_clicks"),
    State("job-table", "selectedRows"),
    running=[
        (Output("stop-confirm-yes-btn", "disabled"), True, False),
        (
            Output("stop-confirm-yes-btn", "children"),
            [dbc.Spinner(size="sm", spinner_class_name="me-2"), "Stopping..."],
            "Stop Runs",
        ),
        (Output("stop-confirm-no-btn", "disabled"), True, False),
    ],
    prevent_initial_call=True,
)
def execute_stop(n_clicks, selected_rows):
    """Stop the selected runs after confirmation and update only their rows."""
    if not n_clicks or not selected_rows:
        raise PreventUpdate

    cancellable = [
        row
        for row in selected_rows
        if row.get("status") in [STATUS_REVERSE_MAPPING["Queued"], STATUS_REVERSE_MAPPING["Running"]]
    ]

    if not cancellable:
        raise PreventUpdate

    results = [(row["job_id"], cancel_run(row["job_id"])) for row in cancellable]
    toast_msg, icon = summarize_stop_results(results)
    job_ids = [job_id for job_id, _ in results]
    rows = _job_rows(db_schema.Job.job_id.in_(job_ids))
    return False, toast_msg, icon, True, {"update": rows} if rows else dash.no_update


def summarize_stop_results(results) -> tuple[str, str]:
    """One toast line per outcome: removed from the queue, asked to stop, or not stoppable."""

    removed = [job_id for job_id, r in results if r["state"] == "cancelled"]
    requested = [job_id for job_id, r in results if r["state"] == "requested"]
    lines = []
    if removed:
        lines.append(f"{len(removed)} queued run(s) removed from the queue; no inputs processed.")
    if requested:
        pending = sum(r["n_pending"] for _, r in results if r["state"] == "requested")
        lines.append(
            f"{len(requested)} running run(s) asked to stop: in-flight inputs finish, completed results are kept, "
            f"{pending} pending input(s) will be recorded as not run."
        )
    for job_id, r in results:
        if not r["success"]:
            lines.append(f"Job {job_id}: {r['message']}")
    toast_msg = " ".join(lines) if lines else "No runs were stopped."
    icon = "success" if removed or requested else "warning"
    return toast_msg, icon


@dash.callback(
    Output("move-front-confirm-modal", "is_open", allow_duplicate=True),
    Output("move-front-confirm-body", "children"),
    Input("run-monitor-page-move-to-front-btn", "n_clicks"),
    State("job-table", "selectedRows"),
    prevent_initial_call=True,
)
def open_move_front_confirmation(n_clicks, selected_rows):
    """Open confirmation modal when Move to Front button is clicked."""
    if not n_clicks or not selected_rows:
        raise PreventUpdate

    movable = [row for row in selected_rows if row.get("status") == STATUS_REVERSE_MAPPING["Queued"]]

    if not movable:
        raise PreventUpdate

    job_ids = [row["job_id"] for row in movable]
    job_list = ", ".join(str(jid) for jid in job_ids)

    body = html.Div(
        [
            html.P(f"Move {len(movable)} queued run(s) to the front of the queue?"),
            html.P(f"Job IDs: {job_list}", className="text-muted mb-2"),
            html.P(
                "The selected runs start before the other queued runs. A run that is already active is never "
                "interrupted; the moved runs wait for it to finish.",
                className="small text-muted",
            ),
        ]
    )

    return True, body


@dash.callback(
    Output("move-front-confirm-modal", "is_open", allow_duplicate=True),
    Input("move-front-confirm-no-btn", "n_clicks"),
    prevent_initial_call=True,
)
def close_move_front_confirmation(n_clicks):
    """Close the move-to-front confirmation modal."""
    if n_clicks:
        return False
    raise PreventUpdate


@dash.callback(
    Output("move-front-confirm-modal", "is_open"),
    Output("move-front-result-toast", "children"),
    Output("move-front-result-toast", "icon"),
    Output("move-front-result-toast", "is_open"),
    Input("move-front-confirm-yes-btn", "n_clicks"),
    State("job-table", "selectedRows"),
    running=[
        (Output("move-front-confirm-yes-btn", "disabled"), True, False),
        (
            Output("move-front-confirm-yes-btn", "children"),
            [dbc.Spinner(size="sm", spinner_class_name="me-2"), "Moving..."],
            "Move to Front",
        ),
        (Output("move-front-confirm-no-btn", "disabled"), True, False),
    ],
    prevent_initial_call=True,
)
def execute_move_to_front(n_clicks, selected_rows):
    """Execute the move-to-front after confirmation."""
    if not n_clicks or not selected_rows:
        raise PreventUpdate

    movable = [row for row in selected_rows if row.get("status") == STATUS_REVERSE_MAPPING["Queued"]]

    if not movable:
        raise PreventUpdate

    results = [(row["job_id"], move_run_to_front(row["job_id"])) for row in movable]
    success_count = sum(1 for _, r in results if r["success"])

    lines = []
    if success_count > 0:
        lines.append(f"{success_count} queued run(s) moved ahead of the other queued runs; active work continues.")
    for job_id, r in results:
        if not r["success"]:
            lines.append(f"Job {job_id}: {r['message']}")

    toast_msg = " ".join(lines) if lines else "No runs were moved."
    icon = "success" if success_count > 0 else "warning"

    return False, toast_msg, icon, True
