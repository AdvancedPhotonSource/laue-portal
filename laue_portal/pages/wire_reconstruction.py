import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, callback, Input, Output
from dash.exceptions import PreventUpdate
from sqlalchemy.orm import Session
import laue_portal.database.db_utils as db_utils
import laue_portal.database.db_schema as db_schema
import laue_portal.components.navbar as navbar
from laue_portal.database.db_utils import get_catalog_data, remove_root_path_prefix
from laue_portal.components.wire_recon_form import wire_recon_form, set_wire_recon_form_props
from config import DEFAULT_VARIABLES
import urllib.parse

dash.register_page(__name__, path="/wire_reconstruction")

layout = html.Div([
        navbar.navbar,
        dcc.Location(id='url-wire-recon-page', refresh=False),
        dbc.Container(id='wire-recon-content-container', fluid=True, className="mt-4",
                  children=[
                        html.H1(id='wire-recon-id-header', 
                               style={"display":"flex", "gap":"10px", "align-items":"baseline", "flexWrap":"wrap"},
                               className="mb-4"),
                        wire_recon_form
                  ]),
])

"""
=======================
Callbacks
=======================
"""

@callback(
    Output('wire-recon-id-header', 'children'),
    Input('url-wire-recon-page', 'href'),
    prevent_initial_call=True
)
def load_wire_recon_data(href):
    if not href:
        raise PreventUpdate

    parsed_url = urllib.parse.urlparse(href)
    query_params = urllib.parse.parse_qs(parsed_url.query)
    
    wirerecon_id_str = query_params.get('wirerecon_id', [None])[0]

    root_path = DEFAULT_VARIABLES.get("root_path", "")

    if wirerecon_id_str:
        try:
            wirerecon_id = int(wirerecon_id_str) if wirerecon_id_str else None
            with Session(db_utils.ENGINE) as session:
                wirerecon_data = session.query(db_schema.WireRecon).filter(db_schema.WireRecon.wirerecon_id == wirerecon_id).first()
                if wirerecon_data:
                    # Add root_path from DEFAULT_VARIABLES
                    root_path = DEFAULT_VARIABLES.get("root_path", "")
                    wirerecon_data.root_path = root_path
                    
                    # Retrieve data_path and filenamePrefix from catalog data
                    catalog_data = get_catalog_data(session, wirerecon_data.scanNumber, root_path)
                    wirerecon_data.data_path = catalog_data["data_path"]
                    wirerecon_data.filenamePrefix = catalog_data["filenamePrefix"]
                    
                    # Convert full paths back to relative paths for display
                    if wirerecon_data.geoFile:
                        wirerecon_data.geoFile = remove_root_path_prefix(wirerecon_data.geoFile, root_path)
                    if wirerecon_data.outputFolder:
                        wirerecon_data.outputFolder = remove_root_path_prefix(wirerecon_data.outputFolder, root_path)
                    
                    # Populate the form with the data
                    set_wire_recon_form_props(wirerecon_data, read_only=True)
                    
                    # Get related links
                    related_links = []
                    
                    # Add job link if it exists
                    if wirerecon_data.job_id:
                        related_links.append(
                            html.A(f"Job ID: {wirerecon_data.job_id}", 
                                   href=f"/job?job_id={wirerecon_data.job_id}")
                        )
                    
                    # Add scan link
                    if wirerecon_data.scanNumber:
                        related_links.append(
                            html.A(f"Scan ID: {wirerecon_data.scanNumber}", 
                                   href=f"/scan?scan_id={wirerecon_data.scanNumber}")
                        )
                    
                    # Build header with links
                    header_content = [html.Span(f"Wire Reconstruction ID: {wirerecon_id}")]
                    
                    if related_links:
                        # Add separator before links
                        header_content.append(html.Span(" • ", className="mx-2", style={"color": "#6c757d"}))
                        
                        # Add each link with separators
                        for i, link in enumerate(related_links):
                            if i > 0:
                                header_content.append(html.Span(" | ", className="mx-2", style={"color": "#6c757d"}))
                            header_content.append(html.Span(link, style={"fontSize": "0.7em"}))
                    
                    return header_content

        except Exception as e:
            print(f"Error loading wire reconstruction data: {e}")
            return f"Error loading data for Wire Recon ID: {wirerecon_id}"
    
    return "No Wire Recon ID provided"
