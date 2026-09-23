"""Wire reconstruction detail page: Parameters, Points, Depth View, and ROI Inspector.

The browser holds identities only -- the artifact path, the selected point,
the depth index, and ROI definitions. Stored frames, reference images, and
traces are prepared by lauelab on the server and cached by
``laue_portal.services.reconstruction_view``; the page receives one 2D image
and small 1D traces at a time. Each figure has exactly one owning callback, so
Dash drops an in-flight response when the same callback is requested again and
a slow response cannot overwrite a newer point or ROI selection.
"""

import urllib.parse

import dash
import dash_ag_grid as dag
import dash_bootstrap_components as dbc
import numpy as np
from dash import Input, Output, Patch, State, callback, dcc, html
from dash.exceptions import PreventUpdate
from lauelab.reconstruct.inspection import ReferenceImage
from lauelab.visualization import (
    DEPTH_AXIS_OPTIONS,
    INTENSITY_OPTIONS,
    REFERENCE_OPTIONS,
    plot_reference_image,
    plot_roi_traces,
)
from sqlalchemy.orm import Session

import laue_portal.components.navbar as navbar
import laue_portal.database.session_utils as session_utils
from laue_portal.components.detail_layout import detail_header, detail_header_content
from laue_portal.components.visualization import depth_view
from laue_portal.components.visualization.detector_view import IMAGE_COLOR_SCALES
from laue_portal.components.visualization.viz_layout import viz_control, viz_graph_with_loading, viz_sidebar_head
from laue_portal.components.wire_recon_form import set_wire_recon_form_props, wire_recon_readonly_form
from laue_portal.config import DEFAULT_VARIABLES
from laue_portal.database.db_utils import get_catalog_data, remove_root_path_prefix
from laue_portal.services import reconstruction_view as view
from laue_portal.workflows.reconstruction import get_reconstruction

dash.register_page(__name__, path="/wire_reconstruction")

TAB_PARAMETERS = "wire-recon-tab-parameters"
TAB_POINTS = "wire-recon-tab-points"
TAB_DEPTH = "wire-recon-tab-depth"
TAB_ROI = "wire-recon-tab-roi"
DEFAULT_ROI_SIZE = 9
GRAPH_CONFIG = {"displayModeBar": True, "scrollZoom": True, "displaylogo": False}


def _options(choices):
    return [{"label": choice.label.replace("(um)", "(µm)"), "value": choice.value} for choice in choices]


def _graph(graph_id, loading_id):
    return viz_graph_with_loading(
        dcc.Graph(id=graph_id, config=GRAPH_CONFIG, style={"height": "100%", "minHeight": 0}), loading_id
    )


def _axis_controls(prefix):
    return [
        viz_control(
            "X axis",
            dbc.RadioItems(id=f"{prefix}-axis", options=_options(DEPTH_AXIS_OPTIONS), value="depth", inline=True),
        ),
        viz_control(
            "Y axis",
            dbc.RadioItems(
                id=f"{prefix}-yscale",
                options=[{"label": "Linear", "value": "linear"}, {"label": "Log", "value": "log"}],
                value="linear",
                inline=True,
            ),
        ),
    ]


POINT_COLUMNS = [
    {"field": "point_id", "headerName": "Point", "pinned": "left", "minWidth": 160},
    {"field": "status", "headerName": "Status", "width": 120},
    {"field": "n_depths", "headerName": "Depths", "width": 100},
    {"field": "depth_first_um", "headerName": "First depth (µm)", "width": 150},
    {"field": "depth_last_um", "headerName": "Last depth (µm)", "width": 150},
    {"field": "shape", "headerName": "Frame (y x)", "width": 130},
    {"field": "dtype", "headerName": "Stored type", "width": 120},
    {"field": "sample_position_um", "headerName": "Sample x, y, z (µm)", "width": 200},
    {"field": "source", "headerName": "Source", "minWidth": 240, "flex": 1},
    {"field": "error", "headerName": "Error", "minWidth": 240, "flex": 1},
]

ROI_COLUMNS = [
    {"field": "id", "headerName": "ROI", "checkboxSelection": True, "headerCheckboxSelection": True, "width": 110},
    {"field": "y", "headerName": "Y", "width": 70},
    {"field": "x", "headerName": "X", "width": 70},
    {"field": "size", "headerName": "Size", "width": 70},
    {
        "field": "color",
        "headerName": "Color",
        "width": 80,
        "cellStyle": {"function": "({'backgroundColor': params.value, 'color': params.value})"},
    },
    {"field": "delete", "headerName": "", "cellRenderer": "RowDeleteButton", "width": 50, "sortable": False},
]

points_tab = html.Div(
    className="pi-viz-table-wrap",
    children=[
        html.Div(id="wr-points-message", className="small text-muted mb-2"),
        dag.AgGrid(
            id="wr-points-grid",
            columnDefs=POINT_COLUMNS,
            rowData=[],
            getRowId="params.data.point_id",
            dashGridOptions={"rowSelection": "single", "suppressCellFocus": True},
            defaultColDef={"resizable": True, "sortable": True, "filter": True},
            style={"height": "calc(100% - 2rem)"},
        ),
    ],
)

depth_tab = html.Div(
    className="pi-viz-layout",
    children=[
        html.Div(
            className="pi-viz-sidebar",
            children=[
                html.Div(
                    className="pi-viz-sidebar-section",
                    children=[
                        viz_sidebar_head("Depth", "bi bi-layers"),
                        viz_control(
                            "Index",
                            dbc.Input(id="wr-depth-index", type="number", min=0, step=1, value=0, debounce=True),
                        ),
                        html.Div(id="wr-depth-readout", className="small text-muted px-3"),
                    ],
                ),
                html.Div(
                    className="pi-viz-sidebar-section",
                    children=[
                        viz_sidebar_head("Image", "bi bi-image"),
                        viz_control(
                            "Colormap",
                            dbc.Select(
                                id="wr-depth-colormap",
                                options=[{"label": name, "value": name} for name in IMAGE_COLOR_SCALES],
                                value="gray",
                            ),
                        ),
                    ],
                ),
            ],
        ),
        html.Div(
            className="pi-viz-main wr-stack",
            children=[
                html.Div(id="wr-depth-status", className="pi-viz-status small text-warning"),
                html.Div(_graph("wr-depth-frame", "wr-depth-frame-loading"), className="wr-panel wr-panel-image"),
            ],
        ),
    ],
)

roi_tab = html.Div(
    className="pi-viz-layout",
    children=[
        html.Div(
            className="pi-viz-sidebar",
            children=[
                html.Div(
                    className="pi-viz-sidebar-section",
                    children=[
                        viz_sidebar_head("Reference", "bi bi-image"),
                        viz_control(
                            "Image",
                            dbc.Select(
                                id="wr-roi-reference", options=_options(REFERENCE_OPTIONS), value="sum_reconstructed"
                            ),
                        ),
                    ],
                ),
                html.Div(
                    className="pi-viz-sidebar-section",
                    children=[
                        viz_sidebar_head("ROIs", "bi bi-bounding-box"),
                        viz_control(
                            "Size",
                            dbc.Input(id="wr-roi-size", type="number", min=1, step=1, value=DEFAULT_ROI_SIZE),
                            html.Span("px", className="pi-viz-unit"),
                        ),
                    ],
                ),
                html.Div(
                    className="pi-viz-sidebar-section",
                    children=[
                        viz_sidebar_head("Traces", "bi bi-graph-up"),
                        *_axis_controls("wr-roi"),
                        viz_control(
                            "ROI values",
                            dbc.RadioItems(id="wr-roi-intensity", options=_options(INTENSITY_OPTIONS), value="sum"),
                        ),
                    ],
                ),
            ],
        ),
        html.Div(
            className="pi-viz-main wr-roi-main",
            children=[
                html.Div(id="wr-roi-status", className="pi-viz-status small wr-roi-status"),
                html.Div(_graph("wr-roi-image", "wr-roi-image-loading"), className="wr-panel wr-roi-image"),
                html.Div(
                    className="wr-panel wr-roi-list",
                    children=[
                        dag.AgGrid(
                            id="wr-roi-grid",
                            columnDefs=ROI_COLUMNS,
                            rowData=[],
                            getRowId="params.data.id",
                            dashGridOptions={
                                "rowSelection": "multiple",
                                "suppressRowClickSelection": True,
                                "suppressCellFocus": True,
                            },
                            defaultColDef={"resizable": True},
                            style={"height": "100%"},
                        ),
                    ],
                ),
                html.Div(_graph("wr-roi-traces", "wr-roi-traces-loading"), className="wr-panel wr-roi-traces"),
            ],
        ),
    ],
)

layout = html.Div(
    [
        navbar.navbar,
        dcc.Location(id="url-wire-recon-page", refresh=False),
        # Where the run's pixels are ({kind, path}); scientific products stay on the server.
        dcc.Store(id="wr-artifact"),
        dcc.Store(id="wr-point"),
        # {point_id: {"next": n, "rois": [...]}}, this page session only.
        dcc.Store(id="wr-rois", data={}),
        # Overlay traces currently drawn on the ROI image, for incremental updates.
        dcc.Store(id="wr-roi-overlays", data={"point": None, "count": 0}),
        # The frame currently drawn in Depth View, so revisiting the tab resends nothing.
        dcc.Store(id="wr-depth-drawn", data=None),
        detail_header("wire-recon-id-header"),
        html.Div(id="wr-point-bar", className="lp-artifact-bar d-flex align-items-center gap-3 px-3 py-1 small"),
        dbc.Tabs(
            id="wire-recon-detail-tabs",
            active_tab=TAB_PARAMETERS,
            className="lp-detail-tabs",
            children=[
                dbc.Tab(
                    label="Parameters",
                    tab_id=TAB_PARAMETERS,
                    children=[
                        html.Div(
                            id="wire-recon-tab-parameters-content",
                            className="pt-3 px-2",
                            children=[wire_recon_readonly_form],
                        )
                    ],
                ),
                dbc.Tab(label="Points", tab_id=TAB_POINTS, children=[points_tab]),
                dbc.Tab(label="Depth View", tab_id=TAB_DEPTH, children=[depth_tab]),
                dbc.Tab(label="ROI Inspector", tab_id=TAB_ROI, children=[roi_tab]),
            ],
        ),
    ],
    className="pi-page wr-page",
)


def _empty_figure(message):
    figure = {
        "data": [],
        "layout": {
            "xaxis": {"visible": False},
            "yaxis": {"visible": False},
            "annotations": [{"text": message, "showarrow": False, "xref": "paper", "yref": "paper"}],
            "plot_bgcolor": "white",
        },
    }
    return figure


@callback(
    Output("wire-recon-id-header", "children"),
    Output("wr-artifact", "data"),
    Input("url-wire-recon-page", "href"),
    prevent_initial_call=True,
)
def load_wire_recon_data(href):
    if not href:
        raise PreventUpdate

    parsed_url = urllib.parse.urlparse(href)
    query_params = urllib.parse.parse_qs(parsed_url.query)

    reconstruction_id_str = query_params.get("reconstruction_id", [None])[0]

    root_path = DEFAULT_VARIABLES.get("root_path", "")

    if reconstruction_id_str:
        try:
            reconstruction_id = int(reconstruction_id_str)
            reconstruction = get_reconstruction(reconstruction_id)
            if reconstruction and reconstruction.method == "wire" and reconstruction.wire_parameters:
                artifact = view.locate_artifact(reconstruction.output_path)
                with Session(session_utils.get_engine()) as session:
                    # Add root_path from DEFAULT_VARIABLES
                    root_path = DEFAULT_VARIABLES.get("root_path", "")
                    reconstruction.root_path = root_path

                    # Convert full paths back to relative paths for display
                    if reconstruction.wire_parameters.geometry_file:
                        reconstruction.wire_parameters.geometry_file = remove_root_path_prefix(
                            reconstruction.wire_parameters.geometry_file, root_path
                        )
                    if reconstruction.output_path:
                        reconstruction.output_path = remove_root_path_prefix(reconstruction.output_path, root_path)

                    reconstruction.data_path = remove_root_path_prefix(reconstruction.input_path, root_path)

                    if not reconstruction.input_path:
                        catalog_data = get_catalog_data(session, reconstruction.scan_number, root_path)
                        reconstruction.data_path = catalog_data.get("data_path", "")

                    # Populate the form with the data
                    set_wire_recon_form_props(reconstruction, read_only=True)

                    # Get related links
                    related_links = []

                    # Add job link if it exists
                    if reconstruction.job_id:
                        related_links.append(
                            (f"Job ID: {reconstruction.job_id}", f"/job?job_id={reconstruction.job_id}")
                        )

                    # Add scan link
                    if reconstruction.scan_number:
                        related_links.append(
                            (
                                f"Scan ID: {reconstruction.scan_number}",
                                f"/scan?scan_id={reconstruction.scan_number}",
                            )
                        )

                    header = detail_header_content(f"Reconstruction R{reconstruction_id}", related_links)
                    return header, artifact.to_store() if artifact else None

        except Exception as e:
            print(f"Error loading wire reconstruction data: {e}")
            return detail_header_content(f"Error loading reconstruction R{reconstruction_id_str}"), None

    return detail_header_content("No reconstruction ID provided"), None


# --- Points ----------------------------------------------------------------------


@callback(
    Output("wr-points-grid", "rowData"),
    Output("wr-points-message", "children"),
    Output("wr-point", "data"),
    Input("wr-artifact", "data"),
)
def load_points(artifact_data):
    """Catalog rows only; the first complete point becomes the initial selection."""

    artifact = view.Artifact.from_store(artifact_data)
    if artifact is None:
        return [], "No reconstructed images were found for this run.", None
    try:
        rows = view.point_rows(artifact)
    except (OSError, ValueError) as error:
        return [], f"Could not read the reconstruction: {error}", None
    first = next((row["point_id"] for row in rows if row["status"] == "complete"), None)
    if artifact.kind == view.KIND_SCAN:
        message = f"Reconstruction file {artifact.path}"
    else:
        message = (
            f"Per-depth files in {artifact.path}. Depths are read when a point is opened, and raw "
            "reference images were not recorded for these runs."
        )
    for row in rows:
        position = row.pop("sample_position_um")
        row["sample_position_um"] = ", ".join(f"{value:.1f}" for value in position) if position else ""
    return rows, message, first


@callback(
    Output("wr-point", "data", allow_duplicate=True),
    Output("wr-points-message", "children", allow_duplicate=True),
    Input("wr-points-grid", "selectedRows"),
    State("wr-point", "data"),
    prevent_initial_call=True,
)
def select_point(selected, current):
    if not selected:
        raise PreventUpdate
    row = selected[0]
    if row["status"] != "complete":
        detail = f": {row['error']}" if row.get("error") else ""
        return dash.no_update, f"Point {row['point_id']} is {row['status']} and has no images{detail}"
    if row["point_id"] == current:
        raise PreventUpdate
    return row["point_id"], dash.no_update


@callback(
    Output("wr-point-bar", "children"),
    Output("wr-points-grid", "selectedRows"),
    Input("wr-point", "data"),
    State("wr-points-grid", "rowData"),
)
def show_point(point_id, rows):
    rows = rows or []
    complete = sum(row["status"] == "complete" for row in rows)
    counts = html.Span(f"{complete} of {len(rows)} points complete", className="text-muted")
    selected = [row for row in rows if row["point_id"] == point_id]
    label = html.Strong(f"Point {point_id}") if point_id else html.Span("No point selected", className="text-muted")
    return [label, counts], selected


# --- Depth View ---------------------------------------------------------------------


def _artifact_and_point(artifact_data, point_id):
    artifact = view.Artifact.from_store(artifact_data)
    if artifact is None or not point_id:
        return None, None
    return artifact, point_id


@callback(
    Output("wr-depth-index", "max"),
    Output("wr-depth-index", "value"),
    Input("wr-point", "data"),
    Input("wire-recon-detail-tabs", "active_tab"),
    State("wr-artifact", "data"),
    State("wr-depth-index", "value"),
)
def reset_depth_index(point_id, tab, artifact_data, index):
    """A new point opens at the depth of its brightest full frame."""

    artifact, point_id = _artifact_and_point(artifact_data, point_id)
    if artifact is None or tab != TAB_DEPTH:
        raise PreventUpdate
    try:
        summary = view.point_summary(artifact, point_id)
        if dash.ctx.triggered_id == "wire-recon-detail-tabs" and index is not None and index < summary.shape[0]:
            return summary.shape[0] - 1, dash.no_update
        trace = view.full_trace(artifact, point_id)
    except view.ViewError:
        raise PreventUpdate from None
    return summary.shape[0] - 1, int(trace.values.argmax())


@callback(
    Output("wr-depth-frame", "figure"),
    Output("wr-depth-readout", "children"),
    Output("wr-depth-status", "children"),
    Output("wr-depth-frame-loading", "children"),
    Output("wr-depth-drawn", "data"),
    Input("wr-depth-index", "value"),
    Input("wr-depth-colormap", "value"),
    Input("wire-recon-detail-tabs", "active_tab"),
    State("wr-point", "data"),
    State("wr-artifact", "data"),
    State("wr-depth-drawn", "data"),
)
def show_depth_frame(index, colormap, tab, point_id, artifact_data, drawn):
    artifact, point_id = _artifact_and_point(artifact_data, point_id)
    if tab != TAB_DEPTH:
        raise PreventUpdate
    if artifact is None:
        return _empty_figure("Select a complete point"), "", "", "", None
    try:
        summary = view.point_summary(artifact, point_id)
        if index is None or not 0 <= int(index) < summary.shape[0]:
            message = f"Depth index must be 0 to {summary.shape[0] - 1}"
            return dash.no_update, "", message, "", dash.no_update
        index = int(index)
        key = {"artifact": artifact.path, "point": point_id, "index": index, "colormap": colormap}
        if drawn == key:
            raise PreventUpdate
        image = view.stored_frame(artifact, point_id, index)
    except view.ViewError as error:
        return dash.no_update, "", str(error), "", dash.no_update
    depth = float(summary.depth_um[index])
    figure = depth_view.frame_figure(
        image,
        point_id=point_id,
        depth_index=index,
        depth_um=depth,
        colormap=colormap,
        limits=depth_view.auto_limits(image),
    )
    readout = f"{depth:.4g} µm of {summary.depth_um[0]:.4g} to {summary.depth_um[-1]:.4g} µm"
    return figure, readout, "", "", key


# --- ROI Inspector ---------------------------------------------------------------------


@callback(
    Output("wr-rois", "data"),
    Output("wr-roi-grid", "rowData"),
    Output("wr-roi-grid", "selectedRows"),
    Output("wr-roi-status", "children"),
    Input("wr-point", "data"),
    Input("wr-roi-image", "clickData"),
    Input("wr-roi-grid", "cellRendererData"),
    State("wr-roi-size", "value"),
    State("wr-rois", "data"),
    State("wr-roi-grid", "selectedRows"),
    State("wr-artifact", "data"),
)
def edit_rois(point_id, click, deleted, size, state, selected, artifact_data):
    """The single owner of ROI definitions, the ROI list, and its selection."""

    trigger = dash.ctx.triggered_id
    rois = depth_view.point_rois(state, point_id)
    selected_ids = [row["id"] for row in selected or []]
    if trigger == "wr-point" or trigger is None:
        # Each point keeps its own ROIs; all start selected when the point is shown again.
        rows = depth_view.roi_rows(rois)
        return dash.no_update, rows, rows, ""
    if not point_id:
        raise PreventUpdate
    if trigger == "wr-roi-grid":
        # A row's delete button; the other ROIs keep their selection.
        roi_id = (deleted or {}).get("value")
        if roi_id is None:
            raise PreventUpdate
        state = depth_view.delete_rois(state, point_id, [roi_id])
        rows = depth_view.roi_rows(depth_view.point_rois(state, point_id))
        return state, rows, [row for row in rows if row["id"] in selected_ids], ""
    # Every click on the image itself adds an ROI; a click on an ROI outline does not.
    if not click or not click.get("points"):
        raise PreventUpdate
    clicked = click["points"][0]
    if clicked.get("curveNumber", 0) != 0:
        raise PreventUpdate
    artifact = view.Artifact.from_store(artifact_data)
    try:
        shape = view.point_summary(artifact, point_id).shape[1:]
        state, roi = depth_view.add_roi(state, point_id, size, clicked["x"], clicked["y"], shape)
    except (depth_view.RoiPlacementError, view.ViewError) as error:
        return dash.no_update, dash.no_update, dash.no_update, html.Span(str(error), className="text-danger")
    rows = depth_view.roi_rows(depth_view.point_rois(state, point_id))
    keep = [row for row in rows if row["id"] in selected_ids or row["id"] == roi["id"]]
    return state, rows, keep, ""


@callback(
    Output("wr-roi-image", "figure"),
    Output("wr-roi-overlays", "data"),
    Output("wr-roi-image-loading", "children"),
    Input("wr-roi-reference", "value"),
    Input("wr-rois", "data"),
    Input("wr-point", "data"),
    Input("wire-recon-detail-tabs", "active_tab"),
    State("wr-roi-overlays", "data"),
    State("wr-artifact", "data"),
)
def show_reference(kind, state, point_id, tab, drawn, artifact_data):
    """Send the reference image when it changes; ROI edits patch only the overlay traces."""

    artifact, point_id = _artifact_and_point(artifact_data, point_id)
    if tab != TAB_ROI:
        raise PreventUpdate
    if artifact is None:
        return _empty_figure("Select a complete point"), {"point": None, "count": 0}, ""
    rois = depth_view.point_rois(state, point_id)
    overlays = depth_view.roi_overlays(rois)
    drawn = drawn or {}
    current = {"artifact": artifact.path, "point": point_id, "kind": kind, "count": len(overlays)}
    if dash.ctx.triggered_id == "wire-recon-detail-tabs" and drawn == current:
        raise PreventUpdate  # revisiting the tab: the browser already shows this image
    if (
        dash.ctx.triggered_id == "wr-rois"
        and drawn.get("artifact") == artifact.path
        and drawn.get("point") == point_id
        and drawn.get("kind") == kind
        and drawn.get("count") is not None
    ):
        # The image already in the browser stays; replace only the squares.
        patch = Patch()
        for position in range(drawn["count"], 0, -1):
            del patch["data"][position]
        shape = view.point_summary(artifact, point_id).shape[1:]
        squares = plot_reference_image(_placeholder_reference(shape, point_id), overlays).data[1:]
        patch["data"].extend([square.to_plotly_json() for square in squares])
        return patch, current, ""
    try:
        reference = view.reference(artifact, point_id, kind)
    except view.ViewError as error:
        message = f"{dict((c.value, c.label) for c in REFERENCE_OPTIONS).get(kind, kind)} is unavailable: {error}"
        return _empty_figure(message), {"point": None, "count": 0}, ""
    figure = plot_reference_image(reference, overlays, limits=depth_view.auto_limits(reference.image))
    return figure, current, ""


def _placeholder_reference(shape, point_id):
    """A stand-in image of the right shape, used only to build the library's overlay traces."""

    return ReferenceImage(np.zeros(shape, dtype=np.uint8), "sum_reconstructed", "stored", point_id, "overlay")


@callback(
    Output("wr-roi-traces", "figure"),
    Output("wr-roi-traces-loading", "children"),
    Input("wr-roi-grid", "selectedRows"),
    Input("wr-roi-axis", "value"),
    Input("wr-roi-yscale", "value"),
    Input("wr-roi-intensity", "value"),
    Input("wire-recon-detail-tabs", "active_tab"),
    State("wr-rois", "data"),
    State("wr-point", "data"),
    State("wr-artifact", "data"),
)
def show_roi_traces(selected, axis, yscale, intensity, tab, state, point_id, artifact_data):
    artifact, point_id = _artifact_and_point(artifact_data, point_id)
    if tab != TAB_ROI:
        raise PreventUpdate
    if artifact is None:
        return _empty_figure("Select a complete point"), ""
    selected_ids = {row["id"] for row in selected or []}
    rois = [roi for roi in depth_view.point_rois(state, point_id) if roi["id"] in selected_ids]
    try:
        traces = {roi["id"]: view.roi_trace(artifact, point_id, roi["id"], roi["bounds"]) for roi in rois}
    except view.ViewError as error:
        return _empty_figure(str(error)), ""
    figure = plot_roi_traces(
        traces,
        colors={roi["id"]: roi["color"] for roi in rois},
        axis=axis,
        normalized=intensity == "normalized",
        log=yscale == "log",
    )
    return figure, ""
