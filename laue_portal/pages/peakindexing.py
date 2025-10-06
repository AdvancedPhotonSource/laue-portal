import dash
from dash import html, dcc, callback, Input, Output
import dash_bootstrap_components as dbc
import laue_portal.database.db_utils as db_utils
import laue_portal.database.db_schema as db_schema
from sqlalchemy.orm import Session
import laue_portal.components.navbar as navbar
from dash.exceptions import PreventUpdate
from laue_portal.database.db_utils import get_catalog_data, remove_root_path_prefix
from laue_portal.components.peakindex_form import peakindex_form, set_peakindex_form_props
from laue_portal.config import DEFAULT_VARIABLES
import urllib.parse
import laue_portal.database.session_utils as session_utils

dash.register_page(__name__, path="/peakindexing") # Simplified path

layout = html.Div([
    navbar.navbar,
    dcc.Location(id='url-peakindexing-page', refresh=False),
    dbc.Container(id='peakindexing-content-container', fluid=True, className="mt-4",
                  children=[
                        html.H1(id='peakindex-id-header', 
                               style={"display":"flex", "gap":"10px", "align-items":"baseline", "flexWrap":"wrap"},
                               className="mb-4"),
                        peakindex_form
                  ]),
])

"""
=======================
Callbacks
=======================
"""

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
    
    peakindex_id_str = query_params.get('peakindex_id', [None])[0]

    root_path = DEFAULT_VARIABLES.get("root_path", "")

    if peakindex_id_str:
        try:
            peakindex_id = int(peakindex_id_str)
            with Session(session_utils.get_engine()) as session:
                peakindex_data = session.query(db_schema.PeakIndex).filter(db_schema.PeakIndex.peakindex_id == peakindex_id).first()
                if peakindex_data:
                    # Add root_path from DEFAULT_VARIABLES
                    peakindex_data.root_path = root_path
                    
                    # Convert full paths back to relative paths for display
                    if peakindex_data.geoFile:
                        peakindex_data.geoFile = remove_root_path_prefix(peakindex_data.geoFile, root_path)
                    if peakindex_data.crystFile:
                        peakindex_data.crystFile = remove_root_path_prefix(peakindex_data.crystFile, root_path)
                    if peakindex_data.outputFolder:
                        peakindex_data.outputFolder = remove_root_path_prefix(peakindex_data.outputFolder, root_path)
                    
                    if peakindex_data.filefolder:
                        peakindex_data.data_path = remove_root_path_prefix(peakindex_data.filefolder, root_path)

                    if any([not hasattr(peakindex_data, field) for field in ['data_path','filenamePrefix']]):
                        # If processing reconstruction data, use the reconstruction output folder as data path
                        if peakindex_data.wirerecon_id:
                            wirerecon_data = session.query(db_schema.WireRecon).filter(db_schema.WireRecon.wirerecon_id == peakindex_data.wirerecon_id).first()
                            if wirerecon_data:
                                if wirerecon_data.outputFolder:
                                    # Use the wire reconstruction output folder as the data path
                                    peakindex_data.data_path = remove_root_path_prefix(wirerecon_data.outputFolder, root_path)
                                if wirerecon_data.filenamePrefix:
                                    peakindex_data.filenamePrefix = wirerecon_data.filenamePrefix
                        elif peakindex_data.recon_id:
                            recon_data = session.query(db_schema.Recon).filter(db_schema.Recon.recon_id == peakindex_data.recon_id).first()
                            if recon_data:
                                if recon_data.file_output:
                                    # Use the reconstruction output folder as the data path
                                    peakindex_data.data_path = remove_root_path_prefix(recon_data.file_output, root_path)
                                if hasattr(recon_data, 'filenamePrefix') and recon_data.filenamePrefix:
                                    peakindex_data.filenamePrefix = recon_data.filenamePrefix
                        
                        if any([not hasattr(peakindex_data, field) for field in ['data_path','filenamePrefix']]):
                            # Retrieve data_path and filenamePrefix from catalog data
                            catalog_data = get_catalog_data(session, peakindex_data.scanNumber, root_path)
                        if not hasattr(peakindex_data, 'data_path'):
                            peakindex_data.data_path = catalog_data.get('data_path', '')
                        if not hasattr(peakindex_data, 'filenamePrefix'):
                            peakindex_data.filenamePrefix = catalog_data.get('filenamePrefix', [])
                    
                    # Populate the form with the data
                    set_peakindex_form_props(peakindex_data, read_only=True)
                    
                    # Get related links for header
                    related_links = []
                    
                    # Add job link if it exists
                    if peakindex_data.job_id:
                        related_links.append(
                            html.A(f"Job ID: {peakindex_data.job_id}", 
                                   href=f"/job?job_id={peakindex_data.job_id}")
                        )
                    
                    if peakindex_data.recon_id:
                        related_links.append(
                            html.A(f"Reconstruction ID: {peakindex_data.recon_id}", 
                                   href=f"/reconstruction?recon_id={peakindex_data.recon_id}")
                        )
                    elif peakindex_data.wirerecon_id:
                        related_links.append(
                            html.A(f"Wire Reconstruction ID: {peakindex_data.wirerecon_id}", 
                                   href=f"/wire_reconstruction?wirerecon_id={peakindex_data.wirerecon_id}")
                        )
                    
                    # Add scan link
                    if peakindex_data.scanNumber:
                        related_links.append(
                            html.A(f"Scan ID: {peakindex_data.scanNumber}", 
                                   href=f"/scan?scan_id={peakindex_data.scanNumber}")
                        )
                    
                    # Build header with links
                    header_content = [html.Span(f"Peak Indexing ID: {peakindex_id}")]

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
            print(f"Error loading peak indexing data: {e}")
            return f"Error loading data for Peak Indexing ID: {peakindex_id}"
    
    return "No Peak Indexing ID provided"
