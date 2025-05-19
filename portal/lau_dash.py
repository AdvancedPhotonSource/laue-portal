import dash
from dash import dcc, ctx, dash_table
from dash import html
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
from dataclasses import dataclass
import pandas as pd
import laue_portal.pages.ui_shared as ui_shared

# Assume images are numpy arrays
dbc_css = "https://cdn.jsdelivr.net/gh/AnnMarieW/dash-bootstrap-templates/dbc.min.css"
# Create a Dash application
app = dash.Dash(__name__, 
                external_stylesheets=[dbc.themes.FLATLY, dbc_css], 
                suppress_callback_exceptions=True,
                pages_folder="laue_portal/pages",)


app.layout = dash.page_container

from dash.dependencies import Input, Output, State

@app.callback(
    Output("nav-scans", "active"),
    Output("nav-recon", "active"),
    Output("nav-index", "active"),
    #Output("nav-createRecon", "active"),
    #Output("nav-createIndex", "active"),
    Input("url", "pathname"),
)
def toggle_active_links(pathname):
    return (
        pathname == "/",                       # nav-scans
        pathname == "/reconstructions",        # nav-recon
        #pathname == "/create_indexing",        # nav-createIndex
        #pathname == "/create_reconstruction",  # nav-createRecon
        pathname == "/indexing",               # nav-index
    )


# Run the application
if __name__ == '__main__':
    app.run(debug=True, port=8053)#, host='0.0.0.0')