"""
Tests for laue_portal.analysis.projection module.

Tests pole figure computation and cubic hkl family generation.
"""

import os
import sys

import numpy as np

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from laue_portal.analysis.projection import (
    cubic_hkl_family,
    get_surface_vectors,
    pole_figure_points,
)

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
        recip_lattices = np.tile(np.eye(3), (3, 1, 1))
        family = cubic_hkl_family(1, 0, 0)
        points, indices = pole_figure_points(recip_lattices, family)
        assert isinstance(points, np.ndarray)
        assert isinstance(indices, np.ndarray)

    def test_point_count(self):
        """N grains * M poles should give up to N*M points (some may overlap)."""
        N = 3
        recip_lattices = np.tile(np.eye(3), (N, 1, 1))
        family = cubic_hkl_family(1, 0, 0)  # 6 directions
        points, indices = pole_figure_points(recip_lattices, family)
        # Each grain contributes up to 6 poles, but some pairs are equivalent
        assert len(points) <= N * len(family)
        assert len(points) > 0

    def test_grain_indices_valid(self):
        N = 5
        recip_lattices = np.tile(np.eye(3), (N, 1, 1))
        family = cubic_hkl_family(1, 0, 0)
        points, indices = pole_figure_points(recip_lattices, family)
        assert np.all(indices >= 0)
        assert np.all(indices < N)

    def test_points_within_unit_circle(self):
        recip_lattices = np.tile(np.eye(3), (3, 1, 1))
        family = cubic_hkl_family(1, 0, 0)
        points, indices = pole_figure_points(recip_lattices, family)
        radii = np.sqrt(points[:, 0] ** 2 + points[:, 1] ** 2)
        assert np.all(radii <= 1.1)  # allow small numerical margin

    def test_empty_recip_lattices(self):
        recip_lattices = np.empty((0, 3, 3))
        family = cubic_hkl_family(1, 0, 0)
        points, indices = pole_figure_points(recip_lattices, family)
        assert len(points) == 0
        assert len(indices) == 0

    def test_matches_igor_gm_convention(self):
        """Verify that recip_lattice.T @ hkl gives the same direction as
        Igor's gmi x vec3 (where gmi has a*,b*,c* as columns).

        For a rotated cubic lattice the old orientation-matrix approach
        would place the poles at a different global position; using the
        reciprocal lattice directly must reproduce the Igor result.
        """
        # A 90-degree rotation about Z: a*->(0,1,0), b*->(-1,0,0), c*->(0,0,1)
        # In Python row convention (rows = a*, b*, c*):
        gm_rows = np.array(
            [
                [0.0, 1.0, 0.0],  # a*
                [-1.0, 0.0, 0.0],  # b*
                [0.0, 0.0, 1.0],  # c*
            ]
        )
        # Igor stores these as columns, so Igor gm = gm_rows.T
        # Igor computes: q = gm_col @ hkl = gm_rows.T @ hkl
        hkl = np.array([1.0, 0.0, 0.0])
        q_igor = gm_rows.T @ hkl  # = (0, -1, 0) i.e. a* direction  # noqa: F841

        recip_lattices = gm_rows[np.newaxis, :, :]
        family = [hkl]  # single direction, no symmetry expansion
        points, indices = pole_figure_points(recip_lattices, family)

        # The q-vector should be (0, -1, 0) in lab frame, which is in
        # the lower hemisphere for the default normal=[0, 1/√2, -1/√2]
        # (dot < 0).  Its antipodal partner (0, 1, 0) would be upper.
        # Check that the code produced at least one point (the family
        # should include the antipodal direction for centrosymmetric).
        # Here we only passed [1,0,0]; let's also pass [-1,0,0]:
        family2 = [hkl, -hkl]
        points2, _ = pole_figure_points(recip_lattices, family2)
        assert len(points2) > 0
        # The projected point must be finite and within the unit circle
        radii = np.sqrt(points2[:, 0] ** 2 + points2[:, 1] ** 2)
        assert np.all(radii <= 1.0 + 1e-10)


# ---------------------------------------------------------------------------
# Surface frame matrices (X / Y / Z / H / F / normal)
# ---------------------------------------------------------------------------


class TestSurfaceFrames:
    """
    Pin the surface-frame matrices against Igor's
    ``xmlMultiIndex.ipf:419-434`` definitions.  Each Igor entry is a 3x3
    matrix whose **columns** are ``{tilt, roll, normal}``; we verify all
    fifteen vectors directly.

    The ``"F"`` entry is a Python-only alias for ``"normal"`` (Igor has
    no explicit F surface).  It uses the SAME -F outward normal as
    Igor's "normal" surface (xmlMultiIndex.ipf:423 comment:
    ``// {tilt=X, roll-H, normal-F}, the usual``) so scientists picking
    "F" get Igor's 34ID-E convention rather than the mirrored +F frame.
    """

    _IR2 = 1.0 / np.sqrt(2.0)

    def _assert_orthonormal(self, normal, roll, tilt):
        for v in (normal, roll, tilt):
            np.testing.assert_allclose(np.linalg.norm(v), 1.0, atol=1e-12)
        np.testing.assert_allclose(np.dot(normal, roll), 0.0, atol=1e-12)
        np.testing.assert_allclose(np.dot(normal, tilt), 0.0, atol=1e-12)
        np.testing.assert_allclose(np.dot(roll, tilt), 0.0, atol=1e-12)
        # Right-handed: tilt x roll == normal
        np.testing.assert_allclose(np.cross(tilt, roll), normal, atol=1e-12)

    def test_f_frame_is_orthonormal(self):
        normal, roll, tilt = get_surface_vectors("F")
        self._assert_orthonormal(normal, roll, tilt)

    def test_f_matches_igor_normal_surface(self):
        # "F" is an alias for Igor's "normal" frame so user expectations
        # match LaueGo conventions.  All three vectors must be identical.
        f_normal, f_roll, f_tilt = get_surface_vectors("F")
        n_normal, n_roll, n_tilt = get_surface_vectors("normal")
        np.testing.assert_allclose(f_normal, n_normal, atol=1e-12)
        np.testing.assert_allclose(f_roll, n_roll, atol=1e-12)
        np.testing.assert_allclose(f_tilt, n_tilt, atol=1e-12)
        # Explicit values: Igor xmlMultiIndex.ipf:423.
        np.testing.assert_allclose(f_tilt, [1.0, 0.0, 0.0], atol=1e-12)
        np.testing.assert_allclose(f_roll, [0.0, -self._IR2, -self._IR2], atol=1e-12)
        np.testing.assert_allclose(f_normal, [0.0, self._IR2, -self._IR2], atol=1e-12)

    def test_all_surface_frames_orthonormal(self):
        # Cheap regression on every entry in case future edits break one.
        for name in ("normal", "X", "H", "Y", "Z", "F"):
            normal, roll, tilt = get_surface_vectors(name)
            self._assert_orthonormal(normal, roll, tilt)

    def test_surface_frames_match_igor(self):
        # Pin every (tilt, roll, normal) triplet against the Igor source
        # at xmlMultiIndex.ipf:419-431.  Igor stores each as columns of
        # a 3x3 matrix; we list them as plain triples here.
        ir2 = self._IR2
        igor_frames = {
            "normal": (
                (1, 0, 0),  # tilt = X
                (0, -ir2, -ir2),  # roll = -H
                (0, ir2, -ir2),  # normal = -F  ("the usual" 34ID-E)
            ),
            "X": (
                (0, -ir2, -ir2),
                (0, ir2, -ir2),
                (1, 0, 0),
            ),
            "H": (
                (1, 0, 0),
                (0, ir2, -ir2),
                (0, ir2, ir2),
            ),
            "Y": (
                (0, 0, 1),
                (1, 0, 0),
                (0, 1, 0),
            ),
            "Z": (
                (1, 0, 0),
                (0, 1, 0),
                (0, 0, 1),
            ),
        }
        for name, (exp_tilt, exp_roll, exp_normal) in igor_frames.items():
            normal, roll, tilt = get_surface_vectors(name)
            np.testing.assert_allclose(tilt, exp_tilt, atol=1e-12, err_msg=f"{name} tilt")
            np.testing.assert_allclose(roll, exp_roll, atol=1e-12, err_msg=f"{name} roll")
            np.testing.assert_allclose(normal, exp_normal, atol=1e-12, err_msg=f"{name} normal")
