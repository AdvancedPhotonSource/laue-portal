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
        dbc.NavItem(dbc.NavLink("Data Import", href="/")),
        dbc.NavItem(dbc.NavLink("Alignment", href="/alignment")),
        dbc.NavItem(dbc.NavLink("Reconstruction", href="/reconstruction")),
        dbc.NavItem(dbc.NavLink("Visualization", href="#")),
        dbc.Button('Export', id='export-params', color='info', className='mr-1'),
        dbc.Button('Import', id='import-params', color='info', className='ml-1'),

    ],
    brand="Magnetic Tomo Reconstruction",
    brand_href="/",
    color="primary",
    className="navbar-expand-lg",
    dark=True,
    style={"max-height": "50px"},
)