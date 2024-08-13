import dash_bootstrap_components as dbc

# TODO: Make navbar links dynamic
"""
Something like this...
@app.callback(
    [Output(f"link-{i}", "active") for i in range(1, 5)],
    [Input('url', 'pathname')]
)
def update_active_links(pathname):
    return [pathname == link.href for link in navbar.children]

"""
navbar = dbc.NavbarSimple(
    children=[
        dbc.NavItem(dbc.NavLink("Reconstructions", href="/")),
        dbc.NavItem(dbc.NavLink("New Reconstruction", href="/new-recon")),
    ],
    brand="Coded Apeture Laue",
    brand_href="/",
    color="primary",
    className="navbar-expand-lg",
    dark=True,
    style={"max-height": "50px"},
)