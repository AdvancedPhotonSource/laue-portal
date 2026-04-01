"""
Tests for laue_portal.analysis.coloring module.

Tests cubic IPF coloring, Rodrigues RGB, HSV wheel, legend image
generation, and batch coloring utilities.
"""

import os
import sys
import numpy as np
import pytest

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from laue_portal.analysis.coloring import (
    cubic_ipf_color,
    rodrigues_rgb,
    hsv_wheel_color,
    make_cubic_ipf_triangle,
    make_color_hexagon,
    batch_ipf_colors,
    batch_rodrigues_rgb,
    rgb_to_plotly_colors,
)


# ---------------------------------------------------------------------------
# Cubic IPF coloring
# ---------------------------------------------------------------------------

class TestCubicIpfColor:

    def test_001_is_red(self):
        """(001) direction should map to red."""
        rgb = cubic_ipf_color([0, 0, 1])
        assert rgb[0] > 0.9  # R
        assert rgb[1] < 0.1  # G
        assert rgb[2] < 0.1  # B

    def test_011_is_green(self):
        """(011) direction should map to green."""
        rgb = cubic_ipf_color([0, 1, 1])
        assert rgb[0] < 0.1  # R
        assert rgb[1] > 0.9  # G
        assert rgb[2] < 0.1  # B

    def test_111_is_blue(self):
        """(111) direction should map to blue."""
        rgb = cubic_ipf_color([1, 1, 1])
        assert rgb[0] < 0.1  # R
        assert rgb[1] < 0.1  # G
        assert rgb[2] > 0.9  # B

    def test_returns_3_values(self):
        rgb = cubic_ipf_color([1, 2, 3])
        assert rgb.shape == (3,)

    def test_values_in_01_range(self):
        rgb = cubic_ipf_color([3, 1, 2])
        assert np.all(rgb >= 0)
        assert np.all(rgb <= 1)

    def test_zero_vector_is_black(self):
        rgb = cubic_ipf_color([0, 0, 0])
        np.testing.assert_allclose(rgb, [0, 0, 0])

    def test_nan_input_gives_nan(self):
        rgb = cubic_ipf_color([1, np.nan, 0])
        assert np.all(np.isnan(rgb))

    def test_negative_indices_same_as_positive(self):
        """Cubic symmetry: abs() folding."""
        rgb_pos = cubic_ipf_color([1, 2, 3])
        rgb_neg = cubic_ipf_color([-1, -2, -3])
        np.testing.assert_allclose(rgb_pos, rgb_neg, atol=1e-10)

    def test_permutation_invariance(self):
        """Cubic symmetry: sort() folding."""
        rgb_a = cubic_ipf_color([1, 2, 3])
        rgb_b = cubic_ipf_color([3, 1, 2])
        rgb_c = cubic_ipf_color([2, 3, 1])
        np.testing.assert_allclose(rgb_a, rgb_b, atol=1e-10)
        np.testing.assert_allclose(rgb_b, rgb_c, atol=1e-10)

    def test_batch_input(self):
        """Should handle (N, 3) input."""
        hkl = np.array([[0, 0, 1], [0, 1, 1], [1, 1, 1]])
        rgb = cubic_ipf_color(hkl)
        assert rgb.shape == (3, 3)

    def test_max_channel_is_one(self):
        """Saturation step ensures max channel = 1."""
        rgb = cubic_ipf_color([1, 2, 5])
        assert abs(np.max(rgb) - 1.0) < 1e-10


# ---------------------------------------------------------------------------
# Rodrigues RGB coloring
# ---------------------------------------------------------------------------

class TestRodriguesRgb:

    def test_zero_rotation_is_black(self):
        rgb = rodrigues_rgb([0, 0, 0])
        np.testing.assert_allclose(rgb, [0, 0, 0])

    def test_positive_x_is_red(self):
        """Rotation about +X should give red component."""
        rgb = rodrigues_rgb([1, 0, 0], max_angle_deg=90)
        assert rgb[0] > rgb[1]
        assert rgb[0] > rgb[2]

    def test_positive_y_is_green(self):
        """Rotation about +Y should give green component."""
        rgb = rodrigues_rgb([0, 1, 0], max_angle_deg=90)
        assert rgb[1] > rgb[0]
        assert rgb[1] > rgb[2]

    def test_positive_z_is_blue(self):
        """Rotation about +Z should give blue component."""
        rgb = rodrigues_rgb([0, 0, 1], max_angle_deg=90)
        assert rgb[2] > rgb[0]
        assert rgb[2] > rgb[1]

    def test_returns_3_values(self):
        rgb = rodrigues_rgb([0.1, 0.2, 0.3])
        assert rgb.shape == (3,)

    def test_values_in_01_range(self):
        rgb = rodrigues_rgb([0.5, -0.3, 0.7], max_angle_deg=45)
        assert np.all(rgb >= 0)
        assert np.all(rgb <= 1)

    def test_batch_input(self):
        vecs = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]])
        rgb = rodrigues_rgb(vecs, max_angle_deg=90)
        assert rgb.shape == (3, 3)


# ---------------------------------------------------------------------------
# HSV wheel coloring
# ---------------------------------------------------------------------------

class TestHsvWheelColor:

    def test_center_is_white(self):
        rgb = hsv_wheel_color(0.0, 0.0)
        np.testing.assert_allclose(rgb, [1, 1, 1])

    def test_positive_x_edge_is_red(self):
        """Hue=0 (along +x) should be red."""
        rgb = hsv_wheel_color(1.0, 0.0, rmax=1.0)
        assert rgb[0] > 0.9
        assert rgb[1] < 0.1

    def test_returns_3_values_scalar(self):
        rgb = hsv_wheel_color(0.5, 0.5)
        assert rgb.shape == (3,)

    def test_values_in_01_range(self):
        rgb = hsv_wheel_color(0.3, -0.7)
        assert np.all(rgb >= 0)
        assert np.all(rgb <= 1)

    def test_batch_input(self):
        dx = np.array([0, 1, 0])
        dy = np.array([0, 0, 1])
        rgb = hsv_wheel_color(dx, dy)
        assert rgb.shape == (3, 3)


# ---------------------------------------------------------------------------
# Legend image generation
# ---------------------------------------------------------------------------

class TestLegendImages:

    def test_ipf_triangle_shape(self):
        img = make_cubic_ipf_triangle(resolution=64)
        assert img.shape == (64, 64, 4)
        assert img.dtype == np.uint8

    def test_ipf_triangle_has_opaque_pixels(self):
        img = make_cubic_ipf_triangle(resolution=64)
        assert np.any(img[:, :, 3] == 255)

    def test_ipf_triangle_has_transparent_pixels(self):
        img = make_cubic_ipf_triangle(resolution=64)
        assert np.any(img[:, :, 3] == 0)

    def test_color_hexagon_shape(self):
        img = make_color_hexagon(resolution=64)
        assert img.shape == (64, 64, 4)
        assert img.dtype == np.uint8

    def test_color_hexagon_has_opaque_pixels(self):
        img = make_color_hexagon(resolution=64)
        assert np.any(img[:, :, 3] == 255)

    def test_color_hexagon_center_is_white(self):
        img = make_color_hexagon(resolution=64)
        cx = 31  # center pixel
        # Center should be white (255, 255, 255)
        assert img[cx, cx, 0] > 240
        assert img[cx, cx, 1] > 240
        assert img[cx, cx, 2] > 240


# ---------------------------------------------------------------------------
# Batch utilities
# ---------------------------------------------------------------------------

class TestBatchUtilities:

    def test_batch_ipf_colors_shape(self):
        dirs = np.array([[0, 0, 1], [0, 1, 1], [1, 1, 1], [1, 2, 3]])
        rgb = batch_ipf_colors(dirs)
        assert rgb.shape == (4, 3)

    def test_batch_ipf_nan_gives_gray(self):
        dirs = np.array([[np.nan, np.nan, np.nan]])
        rgb = batch_ipf_colors(dirs)
        np.testing.assert_allclose(rgb[0], [0.5, 0.5, 0.5])

    def test_batch_rodrigues_rgb_shape(self):
        vecs = np.array([[0, 0, 0], [0.1, 0.2, 0.3]])
        rgb = batch_rodrigues_rgb(vecs)
        assert rgb.shape == (2, 3)

    def test_rgb_to_plotly_colors_format(self):
        rgb = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
        colors = rgb_to_plotly_colors(rgb)
        assert len(colors) == 2
        assert colors[0] == "rgb(255,0,0)"
        assert colors[1] == "rgb(0,255,0)"

    def test_rgb_to_plotly_colors_clamps(self):
        rgb = np.array([[1.5, -0.1, 0.5]])
        colors = rgb_to_plotly_colors(rgb)
        assert colors[0] == "rgb(255,0,127)"
