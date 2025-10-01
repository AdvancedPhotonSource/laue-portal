# import dash_bootstrap_components as dbc

# navbar = dbc.NavbarSimple(
#     children=[
#         dbc.NavItem(dbc.NavLink("Scans", href="/", active="exact")),
#         dbc.NavItem(dbc.NavLink("Mask Reconstructions", href="/reconstructions", active="exact")),
#         dbc.NavItem(dbc.NavLink("Wire Reconstructions", href="/wire-reconstructions", active="exact")),
#         dbc.NavItem(dbc.NavLink("Peak Indexings", href="/peakindexings", active="exact")),
#         dbc.NavItem(dbc.NavLink("Run Monitor", href="/run-monitor", active="exact")),
#         dbc.DropdownMenu(
#             id="manual-entry-dropdown",
#             children=[
#                 dbc.DropdownMenuItem("New Scan", href="/create-scan"),
#                 dbc.DropdownMenuItem("New CA Reconstruction", href="/create-reconstruction"),
#                 dbc.DropdownMenuItem("New Wire Reconstruction", href="/create-wire-reconstruction"),
#                 dbc.DropdownMenuItem("New Peak Indexing", href="/create-peakindexing"),
#             ],
#             nav=True,
#             in_navbar=True,
#             label="Manual Entry",
#         ),
#     ],
#     brand="3DMN Portal",
#     brand_href="/",
#     color="primary",
#     className="navbar-lg",
#     dark=True,
#     style={"max-height": "50px"},
# )




import dash_bootstrap_components as dbc
from dash import html, Input, Output, State, callback

navbar = dbc.Navbar(
    dbc.Container(
        [
            dbc.NavbarBrand("3DMN Portal", href="/"),
            dbc.NavbarToggler(id="nav-toggler"),
            dbc.Collapse(
                dbc.Nav(
                    [
                        dbc.NavItem(dbc.NavLink("Scans", href="/", active="exact")),
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
    #brand="3DMN Portal",
    #brand_href="/",
    color="primary",
    dark=True,
    #className="navbar-lg",
    #style={"max-height": "70px"},
)

@callback(
    Output("nav-collapse", "is_open"),
    Input("nav-toggler", "n_clicks"),
    State("nav-collapse", "is_open"),
    prevent_initial_call=True,
)
def toggle_nav(n, is_open):
    return not is_open