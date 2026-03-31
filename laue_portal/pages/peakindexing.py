import dash
from dash import html, dcc, callback, Input, Output, State, set_props
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

import traceback
from pathlib import Path

dash.register_page(__name__, path="/peakindexing") # Simplified path


# ---------------------------------------------------------------------------
# Visualization tabs (shown when XML results are available)
# ---------------------------------------------------------------------------

def _marker_size_control(slider_id, input_id):
    """Reusable marker-size slider + number input."""
    return dbc.Col([
        dbc.Label("Marker size:", className="me-2 mb-0",
                  style={"whiteSpace": "nowrap"}),
        dcc.Input(
            id=slider_id,
            type="range",
            min=1,
            max=75,
            step=1,
            value=40,
            style={"width": "160px"},
        ),
        dbc.Input(
            id=input_id,
            type="number",
            min=1,
            max=75,
            step=1,
            value=40,
            size="sm",
            style={"width": "60px", "marginLeft": "8px"},
        ),
    ], width="auto",
       style={"display": "flex", "alignItems": "center"})


_viz_tabs = dbc.Tabs(
    id="peakindexing-viz-tabs",
    active_tab="tab-parameters",
    className="mt-4",
    children=[
        dbc.Tab(
            label="Parameters",
            tab_id="tab-parameters",
            children=[
                html.Div(id="tab-parameters-content", className="pt-3",
                         children=[peakindex_form]),
            ],
        ),
        dbc.Tab(
            label="Orientation",
            tab_id="tab-orientation",
            children=[
                html.Div(id="tab-orientation-content", className="pt-3", children=[
                    # Controls row
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Color by:", className="me-2"),
                            dbc.Select(
                                id="orientation-color-select",
                                options=[
                                    {"label": "N Indexed", "value": "n_indexed"},
                                    {"label": "Goodness", "value": "goodness"},
                                    {"label": "RMS Error", "value": "rms_error"},
                                    {"label": "N Patterns", "value": "n_patterns"},
                                ],
                                value="n_indexed",
                                style={"width": "180px", "display": "inline-block"},
                            ),
                        ], width="auto"),
                        _marker_size_control("orientation-marker-slider", "orientation-marker-size"),
                        dbc.Col([
                            dbc.RadioItems(
                                id="orientation-view-toggle",
                                options=[
                                    {"label": "2D", "value": "2d"},
                                    {"label": "3D", "value": "3d"},
                                ],
                                value="2d",
                                inline=True,
                                className="mb-0",
                            ),
                        ], width="auto"),
                    ], className="mb-3 align-items-center g-3"),
                    # Plot
                    dcc.Graph(
                        id="orientation-map-graph",
                        config={"displayModeBar": True, "scrollZoom": True},
                    ),
                    # Selected point details
                    html.Div(
                        id="orientation-point-details",
                        className="mt-3",
                        children=html.Small(
                            "Click a point on the map to view details.",
                            className="text-muted",
                        ),
                    ),
                ]),
            ],
        ),
        dbc.Tab(
            label="Quality",
            tab_id="tab-quality",
            children=[
                html.Div(id="tab-quality-content", className="pt-3", children=[
                    # Controls row
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Metric:", className="me-2"),
                            dbc.Select(
                                id="quality-metric-select",
                                options=[
                                    {"label": "Goodness", "value": "goodness"},
                                    {"label": "RMS Error", "value": "rms_error"},
                                    {"label": "N Indexed", "value": "n_indexed"},
                                    {"label": "N Patterns", "value": "n_patterns"},
                                ],
                                value="goodness",
                                style={"width": "180px", "display": "inline-block"},
                            ),
                        ], width="auto"),
                        _marker_size_control("quality-marker-slider", "quality-marker-size"),
                        dbc.Col([
                            dbc.RadioItems(
                                id="quality-view-toggle",
                                options=[
                                    {"label": "2D", "value": "2d"},
                                    {"label": "3D", "value": "3d"},
                                ],
                                value="2d",
                                inline=True,
                                className="mb-0",
                            ),
                        ], width="auto"),
                    ], className="mb-3 align-items-center g-3"),
                    # Quality map plot
                    dcc.Graph(
                        id="quality-map-graph",
                        config={"displayModeBar": True, "scrollZoom": True},
                    ),
                    # Indexed peaks table
                    html.Div(id="peak-table-container", className="mt-3"),
                ]),
            ],
        ),
    ],
)


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

layout = html.Div([
    navbar.navbar,
    dcc.Location(id='url-peakindexing-page', refresh=False),
    # Store parsed XML data path so visualization callbacks can load it
    dcc.Store(id='peakindexing-xml-path'),
    dbc.Container(
        id='peakindexing-content-container',
        fluid=True,
        className="mt-4",
        children=[
            html.H1(
                id='peakindex-id-header',
                style={
                    "display": "flex",
                    "gap": "10px",
                    "align-items": "baseline",
                    "flexWrap": "wrap",
                },
                className="mb-4",
            ),
            _viz_tabs,
        ],
    ),
])


# ---------------------------------------------------------------------------
# Callback: load page data from DB + resolve XML path
# ---------------------------------------------------------------------------

@callback(
    Output('peakindex-id-header', 'children'),
    Output('peakindexing-xml-path', 'data'),
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

    xml_path = None  # Will be set if we find an XML file

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
                    
                    # Resolve XML path before stripping root_path from outputFolder
                    xml_path = _resolve_xml_path(peakindex_data, root_path)

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
                    
                    return header_content, xml_path
        except Exception as e:
            print(f"Error loading peak indexing data: {e}")
            traceback.print_exc()
            return f"Error loading data for Peak Indexing ID: {peakindex_id}", None
    
    return "No Peak Indexing ID provided", None


# ---------------------------------------------------------------------------
# Callback: update orientation map when XML is available or color changes
# ---------------------------------------------------------------------------

@callback(
    Output('orientation-map-graph', 'figure'),
    Output('orientation-marker-size', 'value'),
    Output('orientation-marker-slider', 'value'),
    Input('peakindexing-xml-path', 'data'),
    Input('orientation-color-select', 'value'),
    Input('orientation-marker-size', 'value'),
    Input('orientation-marker-slider', 'value'),
    Input('orientation-view-toggle', 'value'),
    prevent_initial_call=True,
)
def update_orientation_map(xml_path, color_by, input_size, slider_size, view_mode):
    if not xml_path:
        raise PreventUpdate

    try:
        from laue_portal.analysis.xml_parser import parse_indexing_xml
        from laue_portal.components.visualization.orientation_map import (
            make_orientation_map,
            make_orientation_map_3d,
        )

        parsed = parse_indexing_xml(xml_path)

        triggered = dash.ctx.triggered_id
        if triggered == "orientation-marker-slider":
            marker_size = slider_size
        elif triggered == "orientation-marker-size":
            marker_size = input_size
        else:
            marker_size = input_size if input_size is not None else 40

        marker_size = max(1, int(marker_size))

        if view_mode == "3d":
            fig = make_orientation_map_3d(
                parsed, color_by=color_by or "n_indexed", marker_size=marker_size,
            )
        else:
            fig = make_orientation_map(
                parsed, color_by=color_by or "n_indexed", marker_size=marker_size,
            )
        return fig, marker_size, marker_size
    except PreventUpdate:
        raise
    except Exception as e:
        print(f"Error creating orientation map: {e}")
        traceback.print_exc()
        raise PreventUpdate


# ---------------------------------------------------------------------------
# Callback: show selected point details on orientation map click
# ---------------------------------------------------------------------------

@callback(
    Output('orientation-point-details', 'children'),
    Input('orientation-map-graph', 'clickData'),
    State('peakindexing-xml-path', 'data'),
    prevent_initial_call=True,
)
def show_point_details(click_data, xml_path):
    if not click_data or not xml_path:
        raise PreventUpdate

    try:
        point = click_data["points"][0]
        customdata = point.get("customdata", None)
        if customdata is None or len(customdata) < 8:
            # Scattergl may not provide customdata -- fall back to pointIndex
            point_index = point.get("pointIndex", point.get("pointNumber", None))
            if point_index is None:
                raise PreventUpdate

            from laue_portal.analysis.xml_parser import parse_indexing_xml, get_step_peaks
            parsed = parse_indexing_xml(xml_path)
            step_idx = int(point_index)
            if step_idx >= len(parsed["positions"]):
                raise PreventUpdate

            x_pos = float(parsed["positions"][step_idx, 0])
            y_pos = float(parsed["positions"][step_idx, 1])
            z_pos = float(parsed["positions"][step_idx, 2])
            n_pat = int(parsed["n_patterns"][step_idx])
            n_idx = int(parsed["n_indexed"][step_idx])
            goodness = float(parsed["goodnesses"][step_idx])
            rms_err = float(parsed["rms_errors"][step_idx])
            step_peaks = get_step_peaks(parsed, step_idx)
            n_peaks_total = step_peaks["n_peaks"] if step_peaks else 0
        else:
            step_idx = int(customdata[0])
            x_pos = float(customdata[1])
            y_pos = float(customdata[2])
            z_pos = float(customdata[3])
            n_pat = int(customdata[4])
            n_idx = int(customdata[5])
            goodness = float(customdata[6])
            rms_err = float(customdata[7])

            from laue_portal.analysis.xml_parser import parse_indexing_xml, get_step_peaks
            parsed = parse_indexing_xml(xml_path)
            step_peaks = get_step_peaks(parsed, step_idx)
            n_peaks_total = step_peaks["n_peaks"] if step_peaks else 0

        detail_card = dbc.Card(
            dbc.CardBody([
                html.H6("Selected Point Details", className="card-title"),
                html.P([
                    html.Strong(f"Step #{step_idx}"),
                    f"  Position: ({x_pos:.1f}, {y_pos:.1f}, {z_pos:.1f})",
                ]),
                html.P([
                    f"Patterns: {n_pat}  |  "
                    f"Indexed: {n_idx}/{n_peaks_total}  |  "
                    f"Goodness: {goodness:.1f}  |  "
                    f"RMS error: {rms_err:.5f} deg",
                ]),
            ]),
            className="mt-2",
        )
        return detail_card
    except PreventUpdate:
        raise
    except Exception as e:
        print(f"Error showing point details: {e}")
        traceback.print_exc()
        raise PreventUpdate


# ---------------------------------------------------------------------------
# Callback: update quality map when XML is available or metric changes
# ---------------------------------------------------------------------------

@callback(
    Output('quality-map-graph', 'figure'),
    Output('quality-marker-size', 'value'),
    Output('quality-marker-slider', 'value'),
    Input('peakindexing-xml-path', 'data'),
    Input('quality-metric-select', 'value'),
    Input('quality-marker-size', 'value'),
    Input('quality-marker-slider', 'value'),
    Input('quality-view-toggle', 'value'),
    prevent_initial_call=True,
)
def update_quality_map(xml_path, metric, input_size, slider_size, view_mode):
    if not xml_path:
        raise PreventUpdate

    try:
        from laue_portal.analysis.xml_parser import parse_indexing_xml
        from laue_portal.components.visualization.quality_map import (
            make_quality_map,
            make_quality_map_3d,
        )

        parsed = parse_indexing_xml(xml_path)

        triggered = dash.ctx.triggered_id
        if triggered == "quality-marker-slider":
            marker_size = slider_size
        elif triggered == "quality-marker-size":
            marker_size = input_size
        else:
            marker_size = input_size if input_size is not None else 40

        marker_size = max(1, int(marker_size))

        if view_mode == "3d":
            fig = make_quality_map_3d(
                parsed, metric=metric or "goodness", marker_size=marker_size,
            )
        else:
            fig = make_quality_map(
                parsed, metric=metric or "goodness", marker_size=marker_size,
            )
        return fig, marker_size, marker_size
    except PreventUpdate:
        raise
    except Exception as e:
        print(f"Error creating quality map: {e}")
        traceback.print_exc()
        raise PreventUpdate


# ---------------------------------------------------------------------------
# Callback: populate indexed peaks table when XML is available
# ---------------------------------------------------------------------------

@callback(
    Output('peak-table-container', 'children'),
    Input('peakindexing-xml-path', 'data'),
    prevent_initial_call=True,
)
def update_peak_table(xml_path):
    if not xml_path:
        raise PreventUpdate

    try:
        from laue_portal.analysis.xml_parser import parse_indexing_xml, get_all_indexed_peaks
        from laue_portal.components.visualization.peak_table import make_peak_table

        parsed = parse_indexing_xml(xml_path)
        indexed_peaks = get_all_indexed_peaks(parsed)
        return make_peak_table(indexed_peaks)
    except Exception as e:
        print(f"Error creating peak table: {e}")
        traceback.print_exc()
        return html.Div(
            dbc.Alert(f"Could not load peak table: {e}", color="warning"),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_xml_path(peakindex_data, root_path: str) -> str | None:
    """
    Resolve the full path to the output XML file from the PeakIndex record.

    Checks in order:
    1. peakindex_data.outputXML as an absolute path
    2. peakindex_data.outputFolder / peakindex_data.outputXML
    3. Glob for *.xml in outputFolder
    """
    # Try outputXML directly
    if peakindex_data.outputXML:
        candidate = Path(peakindex_data.outputXML)
        if candidate.is_file():
            return str(candidate)

        # Try relative to outputFolder
        if peakindex_data.outputFolder:
            candidate = Path(peakindex_data.outputFolder) / peakindex_data.outputXML
            if candidate.is_file():
                return str(candidate)

    # Fallback: look for XML files in outputFolder
    if peakindex_data.outputFolder:
        output_dir = Path(peakindex_data.outputFolder)
        if output_dir.is_dir():
            xml_files = sorted(output_dir.glob("*.xml"))
            if xml_files:
                return str(xml_files[0])

    return None
