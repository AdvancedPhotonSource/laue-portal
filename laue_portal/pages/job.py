import dash
from dash import html, dcc, callback, Input, Output, State, set_props
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
import laue_portal.database.db_utils as db_utils
import laue_portal.database.db_schema as db_schema
from sqlalchemy.orm import Session
import laue_portal.components.navbar as navbar
from dash.exceptions import PreventUpdate
import urllib.parse
import pandas as pd
from laue_portal.processing.redis_utils import STATUS_MAPPING

dash.register_page(__name__, path="/job")

layout = html.Div([
    navbar.navbar,
    dcc.Location(id='url-job-page', refresh=False),
    html.Div(
        [
            # Job Info
            html.H1(children=["Job ID: ", html.Div(id="JobID_print")],
                    style={"display":"flex", "gap":"10px", "align-items":"flex-end"},
                    className="mb-4"
            ),

            # Job Details Card
            dbc.Card([
                dbc.CardHeader(
                    dbc.Row([
                        dbc.Col(html.H4("Job Details", className="mb-0"), width="auto"),
                        dbc.Col(
                            html.Div([
                                dbc.Button("Refresh", id="refresh-job-btn", color="success", size="sm", className="me-2"),
                                dbc.Button("Cancel Job", id="cancel-job-btn", color="danger", size="sm", disabled=True)
                            ], className="d-flex justify-content-end"),
                            width=True
                        )
                    ], align="center", justify="between"),
                    className="bg-light"
                ),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.P(children=[html.Strong("Status: "), html.Div(id="Status_print")],
                                   style={"display":"flex", "gap":"5px", "align-items":"flex-end"}
                            ),
                            html.P(children=[html.Strong("Priority: "), html.Div(id="Priority_print")],
                                   style={"display":"flex", "gap":"5px", "align-items":"flex-end"}
                            ),
                            html.P(children=[html.Strong("Author: "), html.Div(id="Author_print")],
                                   style={"display":"flex", "gap":"5px", "align-items":"flex-end"}
                            ),
                            html.P(children=[html.Strong("Computer: "), html.Div(id="Computer_print")],
                                   style={"display":"flex", "gap":"5px", "align-items":"flex-end"}
                            ),
                        ], width=6),
                        dbc.Col([
                            html.P(children=[html.Strong("Submit Time: "), html.Div(id="SubmitTime_print")],
                                   style={"display":"flex", "gap":"5px", "align-items":"flex-end"}
                            ),
                            html.P(children=[html.Strong("Start Time: "), html.Div(id="StartTime_print")],
                                   style={"display":"flex", "gap":"5px", "align-items":"flex-end"}
                            ),
                            html.P(children=[html.Strong("Finish Time: "), html.Div(id="FinishTime_print")],
                                   style={"display":"flex", "gap":"5px", "align-items":"flex-end"}
                            ),
                            html.P(children=[html.Strong("Duration: "), html.Div(id="Duration_print")],
                                   style={"display":"flex", "gap":"5px", "align-items":"flex-end"}
                            ),
                        ], width=6),
                    ]),
                    
                    dbc.Row([
                        dbc.Col([
                            html.P(html.Strong("Notes:")),
                        ], width="auto", align="start"),
                        dbc.Col(
                            dbc.Textarea(
                                id="Notes_print",
                                style={"width": "100%", "minHeight": "100px"},
                                disabled=True
                            )
                        )
                    ], className="mb-3 mt-3", align="start"),
                    
                    dbc.Row([
                        dbc.Col([
                            html.P(html.Strong("Messages:")),
                        ], width="auto", align="start"),
                        dbc.Col(
                            dbc.Textarea(
                                id="Messages_print",
                                style={"width": "100%", "minHeight": "150px"},
                                disabled=True
                            )
                        )
                    ], className="mb-3", align="start")
                ])
            ], className="mb-4 shadow-sm border",
            style={"width": "100%"}),

            # Related Entities Card
            dbc.Card([
                dbc.CardHeader(
                    html.H4("Related Entities", className="mb-0"),
                    className="bg-light"
                ),
                dbc.CardBody([
                    html.Div(id="related-entities-content")
                ])
            ], className="mb-4 shadow-sm border"),

            # Job Logs/Output Card (if applicable)
            dbc.Card([
                dbc.CardHeader(
                    html.H4("Job Output", className="mb-0"),
                    className="bg-light"
                ),
                dbc.CardBody([
                    html.Div(id="job-output-content", children=[
                        html.P("No output available for this job.", className="text-muted")
                    ])
                ])
            ], className="mb-4 shadow-sm border"),
        ],
        style={'width': '100%', 'overflow-x': 'auto'}
    ),
])

"""
=======================
Callbacks
=======================
"""

@callback(
    [Output('JobID_print', 'children'),
     Output('Status_print', 'children'),
     Output('Priority_print', 'children'),
     Output('Author_print', 'children'),
     Output('Computer_print', 'children'),
     Output('SubmitTime_print', 'children'),
     Output('StartTime_print', 'children'),
     Output('FinishTime_print', 'children'),
     Output('Duration_print', 'children'),
     Output('Notes_print', 'value'),
     Output('Messages_print', 'value'),
     Output('related-entities-content', 'children'),
     Output('cancel-job-btn', 'disabled')],
    Input('url-job-page', 'href'),
    prevent_initial_call=True
)
def load_job_data(href):
    if not href:
        raise PreventUpdate

    parsed_url = urllib.parse.urlparse(href)
    query_params = urllib.parse.parse_qs(parsed_url.query)
    
    job_id = query_params.get('id', [None])[0]

    if job_id:
        try:
            job_id = int(job_id)
            with Session(db_utils.ENGINE) as session:
                # Get job data with related entities
                job = session.query(db_schema.Job).filter(db_schema.Job.job_id == job_id).first()
                
                if job:
                    # Calculate duration if both start and finish times exist
                    duration = "—"
                    if job.start_time and job.finish_time:
                        delta = job.finish_time - job.start_time
                        hours, remainder = divmod(delta.total_seconds(), 3600)
                        minutes, seconds = divmod(remainder, 60)
                        duration = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
                    elif job.start_time and job.status == 1:  # Running
                        from datetime import datetime
                        delta = datetime.now() - job.start_time
                        hours, remainder = divmod(delta.total_seconds(), 3600)
                        minutes, seconds = divmod(remainder, 60)
                        duration = f"{int(hours)}h {int(minutes)}m {int(seconds)}s (running)"
                    
                    # Format status with color
                    status_text = STATUS_MAPPING.get(job.status, f"Unknown ({job.status})")
                    status_color = {
                        0: "warning",  # Queued
                        1: "info",     # Running
                        2: "success",  # Finished
                        3: "danger",   # Failed
                        4: "secondary" # Cancelled
                    }.get(job.status, "secondary")
                    
                    status_badge = dbc.Badge(status_text, color=status_color)
                    
                    # Format times
                    submit_time = job.submit_time.strftime("%Y-%m-%d %H:%M:%S") if job.submit_time else "—"
                    start_time = job.start_time.strftime("%Y-%m-%d %H:%M:%S") if job.start_time else "—"
                    finish_time = job.finish_time.strftime("%Y-%m-%d %H:%M:%S") if job.finish_time else "—"
                    
                    # Get related entities
                    related_entities = []
                    
                    # Check for Calibration
                    calib = session.query(db_schema.Calib).filter(db_schema.Calib.job_id == job_id).first()
                    if calib:
                        related_entities.append(
                            html.Div([
                                html.Strong("Calibration: "),
                                html.A(f"Calib ID {calib.calib_id}", href=f"/calibration?id={calib.calib_id}"),
                                f" (Scan {calib.scanNumber})"
                            ], className="mb-2")
                        )
                    
                    # Check for Reconstruction
                    recon = session.query(db_schema.Recon).filter(db_schema.Recon.job_id == job_id).first()
                    if recon:
                        related_entities.append(
                            html.Div([
                                html.Strong("Reconstruction: "),
                                html.A(f"Recon ID {recon.recon_id}", href=f"/reconstruction?reconid={recon.recon_id}"),
                                f" (Scan {recon.scanNumber})"
                            ], className="mb-2")
                        )
                    
                    # Check for Wire Reconstruction
                    wirerecon = session.query(db_schema.WireRecon).filter(db_schema.WireRecon.job_id == job_id).first()
                    if wirerecon:
                        related_entities.append(
                            html.Div([
                                html.Strong("Wire Reconstruction: "),
                                html.A(f"Wire Recon ID {wirerecon.wirerecon_id}", href=f"/wire_reconstruction?wirereconid={wirerecon.wirerecon_id}"),
                                f" (Scan {wirerecon.scanNumber})"
                            ], className="mb-2")
                        )
                    
                    # Check for Peak Index
                    peakindex = session.query(db_schema.PeakIndex).filter(db_schema.PeakIndex.job_id == job_id).first()
                    if peakindex:
                        related_entities.append(
                            html.Div([
                                html.Strong("Peak Index: "),
                                html.A(f"Peak Index ID {peakindex.peakindex_id}", href=f"/indexedpeak?indexid={peakindex.peakindex_id}"),
                                f" (Scan {peakindex.scanNumber})"
                            ], className="mb-2")
                        )
                    
                    if not related_entities:
                        related_entities = [html.P("No related entities found.", className="text-muted")]
                    
                    # Enable cancel button only for pending or running jobs
                    can_cancel = job.status in [0, 1]
                    
                    return (
                        str(job_id),
                        status_badge,
                        str(job.priority),
                        job.author or "—",
                        job.computer_name,
                        submit_time,
                        start_time,
                        finish_time,
                        duration,
                        job.notes or "",
                        job.messages or "",
                        related_entities,
                        not can_cancel
                    )
                else:
                    return (
                        str(job_id),
                        "Not found",
                        "—", "—", "—", "—", "—", "—", "—",
                        "Job not found in database",
                        "",
                        [html.P("Job not found.", className="text-danger")],
                        True
                    )
                    
        except Exception as e:
            print(f"Error loading job data: {e}")
            return (
                str(job_id),
                "Error",
                "—", "—", "—", "—", "—", "—", "—",
                f"Error: {str(e)}",
                "",
                [html.P(f"Error loading job data: {str(e)}", className="text-danger")],
                True
            )
    
    return (
        "—",
        "—",
        "—", "—", "—", "—", "—", "—", "—",
        "",
        "",
        [html.P("No job ID provided.", className="text-muted")],
        True
    )

@callback(
    Output('url-job-page', 'href', allow_duplicate=True),
    Input('refresh-job-btn', 'n_clicks'),
    State('url-job-page', 'href'),
    prevent_initial_call=True
)
def refresh_job_data(n_clicks, current_href):
    if n_clicks:
        # Force a refresh by returning the same URL
        return current_href
    raise PreventUpdate
