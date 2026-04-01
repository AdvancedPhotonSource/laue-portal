"""
Tests for laue_portal.analysis.projection module.

Tests stereographic projection, Wulff net generation, pole figure
computation, and cubic hkl family generation.
"""

import os
import sys
import numpy as np
import pytest

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from laue_portal.analysis.projection import (
    stereographic_project,
    wulff_net_lines,
    pole_figure_points,
    cubic_hkl_family,
    zoom_axis_range,
    project_q_vectors,
)


# ---------------------------------------------------------------------------
# Stereographic Projection
# ---------------------------------------------------------------------------

class TestStereographicProject:

    def test_pole_projects_to_origin(self):
        """A vector along the pole should project to (0, 0)."""
        vectors = np.array([[0, 0, 1.0]])
        sx, sy, lower = stereographic_project(vectors)
        np.testing.assert_allclose(sx[0], 0.0, atol=1e-12)
        np.testing.assert_allclose(sy[0], 0.0, atol=1e-12)
        assert not lower[0]

    def test_equator_projects_to_unit_circle(self):
        """Vector on equator (90 deg from pole) -> r = tan(45) = 1."""
        vectors = np.array([[1, 0, 0.0]])
        sx, sy, lower = stereographic_project(vectors)
        r = np.sqrt(sx[0]**2 + sy[0]**2)
        np.testing.assert_allclose(r, 1.0, atol=1e-10)

    def test_lower_hemisphere_detected(self):
        """Vector in lower hemisphere should be flagged."""
        vectors = np.array([[0, 0, -1.0]])
        sx, sy, lower = stereographic_project(vectors)
        assert lower[0]

    def test_multiple_vectors(self):
        vectors = np.array([[0, 0, 1], [1, 0, 0], [0, 1, 0.0]])
        sx, sy, lower = stereographic_project(vectors)
        assert len(sx) == 3
        assert len(sy) == 3
        assert len(lower) == 3

    def test_45_deg_projects_to_tan_22_5(self):
        """Vector at 45 deg from pole -> r = tan(22.5 deg)."""
        angle = np.radians(45)
        vectors = np.array([[np.sin(angle), 0, np.cos(angle)]])
        sx, sy, lower = stereographic_project(vectors)
        r = np.sqrt(sx[0]**2 + sy[0]**2)
        expected = np.tan(angle / 2)
        np.testing.assert_allclose(r, expected, atol=1e-10)

    def test_custom_pole(self):
        """Projection with custom pole direction."""
        vectors = np.array([[1, 0, 0.0]])
        sx, sy, lower = stereographic_project(vectors, pole=np.array([1, 0, 0]))
        # Vector along pole -> origin
        np.testing.assert_allclose(sx[0], 0.0, atol=1e-10)
        np.testing.assert_allclose(sy[0], 0.0, atol=1e-10)

    def test_zero_vector_projects_to_origin(self):
        vectors = np.array([[0, 0, 0.0]])
        sx, sy, lower = stereographic_project(vectors)
        np.testing.assert_allclose(sx[0], 0.0, atol=1e-12)
        np.testing.assert_allclose(sy[0], 0.0, atol=1e-12)


# ---------------------------------------------------------------------------
# Wulff Net
# ---------------------------------------------------------------------------

class TestWulffNet:

    def test_returns_list_of_dicts(self):
        lines = wulff_net_lines(step_deg=10)
        assert isinstance(lines, list)
        assert len(lines) > 0
        for line in lines:
            assert "x" in line
            assert "y" in line
            assert "weight" in line

    def test_line_weights_valid(self):
        lines = wulff_net_lines(step_deg=10)
        for line in lines:
            assert line["weight"] in (1.0, 0.3, 0.09)

    def test_different_step_sizes(self):
        lines_10 = wulff_net_lines(step_deg=10)
        lines_20 = wulff_net_lines(step_deg=20)
        # Fewer lines with larger step
        assert len(lines_20) < len(lines_10)

    def test_coordinates_finite(self):
        """All projected coordinates should be finite (not inf/NaN except NaN gaps)."""
        lines = wulff_net_lines(step_deg=10)
        for line in lines:
            finite_x = line["x"][~np.isnan(line["x"])]
            finite_y = line["y"][~np.isnan(line["y"])]
            # Should have no inf values (large values near horizon are expected)
            assert np.all(np.isfinite(finite_x))
            assert np.all(np.isfinite(finite_y))

    def test_phi_rotation(self):
        """Rotation should change coordinates."""
        lines_0 = wulff_net_lines(step_deg=20, phi_rotation=0)
        lines_45 = wulff_net_lines(step_deg=20, phi_rotation=45)
        # At least one line should differ
        differs = False
        for l0, l45 in zip(lines_0, lines_45):
            if not np.allclose(l0["x"], l45["x"], atol=1e-6, equal_nan=True):
                differs = True
                break
        assert differs


# ---------------------------------------------------------------------------
# Cubic {hkl} Family
# ---------------------------------------------------------------------------

class TestCubicHklFamily:

    def test_100_gives_6_directions(self):
        family = cubic_hkl_family(1, 0, 0)
        assert len(family) == 6

    def test_110_gives_12_directions(self):
        family = cubic_hkl_family(1, 1, 0)
        assert len(family) == 12

    def test_111_gives_8_directions(self):
        family = cubic_hkl_family(1, 1, 1)
        assert len(family) == 8

    def test_210_gives_24_directions(self):
        family = cubic_hkl_family(2, 1, 0)
        assert len(family) == 24

    def test_321_gives_48_directions(self):
        family = cubic_hkl_family(3, 2, 1)
        assert len(family) == 48

    def test_directions_are_unit_vectors(self):
        family = cubic_hkl_family(1, 1, 0)
        for v in family:
            norm = np.linalg.norm(v)
            assert abs(norm - 1.0) < 1e-10

    def test_directions_are_unique(self):
        """All directions should be distinct (antipodal pairs are allowed)."""
        family = cubic_hkl_family(1, 1, 0)
        for i in range(len(family)):
            for j in range(i + 1, len(family)):
                # Exact duplicates (dot > 0.999) should not exist
                dot = np.dot(family[i], family[j])
                assert dot < 0.999

    def test_negative_input_same_as_positive(self):
        family_pos = cubic_hkl_family(1, 1, 0)
        family_neg = cubic_hkl_family(-1, -1, 0)
        assert len(family_pos) == len(family_neg)


# ---------------------------------------------------------------------------
# Pole Figure Points
# ---------------------------------------------------------------------------

class TestPoleFigurePoints:

    def test_returns_arrays(self):
        orientations = np.tile(np.eye(3), (3, 1, 1))
        family = cubic_hkl_family(1, 0, 0)
        points, indices = pole_figure_points(orientations, family)
        assert isinstance(points, np.ndarray)
        assert isinstance(indices, np.ndarray)

    def test_point_count(self):
        """N grains * M poles should give up to N*M points (some may overlap)."""
        N = 3
        orientations = np.tile(np.eye(3), (N, 1, 1))
        family = cubic_hkl_family(1, 0, 0)  # 6 directions
        points, indices = pole_figure_points(orientations, family)
        # Each grain contributes up to 6 poles, but some pairs are equivalent
        assert len(points) <= N * len(family)
        assert len(points) > 0

    def test_grain_indices_valid(self):
        N = 5
        orientations = np.tile(np.eye(3), (N, 1, 1))
        family = cubic_hkl_family(1, 0, 0)
        points, indices = pole_figure_points(orientations, family)
        assert np.all(indices >= 0)
        assert np.all(indices < N)

    def test_points_within_unit_circle(self):
        orientations = np.tile(np.eye(3), (3, 1, 1))
        family = cubic_hkl_family(1, 0, 0)
        points, indices = pole_figure_points(orientations, family)
        radii = np.sqrt(points[:, 0]**2 + points[:, 1]**2)
        assert np.all(radii <= 1.1)  # allow small numerical margin

    def test_empty_orientations(self):
        orientations = np.empty((0, 3, 3))
        family = cubic_hkl_family(1, 0, 0)
        points, indices = pole_figure_points(orientations, family)
        assert len(points) == 0
        assert len(indices) == 0


# ---------------------------------------------------------------------------
# Zoom helper
# ---------------------------------------------------------------------------

class TestZoomAxisRange:

    def test_90_degrees(self):
        d = zoom_axis_range(90)
        np.testing.assert_allclose(d, 1.0, atol=1e-6)

    def test_45_degrees(self):
        d = zoom_axis_range(45)
        expected = np.tan(np.radians(45) / 2)
        np.testing.assert_allclose(d, expected, atol=1e-10)

    def test_small_angle(self):
        d = zoom_axis_range(5)
        assert d > 0
        assert d < 0.1


# ---------------------------------------------------------------------------
# Q-vector projection
# ---------------------------------------------------------------------------

class TestProjectQVectors:

    def test_basic_projection(self):
        q_vecs = np.array([[0, 0, 1], [1, 0, 0], [0, 1, 0.0]])
        sx, sy, lower = project_q_vectors(q_vecs)
        assert len(sx) == 3

    def test_zero_q_vector(self):
        q_vecs = np.array([[0, 0, 0.0]])
        sx, sy, lower = project_q_vectors(q_vecs)
        np.testing.assert_allclose(sx[0], 0.0, atol=1e-12)
