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
import laue_portal.database.session_utils as session_utils

dash.register_page(__name__, path="/job")

layout = html.Div([
    navbar.navbar,
    dcc.Location(id='url-job-page', refresh=False),
    html.Div(
        [
            # Job Info
            html.H1(id="job-header",
                    style={"display":"flex", "gap":"10px", "align-items":"baseline", "flexWrap":"wrap"},
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
                            html.P(html.Strong("Messages:")),
                        ], width="auto", align="start"),
                        dbc.Col(
                            dbc.Textarea(
                                id="Messages_print",
                                style={"width": "100%", "minHeight": "150px"},
                                disabled=True
                            )
                        )
                    ], className="mb-3 mt-3", align="start")
                ])
            ], className="mb-4 shadow-sm border",
            style={"width": "100%"}),

            # SubJob Output Card
            dbc.Card([
                dbc.CardHeader(
                    html.H4("SubJob Output", className="mb-0"),
                    className="bg-light"
                ),
                dbc.CardBody([
                    html.Div(id="subjob-output-content", children=[
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
    [Output('job-header', 'children'),
     Output('Status_print', 'children'),
     Output('Priority_print', 'children'),
     Output('Computer_print', 'children'),
     Output('SubmitTime_print', 'children'),
     Output('StartTime_print', 'children'),
     Output('FinishTime_print', 'children'),
     Output('Duration_print', 'children'),
     Output('Messages_print', 'value'),
     Output('cancel-job-btn', 'disabled'),
     Output('subjob-output-content', 'children')],
    Input('url-job-page', 'href'),
    prevent_initial_call=True
)
def load_job_data(href):
    if not href:
        raise PreventUpdate

    parsed_url = urllib.parse.urlparse(href)
    query_params = urllib.parse.parse_qs(parsed_url.query)
    
    job_id = query_params.get('job_id', [None])[0]

    if job_id:
        try:
            job_id = int(job_id)
            with Session(session_utils.get_engine()) as session:
                job_data = session.query(db_schema.Job).filter(db_schema.Job.job_id == job_id).first()
                
                if job_data:
                    # Calculate duration if both start and finish times exist
                    duration = "—"
                    if job_data.start_time and job_data.finish_time:
                        delta = job_data.finish_time - job_data.start_time
                        hours, remainder = divmod(delta.total_seconds(), 3600)
                        minutes, seconds = divmod(remainder, 60)
                        duration = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
                    elif job_data.start_time and job_data.status == 1:  # Running
                        from datetime import datetime
                        delta = datetime.now() - job_data.start_time
                        hours, remainder = divmod(delta.total_seconds(), 3600)
                        minutes, seconds = divmod(remainder, 60)
                        duration = f"{int(hours)}h {int(minutes)}m {int(seconds)}s (running)"
                    
                    # Format status with color
                    status_text = STATUS_MAPPING.get(job_data.status, f"Unknown ({job_data.status})")
                    status_color = {
                        0: "warning",  # Queued
                        1: "info",     # Running
                        2: "success",  # Finished
                        3: "danger",   # Failed
                        4: "secondary" # Cancelled
                    }.get(job_data.status, "secondary")
                    
                    status_badge = dbc.Badge(status_text, color=status_color)
                    
                    # Format times
                    submit_time = job_data.submit_time.strftime("%Y-%m-%d %H:%M:%S") if job_data.submit_time else "—"
                    start_time = job_data.start_time.strftime("%Y-%m-%d %H:%M:%S") if job_data.start_time else "—"
                    finish_time = job_data.finish_time.strftime("%Y-%m-%d %H:%M:%S") if job_data.finish_time else "—"
                    
                    # Get related links for header
                    related_links = []
                    
                    # Check for Calibration
                    calib_data = session.query(db_schema.Calib).filter(db_schema.Calib.job_id == job_id).first()
                    if calib_data:
                        related_links.append(
                            html.Span([
                                html.A(f"Calibration ID: {calib_data.calib_id}", href=f"/calibration?calib_id={calib_data.calib_id}"),
                                " | ",
                                html.A(f"Scan ID: {calib_data.scanNumber}", href=f"/scan?scan_id={calib_data.scanNumber}")
                            ])
                        )
                    
                    # Check for Reconstruction
                    recon_data = session.query(db_schema.Recon).filter(db_schema.Recon.job_id == job_id).first()
                    if recon_data:
                        related_links.append(
                            html.Span([
                                html.A(f"Reconstruction ID: {recon_data.recon_id}", href=f"/reconstruction?recon_id={recon_data.recon_id}"),
                                " | ",
                                html.A(f"Scan ID: {recon_data.scanNumber}", href=f"/scan?scan_id={recon_data.scanNumber}")
                            ])
                        )
                    
                    # Check for Wire Reconstruction
                    wirerecon_data = session.query(db_schema.WireRecon).filter(db_schema.WireRecon.job_id == job_id).first()
                    if wirerecon_data:
                        related_links.append(
                            html.Span([
                                html.A(f"Wire Reconstruction ID: {wirerecon_data.wirerecon_id}", href=f"/wire_reconstruction?wirerecon_id={wirerecon_data.wirerecon_id}"),
                                " | ",
                                html.A(f"Scan ID: {wirerecon_data.scanNumber}", href=f"/scan?scan_id={wirerecon_data.scanNumber}")
                            ])
                        )
                    
                    # Check for Peak Index
                    peakindex_data = session.query(db_schema.PeakIndex).filter(db_schema.PeakIndex.job_id == job_id).first()
                    if peakindex_data:
                        related_links.append(
                            html.Span([
                                html.A(f"Peak Indexing ID: {peakindex_data.peakindex_id}", href=f"/peakindexing?peakindex_id={peakindex_data.peakindex_id}"),
                                " | ",
                                html.A(f"Scan ID: {peakindex_data.scanNumber}", href=f"/scan?scan_id={peakindex_data.scanNumber}")
                            ])
                        )
                    
                    # Build header with links
                    header_content = [html.Span(f"Job ID: {job_id}")]
                    
                    if related_links:
                        # Add separator before links
                        header_content.append(html.Span(" • ", className="mx-2", style={"color": "#6c757d"}))
                        
                        # Add each link group with separators
                        for i, link in enumerate(related_links):
                            if i > 0:
                                header_content.append(html.Span(" • ", className="mx-2", style={"color": "#6c757d"}))
                            header_content.append(html.Span(link, style={"fontSize": "0.7em"}))
                    
                    # Get subjob messages for SubJob Output section
                    subjob_output = []
                    subjobs_data = session.query(db_schema.SubJob).filter(db_schema.SubJob.job_id == job_id).order_by(db_schema.SubJob.subjob_id).all()
                    
                    if subjobs_data:
                        for subjob in subjobs_data:
                            # Format subjob status
                            subjob_status_text = STATUS_MAPPING.get(subjob.status, f"Unknown ({subjob.status})")
                            subjob_status_color = {
                                0: "warning",  # Queued
                                1: "info",     # Running
                                2: "success",  # Finished
                                3: "danger",   # Failed
                                4: "secondary" # Cancelled
                            }.get(subjob.status, "secondary")
                            
                            subjob_badge = dbc.Badge(subjob_status_text, color=subjob_status_color, className="me-2")
                            
                            # Build card body content
                            card_body_content = []
                            
                            # Add command section if available
                            if subjob.command:
                                card_body_content.append(
                                    html.Div([
                                        html.Strong("Command:", className="text-primary"),
                                        html.Pre(
                                            subjob.command,
                                            style={
                                                "whiteSpace": "pre-wrap",
                                                "wordBreak": "break-all",
                                                "backgroundColor": "#1e1e1e",
                                                "color": "#d4d4d4",
                                                "padding": "10px",
                                                "borderRadius": "4px",
                                                "fontSize": "0.8rem",
                                                "fontFamily": "monospace",
                                                "marginTop": "5px",
                                                "marginBottom": "10px",
                                                "maxHeight": "150px",
                                                "overflowY": "auto"
                                            }
                                        )
                                    ])
                                )
                            
                            # Add output section
                            card_body_content.append(
                                html.Div([
                                    html.Strong("Output:") if subjob.command else None,
                                    html.Pre(
                                        subjob.messages or "No output available",
                                        style={
                                            "whiteSpace": "pre-wrap",
                                            "wordBreak": "break-word",
                                            "backgroundColor": "#f8f9fa",
                                            "padding": "10px",
                                            "borderRadius": "4px",
                                            "fontSize": "0.875rem",
                                            "maxHeight": "300px",
                                            "overflowY": "auto",
                                            "marginTop": "5px" if subjob.command else "0"
                                        }
                                    )
                                ])
                            )
                            
                            # Create subjob output card
                            subjob_card = dbc.Card([
                                dbc.CardHeader([
                                    html.Span([
                                        html.Strong(f"SubJob {subjob.subjob_id}"),
                                        " - ",
                                        subjob_badge,
                                        html.Small(f"Computer: {subjob.computer_name}", className="text-muted ms-2")
                                    ])
                                ], className="py-2"),
                                dbc.CardBody(card_body_content, className="py-2")
                            ], className="mb-2")
                            
                            subjob_output.append(subjob_card)
                    else:
                        subjob_output = [html.P("No subjobs found for this job.", className="text-muted")]
                    
                    # Enable cancel button only for pending or running jobs
                    can_cancel = job_data.status in [0, 1]
                    
                    return (
                        header_content,
                        status_badge,
                        str(job_data.priority),
                        job_data.computer_name,
                        submit_time,
                        start_time,
                        finish_time,
                        duration,
                        job_data.messages or "",
                        not can_cancel,
                        subjob_output
                    )
                else:
                    return (
                        [html.Span(f"Job ID: {job_id}")],
                        "Not found",
                        "—",
                        "—",
                        "—",
                        "—",
                        "—",
                        "—",
                        "Job not found in database",
                        True,
                        [html.P("No output available for this job.", className="text-muted")]
                    )
                    
        except Exception as e:
            print(f"Error loading job data: {e}")
            return (
                [html.Span(f"Job ID: {job_id}")],
                "Error",
                "—",
                "—",
                "—",
                "—",
                "—",
                "—",
                f"Error: {str(e)}",
                True,
                [html.P("No output available for this job.", className="text-muted")]
            )
    
    return (
        [html.Span("Job ID: —")],
        "—",
        "—",
        "—",
        "—",
        "—",
        "—",
        "—",
        "",
        True,
        [html.P("No output available for this job.", className="text-muted")]
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
