import dash
from dash import dcc, ctx
from dash import html
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
import tomopy
from dataclasses import dataclass
import ui_shared

# Assume images are numpy arrays
dbc_css = "https://cdn.jsdelivr.net/gh/AnnMarieW/dash-bootstrap-templates/dbc.min.css"
# Create a Dash application
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.FLATLY, dbc_css], suppress_callback_exceptions=True)

app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    html.Div(id='page-content')
])


recon_catalog_layout = None

create_recon_layout = None



"""
================
Multi-page Callbacks
================
"""

# Update the index
@app.callback(Output('page-content', 'children'), Input('url', 'pathname'))
def display_page(pathname):
    if pathname == '/':
        return load_layout
    elif pathname == '/recons':
        return recon_catalog_layout
    elif pathname == '/newrecon':
        return create_recon_layout

    #else:
    #    return index_page
    # You could also return a 404 "URL not found" page here


# Run the application
if __name__ == '__main__':
    app.run_server(debug=True)