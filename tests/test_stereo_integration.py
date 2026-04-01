"""
Integration tests for Stage 2 visualization components.

Tests stereo_plot and updated orientation_map with real XML fixture data.
"""

import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from laue_portal.analysis.xml_parser import parse_indexing_xml
from laue_portal.components.visualization.stereo_plot import (
    make_stereo_plot,
    make_pole_figure,
)
from laue_portal.components.visualization.orientation_map import (
    make_orientation_map,
    make_orientation_map_3d,
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
        marker.colorbar is not None
        and marker.colorbar.title is not None
        and marker.colorbar.title.text is not None
    )
    assert not has_colorbar_title


def test_orientation_map_scalar_has_colorbar():
    """Scalar modes SHOULD have a colorbar with a title."""
    fig = make_orientation_map(_parsed(), color_by="n_indexed")
    assert fig.data[0].marker.colorbar is not None
    assert fig.data[0].marker.colorbar.title.text is not None
