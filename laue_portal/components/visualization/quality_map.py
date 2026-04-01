"""
2D and 3D quality map scatter plot components.

Renders sample positions colored by indexing quality metrics
(goodness, rms_error, n_indexed, n_patterns).

Styling matches Igor Pro conventions with Viridis colorscale.
"""

import numpy as np
import plotly.graph_objects as go

from laue_portal.components.visualization.orientation_map import _select_axes


_GRAY_BG = "rgb(156, 156, 156)"

# Metric definitions: key -> (array_key, display_name, colorscale)
_METRICS = {
    "goodness": ("goodnesses", "Goodness", "Viridis"),
    "rms_error": ("rms_errors", "RMS Error (deg)", "Viridis_r"),
    "n_indexed": ("n_indexed", "N Indexed", "Viridis"),
    "n_patterns": ("n_patterns", "N Patterns", "Viridis"),
}


def _get_metric(parsed, metric):
    """Return (color_vals, display_name, colorscale) for a metric key."""
    array_key, display_name, colorscale = _METRICS.get(
        metric, _METRICS["goodness"]
    )
    color_vals = parsed[array_key]
    if hasattr(color_vals, "astype") and color_vals.dtype in (np.int32, np.int64):
        color_vals = color_vals.astype(float)
    return color_vals, display_name, colorscale


def make_quality_map(
    parsed: dict,
    metric: str = "goodness",
    marker_size: int = 10,
) -> go.Figure:
    """
    Create a 2D quality map scatter plot.

    Parameters
    ----------
    parsed : dict
        Output from xml_parser.parse_indexing_xml().
    metric : str
        One of 'goodness', 'rms_error', 'n_indexed', 'n_patterns'.
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
    color_vals, display_name, colorscale = _get_metric(parsed, metric)

    n_points = len(x_vals)
    marker_symbol = "diamond" if has_depth else "square"

    fig = go.Figure()

    fig.add_trace(go.Scattergl(
        x=x_vals,
        y=y_vals,
        mode="markers",
        marker=dict(
            size=marker_size,
            symbol=marker_symbol,
            color=color_vals,
            colorscale=colorscale,
            colorbar=dict(title=display_name),
            line=dict(width=0),
        ),
        hovertemplate=(
            "<b>Step %{customdata[0]}</b><br>"
            f"{display_name}: " + "%{marker.color:.4f}<br>"
            "Position: (%{customdata[1]:.1f}, %{customdata[2]:.1f})<br>"
            "<extra></extra>"
        ),
        customdata=np.column_stack([
            np.arange(n_points),
            positions[:, 0],
            positions[:, 1],
        ]),
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
        uirevision="quality-2d",
    )

    return fig


def make_quality_map_3d(
    parsed: dict,
    metric: str = "goodness",
    marker_size: int = 10,
) -> go.Figure:
    """
    Create a 3D quality map scatter plot using all three sample coordinates.

    Parameters
    ----------
    parsed : dict
        Output from xml_parser.parse_indexing_xml().
    metric : str
        One of 'goodness', 'rms_error', 'n_indexed', 'n_patterns'.
    marker_size : int
        Marker size in pixels.

    Returns
    -------
    go.Figure
    """
    positions = parsed["positions"]
    color_vals, display_name, colorscale = _get_metric(parsed, metric)
    n_points = len(positions)

    fig = go.Figure()

    fig.add_trace(go.Scatter3d(
        x=positions[:, 0],
        y=positions[:, 1],
        z=positions[:, 2],
        mode="markers",
        marker=dict(
            size=max(2, marker_size // 3),
            color=color_vals,
            colorscale=colorscale,
            colorbar=dict(title=display_name),
            line=dict(width=0),
        ),
        hovertemplate=(
            "<b>Step %{customdata[0]}</b><br>"
            f"{display_name}: " + "%{marker.color:.4f}<br>"
            "Position: (%{x:.1f}, %{y:.1f}, %{z:.1f})<br>"
            "<extra></extra>"
        ),
        customdata=np.column_stack([
            np.arange(n_points),
        ]),
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
        uirevision="quality-3d",
    )

    return fig
