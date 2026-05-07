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

from laue_portal.analysis.coloring import (
    batch_ipf_colors,
    batch_rodrigues_rgb,
    hsv_wheel_color,
    pole_figure_color_radius,
    rgb_to_plotly_colors,
)
from laue_portal.analysis.orientation import (
    batch_crystal_directions,
    batch_orientations,
    batch_rodrigues,
    misorientation_from_reference,
)
from laue_portal.analysis.projection import (
    cubic_hkl_family,
    get_surface_vectors,
    pole_figure_points,
)

# Igor Pro background: gbRGB=(40000,40000,40000) / 65535
_GRAY_BG = "rgb(156, 156, 156)"

# Orientation color modes (no colorscale -- per-point RGB)
_ORIENTATION_MODES = {"cubic_ipf", "rodrigues", "misorientation", "pole_hsv"}

# Scalar color modes (use Viridis colorscale + colorbar)
_SCALAR_MODES = {"n_indexed", "goodness", "rms_error", "n_patterns"}

# ---------------------------------------------------------------------------
# Axis selection
# ---------------------------------------------------------------------------
# Names accepted by ``_resolve_axis``.  X/Y/Z come straight from the XML;
# H/F are rotated sample-frame coordinates pre-computed by
# ``xml_parser.parse_indexing_xml`` (see ``yz_to_hf``).  ``depth`` exposes
# the per-step depth field (NaN-padded if absent).  ``auto`` defers to the
# Igor-style heuristic in ``_select_axes_auto``.
_AXIS_CHOICES = ("auto", "X", "Y", "Z", "H", "F", "depth")

_AXIS_LABELS = {
    "X": "X (um)",
    "Y": "Y (um)",
    "Z": "Z (um)",
    "H": "H (um)",
    "F": "F (um)",
    "depth": "depth (um)",
}


def _resolve_axis(parsed, axis_name):
    """
    Return ``(values, label)`` for a named axis.

    Recognised names: ``"X"``, ``"Y"``, ``"Z"``, ``"H"``, ``"F"``,
    ``"depth"``.  Unknown names fall back to X.
    """
    positions = parsed["positions"]
    if axis_name == "X":
        return positions[:, 0], _AXIS_LABELS["X"]
    if axis_name == "Y":
        return positions[:, 1], _AXIS_LABELS["Y"]
    if axis_name == "Z":
        return positions[:, 2], _AXIS_LABELS["Z"]
    if axis_name == "H":
        # ``positions_hf`` is added by xml_parser; fall back to a runtime
        # compute if an old cached dict is missing it.
        hf = parsed.get("positions_hf")
        if hf is None:
            from laue_portal.analysis.xml_parser import positions_hf as _compute_hf

            hf = _compute_hf(positions)
        return hf[:, 0], _AXIS_LABELS["H"]
    if axis_name == "F":
        hf = parsed.get("positions_hf")
        if hf is None:
            from laue_portal.analysis.xml_parser import positions_hf as _compute_hf

            hf = _compute_hf(positions)
        return hf[:, 1], _AXIS_LABELS["F"]
    if axis_name == "depth":
        return parsed["depths"], _AXIS_LABELS["depth"]
    # Unknown -- fall back to X
    return positions[:, 0], _AXIS_LABELS["X"]


def make_orientation_map(
    parsed: dict,
    color_by: str = "n_indexed",
    marker_size: int = 10,
    surface: str = "normal",
    ref_grain_index: int = None,
    pole_hkl: tuple = None,
    pole_center_xy: tuple = None,
    pole_color_rad_deg: float = 22.5,
    palette: str = "Viridis",
    reverse_palette: bool = False,
    cmin: float = None,
    cmax: float = None,
    x_axis: str = "auto",
    y_axis: str = "auto",
) -> go.Figure:
    """
    Create a 2D orientation scatter plot.

    Parameters
    ----------
    parsed : dict
        Output from xml_parser.parse_indexing_xml().
    color_by : str
        Coloring mode: 'n_indexed', 'goodness', 'rms_error', 'n_patterns',
        'cubic_ipf', 'rodrigues', 'misorientation', or 'pole_hsv'.
    marker_size : int
        Marker size in pixels.
    surface : str
        Surface direction name (``"normal"``, ``"X"``, ``"H"``, ``"Y"``,
        ``"Z"``).  Affects IPF crystal-direction coloring.
    ref_grain_index : int, optional
        Reference grain index for ``"misorientation"`` coloring.
    pole_hkl : tuple of int, optional
        Miller indices ``(h, k, l)`` for ``"pole_hsv"`` coloring (e.g.
        ``(1, 0, 0)``).
    pole_center_xy : tuple of float, optional
        ``(x0, y0)`` center for ``"pole_hsv"`` HSV coloring on the pole
        figure.  Default ``(0, 0)``.
    pole_color_rad_deg : float
        Angular color-saturation radius in degrees for ``"pole_hsv"`` mode.
        Default 22.5.
    palette : str
        Plotly colorscale name for scalar modes (e.g. ``"Viridis"``,
        ``"Jet"``, ``"Plasma"``).  Ignored for orientation modes.
    reverse_palette : bool
        Reverse the colorscale (Plotly ``_r`` convention).  Ignored for
        orientation modes.
    cmin, cmax : float, optional
        Manual lower/upper bounds for the scalar colorscale.  When
        ``None`` Plotly auto-selects from the data range.  Ignored for
        orientation modes.
    x_axis, y_axis : str, optional
        Names of the axes to plot.  One of ``"auto"`` (Igor-style
        heuristic, default), ``"X"``, ``"Y"``, ``"Z"``, ``"H"``, ``"F"``,
        or ``"depth"``.  H and F are wire-frame coordinates rotated from
        ``(Y, Z)`` (see ``xml_parser.yz_to_hf``).

    Returns
    -------
    go.Figure
    """
    positions = parsed["positions"]
    depths = parsed["depths"]
    has_depth = not np.all(np.isnan(depths))

    x_vals, y_vals, x_label, y_label = _select_axes(
        positions, depths, has_depth, x_axis=x_axis, y_axis=y_axis, parsed=parsed
    )
    marker_symbol = "diamond" if has_depth else "square"

    fig = go.Figure()

    marker_dict = _build_marker_dict(
        parsed,
        color_by,
        marker_size,
        marker_symbol,
        surface=surface,
        ref_grain_index=ref_grain_index,
        pole_hkl=pole_hkl,
        pole_center_xy=pole_center_xy,
        pole_color_rad_deg=pole_color_rad_deg,
        palette=palette,
        reverse_palette=reverse_palette,
        cmin=cmin,
        cmax=cmax,
    )

    fig.add_trace(
        go.Scattergl(
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
        )
    )

    fig.update_layout(
        xaxis_title=x_label,
        yaxis_title=y_label,
        xaxis=dict(uirevision="orientation-2d-x"),
        plot_bgcolor=_GRAY_BG,
        paper_bgcolor="white",
        yaxis=dict(
            scaleanchor="x",
            scaleratio=1,
            uirevision="orientation-2d-y",
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
    surface: str = "normal",
    ref_grain_index: int = None,
    pole_hkl: tuple = None,
    pole_center_xy: tuple = None,
    pole_color_rad_deg: float = 22.5,
    palette: str = "Viridis",
    reverse_palette: bool = False,
    cmin: float = None,
    cmax: float = None,
    x_axis: str = "X",
    y_axis: str = "Y",
    z_axis: str = "Z",
) -> go.Figure:
    """
    Create a 3D orientation scatter plot using all three sample coordinates.

    Parameters
    ----------
    parsed : dict
        Output from xml_parser.parse_indexing_xml().
    color_by : str
        Coloring mode: 'n_indexed', 'goodness', 'rms_error', 'n_patterns',
        'cubic_ipf', 'rodrigues', 'misorientation', or 'pole_hsv'.
    marker_size : int
        Marker size in pixels.
    surface : str
        Surface direction name (``"normal"``, ``"X"``, ``"H"``, ``"Y"``,
        ``"Z"``).  Affects IPF crystal-direction coloring.
    ref_grain_index : int, optional
        Reference grain index for ``"misorientation"`` coloring.
    pole_hkl : tuple of int, optional
        Miller indices ``(h, k, l)`` for ``"pole_hsv"`` coloring.
    pole_center_xy : tuple of float, optional
        ``(x0, y0)`` center for ``"pole_hsv"`` HSV coloring.
    pole_color_rad_deg : float
        Angular color-saturation radius in degrees for ``"pole_hsv"`` mode.
    palette, reverse_palette, cmin, cmax
        See :func:`make_orientation_map`.  Apply only to scalar modes.
    x_axis, y_axis, z_axis : str, optional
        Names of the three axes.  Each is one of ``"X"``, ``"Y"``, ``"Z"``,
        ``"H"``, ``"F"``, or ``"depth"``.  Defaults reproduce the legacy
        X / Y / Z Cartesian layout.

    Returns
    -------
    go.Figure
    """
    x_vals, x_label = _resolve_axis(parsed, x_axis or "X")
    y_vals, y_label = _resolve_axis(parsed, y_axis or "Y")
    z_vals, z_label = _resolve_axis(parsed, z_axis or "Z")

    fig = go.Figure()

    marker_dict = _build_marker_dict(
        parsed,
        color_by,
        max(2, marker_size // 3),
        surface=surface,
        ref_grain_index=ref_grain_index,
        pole_hkl=pole_hkl,
        pole_center_xy=pole_center_xy,
        pole_color_rad_deg=pole_color_rad_deg,
        palette=palette,
        reverse_palette=reverse_palette,
        cmin=cmin,
        cmax=cmax,
    )

    fig.add_trace(
        go.Scatter3d(
            x=x_vals,
            y=y_vals,
            z=z_vals,
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
        )
    )

    fig.update_layout(
        scene=dict(
            xaxis_title=x_label,
            yaxis_title=y_label,
            zaxis_title=z_label,
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


def _build_marker_dict(
    parsed,
    color_by,
    marker_size,
    marker_symbol=None,
    surface="normal",
    ref_grain_index=None,
    pole_hkl=None,
    pole_center_xy=None,
    pole_color_rad_deg=22.5,
    palette="Viridis",
    reverse_palette=False,
    cmin=None,
    cmax=None,
):
    """Build Plotly marker dict for the given coloring mode."""
    base = dict(
        size=marker_size,
        line=dict(width=0),
    )
    if marker_symbol is not None:
        base["symbol"] = marker_symbol

    if color_by in _ORIENTATION_MODES:
        colors = _get_orientation_colors(
            parsed,
            color_by,
            surface=surface,
            ref_grain_index=ref_grain_index,
            pole_hkl=pole_hkl,
            pole_center_xy=pole_center_xy,
            pole_color_rad_deg=pole_color_rad_deg,
        )
        base["color"] = colors
        # No colorscale or colorbar for per-point RGB
    else:
        color_vals, color_label = _get_scalar_color_values(parsed, color_by)
        base["color"] = color_vals
        # Apply user-selected palette + optional reverse (Plotly _r convention).
        scale = palette or "Viridis"
        if reverse_palette and not scale.endswith("_r"):
            scale = f"{scale}_r"
        base["colorscale"] = scale
        base["colorbar"] = dict(title=color_label)
        # Manual color range; leave Plotly to auto-pick when None.
        if cmin is not None:
            base["cmin"] = float(cmin)
        if cmax is not None:
            base["cmax"] = float(cmax)

    return base


def _build_customdata(parsed):
    """Build customdata array shared by 2D and 3D traces."""
    positions = parsed["positions"]
    n_points = len(positions)
    return np.column_stack(
        [
            np.arange(n_points),
            positions[:, 0],
            positions[:, 1],
            positions[:, 2],
            parsed["n_patterns"],
            parsed["n_indexed"],
            np.nan_to_num(parsed["goodnesses"], nan=0),
            np.nan_to_num(parsed["rms_errors"], nan=0),
        ]
    )


def _select_axes(positions, depths, has_depth, x_axis="auto", y_axis="auto", parsed=None):
    """
    Select X/Y axes for the 2-D orientation map.

    When *x_axis* / *y_axis* are ``"auto"`` (default) the choice follows the
    Igor convention:

    - Wire scan at constant X: X=Zsample, Y=Ysample
    - Wire scan with varying X: X=Xsample, Y=Zsample
    - Non-wire scan: X=Xsample, Y=Ysample

    Otherwise each axis is resolved individually via :func:`_resolve_axis`,
    which accepts ``"X"``, ``"Y"``, ``"Z"``, ``"H"``, ``"F"``, ``"depth"``.
    A *parsed* dict is required when either axis is non-auto so the H/F
    columns can be looked up.
    """
    auto_pair = (x_axis in (None, "auto")) and (y_axis in (None, "auto"))

    if auto_pair:
        if has_depth:
            x_range = np.nanmax(positions[:, 0]) - np.nanmin(positions[:, 0])
            if x_range < 1.0:
                return (
                    positions[:, 2],
                    positions[:, 1],
                    _AXIS_LABELS["Z"],
                    _AXIS_LABELS["Y"],
                )
            else:
                return (
                    positions[:, 0],
                    positions[:, 2],
                    _AXIS_LABELS["X"],
                    _AXIS_LABELS["Z"],
                )
        else:
            return (
                positions[:, 0],
                positions[:, 1],
                _AXIS_LABELS["X"],
                _AXIS_LABELS["Y"],
            )

    # User-selected axes.  Build a minimal parsed-like dict if the caller
    # didn't supply one (legacy callers passed only positions/depths).
    if parsed is None:
        parsed = {"positions": positions, "depths": depths}

    # Resolve "auto" on a per-axis basis by defaulting to X / Y.
    x_choice = "X" if x_axis in (None, "auto") else x_axis
    y_choice = "Y" if y_axis in (None, "auto") else y_axis

    x_vals, x_label = _resolve_axis(parsed, x_choice)
    y_vals, y_label = _resolve_axis(parsed, y_choice)
    return x_vals, y_vals, x_label, y_label


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


def is_scalar_mode(color_by: str) -> bool:
    """Return True if ``color_by`` is one of the scalar/colorbar modes."""
    return color_by in _SCALAR_MODES


def get_scalar_auto_range(parsed: dict, color_by: str):
    """
    Return ``(vmin, vmax)`` from the data for a scalar coloring mode.

    Returns ``(None, None)`` if ``color_by`` is not a scalar mode or if
    the data is empty / all NaN.
    """
    if not is_scalar_mode(color_by):
        return (None, None)

    values, _ = _get_scalar_color_values(parsed, color_by)
    arr = np.asarray(values, dtype=float)
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return (None, None)
    return (float(finite.min()), float(finite.max()))


def _get_orientation_colors(
    parsed,
    color_by,
    surface="normal",
    ref_grain_index=None,
    pole_hkl=None,
    pole_center_xy=None,
    pole_color_rad_deg=22.5,
):
    """Return list of 'rgb(r,g,b)' strings for orientation coloring modes."""
    recip_lattices = parsed["recip_lattices"]
    lattice_params = parsed["lattice_params"]

    # Look up the surface normal vector for the chosen surface direction.
    surf_normal, surf_roll, surf_tilt = get_surface_vectors(surface)

    if color_by == "cubic_ipf":
        crystal_dirs = batch_crystal_directions(recip_lattices, normal=surf_normal)
        rgb = batch_ipf_colors(crystal_dirs)
        return rgb_to_plotly_colors(rgb)

    elif color_by == "rodrigues":
        rod_vecs = batch_rodrigues(recip_lattices, lattice_params)
        rgb = batch_rodrigues_rgb(rod_vecs)
        return rgb_to_plotly_colors(rgb)

    elif color_by == "misorientation" and ref_grain_index is not None:
        orientations = batch_orientations(recip_lattices, lattice_params)
        ref_idx = int(ref_grain_index)
        if ref_idx < 0 or ref_idx >= len(orientations):
            # Invalid reference -- fall back to IPF
            crystal_dirs = batch_crystal_directions(recip_lattices, normal=surf_normal)
            rgb = batch_ipf_colors(crystal_dirs)
            return rgb_to_plotly_colors(rgb)

        result = misorientation_from_reference(orientations, ref_idx)
        rgb = batch_rodrigues_rgb(result["rodrigues"])
        return rgb_to_plotly_colors(rgb)

    elif color_by == "pole_hsv":
        rgb = _compute_pole_hsv_colors(
            recip_lattices,
            hkl=pole_hkl or (1, 0, 0),
            surface_normal=surf_normal,
            surface_roll=surf_roll,
            surface_tilt=surf_tilt,
            center_xy=pole_center_xy,
            color_rad_deg=pole_color_rad_deg,
        )
        return rgb_to_plotly_colors(rgb)

    else:
        # Fallback to IPF
        crystal_dirs = batch_crystal_directions(recip_lattices, normal=surf_normal)
        rgb = batch_ipf_colors(crystal_dirs)
        return rgb_to_plotly_colors(rgb)


def _compute_pole_hsv_colors(
    recip_lattices,
    hkl=(1, 0, 0),
    surface_normal=None,
    surface_roll=None,
    surface_tilt=None,
    center_xy=None,
    color_rad_deg=22.5,
):
    """
    Compute per-grain HSV pole-figure colors for the orientation map.

    Replicates the same algorithm used by ``make_pole_figure`` in
    ``stereo_plot.py`` (and LaueGo's ``MakePolePoints`` + ``poleXY2rgb``):
    for each grain, find the closest symmetry-equivalent pole to the center
    ``(x0, y0)`` on the stereographic projection, then map the displacement
    ``(dx, dy)`` to an HSV color wheel.  Center = white, edge = fully
    saturated.

    Parameters
    ----------
    recip_lattices : ndarray (N, 3, 3)
        Per-grain reciprocal lattice matrices.
    hkl : tuple of int
        Miller indices for the pole family (e.g. ``(1, 0, 0)``).
    surface_normal, surface_roll, surface_tilt : ndarray (3,), optional
        Surface frame vectors.  Defaults to 34ID-E normal surface.
    center_xy : tuple of float, optional
        ``(x0, y0)`` center for the HSV color wheel on the pole figure.
    color_rad_deg : float
        Angular color-saturation radius in degrees.

    Returns
    -------
    ndarray (N, 3)
        RGB values in [0, 1] per grain.
    """
    N_grains = len(recip_lattices)

    if center_xy is not None:
        x0, y0 = float(center_xy[0]), float(center_xy[1])
    else:
        x0, y0 = 0.0, 0.0

    rmax = pole_figure_color_radius(x0, y0, color_rad_deg)

    # Generate the hkl family and compute pole figure points
    family = cubic_hkl_family(*hkl)

    kwargs = {}
    if surface_normal is not None:
        kwargs["surface_normal"] = surface_normal
    if surface_roll is not None:
        kwargs["surface_roll"] = surface_roll
    if surface_tilt is not None:
        kwargs["surface_tilt"] = surface_tilt

    points, grain_indices = pole_figure_points(recip_lattices, family, **kwargs)

    # Filter out NaN/inf points
    if len(points) > 0:
        finite_mask = np.all(np.isfinite(points), axis=1)
        points = points[finite_mask]
        grain_indices = grain_indices[finite_mask]

    # Compute per-grain HSV color from closest pole to center
    grain_rgb = np.ones((N_grains, 3))  # default white

    for grain_idx in range(N_grains):
        mask = grain_indices == grain_idx
        if not np.any(mask):
            continue
        grain_pts = points[mask]
        dists = np.sum((grain_pts - np.array([x0, y0])) ** 2, axis=1)
        closest = np.argmin(dists)
        dx = grain_pts[closest, 0] - x0
        dy = grain_pts[closest, 1] - y0
        grain_rgb[grain_idx] = hsv_wheel_color(dx, dy, rmax=rmax)

    return grain_rgb


# ---------------------------------------------------------------------------
# Cross-plot selection highlighting (Stage 3)
# ---------------------------------------------------------------------------


def apply_selection_highlight(
    fig,
    parsed,
    selected_grains,
    marker_size,
    is_3d=False,
    x_axis="auto",
    y_axis="auto",
    z_axis="Z",
):
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
    x_axis, y_axis, z_axis : str
        Axis selections, must match what was passed to the figure builder
        so the highlight ring lands on the correct points.  ``z_axis`` is
        only used in 3-D mode.
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
        np.isin(np.arange(n_points), list(selected_set)),
        1.0,
        0.2,
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
                new_colors.append(c.replace("rgb(", "rgba(").replace(")", f",{opacity_arr[i]:.2f})"))
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
                new_colors.append(c.replace("rgb(", "rgba(").replace(")", f",{opacity_arr[i]:.2f})"))
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
        x_vals_3d, _ = _resolve_axis(parsed, x_axis or "X")
        y_vals_3d, _ = _resolve_axis(parsed, y_axis or "Y")
        z_vals_3d, _ = _resolve_axis(parsed, z_axis or "Z")
        fig.add_trace(
            go.Scatter3d(
                x=np.asarray(x_vals_3d)[sel_mask],
                y=np.asarray(y_vals_3d)[sel_mask],
                z=np.asarray(z_vals_3d)[sel_mask],
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
            )
        )
    else:
        depths = parsed["depths"]
        has_depth = not np.all(np.isnan(depths))
        x_vals, y_vals, _, _ = _select_axes(positions, depths, has_depth, x_axis=x_axis, y_axis=y_axis, parsed=parsed)
        x_vals = np.asarray(x_vals)
        y_vals = np.asarray(y_vals)

        fig.add_trace(
            go.Scattergl(
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
            )
        )
