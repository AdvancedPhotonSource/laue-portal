import dash
from dash import html, dcc
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc

dash.register_page(__name__, path_template="/scan/<scan_id>")

layout = html.Div(id="scan-detail-page")

@dash.callback(
    Output("scan-detail-page", "children"),
    Input("url", "pathname")
)
def render_scan_detail(pathname):
    scan_id = pathname.split("/scan/")[1]
    return html.Div([
        html.H3(f"Scan Detail: {scan_id}"),
        html.P("This is where you'd display scan-specific analysis, plots, etc.")
    ])