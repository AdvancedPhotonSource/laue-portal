"""Job detail page: one run's state, counters, configuration, versions, and failed-input diagnostics.

Everything shown comes from the job row's stored counters and the run's constant
artifacts (``request.json``, ``run.json``, ``failures.jsonl``). Nothing enumerates
inputs: the failure report is paged, the run log is truncated to its tail. A
small interval refreshes only the live fields while the run is active.
"""

import urllib.parse
from datetime import datetime

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, ctx, dcc, html
from dash.exceptions import PreventUpdate
from sqlalchemy.orm import Session

import laue_portal.components.navbar as navbar
import laue_portal.database.db_schema as db_schema
import laue_portal.database.session_utils as session_utils
from laue_portal.processing.queue.controls import cancel_run
from laue_portal.processing.queue.core import RUN_POLICY
from laue_portal.services import run_summary
from laue_portal.workflows.execution import JobStatus, RunPhase
from laue_portal.workflows.manifest import FailureRecord
from laue_portal.workflows.progress import heartbeat_age_seconds

dash.register_page(__name__, path="/job")

LIVE_REFRESH_SECONDS = 5
STATUS_COLORS = {
    int(JobStatus.QUEUED): "warning",
    int(JobStatus.RUNNING): "info",
    int(JobStatus.FINISHED): "success",
    int(JobStatus.FAILED): "danger",
    int(JobStatus.CANCELLED): "secondary",
}
CATEGORY_COLORS = {
    "input": "warning",
    "numerical": "danger",
    "memory": "danger",
    "error": "danger",
    "cancelled": "secondary",
    "interrupted": "secondary",
    "not_run": "secondary",
}
STOP_EXPLANATION = (
    "A queued run is removed from the queue and none of its inputs are processed. A running run stops taking "
    "new inputs, finishes the inputs already in flight, keeps every completed result, and is recorded as "
    "Cancelled with its unprocessed inputs listed as not run."
)


def _field(label, component_id):
    return html.P(
        children=[html.Strong(f"{label}: "), html.Div(id=component_id)],
        style={"display": "flex", "gap": "5px", "align-items": "flex-end"},
    )


layout = html.Div(
    [
        navbar.navbar,
        dcc.Location(id="url-job-page", refresh=False),
        # Live fields refresh only while the run is queued or running.
        dcc.Interval(id="job-refresh-interval", interval=LIVE_REFRESH_SECONDS * 1000, n_intervals=0, disabled=True),
        dcc.Store(id="job-failures-offset", data=0),
        html.Div(
            [
                html.H1(
                    id="job-header",
                    style={"display": "flex", "gap": "10px", "align-items": "baseline", "flexWrap": "wrap"},
                    className="mb-4",
                ),
                dbc.Card(
                    [
                        dbc.CardHeader(
                            dbc.Row(
                                [
                                    dbc.Col(html.H4("Job Details", className="mb-0"), width="auto"),
                                    dbc.Col(
                                        html.Div(
                                            [
                                                dbc.Button(
                                                    "Refresh",
                                                    id="refresh-job-btn",
                                                    color="success",
                                                    size="sm",
                                                    className="me-2",
                                                ),
                                                dbc.Button(
                                                    "Stop Run",
                                                    id="cancel-job-btn",
                                                    color="danger",
                                                    size="sm",
                                                    disabled=True,
                                                ),
                                            ],
                                            className="d-flex justify-content-end",
                                        ),
                                        width=True,
                                    ),
                                ],
                                align="center",
                                justify="between",
                            ),
                            className="bg-light",
                        ),
                        dbc.CardBody(
                            [
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            [
                                                _field("Status", "Status_print"),
                                                _field("Priority", "Priority_print"),
                                                _field("Computer", "Computer_print"),
                                            ],
                                            width=6,
                                        ),
                                        dbc.Col(
                                            [
                                                _field("Submit Time", "SubmitTime_print"),
                                                _field("Start Time", "StartTime_print"),
                                                _field("Finish Time", "FinishTime_print"),
                                                _field("Duration", "Duration_print"),
                                            ],
                                            width=6,
                                        ),
                                    ]
                                ),
                                dbc.Row(
                                    [
                                        dbc.Col([html.P(html.Strong("Messages:"))], width="auto", align="start"),
                                        dbc.Col(
                                            dbc.Textarea(
                                                id="Messages_print",
                                                style={"width": "100%", "minHeight": "150px"},
                                                disabled=True,
                                            )
                                        ),
                                    ],
                                    className="mb-3 mt-3",
                                    align="start",
                                ),
                            ]
                        ),
                    ],
                    className="mb-4 shadow-sm border",
                    style={"width": "100%"},
                ),
                dbc.Card(
                    [
                        dbc.CardHeader(html.H4("Run Progress", className="mb-0"), className="bg-light"),
                        dbc.CardBody(html.Div(id="run-progress-content")),
                    ],
                    className="mb-4 shadow-sm border",
                ),
                dbc.Card(
                    [
                        dbc.CardHeader(html.H4("Run Configuration", className="mb-0"), className="bg-light"),
                        dbc.CardBody(html.Div(id="run-configuration-content")),
                    ],
                    className="mb-4 shadow-sm border",
                ),
                dbc.Card(
                    [
                        dbc.CardHeader(
                            dbc.Row(
                                [
                                    dbc.Col(html.H4("Failed Inputs", className="mb-0"), width="auto"),
                                    dbc.Col(
                                        html.Div(
                                            [
                                                html.Span(id="failed-inputs-range", className="text-muted small me-3"),
                                                dbc.Button(
                                                    "Previous",
                                                    id="failed-inputs-prev-btn",
                                                    size="sm",
                                                    color="secondary",
                                                    outline=True,
                                                    className="me-2",
                                                    disabled=True,
                                                ),
                                                dbc.Button(
                                                    "Next",
                                                    id="failed-inputs-next-btn",
                                                    size="sm",
                                                    color="secondary",
                                                    outline=True,
                                                    disabled=True,
                                                ),
                                            ],
                                            className="d-flex justify-content-end align-items-center",
                                        ),
                                        width=True,
                                    ),
                                ],
                                align="center",
                                justify="between",
                            ),
                            className="bg-light",
                        ),
                        dbc.CardBody(html.Div(id="failed-inputs-content")),
                    ],
                    className="mb-4 shadow-sm border",
                ),
            ],
            style={"width": "100%", "overflow-x": "auto"},
        ),
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("Stop Run")),
                dbc.ModalBody(
                    [
                        html.P("Stop this run?"),
                        html.P(STOP_EXPLANATION, className="small text-muted"),
                    ]
                ),
                dbc.ModalFooter(
                    [
                        dbc.Button("Stop Run", id="cancel-job-confirm-yes-btn", color="danger", className="me-2"),
                        dbc.Button("Go Back", id="cancel-job-confirm-no-btn", color="secondary"),
                    ]
                ),
            ],
            id="cancel-job-confirm-modal",
            is_open=False,
            centered=True,
        ),
        dbc.Toast(
            id="cancel-job-result-toast",
            header="Stop Run",
            is_open=False,
            dismissable=True,
            duration=6000,
            icon="info",
            style={"position": "fixed", "top": 66, "right": 10, "width": 400, "zIndex": 1050},
        ),
    ]
)


# ---------------------------------------------------------------------------
# Pure builders (tested directly)
# ---------------------------------------------------------------------------


def _job_id_from_href(href):
    if not href:
        return None
    query = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
    value = query.get("job_id", [None])[0]
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _format_time(value):
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else "—"


def _format_seconds(total_seconds: float) -> str:
    hours, remainder = divmod(int(total_seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}h {minutes}m {seconds}s"


def duration_text(job, *, now: datetime | None = None) -> str:
    """Span of a finished run, or the time so far for a running one."""

    if job.start_time and job.finish_time:
        return _format_seconds((job.finish_time - job.start_time).total_seconds())
    if job.start_time and job.status == JobStatus.RUNNING:
        return _format_seconds(((now or datetime.now()) - job.start_time).total_seconds()) + " (running)"
    return "—"


def status_badge(progress):
    """Status badge plus the finer execution phase when it says more than the status."""

    badge = dbc.Badge(progress.status_name, color=STATUS_COLORS.get(progress.status, "secondary"))
    phase = progress.phase
    if phase and phase not in (progress.status_name.lower(), None):
        note = phase.replace("_", " ")
        if phase == RunPhase.INTERRUPTED:
            note = "interrupted: the service or worker stopped; the run is not resumed"
        elif phase == RunPhase.FINALIZING:
            note = "finalizing: closing and validating outputs"
        elif phase in (RunPhase.CREATED, RunPhase.PUBLISHED):
            note = f"{phase}: not yet handed to the queue"
        return html.Span([badge, html.Small(f" {note}", className="text-muted ms-2")])
    return badge


def progress_content(details: run_summary.RunDetails, *, now: datetime | None = None, policy=None):
    """Counters, a segmented bar, and the run's liveness in words."""

    progress = details.progress
    policy = policy or RUN_POLICY
    if progress.n_inputs == 0:
        return [html.P("This job selected no inputs.", className="text-muted mb-0")]

    total = progress.n_inputs
    bars = []
    for count, color, label, striped in (
        (progress.n_succeeded, "success", "succeeded", False),
        (progress.n_failed, "danger", "failed", False),
        (progress.n_not_run, "secondary", "not run", False),
        (progress.n_pending, "warning", "pending", progress.status == JobStatus.RUNNING),
    ):
        if count:
            bars.append(
                dbc.Progress(
                    value=100 * count / total,
                    color=color,
                    bar=True,
                    striped=striped,
                    animated=striped,
                    label=f"{count} {label}",
                )
            )

    counters = dbc.Row(
        [
            dbc.Col(
                [html.H3(str(value), className="mb-0"), html.Small(label, className="text-muted")],
                className="text-center",
            )
            for label, value in (
                ("inputs", progress.n_inputs),
                ("processed", progress.n_processed),
                ("succeeded", progress.n_succeeded),
                ("failed", progress.n_failed),
                ("not run", progress.n_not_run),
                ("pending", progress.n_pending),
            )
        ],
        className="mb-3",
    )

    notes = []
    if progress.status == JobStatus.RUNNING:
        age = heartbeat_age_seconds(progress, now=now)
        if age is None:
            notes.append(html.Span("No heartbeat recorded yet.", className="text-muted"))
        elif age > policy.stale_heartbeat_seconds:
            notes.append(
                html.Span(
                    f"No heartbeat for {int(age)} s (limit {int(policy.stale_heartbeat_seconds)} s): the run "
                    "process is probably gone. The next worker start records this run as interrupted; it is not "
                    "resumed.",
                    className="text-danger",
                )
            )
        else:
            notes.append(html.Span(f"Last heartbeat {int(age)} s ago.", className="text-muted"))
    if progress.cancel_requested_at is not None and not progress.is_terminal:
        notes.append(
            html.Span(
                f" Stop requested at {_format_time(progress.cancel_requested_at)}: the run finishes work in flight "
                "and keeps completed results.",
                className="text-warning",
            )
        )
    if progress.is_terminal:
        notes.append(
            html.Span(
                f"Processed {progress.n_processed} of {progress.n_inputs} input(s): {progress.counter_summary()}.",
                className="text-muted",
            )
        )

    return [
        counters,
        dbc.Progress(bars, style={"height": "22px"}, className="mb-2"),
        html.Div(notes, className="small"),
    ]


def _definition_table(rows: list[tuple[str, str]]):
    return html.Table(
        [
            html.Tbody(
                [
                    html.Tr(
                        [
                            html.Th(label, className="text-muted fw-normal pe-3 text-nowrap", style={"width": "1%"}),
                            html.Td(value, style={"wordBreak": "break-word"}),
                        ]
                    )
                    for label, value in rows
                ]
            )
        ],
        className="table table-sm table-borderless mb-0 small",
    )


def _artifact_links(details: run_summary.RunDetails):
    items = []
    for name, path in sorted(details.artifacts.items()):
        items.append(html.Li([html.Span(f"{name}: ", className="text-muted"), html.Code(path)]))
    if details.run_directory:
        items.append(html.Li([html.Span("run directory: ", className="text-muted"), html.Code(details.run_directory)]))
    if details.progress.failure_report_path:
        items.append(
            html.Li(
                [html.Span("failure report: ", className="text-muted"), html.Code(details.progress.failure_report_path)]
            )
        )
    return (
        html.Ul(items, className="small mb-0") if items else html.Span("No artifacts recorded.", className="text-muted")
    )


def configuration_content(details: run_summary.RunDetails):
    """Submitted configuration, effective execution and versions, artifacts, warnings, and the log tail."""

    sections = []
    heading = []
    if details.display_id:
        heading.append(html.Strong(details.display_id))
    if details.kind:
        heading.append(html.Span(f" {details.kind.replace('_', ' ')}", className="text-muted"))
    if heading:
        sections.append(html.P(heading, className="mb-2"))

    for problem in details.problems:
        sections.append(dbc.Alert(problem, color="warning", className="py-2 small"))

    summary = details.summary or {}
    if summary.get("validation_error"):
        sections.append(
            dbc.Alert(
                [html.Strong("Output validation failed: "), str(summary["validation_error"])],
                color="danger",
                className="py-2 small",
            )
        )
    for warning in summary.get("warnings") or []:
        sections.append(dbc.Alert(str(warning), color="warning", className="py-2 small"))

    request_rows = run_summary.request_rows(details)
    execution_rows = run_summary.execution_rows(details)
    history_rows = run_summary.history_rows(details)

    if details.progress.is_terminal and details.progress.status != JobStatus.FINISHED:
        partial_note = None
        if details.artifacts.get("results"):
            partial_note = (
                "This run did not finish, but its published results hold every input that succeeded and can be "
                "viewed from the linked result page."
            )
        elif details.artifacts.get("reconstruction"):
            partial_note = (
                "Completed point files are available from this incomplete run. Check the scan catalog for point "
                "status and the failure report for recorded errors."
            )
        if partial_note:
            sections.append(dbc.Alert(partial_note, color="info", className="py-2 small"))

    columns = []
    if request_rows:
        columns.append(dbc.Col([html.H6("Submitted request"), _definition_table(request_rows)], md=6))
    if execution_rows:
        columns.append(dbc.Col([html.H6("Execution and versions"), _definition_table(execution_rows)], md=6))
    if history_rows:
        columns.append(dbc.Col([html.H6("Historical per-input records"), _definition_table(history_rows)], md=6))
    if columns:
        sections.append(dbc.Row(columns, className="mb-3"))
    elif details.is_historical or (details.request is None and details.summary is None):
        sections.append(
            html.P(
                "No request or run summary file exists for this job. Runs recorded before whole-run execution keep "
                "only their counters and exported diagnostics.",
                className="text-muted small",
            )
        )

    sections.append(html.H6("Artifacts"))
    sections.append(_artifact_links(details))

    log_tail = details.log_tail
    if log_tail:
        title = "Run log"
        if details.log_truncated:
            title += f" (last {len(log_tail)} of {len(log_tail) + details.log_truncated} lines)"
        sections.append(html.H6(title, className="mt-3"))
        sections.append(
            html.Pre(
                "\n".join(log_tail),
                className="small mb-0",
                style={
                    "whiteSpace": "pre-wrap",
                    "backgroundColor": "#f8f9fa",
                    "padding": "10px",
                    "borderRadius": "4px",
                    "maxHeight": "300px",
                    "overflowY": "auto",
                },
            )
        )
    return sections


def _shorten(text: str, limit: int = 300) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def failure_table(records: list[FailureRecord], *, offset: int, total: int, has_more: bool):
    """One page of the failure report as a table, plus the range text and paging flags."""

    if total == 0 and not records:
        body = html.P("No failed or unattempted inputs.", className="text-muted mb-0")
        return body, "", True, True
    if not records and offset == 0:
        body = html.P(
            f"{total} input(s) did not succeed, but the failure report is not available on this host.",
            className="text-muted mb-0",
        )
        return body, "", True, True

    rows = []
    for record in records:
        position = "—" if record.index is None else str(record.index)
        message = record.message or ""
        rows.append(
            html.Tr(
                [
                    html.Td(position, className="text-nowrap"),
                    html.Td(html.Code(record.input_id) if record.input_id else "—", title=record.source or ""),
                    html.Td(dbc.Badge(record.category, color=CATEGORY_COLORS.get(record.category, "secondary"))),
                    html.Td(record.error_type or "—", className="text-nowrap"),
                    html.Td(_shorten(message), title=message, style={"wordBreak": "break-word"}),
                ]
            )
        )
    table = html.Table(
        [
            html.Thead(
                html.Tr([html.Th("#"), html.Th("Input"), html.Th("Category"), html.Th("Error"), html.Th("Message")])
            ),
            html.Tbody(rows),
        ],
        className="table table-sm table-hover small mb-0",
    )
    first = offset + 1
    last = offset + len(records)
    range_text = f"Showing {first}–{last} of {total}" if total >= last else f"Showing {first}–{last}"
    return table, range_text, offset == 0, not has_more


def _load(job_id: int):
    """Job row (detached copies of the fields the page prints) and run details."""

    with Session(session_utils.get_engine()) as session:
        details = run_summary.load_run_details(session, job_id)
        if details is None:
            return None, None
        job = session.get(db_schema.Job, job_id)
        snapshot = {
            "priority": job.priority,
            "computer_name": job.computer_name,
            "submit_time": job.submit_time,
            "start_time": job.start_time,
            "finish_time": job.finish_time,
            "status": job.status,
            "messages": job.messages or "",
        }
        links = _related_links(session, job_id)
    return (snapshot, links), details


def _related_links(session, job_id):
    related = []
    calib = session.query(db_schema.Calib).filter(db_schema.Calib.job_id == job_id).first()
    if calib:
        related.append(
            html.Span(
                [
                    html.A(f"Calibration ID: {calib.calib_id}", href=f"/calibration?calib_id={calib.calib_id}"),
                    " | ",
                    html.A(f"Scan ID: {calib.scanNumber}", href=f"/scan?scan_id={calib.scanNumber}"),
                ]
            )
        )
    reconstruction = (
        session.query(db_schema.ReconstructionRun).filter(db_schema.ReconstructionRun.job_id == job_id).first()
    )
    if reconstruction:
        detail_path = "/wire_reconstruction" if reconstruction.method == "wire" else "/reconstruction"
        related.append(
            html.Span(
                [
                    html.A(
                        f"Reconstruction R{reconstruction.id}",
                        href=f"{detail_path}?reconstruction_id={reconstruction.id}",
                    ),
                    " | ",
                    html.A(
                        f"Scan ID: {reconstruction.scan_number}", href=f"/scan?scan_id={reconstruction.scan_number}"
                    ),
                ]
            )
        )
    indexing = session.query(db_schema.IndexingRun).filter(db_schema.IndexingRun.job_id == job_id).first()
    if indexing:
        related.append(
            html.Span(
                [
                    html.A(f"Indexing I{indexing.id}", href=f"/peakindexing?indexing_id={indexing.id}"),
                    " | ",
                    html.A(f"Scan ID: {indexing.scan_number}", href=f"/scan?scan_id={indexing.scan_number}"),
                ]
            )
        )
    return related


def _header(job_id, related_links):
    content = [html.Span(f"Job ID: {job_id}" if job_id is not None else "Job ID: —")]
    for link in related_links:
        content.append(html.Span(" • ", className="mx-2", style={"color": "#6c757d"}))
        content.append(html.Span(link, style={"fontSize": "0.7em"}))
    return content


class _Snapshot:
    """Attribute access over the detached job fields, for the duration helper."""

    def __init__(self, values):
        self.__dict__.update(values)


def _live_outputs(snapshot, details, *, now=None):
    progress = details.progress
    return (
        status_badge(progress),
        _format_time(snapshot["finish_time"]),
        duration_text(_Snapshot(snapshot), now=now),
        snapshot["messages"],
        not progress.is_active,
        progress_content(details, now=now),
        not progress.is_active,  # interval disabled once terminal
    )


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------


@callback(
    Output("job-header", "children"),
    Output("Status_print", "children"),
    Output("Priority_print", "children"),
    Output("Computer_print", "children"),
    Output("SubmitTime_print", "children"),
    Output("StartTime_print", "children"),
    Output("FinishTime_print", "children"),
    Output("Duration_print", "children"),
    Output("Messages_print", "value"),
    Output("cancel-job-btn", "disabled"),
    Output("run-progress-content", "children"),
    Output("run-configuration-content", "children"),
    Output("job-refresh-interval", "disabled"),
    Output("job-failures-offset", "data"),
    Input("url-job-page", "href"),
    prevent_initial_call=True,
)
def load_job_data(href):
    if not href:
        raise PreventUpdate
    job_id = _job_id_from_href(href)
    if job_id is None:
        return (_header(None, []), "—", "—", "—", "—", "—", "—", "—", "", True, "", "", True, 0)
    try:
        job, details = _load(job_id)
    except Exception as error:  # the page must render whatever went wrong
        return (_header(job_id, []), "Error", "—", "—", "—", "—", "—", "—", f"Error: {error}", True, "", "", True, 0)
    if job is None:
        return (
            _header(job_id, []),
            "Not found",
            "—",
            "—",
            "—",
            "—",
            "—",
            "—",
            "Job not found in database",
            True,
            html.P("No run recorded for this job.", className="text-muted mb-0"),
            "",
            True,
            0,
        )
    snapshot, links = job
    status, finish_time, duration, messages, cancel_disabled, progress, interval_disabled = _live_outputs(
        snapshot, details
    )
    return (
        _header(job_id, links),
        status,
        str(snapshot["priority"]),
        snapshot["computer_name"],
        _format_time(snapshot["submit_time"]),
        _format_time(snapshot["start_time"]),
        finish_time,
        duration,
        messages,
        cancel_disabled,
        progress,
        configuration_content(details),
        interval_disabled,
        0,
    )


@callback(
    Output("Status_print", "children", allow_duplicate=True),
    Output("FinishTime_print", "children", allow_duplicate=True),
    Output("Duration_print", "children", allow_duplicate=True),
    Output("Messages_print", "value", allow_duplicate=True),
    Output("cancel-job-btn", "disabled", allow_duplicate=True),
    Output("run-progress-content", "children", allow_duplicate=True),
    Output("job-refresh-interval", "disabled", allow_duplicate=True),
    Input("job-refresh-interval", "n_intervals"),
    State("url-job-page", "href"),
    running=[(Output("job-refresh-interval", "disabled"), True, False)],
    prevent_initial_call=True,
)
def refresh_live_fields(n_intervals, href):
    """Refresh the fields that change while a run is active; stop polling once it is terminal."""

    job_id = _job_id_from_href(href)
    if job_id is None:
        raise PreventUpdate
    job, details = _load(job_id)
    if job is None:
        raise PreventUpdate
    snapshot, _ = job
    return _live_outputs(snapshot, details)


@callback(
    Output("failed-inputs-content", "children"),
    Output("failed-inputs-range", "children"),
    Output("failed-inputs-prev-btn", "disabled"),
    Output("failed-inputs-next-btn", "disabled"),
    Output("job-failures-offset", "data", allow_duplicate=True),
    Input("job-failures-offset", "data"),
    Input("failed-inputs-prev-btn", "n_clicks"),
    Input("failed-inputs-next-btn", "n_clicks"),
    Input("job-refresh-interval", "disabled"),
    State("url-job-page", "href"),
    prevent_initial_call=True,
)
def page_failed_inputs(offset, previous_clicks, next_clicks, interval_disabled, href):
    """Show one bounded page of the failure report; reloads when the run finishes."""

    job_id = _job_id_from_href(href)
    if job_id is None:
        raise PreventUpdate
    offset = int(offset or 0)
    trigger = ctx.triggered_id
    if trigger == "failed-inputs-prev-btn":
        offset = max(offset - run_summary.FAILURE_PAGE_SIZE, 0)
    elif trigger == "failed-inputs-next-btn":
        offset += run_summary.FAILURE_PAGE_SIZE
    elif trigger == "job-refresh-interval" and not interval_disabled:
        raise PreventUpdate

    with Session(session_utils.get_engine()) as session:
        details = run_summary.load_run_details(session, job_id)
    if details is None:
        return html.P("No run recorded for this job.", className="text-muted mb-0"), "", True, True, 0
    records, has_more = run_summary.failure_records(details, offset=offset)
    if not records and offset > 0:  # past the end (report shorter than expected): go back one page
        offset = max(offset - run_summary.FAILURE_PAGE_SIZE, 0)
        records, has_more = run_summary.failure_records(details, offset=offset)
    body, range_text, prev_disabled, next_disabled = failure_table(
        records, offset=offset, total=run_summary.failure_total(details), has_more=has_more
    )
    return body, range_text, prev_disabled, next_disabled, offset


@callback(
    Output("url-job-page", "href", allow_duplicate=True),
    Input("refresh-job-btn", "n_clicks"),
    State("url-job-page", "href"),
    prevent_initial_call=True,
)
def refresh_job_data(n_clicks, current_href):
    if n_clicks:
        return current_href
    raise PreventUpdate


@callback(
    Output("cancel-job-confirm-modal", "is_open", allow_duplicate=True),
    Input("cancel-job-btn", "n_clicks"),
    prevent_initial_call=True,
)
def open_cancel_confirmation(n_clicks):
    if n_clicks:
        return True
    raise PreventUpdate


@callback(
    Output("cancel-job-confirm-modal", "is_open", allow_duplicate=True),
    Input("cancel-job-confirm-no-btn", "n_clicks"),
    prevent_initial_call=True,
)
def close_cancel_confirmation(n_clicks):
    if n_clicks:
        return False
    raise PreventUpdate


@callback(
    Output("cancel-job-confirm-modal", "is_open"),
    Output("cancel-job-result-toast", "children"),
    Output("cancel-job-result-toast", "icon"),
    Output("cancel-job-result-toast", "is_open"),
    Output("url-job-page", "href", allow_duplicate=True),
    Input("cancel-job-confirm-yes-btn", "n_clicks"),
    State("url-job-page", "href"),
    running=[
        (Output("cancel-job-confirm-yes-btn", "disabled"), True, False),
        (
            Output("cancel-job-confirm-yes-btn", "children"),
            [dbc.Spinner(size="sm", spinner_class_name="me-2"), "Stopping..."],
            "Stop Run",
        ),
        (Output("cancel-job-confirm-no-btn", "disabled"), True, False),
    ],
    prevent_initial_call=True,
)
def execute_cancel(n_clicks, href):
    """Stop the run after confirmation, then reload the page."""

    if not n_clicks or not href:
        raise PreventUpdate
    job_id = _job_id_from_href(href)
    if job_id is None:
        raise PreventUpdate
    result = cancel_run(job_id)
    icon = "success" if result["success"] else "warning"
    return False, result["message"] or "Could not stop the run.", icon, True, href
