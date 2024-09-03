import dash
from dash import html
import laue_portal.pages.ui_shared as ui_shared

dash.register_page(__name__)

layout = html.Div([ui_shared.navbar,
    html.H1("404 - Page Not Found (404 page WIP)"),
])
