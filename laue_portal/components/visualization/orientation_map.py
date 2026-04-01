"""
2D and 3D orientation map scatter plot components.

Renders sample positions (Xsample, Ysample, Zsample) as scatter plots
colored by crystal orientation or scalar quality metrics.

Coloring modes:
- Scalar: N Indexed, Goodness, RMS Error, N Patterns (Viridis colorscale)
- Cubic IPF: crystal direction mapped to standard IPF triangle colors
- Rodrigues RGB: rotation axis+angle mapped to RGB
- HSV: placeholder for spatial HSV (reserved for pole figure use)

Styling matches Igor Pro's Make2Dplot_xmlData conventions.
"""

import numpy as np
import plotly.graph_objects as go

from laue_portal.analysis.orientation import (
    batch_crystal_directions,
    batch_rodrigues,
)
from laue_portal.analysis.coloring import (
    batch_ipf_colors,
    batch_rodrigues_rgb,
    rgb_to_plotly_colors,
)


# Igor Pro background: gbRGB=(40000,40000,40000) / 65535
_GRAY_BG = "rgb(156, 156, 156)"

# Orientation color modes (no colorscale -- per-point RGB)
_ORIENTATION_MODES = {"cubic_ipf", "rodrigues"}

# Scalar color modes (use Viridis colorscale + colorbar)
_SCALAR_MODES = {"n_indexed", "goodness", "rms_error", "n_patterns"}


def make_orientation_map(
    parsed: dict,
    color_by: str = "n_indexed",
    marker_size: int = 10,
) -> go.Figure:
    """
    Create a 2D orientation scatter plot.

    Parameters
    ----------
    parsed : dict
        Output from xml_parser.parse_indexing_xml().
    color_by : str
        Coloring mode: 'n_indexed', 'goodness', 'rms_error', 'n_patterns',
        'cubic_ipf', or 'rodrigues'.
    marker_size : int
        Marker size in pixels.

    Returns
    -------
    go.Figure
    """
    positions = parsed["positions"]
    depths = parsed["depths"]
    has_depth = not np.all(np.isnan(depths))

    x_vals, y_vals, x_label, y_label = _select_axes(positions, depths, has_depth)
    marker_symbol = "diamond" if has_depth else "square"

    fig = go.Figure()

    marker_dict = _build_marker_dict(parsed, color_by, marker_size, marker_symbol)

    fig.add_trace(go.Scattergl(
        x=x_vals,
        y=y_vals,
        mode="markers",
        marker=marker_dict,
        hovertemplate=(
            "<b>Step %{customdata[0]}</b><br>"
            "Position: (%{customdata[1]:.1f}, %{customdata[2]:.1f}, %{customdata[3]:.1f})<br>"
            "Patterns: %{customdata[4]}<br>"
            "Indexed: %{customdata[5]}  Goodness: %{customdata[6]:.1f}<br>"
            "RMS error: %{customdata[7]:.5f}<br>"
            "<extra></extra>"
        ),
        customdata=_build_customdata(parsed),
    ))

    fig.update_layout(
        xaxis_title=x_label,
        yaxis_title=y_label,
        plot_bgcolor=_GRAY_BG,
        paper_bgcolor="white",
        yaxis=dict(
            scaleanchor="x",
            scaleratio=1,
        ),
        margin=dict(l=60, r=20, t=40, b=60),
        height=550,
        uirevision="orientation-2d",
    )

    return fig


def make_orientation_map_3d(
    parsed: dict,
    color_by: str = "n_indexed",
    marker_size: int = 10,
) -> go.Figure:
    """
    Create a 3D orientation scatter plot using all three sample coordinates.

    Parameters
    ----------
    parsed : dict
        Output from xml_parser.parse_indexing_xml().
    color_by : str
        Coloring mode: 'n_indexed', 'goodness', 'rms_error', 'n_patterns',
        'cubic_ipf', or 'rodrigues'.
    marker_size : int
        Marker size in pixels.

    Returns
    -------
    go.Figure
    """
    positions = parsed["positions"]

    fig = go.Figure()

    marker_dict = _build_marker_dict(parsed, color_by, max(2, marker_size // 3))

    fig.add_trace(go.Scatter3d(
        x=positions[:, 0],
        y=positions[:, 1],
        z=positions[:, 2],
        mode="markers",
        marker=marker_dict,
        hovertemplate=(
            "<b>Step %{customdata[0]}</b><br>"
            "Position: (%{customdata[1]:.1f}, %{customdata[2]:.1f}, %{customdata[3]:.1f})<br>"
            "Patterns: %{customdata[4]}<br>"
            "Indexed: %{customdata[5]}  Goodness: %{customdata[6]:.1f}<br>"
            "RMS error: %{customdata[7]:.5f}<br>"
            "<extra></extra>"
        ),
        customdata=_build_customdata(parsed),
    ))

    fig.update_layout(
        scene=dict(
            xaxis_title="X (um)",
            yaxis_title="Y (um)",
            zaxis_title="Z (um)",
            aspectmode="data",
            bgcolor=_GRAY_BG,
        ),
        margin=dict(l=0, r=0, t=40, b=0),
        height=600,
        uirevision="orientation-3d",
    )

    return fig


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _build_marker_dict(parsed, color_by, marker_size, marker_symbol=None):
    """Build Plotly marker dict for the given coloring mode."""
    base = dict(
        size=marker_size,
        line=dict(width=0),
    )
    if marker_symbol is not None:
        base["symbol"] = marker_symbol

    if color_by in _ORIENTATION_MODES:
        colors = _get_orientation_colors(parsed, color_by)
        base["color"] = colors
        # No colorscale or colorbar for per-point RGB
    else:
        color_vals, color_label = _get_scalar_color_values(parsed, color_by)
        base["color"] = color_vals
        base["colorscale"] = "Viridis"
        base["colorbar"] = dict(title=color_label)

    return base


def _build_customdata(parsed):
    """Build customdata array shared by 2D and 3D traces."""
    positions = parsed["positions"]
    n_points = len(positions)
    return np.column_stack([
        np.arange(n_points),
        positions[:, 0],
        positions[:, 1],
        positions[:, 2],
        parsed["n_patterns"],
        parsed["n_indexed"],
        np.nan_to_num(parsed["goodnesses"], nan=0),
        np.nan_to_num(parsed["rms_errors"], nan=0),
    ])


def _select_axes(positions, depths, has_depth):
    """
    Select X/Y axes following Igor convention.

    - Wire scan at constant X: X=Zsample, Y=Ysample
    - Wire scan with varying X: X=Xsample, Y=Zsample
    - Non-wire scan: X=Xsample, Y=Ysample
    """
    if has_depth:
        x_range = np.nanmax(positions[:, 0]) - np.nanmin(positions[:, 0])
        if x_range < 1.0:
            return (
                positions[:, 2], positions[:, 1],
                "Z (um)", "Y (um)",
            )
        else:
            return (
                positions[:, 0], positions[:, 2],
                "X (um)", "Z (um)",
            )
    else:
        return (
            positions[:, 0], positions[:, 1],
            "X (um)", "Y (um)",
        )


def _get_scalar_color_values(parsed, color_by):
    """Return (color_array, label_string) for scalar coloring modes."""
    if color_by == "n_indexed":
        return parsed["n_indexed"].astype(float), "N Indexed"
    elif color_by == "goodness":
        return parsed["goodnesses"], "Goodness"
    elif color_by == "rms_error":
        return parsed["rms_errors"], "RMS Error"
    elif color_by == "n_patterns":
        return parsed["n_patterns"].astype(float), "N Patterns"
    else:
        return parsed["n_indexed"].astype(float), "N Indexed"


def _get_orientation_colors(parsed, color_by):
    """Return list of 'rgb(r,g,b)' strings for orientation coloring modes."""
    recip_lattices = parsed["recip_lattices"]
    lattice_params = parsed["lattice_params"]

    if color_by == "cubic_ipf":
        crystal_dirs = batch_crystal_directions(recip_lattices)
        rgb = batch_ipf_colors(crystal_dirs)
        return rgb_to_plotly_colors(rgb)

    elif color_by == "rodrigues":
        rod_vecs = batch_rodrigues(recip_lattices, lattice_params)
        rgb = batch_rodrigues_rgb(rod_vecs)
        return rgb_to_plotly_colors(rgb)

    else:
        # Fallback to IPF
        crystal_dirs = batch_crystal_directions(recip_lattices)
        rgb = batch_ipf_colors(crystal_dirs)
        return rgb_to_plotly_colors(rgb)
