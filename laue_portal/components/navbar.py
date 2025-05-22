import dash_bootstrap_components as dbc

navbar = dbc.NavbarSimple(
    children=[
        dbc.NavItem(dbc.NavLink("Scans", href="/", active="exact")),
        dbc.NavItem(dbc.NavLink("Reconstructions", href="/reconstructions", active="exact")),
        dbc.NavItem(dbc.NavLink("Indexations", href="/indexedpeaks", active="exact")),
        dbc.NavItem(dbc.NavLink("Run Monitor", href="/index-runs", active="exact")),
        dbc.DropdownMenu(
            id="manual-entry-dropdown",
            children=[
                dbc.DropdownMenuItem("New Scan", href="/create-scan"),
                dbc.DropdownMenuItem("New Reconstruction", href="/create-reconstruction"),
                dbc.DropdownMenuItem("New Indexation", href="/create-indexedpeaks"),
            ],
            nav=True,
            in_navbar=True,
            label="Manual Entry",
        ),
    ],
    brand="3DMN Portal",
    brand_href="/",
    color="primary",
    className="navbar-lg",
    dark=True,
    style={"max-height": "50px"},
)

