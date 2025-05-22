import dash_bootstrap_components as dbc

navbar = dbc.NavbarSimple(
    children=[
        dbc.NavItem(dbc.NavLink("Scans", href="/", active="exact")),
        dbc.NavItem(dbc.NavLink("New Scan", href="/create-scan", active="exact")),
        dbc.NavItem(dbc.NavLink("Reconstructions", href="/reconstructions", active="exact")),
        dbc.NavItem(dbc.NavLink("New Reconstruction", href="/create-reconstruction", active="exact")),
        dbc.NavItem(dbc.NavLink("Indexations", href="/indexedpeaks", active="exact")),
        dbc.NavItem(dbc.NavLink("New Indexation", href="/create-indexedpeaks", active="exact")),
        dbc.NavItem(dbc.NavLink("Run Monitor", href="/index-runs", active="exact")),
    ],
    brand="Coded Aperture Laue",
    brand_href="/",
    color="primary",
    className="navbar-lg",
    dark=True,
    style={"max-height": "50px"},
)

