"""
Orientation-to-color mapping for crystallographic visualization.

Three color schemes:
1. Cubic IPF standard triangle  (crystal direction -> RGB)
2. Rodrigues vector RGB          (rotation axis+angle -> RGB)
3. HSV color wheel               (polar position -> RGB)

Plus legend image generation for IPF triangle and HSV hexagon.

All algorithms derived from LaueGo Igor Pro source (xmlMultiIndex.ipf,
Utility_JZT.ipf).  Zero Dash/Plotly dependencies.
"""

import numpy as np


# ===================================================================
# Scheme 1: Cubic IPF Standard Triangle
# ===================================================================

def cubic_ipf_color(hkl):
    """
    Map crystal direction(s) to RGB using the cubic IPF standard triangle.

    Corner colors:
        (001) = Red,  (011) = Green,  (111) = Blue
        Center = White

    Only valid for cubic crystals (m-3m point group with 48-fold symmetry).

    Parameters
    ----------
    hkl : array-like (3,) or (N, 3)
        Crystal direction(s).

    Returns
    -------
    ndarray (3,) or (N, 3)
        RGB values in [0, 1].
    """
    hkl = np.asarray(hkl, dtype=float)
    single = hkl.ndim == 1

    if single:
        hkl = hkl.reshape(1, 3)

    rgb = np.zeros((len(hkl), 3))

    for i in range(len(hkl)):
        rgb[i] = _ipf_single(hkl[i])

    if single:
        return rgb[0]
    return rgb


def _ipf_single(vec):
    """Compute IPF color for a single hkl direction."""
    # Handle zero / NaN
    if np.any(np.isnan(vec)):
        return np.array([np.nan, np.nan, np.nan])

    norm = np.linalg.norm(vec)
    if norm < 1e-12:
        return np.array([0.0, 0.0, 0.0])  # black

    # Step 1: fold into positive octant (cubic 8-fold mirror)
    v = np.abs(vec)

    # Step 2: sort ascending to reduce permutations (cubic 6-fold permutation)
    # Result: 0 <= v[0] <= v[1] <= v[2]
    v = np.sort(v)

    # Step 3: normalize to unit length
    v = v / np.linalg.norm(v)

    # Step 4: triangle vertex directions (normalized)
    p001 = np.array([0.0, 0.0, 1.0])
    p011 = np.array([0.0, 1.0 / np.sqrt(2.0), 1.0 / np.sqrt(2.0)])
    p111 = np.array([1.0 / np.sqrt(3.0), 1.0 / np.sqrt(3.0), 1.0 / np.sqrt(3.0)])

    # Step 5: barycentric decomposition
    poles = np.column_stack([p001, p011, p111])  # 3x3
    coefs = np.linalg.solve(poles, v)  # 3 coefficients
    coefs = np.maximum(coefs, 0.0)  # clamp negatives

    # Step 6: saturate so max channel = 1.0
    max_c = np.max(coefs)
    if max_c < 1e-12:
        return np.array([0.0, 0.0, 0.0])

    rgb = coefs / max_c
    # R = coef for (001), G = coef for (011), B = coef for (111)
    return rgb


# ===================================================================
# Scheme 2: Rodrigues Vector RGB
# ===================================================================

def rodrigues_rgb(rodrigues_vec, max_angle_deg=None):
    """
    Map Rodrigues rotation vector(s) to RGB color.

    Color semantics:
        +X -> Red,    -X -> Cyan
        +Y -> Green,  -Y -> Magenta
        +Z -> Blue,   -Z -> Yellow
        Zero rotation -> Black

    Parameters
    ----------
    rodrigues_vec : ndarray (3,) or (N, 3)
        Rodrigues vector(s).
    max_angle_deg : float, optional
        Normalization angle in degrees. Default: 95th percentile of all
        rotation angles in the input.

    Returns
    -------
    ndarray (3,) or (N, 3)
        RGB values in [0, 1].
    """
    rodrigues_vec = np.asarray(rodrigues_vec, dtype=float)
    single = rodrigues_vec.ndim == 1

    if single:
        rodrigues_vec = rodrigues_vec.reshape(1, 3)

    N = len(rodrigues_vec)

    # Compute rotation angles
    lengths = np.linalg.norm(rodrigues_vec, axis=1)
    angles_deg = 2.0 * np.degrees(np.arctan(lengths))

    # Determine max angle for normalization
    if max_angle_deg is None:
        nonzero = angles_deg[angles_deg > 1e-6]
        if len(nonzero) > 0:
            max_angle_deg = np.percentile(nonzero, 95)
        else:
            max_angle_deg = 45.0  # fallback

    rgb = np.zeros((N, 3))

    for i in range(N):
        length = lengths[i]
        if length < 1e-12:
            continue  # black (0,0,0)

        axis = rodrigues_vec[i] / length
        angle = angles_deg[i]
        scaled = axis * (angle / max_angle_deg)
        scaled = np.clip(scaled, -1.0, 1.0)

        r, g, b = 0.0, 0.0, 0.0

        cx, cy, cz = scaled

        if cx > 0:
            r += cx
        else:
            g += abs(cx) / 2.0
            b += abs(cx) / 2.0

        if cy > 0:
            g += cy
        else:
            r += abs(cy) / 2.0
            b += abs(cy) / 2.0

        if cz > 0:
            b += cz
        else:
            r += abs(cz) / 2.0
            g += abs(cz) / 2.0

        rgb[i] = np.clip([r, g, b], 0.0, 1.0)

    if single:
        return rgb[0]
    return rgb


# ===================================================================
# Scheme 3: HSV Color Wheel
# ===================================================================

def hsv_wheel_color(dx, dy, rmax=1.0):
    """
    HSV-style color from position on a polar plot.

    Center = White.  Edge = fully saturated HSV color wheel.

    Parameters
    ----------
    dx, dy : float or ndarray
        Position relative to center.
    rmax : float
        Radius at full saturation.

    Returns
    -------
    ndarray (3,) or (N, 3)
        RGB values in [0, 1].
    """
    dx = np.asarray(dx, dtype=float)
    dy = np.asarray(dy, dtype=float)
    scalar = dx.ndim == 0

    if scalar:
        dx = dx.reshape(1)
        dy = dy.reshape(1)

    N = len(dx)
    rgb = np.ones((N, 3))  # default white

    for i in range(N):
        x, y = dx[i], dy[i]
        r = np.sqrt(x**2 + y**2)

        if r < 1e-12:
            continue  # white (1, 1, 1)

        saturation = min(1.0, r / rmax)
        hue = np.degrees(np.arctan2(y, x)) % 360.0

        # HSV to RGB (6-sector conversion)
        rgb[i] = _hsv_to_rgb(hue, saturation, 1.0)

    if scalar:
        return rgb[0]
    return rgb


def _hsv_to_rgb(h, s, v):
    """Standard HSV to RGB conversion."""
    sector = int(h / 60.0) % 6
    f = h / 60.0 - np.floor(h / 60.0)
    p = v * (1.0 - s)
    q = v * (1.0 - f * s)
    t = v * (1.0 - (1.0 - f) * s)

    if sector == 0:
        return np.array([v, t, p])
    elif sector == 1:
        return np.array([q, v, p])
    elif sector == 2:
        return np.array([p, v, t])
    elif sector == 3:
        return np.array([p, q, v])
    elif sector == 4:
        return np.array([t, p, v])
    else:  # sector == 5
        return np.array([v, p, q])


# ===================================================================
# Color Legend Generation
# ===================================================================

def make_cubic_ipf_triangle(resolution=256):
    """
    Generate the IPF standard triangle color key as an RGBA image.

    Pixel coordinates map to stereographic coordinates in the standard
    triangle: x in [0, sqrt(2)-1], y in [0, 1/(sqrt(3)+1)], y <= x.

    Parameters
    ----------
    resolution : int
        Image size in pixels (square).

    Returns
    -------
    ndarray (resolution, resolution, 4)
        RGBA image with uint8 values [0, 255].
    """
    x_max = np.sqrt(2.0) - 1.0  # ~0.4142
    y_max = 1.0 / (np.sqrt(3.0) + 1.0)  # ~0.3660

    image = np.zeros((resolution, resolution, 4), dtype=np.uint8)

    for j in range(resolution):
        for i in range(resolution):
            # Map pixel to stereographic coordinates
            x = i / (resolution - 1) * x_max
            y = (resolution - 1 - j) / (resolution - 1) * y_max  # y increases upward

            # Only fill inside the triangle: y <= x
            if y > x + 1e-6:
                continue

            # Inverse stereographic projection to get hkl from (x, y)
            denom = 1.0 + x**2 + y**2
            h = 2.0 * x / denom
            k = 2.0 * y / denom
            l = (1.0 - x**2 - y**2) / denom

            rgb = _ipf_single(np.array([h, k, l]))

            if not np.any(np.isnan(rgb)):
                image[j, i, 0] = int(np.clip(rgb[0] * 255, 0, 255))
                image[j, i, 1] = int(np.clip(rgb[1] * 255, 0, 255))
                image[j, i, 2] = int(np.clip(rgb[2] * 255, 0, 255))
                image[j, i, 3] = 255

    return image


def make_color_hexagon(resolution=512):
    """
    Generate a circular HSV color wheel image.

    Parameters
    ----------
    resolution : int
        Image size in pixels (square).

    Returns
    -------
    ndarray (resolution, resolution, 4)
        RGBA image with uint8 values [0, 255].
    """
    image = np.zeros((resolution, resolution, 4), dtype=np.uint8)
    center = (resolution - 1) / 2.0

    for j in range(resolution):
        for i in range(resolution):
            x = (i - center) / center  # map to [-1, 1]
            y = (center - j) / center  # y increases upward

            if x**2 + y**2 > 1.0:
                continue  # outside circle

            rgb = hsv_wheel_color(x, y, rmax=1.0)
            image[j, i, 0] = int(np.clip(rgb[0] * 255, 0, 255))
            image[j, i, 1] = int(np.clip(rgb[1] * 255, 0, 255))
            image[j, i, 2] = int(np.clip(rgb[2] * 255, 0, 255))
            image[j, i, 3] = 255

    return image


# ===================================================================
# Batch coloring for datasets
# ===================================================================

def batch_ipf_colors(crystal_directions):
    """
    Compute cubic IPF colors for an array of crystal directions.

    Parameters
    ----------
    crystal_directions : ndarray (N, 3)
        Crystal directions (from ``batch_crystal_directions``).

    Returns
    -------
    ndarray (N, 3)
        RGB values in [0, 1].  NaN rows produce [0.5, 0.5, 0.5] (gray).
    """
    N = len(crystal_directions)
    rgb = np.full((N, 3), 0.5)  # default gray for invalid

    for i in range(N):
        d = crystal_directions[i]
        if np.any(np.isnan(d)):
            continue
        rgb[i] = _ipf_single(d)

    return rgb


def batch_rodrigues_rgb(rodrigues_vecs, max_angle_deg=None):
    """
    Compute Rodrigues RGB colors for an array of Rodrigues vectors.

    Parameters
    ----------
    rodrigues_vecs : ndarray (N, 3)
        Rodrigues vectors.
    max_angle_deg : float, optional
        Normalization angle.

    Returns
    -------
    ndarray (N, 3)
        RGB values in [0, 1].
    """
    return rodrigues_rgb(rodrigues_vecs, max_angle_deg=max_angle_deg)


def rgb_to_plotly_colors(rgb_array):
    """
    Convert an (N, 3) float RGB array to a list of 'rgb(r,g,b)' strings
    for use with Plotly marker colors.

    Parameters
    ----------
    rgb_array : ndarray (N, 3)
        RGB values in [0, 1].

    Returns
    -------
    list of str
        Plotly-compatible color strings.
    """
    colors = []
    for i in range(len(rgb_array)):
        r = int(np.clip(rgb_array[i, 0] * 255, 0, 255))
        g = int(np.clip(rgb_array[i, 1] * 255, 0, 255))
        b = int(np.clip(rgb_array[i, 2] * 255, 0, 255))
        colors.append(f"rgb({r},{g},{b})")
    return colors
