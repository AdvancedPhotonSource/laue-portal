"""Pole figure Dash/Plotly components."""

import logging

import numpy as np
import plotly.graph_objects as go

from laue_portal.analysis.coloring import (
    batch_ipf_colors,
    hsv_wheel_color,
    pole_figure_color_radius,
    rgb_to_plotly_colors,
)
from laue_portal.analysis.orientation import (
    batch_crystal_directions,
)
from laue_portal.analysis.projection import (
    cubic_hkl_family,
    pole_figure_points,
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
    center_xy=None,
    surface_vectors=None,
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
    center_xy : tuple of float, optional
        ``(x0, y0)`` center for HSV position coloring.  Default ``(0, 0)``.
        When a user clicks a point on the pole figure, pass its
        stereographic coordinates here to recenter the HSV color wheel
        (matching Igor Pro's cursor-based ``MakePolePoints``).

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
        if abs(alpha - 90.0) > _ANG_TOL or abs(beta - 90.0) > _ANG_TOL or abs(gamma - 90.0) > _ANG_TOL:
            logger.warning(
                "Non-cubic lattice detected (alpha=%.1f, beta=%.1f, "
                "gamma=%.1f deg). Pole family generation via "
                "cubic_hkl_family() may be inaccurate for non-cubic "
                "crystal systems.",
                alpha,
                beta,
                gamma,
            )

    # Look up surface vectors
    if surface_vectors is None:
        surf_normal, surf_roll, surf_tilt = get_surface_vectors(surface)
    else:
        surf_normal, surf_roll, surf_tilt = surface_vectors

    # Generate hkl family
    family = cubic_hkl_family(*hkl)

    # Compute pole figure points using the measured reciprocal lattices
    # directly (matching Igor Pro's MakePolePoints: q = gm * hkl).
    points, grain_indices = pole_figure_points(
        recip_lattices,
        family,
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
        if center_xy is not None:
            x0, y0 = float(center_xy[0]), float(center_xy[1])
        else:
            x0, y0 = 0.0, 0.0
        rmax = pole_figure_color_radius(x0, y0, color_rad_deg)

        N_grains = len(recip_lattices)
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

        point_colors = rgb_to_plotly_colors(grain_rgb[grain_indices])

    elif color_scheme == "ipf" and len(points) > 0:
        crystal_dirs = batch_crystal_directions(
            recip_lattices,
            normal=surf_normal,
        )
        ipf_rgb = batch_ipf_colors(crystal_dirs)

        # Map grain colors to pole points
        point_colors = rgb_to_plotly_colors(ipf_rgb[grain_indices])
    else:
        point_colors = "rgb(214, 20, 0)"

    fig = go.Figure()

    if len(points) > 0:
        fig.add_trace(
            go.Scattergl(
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
                hovertemplate=("x: %{x:.4f}<br>y: %{y:.4f}<br>Grain: %{customdata[0]}<br><extra></extra>"),
                name=f"{{{_format_hkl(*hkl)}}} ({len(points)} pts)",
                uid="pole-figure-data",
            )
        )

    # Color saturation circle overlay (HSV position mode only)
    if color_scheme == "hsv_position" and len(points) > 0:
        if center_xy is not None:
            x0, y0 = float(center_xy[0]), float(center_xy[1])
        else:
            x0, y0 = 0.0, 0.0
        rmax = pole_figure_color_radius(x0, y0, color_rad_deg)
        theta_circle = np.linspace(0, 2 * np.pi, 100)
        fig.add_trace(
            go.Scattergl(
                x=x0 + rmax * np.cos(theta_circle),
                y=y0 + rmax * np.sin(theta_circle),
                mode="lines",
                line=dict(color="black", width=1, dash="dot"),
                showlegend=False,
                hoverinfo="skip",
            )
        )

    # Unit circle boundary
    theta = np.linspace(0, 2 * np.pi, 200)
    fig.add_trace(
        go.Scattergl(
            x=np.cos(theta),
            y=np.sin(theta),
            mode="lines",
            line=dict(color="black", width=1, dash="dash"),
            showlegend=False,
            hoverinfo="skip",
        )
    )

    # Crosshair (+) at the global pole-figure center (origin), matching the
    # style/size of the selected-point crosshair below.
    _origin_arm = pole_figure_color_radius(0.0, 0.0, color_rad_deg) * 0.1
    fig.add_trace(
        go.Scattergl(
            x=[-_origin_arm, _origin_arm],
            y=[0.0, 0.0],
            mode="lines",
            line=dict(color="black", width=2),
            showlegend=False,
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scattergl(
            x=[0.0, 0.0],
            y=[-_origin_arm, _origin_arm],
            mode="lines",
            line=dict(color="black", width=2),
            showlegend=False,
            hoverinfo="skip",
        )
    )

    # Crosshair (+) on the selected reference point, scaled to color radius
    if center_xy is not None:
        cx, cy = float(center_xy[0]), float(center_xy[1])
        rmax = pole_figure_color_radius(cx, cy, color_rad_deg)
        arm = rmax * 0.1  # 10% of color radius
        # Horizontal bar
        fig.add_trace(
            go.Scattergl(
                x=[cx - arm, cx + arm],
                y=[cy, cy],
                mode="lines",
                line=dict(color="black", width=2),
                showlegend=False,
                hoverinfo="skip",
            )
        )
        # Vertical bar
        fig.add_trace(
            go.Scattergl(
                x=[cx, cx],
                y=[cy - arm, cy + arm],
                mode="lines",
                line=dict(color="black", width=2),
                showlegend=False,
                hoverinfo="skip",
            )
        )

    fig.update_layout(
        xaxis=dict(
            range=[-1.1, 1.1],
            scaleanchor="y",
            scaleratio=1,
            showgrid=False,
            zeroline=False,
            title="",
            uirevision="pole-figure-x",
        ),
        yaxis=dict(
            range=[-1.1, 1.1],
            showgrid=False,
            zeroline=False,
            title="",
            uirevision="pole-figure-y",
        ),
        plot_bgcolor=_GRAY_BG,
        paper_bgcolor="white",
        margin=dict(l=40, r=40, t=40, b=40),
        autosize=True,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        dragmode="lasso",  # enable lasso select for ROI picking (Stage 3)
        uirevision="pole-figure",
    )

    return fig
