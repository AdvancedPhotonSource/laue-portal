import dash
from dash import html
import laue_portal.pages.ui_shared as ui_shared
import laue_portal.components.navbar as navbar

dash.register_page(__name__)

layout = html.Div([navbar.navbar,
    html.H1("404 - Page Not Found (404 page WIP)"),
])
