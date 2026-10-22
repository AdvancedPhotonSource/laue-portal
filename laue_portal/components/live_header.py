"""Ready controls and active-run progress for the live page."""

from datetime import datetime

import dash_bootstrap_components as dbc
from dash import dcc, html

from laue_portal.workflows.live import TERMINAL

BUTTONS = ("validate", "start", "stop", "resume")


def header_view(status):
    active = status is not None and status["state"] not in TERMINAL
    recovery = active and status["state"] == "recovery"
    action = status["action"] if active else None
    visible = (not active, not active, active, recovery)
    disabled = (active, active, not active or (bool(action) and not recovery), not recovery)
    return {
        "className": "lp-form-card lp-live-header "
        + ("lp-form-card--teal lp-live-header--active" if active else "lp-form-card--slate lp-live-header--ready"),
        "phase": ("Stopping" if action and not recovery else status["state"].capitalize())
        if active
        else "Ready to start",
        "details": run_details(status) if active else [],
        "details_style": {} if active else {"display": "none"},
        "disabled": disabled,
        "styles": tuple({} if show else {"display": "none"} for show in visible),
    }


def build_header(status=None):
    view = header_view(status)
    controls = []
    for name, disabled, style in zip(BUTTONS, view["disabled"], view["styles"], strict=True):
        controls.append(
            dbc.Button(
                "Start live run" if name == "start" else name.capitalize(),
                id=f"live-{name}",
                color="danger" if name == "stop" else "primary",
                outline=name != "start",
                size="sm",
                disabled=disabled,
                style=style,
            )
        )
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [html.H2("Live"), html.Span(view["phase"], id="live-phase", className="lp-live-phase")],
                        className="lp-live-heading",
                    ),
                    html.Div(controls, className="lp-form-card-actions"),
                ],
                className="lp-form-card-head",
            ),
            html.Div(
                view["details"],
                id="live-status",
                className="lp-form-card-body lp-live-status",
                style=view["details_style"],
            ),
        ],
        id="live-header",
        className=view["className"],
    )


def run_details(status):
    links = []
    for name, run_id, job_id, href in (
        (
            "Reconstruction",
            status["reconstruction_id"],
            status["reconstruction_job_id"],
            "/wire_reconstruction?reconstruction_id=",
        ),
        ("Indexing", status["indexing_id"], status["indexing_job_id"], "/peakindexing?indexing_id="),
    ):
        if run_id:
            prefix = "R" if name == "Reconstruction" else "I"
            links.append(
                html.Div(
                    [
                        dcc.Link(f"{name} {prefix}{run_id}", href=f"{href}{run_id}", className="lp-live-run-name"),
                        dcc.Link(f"Job {job_id}", href=f"/job?job_id={job_id}", className="lp-live-job-link"),
                    ],
                    className="lp-live-run-link",
                )
            )
    counters = [
        html.Span([html.Strong(str(count)), f" {label}"])
        for count, label in (
            [(status["arrived"], "arrived")]
            + ([(status["reconstructed"], "reconstructed")] if status["reconstruction_id"] else [])
            + ([(status["indexed_points"], "index-processed")] if status["indexing_id"] else [])
            + [(status["pending"], "pending"), (status["failures"], "failed")]
        )
    ]
    if status["published_at"]:
        published = datetime.fromisoformat(status["published_at"]).isoformat(sep=" ", timespec="seconds")
        counters.append(
            html.Time(f"Published {published}", dateTime=status["published_at"], className="lp-live-published")
        )
    details = [html.Div(links, className="lp-live-overview"), html.Div(counters, className="lp-live-counters")]
    if status["error"]:
        details.append(dbc.Alert(status["error"], color="warning"))
    arrivals = status.get("arrival_status") or {}
    if arrivals.get("error"):
        details.append(dbc.Alert(arrivals["error"], color="warning"))
    elif arrivals.get("daq_status") and arrivals["daq_status"] != "running":
        details.append(html.Small(f"DAQ: {arrivals['daq_status']}"))
    return details
