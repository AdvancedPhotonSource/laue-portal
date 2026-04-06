"""
Stereographic projection and pole figure Dash/Plotly components.

Renders:
- Q-vector stereographic projections with Wulff net overlay and hkl labels
- Pole figures with per-grain orientation coloring

Stereographic projection convention (matching Igor Pro):
- Q-vectors are projected relative to the **sample surface normal** as pole
- Lower hemisphere points (dot(q, normal) < 0) are **discarded** (not plotted)
- Projection formula: r = tan(delta/2) where delta = angle from pole

Styling matches Igor Pro's MakeStereo / Make_GraphPoles conventions.
"""

import logging

import numpy as np
import plotly.graph_objects as go

from laue_portal.analysis.projection import (
    stereographic_project,
    wulff_net_lines,
    pole_figure_points,
    cubic_hkl_family,
    zoom_axis_range,
    _DEFAULT_NORMAL,
    _DEFAULT_ROLL,
    _DEFAULT_TILT,
)
from laue_portal.analysis.orientation import (
    batch_orientations,
    batch_crystal_directions,
)
from laue_portal.analysis.coloring import (
    batch_ipf_colors,
    hsv_wheel_color,
    pole_figure_color_radius,
    rgb_to_plotly_colors,
)


logger = logging.getLogger(__name__)

_GRAY_BG = "rgb(156, 156, 156)"

# Unicode combining overline for negative Miller indices
_OVERLINE = "\u0305"


def _format_hkl(h, k, l):
    """Format Miller indices with overlines for negatives."""
    parts = []
    for idx in (h, k, l):
        if idx < 0:
            parts.append(f"{abs(idx)}{_OVERLINE}")
        else:
            parts.append(str(idx))
    return "".join(parts)


def _project_q_to_surface(q_vectors):
    """
    Project Q-vectors onto a stereographic plane using the sample surface
    normal as the pole.  Matches Igor Pro's convention.

    Only upper-hemisphere points (dot(q, normal) >= 0) are kept.
    Lower-hemisphere points are discarded.

    Parameters
    ----------
    q_vectors : ndarray (M, 3)
        Q-vectors (unit or non-unit; will be normalized).

    Returns
    -------
    sx, sy : ndarray -- projected coordinates (only upper-hemisphere points)
    labels_mask : ndarray (M,) bool -- True for kept points
    """
    normal = _DEFAULT_NORMAL
    roll = _DEFAULT_ROLL
    tilt = _DEFAULT_TILT

    M = len(q_vectors)
    sx_all = np.full(M, np.nan)
    sy_all = np.full(M, np.nan)
    keep = np.zeros(M, dtype=bool)

    for i in range(M):
        q = q_vectors[i]
        qnorm = np.linalg.norm(q)
        if qnorm < 1e-12:
            continue
        q = q / qnorm

        dot_normal = np.dot(q, normal)

        # Discard lower hemisphere (matching Igor Pro)
        if dot_normal < 0:
            continue

        keep[i] = True

        # Stereographic projection: r = sin(theta) / (1 + cos(theta))
        # where theta = angle from normal, cos(theta) = dot_normal
        sin_theta = np.sqrt(max(0, 1.0 - dot_normal**2))
        denom = 1.0 + dot_normal
        r = sin_theta / denom if denom > 1e-12 else 0.0

        # Project to 2D using tilt/roll basis
        x_comp = np.dot(q, tilt)
        y_comp = np.dot(q, roll)
        phi = np.arctan2(y_comp, x_comp)

        sx_all[i] = r * np.cos(phi)
        sy_all[i] = r * np.sin(phi)

    return sx_all[keep], sy_all[keep], keep


# ===================================================================
# Stereographic Projection Plot (Q-vectors)
# ===================================================================

def make_stereo_plot(
    parsed,
    step_index=None,
    zoom_deg=90,
    show_wulff=True,
    wulff_step_deg=10,
    marker_size=6,
):
    """
    Create a stereographic projection plot of Q-vectors.

    Projects Q-vectors relative to the sample surface normal.
    Only upper-hemisphere points are shown (matching Igor Pro convention).

    Parameters
    ----------
    parsed : dict
        Output from xml_parser.parse_indexing_xml().
    step_index : int, optional
        Which step to show. None = all steps.
    zoom_deg : float
        Zoom angle in degrees (5-90).
    show_wulff : bool
        Whether to show Wulff net overlay.
    wulff_step_deg : int
        Angular step for Wulff net lines.
    marker_size : int
        Marker size in pixels.

    Returns
    -------
    go.Figure
    """
    from laue_portal.analysis.xml_parser import get_step_peaks

    fig = go.Figure()

    # Collect Q-vectors and hkl labels across steps
    all_sx, all_sy = [], []
    all_labels = []

    if step_index is not None:
        step_indices = [step_index]
    else:
        step_indices = range(len(parsed["positions"]))

    for si in step_indices:
        step_data = get_step_peaks(parsed, si)
        if step_data is None or step_data["q_vectors"] is None:
            continue

        q_vecs = step_data["q_vectors"]
        if len(q_vecs) == 0:
            continue

        # Build hkl labels from patterns
        hkl_map = {}  # peak_index -> (h, k, l)
        for pat in step_data.get("patterns", []):
            if pat.get("hkl") is not None and pat.get("peak_indices") is not None:
                for j, pk_idx in enumerate(pat["peak_indices"]):
                    if pk_idx < len(q_vecs):
                        hkl_map[int(pk_idx)] = tuple(pat["hkl"][j].astype(int))

        # Project using surface normal as pole
        sx, sy, keep = _project_q_to_surface(q_vecs)

        all_sx.extend(sx)
        all_sy.extend(sy)

        # Only include labels for kept points
        kept_indices = np.where(keep)[0]
        for pk_idx in kept_indices:
            if pk_idx in hkl_map:
                h, k, l = hkl_map[pk_idx]
                all_labels.append(_format_hkl(h, k, l))
            else:
                all_labels.append("")

    if len(all_sx) > 0:
        all_sx = np.array(all_sx)
        all_sy = np.array(all_sy)

        # Show hkl text labels only for single-step view (too cluttered for all)
        use_text = step_index is not None and len(all_sx) < 50

        fig.add_trace(go.Scattergl(
            x=all_sx,
            y=all_sy,
            mode="markers+text" if use_text else "markers",
            marker=dict(
                size=marker_size,
                color="rgb(214, 20, 0)",  # Igor peak marker color
                symbol="circle",
                line=dict(width=0),
            ),
            text=all_labels if use_text else None,
            textposition="top center" if use_text else None,
            textfont=dict(size=9) if use_text else None,
            hovertemplate=(
                "x: %{x:.4f}<br>y: %{y:.4f}<br>"
                "%{text}<br><extra></extra>"
            ) if use_text else (
                "x: %{x:.4f}<br>y: %{y:.4f}<br>"
                "<extra></extra>"
            ),
            name=f"Q-vectors ({len(all_sx)} pts)",
            uid="stereo-qvectors",
        ))

    # Wulff net overlay
    if show_wulff:
        wulff = wulff_net_lines(step_deg=wulff_step_deg)
        for line in wulff:
            w = line["weight"]
            if w >= 0.9:
                color = "black"
                opacity = 1.0
                width = 1.0
            elif w >= 0.2:
                color = "gray"
                opacity = 0.3
                width = 0.5
            else:
                color = "lightgray"
                opacity = 0.09
                width = 0.3

            fig.add_trace(go.Scattergl(
                x=line["x"],
                y=line["y"],
                mode="lines",
                line=dict(color=color, width=width),
                opacity=opacity,
                showlegend=False,
                hoverinfo="skip",
            ))

    # Unit circle boundary
    theta = np.linspace(0, 2 * np.pi, 200)
    d = zoom_axis_range(zoom_deg)
    fig.add_trace(go.Scattergl(
        x=d * np.cos(theta),
        y=d * np.sin(theta),
        mode="lines",
        line=dict(color="black", width=1, dash="dash"),
        showlegend=False,
        hoverinfo="skip",
    ))

    fig.update_layout(
        xaxis=dict(
            range=[-d * 1.05, d * 1.05],
            scaleanchor="y",
            scaleratio=1,
            showgrid=False,
            zeroline=False,
        ),
        yaxis=dict(
            range=[-d * 1.05, d * 1.05],
            showgrid=False,
            zeroline=False,
        ),
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=40, r=40, t=40, b=40),
        autosize=True,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        uirevision=f"stereo-{zoom_deg}",
    )

    return fig


# ===================================================================
# Pole Figure Plot
# ===================================================================

def make_pole_figure(
    parsed,
    hkl=(1, 0, 0),
    color_scheme="hsv_position",
    color_rad_deg=22.5,
    marker_size=5,
    surface="normal",
):
    """
    Create a pole figure scatter plot.

    Projects crystal pole directions relative to the sample surface normal.
    Only upper-hemisphere points are shown (matching Igor Pro convention).

    Color schemes:
        ``"hsv_position"`` (default): LaueGo-style HSV position coloring.
            Each grain's color is determined by the XY position of its
            closest pole to the center, using a HSV color wheel.  Center =
            white, edge = fully saturated.  Matches LaueGo's
            ``MakePolePoints`` + ``poleXY2rgb``.
        ``"ipf"``: Cubic IPF standard triangle coloring (crystal direction
            along surface normal).  This is LaueGo's *orientation map*
            coloring, not its pole figure coloring.
        ``"uniform"``: Uniform red.

    Parameters
    ----------
    parsed : dict
        Output from xml_parser.parse_indexing_xml().
    hkl : tuple of int
        Miller indices for the pole family (e.g., (1,0,0), (1,1,0), (1,1,1)).
    color_scheme : str
        ``"hsv_position"`` (default), ``"ipf"``, or ``"uniform"``.
    color_rad_deg : float
        Angular radius (degrees) at which HSV colors reach full saturation.
        Default 22.5, matching LaueGo. Only used with ``"hsv_position"``.
    marker_size : int
        Marker size in pixels.
    surface : str
        Surface direction name for the projection.  One of ``"normal"``
        (default 34ID-E), ``"X"``, ``"H"``, ``"Y"``, ``"Z"``.

    Returns
    -------
    go.Figure
    """
    from laue_portal.analysis.projection import get_surface_vectors

    recip_lattices = parsed["recip_lattices"]
    lattice_params = parsed["lattice_params"]

    # Warn if lattice angles are not all 90 deg (non-cubic crystal).
    # cubic_hkl_family() uses brute-force permutation + sign enumeration
    # which is only correct for cubic symmetry.
    if len(lattice_params) >= 6:
        alpha, beta, gamma = lattice_params[3], lattice_params[4], lattice_params[5]
        _ANG_TOL = 0.5  # degrees
        if (abs(alpha - 90.0) > _ANG_TOL
                or abs(beta - 90.0) > _ANG_TOL
                or abs(gamma - 90.0) > _ANG_TOL):
            logger.warning(
                "Non-cubic lattice detected (alpha=%.1f, beta=%.1f, "
                "gamma=%.1f deg). Pole family generation via "
                "cubic_hkl_family() may be inaccurate for non-cubic "
                "crystal systems.",
                alpha, beta, gamma,
            )

    # Look up surface vectors
    surf_normal, surf_roll, surf_tilt = get_surface_vectors(surface)

    # Compute orientation matrices (NaN recip lattices -> identity)
    orientations = batch_orientations(recip_lattices, lattice_params)

    # Generate hkl family
    family = cubic_hkl_family(*hkl)

    # Compute pole figure points using the selected surface
    points, grain_indices = pole_figure_points(
        orientations, family,
        surface_normal=surf_normal,
        surface_roll=surf_roll,
        surface_tilt=surf_tilt,
    )

    # Filter out NaN points (from grains with no indexing data)
    if len(points) > 0:
        finite_mask = np.all(np.isfinite(points), axis=1)
        points = points[finite_mask]
        grain_indices = grain_indices[finite_mask]

    # Compute colors
    if color_scheme == "hsv_position" and len(points) > 0:
        # LaueGo-style HSV position coloring (MakePolePoints + poleXY2rgb)
        x0, y0 = 0.0, 0.0  # center (cursor not applicable in web UI)
        rmax = pole_figure_color_radius(x0, y0, color_rad_deg)

        N_grains = len(recip_lattices)
        grain_rgb = np.ones((N_grains, 3))  # default white

        for grain_idx in range(N_grains):
            mask = grain_indices == grain_idx
            if not np.any(mask):
                continue
            grain_pts = points[mask]
            dists = np.sum((grain_pts - np.array([x0, y0]))**2, axis=1)
            closest = np.argmin(dists)
            dx = grain_pts[closest, 0] - x0
            dy = grain_pts[closest, 1] - y0
            grain_rgb[grain_idx] = hsv_wheel_color(dx, dy, rmax=rmax)

        point_colors = rgb_to_plotly_colors(grain_rgb[grain_indices])

    elif color_scheme == "ipf" and len(points) > 0:
        crystal_dirs = batch_crystal_directions(
            recip_lattices, normal=surf_normal,
        )
        ipf_rgb = batch_ipf_colors(crystal_dirs)

        # Map grain colors to pole points
        point_colors = rgb_to_plotly_colors(ipf_rgb[grain_indices])
    else:
        point_colors = "rgb(214, 20, 0)"

    fig = go.Figure()

    if len(points) > 0:
        fig.add_trace(go.Scattergl(
            x=points[:, 0],
            y=points[:, 1],
            mode="markers",
            marker=dict(
                size=marker_size,
                color=point_colors,
                symbol="circle",
                line=dict(width=0),
            ),
            customdata=grain_indices.reshape(-1, 1),
            hovertemplate=(
                "x: %{x:.4f}<br>y: %{y:.4f}<br>"
                "Grain: %{customdata[0]}<br>"
                "<extra></extra>"
            ),
            name=f"{{{_format_hkl(*hkl)}}} ({len(points)} pts)",
            uid="pole-figure-data",
        ))

    # Color saturation circle overlay (HSV position mode only)
    if color_scheme == "hsv_position" and len(points) > 0:
        x0, y0 = 0.0, 0.0
        rmax = pole_figure_color_radius(x0, y0, color_rad_deg)
        theta_circle = np.linspace(0, 2 * np.pi, 100)
        fig.add_trace(go.Scattergl(
            x=x0 + rmax * np.cos(theta_circle),
            y=y0 + rmax * np.sin(theta_circle),
            mode="lines",
            line=dict(color="black", width=1, dash="dot"),
            showlegend=False,
            hoverinfo="skip",
        ))

    # Unit circle boundary
    theta = np.linspace(0, 2 * np.pi, 200)
    fig.add_trace(go.Scattergl(
        x=np.cos(theta),
        y=np.sin(theta),
        mode="lines",
        line=dict(color="black", width=1, dash="dash"),
        showlegend=False,
        hoverinfo="skip",
    ))

    fig.update_layout(
        xaxis=dict(
            range=[-1.1, 1.1],
            scaleanchor="y",
            scaleratio=1,
            showgrid=False,
            zeroline=False,
            title="",
        ),
        yaxis=dict(
            range=[-1.1, 1.1],
            showgrid=False,
            zeroline=False,
            title="",
        ),
        plot_bgcolor=_GRAY_BG,
        paper_bgcolor="white",
        margin=dict(l=40, r=40, t=40, b=40),
        autosize=True,
        title=f"Pole Figure: {{{_format_hkl(*hkl)}}}",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        dragmode="lasso",  # enable lasso select for ROI picking (Stage 3)
        uirevision="pole-figure",
    )

    return fig
