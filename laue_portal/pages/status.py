import dash
from dash import html, dcc
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output
import laue_portal.components.navbar as navbar
from laue_portal.processing import redis_utils
from laue_portal import config
import os

dash.register_page(__name__, path='/')

# Build the layout
layout = html.Div([
    navbar.navbar,
    dbc.Container([
        # Auto-refresh interval (every 5 seconds)
        dcc.Interval(
            id='status-refresh-interval',
            interval=5*1000,  # in milliseconds
            n_intervals=0
        ),
        
        # Row 1: Welcome and Connection Status
        dbc.Row([
            # Welcome Card
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H4("Welcome to the 3DMN Laue Portal", className="mb-0")),
                    dbc.CardBody([
                        html.P([
                            "The 3DMN Laue Portal is a data processing platform for ",
                            "Laue X-ray diffraction experiments at beamline 34-ID-E."
                        ], className="mb-3"),
                        html.H6("Capabilities:", className="mb-2"),
                        html.Ul([
                            html.Li("Scan management and tracking"),
                            html.Li("Wire-based depth reconstruction"),
                            html.Li("Coded aperture reconstruction"),
                            html.Li("Automated peak indexing"),
                            html.Li("Distributed job queue"),
                        ], className="mb-0"),
                    ])
                ], className="h-100")
            ], md=6, className="mb-4"),
            
            # Connection Status Card
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H4("Connection Status", className="mb-0")),
                    dbc.CardBody([
                        html.Div(id='connection-status-content')
                    ])
                ], className="h-100")
            ], md=6, className="mb-4"),
        ]),
        
        # Row 2: System Resources and Quick Actions
        dbc.Row([
            # System Resources Card
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H4("System Resources", className="mb-0")),
                    dbc.CardBody([
                        html.Div(id='system-resources-content')
                    ])
                ], className="h-100")
            ], md=6, className="mb-4"),
            
            # Quick Actions Card
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H4("Quick Actions", className="mb-0")),
                    dbc.CardBody([
                        dbc.ListGroup([
                            dbc.ListGroupItem([
                                html.I(className="bi bi-list-ul me-2"),
                                "View All Scans"
                            ], href="/scans", action=True, className="d-flex align-items-center"),
                            dbc.ListGroupItem([
                                html.I(className="bi bi-gear me-2"),
                                "Create Wire Reconstruction"
                            ], href="/create-wire-reconstruction", action=True, className="d-flex align-items-center"),
                            dbc.ListGroupItem([
                                html.I(className="bi bi-grid-3x3 me-2"),
                                "Create Coded Aperture Reconstruction"
                            ], href="/create-reconstruction", action=True, className="d-flex align-items-center"),
                            dbc.ListGroupItem([
                                html.I(className="bi bi-search me-2"),
                                "Create Peak Indexing"
                            ], href="/create-peakindexing", action=True, className="d-flex align-items-center"),
                            dbc.ListGroupItem([
                                html.I(className="bi bi-activity me-2"),
                                "Monitor Job Queue"
                            ], href="/run-monitor", action=True, className="d-flex align-items-center"),
                        ], flush=True)
                    ])
                ], className="h-100")
            ], md=6, className="mb-4"),
        ]),
        
    ], fluid=True, className="mt-4")
])


# Callback to update connection status
@dash.callback(
    Output('connection-status-content', 'children'),
    Input('status-refresh-interval', 'n_intervals')
)
def update_connection_status(n):
    """Update the connection status card with current system information."""
    
    # Check Redis connection
    redis_connected = redis_utils.check_redis_connection()
    redis_startup_status = redis_utils.REDIS_CONNECTED_AT_STARTUP
    
    # Database path
    db_path = config.db_file
    db_exists = os.path.exists(db_path)
    
    # Server info
    dash_url = f"http://{config.DASH_CONFIG['host']}:{config.DASH_CONFIG['port']}"
    redis_url = f"{config.REDIS_CONFIG['host']}:{config.REDIS_CONFIG['port']}"
    
    return [
        # Database Status
        html.Div([
            html.Strong("Database: "),
            dbc.Badge(
                "Connected" if db_exists else "Not Found",
                color="success" if db_exists else "danger",
                className="me-2"
            ),
            html.Br(),
            html.Small(db_path, className="text-muted"),
        ], className="mb-3"),
        
        # Dash Server Status
        html.Div([
            html.Strong("Dash Server: "),
            dbc.Badge("Running", color="success", className="me-2"),
            html.Br(),
            html.Small(dash_url, className="text-muted"),
        ], className="mb-3"),
        
        # Redis Status
        html.Div([
            html.Strong("Redis Queue: "),
            dbc.Badge(
                "Connected" if redis_connected else "Disconnected",
                color="success" if redis_connected else "danger",
                className="me-2"
            ),
            html.Br(),
            html.Small(redis_url, className="text-muted"),
            html.Br(),
            html.Small(
                f"Startup status: {'Connected' if redis_startup_status else 'Disconnected'}" 
                if redis_startup_status is not None else "Startup status: Unknown",
                className="text-muted fst-italic"
            ),
        ], className="mb-0"),
    ]


# Callback to update system resources
@dash.callback(
    Output('system-resources-content', 'children'),
    Input('status-refresh-interval', 'n_intervals')
)
def update_system_resources(n):
    """Update the system resources card with queue and worker information."""
    
    try:
        # Get queue statistics
        queue_stats = redis_utils.get_queue_stats()
        
        # Get worker information
        workers_info = redis_utils.get_workers_info()
        
        return [
            # Queue Statistics
            html.H6("Job Queue:", className="mb-2"),
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.H3(queue_stats.get('queued', 0), className="mb-0 text-primary"),
                        html.Small("Queued", className="text-muted")
                    ], className="text-center")
                ], width=6),
                dbc.Col([
                    html.Div([
                        html.H3(queue_stats.get('started', 0), className="mb-0 text-info"),
                        html.Small("Running", className="text-muted")
                    ], className="text-center")
                ], width=6),
            ], className="mb-3"),
            
            html.Hr(),
            
            # Worker Information
            html.H6("Workers:", className="mb-2"),
            html.Div([
                dbc.Badge(
                    f"{len(workers_info)} Active" if workers_info else "No Workers",
                    color="success" if workers_info else "warning",
                    className="me-2"
                ),
                html.Br() if workers_info else None,
                html.Div([
                    html.Div([
                        html.Small([
                            html.Strong(f"{worker['name']}: "),
                            f"{worker['state']}"
                        ])
                    ], className="mb-1") for worker in workers_info
                ] if workers_info else [], className="mt-2")
            ], className="mb-0"),
        ]
        
    except Exception as e:
        return [
            dbc.Alert([
                html.I(className="bi bi-exclamation-triangle me-2"),
                "No system data. Redis is not connected."
            ], color="warning", className="mb-0")
        ]
