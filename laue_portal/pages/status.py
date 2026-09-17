import os
from datetime import datetime

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html
from dash.dependencies import Input, Output

import laue_portal.components.navbar as navbar
import laue_portal.database.session_utils as session_utils
from laue_portal import config
from laue_portal.processing.queue import core as queue_core
from laue_portal.processing.queue.inspection import get_queue_stats, get_workers_info
from laue_portal.workflows.progress import ACTIVE_STATUSES, RunProgress, heartbeat_age_seconds

dash.register_page(__name__, path="/")

# Build the layout
layout = html.Div(
    [
        navbar.navbar,
        dbc.Container(
            [
                # Auto-refresh interval (every 5 seconds)
                dcc.Interval(
                    id="status-refresh-interval",
                    interval=5 * 1000,  # in milliseconds
                    n_intervals=0,
                ),
                # Row 1: Welcome and Connection Status
                dbc.Row(
                    [
                        # Welcome Card
                        dbc.Col(
                            [
                                dbc.Card(
                                    [
                                        dbc.CardHeader(html.H4("Welcome to the 3DMN Laue Portal", className="mb-0")),
                                        dbc.CardBody(
                                            [
                                                html.P(
                                                    [
                                                        "The 3DMN Laue Portal is a data processing platform for ",
                                                        "Laue X-ray diffraction experiments at beamline 34-ID-E.",
                                                    ],
                                                    className="mb-3",
                                                ),
                                                html.H6("Capabilities:", className="mb-2"),
                                                html.Ul(
                                                    [
                                                        html.Li("Scan management and tracking"),
                                                        html.Li("Wire-based depth reconstruction"),
                                                        html.Li("Coded aperture reconstruction"),
                                                        html.Li("Automated peak indexing"),
                                                        html.Li("Whole-run job queue"),
                                                    ],
                                                    className="mb-0",
                                                ),
                                            ]
                                        ),
                                    ],
                                    className="h-100",
                                )
                            ],
                            md=6,
                            className="mb-4",
                        ),
                        # Connection Status Card
                        dbc.Col(
                            [
                                dbc.Card(
                                    [
                                        dbc.CardHeader(html.H4("Connection Status", className="mb-0")),
                                        dbc.CardBody([html.Div(id="connection-status-content")]),
                                    ],
                                    className="h-100",
                                )
                            ],
                            md=6,
                            className="mb-4",
                        ),
                    ]
                ),
                # Row 2: System Resources and Quick Actions
                dbc.Row(
                    [
                        # System Resources Card
                        dbc.Col(
                            [
                                dbc.Card(
                                    [
                                        dbc.CardHeader(html.H4("System Resources", className="mb-0")),
                                        dbc.CardBody([html.Div(id="system-resources-content")]),
                                    ],
                                    className="h-100",
                                )
                            ],
                            md=6,
                            className="mb-4",
                        ),
                        # Quick Actions Card
                        dbc.Col(
                            [
                                dbc.Card(
                                    [
                                        dbc.CardHeader(html.H4("Quick Actions", className="mb-0")),
                                        dbc.CardBody(
                                            [
                                                dbc.ListGroup(
                                                    [
                                                        dbc.ListGroupItem(
                                                            [html.I(className="bi bi-list-ul me-2"), "View All Scans"],
                                                            href="/scans",
                                                            action=True,
                                                            className="d-flex align-items-center",
                                                        ),
                                                        dbc.ListGroupItem(
                                                            [
                                                                html.I(className="bi bi-gear me-2"),
                                                                "Create Wire Reconstruction",
                                                            ],
                                                            href="/create-wire-reconstruction",
                                                            action=True,
                                                            className="d-flex align-items-center",
                                                        ),
                                                        dbc.ListGroupItem(
                                                            [
                                                                html.I(className="bi bi-grid-3x3 me-2"),
                                                                "Create Coded Aperture Reconstruction",
                                                            ],
                                                            href="/create-reconstruction",
                                                            action=True,
                                                            className="d-flex align-items-center",
                                                        ),
                                                        dbc.ListGroupItem(
                                                            [
                                                                html.I(className="bi bi-search me-2"),
                                                                "Create Peak Indexing",
                                                            ],
                                                            href="/create-peakindexing",
                                                            action=True,
                                                            className="d-flex align-items-center",
                                                        ),
                                                        dbc.ListGroupItem(
                                                            [
                                                                html.I(className="bi bi-activity me-2"),
                                                                "Monitor Job Queue",
                                                            ],
                                                            href="/run-monitor",
                                                            action=True,
                                                            className="d-flex align-items-center",
                                                        ),
                                                    ],
                                                    flush=True,
                                                )
                                            ]
                                        ),
                                    ],
                                    className="h-100",
                                )
                            ],
                            md=6,
                            className="mb-4",
                        ),
                    ]
                ),
                # Row 3: Active runs from the database (the authority for run state)
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dbc.Card(
                                    [
                                        dbc.CardHeader(html.H4("Active Runs", className="mb-0")),
                                        dbc.CardBody([html.Div(id="active-runs-content")]),
                                    ],
                                )
                            ],
                            md=12,
                            className="mb-4",
                        ),
                    ]
                ),
            ],
            fluid=True,
            className="mt-4",
        ),
    ]
)


def active_run_rows(now=None):
    """Queued and running jobs with their counters and liveness, from stored state only."""

    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from laue_portal.database import db_schema

    now = now or datetime.now()
    stale_after = queue_core.RUN_POLICY.stale_heartbeat_seconds
    rows = []
    with Session(session_utils.get_engine()) as session:
        jobs = session.scalars(
            select(db_schema.Job).where(db_schema.Job.status.in_(ACTIVE_STATUSES)).order_by(db_schema.Job.job_id.desc())
        ).all()
        for job in jobs:
            progress = RunProgress.from_job(job)
            age = heartbeat_age_seconds(progress, now=now)
            if job.indexing_run is not None:
                display = f"Indexing I{job.indexing_run.id}"
            elif job.reconstruction_run is not None:
                display = f"Reconstruction R{job.reconstruction_run.id}"
            else:
                display = "Job"
            stale = progress.status == 1 and (age is None or age > stale_after)
            rows.append(
                {
                    "job_id": job.job_id,
                    "display": display,
                    "status": progress.status_name,
                    "phase": progress.phase,
                    "progress": progress.progress_text() or "no inputs",
                    "heartbeat_age": None if age is None else int(age),
                    "stale": stale,
                    "cancel_requested": progress.cancel_requested_at is not None,
                }
            )
    return rows


def active_runs_content(rows):
    if not rows:
        return html.P("No queued or running runs.", className="text-muted mb-0")
    items = []
    for row in rows:
        notes = []
        if row["cancel_requested"]:
            notes.append(dbc.Badge("stop requested", color="warning", className="ms-2"))
        if row["status"] == "Running":
            if row["stale"]:
                notes.append(
                    dbc.Badge(
                        "no heartbeat; reconciled as interrupted at the next worker start",
                        color="danger",
                        className="ms-2",
                    )
                )
            elif row["heartbeat_age"] is not None:
                notes.append(html.Small(f" heartbeat {row['heartbeat_age']} s ago", className="text-muted ms-2"))
        items.append(
            html.Li(
                [
                    html.A(f"Job {row['job_id']}", href=f"/job?job_id={row['job_id']}"),
                    html.Span(f" {row['display']}: ", className="text-muted"),
                    dbc.Badge(row["status"], color="info" if row["status"] == "Running" else "warning"),
                    html.Span(f" {row['progress']}", className="ms-2"),
                    *notes,
                ],
                className="mb-1",
            )
        )
    return html.Ul(items, className="list-unstyled mb-0 small")


@dash.callback(Output("active-runs-content", "children"), Input("status-refresh-interval", "n_intervals"))
def update_active_runs(n):
    try:
        return active_runs_content(active_run_rows())
    except Exception as error:
        return dbc.Alert(f"Could not read run state: {error}", color="warning", className="mb-0")


# Callback to update connection status
@dash.callback(Output("connection-status-content", "children"), Input("status-refresh-interval", "n_intervals"))
def update_connection_status(n):
    """Update the connection status card with current system information."""

    # Check Redis connection
    redis_connected = queue_core.check_redis_connection()
    redis_startup_status = queue_core.REDIS_CONNECTED_AT_STARTUP

    # Database path
    db_path = config.db_file
    db_exists = os.path.exists(db_path)

    # Server info
    dash_url = f"http://{config.DASH_CONFIG['host']}:{config.DASH_CONFIG['port']}"
    redis_url = f"{config.REDIS_CONFIG['host']}:{config.REDIS_CONFIG['port']}"

    return [
        # Database Status
        html.Div(
            [
                html.Strong("Database: "),
                dbc.Badge(
                    "Connected" if db_exists else "Not Found",
                    color="success" if db_exists else "danger",
                    className="me-2",
                ),
                html.Br(),
                html.Small(db_path, className="text-muted"),
            ],
            className="mb-3",
        ),
        # Dash Server Status
        html.Div(
            [
                html.Strong("Dash Server: "),
                dbc.Badge("Running", color="success", className="me-2"),
                html.Br(),
                html.Small(dash_url, className="text-muted"),
            ],
            className="mb-3",
        ),
        # Redis Status
        html.Div(
            [
                html.Strong("Redis Queue: "),
                dbc.Badge(
                    "Connected" if redis_connected else "Disconnected",
                    color="success" if redis_connected else "danger",
                    className="me-2",
                ),
                html.Br(),
                html.Small(redis_url, className="text-muted"),
                html.Br(),
                html.Small(
                    f"Startup status: {'Connected' if redis_startup_status else 'Disconnected'}"
                    if redis_startup_status is not None
                    else "Startup status: Unknown",
                    className="text-muted fst-italic",
                ),
            ],
            className="mb-0",
        ),
    ]


# Callback to update system resources
@dash.callback(Output("system-resources-content", "children"), Input("status-refresh-interval", "n_intervals"))
def update_system_resources(n):
    """Update the system resources card with queue and worker information."""

    try:
        # Get queue statistics
        queue_stats = get_queue_stats()

        # Get worker information
        workers_info = get_workers_info()

        return [
            # Queue Statistics
            html.H6("Queue", className="mb-2"),
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Div(
                                [
                                    html.H3(queue_stats.get("queued", 0), className="mb-0 text-primary"),
                                    html.Small("Queued", className="text-muted"),
                                ],
                                className="text-center",
                            )
                        ],
                        width=6,
                    ),
                    dbc.Col(
                        [
                            html.Div(
                                [
                                    html.H3(queue_stats.get("started", 0), className="mb-0 text-info"),
                                    html.Small("Running", className="text-muted"),
                                ],
                                className="text-center",
                            )
                        ],
                        width=6,
                    ),
                ],
                className="mb-3",
            ),
            html.Hr(),
            # Worker Information
            html.H6("Workers:", className="mb-2"),
            html.Div(
                [
                    dbc.Badge(
                        f"{len(workers_info)} Active" if workers_info else "No Workers",
                        color="success" if workers_info else "warning",
                        className="me-2",
                    ),
                    html.Br() if workers_info else None,
                    html.Div(
                        [
                            html.Div(
                                [html.Small([html.Strong(f"{worker['name']}: "), f"{worker['state']}"])],
                                className="mb-1",
                            )
                            for worker in workers_info
                        ]
                        if workers_info
                        else [],
                        className="mt-2",
                    ),
                ],
                className="mb-0",
            ),
        ]

    except Exception:
        return [
            dbc.Alert(
                [html.I(className="bi bi-exclamation-triangle me-2"), "No system data. Redis is not connected."],
                color="warning",
                className="mb-0",
            )
        ]
