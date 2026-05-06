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

from dash import html
from PIL import Image

from laue_portal.analysis.coloring import (
    make_color_hexagon,
    make_cubic_ipf_triangle,
)

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
# Dispatchers used by page callbacks
# ---------------------------------------------------------------------------


def orientation_color_key(color_mode: Optional[str], surface: Optional[str]) -> html.Div:
    """
    Return the appropriate color-key widget for the *Orientation* tab.

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
    return _empty_key()


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
        return hsv_hexagon_legend(caption="Stereographic position (HSV)")
    return _empty_key()
