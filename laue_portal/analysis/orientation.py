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
    direct = np.array(
        [
            [a, 0.0, 0.0],
            [b * cos_g, b * sin_g, 0.0],
            [c * cos_b, c * (cos_a - cos_b * cos_g) / sin_g, c * V / sin_g],
        ]
    )

    # Reciprocal lattice = 2*pi * inv(direct)^T
    reciprocal = 2.0 * np.pi * np.linalg.inv(direct).T

    return reciprocal


def recip_to_orientation(recip_lattice, reference_recip):
    """
    Compute orientation matrix from measured and reference reciprocal lattices.

    R = measured.T @ inv(reference.T)

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
    # Convention note: both matrices store a*, b*, c* as **rows** (Python
    # convention), but the crystallographic relation G_meas = R @ G_ref
    # assumes the column convention (Igor Pro / LaueGo).  Transpose both
    # to match:  R = G_meas_col @ inv(G_ref_col) = meas.T @ inv(ref.T).
    return recip_lattice.T @ np.linalg.inv(reference_recip.T)


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

    # Rotation axis from skew-symmetric part.  Sign follows Igor's
    # axisOfMatrix() convention after its 2007 Rodrigues polarity fix.
    axis = np.array(
        [
            R[2, 1] - R[1, 2],
            R[0, 2] - R[2, 0],
            R[1, 0] - R[0, 1],
        ]
    )
    axis_norm = np.linalg.norm(axis)
    if axis_norm < 1e-12:
        return np.zeros(3)
    axis = axis / axis_norm

    return axis * np.tan(angle / 2.0)


def crystal_direction_along_normal(recip_lattice, normal=None):
    """
    Compute crystal direction (hkl) that points along the sample normal.

    hkl = inv(recip_lattice.T) @ normal

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
        # Convention note: the XML parser stores a*, b*, c* as **rows**
        # (Python / numpy convention), but the crystallographic equation
        # Q_lab = G @ hkl requires a*, b*, c* as **columns** (the Igor
        # Pro / LaueGo convention used in xmlMultiIndex.ipf).  Transpose
        # to convert from row convention to column convention before
        # inverting.  See also pole_figure_points() in projection.py
        # which applies the same transpose for the forward transform.
        hkl = np.linalg.inv(recip_lattice.T) @ normal
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


def batch_rodrigues(
    recip_lattices,
    lattice_params,
    symmetry_ops=None,
    reference_index=None,
    reference_recip=None,
    return_valid=False,
):
    """
    Compute Rodrigues vectors for an array of reciprocal lattice matrices.

    Parameters
    ----------
    recip_lattices : ndarray (N, 3, 3)
        Array of reciprocal lattice matrices.
    lattice_params : ndarray (6,)
        Lattice parameters: a, b, c, alpha, beta, gamma.
    symmetry_ops : ndarray (M, 3, 3), optional
        Proper crystal symmetry operations.  When supplied, each orientation
        is symmetry-reduced to the smallest rotation from the reference before
        conversion to a Rodrigues vector, matching LaueGo's
        ``symReducedRecipLattice`` path.
    reference_index : int, optional
        Index of the grain/step to use as the reference orientation.  ``None``
        uses the standard lab-system orientation from the lattice parameters.
    reference_recip : ndarray (3, 3), optional
        Custom reference reciprocal lattice with rows ``[astar; bstar; cstar]``.
        Takes precedence over ``reference_index`` when valid.
    return_valid : bool
        If True, also return a mask for points with valid reciprocal lattices.

    Returns
    -------
    ndarray (N, 3) or tuple
        Rodrigues vectors, zeros where computation fails.  If
        ``return_valid`` is True, returns ``(rodrigues, valid_mask)``.
    """
    orientations = batch_orientations(recip_lattices, lattice_params)
    N = len(orientations)
    rodrigues = np.zeros((N, 3))
    valid = np.zeros(N, dtype=bool)

    ref_orientation = None
    if reference_recip is not None:
        ref_rl = np.asarray(reference_recip, dtype=float)
        if ref_rl.shape == (3, 3) and not (np.any(np.isnan(ref_rl)) or np.allclose(ref_rl, 0.0)):
            try:
                ref_recip = lattice_params_to_reciprocal(*lattice_params)
                ref_orientation = recip_to_orientation(ref_rl, ref_recip)
            except np.linalg.LinAlgError:
                ref_orientation = None

    if ref_orientation is None and reference_index is not None:
        try:
            ref_idx = int(reference_index)
        except (TypeError, ValueError):
            ref_idx = -1
        if 0 <= ref_idx < N:
            ref_rl = recip_lattices[ref_idx]
            if not (np.any(np.isnan(ref_rl)) or np.allclose(ref_rl, 0.0)):
                ref_orientation = orientations[ref_idx]

    for i in range(N):
        rl = recip_lattices[i]
        if np.any(np.isnan(rl)) or np.allclose(rl, 0.0):
            continue

        try:
            R = orientations[i]
            if symmetry_ops is not None:
                R = symmetry_reduce_orientation(R, reference=ref_orientation, symmetry_ops=symmetry_ops)
            elif ref_orientation is not None:
                R = R @ np.linalg.inv(ref_orientation)
            rodrigues[i] = orientation_to_rodrigues(R)
            valid[i] = True
        except np.linalg.LinAlgError:
            continue

    if return_valid:
        return rodrigues, valid
    return rodrigues


# ---------------------------------------------------------------------------
# Symmetry operations
# ---------------------------------------------------------------------------


def _rotation_matrix(axis, angle_deg):
    """Return a proper rotation matrix about ``axis`` by ``angle_deg``."""
    a = np.radians(angle_deg)
    c, s = np.cos(a), np.sin(a)
    ax = np.asarray(axis, dtype=float)
    ax = ax / np.linalg.norm(ax)
    x, y, z = ax
    c1 = 1.0 - c
    return np.array(
        [
            [c + x * x * c1, x * y * c1 - z * s, x * z * c1 + y * s],
            [x * y * c1 + z * s, c + y * y * c1, y * z * c1 - x * s],
            [x * z * c1 - y * s, y * z * c1 + x * s, c + z * z * c1],
        ]
    )


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

    # Identity
    ops.append(np.eye(3))

    # Four-fold axes: [100], [010], [001] at 90, 180, 270 deg
    for axis in ([1, 0, 0], [0, 1, 0], [0, 0, 1]):
        for angle in (90, 180, 270):
            ops.append(_rotation_matrix(axis, angle))

    # Three-fold axes: [111], [-111], [1-11], [-1-11] at 120, 240 deg
    for axis in ([1, 1, 1], [-1, 1, 1], [1, -1, 1], [-1, -1, 1]):
        for angle in (120, 240):
            ops.append(_rotation_matrix(axis, angle))

    # Two-fold axes: [110], [1-10], [101], [10-1], [011], [01-1] at 180 deg
    for axis in ([1, 1, 0], [1, -1, 0], [1, 0, 1], [1, 0, -1], [0, 1, 1], [0, 1, -1]):
        ops.append(_rotation_matrix(axis, 180))

    return np.array(ops)


def _make_hexagonal_symmetry_ops():
    """
    Build the 12 proper rotations for the full hexagonal point group 622.

    This is the proper-rotation subset of the common hexagonal Laue group
    6/mmm: six rotations about c*, plus six two-fold rotations about axes in
    the basal plane.  It mirrors Igor's use of proper operations only in
    ``MakeSymmetryOps`` / ``symReducedRecipLattice``.
    """
    ops = []

    # Six-fold axis along c*.
    for angle in (0, 60, 120, 180, 240, 300):
        ops.append(_rotation_matrix([0, 0, 1], angle))

    # Six two-fold axes in the basal plane, separated by 30 degrees.
    for angle in (0, 30, 60, 90, 120, 150):
        axis = [np.cos(np.radians(angle)), np.sin(np.radians(angle)), 0.0]
        ops.append(_rotation_matrix(axis, 180))

    return np.array(ops)


# Pre-computed constant: 24 cubic proper rotation matrices
CUBIC_SYMMETRY_OPS = _make_cubic_symmetry_ops()

# Pre-computed constant: 12 full hexagonal proper rotation matrices
HEXAGONAL_SYMMETRY_OPS = _make_hexagonal_symmetry_ops()

# Pre-computed transposes for vectorized misorientation.
# Since symmetry ops are orthogonal, inv(S) = S.T.
# Stacked as (24, 3, 3) for batch matmul.
_SYM_OPS_T = np.array([s.T for s in CUBIC_SYMMETRY_OPS])


def symmetry_ops_for_space_group(space_group):
    """
    Return supported proper symmetry operations for a crystallographic space group.

    Currently supports hexagonal space groups 168-194 and cubic space groups
    195-230.  Unsupported or missing groups return ``None`` so callers can
    fall back to unreduced rotations.
    """
    try:
        sg = int(space_group)
    except (TypeError, ValueError):
        return None

    if 195 <= sg <= 230:
        return CUBIC_SYMMETRY_OPS
    if 168 <= sg <= 194:
        return HEXAGONAL_SYMMETRY_OPS
    return None


def symmetry_ops_for_name(symmetry):
    """Return supported proper symmetry operations by UI/option name."""
    if symmetry == "cubic":
        return CUBIC_SYMMETRY_OPS
    if symmetry == "hexagonal":
        return HEXAGONAL_SYMMETRY_OPS
    return None


def symmetry_reduce_orientation(R, reference=None, symmetry_ops=None):
    """
    Symmetry-reduce an orientation to the smallest rotation from ``reference``.

    This ports LaueGo's ``symReducedRecipLattice`` trace-maximization logic
    into orientation-matrix form.  Candidates are ``R @ S.T @ inv(reference)``;
    the largest trace gives the smallest rotation angle.
    """
    if symmetry_ops is None:
        return R

    if reference is None:
        ref_inv = np.eye(3)
    else:
        ref_inv = np.linalg.inv(reference)

    sym_ops_t = np.swapaxes(np.asarray(symmetry_ops, dtype=float), 1, 2)
    candidates = R @ (sym_ops_t @ ref_inv)
    traces = candidates[:, 0, 0] + candidates[:, 1, 1] + candidates[:, 2, 2]
    return candidates[int(np.argmax(traces))]


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


def misorientation_from_reference(orientations, ref_index, symmetry_reduce=True):
    """
    Compute symmetry-reduced misorientation of every grain relative to one
    reference grain.  Returns Rodrigues vectors suitable for RGB coloring.

    Ports the inner loop of Igor's ``ProcessLoadedXMLfile``
    (xmlMultiIndex.ipf:4193-4241) combined with ``makeRGBJZT``.

    Complexity is O(N * 24) -- linear in the number of grains, fully
    vectorized across symmetry operations.

    Parameters
    ----------
    orientations : ndarray (N, 3, 3)
        Orientation matrices for all grains.
    ref_index : int
        Index of the reference grain.
    symmetry_reduce : bool
        Apply cubic symmetry reduction (default True).

    Returns
    -------
    dict
        ``rodrigues`` : ndarray (N, 3) -- Rodrigues vectors relative to the
            reference grain.  The reference grain itself has [0, 0, 0].
        ``angles`` : ndarray (N,) -- misorientation angles in degrees.
    """
    N = len(orientations)
    R_ref = orientations[ref_index]
    R_ref_inv = np.linalg.inv(R_ref)

    rodrigues = np.zeros((N, 3))
    angles = np.zeros(N)

    if symmetry_reduce:
        # Pre-compute all 24 symmetry-equivalent inverses of the reference:
        #   S.T @ R_ref_inv  for each symmetry op S  -> shape (24, 3, 3)
        sym_ref_inv = _SYM_OPS_T @ R_ref_inv  # (24, 3, 3)

        for i in range(N):
            if i == ref_index:
                continue  # stays at zero

            # C_all[s] = R_i @ sym_ref_inv[s]  ->  (24, 3, 3)
            C_all = orientations[i] @ sym_ref_inv  # (24, 3, 3)
            traces = C_all[:, 0, 0] + C_all[:, 1, 1] + C_all[:, 2, 2]
            all_angles = np.degrees(np.arccos(np.clip((traces - 1.0) / 2.0, -1.0, 1.0)))
            best = int(np.argmin(all_angles))
            angle = all_angles[best]
            angles[i] = angle

            if angle < 1e-12:
                continue

            C = C_all[best]
            axis = np.array(
                [
                    C[1, 2] - C[2, 1],
                    C[2, 0] - C[0, 2],
                    C[0, 1] - C[1, 0],
                ]
            )
            axis_norm = np.linalg.norm(axis)
            if axis_norm < 1e-12:
                continue
            axis /= axis_norm
            rodrigues[i] = axis * np.tan(np.radians(angle) / 2.0)
    else:
        for i in range(N):
            if i == ref_index:
                continue
            C = orientations[i] @ R_ref_inv
            trace = C[0, 0] + C[1, 1] + C[2, 2]
            angle = np.degrees(np.arccos(np.clip((trace - 1.0) / 2.0, -1.0, 1.0)))
            angles[i] = angle
            if angle < 1e-12:
                continue
            axis = np.array(
                [
                    C[1, 2] - C[2, 1],
                    C[2, 0] - C[0, 2],
                    C[0, 1] - C[1, 0],
                ]
            )
            axis_norm = np.linalg.norm(axis)
            if axis_norm < 1e-12:
                continue
            axis /= axis_norm
            rodrigues[i] = axis * np.tan(np.radians(angle) / 2.0)

    return {
        "rodrigues": rodrigues,
        "angles": angles,
    }


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
            orientations[i],
            orientations[j],
            symmetry_reduce=symmetry_reduce,
        )

    return {
        "angles": angles,
        "mean": float(np.mean(angles)),
        "min": float(np.min(angles)),
        "max": float(np.max(angles)),
        "pairs": pairs,
    }
