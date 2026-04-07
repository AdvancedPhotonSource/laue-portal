"""
Orientation analysis: reciprocal lattice -> orientation matrix -> Rodrigues vectors.

Converts reciprocal lattice matrices from indexed XML data to orientation
representations and computes crystal directions for IPF coloring.  Includes
misorientation angle calculation with cubic symmetry reduction.

All algorithms derived from LaueGo Igor Pro source (LatticeSym.ipf,
microGeometryN.ipf, GrainMath.ipf, PoleFigure.ipf).  Zero Dash/Plotly
dependencies.
"""

from itertools import combinations

import numpy as np

# 34ID-E convention: sample surface at 45 degrees to beam
_DEFAULT_NORMAL = np.array([0.0, 1.0 / np.sqrt(2.0), -1.0 / np.sqrt(2.0)])


def lattice_params_to_reciprocal(a, b, c, alpha_deg, beta_deg, gamma_deg):
    """
    Compute reference reciprocal lattice matrix from lattice constants.

    Convention: a || x, c* || z  (matching LaueGo's ``setDirectRecip``).

    Parameters
    ----------
    a, b, c : float
        Lattice constants in nm.
    alpha_deg, beta_deg, gamma_deg : float
        Lattice angles in degrees.

    Returns
    -------
    ndarray (3, 3)
        Reciprocal lattice vectors as rows (a*, b*, c*).
    """
    alpha = np.radians(alpha_deg)
    beta = np.radians(beta_deg)
    gamma = np.radians(gamma_deg)

    cos_a = np.cos(alpha)
    cos_b = np.cos(beta)
    cos_g = np.cos(gamma)
    sin_g = np.sin(gamma)

    # Volume factor
    V = np.sqrt(1.0 - cos_a**2 - cos_b**2 - cos_g**2 + 2.0 * cos_a * cos_b * cos_g)

    # Direct lattice matrix (rows = a, b, c vectors)
    direct = np.array([
        [a,         0.0,                                       0.0],
        [b * cos_g, b * sin_g,                                 0.0],
        [c * cos_b, c * (cos_a - cos_b * cos_g) / sin_g,      c * V / sin_g],
    ])

    # Reciprocal lattice = 2*pi * inv(direct)^T
    reciprocal = 2.0 * np.pi * np.linalg.inv(direct).T

    return reciprocal


def recip_to_orientation(recip_lattice, reference_recip):
    """
    Compute orientation matrix from measured and reference reciprocal lattices.

    R = measured @ inv(reference)

    Parameters
    ----------
    recip_lattice : ndarray (3, 3)
        Measured reciprocal lattice matrix (rows = a*, b*, c*).
    reference_recip : ndarray (3, 3)
        Reference reciprocal lattice matrix from lattice parameters.

    Returns
    -------
    ndarray (3, 3)
        Rotation / orientation matrix.
    """
    return recip_lattice @ np.linalg.inv(reference_recip)


def orientation_to_rodrigues(R):
    """
    Convert a 3x3 rotation matrix to a Rodrigues vector.

    R_vec = axis * tan(angle / 2)

    Parameters
    ----------
    R : ndarray (3, 3)
        Rotation matrix.

    Returns
    -------
    ndarray (3,)
        Rodrigues vector.
    """
    trace = R[0, 0] + R[1, 1] + R[2, 2]
    angle = np.arccos(np.clip((trace - 1.0) / 2.0, -1.0, 1.0))

    if angle < 1e-12:
        return np.zeros(3)

    # Rotation axis from skew-symmetric part
    axis = np.array([
        R[1, 2] - R[2, 1],
        R[2, 0] - R[0, 2],
        R[0, 1] - R[1, 0],
    ])
    axis_norm = np.linalg.norm(axis)
    if axis_norm < 1e-12:
        return np.zeros(3)
    axis = axis / axis_norm

    return axis * np.tan(angle / 2.0)


def crystal_direction_along_normal(recip_lattice, normal=None):
    """
    Compute crystal direction (hkl) that points along the sample normal.

    hkl = inv(recip_lattice) @ normal

    Parameters
    ----------
    recip_lattice : ndarray (3, 3)
        Reciprocal lattice matrix (rows = a*, b*, c*).
    normal : ndarray (3,), optional
        Sample surface normal in lab frame.
        Default is [0, 1/sqrt(2), -1/sqrt(2)] (34ID-E convention for
        45-degree sample surface).

    Returns
    -------
    ndarray (3,)
        Crystal direction (hkl) -- not necessarily integer, normalized to
        unit length.
    """
    if normal is None:
        normal = _DEFAULT_NORMAL

    try:
        hkl = np.linalg.inv(recip_lattice) @ normal
    except np.linalg.LinAlgError:
        return np.zeros(3)

    norm = np.linalg.norm(hkl)
    if norm < 1e-12:
        return np.zeros(3)
    return hkl / norm


# ---------------------------------------------------------------------------
# Batch operations for full datasets
# ---------------------------------------------------------------------------

def batch_crystal_directions(recip_lattices, normal=None):
    """
    Compute crystal directions for an array of reciprocal lattice matrices.

    Parameters
    ----------
    recip_lattices : ndarray (N, 3, 3)
        Array of reciprocal lattice matrices.
    normal : ndarray (3,), optional
        Sample surface normal.

    Returns
    -------
    ndarray (N, 3)
        Crystal directions (unit vectors), NaN rows where inversion fails.
    """
    if normal is None:
        normal = _DEFAULT_NORMAL

    N = len(recip_lattices)
    directions = np.full((N, 3), np.nan)

    for i in range(N):
        rl = recip_lattices[i]
        # Skip if all zeros or contains NaN (no indexing data for this step)
        if np.any(np.isnan(rl)) or np.allclose(rl, 0.0):
            continue
        try:
            directions[i] = crystal_direction_along_normal(rl, normal)
        except np.linalg.LinAlgError:
            continue

    return directions


def batch_orientations(recip_lattices, lattice_params):
    """
    Compute orientation matrices for an array of reciprocal lattice matrices.

    Parameters
    ----------
    recip_lattices : ndarray (N, 3, 3)
        Array of reciprocal lattice matrices.
    lattice_params : ndarray (6,)
        Lattice parameters: a, b, c, alpha, beta, gamma.

    Returns
    -------
    ndarray (N, 3, 3)
        Orientation matrices, identity where computation fails.
    """
    ref_recip = lattice_params_to_reciprocal(*lattice_params)
    N = len(recip_lattices)
    orientations = np.tile(np.eye(3), (N, 1, 1))

    for i in range(N):
        rl = recip_lattices[i]
        # Skip if all zeros or contains NaN (no indexing data for this step)
        if np.any(np.isnan(rl)) or np.allclose(rl, 0.0):
            continue
        try:
            orientations[i] = recip_to_orientation(rl, ref_recip)
        except np.linalg.LinAlgError:
            continue

    return orientations


def batch_rodrigues(recip_lattices, lattice_params):
    """
    Compute Rodrigues vectors for an array of reciprocal lattice matrices.

    Parameters
    ----------
    recip_lattices : ndarray (N, 3, 3)
        Array of reciprocal lattice matrices.
    lattice_params : ndarray (6,)
        Lattice parameters: a, b, c, alpha, beta, gamma.

    Returns
    -------
    ndarray (N, 3)
        Rodrigues vectors, zeros where computation fails.
    """
    orientations = batch_orientations(recip_lattices, lattice_params)
    N = len(orientations)
    rodrigues = np.zeros((N, 3))

    for i in range(N):
        rodrigues[i] = orientation_to_rodrigues(orientations[i])

    return rodrigues


# ---------------------------------------------------------------------------
# Cubic symmetry operations (24 proper rotations of point group 432 / m-3m)
# ---------------------------------------------------------------------------

def _make_cubic_symmetry_ops():
    """
    Build the 24 proper rotation matrices for cubic symmetry.

    From ``MakeCubicSymmetryOps()`` in GrainMath.ipf:

    - 1 identity
    - 9 four-fold: 90, 180, 270 deg about [100], [010], [001]
    - 8 three-fold: 120, 240 deg about [111], [-111], [1-11], [-1-11]
    - 6 two-fold: 180 deg about [110], [1-10], [101], [10-1], [011], [01-1]

    Returns
    -------
    ndarray (24, 3, 3)
    """
    ops = []

    # Helper: rotation matrix about a unit axis by angle (radians)
    def _rot(axis, angle_deg):
        a = np.radians(angle_deg)
        c, s = np.cos(a), np.sin(a)
        ax = np.asarray(axis, dtype=float)
        ax = ax / np.linalg.norm(ax)
        x, y, z = ax
        c1 = 1.0 - c
        return np.array([
            [c + x * x * c1,     x * y * c1 - z * s, x * z * c1 + y * s],
            [x * y * c1 + z * s, c + y * y * c1,      y * z * c1 - x * s],
            [x * z * c1 - y * s, y * z * c1 + x * s,  c + z * z * c1],
        ])

    # Identity
    ops.append(np.eye(3))

    # Four-fold axes: [100], [010], [001] at 90, 180, 270 deg
    for axis in ([1, 0, 0], [0, 1, 0], [0, 0, 1]):
        for angle in (90, 180, 270):
            ops.append(_rot(axis, angle))

    # Three-fold axes: [111], [-111], [1-11], [-1-11] at 120, 240 deg
    for axis in ([1, 1, 1], [-1, 1, 1], [1, -1, 1], [-1, -1, 1]):
        for angle in (120, 240):
            ops.append(_rot(axis, angle))

    # Two-fold axes: [110], [1-10], [101], [10-1], [011], [01-1] at 180 deg
    for axis in ([1, 1, 0], [1, -1, 0], [1, 0, 1],
                 [1, 0, -1], [0, 1, 1], [0, 1, -1]):
        ops.append(_rot(axis, 180))

    return np.array(ops)


# Pre-computed constant: 24 cubic proper rotation matrices
CUBIC_SYMMETRY_OPS = _make_cubic_symmetry_ops()

# Pre-computed transposes for vectorized misorientation.
# Since symmetry ops are orthogonal, inv(S) = S.T.
# Stacked as (24, 3, 3) for batch matmul.
_SYM_OPS_T = np.array([s.T for s in CUBIC_SYMMETRY_OPS])


# ---------------------------------------------------------------------------
# Misorientation
# ---------------------------------------------------------------------------

def _rotation_angle(R):
    """Return rotation angle (degrees) of a 3x3 rotation matrix."""
    trace = R[0, 0] + R[1, 1] + R[2, 2]
    return np.degrees(np.arccos(np.clip((trace - 1.0) / 2.0, -1.0, 1.0)))


def misorientation_angle(R1, R2, symmetry_reduce=True):
    """
    Compute misorientation angle between two orientation matrices.

    From ``AngleBetweenMats()`` in PoleFigure.ipf:606-637.

    Uses vectorized numpy operations: all 24 cubic symmetry equivalents
    are evaluated in a single batched matmul.

    Parameters
    ----------
    R1, R2 : ndarray (3, 3)
        Orientation matrices.
    symmetry_reduce : bool
        If True (default), apply cubic symmetry to find the minimum
        misorientation angle (disorientation).

    Returns
    -------
    float
        Misorientation angle in degrees.
    """
    R2_inv = np.linalg.inv(R2)

    if not symmetry_reduce:
        C = R1 @ R2_inv
        return float(_rotation_angle(C))

    # R1 @ inv(R2 @ S) = R1 @ S.T @ R2_inv  (since S is orthogonal)
    # Compute all 24 products in one batch:
    #   (24, 3, 3) = _SYM_OPS_T @ R2_inv[None]  →  R1 @ each
    C_all = R1 @ (_SYM_OPS_T @ R2_inv)  # (24, 3, 3)
    traces = C_all[:, 0, 0] + C_all[:, 1, 1] + C_all[:, 2, 2]
    angles = np.degrees(np.arccos(np.clip((traces - 1.0) / 2.0, -1.0, 1.0)))
    return float(np.min(angles))


def pairwise_misorientation(orientations, indices=None, symmetry_reduce=True):
    """
    Compute pairwise misorientation angles for a subset of grains.

    Parameters
    ----------
    orientations : ndarray (N, 3, 3)
        All orientation matrices.
    indices : array-like of int, optional
        Subset of grain indices to compare.  If None, use all.
    symmetry_reduce : bool
        Apply cubic symmetry reduction (default True).

    Returns
    -------
    dict
        ``angles`` : ndarray -- all pairwise misorientation angles (degrees)
        ``mean`` : float -- mean misorientation angle
        ``min`` : float -- minimum pairwise angle
        ``max`` : float -- maximum pairwise angle
        ``pairs`` : list of (i, j) -- grain index pairs
    """
    if indices is None:
        indices = np.arange(len(orientations))
    else:
        indices = np.asarray(indices)

    if len(indices) < 2:
        return {
            "angles": np.array([]),
            "mean": 0.0,
            "min": 0.0,
            "max": 0.0,
            "pairs": [],
        }

    pairs = list(combinations(indices, 2))
    angles = np.empty(len(pairs))

    for k, (i, j) in enumerate(pairs):
        angles[k] = misorientation_angle(
            orientations[i], orientations[j],
            symmetry_reduce=symmetry_reduce,
        )

    return {
        "angles": angles,
        "mean": float(np.mean(angles)),
        "min": float(np.min(angles)),
        "max": float(np.max(angles)),
        "pairs": pairs,
    }
