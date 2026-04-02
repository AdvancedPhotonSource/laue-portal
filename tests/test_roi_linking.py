"""
Tests for ROI picking, cross-plot linking, and misorientation calculations.

Tests the end-to-end flow from pole figure lasso selection to orientation/quality
map highlighting and pairwise misorientation statistics.
"""

import os
import sys

import numpy as np
import pytest

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from laue_portal.analysis.xml_parser import parse_indexing_xml
from laue_portal.analysis.orientation import (
    batch_orientations,
    pairwise_misorientation,
    misorientation_angle,
    CUBIC_SYMMETRY_OPS,
)
from laue_portal.components.visualization.orientation_map import (
    make_orientation_map,
    make_orientation_map_3d,
    apply_selection_highlight,
)
from laue_portal.components.visualization.quality_map import (
    make_quality_map,
    make_quality_map_3d,
)
from laue_portal.components.visualization.stereo_plot import make_pole_figure

FIXTURE_XML = os.path.join(os.path.dirname(__file__), "fixtures", "test_indexing.xml")


def _parsed():
    return parse_indexing_xml(FIXTURE_XML)


# ---------------------------------------------------------------------------
# Pole figure provides grain indices in customdata for lasso selection
# ---------------------------------------------------------------------------

class TestPoleFigureCustomdata:

    def test_customdata_contains_grain_indices(self):
        """Pole figure scatter trace should have grain_indices in customdata."""
        fig = make_pole_figure(_parsed(), hkl=(1, 0, 0))
        # First trace is the scatter data (second is unit circle)
        data_trace = fig.data[0]
        assert data_trace.customdata is not None
        assert len(data_trace.customdata) > 0

    def test_grain_indices_are_integers(self):
        """Grain indices in customdata should be integer-valued."""
        fig = make_pole_figure(_parsed(), hkl=(1, 0, 0))
        grain_ids = fig.data[0].customdata[:, 0]
        for gid in grain_ids:
            assert float(gid) == int(gid)

    def test_grain_indices_within_bounds(self):
        """Grain indices should be valid step indices."""
        parsed = _parsed()
        n_steps = len(parsed["positions"])
        fig = make_pole_figure(parsed, hkl=(1, 0, 0))
        grain_ids = fig.data[0].customdata[:, 0]
        assert np.all(grain_ids >= 0)
        assert np.all(grain_ids < n_steps)

    def test_dragmode_is_lasso(self):
        """Pole figure should have lasso dragmode for ROI picking."""
        fig = make_pole_figure(_parsed(), hkl=(1, 0, 0))
        assert fig.layout.dragmode == "lasso"


# ---------------------------------------------------------------------------
# Cross-plot highlighting on orientation map
# ---------------------------------------------------------------------------

class TestOrientationMapHighlighting:

    def test_no_highlight_without_selection(self):
        """Without selection, orientation map should have 1 trace."""
        fig = make_orientation_map(_parsed(), color_by="cubic_ipf")
        assert len(fig.data) == 1

    def test_highlight_adds_trace(self):
        """apply_selection_highlight should add a highlight trace."""
        parsed = _parsed()
        fig = make_orientation_map(parsed, color_by="cubic_ipf")
        apply_selection_highlight(fig, parsed, [0, 1], marker_size=40)
        assert len(fig.data) == 2
        assert "Selected" in fig.data[1].name

    def test_highlight_trace_marker_is_open_circle(self):
        """Highlight trace should use open circles."""
        parsed = _parsed()
        fig = make_orientation_map(parsed, color_by="cubic_ipf")
        apply_selection_highlight(fig, parsed, [0], marker_size=40)
        assert fig.data[1].marker.symbol == "circle-open"

    def test_highlight_trace_count_matches_selection(self):
        """Highlight trace should have points only for selected grains."""
        parsed = _parsed()
        selected = [0, 1]

        fig = make_orientation_map(parsed, color_by="cubic_ipf")
        apply_selection_highlight(fig, parsed, selected, marker_size=40)

        # Highlight trace should have exactly len(selected) points
        assert len(fig.data[1].x) == len(selected)

    def test_main_trace_dimmed_with_rgb_colors(self):
        """When IPF colors are used, main trace should switch to rgba with opacity."""
        parsed = _parsed()
        fig = make_orientation_map(parsed, color_by="cubic_ipf")
        apply_selection_highlight(fig, parsed, [0], marker_size=40)

        colors = fig.data[0].marker.color
        # Unselected points should have rgba with low opacity
        # (point 1 is not selected)
        if len(colors) > 1:
            assert "rgba(" in colors[1]
            assert ",0.20)" in colors[1]

    def test_selected_point_full_opacity(self):
        """Selected points should keep full opacity in rgba."""
        parsed = _parsed()
        fig = make_orientation_map(parsed, color_by="cubic_ipf")
        apply_selection_highlight(fig, parsed, [0], marker_size=40)

        colors = fig.data[0].marker.color
        # Point 0 is selected, should have opacity 1.0
        assert "rgba(" in colors[0]
        assert ",1.00)" in colors[0]

    def test_scalar_mode_converted_to_rgba(self):
        """For scalar coloring, colors should be converted to per-point RGBA
        with 0.2 opacity for unselected points."""
        parsed = _parsed()
        fig = make_orientation_map(parsed, color_by="n_indexed")
        apply_selection_highlight(fig, parsed, [0], marker_size=40)
        colors = fig.data[0].marker.color
        # Should now be per-point RGBA strings instead of scalar array
        assert isinstance(colors, (list, tuple))
        assert all("rgba(" in c for c in colors)
        # Unselected point (index 1) should have low opacity
        assert ",0.20)" in colors[1]
        # Selected point (index 0) should have full opacity
        assert ",1.00)" in colors[0]

    def test_empty_selection_no_highlight(self):
        """Empty selection should not add any highlight trace."""
        parsed = _parsed()
        fig = make_orientation_map(parsed, color_by="cubic_ipf")
        apply_selection_highlight(fig, parsed, [], marker_size=40)
        # No highlight should be added for empty selection
        assert len(fig.data) == 1


# ---------------------------------------------------------------------------
# Cross-plot highlighting on quality map
# ---------------------------------------------------------------------------

class TestQualityMapHighlighting:

    def test_highlight_adds_trace(self):
        parsed = _parsed()
        fig = make_quality_map(parsed, metric="goodness")
        apply_selection_highlight(fig, parsed, [0, 1], marker_size=40)
        assert len(fig.data) == 2
        assert "Selected" in fig.data[1].name

    def test_highlight_on_3d_quality(self):
        parsed = _parsed()
        fig = make_quality_map_3d(parsed, metric="goodness")
        apply_selection_highlight(fig, parsed, [0], marker_size=40, is_3d=True)
        assert len(fig.data) == 2
        # 3D highlight should use scatter3d
        assert fig.data[1].type == "scatter3d"


# ---------------------------------------------------------------------------
# 3D orientation map highlighting
# ---------------------------------------------------------------------------

class TestOrientationMap3DHighlighting:

    def test_3d_highlight_adds_scatter3d(self):
        parsed = _parsed()
        fig = make_orientation_map_3d(parsed, color_by="cubic_ipf")
        apply_selection_highlight(fig, parsed, [0], marker_size=40, is_3d=True)
        assert len(fig.data) == 2
        assert fig.data[1].type == "scatter3d"


# ---------------------------------------------------------------------------
# Misorientation with real XML data
# ---------------------------------------------------------------------------

class TestMisorientationWithFixture:

    def test_pairwise_on_fixture_data(self):
        """Pairwise misorientation should work on fixture data."""
        parsed = _parsed()
        orientations = batch_orientations(
            parsed["recip_lattices"], parsed["lattice_params"],
        )
        result = pairwise_misorientation(orientations, symmetry_reduce=True)
        assert "angles" in result
        assert len(result["angles"]) > 0
        # All angles should be non-negative
        assert np.all(result["angles"] >= 0)

    def test_subset_misorientation(self):
        """Subset misorientation should produce fewer pairs."""
        parsed = _parsed()
        orientations = batch_orientations(
            parsed["recip_lattices"], parsed["lattice_params"],
        )
        full = pairwise_misorientation(orientations)
        sub = pairwise_misorientation(orientations, indices=[0, 1])
        assert len(sub["angles"]) <= len(full["angles"])

    def test_self_misorientation_zero(self):
        """Misorientation of a grain with itself should be 0."""
        parsed = _parsed()
        orientations = batch_orientations(
            parsed["recip_lattices"], parsed["lattice_params"],
        )
        angle = misorientation_angle(orientations[0], orientations[0])
        assert abs(angle) < 1e-5
