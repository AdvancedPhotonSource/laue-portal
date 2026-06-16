"""
Color-key (legend) widgets for the peak-indexing visualization tabs.

Provides reference images for orientation color modes that produce
per-point RGB values without a Plotly colorbar:

* ``cubic_ipf`` -> standard cubic IPF stereographic triangle with
  001 (red) / 101 (green) / 111 (blue) corners.
* ``pole_hsv`` (and pole-figure ``hsv_position``) -> circular HSV
  color wheel.

The pixel arrays are produced once at import time by
:func:`laue_portal.analysis.coloring.make_cubic_ipf_triangle` and
:func:`laue_portal.analysis.coloring.make_color_hexagon`, then encoded
as base64 PNG data URIs that can be served directly via ``html.Img``.

The corner labels (001 / 101 / 111) and the dynamic caption
("Crystal direction \u2225 sample normal", ...) are rendered as HTML
elements layered around the image so they remain styleable via CSS
without requiring PIL fonts.
"""

from __future__ import annotations

import base64
import io
from typing import Optional

import dash_bootstrap_components as dbc
from dash import html
from PIL import Image

from laue_portal.analysis.coloring import (
    make_color_hexagon,
    make_cubic_ipf_triangle,
)

# ---------------------------------------------------------------------------
# Palette options (Plotly built-in colorscale names)
# ---------------------------------------------------------------------------

#: Palettes offered to the user for scalar color modes on the orientation
#: tab.  Values must match Plotly's built-in colorscale names (case
#: insensitive).  ``Viridis`` is the default; ``Jet`` and ``Rainbow`` are
#: included on request despite being perceptually non-uniform.
PALETTE_OPTIONS = [
    {"label": "Viridis", "value": "Viridis"},
    {"label": "Plasma", "value": "Plasma"},
    {"label": "Inferno", "value": "Inferno"},
    {"label": "Magma", "value": "Magma"},
    {"label": "Jet", "value": "Jet"},
    {"label": "Rainbow", "value": "Rainbow"},
    {"label": "Terrain", "value": "Earth"},
]

# Note: Plotly does not ship a built-in named "terrain" colorscale, but
# its "Earth" colorscale is the conventional analogue (greens -> browns
# -> whites). We expose it under the user-facing label "Terrain".

DEFAULT_PALETTE = "Viridis"

# ---------------------------------------------------------------------------
# Pre-rendered color-key images (computed once at import)
# ---------------------------------------------------------------------------


def _rgba_array_to_data_uri(rgba: "np.ndarray") -> str:  # noqa: F821
    """Encode an (H, W, 4) uint8 RGBA array as a base64 PNG data URI."""
    img = Image.fromarray(rgba, mode="RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


# Generated lazily on first access so module import stays cheap; cached
# afterwards. Resolutions chosen to render crisply in the ~200 px sidebar
# slot (devices with 2x DPR render at 400 px).
_IPF_TRIANGLE_RES = 256
_HSV_HEXAGON_RES = 256

_ipf_triangle_uri: Optional[str] = None
_hsv_hexagon_uri: Optional[str] = None


def _get_ipf_triangle_uri() -> str:
    global _ipf_triangle_uri
    if _ipf_triangle_uri is None:
        _ipf_triangle_uri = _rgba_array_to_data_uri(make_cubic_ipf_triangle(resolution=_IPF_TRIANGLE_RES))
    return _ipf_triangle_uri


def _get_hsv_hexagon_uri() -> str:
    global _hsv_hexagon_uri
    if _hsv_hexagon_uri is None:
        _hsv_hexagon_uri = _rgba_array_to_data_uri(make_color_hexagon(resolution=_HSV_HEXAGON_RES))
    return _hsv_hexagon_uri


# ---------------------------------------------------------------------------
# Caption helpers
# ---------------------------------------------------------------------------

# Human-readable surface-direction labels matching the
# ``orientation-surface-select`` / ``stereo-surface-select`` options.
_SURFACE_LABELS = {
    "normal": "sample normal",
    "X": "sample X",
    "H": "sample H",
    "Y": "sample Y",
    "Z": "sample Z",
    "F": "sample F",
}


def _surface_label(surface: Optional[str]) -> str:
    if not surface:
        return "sample normal"
    return _SURFACE_LABELS.get(surface, f"sample {surface}")


# ---------------------------------------------------------------------------
# Public component builders
# ---------------------------------------------------------------------------


def ipf_triangle_legend(caption: Optional[str] = None) -> html.Div:
    """
    Build the cubic IPF reference triangle widget.

    Parameters
    ----------
    caption
        Optional short text rendered below the triangle (e.g.
        ``"Crystal direction \u2225 sample normal"``).
    """
    img = html.Img(
        src=_get_ipf_triangle_uri(),
        alt="Cubic IPF standard triangle",
        className="pi-ipf-legend-img",
        draggable="false",
    )

    # Corner label positions are tuned to the geometry of
    # ``make_cubic_ipf_triangle``: the triangle occupies the lower-left
    # half of the square, with vertices at the bottom-left (001), the
    # right edge midpoint-ish (101), and the top-right (111).
    corners = [
        html.Span("001", className="pi-ipf-corner-label pi-ipf-corner-001"),
        html.Span("101", className="pi-ipf-corner-label pi-ipf-corner-101"),
        html.Span("111", className="pi-ipf-corner-label pi-ipf-corner-111"),
    ]

    children = [
        html.Div([img, *corners], className="pi-ipf-legend-frame"),
    ]
    if caption:
        children.append(html.Div(caption, className="pi-ipf-caption"))

    return html.Div(children, className="pi-ipf-legend")


def hsv_hexagon_legend(caption: Optional[str] = None) -> html.Div:
    """
    Build the HSV color-wheel reference widget for ``pole_hsv`` mode.

    Six axis labels are layered around the circle (none on the vertical
    poles): +X right, -X left, +Y top-left, -Y bottom-right, +Z
    bottom-left, -Z top-right. Positioning is done via CSS classes so
    the labels remain styleable.
    """
    img = html.Img(
        src=_get_hsv_hexagon_uri(),
        alt="HSV color wheel",
        className="pi-ipf-legend-img pi-ipf-legend-img--circle",
        draggable="false",
    )
    axis_labels = [
        html.Span("+X", className="pi-hsv-axis-label pi-hsv-axis-px"),
        html.Span("\u2212X", className="pi-hsv-axis-label pi-hsv-axis-nx"),
        html.Span("+Y", className="pi-hsv-axis-label pi-hsv-axis-py"),
        html.Span("\u2212Y", className="pi-hsv-axis-label pi-hsv-axis-ny"),
        html.Span("+Z", className="pi-hsv-axis-label pi-hsv-axis-pz"),
        html.Span("\u2212Z", className="pi-hsv-axis-label pi-hsv-axis-nz"),
    ]
    children = [html.Div([img, *axis_labels], className="pi-ipf-legend-frame")]
    if caption:
        children.append(html.Div(caption, className="pi-ipf-caption"))
    return html.Div(children, className="pi-ipf-legend")


def _empty_key(text: str = "No reference key for this color mode.") -> html.Div:
    return html.Div(
        html.Small(text, className="text-muted"),
        className="pi-ipf-legend pi-ipf-legend--empty",
    )


# ---------------------------------------------------------------------------
# Scalar-mode controls (palette + manual vmin/vmax)
# ---------------------------------------------------------------------------

# Stable IDs for the scalar control widgets.  The page callbacks read
# these as Inputs/States so they need to be addressable even when the
# section is rendered dynamically by the dispatcher.
SCALAR_PALETTE_ID = "orientation-color-palette"
SCALAR_REVERSE_ID = "orientation-color-reverse"
SCALAR_MIN_ID = "orientation-color-min"
SCALAR_MAX_ID = "orientation-color-max"
SCALAR_RESET_ID = "orientation-color-reset-btn"


def scalar_color_controls(
    palette: str = DEFAULT_PALETTE,
    reverse: bool = False,
    vmin: Optional[float] = None,
    vmax: Optional[float] = None,
) -> html.Div:
    """
    Build the palette + min/max + reset controls shown for scalar
    coloring modes (``n_indexed``, ``goodness``, ``rms_error``,
    ``n_patterns``).

    All inputs use stable IDs (see ``SCALAR_*_ID`` constants) so the
    page-side callbacks can read them as ``State`` even though this
    fragment is rendered dynamically by
    :func:`orientation_color_key`.
    """
    return html.Div(
        className="pi-color-controls",
        children=[
            # ── Palette select ──
            html.Div(
                className="pi-color-controls-row",
                children=[
                    html.Label("Palette", className="pi-color-controls-label"),
                    dbc.Select(
                        id=SCALAR_PALETTE_ID,
                        options=PALETTE_OPTIONS,
                        value=palette or DEFAULT_PALETTE,
                        className="form-select",
                    ),
                ],
            ),
            # ── Reverse checkbox ──
            html.Div(
                className="pi-color-controls-row",
                children=[
                    html.Label("", className="pi-color-controls-label"),
                    dbc.Checkbox(
                        id=SCALAR_REVERSE_ID,
                        label="Reverse",
                        value=bool(reverse),
                        className="pi-color-controls-check",
                    ),
                ],
            ),
            # ── Min / Max numeric inputs ──
            html.Div(
                className="pi-color-controls-row pi-color-controls-row--pair",
                children=[
                    html.Label("Min", className="pi-color-controls-label"),
                    dbc.Input(
                        id=SCALAR_MIN_ID,
                        type="number",
                        step="any",
                        value=vmin,
                        debounce=True,
                        className="form-control pi-color-controls-num",
                    ),
                ],
            ),
            html.Div(
                className="pi-color-controls-row pi-color-controls-row--pair",
                children=[
                    html.Label("Max", className="pi-color-controls-label"),
                    dbc.Input(
                        id=SCALAR_MAX_ID,
                        type="number",
                        step="any",
                        value=vmax,
                        debounce=True,
                        className="form-control pi-color-controls-num",
                    ),
                ],
            ),
            # ── Reset to auto range ──
            html.Div(
                className="pi-color-controls-row pi-color-controls-row--reset",
                children=[
                    dbc.Button(
                        [html.I(className="bi bi-arrow-counterclockwise me-1"), "Reset range"],
                        id=SCALAR_RESET_ID,
                        color="secondary",
                        outline=True,
                        size="sm",
                    ),
                ],
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Dispatchers used by page callbacks
# ---------------------------------------------------------------------------


def orientation_color_key(color_mode: Optional[str], surface: Optional[str]) -> html.Div:
    """
    Return the legend (image) portion of the orientation color-key slot.

    The scalar mode controls (palette/min/max/reset) are mounted once in
    the static page layout via :func:`scalar_color_controls` and
    show/hide via :func:`scalar_controls_visible` rather than being
    re-created here.  This keeps the control IDs available to Dash
    callbacks regardless of the current color mode.

    Parameters
    ----------
    color_mode
        Value of ``orientation-color-select`` (e.g. ``"cubic_ipf"``).
    surface
        Value of ``orientation-surface-select`` (e.g. ``"normal"``).
    """
    surf = _surface_label(surface)

    if color_mode == "cubic_ipf":
        return ipf_triangle_legend(
            caption=f"Crystal direction \u2225 {surf}",
        )
    if color_mode == "pole_hsv":
        return hsv_hexagon_legend(
            caption=f"{surf.capitalize()} direction in stereographic HSV",
        )
    if color_mode in {"rodrigues", "n_indexed", "goodness", "rms_error", "n_patterns"}:
        # These modes carry their visual feedback in the figure or controls.
        # Keep this slot empty so controls sit flush against the section head.
        return html.Div()
    return _empty_key()


def scalar_controls_visible(color_mode: Optional[str]) -> dict:
    """Return a CSS ``style`` dict that hides the scalar controls block
    for non-scalar coloring modes."""
    if color_mode in {"n_indexed", "goodness", "rms_error", "n_patterns"}:
        return {"display": "block"}
    return {"display": "none"}


def stereo_color_key(color_mode: Optional[str]) -> html.Div:
    """
    Return the appropriate color-key widget for the *Pole Figure* tab.

    The pole-figure tab has its own surface selector but the legend on
    this tab represents the cubic fundamental zone itself, so the caption
    stays static.
    """
    if color_mode == "ipf":
        return ipf_triangle_legend(caption="Cubic IPF (m\u20133m)")
    if color_mode == "hsv_position":
        return hsv_hexagon_legend(caption="Pole position (HSV)")
    return _empty_key()
