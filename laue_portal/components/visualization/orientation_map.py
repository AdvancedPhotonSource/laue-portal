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
        uid="orientation-2d-main",
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
        uirevision="orientation-2d",
        autosize=True,
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
        uid="orientation-3d-main",
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
        uirevision="orientation-3d",
        scene_uirevision="orientation-3d",
        autosize=True,
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


# ---------------------------------------------------------------------------
# Cross-plot selection highlighting (Stage 3)
# ---------------------------------------------------------------------------

def apply_selection_highlight(fig, parsed, selected_grains, marker_size,
                              is_3d=False):
    """
    Modify a figure in-place to highlight selected grains.

    Strategy:
    - Dim the existing (first) data trace by reducing opacity
    - Add a second highlight trace with bright outlines for selected grains

    Parameters
    ----------
    fig : go.Figure
        The orientation or quality map figure to modify.
    parsed : dict
        Parsed XML data from ``parse_indexing_xml()``.
    selected_grains : list of int
        Grain (step) indices to highlight.
    marker_size : int
        Current marker size (highlight ring will be larger).
    is_3d : bool
        Whether the figure is a 3D scatter plot.
    """
    if not fig.data or not selected_grains:
        return

    positions = parsed["positions"]
    n_points = len(positions)
    selected_set = set(selected_grains)

    # Dim unselected points on the main trace
    main_trace = fig.data[0]
    current_colors = main_trace.marker.color

    # Build opacity array: 0.2 for unselected, 1.0 for selected
    opacity_arr = np.where(
        np.isin(np.arange(n_points), list(selected_set)), 1.0, 0.2,
    )

    # Determine if colors are per-point RGB strings or scalar values
    is_rgb_strings = (
        isinstance(current_colors, (list, tuple))
        and len(current_colors) == n_points
        and isinstance(current_colors[0], str)
    )

    if is_rgb_strings:
        # Per-point RGB strings -- convert to RGBA with opacity
        new_colors = []
        for i, c in enumerate(current_colors):
            if c.startswith("rgb("):
                new_colors.append(
                    c.replace("rgb(", "rgba(").replace(")", f",{opacity_arr[i]:.2f})")
                )
            else:
                new_colors.append(c)
        main_trace.marker.color = new_colors
    else:
        # Scalar colorscale mode -- Scattergl doesn't support per-point
        # opacity, so sample the colorscale to get per-point RGB strings,
        # then apply per-point opacity via RGBA.
        import plotly.colors as pc

        color_vals = np.asarray(current_colors, dtype=float)
        colorscale = main_trace.marker.colorscale

        # Resolve colorscale to list-of-lists format expected by
        # pc.sample_colorscale.  Plotly stores it as tuple-of-tuples
        # after figure creation; convert back.
        if isinstance(colorscale, str):
            colorscale = pc.get_colorscale(colorscale)
        else:
            colorscale = [[pos, col] for pos, col in colorscale]

        # Normalize values to [0, 1]
        vmin = np.nanmin(color_vals)
        vmax = np.nanmax(color_vals)
        if vmax - vmin > 0:
            normed = (color_vals - vmin) / (vmax - vmin)
        else:
            normed = np.zeros_like(color_vals)
        normed = np.clip(normed, 0, 1)

        # Sample colorscale to get per-point RGB, then apply opacity
        sampled = pc.sample_colorscale(colorscale, normed, colortype="rgb")
        new_colors = []
        for i, c in enumerate(sampled):
            if c.startswith("rgb("):
                new_colors.append(
                    c.replace("rgb(", "rgba(").replace(")", f",{opacity_arr[i]:.2f})")
                )
            else:
                new_colors.append(c)
        main_trace.marker.color = new_colors
        # Remove colorscale since we're now using per-point colors
        main_trace.marker.colorscale = None

    # Add highlight ring trace for selected grains
    sel_mask = np.isin(np.arange(n_points), list(selected_set))
    if not np.any(sel_mask):
        return

    highlight_size = max(marker_size + 6, int(marker_size * 1.4))

    # Derive a stable uid from the main trace so Plotly can track this
    # highlight trace across figure updates even when trace count changes.
    main_uid = fig.data[0].uid or "main"
    highlight_uid = main_uid.replace("-main", "-highlight")

    if is_3d:
        fig.add_trace(go.Scatter3d(
            x=positions[sel_mask, 0],
            y=positions[sel_mask, 1],
            z=positions[sel_mask, 2],
            mode="markers",
            marker=dict(
                size=max(3, highlight_size // 3),
                color="rgba(0,0,0,0)",
                symbol="circle",
                line=dict(color="white", width=2),
            ),
            hoverinfo="skip",
            showlegend=True,
            name=f"Selected ({sel_mask.sum()})",
            uid=highlight_uid,
        ))
    else:
        depths = parsed["depths"]
        has_depth = not np.all(np.isnan(depths))
        x_vals, y_vals, _, _ = _select_axes(positions, depths, has_depth)

        fig.add_trace(go.Scattergl(
            x=x_vals[sel_mask],
            y=y_vals[sel_mask],
            mode="markers",
            marker=dict(
                size=highlight_size,
                color="rgba(0,0,0,0)",
                symbol="circle-open",
                line=dict(color="white", width=2),
            ),
            hoverinfo="skip",
            showlegend=True,
            name=f"Selected ({sel_mask.sum()})",
            uid=highlight_uid,
        ))
