"""
Tests for laue_portal.analysis.orientation module.

Tests reciprocal lattice computation, orientation matrix extraction,
Rodrigues vector conversion, and crystal direction calculation.
"""

import os
import sys
import numpy as np
import pytest

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from laue_portal.analysis.orientation import (
    lattice_params_to_reciprocal,
    recip_to_orientation,
    orientation_to_rodrigues,
    crystal_direction_along_normal,
    batch_crystal_directions,
    batch_orientations,
    batch_rodrigues,
    CUBIC_SYMMETRY_OPS,
    misorientation_angle,
    pairwise_misorientation,
)


# ---------------------------------------------------------------------------
# lattice_params_to_reciprocal
# ---------------------------------------------------------------------------

class TestLatticeParamsToReciprocal:

    def test_cubic_returns_3x3(self):
        recip = lattice_params_to_reciprocal(0.40495, 0.40495, 0.40495, 90, 90, 90)
        assert recip.shape == (3, 3)

    def test_cubic_orthogonality(self):
        """For cubic, a* b* c* should be mutually orthogonal."""
        recip = lattice_params_to_reciprocal(0.40495, 0.40495, 0.40495, 90, 90, 90)
        # Rows are a*, b*, c*
        dot_ab = np.dot(recip[0], recip[1])
        dot_ac = np.dot(recip[0], recip[2])
        dot_bc = np.dot(recip[1], recip[2])
        assert abs(dot_ab) < 1e-10
        assert abs(dot_ac) < 1e-10
        assert abs(dot_bc) < 1e-10

    def test_cubic_equal_lengths(self):
        """For cubic, |a*| = |b*| = |c*|."""
        recip = lattice_params_to_reciprocal(0.40495, 0.40495, 0.40495, 90, 90, 90)
        lengths = np.linalg.norm(recip, axis=1)
        assert abs(lengths[0] - lengths[1]) < 1e-10
        assert abs(lengths[1] - lengths[2]) < 1e-10

    def test_cubic_reciprocal_magnitude(self):
        """For cubic, |a*| = 2*pi/a."""
        a = 0.40495
        recip = lattice_params_to_reciprocal(a, a, a, 90, 90, 90)
        expected = 2 * np.pi / a
        actual = np.linalg.norm(recip[0])
        assert abs(actual - expected) < 1e-6

    def test_hexagonal_returns_3x3(self):
        """Hexagonal lattice (a=b!=c, alpha=beta=90, gamma=120)."""
        recip = lattice_params_to_reciprocal(0.3, 0.3, 0.5, 90, 90, 120)
        assert recip.shape == (3, 3)

    def test_hexagonal_c_star_along_z(self):
        """c* should be along z (convention: c* || z)."""
        recip = lattice_params_to_reciprocal(0.3, 0.3, 0.5, 90, 90, 120)
        c_star = recip[2]
        # c* should have zero x and y components
        assert abs(c_star[0]) < 1e-10
        assert abs(c_star[1]) < 1e-10
        assert c_star[2] > 0

    def test_direct_times_reciprocal_gives_2pi_identity(self):
        """direct @ reciprocal^T = 2*pi * I."""
        a, b, c = 0.40495, 0.40495, 0.40495
        recip = lattice_params_to_reciprocal(a, b, c, 90, 90, 90)
        # Reconstruct direct lattice
        direct = np.array([
            [a, 0, 0],
            [0, b, 0],
            [0, 0, c],
        ])
        product = direct @ recip.T
        expected = 2 * np.pi * np.eye(3)
        np.testing.assert_allclose(product, expected, atol=1e-8)


# ---------------------------------------------------------------------------
# recip_to_orientation
# ---------------------------------------------------------------------------

class TestRecipToOrientation:

    def test_identity_for_reference(self):
        """Reference reciprocal lattice should give identity orientation."""
        ref = lattice_params_to_reciprocal(0.40495, 0.40495, 0.40495, 90, 90, 90)
        R = recip_to_orientation(ref, ref)
        np.testing.assert_allclose(R, np.eye(3), atol=1e-10)

    def test_returns_3x3(self):
        ref = lattice_params_to_reciprocal(0.40495, 0.40495, 0.40495, 90, 90, 90)
        # Slightly rotated
        angle = np.radians(10)
        rot = np.array([
            [np.cos(angle), -np.sin(angle), 0],
            [np.sin(angle),  np.cos(angle), 0],
            [0, 0, 1],
        ])
        measured = rot @ ref
        R = recip_to_orientation(measured, ref)
        assert R.shape == (3, 3)

    def test_recovers_rotation(self):
        """Should recover a known rotation."""
        ref = lattice_params_to_reciprocal(0.40495, 0.40495, 0.40495, 90, 90, 90)
        angle = np.radians(30)
        rot = np.array([
            [1, 0, 0],
            [0, np.cos(angle), -np.sin(angle)],
            [0, np.sin(angle),  np.cos(angle)],
        ])
        measured = rot @ ref
        R = recip_to_orientation(measured, ref)
        np.testing.assert_allclose(R, rot, atol=1e-10)


# ---------------------------------------------------------------------------
# orientation_to_rodrigues
# ---------------------------------------------------------------------------

class TestOrientationToRodrigues:

    def test_identity_gives_zero_vector(self):
        rod = orientation_to_rodrigues(np.eye(3))
        np.testing.assert_allclose(rod, [0, 0, 0], atol=1e-12)

    def test_90_deg_about_z(self):
        """90 deg about z: |rod| = tan(45) = 1, axis along z."""
        angle = np.radians(90)
        R = np.array([
            [np.cos(angle), -np.sin(angle), 0],
            [np.sin(angle),  np.cos(angle), 0],
            [0, 0, 1],
        ])
        rod = orientation_to_rodrigues(R)
        # Length should be tan(45 deg) = 1
        np.testing.assert_allclose(np.linalg.norm(rod), 1.0, atol=1e-10)
        # Should be along z axis (x and y components zero)
        np.testing.assert_allclose(rod[0], 0.0, atol=1e-10)
        np.testing.assert_allclose(rod[1], 0.0, atol=1e-10)

    def test_rodrigues_length_is_tan_half_angle(self):
        """For arbitrary rotation, |R_vec| = tan(angle/2)."""
        angle = np.radians(60)
        R = np.array([
            [1, 0, 0],
            [0, np.cos(angle), -np.sin(angle)],
            [0, np.sin(angle),  np.cos(angle)],
        ])
        rod = orientation_to_rodrigues(R)
        expected_length = np.tan(np.radians(60) / 2)
        assert abs(np.linalg.norm(rod) - expected_length) < 1e-10

    def test_returns_3_vector(self):
        rod = orientation_to_rodrigues(np.eye(3))
        assert rod.shape == (3,)


# ---------------------------------------------------------------------------
# crystal_direction_along_normal
# ---------------------------------------------------------------------------

class TestCrystalDirectionAlongNormal:

    def test_returns_unit_vector(self):
        recip = lattice_params_to_reciprocal(0.40495, 0.40495, 0.40495, 90, 90, 90)
        d = crystal_direction_along_normal(recip)
        norm = np.linalg.norm(d)
        assert abs(norm - 1.0) < 1e-10 or norm < 1e-12

    def test_z_normal_gives_001(self):
        """With surface normal along z, crystal dir should be (001) for
        un-rotated cubic crystal."""
        recip = lattice_params_to_reciprocal(0.40495, 0.40495, 0.40495, 90, 90, 90)
        d = crystal_direction_along_normal(recip, normal=np.array([0, 0, 1]))
        # For unrotated cubic, inv(recip) @ [0,0,1] should be along [0,0,1]
        assert abs(d[2]) > 0.9

    def test_zero_recip_returns_zeros(self):
        """Singular matrix should return zeros gracefully."""
        d = crystal_direction_along_normal(np.zeros((3, 3)), normal=np.array([0, 0, 1]))
        np.testing.assert_allclose(d, [0, 0, 0], atol=1e-12)


# ---------------------------------------------------------------------------
# Batch operations
# ---------------------------------------------------------------------------

class TestBatchOperations:

    @pytest.fixture
    def cubic_data(self):
        """Synthetic data: 4 steps with known reciprocal lattices."""
        lattice_params = np.array([0.40495, 0.40495, 0.40495, 90, 90, 90])
        ref = lattice_params_to_reciprocal(*lattice_params)

        # 4 orientations: identity, 30deg about x, 45deg about y, 60deg about z
        angles = [0, 30, 45, 60]
        axes = ['x', 'x', 'y', 'z']
        recip_lattices = np.zeros((4, 3, 3))

        for i, (angle, axis) in enumerate(zip(angles, axes)):
            a = np.radians(angle)
            if axis == 'x':
                R = np.array([[1,0,0],[0,np.cos(a),-np.sin(a)],[0,np.sin(a),np.cos(a)]])
            elif axis == 'y':
                R = np.array([[np.cos(a),0,np.sin(a)],[0,1,0],[-np.sin(a),0,np.cos(a)]])
            else:
                R = np.array([[np.cos(a),-np.sin(a),0],[np.sin(a),np.cos(a),0],[0,0,1]])
            recip_lattices[i] = R @ ref

        return recip_lattices, lattice_params

    def test_batch_crystal_directions_shape(self, cubic_data):
        recip_lattices, _ = cubic_data
        dirs = batch_crystal_directions(recip_lattices)
        assert dirs.shape == (4, 3)

    def test_batch_crystal_directions_unit_vectors(self, cubic_data):
        recip_lattices, _ = cubic_data
        dirs = batch_crystal_directions(recip_lattices)
        for i in range(4):
            if not np.any(np.isnan(dirs[i])):
                norm = np.linalg.norm(dirs[i])
                assert abs(norm - 1.0) < 1e-8

    def test_batch_orientations_shape(self, cubic_data):
        recip_lattices, lattice_params = cubic_data
        orientations = batch_orientations(recip_lattices, lattice_params)
        assert orientations.shape == (4, 3, 3)

    def test_batch_orientations_identity_first(self, cubic_data):
        recip_lattices, lattice_params = cubic_data
        orientations = batch_orientations(recip_lattices, lattice_params)
        np.testing.assert_allclose(orientations[0], np.eye(3), atol=1e-8)

    def test_batch_rodrigues_shape(self, cubic_data):
        recip_lattices, lattice_params = cubic_data
        rodrigues = batch_rodrigues(recip_lattices, lattice_params)
        assert rodrigues.shape == (4, 3)

    def test_batch_rodrigues_zero_for_identity(self, cubic_data):
        recip_lattices, lattice_params = cubic_data
        rodrigues = batch_rodrigues(recip_lattices, lattice_params)
        np.testing.assert_allclose(rodrigues[0], [0, 0, 0], atol=1e-10)

    def test_batch_handles_zero_recip(self):
        """Steps with zero reciprocal lattices should produce NaN/zero."""
        recip_lattices = np.zeros((2, 3, 3))
        lattice_params = np.array([0.40495, 0.40495, 0.40495, 90, 90, 90])

        dirs = batch_crystal_directions(recip_lattices)
        assert dirs.shape == (2, 3)
        assert np.all(np.isnan(dirs))

        orientations = batch_orientations(recip_lattices, lattice_params)
        # Should fallback to identity
        np.testing.assert_allclose(orientations[0], np.eye(3))

        rodrigues = batch_rodrigues(recip_lattices, lattice_params)
        np.testing.assert_allclose(rodrigues, 0, atol=1e-10)


# ---------------------------------------------------------------------------
# Cubic symmetry operations
# ---------------------------------------------------------------------------

class TestCubicSymmetryOps:

    def test_count(self):
        """There should be exactly 24 proper cubic rotations."""
        assert CUBIC_SYMMETRY_OPS.shape == (24, 3, 3)

    def test_all_orthogonal(self):
        """Each matrix should be orthogonal: R @ R^T = I."""
        for i, R in enumerate(CUBIC_SYMMETRY_OPS):
            product = R @ R.T
            np.testing.assert_allclose(product, np.eye(3), atol=1e-10,
                                       err_msg=f"Op {i} not orthogonal")

    def test_all_proper(self):
        """Each matrix should have determinant +1 (proper rotation)."""
        for i, R in enumerate(CUBIC_SYMMETRY_OPS):
            det = np.linalg.det(R)
            assert abs(det - 1.0) < 1e-10, f"Op {i} det={det}"

    def test_identity_present(self):
        """The identity matrix should be in the set."""
        found = False
        for R in CUBIC_SYMMETRY_OPS:
            if np.allclose(R, np.eye(3), atol=1e-10):
                found = True
                break
        assert found, "Identity not found in cubic symmetry ops"

    def test_all_unique(self):
        """All 24 operations should be distinct."""
        for i in range(24):
            for j in range(i + 1, 24):
                assert not np.allclose(CUBIC_SYMMETRY_OPS[i],
                                       CUBIC_SYMMETRY_OPS[j], atol=1e-10), \
                    f"Ops {i} and {j} are identical"

    def test_closure(self):
        """Product of any two ops should also be in the set (group closure)."""
        ops_list = list(CUBIC_SYMMETRY_OPS)
        for i in range(24):
            for j in range(24):
                product = CUBIC_SYMMETRY_OPS[i] @ CUBIC_SYMMETRY_OPS[j]
                found = any(np.allclose(product, op, atol=1e-10) for op in ops_list)
                assert found, (
                    f"Product of ops {i} and {j} not found in group"
                )


# ---------------------------------------------------------------------------
# Misorientation angle
# ---------------------------------------------------------------------------

class TestMisorientationAngle:

    def _rot_z(self, deg):
        """Rotation matrix about z by deg degrees."""
        a = np.radians(deg)
        return np.array([
            [np.cos(a), -np.sin(a), 0],
            [np.sin(a),  np.cos(a), 0],
            [0, 0, 1],
        ])

    def _rot_x(self, deg):
        """Rotation matrix about x by deg degrees."""
        a = np.radians(deg)
        return np.array([
            [1, 0, 0],
            [0, np.cos(a), -np.sin(a)],
            [0, np.sin(a),  np.cos(a)],
        ])

    def test_identical_orientations_zero(self):
        """Misorientation between identical orientations is 0."""
        R = self._rot_z(30)
        angle = misorientation_angle(R, R, symmetry_reduce=False)
        assert abs(angle) < 1e-8

    def test_known_angle_no_symmetry(self):
        """Without symmetry, misorientation should equal the relative rotation angle."""
        R1 = np.eye(3)
        R2 = self._rot_z(25)
        angle = misorientation_angle(R1, R2, symmetry_reduce=False)
        assert abs(angle - 25.0) < 1e-6

    def test_known_angle_with_symmetry(self):
        """With cubic symmetry, 90 deg about [001] should give 0 (it's a symmetry op)."""
        R1 = np.eye(3)
        R2 = self._rot_z(90)
        angle = misorientation_angle(R1, R2, symmetry_reduce=True)
        assert abs(angle) < 1e-6

    def test_symmetry_reduces_angle(self):
        """Symmetry-reduced angle should be <= unreduced angle."""
        R1 = np.eye(3)
        R2 = self._rot_z(50)
        raw_angle = misorientation_angle(R1, R2, symmetry_reduce=False)
        sym_angle = misorientation_angle(R1, R2, symmetry_reduce=True)
        assert sym_angle <= raw_angle + 1e-8

    def test_cubic_max_disorientation(self):
        """For cubic, the maximum disorientation angle is 62.8 deg.
        A 180 deg rotation about [100] is a symmetry op, so its
        symmetry-reduced misorientation from identity should be 0."""
        R1 = np.eye(3)
        # 180 about x is a cubic symmetry op
        R2 = self._rot_x(180)
        angle = misorientation_angle(R1, R2, symmetry_reduce=True)
        assert abs(angle) < 1e-6

    def test_commutativity(self):
        """misorientation(R1, R2) should equal misorientation(R2, R1)
        for symmetry-reduced case."""
        R1 = self._rot_z(20)
        R2 = self._rot_x(35)
        angle_12 = misorientation_angle(R1, R2, symmetry_reduce=True)
        angle_21 = misorientation_angle(R2, R1, symmetry_reduce=True)
        assert abs(angle_12 - angle_21) < 1e-6

    def test_non_trivial_symmetry_reduction(self):
        """A 95 deg rotation about [001] should reduce to 5 deg
        (closest symmetry op is 90 deg about [001])."""
        R1 = np.eye(3)
        R2 = self._rot_z(95)
        angle = misorientation_angle(R1, R2, symmetry_reduce=True)
        assert abs(angle - 5.0) < 1e-5


# ---------------------------------------------------------------------------
# Pairwise misorientation
# ---------------------------------------------------------------------------

class TestPairwiseMisorientation:

    @pytest.fixture
    def orientations(self):
        """3 orientation matrices: identity, 10 deg about z, 20 deg about z."""
        R0 = np.eye(3)
        a10 = np.radians(10)
        R1 = np.array([
            [np.cos(a10), -np.sin(a10), 0],
            [np.sin(a10),  np.cos(a10), 0],
            [0, 0, 1],
        ])
        a20 = np.radians(20)
        R2 = np.array([
            [np.cos(a20), -np.sin(a20), 0],
            [np.sin(a20),  np.cos(a20), 0],
            [0, 0, 1],
        ])
        return np.array([R0, R1, R2])

    def test_returns_dict_keys(self, orientations):
        result = pairwise_misorientation(orientations)
        assert "angles" in result
        assert "mean" in result
        assert "min" in result
        assert "max" in result
        assert "pairs" in result

    def test_pair_count(self, orientations):
        """3 grains -> 3 pairs: (0,1), (0,2), (1,2)."""
        result = pairwise_misorientation(orientations)
        assert len(result["angles"]) == 3
        assert len(result["pairs"]) == 3

    def test_known_angles(self, orientations):
        """Angles should be ~10, ~20, ~10 degrees (no symmetry reduction for
        small angles)."""
        result = pairwise_misorientation(orientations, symmetry_reduce=False)
        angles = sorted(result["angles"])
        assert abs(angles[0] - 10.0) < 1e-4
        assert abs(angles[1] - 10.0) < 1e-4
        assert abs(angles[2] - 20.0) < 1e-4

    def test_subset_indices(self, orientations):
        """Selecting only grains 0 and 2 should give 1 pair with ~20 deg."""
        result = pairwise_misorientation(orientations, indices=[0, 2],
                                          symmetry_reduce=False)
        assert len(result["angles"]) == 1
        assert abs(result["angles"][0] - 20.0) < 1e-4

    def test_single_grain(self, orientations):
        """Single grain -> no pairs."""
        result = pairwise_misorientation(orientations, indices=[0])
        assert len(result["angles"]) == 0
        assert result["mean"] == 0.0

    def test_mean_min_max(self, orientations):
        result = pairwise_misorientation(orientations, symmetry_reduce=False)
        assert result["min"] <= result["mean"] <= result["max"]
        assert abs(result["min"] - 10.0) < 1e-4
        assert abs(result["max"] - 20.0) < 1e-4
