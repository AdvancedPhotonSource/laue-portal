"""
Integration tests for Stage 2 visualization components.

Tests stereo_plot and updated orientation_map with real XML fixture data.
"""

import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from laue_portal.analysis.xml_parser import parse_indexing_xml
from laue_portal.components.visualization.orientation_map import (
    make_orientation_map,
    make_orientation_map_3d,
)
from laue_portal.components.visualization.stereo_plot import (
    make_pole_figure,
    make_stereo_plot,
)

FIXTURE_XML = os.path.join(os.path.dirname(__file__), "fixtures", "test_indexing.xml")


def _parsed():
    return parse_indexing_xml(FIXTURE_XML)


# ---------------------------------------------------------------------------
# Stereo plot
# ---------------------------------------------------------------------------


def test_stereo_plot_creates_figure():
    fig = make_stereo_plot(_parsed())
    assert fig is not None
    # Should have at least the unit circle trace
    assert len(fig.data) >= 1


def test_stereo_plot_with_wulff_net():
    fig = make_stereo_plot(_parsed(), show_wulff=True, wulff_step_deg=10)
    # Wulff net adds many traces
    assert len(fig.data) > 3


def test_stereo_plot_without_wulff_net():
    fig = make_stereo_plot(_parsed(), show_wulff=False)
    # Fewer traces without Wulff net
    fig_with = make_stereo_plot(_parsed(), show_wulff=True)
    assert len(fig.data) < len(fig_with.data)


def test_stereo_plot_single_step():
    fig = make_stereo_plot(_parsed(), step_index=0)
    assert fig is not None


def test_stereo_plot_zoom():
    fig_90 = make_stereo_plot(_parsed(), zoom_deg=90)
    fig_45 = make_stereo_plot(_parsed(), zoom_deg=45)
    # Both should create valid figures
    assert fig_90 is not None
    assert fig_45 is not None


def test_stereo_plot_marker_size():
    fig = make_stereo_plot(_parsed(), marker_size=10)
    assert fig is not None


# ---------------------------------------------------------------------------
# Pole figure
# ---------------------------------------------------------------------------


def test_pole_figure_creates_figure():
    fig = make_pole_figure(_parsed(), hkl=(1, 0, 0))
    assert fig is not None
    assert len(fig.data) >= 1


def test_pole_figure_100():
    fig = make_pole_figure(_parsed(), hkl=(1, 0, 0))
    assert fig.layout.title.text is not None
    assert "100" in fig.layout.title.text


def test_pole_figure_110():
    fig = make_pole_figure(_parsed(), hkl=(1, 1, 0))
    assert fig is not None


def test_pole_figure_111():
    fig = make_pole_figure(_parsed(), hkl=(1, 1, 1))
    assert fig is not None


def test_pole_figure_gray_background():
    fig = make_pole_figure(_parsed(), hkl=(1, 0, 0))
    assert fig.layout.plot_bgcolor == "rgb(156, 156, 156)"


def test_pole_figure_aspect_ratio():
    fig = make_pole_figure(_parsed(), hkl=(1, 0, 0))
    assert fig.layout.xaxis.scaleanchor == "y"
    assert fig.layout.xaxis.scaleratio == 1


def test_pole_figure_lasso_dragmode():
    """Pole figures should have lasso dragmode for ROI picking."""
    fig = make_pole_figure(_parsed(), hkl=(1, 0, 0))
    assert fig.layout.dragmode == "lasso"


def test_pole_figure_default_hsv_position():
    """Default color scheme is now hsv_position (not ipf)."""
    fig = make_pole_figure(_parsed(), hkl=(1, 0, 0))
    # With hsv_position and data, there should be: data trace + color circle + unit circle
    assert len(fig.data) >= 2
    # Data trace should have per-point colors
    colors = fig.data[0].marker.color
    assert isinstance(colors, (list, tuple))
    assert colors[0].startswith("rgb(")


def test_pole_figure_hsv_has_color_circle():
    """HSV position mode should draw a dashed color saturation circle."""
    fig = make_pole_figure(_parsed(), hkl=(1, 0, 0), color_scheme="hsv_position")
    # Find a trace with dash="dot" (the color circle)
    dot_traces = [t for t in fig.data if hasattr(t, "line") and t.line and t.line.dash == "dot"]
    assert len(dot_traces) >= 1


def test_pole_figure_ipf_still_works():
    """IPF coloring should still work when explicitly requested."""
    fig = make_pole_figure(_parsed(), hkl=(1, 0, 0), color_scheme="ipf")
    assert fig is not None
    colors = fig.data[0].marker.color
    assert isinstance(colors, (list, tuple))
    assert colors[0].startswith("rgb(")


def test_pole_figure_uniform_color():
    """Uniform mode should give a single color string."""
    fig = make_pole_figure(_parsed(), hkl=(1, 0, 0), color_scheme="uniform")
    assert fig is not None
    colors = fig.data[0].marker.color
    assert isinstance(colors, str)


def test_pole_figure_surface_normal():
    """Different surface selections should produce figures."""
    for surface in ("normal", "X", "H", "Y", "Z"):
        fig = make_pole_figure(_parsed(), hkl=(1, 0, 0), surface=surface)
        assert fig is not None


def test_pole_figure_color_radius_custom():
    """Custom color radius should work."""
    fig = make_pole_figure(_parsed(), hkl=(1, 0, 0), color_scheme="hsv_position", color_rad_deg=45.0)
    assert fig is not None


# ---------------------------------------------------------------------------
# Updated orientation map with IPF/Rodrigues coloring
# ---------------------------------------------------------------------------


def test_orientation_map_cubic_ipf():
    fig = make_orientation_map(_parsed(), color_by="cubic_ipf")
    assert len(fig.data) == 1
    assert fig.data[0].type == "scattergl"
    # IPF colors are per-point RGB strings (Plotly may store as tuple or list)
    colors = fig.data[0].marker.color
    assert isinstance(colors, (list, tuple))
    assert colors[0].startswith("rgb(")


def test_orientation_map_rodrigues():
    fig = make_orientation_map(_parsed(), color_by="rodrigues")
    assert len(fig.data) == 1
    colors = fig.data[0].marker.color
    assert isinstance(colors, (list, tuple))


def test_orientation_map_3d_cubic_ipf():
    fig = make_orientation_map_3d(_parsed(), color_by="cubic_ipf")
    assert len(fig.data) == 1
    assert fig.data[0].type == "scatter3d"
    colors = fig.data[0].marker.color
    assert isinstance(colors, (list, tuple))


def test_orientation_map_scalar_modes_still_work():
    """Scalar modes should still work with a colorscale."""
    parsed = _parsed()
    for mode in ("n_indexed", "goodness", "rms_error", "n_patterns"):
        fig = make_orientation_map(parsed, color_by=mode)
        # Plotly expands "Viridis" string to a tuple of color stops
        assert fig.data[0].marker.colorscale is not None


def test_orientation_map_ipf_no_colorbar():
    """IPF/Rodrigues modes should NOT have a colorbar title."""
    fig = make_orientation_map(_parsed(), color_by="cubic_ipf")
    marker = fig.data[0].marker
    # When no colorbar is set, Plotly creates an empty object with no title
    has_colorbar_title = (
        marker.colorbar is not None and marker.colorbar.title is not None and marker.colorbar.title.text is not None
    )
    assert not has_colorbar_title


def test_orientation_map_scalar_has_colorbar():
    """Scalar modes SHOULD have a colorbar with a title."""
    fig = make_orientation_map(_parsed(), color_by="n_indexed")
    assert fig.data[0].marker.colorbar is not None
    assert fig.data[0].marker.colorbar.title.text is not None


# ---------------------------------------------------------------------------
# Orientation map surface normal selection (Fix 3)
# ---------------------------------------------------------------------------


def test_orientation_map_surface_normal():
    """Different surface selections should produce valid figures."""
    for surface in ("normal", "X", "H", "Y", "Z"):
        fig = make_orientation_map(_parsed(), color_by="cubic_ipf", surface=surface)
        assert fig is not None
        colors = fig.data[0].marker.color
        assert isinstance(colors, (list, tuple))
        assert colors[0].startswith("rgb(")


def test_orientation_map_3d_surface_normal():
    """3D orientation map should accept surface parameter."""
    for surface in ("normal", "X", "H", "Y", "Z"):
        fig = make_orientation_map_3d(_parsed(), color_by="cubic_ipf", surface=surface)
        assert fig is not None
        colors = fig.data[0].marker.color
        assert isinstance(colors, (list, tuple))
        assert colors[0].startswith("rgb(")


def test_orientation_map_surface_changes_ipf_colors():
    """Different surfaces should produce different IPF colors."""
    parsed = _parsed()
    fig_normal = make_orientation_map(parsed, color_by="cubic_ipf", surface="normal")
    fig_z = make_orientation_map(parsed, color_by="cubic_ipf", surface="Z")
    # At least some colors should differ between different surface normals
    colors_normal = fig_normal.data[0].marker.color
    colors_z = fig_z.data[0].marker.color
    assert colors_normal != colors_z


def test_orientation_map_surface_default_is_normal():
    """Default surface should be 'normal', producing same result as explicit."""
    parsed = _parsed()
    fig_default = make_orientation_map(parsed, color_by="cubic_ipf")
    fig_explicit = make_orientation_map(parsed, color_by="cubic_ipf", surface="normal")
    assert fig_default.data[0].marker.color == fig_explicit.data[0].marker.color


def test_orientation_map_surface_scalar_unaffected():
    """Scalar coloring modes should not be affected by surface selection."""
    parsed = _parsed()
    fig_normal = make_orientation_map(parsed, color_by="n_indexed", surface="normal")
    fig_z = make_orientation_map(parsed, color_by="n_indexed", surface="Z")
    # Scalar modes use the same color values regardless of surface
    import numpy as np

    np.testing.assert_array_equal(
        fig_normal.data[0].marker.color,
        fig_z.data[0].marker.color,
    )
