import dash
from dash import html, dcc, callback, Input, Output
import dash_bootstrap_components as dbc
import laue_portal.database.db_utils as db_utils
import laue_portal.database.db_schema as db_schema
from sqlalchemy.orm import Session
import laue_portal.components.navbar as navbar
from dash.exceptions import PreventUpdate
from sqlalchemy import asc # Import asc for ordering
from laue_portal.components.peakindex_form import peakindex_form, set_peakindex_form_props
import urllib.parse

dash.register_page(__name__, path="/peakindexing") # Simplified path

layout = html.Div([
    navbar.navbar,
    dcc.Location(id='url-peakindexing-page', refresh=False),
    dbc.Container(id='peakindexing-content-container', fluid=True, className="mt-4",
                  children=[
                        html.H2(id='peakindex-id-header', className="mb-3"),
                        peakindex_form
                  ]),
])

@callback(
    Output('peakindex-id-header', 'children'),
    Input('url-peakindexing-page', 'href'),
    prevent_initial_call=True
)
def load_peakindexing_data(href):
    if not href:
        raise PreventUpdate

    parsed_url = urllib.parse.urlparse(href)
    query_params = urllib.parse.parse_qs(parsed_url.query)
    
    index_id = query_params.get('peakindex_id', [None])[0]

    if index_id:
        try:
            index_id = int(index_id)
            with Session(db_utils.ENGINE) as session:
                peakindex_data = session.query(db_schema.PeakIndex).filter(db_schema.PeakIndex.peakindex_id == index_id).first()
                if peakindex_data:
                    set_peakindex_form_props(peakindex_data, read_only=True)
                    return f"Peak Indexing | ID: {index_id}"
        except Exception as e:
            print(f"Error loading peak indexing data: {e}")
            return f"Error loading data for Peak Indexing ID: {index_id}"
    
    return "No Peak Indexing ID provided"
