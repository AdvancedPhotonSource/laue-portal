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
from laue_portal.processing.redis_utils import (
    STATUS_REVERSE_MAPPING,
    cancel_batch_job,
    move_batch_to_front,
)

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
                            ],
                            className="bg-light px-2 py-2 d-flex justify-content-end w-100",
                        )
                    ],
                    width=12,
                )
            ],
            className="mb-3 mt-0",
        ),
        dbc.Container(
            fluid=True,
            className="p-0",
            children=[
                dag.AgGrid(
                    id="job-table",
                    columnSize="responsiveSizeToFit",
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
                dbc.ModalHeader(dbc.ModalTitle("Confirm Cancel")),
                dbc.ModalBody(id="stop-confirm-body"),
                dbc.ModalFooter(
                    [
                        dbc.Button("Cancel Jobs", id="stop-confirm-yes-btn", color="danger", className="me-2"),
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
            header="Cancel Result",
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
    db_schema.Recon.recon_id,
    db_schema.WireRecon.wirerecon_id,
    db_schema.PeakIndex.peakindex_id,
]

CUSTOM_HEADER_NAMES = {
    "job_id": "Job ID",
    "wirerecon_id": "Recon ID (Wire)",
    "scanNumber": "Scan ID",
    "calib_id": "Calibration ID",
    "submit_time": "Date",
    "subjob_id": "SubJob ID",
    "duration_display": "Duration",
    "author": "Author",
}


def calculate_duration_display(start_time, finish_time, current_time):
    """Calculate duration display string for jobs/subjobs"""
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


def _get_jobs():
    with Session(session_utils.get_engine()) as session:
        # Query all subjobs once
        subjobs = pd.read_sql(
            session.query(db_schema.SubJob).order_by(db_schema.SubJob.subjob_id).statement, session.bind
        )

        subjob_columns = ["total_subjobs", "completed_subjobs", "failed_subjobs", "running_subjobs", "queued_subjobs"]

        # Calculate subjob statistics from the single query
        subjob_stats_df = pd.DataFrame()
        if not subjobs.empty:
            # Calculate statistics using pandas
            grouped_subjobs = subjobs.groupby("job_id")

            # Create the stats dataframe manually to avoid MultiIndex issues
            subjob_stats_df = pd.DataFrame(
                {
                    "job_id": list(grouped_subjobs.groups.keys()),
                    "total_subjobs": grouped_subjobs.size().values,
                    "completed_subjobs": grouped_subjobs["status"]
                    .apply(lambda x: (x == STATUS_REVERSE_MAPPING["Finished"]).sum())
                    .values,
                    "failed_subjobs": grouped_subjobs["status"]
                    .apply(lambda x: (x == STATUS_REVERSE_MAPPING["Failed"]).sum())
                    .values,
                    "running_subjobs": grouped_subjobs["status"]
                    .apply(lambda x: (x == STATUS_REVERSE_MAPPING["Running"]).sum())
                    .values,
                    "queued_subjobs": grouped_subjobs["status"]
                    .apply(lambda x: (x == STATUS_REVERSE_MAPPING["Queued"]).sum())
                    .values,
                }
            )

        catalog_calib = aliased(db_schema.Catalog)
        catalog_recon = aliased(db_schema.Catalog)
        catalog_wirerecon = aliased(db_schema.Catalog)
        catalog_peakindex = aliased(db_schema.Catalog)

        # Main query for jobs with related entities
        jobs = pd.read_sql(
            session.query(
                db_schema.Job,
                *REFERENCE_COLS,
                func.coalesce(
                    db_schema.Calib.scanNumber,
                    db_schema.Recon.scanNumber,
                    db_schema.WireRecon.scanNumber,
                    db_schema.PeakIndex.scanNumber,
                ).label("scanNumber"),
                func.coalesce(
                    catalog_calib.aperture,
                    catalog_recon.aperture,
                    catalog_wirerecon.aperture,
                    catalog_peakindex.aperture,
                ).label("aperture"),
                func.coalesce(
                    db_schema.Calib.author,
                    db_schema.Recon.author,
                    db_schema.WireRecon.author,
                    db_schema.PeakIndex.author,
                ).label("author"),
            )
            .outerjoin(db_schema.Calib, db_schema.Job.job_id == db_schema.Calib.job_id)
            .outerjoin(db_schema.Recon, db_schema.Job.job_id == db_schema.Recon.job_id)
            .outerjoin(db_schema.WireRecon, db_schema.Job.job_id == db_schema.WireRecon.job_id)
            .outerjoin(db_schema.PeakIndex, db_schema.Job.job_id == db_schema.PeakIndex.job_id)
            .outerjoin(catalog_calib, db_schema.Calib.scanNumber == catalog_calib.scanNumber)
            .outerjoin(catalog_recon, db_schema.Recon.scanNumber == catalog_recon.scanNumber)
            .outerjoin(catalog_wirerecon, db_schema.WireRecon.scanNumber == catalog_wirerecon.scanNumber)
            .outerjoin(catalog_peakindex, db_schema.PeakIndex.scanNumber == catalog_peakindex.scanNumber)
            .order_by(db_schema.Job.job_id.desc())
            .statement,
            session.bind,
        )

        # Merge subjob statistics with jobs
        if not subjob_stats_df.empty:
            jobs = jobs.merge(subjob_stats_df, on="job_id", how="left")
            # Fill NaN values with 0 for jobs without subjobs
            jobs[subjob_columns] = jobs[subjob_columns].fillna(0).astype(int)
        else:
            # Add empty columns if no subjobs exist
            jobs[subjob_columns] = 0

        # Pre-calculate durations for jobs
        current_time = datetime.now()

        # Create job rows
        all_rows = []
        for _, job in jobs.iterrows():
            job_row = job.to_dict()
            job_row["row_type"] = "job"
            # Calculate duration for job rows
            job_row["duration_display"] = calculate_duration_display(
                job_row.get("start_time"), job_row.get("finish_time"), current_time
            )
            all_rows.append(job_row)

        # Convert to DataFrame
        combined_df = pd.DataFrame(all_rows)

    # Format columns for ag-grid
    cols = []

    # Add explicit checkbox column as the first column
    cols.append(
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
    )

    # Get all unique columns from combined dataframe
    all_columns = combined_df.columns.tolist()

    for field_key in all_columns:
        # Skip internal columns and special columns we'll add at specific positions
        if field_key in [
            "row_type",
            "priority",
            "computer_name",
            "author",
            "completed_subjobs",
            "failed_subjobs",
            "running_subjobs",
            "queued_subjobs",
            "duration",
            "total_subjobs",
            "finish_time",
            "submit_time",
            "duration_display",
        ] + [col.key for col in REFERENCE_COLS]:
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
        elif field_key == "scanNumber":
            col_def["cellRenderer"] = "ScanLinkRenderer"  # Use the custom JS renderer
        elif field_key in ["submit_time", "start_time", "finish_time"]:
            col_def["cellRenderer"] = "DateFormatter"  # Use the date formatter for datetime fields
        elif field_key == "status":
            col_def["cellRenderer"] = "StatusRenderer"  # Use custom status renderer

        cols.append(col_def)

    # Create Job Reference column
    job_reference_col = {
        "headerName": "Job Reference",
        "valueGetter": {
            "function": """ [
                    'calib_id',
                    'recon_id',
                    'wirerecon_id',
                    'peakindex_id'
        ];"""
        },
        "cellRenderer": "JobRefsRenderer",
        "width": 250,
        "filter": True,
        "sortable": True,
        "resizable": True,
        "suppressMenuHide": True,
    }

    # Create SubJobs Progress column
    subjobs_progress_col = None
    if "total_subjobs" in all_columns:
        subjobs_progress_col = {
            "headerName": "SubJobs Progress",
            "field": "total_subjobs",
            "cellRenderer": "SubJobProgressRenderer",
            "width": 200,
            "filter": True,
            "sortable": True,
            "resizable": True,
            "suppressMenuHide": True,
        }

    # Insert Job Reference at position 1 (after checkbox column)
    cols.insert(1, job_reference_col)

    # Insert Author at position 2
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

    # Insert SubJobs Progress at position 5
    if subjobs_progress_col:
        cols.insert(5, subjobs_progress_col)

    # Create Duration column
    duration_col = {
        "headerName": "Duration",
        "field": "duration_display",
        "filter": True,
        "sortable": True,
        "resizable": True,
        "suppressMenuHide": True,
        "width": 200,
    }

    # Insert Duration at position 8
    cols.insert(8, duration_col)

    return cols, combined_df.to_dict("records")


@dash.callback(
    Output("job-table", "columnDefs"),
    Output("job-table", "rowData"),
    Input("url", "pathname"),
    prevent_initial_call=True,
)
def get_jobs(path):
    if path == "/run-monitor":
        cols, jobs = _get_jobs()
        return cols, jobs
    else:
        raise PreventUpdate


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
            html.P(f"Cancel {len(cancellable)} job(s)?"),
            html.P(f"Job IDs: {job_list}", className="text-muted mb-2"),
            html.P(
                ["Queued subjobs will be cancelled immediately. ", "Running subjobs will be left to finish naturally."],
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
    Output("job-table", "rowData", allow_duplicate=True),
    Output("job-table", "columnDefs", allow_duplicate=True),
    Input("stop-confirm-yes-btn", "n_clicks"),
    State("job-table", "selectedRows"),
    running=[
        (Output("stop-confirm-yes-btn", "disabled"), True, False),
        (
            Output("stop-confirm-yes-btn", "children"),
            [dbc.Spinner(size="sm", spinner_class_name="me-2"), "Cancelling..."],
            "Cancel Jobs",
        ),
        (Output("stop-confirm-no-btn", "disabled"), True, False),
    ],
    prevent_initial_call=True,
)
def execute_stop(n_clicks, selected_rows):
    """Execute the cancellation after confirmation."""
    if not n_clicks or not selected_rows:
        raise PreventUpdate

    cancellable = [
        row
        for row in selected_rows
        if row.get("status") in [STATUS_REVERSE_MAPPING["Queued"], STATUS_REVERSE_MAPPING["Running"]]
    ]

    if not cancellable:
        raise PreventUpdate

    results = []
    for row in cancellable:
        job_id = row["job_id"]
        result = cancel_batch_job(job_id)
        results.append((job_id, result))

    # Build summary message
    total_cancelled = sum(r["cancelled_count"] for _, r in results)
    total_skipped = sum(r["skipped_running"] for _, r in results)
    success_count = sum(1 for _, r in results if r["success"])

    lines = []
    if success_count > 0:
        lines.append(f"{success_count} job(s) cancelled.")
    if total_cancelled > 0:
        lines.append(f"{total_cancelled} queued subjob(s) stopped.")
    if total_skipped > 0:
        lines.append(f"{total_skipped} running subjob(s) left to finish.")

    # Add per-job details if there were issues
    for job_id, r in results:
        if not r["success"]:
            lines.append(f"Job {job_id}: {r['message']}")

    toast_msg = " ".join(lines) if lines else "No jobs were cancelled."
    icon = "success" if success_count > 0 else "warning"

    # Refresh the table data
    cols, jobs = _get_jobs()

    return False, toast_msg, icon, True, jobs, cols


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
            html.P(f"Move {len(movable)} job(s) to the front of the queue?"),
            html.P(f"Job IDs: {job_list}", className="text-muted mb-2"),
            html.P(
                "All queued subjobs for these jobs will be moved ahead of other queued work.",
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

    results = []
    for row in movable:
        job_id = row["job_id"]
        result = move_batch_to_front(job_id)
        results.append((job_id, result))

    total_moved = sum(r["moved_count"] for _, r in results)
    success_count = sum(1 for _, r in results if r["success"])

    lines = []
    if success_count > 0:
        lines.append(f"{success_count} job(s) moved to front.")
    if total_moved > 0:
        lines.append(f"{total_moved} subjob(s) repositioned.")

    for job_id, r in results:
        if not r["success"]:
            lines.append(f"Job {job_id}: {r['message']}")

    toast_msg = " ".join(lines) if lines else "No jobs were moved."
    icon = "success" if success_count > 0 else "warning"

    return False, toast_msg, icon, True
