"""
Stereographic projection, Wulff net, pole figure computation, and
cubic {hkl} family generation.

All algorithms derived from LaueGo Igor Pro source (StereographicProjection.ipf,
PoleFigure.ipf, xmlMultiIndex.ipf).  Zero Dash/Plotly dependencies.
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
        "tilt":   np.array([1.0, 0.0, 0.0]),
        "roll":   np.array([0.0, -_ir2, -_ir2]),
        "normal": np.array([0.0, _ir2, -_ir2]),
    },
    "X": {  # normal = X
        "tilt":   np.array([0.0, -_ir2, -_ir2]),
        "roll":   np.array([0.0, _ir2, -_ir2]),
        "normal": np.array([1.0, 0.0, 0.0]),
    },
    "H": {  # normal = H
        "tilt":   np.array([1.0, 0.0, 0.0]),
        "roll":   np.array([0.0, _ir2, -_ir2]),
        "normal": np.array([0.0, _ir2, _ir2]),
    },
    "Y": {  # normal = Y (lab up)
        "tilt":   np.array([0.0, 0.0, 1.0]),
        "roll":   np.array([1.0, 0.0, 0.0]),
        "normal": np.array([0.0, 1.0, 0.0]),
    },
    "Z": {  # normal = Z (downstream)
        "tilt":   np.array([1.0, 0.0, 0.0]),
        "roll":   np.array([0.0, 1.0, 0.0]),
        "normal": np.array([0.0, 0.0, 1.0]),
    },
}


def get_surface_vectors(surface="normal"):
    """
    Look up the ``(normal, roll, tilt)`` vectors for a named surface.

    Parameters
    ----------
    surface : str
        One of ``"normal"`` (default), ``"X"``, ``"H"``, ``"Y"``, ``"Z"``.

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
# Stereographic Projection
# ===================================================================

def stereographic_project(vectors, pole=None, azimuth_ref=None):
    """
    Project unit vectors onto a stereographic plane.

    Uses the standard projection: r = tan(delta/2) where delta is the
    polar angle from the pole direction.

    Parameters
    ----------
    vectors : ndarray (N, 3)
        Unit vectors to project.
    pole : ndarray (3,), optional
        Projection center direction (default [0, 0, 1]).
    azimuth_ref : ndarray (3,), optional
        Direction defining phi = 0.  If None, uses the x-axis projected
        perpendicular to the pole.

    Returns
    -------
    sx : ndarray (N,)
        Projected x coordinates.
    sy : ndarray (N,)
        Projected y coordinates.
    lower_hemisphere : ndarray (N,) bool
        True if the vector was in the lower hemisphere (negated before
        projection).
    """
    vectors = np.asarray(vectors, dtype=float)
    N = len(vectors)

    if pole is None:
        pole = np.array([0.0, 0.0, 1.0])
    else:
        pole = np.asarray(pole, dtype=float)
    pole = pole / np.linalg.norm(pole)

    # Build orthonormal frame: zhat = pole, xhat, yhat
    zhat = pole

    if azimuth_ref is not None:
        xhat = np.asarray(azimuth_ref, dtype=float)
        xhat = xhat - np.dot(xhat, zhat) * zhat
        xhat = xhat / np.linalg.norm(xhat)
    else:
        # Pick x-hat perpendicular to pole
        if abs(zhat[2]) < 0.9:
            up = np.array([0.0, 0.0, 1.0])
        else:
            up = np.array([1.0, 0.0, 0.0])
        xhat = up - np.dot(up, zhat) * zhat
        xhat = xhat / np.linalg.norm(xhat)

    yhat = np.cross(zhat, xhat)

    sx = np.zeros(N)
    sy = np.zeros(N)
    lower_hemisphere = np.zeros(N, dtype=bool)

    for i in range(N):
        g = vectors[i]
        g_norm = np.linalg.norm(g)
        if g_norm < 1e-12:
            continue
        g = g / g_norm

        cos_delta = np.dot(g, zhat)

        # If in lower hemisphere, negate
        if cos_delta < 0:
            g = -g
            cos_delta = -cos_delta
            lower_hemisphere[i] = True

        delta = np.arccos(np.clip(cos_delta, -1.0, 1.0))
        r = np.tan(delta / 2.0)

        dx = np.dot(g, xhat)
        dy = np.dot(g, yhat)
        phi = np.arctan2(dy, dx)

        sx[i] = r * np.cos(phi)
        sy[i] = r * np.sin(phi)

    return sx, sy, lower_hemisphere


# ===================================================================
# Wulff Net
# ===================================================================

def wulff_net_lines(step_deg=10, phi_rotation=0.0, n_points_per_line=91):
    """
    Generate Wulff net lines for stereographic projection overlay.

    Returns latitude lines (small circles) and longitude lines (great
    circles) at the given angular step.

    Parameters
    ----------
    step_deg : int
        Angular step in degrees.
    phi_rotation : float
        Azimuthal rotation of the net in degrees.
    n_points_per_line : int
        Number of points per line (controls smoothness).

    Returns
    -------
    list of dict
        Each dict has keys:
            'x': ndarray -- projected x coordinates (NaN-separated for gaps)
            'y': ndarray -- projected y coordinates
            'weight': float -- line weight (1.0, 0.3, or 0.09)
    """
    lines = []
    phi_rad = np.radians(phi_rotation)

    # Latitude lines: constant latitude, varying longitude
    for lat_deg in range(-90 + step_deg, 90, step_deg):
        lat_rad = np.radians(lat_deg)
        lon_range = np.linspace(-90, 90, n_points_per_line)

        pts_x = []
        pts_y = []
        for lon_deg in lon_range:
            lon_rad = np.radians(lon_deg)

            # Spherical to Cartesian
            gx = np.cos(lat_rad) * np.cos(lon_rad)
            gy = np.cos(lat_rad) * np.sin(lon_rad)
            gz = np.sin(lat_rad)

            # Stereographic projection (pole = [0,0,1])
            ge = np.sqrt(gx**2 + gy**2)
            if gz <= -1.0 + 1e-12:
                pts_x.append(np.nan)
                pts_y.append(np.nan)
                continue

            delta = np.arctan2(ge, abs(gz))
            if gz < 0:
                delta = np.pi - delta
            r = np.tan(delta / 2.0)

            if ge > 1e-12:
                phi = np.arctan2(gy, gx)
            else:
                phi = 0.0

            x_proj = r * np.cos(phi)
            y_proj = r * np.sin(phi)

            # Apply azimuthal rotation (Igor convention)
            x_rot = np.cos(phi_rad) * y_proj - np.sin(phi_rad) * x_proj
            y_rot = np.sin(phi_rad) * y_proj + np.cos(phi_rad) * x_proj

            pts_x.append(x_rot)
            pts_y.append(y_rot)

        weight = _line_weight(lat_deg, step_deg)
        lines.append({
            'x': np.array(pts_x),
            'y': np.array(pts_y),
            'weight': weight,
        })

    # Longitude lines: constant longitude, varying latitude
    for lon_deg in range(-90 + step_deg, 90, step_deg):
        lon_rad = np.radians(lon_deg)
        lat_range = np.linspace(-90, 90, n_points_per_line)

        pts_x = []
        pts_y = []
        for lat_deg_pt in lat_range:
            lat_rad = np.radians(lat_deg_pt)

            gx = np.cos(lat_rad) * np.cos(lon_rad)
            gy = np.cos(lat_rad) * np.sin(lon_rad)
            gz = np.sin(lat_rad)

            ge = np.sqrt(gx**2 + gy**2)
            if gz <= -1.0 + 1e-12:
                pts_x.append(np.nan)
                pts_y.append(np.nan)
                continue

            delta = np.arctan2(ge, abs(gz))
            if gz < 0:
                delta = np.pi - delta
            r = np.tan(delta / 2.0)

            if ge > 1e-12:
                phi = np.arctan2(gy, gx)
            else:
                phi = 0.0

            x_proj = r * np.cos(phi)
            y_proj = r * np.sin(phi)

            x_rot = np.cos(phi_rad) * y_proj - np.sin(phi_rad) * x_proj
            y_rot = np.sin(phi_rad) * y_proj + np.cos(phi_rad) * x_proj

            pts_x.append(x_rot)
            pts_y.append(y_rot)

        weight = _line_weight(lon_deg, step_deg)
        lines.append({
            'x': np.array(pts_x),
            'y': np.array(pts_y),
            'weight': weight,
        })

    return lines


def _line_weight(angle_deg, step_deg):
    """Determine Wulff net line weight based on angle."""
    angle = abs(angle_deg)
    if angle % 20 == 0:
        return 1.0   # black
    elif angle % 10 == 0:
        return 0.3   # gray
    else:
        return 0.09  # light gray


# ===================================================================
# Pole Figure Computation
# ===================================================================

def pole_figure_points(orientations, hkl_family, surface_normal=None,
                       surface_roll=None, surface_tilt=None):
    """
    Compute pole figure scatter points.

    For each grain orientation, transforms all symmetry-equivalent pole
    directions into the lab frame and stereographically projects them
    onto the sample surface plane.

    Parameters
    ----------
    orientations : ndarray (N, 3, 3)
        Orientation matrices (from ``batch_orientations``).
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

    for i, orient in enumerate(orientations):
        for pole_dir in hkl_family:
            # Transform pole to lab frame
            vec = orient @ pole_dir
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
            sin_theta = np.sqrt(1.0 - np.clip(dot_normal, 0, 1)**2)
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


# ===================================================================
# Stereographic zoom helper
# ===================================================================

def zoom_axis_range(zoom_deg):
    """
    Compute axis range for a given zoom angle.

    Parameters
    ----------
    zoom_deg : float
        Zoom angle in degrees (5-90).

    Returns
    -------
    float
        Axis limit d such that range is [-d, d].
    """
    theta_rad = np.radians(np.clip(zoom_deg, 1, 90))
    return np.tan(theta_rad / 2.0)


# ===================================================================
# Q-vector stereographic projection for single-step detail
# ===================================================================

def project_q_vectors(q_vectors, pole=None):
    """
    Project Q-vectors onto a stereographic plane for a single step.

    Parameters
    ----------
    q_vectors : ndarray (M, 3)
        Q-vectors (Qx, Qy, Qz) from indexed peaks.
    pole : ndarray (3,), optional
        Projection center direction (default [0, 0, 1]).

    Returns
    -------
    sx : ndarray (M,)
        Projected x coordinates.
    sy : ndarray (M,)
        Projected y coordinates.
    lower_hemisphere : ndarray (M,) bool
        True if the Q-vector was in the lower hemisphere.
    """
    # Normalize Q-vectors to unit length
    norms = np.linalg.norm(q_vectors, axis=1, keepdims=True)
    mask = norms.flatten() > 1e-12
    unit_q = np.zeros_like(q_vectors)
    unit_q[mask] = q_vectors[mask] / norms[mask]

    return stereographic_project(unit_q, pole=pole)
