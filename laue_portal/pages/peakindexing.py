import traceback
import urllib.parse
from pathlib import Path

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, dcc, html
from dash.exceptions import PreventUpdate
from sqlalchemy.orm import Session

import laue_portal.components.navbar as navbar
import laue_portal.database.db_schema as db_schema
import laue_portal.database.session_utils as session_utils
from laue_portal.components.peakindex_form import peakindex_form, set_peakindex_form_props
from laue_portal.config import DEFAULT_VARIABLES
from laue_portal.database.db_utils import get_catalog_data, remove_root_path_prefix

dash.register_page(__name__, path="/peakindexing")  # Simplified path


# ---------------------------------------------------------------------------
# Visualization helpers — sidebar control builders
# ---------------------------------------------------------------------------


def _viz_sidebar_head(title, icon_class="bi bi-sliders"):
    """Section header inside a visualization sidebar."""
    return html.Div(
        [
            html.I(className=f"pi-viz-section-icon {icon_class}"),
            html.H4(title),
        ],
        className="pi-viz-sidebar-head",
    )


def _viz_control(label_text, *children):
    """Single labelled control row inside a visualization sidebar."""
    return html.Div(
        [html.Label(label_text), *children],
        className="pi-viz-control",
    )


def _viz_graph_with_loading(graph, target_id, text="Updating\u2026"):
    """Wrap a dcc.Graph in a dcc.Loading overlay shown during callbacks."""
    return dcc.Loading(
        type="circle",
        overlay_style={"visibility": "visible", "opacity": 1},
        custom_spinner=html.Div(
            [
                dbc.Spinner(size="sm", color="secondary", spinner_class_name="me-2"),
                html.Span(text, className="pi-viz-loading-text"),
            ],
            style={
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "center",
                "padding": "2rem",
            },
        ),
        children=[graph, html.Div(id=target_id)],
    )


# ---------------------------------------------------------------------------
# Visualization tabs — sidebar + main content layout
# ---------------------------------------------------------------------------

_viz_tabs = dbc.Tabs(
    id="peakindexing-viz-tabs",
    active_tab="tab-parameters",
    className="pi-viz-tabs",
    children=[
        # ==================================================================
        # Tab: Parameters (unchanged — full-width accordion form)
        # ==================================================================
        dbc.Tab(
            label="Parameters",
            tab_id="tab-parameters",
            children=[
                html.Div(id="tab-parameters-content", className="pt-3 px-2", children=[peakindex_form]),
            ],
        ),
        # ==================================================================
        # Tab: Orientation — sidebar + map
        # ==================================================================
        dbc.Tab(
            label="Orientation",
            tab_id="tab-orientation",
            children=[
                html.Div(
                    id="tab-orientation-content",
                    className="pi-viz-layout",
                    children=[
                        # ── Sidebar ──
                        html.Div(
                            className="pi-viz-sidebar",
                            children=[
                                html.Div(
                                    className="pi-viz-sidebar-section",
                                    children=[
                                        _viz_sidebar_head("Color", "bi bi-palette"),
                                        _viz_control(
                                            "Color by",
                                            dbc.Select(
                                                id="orientation-color-select",
                                                options=[
                                                    {"label": "Cubic IPF", "value": "cubic_ipf"},
                                                    {"label": "Rodrigues RGB", "value": "rodrigues"},
                                                    {"label": "Misorientation", "value": "misorientation"},
                                                    {"label": "Pole Figure HSV", "value": "pole_hsv"},
                                                    {"label": "N Indexed", "value": "n_indexed"},
                                                    {"label": "Goodness", "value": "goodness"},
                                                    {"label": "RMS Error", "value": "rms_error"},
                                                    {"label": "N Patterns", "value": "n_patterns"},
                                                ],
                                                value="cubic_ipf",
                                                className="form-select",
                                            ),
                                        ),
                                    ],
                                ),
                                html.Div(
                                    className="pi-viz-sidebar-section",
                                    children=[
                                        _viz_sidebar_head("Projection", "bi bi-grid-3x3"),
                                        _viz_control(
                                            "Surface",
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
                                                className="form-select",
                                            ),
                                        ),
                                        _viz_control(
                                            "View",
                                            dbc.RadioItems(
                                                id="orientation-view-toggle",
                                                options=[
                                                    {"label": "2D", "value": "2d"},
                                                    {"label": "3D", "value": "3d"},
                                                ],
                                                value="2d",
                                                inline=True,
                                                className="pi-viz-btn-toggle",
                                                inputClassName="btn-check",
                                                labelClassName="btn btn-outline-secondary btn-sm",
                                                labelCheckedClassName="btn btn-secondary btn-sm",
                                            ),
                                        ),
                                    ],
                                ),
                                html.Div(
                                    className="pi-viz-sidebar-section",
                                    children=[
                                        _viz_sidebar_head("Display", "bi bi-aspect-ratio"),
                                        _viz_control(
                                            "Marker",
                                            dbc.Input(
                                                id="orientation-marker-size",
                                                type="number",
                                                min=1,
                                                max=75,
                                                step=1,
                                                value=40,
                                                className="form-control",
                                            ),
                                        ),
                                    ],
                                ),
                            ],
                        ),
                        # ── Main visualization ──
                        html.Div(
                            className="pi-viz-main",
                            children=[
                                _viz_graph_with_loading(
                                    dcc.Graph(
                                        id="orientation-map-graph",
                                        config={"displayModeBar": True, "scrollZoom": True},
                                        style={"height": "100%", "minHeight": "400px"},
                                    ),
                                    "orientation-loading-target",
                                ),
                                html.Div(
                                    id="orientation-point-details",
                                    className="pi-viz-details",
                                    children=html.Small(
                                        "Click a point on the map to view details.",
                                        className="text-muted",
                                    ),
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        ),
        # ==================================================================
        # Tab: Pole Figure — sidebar + plot
        # ==================================================================
        dbc.Tab(
            label="Pole Figure",
            tab_id="tab-poles",
            children=[
                html.Div(
                    id="tab-poles-content",
                    className="pi-viz-layout",
                    children=[
                        # ── Sidebar ──
                        html.Div(
                            className="pi-viz-sidebar",
                            children=[
                                html.Div(
                                    className="pi-viz-sidebar-section",
                                    children=[
                                        _viz_sidebar_head("Pole", "bi bi-bullseye"),
                                        _viz_control(
                                            "{hkl}",
                                            dbc.Select(
                                                id="stereo-hkl-select",
                                                options=[
                                                    {"label": "{100}", "value": "1,0,0"},
                                                    {"label": "{110}", "value": "1,1,0"},
                                                    {"label": "{111}", "value": "1,1,1"},
                                                    {"label": "{210}", "value": "2,1,0"},
                                                ],
                                                value="1,0,0",
                                                className="form-select",
                                            ),
                                        ),
                                        _viz_control(
                                            "Surface",
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
                                                className="form-select",
                                            ),
                                        ),
                                    ],
                                ),
                                html.Div(
                                    className="pi-viz-sidebar-section",
                                    children=[
                                        _viz_sidebar_head("Color", "bi bi-palette"),
                                        _viz_control(
                                            "Scheme",
                                            dbc.Select(
                                                id="stereo-color-select",
                                                options=[
                                                    {"label": "Position HSV", "value": "hsv_position"},
                                                    {"label": "Cubic IPF", "value": "ipf"},
                                                    {"label": "Uniform", "value": "uniform"},
                                                ],
                                                value="hsv_position",
                                                className="form-select",
                                            ),
                                        ),
                                        html.Div(
                                            id="stereo-color-rad-col",
                                            className="pi-viz-control",
                                            children=[
                                                html.Label("Radius"),
                                                dbc.Input(
                                                    id="stereo-color-rad",
                                                    type="number",
                                                    min=0.1,
                                                    max=90,
                                                    step="any",
                                                    value=22.5,
                                                    className="form-control",
                                                ),
                                                html.Span("\u00b0", className="pi-viz-unit"),
                                            ],
                                            style={"display": "flex", "alignItems": "center"},
                                        ),
                                        html.Div(
                                            id="pole-figure-reset-col",
                                            className="pi-viz-control",
                                            style={"display": "none"},
                                            children=[
                                                html.Label(""),
                                                dbc.Button(
                                                    "Reset color center",
                                                    id="pole-figure-reset-btn",
                                                    color="secondary",
                                                    size="sm",
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                                html.Div(
                                    className="pi-viz-sidebar-section",
                                    children=[
                                        _viz_sidebar_head("Display", "bi bi-aspect-ratio"),
                                        _viz_control(
                                            "Marker",
                                            dbc.Input(
                                                id="stereo-marker-size",
                                                type="number",
                                                min=1,
                                                max=75,
                                                step=1,
                                                value=12,
                                                className="form-control",
                                            ),
                                        ),
                                    ],
                                ),
                            ],
                        ),
                        # ── Main visualization ──
                        html.Div(
                            className="pi-viz-main",
                            children=[
                                _viz_graph_with_loading(
                                    dcc.Graph(
                                        id="stereo-plot-graph",
                                        config={
                                            "displayModeBar": True,
                                            "scrollZoom": True,
                                            "modeBarButtonsToAdd": ["lasso2d", "select2d"],
                                        },
                                        style={"height": "100%", "minHeight": "400px"},
                                    ),
                                    "poles-loading-target",
                                ),
                                html.Div(
                                    className="pi-viz-details",
                                    children=[
                                        html.Div(
                                            id="pole-figure-center-info",
                                            children=html.Small(
                                                "Click a point to set color center.",
                                                className="text-muted",
                                            ),
                                        ),
                                        html.Div(
                                            id="stereo-selection-info",
                                            children=html.Small(
                                                "Use lasso or box select to pick regions of interest.",
                                                className="text-muted",
                                            ),
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        ),
        # ==================================================================
        # Tab: Stereographic — sidebar + plot
        # ==================================================================
        dbc.Tab(
            label="Stereographic",
            tab_id="tab-stereo",
            children=[
                html.Div(
                    id="tab-stereo-content",
                    className="pi-viz-layout",
                    children=[
                        # ── Sidebar ──
                        html.Div(
                            className="pi-viz-sidebar",
                            children=[
                                html.Div(
                                    className="pi-viz-sidebar-section",
                                    children=[
                                        _viz_sidebar_head("Zoom", "bi bi-zoom-in"),
                                        html.Div(
                                            className="pi-viz-control",
                                            children=[
                                                html.Label("Range"),
                                                dcc.Input(
                                                    id="stereo-zoom-slider",
                                                    type="range",
                                                    min=5,
                                                    max=90,
                                                    step=5,
                                                    value=90,
                                                ),
                                                html.Span(
                                                    id="stereo-zoom-label",
                                                    children="90\u00b0",
                                                    className="pi-viz-unit",
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                                html.Div(
                                    className="pi-viz-sidebar-section",
                                    children=[
                                        _viz_sidebar_head("Wulff Net", "bi bi-globe2"),
                                        _viz_control(
                                            "",
                                            dbc.Checkbox(
                                                id="stereo-wulff-toggle",
                                                label="Show Wulff net",
                                                value=True,
                                            ),
                                        ),
                                        _viz_control(
                                            "Step",
                                            dbc.Select(
                                                id="stereo-wulff-step",
                                                options=[
                                                    {"label": "5\u00b0", "value": "5"},
                                                    {"label": "10\u00b0", "value": "10"},
                                                    {"label": "20\u00b0", "value": "20"},
                                                ],
                                                value="10",
                                                className="form-select",
                                            ),
                                        ),
                                    ],
                                ),
                                html.Div(
                                    className="pi-viz-sidebar-section",
                                    children=[
                                        _viz_sidebar_head("Display", "bi bi-aspect-ratio"),
                                        _viz_control(
                                            "Marker",
                                            dbc.Input(
                                                id="stereoprojection-marker-size",
                                                type="number",
                                                min=1,
                                                max=75,
                                                step=1,
                                                value=12,
                                                className="form-control",
                                            ),
                                        ),
                                    ],
                                ),
                                html.Div(
                                    className="pi-viz-sidebar-section",
                                    style={"padding": ".4rem .55rem"},
                                    children=[
                                        dbc.Button(
                                            [html.I(className="bi bi-play-fill me-1"), "Render"],
                                            id="stereo-render-btn",
                                            color="success",
                                            size="sm",
                                            style={"width": "100%"},
                                        ),
                                    ],
                                ),
                            ],
                        ),
                        # ── Main visualization ──
                        html.Div(
                            className="pi-viz-main",
                            children=[
                                _viz_graph_with_loading(
                                    dcc.Graph(
                                        id="stereo-projection-graph",
                                        config={"displayModeBar": True, "scrollZoom": True},
                                        style={"height": "100%", "minHeight": "400px"},
                                    ),
                                    "stereo-loading-target",
                                    text="Rendering\u2026",
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        ),
        # ==================================================================
        # Tab: Peaks — full-width table
        # ==================================================================
        dbc.Tab(
            label="Peaks",
            tab_id="tab-peaks",
            children=[
                html.Div(
                    id="tab-peaks-content",
                    className="pi-viz-table-wrap",
                    children=[
                        html.Div(id="peak-table-container"),
                    ],
                ),
            ],
        ),
    ],
)


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

layout = html.Div(
    [
        navbar.navbar,
        dcc.Location(id="url-peakindexing-page", refresh=False),
        # Store parsed XML data path so visualization callbacks can load it
        dcc.Store(id="peakindexing-xml-path"),
        # Store selected grain indices for cross-plot linking
        dcc.Store(id="selected-grain-indices", data=[]),
        # Store pole figure color center: {x, y, grain_index} or None
        dcc.Store(id="pole-figure-center", data=None),
        # Page header
        html.Div(
            id="peakindex-id-header",
            className="pi-page-header",
        ),
        # Visualization tabs
        _viz_tabs,
    ]
)


# ---------------------------------------------------------------------------
# Callback: load page data from DB + resolve XML path
# ---------------------------------------------------------------------------


@callback(
    Output("peakindex-id-header", "children"),
    Output("peakindexing-xml-path", "data"),
    Input("url-peakindexing-page", "href"),
    prevent_initial_call=True,
)
def load_peakindexing_data(href):
    if not href:
        raise PreventUpdate

    parsed_url = urllib.parse.urlparse(href)
    query_params = urllib.parse.parse_qs(parsed_url.query)

    peakindex_id_str = query_params.get("peakindex_id", [None])[0]

    root_path = DEFAULT_VARIABLES.get("root_path", "")

    xml_path = None  # Will be set if we find an XML file

    if peakindex_id_str:
        try:
            peakindex_id = int(peakindex_id_str)
            with Session(session_utils.get_engine()) as session:
                peakindex_data = (
                    session.query(db_schema.PeakIndex).filter(db_schema.PeakIndex.peakindex_id == peakindex_id).first()
                )
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

                    if any([not hasattr(peakindex_data, field) for field in ["data_path", "filenamePrefix"]]):
                        # If processing reconstruction data, use the reconstruction output folder as data path
                        if peakindex_data.wirerecon_id:
                            wirerecon_data = (
                                session.query(db_schema.WireRecon)
                                .filter(db_schema.WireRecon.wirerecon_id == peakindex_data.wirerecon_id)
                                .first()
                            )
                            if wirerecon_data:
                                if wirerecon_data.outputFolder:
                                    # Use the wire reconstruction output folder as the data path
                                    peakindex_data.data_path = remove_root_path_prefix(
                                        wirerecon_data.outputFolder, root_path
                                    )
                                if wirerecon_data.filenamePrefix:
                                    peakindex_data.filenamePrefix = wirerecon_data.filenamePrefix
                        elif peakindex_data.recon_id:
                            recon_data = (
                                session.query(db_schema.Recon)
                                .filter(db_schema.Recon.recon_id == peakindex_data.recon_id)
                                .first()
                            )
                            if recon_data:
                                if recon_data.file_output:
                                    # Use the reconstruction output folder as the data path
                                    peakindex_data.data_path = remove_root_path_prefix(
                                        recon_data.file_output, root_path
                                    )
                                if hasattr(recon_data, "filenamePrefix") and recon_data.filenamePrefix:
                                    peakindex_data.filenamePrefix = recon_data.filenamePrefix

                        if any([not hasattr(peakindex_data, field) for field in ["data_path", "filenamePrefix"]]):
                            # Retrieve data_path and filenamePrefix from catalog data
                            catalog_data = get_catalog_data(session, peakindex_data.scanNumber, root_path)
                        if not hasattr(peakindex_data, "data_path"):
                            peakindex_data.data_path = catalog_data.get("data_path", "")
                        if not hasattr(peakindex_data, "filenamePrefix"):
                            peakindex_data.filenamePrefix = catalog_data.get("filenamePrefix", [])

                    # Populate the form with the data
                    set_peakindex_form_props(peakindex_data, read_only=True)

                    # Get related links for header
                    related_links = []

                    # Add job link if it exists
                    if peakindex_data.job_id:
                        related_links.append(
                            html.A(f"Job ID: {peakindex_data.job_id}", href=f"/job?job_id={peakindex_data.job_id}")
                        )

                    if peakindex_data.recon_id:
                        related_links.append(
                            html.A(
                                f"Reconstruction ID: {peakindex_data.recon_id}",
                                href=f"/reconstruction?recon_id={peakindex_data.recon_id}",
                            )
                        )
                    elif peakindex_data.wirerecon_id:
                        related_links.append(
                            html.A(
                                f"Wire Reconstruction ID: {peakindex_data.wirerecon_id}",
                                href=f"/wire_reconstruction?wirerecon_id={peakindex_data.wirerecon_id}",
                            )
                        )

                    # Add scan link
                    if peakindex_data.scanNumber:
                        related_links.append(
                            html.A(
                                f"Scan ID: {peakindex_data.scanNumber}",
                                href=f"/scan?scan_id={peakindex_data.scanNumber}",
                            )
                        )

                    # Build header with links using modernised classes
                    header_content = [
                        html.Span(f"Peak Indexing ID: {peakindex_id}", className="pi-page-title"),
                    ]

                    if related_links:
                        link_children = []
                        for i, link in enumerate(related_links):
                            if i > 0:
                                link_children.append(html.Span("|", className="pi-page-sep"))
                            link_children.append(link)
                        header_content.append(html.Span(link_children, className="pi-page-links"))

                    return header_content, xml_path
        except Exception as e:
            print(f"Error loading peak indexing data: {e}")
            traceback.print_exc()
            return [
                html.Span(f"Error loading data for Peak Indexing ID: {peakindex_id}", className="pi-page-title")
            ], None

    return [html.Span("No Peak Indexing ID provided", className="pi-page-title")], None


# ---------------------------------------------------------------------------
# Callback: update orientation map when XML is available or color changes
# ---------------------------------------------------------------------------


@callback(
    Output("orientation-map-graph", "figure"),
    Output("orientation-marker-size", "value"),
    Output("orientation-loading-target", "children"),
    Input("peakindexing-xml-path", "data"),
    Input("orientation-color-select", "value"),
    Input("orientation-surface-select", "value"),
    Input("orientation-marker-size", "value"),
    Input("orientation-view-toggle", "value"),
    Input("selected-grain-indices", "data"),
    Input("pole-figure-center", "data"),
    Input("stereo-hkl-select", "value"),
    Input("stereo-color-rad", "value"),
    Input("stereo-surface-select", "value"),
    prevent_initial_call=True,
)
def update_orientation_map(
    xml_path,
    color_by,
    surface,
    input_size,
    view_mode,
    selected_grains,
    pole_center,
    pole_hkl_str,
    pole_color_rad_deg,
    pole_surface,
):
    if not xml_path:
        raise PreventUpdate

    # Skip unnecessary re-renders: if a pole-figure-only control
    # (hkl, color radius, surface) changed but the orientation map
    # isn't using pole_hsv mode, there is nothing to update.
    triggered = dash.ctx.triggered_id
    _POLE_ONLY_TRIGGERS = {"stereo-hkl-select", "stereo-color-rad", "stereo-surface-select"}
    if triggered in _POLE_ONLY_TRIGGERS and (color_by or "cubic_ipf") != "pole_hsv":
        raise PreventUpdate

    try:
        from laue_portal.analysis.xml_parser import parse_indexing_xml
        from laue_portal.components.visualization.orientation_map import (
            apply_selection_highlight,
            make_orientation_map,
            make_orientation_map_3d,
        )

        parsed = parse_indexing_xml(xml_path)

        marker_size = max(1, int(input_size or 40))

        # Determine effective color mode and reference grain.
        effective_color = color_by or "cubic_ipf"
        ref_grain_index = None
        if pole_center and pole_center.get("grain_index") is not None:
            ref_grain_index = pole_center["grain_index"]

        # Pole figure parameters for pole_hsv mode
        pole_hkl = None
        pole_center_xy = None
        pole_rad = float(pole_color_rad_deg or 22.5)

        if effective_color == "pole_hsv":
            # Parse hkl from the pole figure selector
            if pole_hkl_str:
                pole_hkl = tuple(int(x) for x in pole_hkl_str.split(","))
            else:
                pole_hkl = (1, 0, 0)

            # Use pole figure center if available
            if pole_center:
                pole_center_xy = (pole_center.get("x", 0.0), pole_center.get("y", 0.0))

            # Use pole figure surface for consistency
            if pole_surface:
                surface = pole_surface

        if view_mode == "3d":
            fig = make_orientation_map_3d(
                parsed,
                color_by=effective_color,
                marker_size=marker_size,
                surface=surface or "normal",
                ref_grain_index=ref_grain_index,
                pole_hkl=pole_hkl,
                pole_center_xy=pole_center_xy,
                pole_color_rad_deg=pole_rad,
            )
        else:
            fig = make_orientation_map(
                parsed,
                color_by=effective_color,
                marker_size=marker_size,
                surface=surface or "normal",
                ref_grain_index=ref_grain_index,
                pole_hkl=pole_hkl,
                pole_center_xy=pole_center_xy,
                pole_color_rad_deg=pole_rad,
            )

        # Cross-plot highlighting: dim unselected points, ring selected ones
        if selected_grains:
            apply_selection_highlight(fig, parsed, selected_grains, marker_size, is_3d=(view_mode == "3d"))

        return fig, marker_size, ""
    except PreventUpdate:
        raise
    except Exception as e:
        print(f"Error creating orientation map: {e}")
        traceback.print_exc()
        raise PreventUpdate from None


# ---------------------------------------------------------------------------
# Callback: show selected point details on orientation map click
# ---------------------------------------------------------------------------


@callback(
    Output("orientation-point-details", "children"),
    Input("orientation-map-graph", "clickData"),
    State("peakindexing-xml-path", "data"),
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

            from laue_portal.analysis.xml_parser import get_step_peaks, parse_indexing_xml

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

            from laue_portal.analysis.xml_parser import get_step_peaks, parse_indexing_xml

            parsed = parse_indexing_xml(xml_path)
            step_peaks = get_step_peaks(parsed, step_idx)
            n_peaks_total = step_peaks["n_peaks"] if step_peaks else 0

        detail_card = dbc.Card(
            dbc.CardBody(
                [
                    html.H6("Selected Point Details", className="card-title"),
                    html.P(
                        [
                            html.Strong(f"Step #{step_idx}"),
                            f"  Position: ({x_pos:.1f}, {y_pos:.1f}, {z_pos:.1f})",
                        ]
                    ),
                    html.P(
                        [
                            f"Patterns: {n_pat}  |  "
                            f"Indexed: {n_idx}/{n_peaks_total}  |  "
                            f"Goodness: {goodness:.1f}  |  "
                            f"RMS error: {rms_err:.5f} deg",
                        ]
                    ),
                ]
            ),
            className="mt-2",
        )
        return detail_card
    except PreventUpdate:
        raise
    except Exception as e:
        print(f"Error showing point details: {e}")
        traceback.print_exc()
        raise PreventUpdate from None


# ---------------------------------------------------------------------------
# Callback: update pole figure plot (auto-renders on data/control changes)
# ---------------------------------------------------------------------------


@callback(
    Output("stereo-plot-graph", "figure"),
    Output("stereo-marker-size", "value"),
    Output("stereo-color-rad-col", "style"),
    Output("poles-loading-target", "children"),
    Input("peakindexing-xml-path", "data"),
    Input("stereo-hkl-select", "value"),
    Input("stereo-marker-size", "value"),
    Input("stereo-color-select", "value"),
    Input("stereo-color-rad", "value"),
    Input("stereo-surface-select", "value"),
    Input("pole-figure-center", "data"),
    prevent_initial_call=True,
)
def update_pole_figure(
    xml_path,
    hkl_str,
    input_size,
    color_scheme,
    color_rad_deg,
    surface,
    pole_center,
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

        marker_size = max(1, int(input_size or 12))
        hkl = tuple(int(x) for x in hkl_str.split(","))

        # Pass center from store if available
        center_xy = None
        if pole_center and color_scheme == "hsv_position":
            center_xy = (pole_center["x"], pole_center["y"])

        fig = make_pole_figure(
            parsed,
            hkl=hkl,
            color_scheme=color_scheme or "hsv_position",
            color_rad_deg=float(color_rad_deg or 22.5),
            marker_size=marker_size,
            surface=surface or "normal",
            center_xy=center_xy,
        )

        return fig, marker_size, rad_col_style, ""
    except PreventUpdate:
        raise
    except Exception as e:
        print(f"Error creating pole figure: {e}")
        traceback.print_exc()
        raise PreventUpdate from None


# ---------------------------------------------------------------------------
# Callback: render stereographic projection (on-demand via button click)
# ---------------------------------------------------------------------------


@callback(
    Output("stereo-projection-graph", "figure"),
    Output("stereoprojection-marker-size", "value"),
    Output("stereo-zoom-label", "children"),
    Output("stereo-loading-target", "children"),
    Input("stereo-render-btn", "n_clicks"),
    State("peakindexing-xml-path", "data"),
    State("stereo-zoom-slider", "value"),
    State("stereo-wulff-toggle", "value"),
    State("stereo-wulff-step", "value"),
    State("stereoprojection-marker-size", "value"),
    prevent_initial_call=True,
)
def render_stereo_projection(
    n_clicks,
    xml_path,
    zoom_deg,
    show_wulff,
    wulff_step,
    input_size,
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

        return fig, marker_size, zoom_label, ""
    except PreventUpdate:
        raise
    except Exception as e:
        print(f"Error creating stereo projection: {e}")
        traceback.print_exc()
        raise PreventUpdate from None


# ---------------------------------------------------------------------------
# Callback: populate indexed peaks table when XML is available
# ---------------------------------------------------------------------------


@callback(
    Output("peak-table-container", "children"),
    Input("peakindexing-xml-path", "data"),
    prevent_initial_call=True,
)
def update_peak_table(xml_path):
    if not xml_path:
        raise PreventUpdate

    try:
        from laue_portal.analysis.xml_parser import get_all_indexed_peaks, parse_indexing_xml
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
# Callback: handle click on pole figure to set/clear color center
# ---------------------------------------------------------------------------


@callback(
    Output("pole-figure-center", "data"),
    Output("pole-figure-center-info", "children"),
    Output("pole-figure-reset-col", "style"),
    Output("orientation-color-select", "value"),
    Input("stereo-plot-graph", "clickData"),
    Input("pole-figure-reset-btn", "n_clicks"),
    State("pole-figure-center", "data"),
    State("peakindexing-xml-path", "data"),
    State("stereo-hkl-select", "value"),
    State("stereo-surface-select", "value"),
    State("orientation-color-select", "value"),
    prevent_initial_call=True,
)
def handle_pole_figure_click(click_data, reset_clicks, current_center, xml_path, hkl_str, surface, current_color_by):
    """Set or clear the HSV color center when a point is clicked or reset is pressed."""
    triggered = dash.ctx.triggered_id
    _default_hint = html.Small(
        "Click a point to set color center.",
        className="text-muted",
    )
    _hide_btn = {"display": "none"}

    # Reset button was clicked -- revert to default IPF coloring
    if triggered == "pole-figure-reset-btn":
        restore_color = "cubic_ipf"
        if current_center is not None and current_center.get("prev_color_by"):
            restore_color = current_center["prev_color_by"]
        return None, _default_hint, _hide_btn, restore_color

    # Pole figure click
    if not click_data or not click_data.get("points"):
        raise PreventUpdate

    point = click_data["points"][0]

    x = point.get("x")
    y = point.get("y")
    customdata = point.get("customdata")
    if x is None or y is None:
        raise PreventUpdate

    # Extract grain index -- try customdata first, fall back to pointIndex
    grain_index = None
    if customdata is not None and len(customdata) > 0:
        grain_index = int(customdata[0])
    else:
        # Scattergl may omit customdata in clickData.  Use pointIndex to
        # look up the grain index from the pole figure mapping.
        point_index = point.get("pointIndex", point.get("pointNumber"))
        if point_index is not None and xml_path:
            try:
                import numpy as np

                from laue_portal.analysis.projection import (
                    cubic_hkl_family,
                    get_surface_vectors,
                    pole_figure_points,
                )
                from laue_portal.analysis.xml_parser import parse_indexing_xml

                parsed = parse_indexing_xml(xml_path)
                hkl = tuple(int(v) for v in hkl_str.split(","))
                family = cubic_hkl_family(*hkl)
                surf_normal, _, _ = get_surface_vectors(surface or "normal")
                pts, grain_indices = pole_figure_points(
                    parsed["recip_lattices"],
                    family,
                    surface_normal=surf_normal,
                )
                if len(pts) > 0:
                    finite_mask = np.all(np.isfinite(pts), axis=1)
                    grain_indices = grain_indices[finite_mask]
                if 0 <= point_index < len(grain_indices):
                    grain_index = int(grain_indices[point_index])
            except Exception as e:
                print(f"Error resolving grain index from click: {e}")
                traceback.print_exc()

    if grain_index is None:
        raise PreventUpdate

    # Toggle: clicking the current reference clears it
    if current_center is not None and current_center.get("grain_index") == grain_index:
        restore_color = "cubic_ipf"
        if current_center is not None and current_center.get("prev_color_by"):
            restore_color = current_center["prev_color_by"]
        return None, _default_hint, _hide_btn, restore_color

    # Save the current color mode so we can restore it on reset
    prev_color = current_color_by if current_color_by not in ("misorientation", "pole_hsv") else "cubic_ipf"
    new_center = {
        "x": float(x),
        "y": float(y),
        "grain_index": grain_index,
        "prev_color_by": prev_color,
    }
    grain_label = f"grain #{grain_index}"
    info = html.Small(
        [
            html.Strong("Color center: "),
            f"{grain_label} at ({x:.3f}, {y:.3f})",
        ]
    )
    _show_btn = {"display": "flex", "alignItems": "center"}

    return new_center, info, _show_btn, "pole_hsv"


# ---------------------------------------------------------------------------
# Callback: handle lasso/box selection on pole figure (ROI picking)
# ---------------------------------------------------------------------------


@callback(
    Output("selected-grain-indices", "data"),
    Output("stereo-selection-info", "children"),
    Input("stereo-plot-graph", "selectedData"),
    State("peakindexing-xml-path", "data"),
    State("stereo-hkl-select", "value"),
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

            from laue_portal.analysis.projection import (
                cubic_hkl_family,
                pole_figure_points,
            )
            from laue_portal.analysis.xml_parser import parse_indexing_xml

            parsed = parse_indexing_xml(xml_path)

            hkl = tuple(int(x) for x in hkl_str.split(","))
            family = cubic_hkl_family(*hkl)
            points, grain_indices = pole_figure_points(
                parsed["recip_lattices"],
                family,
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
            "No grains in selection.",
            className="text-muted",
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
                from laue_portal.analysis.orientation import (
                    batch_orientations,
                    pairwise_misorientation,
                )
                from laue_portal.analysis.xml_parser import parse_indexing_xml

                parsed = parse_indexing_xml(xml_path)
                orientations = batch_orientations(
                    parsed["recip_lattices"],
                    parsed["lattice_params"],
                )

                # Only compute if selected indices are within bounds
                valid_indices = [i for i in selected if i < len(orientations)]
                if len(valid_indices) >= 2:
                    mis = pairwise_misorientation(
                        orientations,
                        indices=valid_indices,
                        symmetry_reduce=True,
                    )
                    misorientation_info = [
                        html.Br(),
                        html.Strong("Misorientation: "),
                        f"mean {mis['mean']:.2f}\u00b0, range [{mis['min']:.2f}\u00b0, {mis['max']:.2f}\u00b0]",
                    ]
            except Exception as e:
                print(f"Error computing misorientation: {e}")
                traceback.print_exc()

    # Build summary card
    summary = dbc.Card(
        dbc.CardBody(
            [
                html.H6("ROI Selection", className="card-title"),
                html.P(
                    [
                        html.Strong("Selected: "),
                        f"{n_poles} poles from {len(selected)} grain{'s' if len(selected) != 1 else ''}",
                        *misorientation_info,
                    ]
                ),
                html.Small(
                    "Selected grains are highlighted on the Orientation tab.",
                    className="text-muted",
                ),
            ]
        ),
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
