"""
Pole figure computation and cubic {hkl} family generation.

Algorithms are derived from LaueGo Igor Pro source (PoleFigure.ipf,
xmlMultiIndex.ipf).  Zero Dash/Plotly dependencies.
"""

import numpy as np

# 34ID-E surface coordinate system (default)
_DEFAULT_NORMAL = np.array([0.0, 1.0 / np.sqrt(2.0), -1.0 / np.sqrt(2.0)])
_DEFAULT_ROLL = np.array([0.0, -1.0 / np.sqrt(2.0), -1.0 / np.sqrt(2.0)])
_DEFAULT_TILT = np.array([1.0, 0.0, 0.0])


# ===================================================================
# Surface Coordinate Frames
# ===================================================================
#
# Predefined surface matrices matching LaueGo's NewPoleFigure
# (xmlMultiIndex.ipf:419-434).  Each entry defines {tilt, roll, normal}
# as three perpendicular unit vectors in beam-line XYZ coordinates.
#
# Beam-line coordinate system: X = out door, Y = up, Z = downstream.

_ir2 = 1.0 / np.sqrt(2.0)

_SURFACE_MATRICES = {
    "normal": {  # 34ID-E default: {tilt=X, roll=-H, normal=-F}
        "tilt": np.array([1.0, 0.0, 0.0]),
        "roll": np.array([0.0, -_ir2, -_ir2]),
        "normal": np.array([0.0, _ir2, -_ir2]),
    },
    "X": {  # normal = X
        "tilt": np.array([0.0, -_ir2, -_ir2]),
        "roll": np.array([0.0, _ir2, -_ir2]),
        "normal": np.array([1.0, 0.0, 0.0]),
    },
    "H": {  # normal = H
        "tilt": np.array([1.0, 0.0, 0.0]),
        "roll": np.array([0.0, _ir2, -_ir2]),
        "normal": np.array([0.0, _ir2, _ir2]),
    },
    "Y": {  # normal = Y (lab up)
        "tilt": np.array([0.0, 0.0, 1.0]),
        "roll": np.array([1.0, 0.0, 0.0]),
        "normal": np.array([0.0, 1.0, 0.0]),
    },
    "Z": {  # normal = Z (downstream)
        "tilt": np.array([1.0, 0.0, 0.0]),
        "roll": np.array([0.0, 1.0, 0.0]),
        "normal": np.array([0.0, 0.0, 1.0]),
    },
    "F": {  # 34ID-E "F surface" -- alias for the default "normal" frame.
        # Igor's xmlMultiIndex.ipf:423 uses {tilt=X, roll=-H, normal=-F}
        # as the canonical 34ID-E sample-surface frame and labels it
        # "the usual"; F is the surface-normal axis with the OUTWARD
        # normal pointing in the -F direction (= (Y-Z)/sqrt(2)).  This
        # entry exists as an explicit user-facing label so scientists
        # asking for the "F surface" get Igor's convention rather than
        # the geometrically-natural +F (which would mirror their pole
        # figures relative to LaueGo).  Identical to "normal" by
        # construction.
        "tilt": np.array([1.0, 0.0, 0.0]),
        "roll": np.array([0.0, -_ir2, -_ir2]),
        "normal": np.array([0.0, _ir2, -_ir2]),
    },
}


def get_surface_vectors(surface="normal"):
    """
    Look up the ``(normal, roll, tilt)`` vectors for a named surface.

    Parameters
    ----------
    surface : str
        One of ``"normal"`` (default), ``"X"``, ``"H"``, ``"Y"``, ``"Z"``,
        ``"F"``.

    Returns
    -------
    normal : ndarray (3,)
    roll : ndarray (3,)
    tilt : ndarray (3,)

    Raises
    ------
    ValueError
        If *surface* is not a recognised name.
    """
    key = surface if surface in _SURFACE_MATRICES else "normal"
    entry = _SURFACE_MATRICES[key]
    return entry["normal"], entry["roll"], entry["tilt"]


# ===================================================================
# Pole Figure Computation
# ===================================================================


def pole_figure_points(recip_lattices, hkl_family, surface_normal=None, surface_roll=None, surface_tilt=None):
    """
    Compute pole figure scatter points.

    For each grain, transforms all symmetry-equivalent pole directions
    into the lab frame using the measured reciprocal lattice and
    stereographically projects them onto the sample surface plane.

    This matches Igor Pro's ``MakePolePoints`` (xmlMultiIndex.ipf) which
    computes ``q = gm * hkl`` directly rather than going through an
    intermediate orientation matrix.

    Parameters
    ----------
    recip_lattices : ndarray (N, 3, 3)
        Measured reciprocal lattice matrices with a*, b*, c* as **rows**
        (as returned by ``xml_parser.parse_indexing_xml``).  Each
        ``recip_lattices[i]`` is the 3x3 matrix for grain *i*.
    hkl_family : list of ndarray (3,)
        Symmetry-equivalent pole directions (from ``cubic_hkl_family``).
    surface_normal : ndarray (3,), optional
        Sample surface normal. Default: 34ID-E convention.
    surface_roll : ndarray (3,), optional
        Roll direction for 2-D projection. Default: 34ID-E convention.
    surface_tilt : ndarray (3,), optional
        Tilt direction for 2-D projection. Default: 34ID-E convention.

    Returns
    -------
    points : ndarray (M, 2)
        (x, y) projected positions on the pole figure.
    grain_indices : ndarray (M,) int
        Which grain each point belongs to.
    """
    if surface_normal is None:
        normal = _DEFAULT_NORMAL
    else:
        normal = np.asarray(surface_normal, dtype=float)
    normal = normal / np.linalg.norm(normal)

    roll = _DEFAULT_ROLL if surface_roll is None else np.asarray(surface_roll, dtype=float)
    tilt = _DEFAULT_TILT if surface_tilt is None else np.asarray(surface_tilt, dtype=float)

    all_x = []
    all_y = []
    all_grains = []

    for i, gm in enumerate(recip_lattices):
        for pole_dir in hkl_family:
            # Transform pole to lab frame using reciprocal lattice
            # directly, matching Igor's: MatrixOp vec3 = gmi x vec3
            # Python stores a*,b*,c* as rows, so gm.T @ hkl gives
            # q = a*·h + b*·k + c*·l  (the lab-frame Q-vector).
            vec = gm.T @ pole_dir
            vec_norm = np.linalg.norm(vec)
            if vec_norm < 1e-12:
                continue
            vec = vec / vec_norm

            # Upper hemisphere only (matching Igor Pro's MakePolePoints).
            # For centrosymmetric crystals every pole direction has an
            # antipodal partner already in the hkl family, so the upper-
            # hemisphere version is always present via that partner.
            dot_normal = np.dot(vec, normal)
            if dot_normal < 0:
                continue

            # Stereographic projection
            sin_theta = np.sqrt(1.0 - np.clip(dot_normal, 0, 1) ** 2)
            r = sin_theta / (1.0 + dot_normal) if (1.0 + dot_normal) > 1e-12 else 0.0

            # Project to 2D
            x_comp = np.dot(vec, tilt)
            y_comp = np.dot(vec, roll)
            phi = np.arctan2(y_comp, x_comp)

            x = r * np.cos(phi)
            y = r * np.sin(phi)

            all_x.append(x)
            all_y.append(y)
            all_grains.append(i)

    if len(all_x) == 0:
        return np.empty((0, 2)), np.empty(0, dtype=int)

    points = np.column_stack([all_x, all_y])
    grain_indices = np.array(all_grains, dtype=int)

    return points, grain_indices


# ===================================================================
# Cubic {hkl} Family Generation
# ===================================================================


def cubic_hkl_family(h, k, l):
    """
    Generate all symmetry-equivalent directions for a cubic {hkl} family.

    .. warning::
       This function uses brute-force permutation and sign enumeration,
       which is **only correct for cubic crystals**.  For non-cubic
       crystal systems (hexagonal, tetragonal, orthorhombic, etc.) the
       generated family will be incorrect because the symmetry-equivalent
       directions depend on the space-group symmetry operations, not
       simple index permutations.  See ``CUBIC_SYMMETRY_OPS`` in
       ``orientation.py`` for the 24 proper rotations of the cubic group.

    Example counts (cubic):
        {100} -> 6 directions
        {110} -> 12 directions
        {111} -> 8 directions
        {210} -> 24 directions
        {321} -> 48 directions

    Parameters
    ----------
    h, k, l : int
        Miller indices.  Must be from a **cubic** crystal system.

    Returns
    -------
    list of ndarray (3,)
        Unique normalized directions.
    """
    # Take absolute values
    vals = [abs(h), abs(k), abs(l)]

    # Generate all 6 permutations
    perms = set()
    indices = vals
    for p0 in indices:
        for p1 in indices:
            for p2 in indices:
                if sorted([p0, p1, p2]) == sorted(indices):
                    perms.add((p0, p1, p2))

    # Generate all 8 sign combinations for each permutation
    candidates = []
    for perm in perms:
        for s0 in [1, -1]:
            for s1 in [1, -1]:
                for s2 in [1, -1]:
                    vec = (s0 * perm[0], s1 * perm[1], s2 * perm[2])
                    if vec == (0, 0, 0):
                        continue
                    candidates.append(vec)

    # Normalize and remove duplicates (exact duplicates only, NOT antipodal)
    unique = []
    for cand in candidates:
        v = np.array(cand, dtype=float)
        v = v / np.linalg.norm(v)

        is_dup = False
        for u in unique:
            if np.dot(v, u) > 0.999:
                is_dup = True
                break
        if not is_dup:
            unique.append(v)

    return unique
