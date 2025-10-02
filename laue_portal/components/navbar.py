import dash_bootstrap_components as dbc
from dash import html, Input, Output, State, callback, dcc
from laue_portal.processing.redis_utils import REDIS_CONNECTED_AT_STARTUP

navbar = dbc.Navbar(
    dbc.Container(
        [
            dbc.NavbarBrand("3DMN Portal", href="/", id="navbar-brand"),
            html.Div([
                html.I(
                    className="bi bi-hdd-network",
                    style={
                        'fontSize': '1.5rem',
                        'color': '#90EE90' if REDIS_CONNECTED_AT_STARTUP else '#FF6B6B'
                    }
                ),
            ], className="d-flex align-items-center ms-2"),
            dbc.NavbarToggler(id="nav-toggler"),
            dbc.Collapse(
                dbc.Nav(
                    [
                        dbc.NavItem(dbc.NavLink("Scans", href="/scans", active="exact")),
                        dbc.NavItem(dbc.NavLink("Mask Reconstructions", href="/reconstructions", active="exact")),
                        dbc.NavItem(dbc.NavLink("Wire Reconstructions", href="/wire-reconstructions", active="exact")),
                        dbc.NavItem(dbc.NavLink("Indexations", href="/peakindexings", active="exact")),
                        dbc.NavItem(dbc.NavLink("Run Monitor", href="/run-monitor", active="exact")),
                        dbc.DropdownMenu(
                            label="Menu",
                            nav=True, in_navbar=True, align_end=True,   
                            children=[
                                dbc.DropdownMenuItem("New Scan", href="/create-scan"),
                                dbc.DropdownMenuItem("New CA Reconstruction", href="/create-reconstruction"),
                                dbc.DropdownMenuItem("New Wire Reconstruction", href="/create-wire-reconstruction"),
                                dbc.DropdownMenuItem("New LaueGo Indexation", href="/create-peakindexing"),
                                dbc.DropdownMenuItem(divider=True),
                                # dbc.DropdownMenuItem("Update Current DB", id="update-db"),
                                # dbc.DropdownMenuItem("Save as New DB", id="save-new-db"),
                                #dbc.DropdownMenuItem(divider=True),
                                dbc.DropdownMenuItem("Activate Admin Mode", id="activate-admin"),
                            ],
                        ),
                    ],
                    navbar=True, className="ms-auto",
                ),
                id="nav-collapse",
                is_open=False,
                navbar=True,
            ),
        ],
        fluid=True,
    ),
    className="py-3",
    color="primary",
    dark=True,
)

@callback(
    Output("nav-collapse", "is_open"),
    Input("nav-toggler", "n_clicks"),
    State("nav-collapse", "is_open"),
    prevent_initial_call=True,
)
def toggle_nav(n, is_open):
    return not is_open
