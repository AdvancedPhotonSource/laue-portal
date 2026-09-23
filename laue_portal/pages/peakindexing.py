import math
import os
import traceback
import urllib.parse
from pathlib import Path

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, dcc, html
from dash.exceptions import PreventUpdate
from lauelab.visualization import selection_from_plotly
from sqlalchemy.orm import Session

import laue_portal.components.navbar as navbar
import laue_portal.database.session_utils as session_utils
from laue_portal.analysis.detector_image import load_detector_image
from laue_portal.components.detail_layout import detail_header, detail_header_content
from laue_portal.components.peakindex_form import peakindex_readonly_form, set_peakindex_form_props
from laue_portal.components.visualization import detector_view as detector_adapter
from laue_portal.components.visualization import orientation_map as map_adapter
from laue_portal.components.visualization import stereo_plot as pole_adapter
from laue_portal.components.visualization.ipf_legend import (
    DEFAULT_PALETTE,
    SCALAR_MAX_ID,
    SCALAR_MIN_ID,
    SCALAR_PALETTE_ID,
    SCALAR_RESET_ID,
    SCALAR_REVERSE_ID,
    orientation_color_key,
    scalar_color_controls,
    scalar_controls_visible,
    stereo_color_key,
)
from laue_portal.components.visualization.pattern_table import make_pattern_table, pattern_rows
from laue_portal.components.visualization.peak_table import make_peak_table, peak_rows
from laue_portal.components.visualization.scope_bar import (
    DEFAULT_SCOPE,
    SCOPE_MIN_PEAKS_ID,
    SCOPE_PATTERN0_ID,
    SCOPE_RESET_ID,
    SCOPE_STORE_ID,
    normalize_scope,
    scope_bar,
    to_data_scope,
)
from laue_portal.components.visualization.viz_layout import viz_control, viz_graph_with_loading, viz_sidebar_head
from laue_portal.config import DEFAULT_VARIABLES
from laue_portal.database.db_utils import get_catalog_data, remove_root_path_prefix
from laue_portal.services import indexing_results
from laue_portal.services.dataset_cache import get_dataset
from laue_portal.workflows.indexing import get_indexing

dash.register_page(__name__, path="/peakindexing")  # Simplified path


# ---------------------------------------------------------------------------
# Visualization helpers — sidebar control builders
# ---------------------------------------------------------------------------


def _rgb_symmetry_controls_visible(color_mode):
    """Show Rodrigues RGB controls only for Rodrigues coloring."""
    return {} if color_mode == "rodrigues" else {"display": "none"}


def _rgb_reference_step_visible(color_mode, reference_mode):
    """Show reference-step input only when Rodrigues uses a step reference."""
    return {} if color_mode == "rodrigues" and reference_mode == "step" else {"display": "none"}


def _rgb_reference_matrix_visible(color_mode, reference_mode):
    """Show custom G_ref matrix only for Rodrigues custom-reference mode."""
    return {} if color_mode == "rodrigues" and reference_mode == "custom" else {"display": "none"}


def _surface_custom_visible(surface):
    """Show custom surface frame inputs only for the Custom surface option."""
    return {} if surface == "custom" else {"display": "none"}


def _rgb_reference_matrix_inputs():
    """Compact 3x3 input grid for G_ref rows = [astar; bstar; cstar]."""
    rows = []
    for row_label, row_name in (("a*", "a"), ("b*", "b"), ("c*", "c")):
        rows.append(html.Div(row_label, className="pi-matrix-row-label"))
        for col in range(3):
            rows.append(
                dbc.Input(
                    id=f"orientation-rgb-reference-{row_name}{col}",
                    type="number",
                    step="any",
                    debounce=True,
                    size="sm",
                )
            )
    return html.Div(rows, className="pi-matrix-input")


def _surface_frame_inputs(prefix):
    """Compact 3x3 input grid for custom surface rows = [tilt; roll; normal]."""
    defaults = {
        "tilt": (1.0, 0.0, 0.0),
        "roll": (0.0, -1.0 / math.sqrt(2.0), -1.0 / math.sqrt(2.0)),
        "normal": (0.0, 1.0 / math.sqrt(2.0), -1.0 / math.sqrt(2.0)),
    }
    rows = []
    for row_label, row_name in (("tilt", "tilt"), ("roll", "roll"), ("normal", "normal")):
        rows.append(html.Div(row_label, className="pi-matrix-row-label"))
        for col, value in zip(("x", "y", "z"), defaults[row_name], strict=False):
            rows.append(
                dbc.Input(
                    id=f"{prefix}-surface-{row_name}-{col}",
                    type="number",
                    step="any",
                    value=value,
                    debounce=True,
                    size="sm",
                )
            )
    return html.Div(rows, className="pi-matrix-input")


def _stereo_hkl_inputs():
    """Compact integer HKL inputs with an explicit apply action."""
    fields = []
    for label, input_id, value in (
        ("h", "stereo-hkl-h", 1),
        ("k", "stereo-hkl-k", 0),
        ("l", "stereo-hkl-l", 0),
    ):
        fields.append(html.Div(label, className="pi-matrix-row-label"))
        fields.append(
            dbc.Input(
                id=input_id,
                type="number",
                step=1,
                value=value,
                debounce=True,
                size="sm",
            )
        )
    return html.Div(
        [
            html.Div(fields, className="pi-hkl-input"),
            dbc.Button(
                "Update",
                id="stereo-hkl-update-btn",
                color="primary",
                size="sm",
                disabled=True,
                className="pi-hkl-update",
            ),
        ],
        className="pi-hkl-control",
    )


def _parse_stereo_hkl(h, k, l):
    """Return a valid integer HKL triplet or raise ValueError."""
    parsed = []
    for value in (h, k, l):
        if value is None or value == "":
            raise ValueError("HKL requires h, k, and l")
        fval = float(value)
        if not math.isfinite(fval) or not fval.is_integer():
            raise ValueError("HKL values must be finite integers")
        parsed.append(int(fval))
    hkl = tuple(parsed)
    if hkl == (0, 0, 0):
        raise ValueError("HKL cannot be 0,0,0")
    return hkl


# ---------------------------------------------------------------------------
# Visualization tabs — sidebar + main content layout
# ---------------------------------------------------------------------------

_viz_tabs = dbc.Tabs(
    id="peakindexing-viz-tabs",
    active_tab="tab-parameters",
    className="lp-detail-tabs",
    children=[
        # ==================================================================
        # Tab: Parameters (unchanged — full-width accordion form)
        # ==================================================================
        dbc.Tab(
            label="Parameters",
            tab_id="tab-parameters",
            children=[
                html.Div(id="tab-parameters-content", className="pt-3 px-2", children=[peakindex_readonly_form]),
            ],
        ),
        # ==================================================================
        # Tab: Color Map — sidebar + map
        # ==================================================================
        dbc.Tab(
            # This tab used to be called "Orientation"; IDs/functions keep that name for now.
            label="Color Map",
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
                                        viz_sidebar_head("Color", "bi bi-palette"),
                                        viz_control(
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
                                        viz_sidebar_head("Color", "bi bi-palette2"),
                                        # Legend image (IPF triangle / HSV hexagon /
                                        # empty placeholder).  Children are swapped
                                        # by the dispatcher callback per color mode.
                                        html.Div(
                                            id="orientation-color-key",
                                            children=orientation_color_key("cubic_ipf", "normal"),
                                        ),
                                        # Scalar-mode controls (palette + min/max +
                                        # reset).  Always mounted so callbacks can
                                        # reference their stable IDs; visibility
                                        # toggled via the ``style`` output.
                                        html.Div(
                                            id="orientation-color-controls-wrap",
                                            style=scalar_controls_visible("cubic_ipf"),
                                            children=scalar_color_controls(),
                                        ),
                                        html.Div(
                                            id="orientation-rgb-symmetry-wrap",
                                            style={"display": "none"},
                                            children=[
                                                viz_control(
                                                    "RGB symmetry",
                                                    dbc.Select(
                                                        id="orientation-rgb-symmetry-select",
                                                        options=[
                                                            {"label": "Auto (crystal)", "value": "auto"},
                                                            {"label": "Cubic", "value": "cubic"},
                                                            {"label": "Hexagonal", "value": "hexagonal"},
                                                            {"label": "None", "value": "none"},
                                                        ],
                                                        value="auto",
                                                        className="form-select",
                                                    ),
                                                ),
                                                viz_control(
                                                    "Reference",
                                                    dbc.Select(
                                                        id="orientation-rgb-reference-select",
                                                        options=[
                                                            {"label": "Lab system", "value": "lab"},
                                                            {"label": "Step #", "value": "step"},
                                                            {"label": "Custom G_ref", "value": "custom"},
                                                        ],
                                                        value="lab",
                                                        className="form-select",
                                                    ),
                                                ),
                                                html.Div(
                                                    id="orientation-rgb-reference-step-wrap",
                                                    style={"display": "none"},
                                                    children=viz_control(
                                                        "Ref step",
                                                        dbc.Input(
                                                            id="orientation-rgb-reference-step",
                                                            type="number",
                                                            min=0,
                                                            step=1,
                                                            value=0,
                                                            debounce=True,
                                                        ),
                                                    ),
                                                ),
                                                html.Div(
                                                    id="orientation-rgb-reference-matrix-wrap",
                                                    style={"display": "none"},
                                                    children=viz_control(
                                                        "G_ref rows",
                                                        _rgb_reference_matrix_inputs(),
                                                    ),
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                                html.Div(
                                    className="pi-viz-sidebar-section",
                                    children=[
                                        viz_sidebar_head("Projection", "bi bi-grid-3x3"),
                                        viz_control(
                                            "Surface",
                                            dbc.Select(
                                                id="orientation-surface-select",
                                                options=[
                                                    {"label": "Normal", "value": "normal"},
                                                    {"label": "X", "value": "X"},
                                                    {"label": "H", "value": "H"},
                                                    {"label": "Y", "value": "Y"},
                                                    {"label": "Z", "value": "Z"},
                                                    {"label": "F", "value": "F"},
                                                    {"label": "Custom", "value": "custom"},
                                                ],
                                                value="normal",
                                                className="form-select",
                                            ),
                                        ),
                                        html.Div(
                                            id="orientation-surface-custom-wrap",
                                            style={"display": "none"},
                                            children=viz_control(
                                                "Custom frame",
                                                _surface_frame_inputs("orientation"),
                                            ),
                                        ),
                                        viz_control(
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
                                        # Custom plot axes.  H and F are wire-frame
                                        # coords rotated from (Y, Z); see
                                        # ``xml_parser.yz_to_hf``.  The "lab" axes are
                                        # beam-line voxel-in-sample coords (Igor's
                                        # XX/YY/ZZ/HH/FF): negated stage position with
                                        # depth folded into Z; see
                                        # ``xml_parser.positions_lab``.  Defaults are
                                        # X/H in 2-D and X/Y/Z in 3-D.
                                        html.Div(
                                            id="orientation-2d-axis-wrap",
                                            children=[
                                                viz_control(
                                                    "X axis",
                                                    dbc.Select(
                                                        id="orientation-x-axis-select",
                                                        options=[
                                                            {"label": "X motor", "value": "X"},
                                                            {"label": "Y motor", "value": "Y"},
                                                            {"label": "Z motor", "value": "Z"},
                                                            {"label": "H", "value": "H"},
                                                            {"label": "F", "value": "F"},
                                                            {"label": "Depth", "value": "depth"},
                                                            {"label": "X lab", "value": "Xlab"},
                                                            {"label": "Y lab", "value": "Ylab"},
                                                            {"label": "Z lab", "value": "Zlab"},
                                                            {"label": "H lab", "value": "Hlab"},
                                                            {"label": "F lab", "value": "Flab"},
                                                        ],
                                                        value="X",
                                                        className="form-select",
                                                    ),
                                                ),
                                                viz_control(
                                                    "Y axis",
                                                    dbc.Select(
                                                        id="orientation-y-axis-select",
                                                        options=[
                                                            {"label": "X motor", "value": "X"},
                                                            {"label": "Y motor", "value": "Y"},
                                                            {"label": "Z motor", "value": "Z"},
                                                            {"label": "H", "value": "H"},
                                                            {"label": "F", "value": "F"},
                                                            {"label": "Depth", "value": "depth"},
                                                            {"label": "X lab", "value": "Xlab"},
                                                            {"label": "Y lab", "value": "Ylab"},
                                                            {"label": "Z lab", "value": "Zlab"},
                                                            {"label": "H lab", "value": "Hlab"},
                                                            {"label": "F lab", "value": "Flab"},
                                                        ],
                                                        value="H",
                                                        className="form-select",
                                                    ),
                                                ),
                                            ],
                                        ),
                                        html.Div(
                                            id="orientation-3d-axis-wrap",
                                            style={"display": "none"},
                                            children=[
                                                viz_control(
                                                    "X axis",
                                                    dbc.Select(
                                                        id="orientation-3d-x-axis-select",
                                                        options=[
                                                            {"label": "X motor", "value": "X"},
                                                            {"label": "Y motor", "value": "Y"},
                                                            {"label": "Z motor", "value": "Z"},
                                                            {"label": "H", "value": "H"},
                                                            {"label": "F", "value": "F"},
                                                            {"label": "Depth", "value": "depth"},
                                                            {"label": "X lab", "value": "Xlab"},
                                                            {"label": "Y lab", "value": "Ylab"},
                                                            {"label": "Z lab", "value": "Zlab"},
                                                            {"label": "H lab", "value": "Hlab"},
                                                            {"label": "F lab", "value": "Flab"},
                                                        ],
                                                        value="X",
                                                        className="form-select",
                                                    ),
                                                ),
                                                viz_control(
                                                    "Y axis",
                                                    dbc.Select(
                                                        id="orientation-3d-y-axis-select",
                                                        options=[
                                                            {"label": "X motor", "value": "X"},
                                                            {"label": "Y motor", "value": "Y"},
                                                            {"label": "Z motor", "value": "Z"},
                                                            {"label": "H", "value": "H"},
                                                            {"label": "F", "value": "F"},
                                                            {"label": "Depth", "value": "depth"},
                                                            {"label": "X lab", "value": "Xlab"},
                                                            {"label": "Y lab", "value": "Ylab"},
                                                            {"label": "Z lab", "value": "Zlab"},
                                                            {"label": "H lab", "value": "Hlab"},
                                                            {"label": "F lab", "value": "Flab"},
                                                        ],
                                                        value="Y",
                                                        className="form-select",
                                                    ),
                                                ),
                                                viz_control(
                                                    "Z axis",
                                                    dbc.Select(
                                                        id="orientation-z-axis-select",
                                                        options=[
                                                            {"label": "X motor", "value": "X"},
                                                            {"label": "Y motor", "value": "Y"},
                                                            {"label": "Z motor", "value": "Z"},
                                                            {"label": "H", "value": "H"},
                                                            {"label": "F", "value": "F"},
                                                            {"label": "Depth", "value": "depth"},
                                                            {"label": "X lab", "value": "Xlab"},
                                                            {"label": "Y lab", "value": "Ylab"},
                                                            {"label": "Z lab", "value": "Zlab"},
                                                            {"label": "H lab", "value": "Hlab"},
                                                            {"label": "F lab", "value": "Flab"},
                                                        ],
                                                        value="Z",
                                                        className="form-select",
                                                    ),
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                                html.Div(
                                    className="pi-viz-sidebar-section",
                                    children=[
                                        viz_sidebar_head("Display", "bi bi-aspect-ratio"),
                                        viz_control(
                                            "Marker",
                                            dbc.Input(
                                                id="orientation-marker-size",
                                                type="number",
                                                min=1,
                                                max=75,
                                                step=1,
                                                value=40,
                                                debounce=True,
                                                className="form-control",
                                            ),
                                        ),
                                        viz_control(
                                            "Non-indexed",
                                            dbc.Select(
                                                id="orientation-nonindexed-style",
                                                options=[
                                                    {"label": "Gray", "value": "gray"},
                                                    {"label": "Red", "value": "red"},
                                                    {"label": "Blue", "value": "blue"},
                                                    {"label": "Green", "value": "green"},
                                                    {
                                                        "label": "Transparent (removed in 3D)",
                                                        "value": "transparent",
                                                    },
                                                ],
                                                value="gray",
                                                className="form-select",
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
                                viz_graph_with_loading(
                                    dcc.Graph(
                                        id="orientation-map-graph",
                                        config={"displayModeBar": True, "scrollZoom": True},
                                        style={"height": "100%", "minHeight": 0},
                                    ),
                                    "orientation-loading-target",
                                    cursor_readout_id="orientation-cursor-readout",
                                ),
                                html.Div(id="orientation-map-status", className="pi-viz-status small"),
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
                                        viz_sidebar_head("Pole", "bi bi-bullseye"),
                                        viz_control(
                                            "{hkl}",
                                            _stereo_hkl_inputs(),
                                        ),
                                        viz_control(
                                            "Surface",
                                            dbc.Select(
                                                id="stereo-surface-select",
                                                options=[
                                                    {"label": "Normal", "value": "normal"},
                                                    {"label": "X", "value": "X"},
                                                    {"label": "H", "value": "H"},
                                                    {"label": "Y", "value": "Y"},
                                                    {"label": "Z", "value": "Z"},
                                                    {"label": "F", "value": "F"},
                                                    {"label": "Custom", "value": "custom"},
                                                ],
                                                value="normal",
                                                className="form-select",
                                            ),
                                        ),
                                        html.Div(
                                            id="stereo-surface-custom-wrap",
                                            style={"display": "none"},
                                            children=viz_control(
                                                "Custom frame",
                                                _surface_frame_inputs("stereo"),
                                            ),
                                        ),
                                    ],
                                ),
                                html.Div(
                                    className="pi-viz-sidebar-section",
                                    children=[
                                        viz_sidebar_head("Color", "bi bi-palette"),
                                        viz_control(
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
                                                    debounce=True,
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
                                        viz_sidebar_head("Color Key", "bi bi-triangle"),
                                        html.Div(
                                            id="stereo-color-key",
                                            children=stereo_color_key("hsv_position"),
                                        ),
                                    ],
                                ),
                                html.Div(
                                    className="pi-viz-sidebar-section",
                                    children=[
                                        viz_sidebar_head("Display", "bi bi-aspect-ratio"),
                                        viz_control(
                                            "Marker",
                                            dbc.Input(
                                                id="stereo-marker-size",
                                                type="number",
                                                min=1,
                                                max=75,
                                                step=1,
                                                value=12,
                                                debounce=True,
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
                                viz_graph_with_loading(
                                    dcc.Graph(
                                        id="stereo-plot-graph",
                                        config={
                                            "displayModeBar": True,
                                            "scrollZoom": True,
                                            "modeBarButtonsToAdd": ["lasso2d", "select2d"],
                                        },
                                        style={"height": "100%", "minHeight": 0},
                                    ),
                                    "poles-loading-target",
                                    cursor_readout_id="stereo-cursor-readout",
                                ),
                                html.Div(id="stereo-plot-status", className="pi-viz-status small"),
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
        # Tab: Detector View — sidebar + Plotly back-projection figure
        # ==================================================================
        dbc.Tab(
            label="Detector View",
            tab_id="tab-detector",
            children=[
                html.Div(
                    id="tab-detector-content",
                    className="pi-viz-layout",
                    children=[
                        # ── Sidebar ──
                        html.Div(
                            className="pi-viz-sidebar",
                            children=[
                                html.Div(
                                    className="pi-viz-sidebar-section",
                                    children=[
                                        viz_sidebar_head("Step", "bi bi-list-ol"),
                                        viz_control(
                                            "Step #",
                                            html.Div(
                                                [
                                                    dbc.Input(
                                                        id="detector-step-select",
                                                        type="number",
                                                        min=0,
                                                        step=1,
                                                        value=None,
                                                        debounce=True,
                                                        className="form-control",
                                                    ),
                                                    html.Small(
                                                        "Steps: load data",
                                                        id="detector-step-range-text",
                                                        className="text-muted",
                                                    ),
                                                ],
                                                className="pi-viz-field-stack",
                                            ),
                                        ),
                                    ],
                                ),
                                html.Div(
                                    className="pi-viz-sidebar-section",
                                    children=[
                                        viz_sidebar_head("Display", "bi bi-eye"),
                                        viz_control(
                                            "",
                                            dbc.Checkbox(
                                                id="detector-show-detected",
                                                label="Show detected peaks",
                                                value=True,
                                            ),
                                        ),
                                        viz_control(
                                            "",
                                            dbc.Checkbox(
                                                id="detector-show-indexed",
                                                label="Show indexed peaks",
                                                value=True,
                                            ),
                                        ),
                                        viz_control(
                                            "",
                                            dbc.Checkbox(
                                                id="detector-show-missing",
                                                label="Show simulated missing peaks",
                                                value=False,
                                            ),
                                        ),
                                        viz_control(
                                            "",
                                            dbc.Checkbox(
                                                id="detector-show-hkl",
                                                label="Show hkl labels",
                                                value=True,
                                            ),
                                        ),
                                        viz_control(
                                            "Marker",
                                            dbc.Input(
                                                id="detector-marker-size",
                                                type="number",
                                                min=1,
                                                max=40,
                                                step=1,
                                                value=10,
                                                debounce=True,
                                                className="form-control",
                                            ),
                                        ),
                                        viz_control(
                                            "Label size",
                                            dbc.Input(
                                                id="detector-label-size",
                                                type="number",
                                                min=6,
                                                max=24,
                                                step=1,
                                                value=10,
                                                debounce=True,
                                                className="form-control",
                                            ),
                                        ),
                                    ],
                                ),
                                html.Div(
                                    className="pi-viz-sidebar-section",
                                    children=[
                                        viz_sidebar_head("Image", "bi bi-image"),
                                        viz_control(
                                            "",
                                            dbc.Checkbox(
                                                id="detector-show-image",
                                                label="Show detector image",
                                                value=True,
                                            ),
                                        ),
                                        viz_control(
                                            "Colormap",
                                            dbc.Select(
                                                id="detector-image-colormap",
                                                options=[
                                                    {"label": "Gray", "value": "gray"},
                                                    {"label": "Terrain", "value": "terrain_r"},
                                                    {"label": "Gray reversed", "value": "gray_r"},
                                                    {"label": "Viridis", "value": "viridis"},
                                                    {"label": "Plasma", "value": "plasma"},
                                                    {"label": "Inferno", "value": "inferno"},
                                                    {"label": "Magma", "value": "magma"},
                                                    {"label": "Turbo", "value": "turbo"},
                                                    {"label": "Jet", "value": "jet"},
                                                ],
                                                value="gray",
                                                className="form-select",
                                            ),
                                        ),
                                        viz_control(
                                            "Min I",
                                            dbc.Input(
                                                id="detector-image-vmin",
                                                type="number",
                                                step="any",
                                                value=None,
                                                debounce=True,
                                                placeholder="auto",
                                                className="form-control",
                                            ),
                                        ),
                                        viz_control(
                                            "Max I",
                                            dbc.Input(
                                                id="detector-image-vmax",
                                                type="number",
                                                step="any",
                                                value=None,
                                                debounce=True,
                                                placeholder="auto",
                                                className="form-control",
                                            ),
                                        ),
                                        html.Div(
                                            className="pi-viz-control pi-viz-control-slider",
                                            children=[
                                                html.Label("Opacity"),
                                                html.Div(
                                                    dcc.Slider(
                                                        id="detector-image-opacity",
                                                        min=0,
                                                        max=1,
                                                        step=0.05,
                                                        value=0.8,
                                                        marks={0: "0", 0.5: "0.5", 1: "1"},
                                                        tooltip={"placement": "bottom", "always_visible": False},
                                                    ),
                                                    className="pi-viz-slider-wide",
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                                html.Div(
                                    className="pi-viz-sidebar-section",
                                    children=[
                                        viz_sidebar_head("Patterns", "bi bi-collection"),
                                        # Per-step pattern checklist is populated
                                        # dynamically; empty list at startup.
                                        html.Div(
                                            id="detector-pattern-checklist-wrap",
                                            children=dbc.Checklist(
                                                id="detector-pattern-checklist",
                                                options=[],
                                                value=[],
                                                inline=False,
                                                className="small",
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
                                viz_graph_with_loading(
                                    dcc.Graph(
                                        id="detector-view-graph",
                                        config={"displayModeBar": True, "scrollZoom": True},
                                        style={"height": "100%", "minHeight": 0},
                                    ),
                                    "detector-loading-target",
                                ),
                                html.Div(id="detector-view-status", className="pi-viz-status small"),
                                html.Div(
                                    id="detector-step-summary",
                                    className="pi-viz-details",
                                    children=html.Small(
                                        "Pick a step from the sidebar to view its detector overlay.",
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
        # Tab: Peaks - full-width table
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
        # ==================================================================
        # Tab: Patterns - full-width table
        # ==================================================================
        dbc.Tab(
            label="Patterns",
            tab_id="tab-patterns",
            children=[
                html.Div(
                    id="tab-patterns-content",
                    className="pi-viz-table-wrap",
                    children=[
                        html.Div(id="pattern-table-container"),
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
        # Identity of the result artifact shown (path and kind); datasets stay in the server cache.
        dcc.Store(id="peakindexing-source"),
        # Store DB/config roots used to resolve detector image files.
        dcc.Store(id="peakindexing-path-context", data={}),
        # Selected pattern identities [frame_id, pattern_index] for cross-plot linking
        dcc.Store(id="selected-grain-indices", data=[]),
        # HKL inputs are drafts until the user explicitly applies them.
        dcc.Store(id="stereo-applied-hkl", data=[1, 0, 0]),
        # Store pole figure color center: {x, y, grain_index} or None
        dcc.Store(id="pole-figure-center", data=None),
        # Store auto-computed (min, max) for the current scalar color mode.
        # Written by the orientation-map figure callback whenever the data
        # or color mode changes; read by the reset/auto callback that
        # populates the Min/Max inputs.
        dcc.Store(id="orientation-color-auto-range", data=None),
        # Page header
        detail_header("peakindex-id-header"),
        # Result artifacts found for this run (results file, historical XML, or nothing).
        dcc.Store(id="peakindexing-artifacts", data=None),
        html.Div(
            [
                html.Span(id="peakindexing-artifact-status", className="lp-artifact-status text-muted small"),
                dbc.Button(
                    "Convert XML to HDF5",
                    id="peakindexing-convert-btn",
                    size="sm",
                    color="primary",
                    outline=True,
                    style={"display": "none"},
                ),
                dbc.Toast(
                    id="peakindexing-convert-toast",
                    header="Result conversion",
                    is_open=False,
                    dismissable=True,
                    duration=10000,
                    icon="info",
                    style={"position": "fixed", "top": 66, "right": 10, "width": 420, "zIndex": 1050},
                ),
            ],
            id="peakindexing-artifact-bar",
            className="lp-artifact-bar d-none",
        ),
        # Global data-scope filters -- apply across every tab, so they sit
        # above the tab strip rather than in any one tab's sidebar.
        scope_bar(DEFAULT_SCOPE),
        # Visualization tabs
        _viz_tabs,
    ],
    className="pi-page",
)


# ---------------------------------------------------------------------------
# Callback: load page data from DB and resolve the result artifact
#
# Callbacks receive only the artifact identity (``peakindexing-source``); the
# normalized dataset is loaded once per artifact into the server-side cache.
# ---------------------------------------------------------------------------


def _dataset(source):
    """The cached dataset for the page's source store, or raise PreventUpdate."""

    if not source or not source.get("path"):
        raise PreventUpdate
    return get_dataset(source["path"], geometry=source.get("geometry"))


def _source_for(resolution, parameters):
    """Source store payload: the validated results file first, else the historical XML."""

    if resolution.status == indexing_results.STATUS_RESULTS:
        return {"path": resolution.results_path, "kind": "results"}
    if resolution.status == indexing_results.STATUS_XML_ONLY:
        geometry = parameters.geometry_file if parameters is not None else None
        return {
            "path": resolution.xml_path,
            "kind": "xml",
            "geometry": geometry if geometry and os.path.isfile(geometry) else None,
        }
    return None


@callback(
    Output("peakindex-id-header", "children"),
    Output("peakindexing-source", "data"),
    Output("peakindexing-path-context", "data"),
    Output("peakindexing-artifacts", "data"),
    Input("url-peakindexing-page", "href"),
    prevent_initial_call=True,
)
def load_peakindexing_data(href):
    if not href:
        raise PreventUpdate

    parsed_url = urllib.parse.urlparse(href)
    query_params = urllib.parse.parse_qs(parsed_url.query)

    indexing_id_str = query_params.get("indexing_id", [None])[0]

    root_path = DEFAULT_VARIABLES.get("root_path", "")

    source = None
    artifacts = None
    path_context = {"root_path": root_path}

    if indexing_id_str:
        try:
            indexing_id = int(indexing_id_str)
            indexing = get_indexing(indexing_id)
            if indexing and indexing.method == "lauego" and indexing.lauego_parameters:
                with Session(session_utils.get_engine()) as session:
                    # Add root_path from DEFAULT_VARIABLES
                    indexing.root_path = root_path
                    parameters = indexing.lauego_parameters

                    # Resolve artifacts before display fields are rewritten for the form.
                    resolution = indexing_results.resolve_indexing_artifacts(indexing)
                    artifacts = resolution.as_dict()
                    source = _source_for(resolution, parameters)

                    # Convert full paths back to relative paths for display
                    if parameters.geometry_file:
                        parameters.geometry_file = remove_root_path_prefix(parameters.geometry_file, root_path)
                    if parameters.crystal_file:
                        parameters.crystal_file = remove_root_path_prefix(parameters.crystal_file, root_path)

                    output_folder_full = indexing.output_path
                    data_folder_full = indexing.input_path
                    if output_folder_full:
                        path_context["output_folder"] = str(output_folder_full)
                    if data_folder_full:
                        path_context["data_folder"] = str(data_folder_full)

                    if indexing.output_path:
                        indexing.output_path = remove_root_path_prefix(indexing.output_path, root_path)
                    indexing.data_path = remove_root_path_prefix(indexing.input_path, root_path)
                    if not indexing.input_path:
                        catalog_data = get_catalog_data(session, indexing.scan_number, root_path)
                        indexing.data_path = catalog_data.get("data_path", "")

                    # Populate the form with the data
                    set_peakindex_form_props(indexing, read_only=True)

                    # Get related links for header
                    related_links = []

                    # Add job link if it exists
                    if indexing.job_id:
                        related_links.append((f"Job ID: {indexing.job_id}", f"/job?job_id={indexing.job_id}"))

                    if indexing.reconstruction:
                        detail_path = (
                            "/wire_reconstruction" if indexing.reconstruction.method == "wire" else "/reconstruction"
                        )
                        related_links.append(
                            (
                                f"Reconstruction R{indexing.reconstruction_id}",
                                f"{detail_path}?reconstruction_id={indexing.reconstruction_id}",
                            )
                        )

                    # Add scan link
                    if indexing.scan_number:
                        related_links.append(
                            (
                                f"Scan ID: {indexing.scan_number}",
                                f"/scan?scan_id={indexing.scan_number}",
                            )
                        )

                    header_content = detail_header_content(f"Indexing I{indexing_id}", related_links)
                    return header_content, source, path_context, artifacts
        except Exception as e:
            print(f"Error loading peak indexing data: {e}")
            traceback.print_exc()
            return (
                detail_header_content(f"Error loading indexing I{indexing_id_str}"),
                None,
                path_context,
                None,
            )

    return detail_header_content("No indexing ID provided"), None, path_context, None


def artifact_status_text(artifacts: dict | None) -> tuple[str, bool]:
    """Human summary of the resolved artifacts and whether conversion is offered."""

    if not artifacts:
        return "", False
    status = artifacts.get("status")
    if status == indexing_results.STATUS_RESULTS:
        return "", False
    if status == indexing_results.STATUS_XML_ONLY:
        return "XML only:", True
    if status == indexing_results.STATUS_AMBIGUOUS:
        names = ", ".join(Path(path).name for path in artifacts.get("xml_candidates", []))
        return f"Several XML files and no recorded name; choose one manually: {names}", False
    return "No results file or XML document found for this run.", False


@callback(
    Output("peakindexing-artifact-status", "children"),
    Output("peakindexing-convert-btn", "style"),
    Output("peakindexing-artifact-bar", "className"),
    Input("peakindexing-artifacts", "data"),
)
def render_artifact_status(artifacts):
    text, convertible = artifact_status_text(artifacts)
    bar_class = "lp-artifact-bar d-flex align-items-center gap-2 px-3 py-1" if text else "lp-artifact-bar d-none"
    return text, {} if convertible else {"display": "none"}, bar_class


@callback(
    Output("peakindexing-convert-toast", "children"),
    Output("peakindexing-convert-toast", "icon"),
    Output("peakindexing-convert-toast", "is_open"),
    Output("url-peakindexing-page", "href", allow_duplicate=True),
    Input("peakindexing-convert-btn", "n_clicks"),
    State("peakindexing-artifacts", "data"),
    State("url-peakindexing-page", "href"),
    running=[
        (Output("peakindexing-convert-btn", "disabled"), True, False),
        (Output("peakindexing-convert-btn", "children"), "Converting...", "Convert XML to HDF5"),
    ],
    prevent_initial_call=True,
)
def convert_results(n_clicks, artifacts, href):
    """Convert this run's XML through the shared service and reload the page on success."""

    if not n_clicks or not artifacts or artifacts.get("status") != indexing_results.STATUS_XML_ONLY:
        raise PreventUpdate
    report = indexing_results.convert_indexing_results([int(artifacts["indexing_id"])])
    outcome = report.outcomes[0]
    succeeded = outcome.outcome in (
        indexing_results.OUTCOME_CONVERTED,
        indexing_results.OUTCOME_LINKED,
        indexing_results.OUTCOME_ALREADY_CONVERTED,
    )
    message = f"I{outcome.indexing_id}: {outcome.outcome.replace('_', ' ')}: {outcome.message}"
    if outcome.destination and succeeded:
        message += f" -> {outcome.destination}"
    return message, ("success" if succeeded else "danger"), True, (href if succeeded else dash.no_update)


# ---------------------------------------------------------------------------
# Callbacks: apply pole-figure HKL only when requested
# ---------------------------------------------------------------------------


dash.clientside_callback(
    """
    function(h, k, l, applied) {
        const values = [h, k, l];
        const draft = values.map(Number);
        const valid = values.every(value => value !== null && value !== "")
            && draft.every(Number.isFinite)
            && draft.every(Number.isInteger)
            && draft.some(value => value !== 0);
        const current = Array.isArray(applied) ? applied.map(Number) : [1, 0, 0];
        const changed = draft.some((value, index) => value !== current[index]);
        return !(valid && changed);
    }
    """,
    Output("stereo-hkl-update-btn", "disabled"),
    Input("stereo-hkl-h", "value"),
    Input("stereo-hkl-k", "value"),
    Input("stereo-hkl-l", "value"),
    Input("stereo-applied-hkl", "data"),
)


@callback(
    Output("stereo-applied-hkl", "data"),
    Input("stereo-hkl-update-btn", "n_clicks"),
    State("stereo-hkl-h", "value"),
    State("stereo-hkl-k", "value"),
    State("stereo-hkl-l", "value"),
    prevent_initial_call=True,
)
def apply_stereo_hkl(n_clicks, h, k, l):
    if not n_clicks:
        raise PreventUpdate
    try:
        return list(_parse_stereo_hkl(h, k, l))
    except ValueError:
        raise PreventUpdate from None


def _stale(message: str):
    """Status line shown when a plot could not be updated and the previous one stays."""

    return html.Span(
        [html.I(className="bi bi-exclamation-triangle me-1"), f"Not updated: {message} Showing the last valid plot."],
        className="text-danger",
    )


def _pattern_reference(pole_center):
    """``(frame_id, pattern_index)`` chosen in the pole figure, or None."""

    if not pole_center or pole_center.get("pattern_index") is None:
        return None
    return (pole_center.get("frame_id"), int(pole_center["pattern_index"]))


# ---------------------------------------------------------------------------
# Callback: color map
# ---------------------------------------------------------------------------


@callback(
    Output("orientation-map-graph", "figure"),
    Output("orientation-marker-size", "value"),
    Output("orientation-loading-target", "children"),
    Output("orientation-map-status", "children"),
    Input("peakindexing-source", "data"),
    Input(SCOPE_STORE_ID, "data"),
    Input("orientation-color-select", "value"),
    Input("orientation-rgb-symmetry-select", "value"),
    Input("orientation-rgb-reference-select", "value"),
    Input("orientation-rgb-reference-step", "value"),
    Input("orientation-rgb-reference-a0", "value"),
    Input("orientation-rgb-reference-a1", "value"),
    Input("orientation-rgb-reference-a2", "value"),
    Input("orientation-rgb-reference-b0", "value"),
    Input("orientation-rgb-reference-b1", "value"),
    Input("orientation-rgb-reference-b2", "value"),
    Input("orientation-rgb-reference-c0", "value"),
    Input("orientation-rgb-reference-c1", "value"),
    Input("orientation-rgb-reference-c2", "value"),
    Input("orientation-surface-select", "value"),
    Input("orientation-surface-tilt-x", "value"),
    Input("orientation-surface-tilt-y", "value"),
    Input("orientation-surface-tilt-z", "value"),
    Input("orientation-surface-roll-x", "value"),
    Input("orientation-surface-roll-y", "value"),
    Input("orientation-surface-roll-z", "value"),
    Input("orientation-surface-normal-x", "value"),
    Input("orientation-surface-normal-y", "value"),
    Input("orientation-surface-normal-z", "value"),
    Input("orientation-marker-size", "value"),
    Input("orientation-nonindexed-style", "value"),
    Input("orientation-view-toggle", "value"),
    Input("selected-grain-indices", "data"),
    Input("pole-figure-center", "data"),
    Input("stereo-applied-hkl", "data"),
    Input("stereo-color-rad", "value"),
    Input("stereo-surface-select", "value"),
    Input("stereo-surface-tilt-x", "value"),
    Input("stereo-surface-tilt-y", "value"),
    Input("stereo-surface-tilt-z", "value"),
    Input("stereo-surface-roll-x", "value"),
    Input("stereo-surface-roll-y", "value"),
    Input("stereo-surface-roll-z", "value"),
    Input("stereo-surface-normal-x", "value"),
    Input("stereo-surface-normal-y", "value"),
    Input("stereo-surface-normal-z", "value"),
    Input(SCALAR_PALETTE_ID, "value"),
    Input(SCALAR_REVERSE_ID, "value"),
    Input(SCALAR_MIN_ID, "value"),
    Input(SCALAR_MAX_ID, "value"),
    Input("orientation-x-axis-select", "value"),
    Input("orientation-y-axis-select", "value"),
    Input("orientation-3d-x-axis-select", "value"),
    Input("orientation-3d-y-axis-select", "value"),
    Input("orientation-z-axis-select", "value"),
    prevent_initial_call=True,
)
def update_orientation_map(
    source,
    scope,
    color_by,
    rgb_symmetry,
    rgb_reference_mode,
    rgb_reference_step,
    ref_a0,
    ref_a1,
    ref_a2,
    ref_b0,
    ref_b1,
    ref_b2,
    ref_c0,
    ref_c1,
    ref_c2,
    surface,
    surface_tilt_x,
    surface_tilt_y,
    surface_tilt_z,
    surface_roll_x,
    surface_roll_y,
    surface_roll_z,
    surface_normal_x,
    surface_normal_y,
    surface_normal_z,
    input_size,
    nonindexed_style,
    view_mode,
    selected_patterns,
    pole_center,
    pole_hkl,
    pole_color_rad_deg,
    pole_surface,
    pole_surface_tilt_x,
    pole_surface_tilt_y,
    pole_surface_tilt_z,
    pole_surface_roll_x,
    pole_surface_roll_y,
    pole_surface_roll_z,
    pole_surface_normal_x,
    pole_surface_normal_y,
    pole_surface_normal_z,
    palette,
    reverse_palette,
    user_vmin,
    user_vmax,
    x_axis,
    y_axis,
    x_axis_3d,
    y_axis_3d,
    z_axis,
):
    if not source:
        raise PreventUpdate

    triggered = dash.ctx.triggered_id
    effective_color = color_by or "cubic_ipf"
    _POLE_ONLY_TRIGGERS = {
        "stereo-applied-hkl",
        "stereo-color-rad",
        "stereo-surface-select",
        "stereo-surface-tilt-x",
        "stereo-surface-tilt-y",
        "stereo-surface-tilt-z",
        "stereo-surface-roll-x",
        "stereo-surface-roll-y",
        "stereo-surface-roll-z",
        "stereo-surface-normal-x",
        "stereo-surface-normal-y",
        "stereo-surface-normal-z",
    }
    if triggered in _POLE_ONLY_TRIGGERS and effective_color != "pole_hsv":
        raise PreventUpdate
    if triggered in {
        SCALAR_PALETTE_ID,
        SCALAR_REVERSE_ID,
        SCALAR_MIN_ID,
        SCALAR_MAX_ID,
    } and not map_adapter.is_scalar_mode(effective_color):
        raise PreventUpdate

    marker_size = max(1, int(input_size or 40))
    is_3d_view = str(view_mode).lower() == "3d"
    if is_3d_view:
        axes = (x_axis_3d or "X", y_axis_3d or "Y", z_axis or "Z")
    else:
        axes = (x_axis or "X", y_axis or "H")

    try:
        dataset = _dataset(source)
        data_scope = to_data_scope(scope)
        if effective_color == "pole_hsv":
            surface_value = map_adapter.resolve_surface(
                pole_surface,
                [
                    pole_surface_tilt_x,
                    pole_surface_tilt_y,
                    pole_surface_tilt_z,
                    pole_surface_roll_x,
                    pole_surface_roll_y,
                    pole_surface_roll_z,
                    pole_surface_normal_x,
                    pole_surface_normal_y,
                    pole_surface_normal_z,
                ],
            )
            rendered_pole_hkl = _parse_stereo_hkl(*(pole_hkl or (1, 0, 0)))
        else:
            surface_value = map_adapter.resolve_surface(
                surface,
                [
                    surface_tilt_x,
                    surface_tilt_y,
                    surface_tilt_z,
                    surface_roll_x,
                    surface_roll_y,
                    surface_roll_z,
                    surface_normal_x,
                    surface_normal_y,
                    surface_normal_z,
                ],
            )
            rendered_pole_hkl = (1, 0, 0)
        pole_center_xy = (0.0, 0.0)
        if pole_center and pole_center.get("x") is not None:
            pole_center_xy = (float(pole_center["x"]), float(pole_center["y"]))
        reference_matrix = None
        if rgb_reference_mode == "custom":
            reference_matrix = map_adapter.parse_reference_matrix(
                [ref_a0, ref_a1, ref_a2, ref_b0, ref_b1, ref_b2, ref_c0, ref_c1, ref_c2]
            )

        fig, map_data = map_adapter.build_map(
            dataset,
            scope=data_scope,
            axes=axes,
            color=effective_color,
            surface=surface_value,
            marker_size=marker_size,
            nonindexed_style=nonindexed_style or "gray",
            palette=palette or DEFAULT_PALETTE,
            reverse=bool(reverse_palette),
            cmin=user_vmin,
            cmax=user_vmax,
            symmetry=rgb_symmetry or "auto",
            reference_mode=rgb_reference_mode or "lab",
            reference_step=rgb_reference_step,
            reference_matrix=reference_matrix,
            pole_hkl=rendered_pole_hkl,
            pole_center=pole_center_xy,
            pole_radius_deg=float(pole_color_rad_deg or 22.5),
            misorientation_reference=_pattern_reference(pole_center),
        )
        map_adapter.highlight_selection(fig, map_data, selected_patterns, marker_size=marker_size)
        return fig, marker_size, "", ""
    except PreventUpdate:
        raise
    except (ValueError, KeyError) as error:
        return dash.no_update, marker_size, "", _stale(str(error).strip("'\""))
    except Exception as error:
        print(f"Error creating orientation map: {error}")
        traceback.print_exc()
        return dash.no_update, marker_size, "", _stale(f"{type(error).__name__}: {error}")


@callback(
    Output("orientation-2d-axis-wrap", "style"),
    Output("orientation-3d-axis-wrap", "style"),
    Input("orientation-view-toggle", "value"),
)
def toggle_axis_visibility(view_mode):
    if str(view_mode).lower() == "3d":
        return {"display": "none"}, {"display": "block"}
    return {"display": "block"}, {"display": "none"}


@callback(
    Output("orientation-point-details", "children"),
    Input("orientation-map-graph", "clickData"),
    State("peakindexing-source", "data"),
    prevent_initial_call=True,
)
def show_point_details(click_data, source):
    if not click_data or not source:
        raise PreventUpdate
    try:
        selection = selection_from_plotly(click_data)
        if not selection.frame_ids:
            raise PreventUpdate
        dataset = _dataset(source)
        frame_id = selection.frame_ids[0]
        pattern_index = selection.pattern_ids[0][1] if selection.pattern_ids else None
        details = map_adapter.point_details(dataset, frame_id, pattern_index)
    except PreventUpdate:
        raise
    except Exception as error:
        print(f"Error showing point details: {error}")
        traceback.print_exc()
        raise PreventUpdate from None

    x_pos, y_pos, z_pos = details["sample_position"]
    depth = "" if details["depth"] is None else f"  Depth: {details['depth']:.2f} um"
    if details["pattern_index"] is None:
        pattern_line = f"Patterns: {details['n_patterns']}  |  Detected peaks: {details['n_peaks']}  |  no indexed pattern at this point"
    else:
        pattern_line = (
            f"Pattern {details['pattern_index']} of {details['n_patterns']}  |  "
            f"Indexed: {details['n_indexed']}/{details['n_peaks']}  |  "
            f"Goodness: {details['goodness']:.1f}  |  "
            f"RMS error: {details['rms_error_deg']:.5f} deg"
        )
    return dbc.Card(
        dbc.CardBody(
            [
                html.H6("Clicked Point Details", className="card-title"),
                html.P(
                    [
                        html.Strong(f"Step #{details['step']}"),
                        f"  (frame {details['frame_id']})  Motor position: ({x_pos:.1f}, {y_pos:.1f}, {z_pos:.1f}){depth}",
                    ]
                ),
                html.P(pattern_line),
            ]
        ),
        className="mt-2",
    )


# ---------------------------------------------------------------------------
# Callback: pole figure
# ---------------------------------------------------------------------------


@callback(
    Output("stereo-plot-graph", "figure"),
    Output("stereo-marker-size", "value"),
    Output("stereo-color-rad-col", "style"),
    Output("poles-loading-target", "children"),
    Output("stereo-plot-status", "children"),
    Input("peakindexing-source", "data"),
    Input(SCOPE_STORE_ID, "data"),
    Input("stereo-applied-hkl", "data"),
    Input("stereo-marker-size", "value"),
    Input("stereo-color-select", "value"),
    Input("stereo-color-rad", "value"),
    Input("stereo-surface-select", "value"),
    Input("stereo-surface-tilt-x", "value"),
    Input("stereo-surface-tilt-y", "value"),
    Input("stereo-surface-tilt-z", "value"),
    Input("stereo-surface-roll-x", "value"),
    Input("stereo-surface-roll-y", "value"),
    Input("stereo-surface-roll-z", "value"),
    Input("stereo-surface-normal-x", "value"),
    Input("stereo-surface-normal-y", "value"),
    Input("stereo-surface-normal-z", "value"),
    Input("pole-figure-center", "data"),
    Input("selected-grain-indices", "data"),
    prevent_initial_call=True,
)
def update_pole_figure(
    source,
    scope,
    applied_hkl,
    input_size,
    color_scheme,
    color_rad_deg,
    surface,
    surface_tilt_x,
    surface_tilt_y,
    surface_tilt_z,
    surface_roll_x,
    surface_roll_y,
    surface_roll_z,
    surface_normal_x,
    surface_normal_y,
    surface_normal_z,
    pole_center,
    selected_patterns,
):
    if not source:
        raise PreventUpdate

    rad_col_style = {"display": "flex", "alignItems": "center"}
    if color_scheme != "hsv_position":
        rad_col_style["display"] = "none"
    marker_size = max(1, int(input_size or 12))

    try:
        dataset = _dataset(source)
        hkl = _parse_stereo_hkl(*(applied_hkl or (1, 0, 0)))
        surface_value = map_adapter.resolve_surface(
            surface,
            [
                surface_tilt_x,
                surface_tilt_y,
                surface_tilt_z,
                surface_roll_x,
                surface_roll_y,
                surface_roll_z,
                surface_normal_x,
                surface_normal_y,
                surface_normal_z,
            ],
        )
        center = (0.0, 0.0)
        if pole_center and color_scheme == "hsv_position" and pole_center.get("x") is not None:
            center = (float(pole_center["x"]), float(pole_center["y"]))
        fig, _pole_data = pole_adapter.build_pole_figure(
            dataset,
            scope=to_data_scope(scope),
            hkl=hkl,
            surface=surface_value,
            color=color_scheme or "hsv_position",
            radius_deg=float(color_rad_deg or 22.5),
            center=center,
            marker_size=marker_size,
        )
        pole_adapter.highlight_pole_selection(fig, selected_patterns, marker_size=marker_size)
        return fig, marker_size, rad_col_style, "", ""
    except PreventUpdate:
        raise
    except (ValueError, KeyError) as error:
        return dash.no_update, marker_size, rad_col_style, "", _stale(str(error).strip("'\""))
    except Exception as error:
        print(f"Error creating pole figure: {error}")
        traceback.print_exc()
        return dash.no_update, marker_size, rad_col_style, "", _stale(f"{type(error).__name__}: {error}")


# ---------------------------------------------------------------------------
# Callbacks: tables
#
# Row data is still delivered whole to AG Grid (client-side pagination); the
# payload for the largest historical run is recorded in the P5 report.
# ---------------------------------------------------------------------------


@callback(
    Output("peak-table-container", "children"),
    Input("peakindexing-source", "data"),
    Input(SCOPE_STORE_ID, "data"),
    prevent_initial_call=True,
)
def update_peak_table(source, scope):
    if not source:
        raise PreventUpdate
    try:
        dataset = _dataset(source)
        return make_peak_table(peak_rows(dataset, to_data_scope(scope)))
    except Exception as e:
        print(f"Error creating peak table: {e}")
        traceback.print_exc()
        return html.Div(dbc.Alert(f"Could not load peak table: {e}", color="warning"))


@callback(
    Output("pattern-table-container", "children"),
    Input("peakindexing-source", "data"),
    Input(SCOPE_STORE_ID, "data"),
    prevent_initial_call=True,
)
def update_pattern_table(source, scope):
    if not source:
        raise PreventUpdate
    try:
        dataset = _dataset(source)
        return make_pattern_table(pattern_rows(dataset, to_data_scope(scope)))
    except Exception as e:
        print(f"Error creating pattern table: {e}")
        traceback.print_exc()
        return html.Div(dbc.Alert(f"Could not load pattern table: {e}", color="warning"))


@callback(
    Output("indexed-peaks-grid", "columnDefs"),
    Input("peak-columns-default", "value"),
    Input("peak-columns-geometry", "value"),
    Input("peak-columns-fit", "value"),
    Input("peak-columns-indexing", "value"),
    State("indexed-peaks-grid", "columnDefs"),
    prevent_initial_call=True,
)
def update_peak_columns(default_cols, geometry_cols, fit_cols, indexing_cols, column_defs):
    if not column_defs:
        raise PreventUpdate
    visible = set(default_cols or [])
    for group in (geometry_cols, fit_cols, indexing_cols):
        visible.update(group or [])
    for col_def in column_defs:
        field = col_def.get("field")
        if field:
            col_def["hide"] = field not in visible
    return column_defs


@callback(
    Output("indexed-patterns-grid", "columnDefs"),
    Input("pattern-columns-default", "value"),
    Input("pattern-columns-position", "value"),
    Input("pattern-columns-run", "value"),
    State("indexed-patterns-grid", "columnDefs"),
    prevent_initial_call=True,
)
def update_pattern_columns(default_cols, position_cols, run_cols, column_defs):
    if not column_defs:
        raise PreventUpdate
    visible = set(default_cols or [])
    for group in (position_cols, run_cols):
        visible.update(group or [])
    for col_def in column_defs:
        field = col_def.get("field")
        if field:
            col_def["hide"] = field not in visible
    return column_defs


# ---------------------------------------------------------------------------
# Callback: click on pole figure to set/clear the color center and reference pattern
# ---------------------------------------------------------------------------


@callback(
    Output("pole-figure-center", "data"),
    Output("pole-figure-center-info", "children"),
    Output("pole-figure-reset-col", "style"),
    Output("orientation-color-select", "value"),
    Input("stereo-plot-graph", "clickData"),
    Input("pole-figure-reset-btn", "n_clicks"),
    State("pole-figure-center", "data"),
    State("orientation-color-select", "value"),
    prevent_initial_call=True,
)
def handle_pole_figure_click(click_data, reset_clicks, current_center, current_color_by):
    """Set or clear the HSV color center (and misorientation reference) from a clicked pole."""

    triggered = dash.ctx.triggered_id
    _default_hint = html.Small("Click a point to set color center.", className="text-muted")
    _hide_btn = {"display": "none"}

    def restore():
        restore_color = "cubic_ipf"
        if current_center is not None and current_center.get("prev_color_by"):
            restore_color = current_center["prev_color_by"]
        return None, _default_hint, _hide_btn, restore_color

    if triggered == "pole-figure-reset-btn":
        return restore()

    if not click_data or not click_data.get("points"):
        raise PreventUpdate
    point = click_data["points"][0]
    x, y = point.get("x"), point.get("y")
    selection = selection_from_plotly(click_data)
    if x is None or y is None or not selection.pattern_ids:
        raise PreventUpdate
    frame_id, pattern_index = selection.pattern_ids[0]

    if (
        current_center is not None
        and current_center.get("frame_id") == frame_id
        and current_center.get("pattern_index") == pattern_index
    ):
        return restore()  # clicking the current reference clears it

    prev_color = current_color_by if current_color_by not in ("misorientation", "pole_hsv") else "cubic_ipf"
    new_center = {
        "x": float(x),
        "y": float(y),
        "frame_id": frame_id,
        "pattern_index": int(pattern_index),
        "prev_color_by": prev_color,
    }
    info = html.Small(
        [html.Strong("Color center: "), f"frame {frame_id} pattern {pattern_index} at ({x:.3f}, {y:.3f})"]
    )
    return new_center, info, {"display": "flex", "alignItems": "center"}, "pole_hsv"


# ---------------------------------------------------------------------------
# Callback: lasso/box selection on the pole figure (ROI picking)
# ---------------------------------------------------------------------------


@callback(
    Output("selected-grain-indices", "data"),
    Output("stereo-selection-info", "children"),
    Input("stereo-plot-graph", "selectedData"),
    State("peakindexing-source", "data"),
    prevent_initial_call=True,
)
def handle_pole_selection(selected_data, source):
    """Turn a lasso/box selection into stable pattern identities and summarize misorientation."""

    if not selected_data or not selected_data.get("points"):
        return [], html.Small(
            "Use lasso or box select on the pole figure to pick regions of interest.",
            className="text-muted",
        )
    selection = selection_from_plotly(selected_data)
    selected = [[frame_id, pattern_index] for frame_id, pattern_index in selection.pattern_ids]
    if not selected:
        return [], html.Small("No patterns in selection.", className="text-muted")

    misorientation_info = []
    if source and len(selected) >= 2:
        try:
            summary = pole_adapter.misorientation_summary(_dataset(source), selected)
        except Exception as error:
            print(f"Error computing misorientation: {error}")
            traceback.print_exc()
            summary = None
        if summary and summary.get("skipped"):
            misorientation_info = [
                html.Br(),
                html.Small(
                    f"Misorientation stats skipped (>{summary['limit']} patterns selected).",
                    className="text-muted",
                ),
            ]
        elif summary:
            misorientation_info = [
                html.Br(),
                html.Strong("Misorientation: "),
                f"mean {summary['mean']:.2f}°, range [{summary['min']:.2f}°, {summary['max']:.2f}°] "
                f"over {summary['n_pairs']} pairs ({summary['symmetry']} symmetry)",
            ]

    n_poles = len(selected_data["points"])
    summary_card = dbc.Card(
        dbc.CardBody(
            [
                html.H6("ROI Selection", className="card-title"),
                html.P(
                    [
                        html.Strong("Selected: "),
                        f"{n_poles} poles from {len(selected)} pattern{'s' if len(selected) != 1 else ''}",
                        *misorientation_info,
                    ]
                ),
                html.Small(
                    "Selected patterns are highlighted on the Color Map and Pole Figure tabs.", className="text-muted"
                ),
            ]
        ),
        className="mt-2",
    )
    return selected, summary_card


# ---------------------------------------------------------------------------
# Callbacks: scalar color-range auto-fill (acyclic: Store -> Min/Max -> figure)
# ---------------------------------------------------------------------------


@callback(
    Output("orientation-color-auto-range", "data"),
    Input("orientation-color-select", "value"),
    Input("peakindexing-source", "data"),
    Input(SCOPE_STORE_ID, "data"),
    prevent_initial_call=True,
)
def compute_orientation_auto_range(color_mode, source, scope):
    """Publish the data range of the current scalar color mode (None for orientation colors)."""

    if not source:
        raise PreventUpdate
    effective_color = color_mode or "cubic_ipf"
    if not map_adapter.is_scalar_mode(effective_color):
        return None
    try:
        dataset = _dataset(source)
        auto_vmin, auto_vmax = map_adapter.scalar_range_for(dataset, to_data_scope(scope), effective_color)
        return {"mode": effective_color, "min": auto_vmin, "max": auto_vmax}
    except Exception as e:
        print(f"Error computing scalar auto-range: {e}")
        traceback.print_exc()
        return None


@callback(
    Output(SCALAR_MIN_ID, "value"),
    Output(SCALAR_MAX_ID, "value"),
    Input("orientation-color-auto-range", "data"),
    Input(SCALAR_RESET_ID, "n_clicks"),
    State("orientation-color-select", "value"),
    prevent_initial_call=True,
)
def reset_scalar_color_range(auto_range, _reset_clicks, color_mode):
    """Populate the Min/Max inputs from the auto-computed range or on Reset."""

    triggered = dash.ctx.triggered_id
    if triggered == SCALAR_RESET_ID:
        if auto_range and auto_range.get("mode") == (color_mode or ""):
            return auto_range.get("min"), auto_range.get("max")
        return None, None
    if not auto_range:
        return None, None
    if auto_range.get("mode") != (color_mode or ""):
        raise PreventUpdate
    return auto_range.get("min"), auto_range.get("max")


# ---------------------------------------------------------------------------
# Callbacks: color keys
# ---------------------------------------------------------------------------


@callback(
    Output("orientation-color-key", "children"),
    Output("orientation-color-controls-wrap", "style"),
    Output("orientation-rgb-symmetry-wrap", "style"),
    Output("orientation-rgb-reference-step-wrap", "style"),
    Output("orientation-rgb-reference-matrix-wrap", "style"),
    Output("orientation-surface-custom-wrap", "style"),
    Input("orientation-color-select", "value"),
    Input("orientation-surface-select", "value"),
    Input("orientation-rgb-reference-select", "value"),
)
def update_orientation_color_key(color_mode, surface, reference_mode):
    """Refresh the orientation legend and mode-specific color controls."""
    return (
        orientation_color_key(color_mode, surface),
        scalar_controls_visible(color_mode),
        _rgb_symmetry_controls_visible(color_mode),
        _rgb_reference_step_visible(color_mode, reference_mode),
        _rgb_reference_matrix_visible(color_mode, reference_mode),
        _surface_custom_visible(surface),
    )


@callback(
    Output("stereo-color-key", "children"),
    Output("stereo-surface-custom-wrap", "style"),
    Input("stereo-color-select", "value"),
    Input("stereo-surface-select", "value"),
)
def update_stereo_color_key(color_mode, surface):
    """Refresh the pole-figure reference legend and surface controls."""
    return stereo_color_key(color_mode), _surface_custom_visible(surface)


# ---------------------------------------------------------------------------
# Detector view tab
#
# "Step #" is the frame position: the manifest index of a native run and the
# XML step order of a converted historical run. Frame identities travel in
# customdata and the summary card.
# ---------------------------------------------------------------------------


def _detector_frame(dataset, scope, step_value):
    """The frame identity for a step input, provided the scope keeps that frame."""

    try:
        frame_id = map_adapter.frame_id_at(dataset, step_value)
    except (TypeError, ValueError):
        raise PreventUpdate from None
    position = map_adapter.frame_position(dataset, frame_id)
    if position not in set(detector_adapter.eligible_frames(dataset, scope).tolist()):
        raise PreventUpdate
    return frame_id


@callback(
    Output("detector-step-select", "min"),
    Output("detector-step-select", "max"),
    Output("detector-step-select", "value"),
    Output("detector-step-range-text", "children"),
    Input("peakindexing-source", "data"),
    Input(SCOPE_STORE_ID, "data"),
    prevent_initial_call=True,
)
def populate_detector_step_input(source, scope):
    """Bounds for the step input; the first eligible frame with an indexed pattern is preselected."""

    if not source:
        raise PreventUpdate
    try:
        dataset = _dataset(source)
        eligible = detector_adapter.eligible_frames(dataset, to_data_scope(scope))
    except Exception as e:
        print(f"Error preparing detector steps: {e}")
        raise PreventUpdate from None
    if not len(eligible):
        return 0, 0, None, "No steps match the data scope"
    with_patterns = [position for position in eligible if (dataset.pattern_frame_indices == position).any()]
    default_value = int(with_patterns[0] if with_patterns else eligible[0])
    step_min, step_max = int(eligible[0]), int(eligible[-1])
    return step_min, step_max, default_value, f"Eligible steps: {len(eligible)} ({step_min} to {step_max})"


@callback(
    Output("detector-pattern-checklist", "options"),
    Output("detector-pattern-checklist", "value"),
    Input("peakindexing-source", "data"),
    Input(SCOPE_STORE_ID, "data"),
    Input("detector-step-select", "value"),
    prevent_initial_call=True,
)
def populate_detector_pattern_checklist(source, scope, step_value):
    """Refresh the pattern checklist whenever the step changes."""

    if not source:
        return [], []
    if step_value is None or step_value == "":
        raise PreventUpdate
    try:
        dataset = _dataset(source)
        frame_id = _detector_frame(dataset, to_data_scope(scope), step_value)
        patterns = detector_adapter.frame_patterns(dataset, frame_id)
    except PreventUpdate:
        raise
    except Exception:
        return [], []
    options = [{"label": f"Pattern {rank} ({n_indexed} indexed)", "value": rank} for rank, n_indexed in patterns]
    return options, [rank for rank, _ in patterns]


@callback(
    Output("detector-view-graph", "figure"),
    Output("detector-step-summary", "children"),
    Output("detector-loading-target", "children"),
    Output("detector-view-status", "children"),
    Input("peakindexing-source", "data"),
    Input(SCOPE_STORE_ID, "data"),
    Input("peakindexing-path-context", "data"),
    Input("detector-step-select", "value"),
    Input("detector-show-detected", "value"),
    Input("detector-show-indexed", "value"),
    Input("detector-show-missing", "value"),
    Input("detector-show-hkl", "value"),
    Input("detector-marker-size", "value"),
    Input("detector-label-size", "value"),
    Input("detector-pattern-checklist", "value"),
    Input("detector-show-image", "value"),
    Input("detector-image-colormap", "value"),
    Input("detector-image-vmin", "value"),
    Input("detector-image-vmax", "value"),
    Input("detector-image-opacity", "value"),
    prevent_initial_call=True,
)
def update_detector_view(
    source,
    scope,
    path_context,
    step_value,
    show_detected,
    show_indexed,
    show_missing,
    show_hkl,
    marker_size,
    label_size,
    selected_patterns,
    show_image,
    image_colormap,
    image_vmin,
    image_vmax,
    image_opacity,
):
    """Re-render the detector overlay whenever the user changes any control."""

    if not source or step_value is None:
        raise PreventUpdate
    try:
        dataset = _dataset(source)
        frame_id = _detector_frame(dataset, to_data_scope(scope), step_value)
        position = map_adapter.frame_position(dataset, frame_id)
    except PreventUpdate:
        raise
    except Exception as e:
        print(f"Error resolving detector frame: {e}")
        raise PreventUpdate from None

    notes = []
    image = None
    image_result = None
    limits = None
    if show_image:
        path_context = path_context or {}
        image_result = load_detector_image(
            dataset.input_images[position],
            source=dataset.sources[position],
            xml_path=source.get("path"),
            data_folder=path_context.get("data_folder"),
            root_path=path_context.get("root_path"),
        )
        if image_result.image is not None:
            image = image_result.image.data
            limits = detector_adapter.image_limits(
                image_vmin, image_vmax, image_result.image.vmin, image_result.image.vmax
            )
        elif image_result.warning:
            notes.append(image_result.warning)

    common = dict(
        frame_id=frame_id,
        patterns=tuple(selected_patterns) if selected_patterns else (),
        image=image,
        show_detected=bool(show_detected),
        show_indexed=bool(show_indexed),
        show_hkl_labels=bool(show_hkl),
        marker_size=max(1, int(marker_size or 10)),
        label_size=max(6, int(label_size or 10)),
        image_colormap=image_colormap or "gray",
        limits=limits,
        image_opacity=float(image_opacity if image_opacity is not None else 0.8),
    )
    try:
        try:
            fig, view = detector_adapter.build_detector_view(dataset, show_simulated=bool(show_missing), **common)
        except (ValueError, RuntimeError) as error:
            if not show_missing:
                raise
            # Keep measured and indexed overlays; report the simulation problem explicitly.
            notes.append(f"Simulated missing reflections unavailable: {error}")
            fig, view = detector_adapter.build_detector_view(dataset, show_simulated=False, **common)
    except (ValueError, KeyError) as error:
        message = str(error)
        if "geometry" in message:
            message = "Detector geometry is not available for this result; back-projection cannot be computed."
        return dash.no_update, dbc.Alert(message, color="warning", className="mb-0"), "", ""
    except Exception as error:
        print(f"Error rendering detector view: {error}")
        traceback.print_exc()
        return (
            dash.no_update,
            dbc.Alert(f"Could not render detector view: {error}", color="danger", className="mb-0"),
            "",
            "",
        )

    summary = detector_adapter.detector_summary(dataset, view)
    status = html.Span(" ".join(notes), className="text-warning") if notes else ""
    return fig, _detector_step_summary(summary, image_result), "", status


def _detector_step_summary(summary, image_result=None):
    """Compose the small summary card shown beneath the detector graph."""

    x_pos, y_pos, z_pos = summary["sample_position"]
    header_bits = [
        html.Strong(f"Step #{summary['step']}"),
        f"  (frame {summary['frame_id']})  Motor position: ({x_pos:.1f}, {y_pos:.1f}, {z_pos:.1f})",
        html.Br(),
        f"Detector: {summary['detector_id'] or '?'}  |  ",
        f"Detected: {summary['n_measured']}  |  ",
        f"Indexed peaks: {summary['n_indexed_peaks']} ({summary['indexed_fraction'] * 100:.0f}%)",
    ]
    pattern_rows_ = []
    for pattern in summary["patterns"]:
        simulated = f", simulated missing={pattern['n_simulated']}" if pattern.get("n_simulated") else ""
        quality = ""
        if pattern["rms_error_deg"] is not None:
            quality = f", RMS={pattern['rms_error_deg']:.4f}°, goodness={pattern['goodness']:.1f}"
        pattern_rows_.append(
            html.Li(
                f"Pattern {pattern['pattern_index']}: {pattern['n_indexed']} indexed peaks, "
                f"{pattern['n_predicted']} predicted positions{quality}{simulated}"
            )
        )
    body = [html.P(header_bits, className="mb-1")]
    if image_result is not None and image_result.image is not None:
        body.append(
            html.Small(
                f"Image: {image_result.image.path} [{image_result.image.dataset}]",
                className="text-muted d-block mb-1",
            )
        )
    if pattern_rows_:
        body.append(html.Ul(pattern_rows_, className="mb-0 small"))
    return dbc.Card(dbc.CardBody(body), className="mt-2")


# ---------------------------------------------------------------------------
# Callbacks: global data-scope bar (acyclic: controls | Reset -> store; Reset -> controls)
# ---------------------------------------------------------------------------


@callback(
    Output(SCOPE_STORE_ID, "data"),
    Input(SCOPE_PATTERN0_ID, "value"),
    Input(SCOPE_MIN_PEAKS_ID, "value"),
    Input(SCOPE_RESET_ID, "n_clicks"),
)
def collect_data_scope(pattern0_only, min_peaks, reset_clicks):
    """Gather the scope controls into the single global scope store."""
    if dash.ctx.triggered_id == SCOPE_RESET_ID:
        return dict(DEFAULT_SCOPE)
    # The control shows the inclusive maximum to skip (for example, <= 3),
    # while consumers use the minimum peak count to retain (4). Zero is the
    # special off value and keeps every step.
    try:
        displayed_maximum = int(min_peaks)
        minimum_to_keep = displayed_maximum + 1 if displayed_maximum > 0 else 0
    except (TypeError, ValueError):
        minimum_to_keep = DEFAULT_SCOPE["min_peaks"]
    return normalize_scope({"pattern0_only": pattern0_only, "min_peaks": minimum_to_keep})


@callback(
    Output(SCOPE_PATTERN0_ID, "value"),
    Output(SCOPE_MIN_PEAKS_ID, "value"),
    Input(SCOPE_RESET_ID, "n_clicks"),
    prevent_initial_call=True,
)
def reset_data_scope_controls(n_clicks):
    """Return the scope widgets to their neutral values."""
    return DEFAULT_SCOPE["pattern0_only"], DEFAULT_SCOPE["min_peaks"] - 1
