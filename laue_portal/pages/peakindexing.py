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

def _marker_size_control(slider_id, input_id, default_value=40):
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
            value=default_value,
            style={"width": "160px"},
        ),
        dbc.Input(
            id=input_id,
            type="number",
            min=1,
            max=75,
            step=1,
            value=default_value,
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
                                    {"label": "Cubic IPF", "value": "cubic_ipf"},
                                    {"label": "Rodrigues RGB", "value": "rodrigues"},
                                    {"label": "N Indexed", "value": "n_indexed"},
                                    {"label": "Goodness", "value": "goodness"},
                                    {"label": "RMS Error", "value": "rms_error"},
                                    {"label": "N Patterns", "value": "n_patterns"},
                                ],
                                value="cubic_ipf",
                                style={"width": "180px", "display": "inline-block"},
                            ),
                        ], width="auto"),
                        dbc.Col([
                            dbc.Label("Surface:", className="me-2"),
                            dbc.Select(
                                id="orientation-surface-select",
                                options=[
                                    {"label": "Normal", "value": "normal"},
                                    {"label": "X", "value": "X"},
                                    {"label": "H", "value": "H"},
                                    {"label": "Y", "value": "Y"},
                                    {"label": "Z", "value": "Z"},
                                ],
                                value="normal",
                                style={"width": "110px", "display": "inline-block"},
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
                        dbc.Col(
                            dcc.Loading(
                                type="circle",
                                overlay_style={"visibility": "visible", "opacity": 1},
                                custom_spinner=html.Div([
                                    dbc.Spinner(size="sm", color="secondary",
                                                spinner_class_name="me-2"),
                                    html.Span("Updating\u2026",
                                              style={"color": "#0d6efd",
                                                     "fontSize": "1.05rem",
                                                     "fontWeight": "700"}),
                                ], style={"display": "flex", "alignItems": "center"}),
                                children=html.Div(id="orientation-loading-target"),
                            ),
                            width="auto",
                            style={"paddingLeft": "3.5rem"},
                        ),
                    ], className="mb-3 align-items-center g-3"),
                    # Plot
                    dcc.Graph(
                        id="orientation-map-graph",
                        config={"displayModeBar": True, "scrollZoom": True},
                        style={"height": "calc(100vh - 220px)", "minHeight": "400px"},
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
            label="Pole Figure",
            tab_id="tab-poles",
            children=[
                html.Div(id="tab-poles-content", className="pt-3", children=[
                    # Controls row
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Pole {hkl}:", className="me-2"),
                            dbc.Select(
                                id="stereo-hkl-select",
                                options=[
                                    {"label": "{100}", "value": "1,0,0"},
                                    {"label": "{110}", "value": "1,1,0"},
                                    {"label": "{111}", "value": "1,1,1"},
                                    {"label": "{210}", "value": "2,1,0"},
                                ],
                                value="1,0,0",
                                style={"width": "120px", "display": "inline-block"},
                            ),
                        ], width="auto"),
                        _marker_size_control("stereo-marker-slider", "stereo-marker-size", default_value=12),
                        dbc.Col([
                            dbc.Label("Color:", className="me-2"),
                            dbc.Select(
                                id="stereo-color-select",
                                options=[
                                    {"label": "Position HSV", "value": "hsv_position"},
                                    {"label": "Cubic IPF", "value": "ipf"},
                                    {"label": "Uniform", "value": "uniform"},
                                ],
                                value="hsv_position",
                                style={"width": "150px", "display": "inline-block"},
                            ),
                        ], width="auto"),
                        dbc.Col([
                            dbc.Label("Color radius:", className="me-2 mb-0",
                                      style={"whiteSpace": "nowrap"}),
                            dbc.Input(
                                id="stereo-color-rad",
                                type="number",
                                min=1,
                                max=90,
                                step=0.5,
                                value=22.5,
                                size="sm",
                                style={"width": "75px"},
                            ),
                            html.Span("\u00b0", style={"marginLeft": "2px"}),
                        ], id="stereo-color-rad-col", width="auto",
                           style={"display": "flex", "alignItems": "center"}),
                        dbc.Col([
                            dbc.Label("Surface:", className="me-2"),
                            dbc.Select(
                                id="stereo-surface-select",
                                options=[
                                    {"label": "Normal", "value": "normal"},
                                    {"label": "X", "value": "X"},
                                    {"label": "H", "value": "H"},
                                    {"label": "Y", "value": "Y"},
                                    {"label": "Z", "value": "Z"},
                                ],
                                value="normal",
                                style={"width": "110px", "display": "inline-block"},
                            ),
                        ], width="auto"),
                        dbc.Col(
                            dcc.Loading(
                                type="circle",
                                overlay_style={"visibility": "visible", "opacity": 1},
                                custom_spinner=html.Div([
                                    dbc.Spinner(size="sm", color="secondary",
                                                spinner_class_name="me-2"),
                                    html.Span("Updating\u2026",
                                              style={"color": "#0d6efd",
                                                     "fontSize": "1.05rem",
                                                     "fontWeight": "700"}),
                                ], style={"display": "flex", "alignItems": "center"}),
                                children=html.Div(id="poles-loading-target"),
                            ),
                            width="auto",
                            style={"paddingLeft": "3.5rem"},
                        ),
                    ], className="mb-3 align-items-center g-3"),
                    # Pole figure plot
                    dcc.Graph(
                        id="stereo-plot-graph",
                        config={
                            "displayModeBar": True,
                            "scrollZoom": True,
                            "modeBarButtonsToAdd": ["lasso2d", "select2d"],
                        },
                        style={"height": "calc(100vh - 220px)", "minHeight": "400px"},
                    ),
                    # ROI selection info
                    html.Div(
                        id="stereo-selection-info",
                        className="mt-3",
                        children=html.Small(
                            "Use lasso or box select on the pole figure to pick regions of interest.",
                            className="text-muted",
                        ),
                    ),
                ]),
            ],
        ),
        dbc.Tab(
            label="Stereographic",
            tab_id="tab-stereo",
            children=[
                html.Div(id="tab-stereo-content", className="pt-3", children=[
                    # Controls row
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Zoom:", className="me-2 mb-0",
                                      style={"whiteSpace": "nowrap"}),
                            dcc.Input(
                                id="stereo-zoom-slider",
                                type="range",
                                min=5,
                                max=90,
                                step=5,
                                value=90,
                                style={"width": "160px"},
                            ),
                            html.Span(
                                id="stereo-zoom-label",
                                children="90\u00b0",
                                style={"marginLeft": "8px", "minWidth": "40px"},
                            ),
                        ], width="auto",
                           style={"display": "flex", "alignItems": "center"}),
                        dbc.Col([
                            dbc.Checkbox(
                                id="stereo-wulff-toggle",
                                label="Wulff net",
                                value=True,
                            ),
                        ], width="auto"),
                        dbc.Col([
                            dbc.Label("Wulff step:", className="me-2"),
                            dbc.Select(
                                id="stereo-wulff-step",
                                options=[
                                    {"label": "5\u00b0", "value": "5"},
                                    {"label": "10\u00b0", "value": "10"},
                                    {"label": "20\u00b0", "value": "20"},
                                ],
                                value="10",
                                style={"width": "80px", "display": "inline-block"},
                            ),
                        ], width="auto"),
                        _marker_size_control("stereoprojection-marker-slider",
                                             "stereoprojection-marker-size", default_value=12),
                        dbc.Col([
                            dbc.Button(
                                "Render",
                                id="stereo-render-btn",
                                color="primary",
                                size="sm",
                            ),
                        ], width="auto"),
                        dbc.Col(
                            dcc.Loading(
                                type="circle",
                                overlay_style={"visibility": "visible", "opacity": 1},
                                custom_spinner=html.Div([
                                    dbc.Spinner(size="sm", color="secondary",
                                                spinner_class_name="me-2"),
                                    html.Span("Rendering\u2026",
                                              style={"color": "#0d6efd",
                                                     "fontSize": "1.05rem",
                                                     "fontWeight": "700"}),
                                ], style={"display": "flex", "alignItems": "center"}),
                                children=html.Div(id="stereo-loading-target"),
                            ),
                            width="auto",
                            style={"paddingLeft": "3.5rem"},
                        ),
                    ], className="mb-3 align-items-center g-3"),
                    # Stereographic projection plot
                    dcc.Graph(
                        id="stereo-projection-graph",
                        config={"displayModeBar": True, "scrollZoom": True},
                        style={"height": "calc(100vh - 220px)", "minHeight": "400px"},
                    ),
                ]),
            ],
        ),
        dbc.Tab(
            label="Peaks",
            tab_id="tab-peaks",
            children=[
                html.Div(id="tab-peaks-content", className="pt-3", children=[
                    html.Div(id="peak-table-container"),
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
    # Store selected grain indices for cross-plot linking (Stage 3)
    dcc.Store(id='selected-grain-indices', data=[]),
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
    Output('orientation-loading-target', 'children'),
    Input('peakindexing-xml-path', 'data'),
    Input('orientation-color-select', 'value'),
    Input('orientation-surface-select', 'value'),
    Input('orientation-marker-size', 'value'),
    Input('orientation-marker-slider', 'value'),
    Input('orientation-view-toggle', 'value'),
    Input('selected-grain-indices', 'data'),
    prevent_initial_call=True,
)
def update_orientation_map(xml_path, color_by, surface, input_size, slider_size,
                           view_mode, selected_grains):
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

        from laue_portal.components.visualization.orientation_map import (
            apply_selection_highlight,
        )

        if view_mode == "3d":
            fig = make_orientation_map_3d(
                parsed, color_by=color_by or "cubic_ipf",
                marker_size=marker_size,
                surface=surface or "normal",
            )
        else:
            fig = make_orientation_map(
                parsed, color_by=color_by or "cubic_ipf",
                marker_size=marker_size,
                surface=surface or "normal",
            )

        # Cross-plot highlighting: dim unselected points, ring selected ones
        if selected_grains:
            apply_selection_highlight(fig, parsed, selected_grains, marker_size,
                                     is_3d=(view_mode == "3d"))

        return fig, marker_size, marker_size, ""
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
# Callback: update pole figure plot (auto-renders on data/control changes)
# ---------------------------------------------------------------------------

@callback(
    Output('stereo-plot-graph', 'figure'),
    Output('stereo-marker-size', 'value'),
    Output('stereo-marker-slider', 'value'),
    Output('stereo-color-rad-col', 'style'),
    Output('poles-loading-target', 'children'),
    Input('peakindexing-xml-path', 'data'),
    Input('stereo-hkl-select', 'value'),
    Input('stereo-marker-size', 'value'),
    Input('stereo-marker-slider', 'value'),
    Input('stereo-color-select', 'value'),
    Input('stereo-color-rad', 'value'),
    Input('stereo-surface-select', 'value'),
    prevent_initial_call=True,
)
def update_pole_figure(
    xml_path, hkl_str, input_size, slider_size,
    color_scheme, color_rad_deg, surface,
):
    if not xml_path:
        raise PreventUpdate

    # Show/hide color radius input based on color scheme
    rad_col_style = {"display": "flex", "alignItems": "center"}
    if color_scheme != "hsv_position":
        rad_col_style["display"] = "none"

    try:
        from laue_portal.analysis.xml_parser import parse_indexing_xml
        from laue_portal.components.visualization.stereo_plot import (
            make_pole_figure,
        )

        parsed = parse_indexing_xml(xml_path)

        triggered = dash.ctx.triggered_id
        if triggered == "stereo-marker-slider":
            marker_size = slider_size
        elif triggered == "stereo-marker-size":
            marker_size = input_size
        else:
            marker_size = input_size if input_size is not None else 12

        marker_size = max(1, int(marker_size))
        hkl = tuple(int(x) for x in hkl_str.split(","))

        fig = make_pole_figure(
            parsed,
            hkl=hkl,
            color_scheme=color_scheme or "hsv_position",
            color_rad_deg=float(color_rad_deg or 22.5),
            marker_size=marker_size,
            surface=surface or "normal",
        )

        return fig, marker_size, marker_size, rad_col_style, ""
    except PreventUpdate:
        raise
    except Exception as e:
        print(f"Error creating pole figure: {e}")
        traceback.print_exc()
        raise PreventUpdate


# ---------------------------------------------------------------------------
# Callback: render stereographic projection (on-demand via button click)
# ---------------------------------------------------------------------------

@callback(
    Output('stereo-projection-graph', 'figure'),
    Output('stereoprojection-marker-size', 'value'),
    Output('stereoprojection-marker-slider', 'value'),
    Output('stereo-zoom-label', 'children'),
    Output('stereo-loading-target', 'children'),
    Input('stereo-render-btn', 'n_clicks'),
    State('peakindexing-xml-path', 'data'),
    State('stereo-zoom-slider', 'value'),
    State('stereo-wulff-toggle', 'value'),
    State('stereo-wulff-step', 'value'),
    State('stereoprojection-marker-size', 'value'),
    State('stereoprojection-marker-slider', 'value'),
    prevent_initial_call=True,
)
def render_stereo_projection(
    n_clicks, xml_path, zoom_deg,
    show_wulff, wulff_step, input_size, slider_size,
):
    if not xml_path:
        raise PreventUpdate

    try:
        from laue_portal.analysis.xml_parser import parse_indexing_xml
        from laue_portal.components.visualization.stereo_plot import (
            make_stereo_plot,
        )

        parsed = parse_indexing_xml(xml_path)

        marker_size = max(1, int(input_size or 12))
        zoom = int(zoom_deg) if zoom_deg else 90
        wulff_step_int = int(wulff_step) if wulff_step else 10
        zoom_label = f"{zoom}\u00b0"

        fig = make_stereo_plot(
            parsed,
            step_index=None,
            zoom_deg=zoom,
            show_wulff=bool(show_wulff),
            wulff_step_deg=wulff_step_int,
            marker_size=marker_size,
        )

        return fig, marker_size, marker_size, zoom_label, ""
    except PreventUpdate:
        raise
    except Exception as e:
        print(f"Error creating stereo projection: {e}")
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
# Callback: handle lasso/box selection on pole figure (ROI picking)
# ---------------------------------------------------------------------------

@callback(
    Output('selected-grain-indices', 'data'),
    Output('stereo-selection-info', 'children'),
    Input('stereo-plot-graph', 'selectedData'),
    State('peakindexing-xml-path', 'data'),
    State('stereo-hkl-select', 'value'),
    prevent_initial_call=True,
)
def handle_pole_selection(selected_data, xml_path, hkl_str):
    """Process lasso/box selection on the pole figure to extract grain indices."""
    # If selection is cleared (double-click to deselect), reset
    if not selected_data or not selected_data.get("points"):
        return [], html.Small(
            "Use lasso or box select on the pole figure to pick regions of interest.",
            className="text-muted",
        )

    # Extract unique grain indices from selected points.
    #
    # Plotly Scattergl's selectedData may or may not include customdata
    # depending on the Plotly/browser version.  We try customdata first;
    # if it is absent we fall back to pointIndex and look up grain indices
    # by recomputing the pole figure grain-index mapping.
    grain_set = set()
    fallback_point_indices = []

    for pt in selected_data["points"]:
        customdata = pt.get("customdata")
        if customdata is not None and len(customdata) > 0:
            grain_set.add(int(customdata[0]))
        else:
            # Collect pointIndex / pointNumber for fallback lookup
            pi = pt.get("pointIndex", pt.get("pointNumber"))
            if pi is not None:
                fallback_point_indices.append(int(pi))

    # Fallback: recompute grain_indices mapping from the pole figure and
    # use pointIndex to look up grain indices.
    if not grain_set and fallback_point_indices and xml_path:
        try:
            import numpy as np
            from laue_portal.analysis.xml_parser import parse_indexing_xml
            from laue_portal.analysis.projection import (
                pole_figure_points,
                cubic_hkl_family,
            )

            parsed = parse_indexing_xml(xml_path)

            hkl = tuple(int(x) for x in hkl_str.split(","))
            family = cubic_hkl_family(*hkl)
            points, grain_indices = pole_figure_points(
                parsed["recip_lattices"], family,
            )

            # Apply same NaN filter as make_pole_figure so point indices
            # match the rendered trace
            if len(points) > 0:
                finite_mask = np.all(np.isfinite(points), axis=1)
                grain_indices = grain_indices[finite_mask]

            for pi in fallback_point_indices:
                if 0 <= pi < len(grain_indices):
                    grain_set.add(int(grain_indices[pi]))
        except Exception as e:
            print(f"Error in fallback grain extraction: {e}")
            traceback.print_exc()

    selected = sorted(grain_set)

    if not selected:
        return [], html.Small(
            "No grains in selection.", className="text-muted",
        )

    # Count selected poles
    n_poles = len(selected_data["points"])

    # Compute misorientation statistics if we have the XML and >= 2 grains.
    # Pairwise misorientation is O(k^2 * 24) so cap the grain count to
    # keep the response interactive.
    _MAX_GRAINS_FOR_MISORIENTATION = 700
    misorientation_info = []
    if xml_path and len(selected) >= 2:
        if len(selected) > _MAX_GRAINS_FOR_MISORIENTATION:
            misorientation_info = [
                html.Br(),
                html.Small(
                    f"Misorientation stats skipped (>{_MAX_GRAINS_FOR_MISORIENTATION} grains selected).",
                    className="text-muted",
                ),
            ]
        else:
            try:
                from laue_portal.analysis.xml_parser import parse_indexing_xml
                from laue_portal.analysis.orientation import (
                    batch_orientations,
                    pairwise_misorientation,
                )

                parsed = parse_indexing_xml(xml_path)
                orientations = batch_orientations(
                    parsed["recip_lattices"], parsed["lattice_params"],
                )

                # Only compute if selected indices are within bounds
                valid_indices = [i for i in selected if i < len(orientations)]
                if len(valid_indices) >= 2:
                    mis = pairwise_misorientation(
                        orientations, indices=valid_indices,
                        symmetry_reduce=True,
                    )
                    misorientation_info = [
                        html.Br(),
                        html.Strong("Misorientation: "),
                        f"mean {mis['mean']:.2f}\u00b0, "
                        f"range [{mis['min']:.2f}\u00b0, {mis['max']:.2f}\u00b0]",
                    ]
            except Exception as e:
                print(f"Error computing misorientation: {e}")
                traceback.print_exc()

    # Build summary card
    summary = dbc.Card(
        dbc.CardBody([
            html.H6("ROI Selection", className="card-title"),
            html.P([
                html.Strong(f"Selected: "),
                f"{n_poles} poles from {len(selected)} grain"
                f"{'s' if len(selected) != 1 else ''}",
                *misorientation_info,
            ]),
            html.Small(
                "Selected grains are highlighted on the Orientation tab.",
                className="text-muted",
            ),
        ]),
        className="mt-2",
    )

    return selected, summary


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
