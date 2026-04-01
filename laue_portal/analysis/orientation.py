"""
Orientation analysis: reciprocal lattice -> orientation matrix -> Rodrigues vectors.

Converts reciprocal lattice matrices from indexed XML data to orientation
representations and computes crystal directions for IPF coloring.

All algorithms derived from LaueGo Igor Pro source (LatticeSym.ipf,
microGeometryN.ipf).  Zero Dash/Plotly dependencies.
"""

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
