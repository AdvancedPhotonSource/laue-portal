import dash
from dash import html
import dash_bootstrap_components as dbc
import laue_portal.components.navbar as navbar

dash.register_page(__name__, path='/')

layout = html.Div([
    navbar.navbar,
    dbc.Container([
        html.H1("Status", className="mt-4"),
        html.Hr(),
        html.P("Status page content coming soon...", className="text-muted"),
    ], fluid=True)
])
