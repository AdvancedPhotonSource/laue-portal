"""
Back-projection of indexed reciprocal-lattice solutions onto detector pixels.

This module is the Python port of LaueGo's ``q2pixel`` / ``pixel2XYZ`` /
``XYZ2pixel`` (``microGeometryN.ipf:1178-1430``) plus the per-image overlay
loop in ``xmlPixelinfoForMovies`` (``xmlMultiIndex.ipf:104-260``).  Given a
parsed indexed-XML solution and a :class:`~laue_portal.analysis.geometry.
BeamlineGeometry`, it returns measured and predicted pixel positions ready
for plotting on top of the detector image.

Zero Dash / Plotly dependencies; all coordinates are NumPy arrays.

Coordinate conventions
----------------------
- Pixels are **full-chip, un-binned, zero-based** throughout the math.
- A separate helper, :func:`full_to_roi`, converts to the binned / ROI
  pixel system used by ``<Xpixel>`` / ``<Ypixel>`` arrays in the XML
  whenever an ROI is in effect.  For the common
  ``startx=0, groupx=1, starty=0, groupy=1`` case this is the identity.
- Incident beam direction ``ki = (0, 0, 1)`` (hard-coded in Igor too).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

from laue_portal.analysis.geometry import BeamlineGeometry, DetectorGeometry

_KI = np.array([0.0, 0.0, 1.0])


# ---------------------------------------------------------------------------
# Core math: detector ↔ XYZ / Q
# ---------------------------------------------------------------------------


def pixel_to_xyz(d: DetectorGeometry, px: float, py: float) -> np.ndarray:
    """
    Convert detector pixel ``(px, py)`` to a point in the beam-line frame.

    Port of Igor's ``pixel2XYZ`` (``microGeometryN.ipf:1353-1371``).
    Distortion correction (``peakCorrect``) is **not** applied -- we rely
    on the indexer having already used the same un-distorted convention
    that the geometry file expresses.

    Parameters
    ----------
    d : DetectorGeometry
    px, py : float
        Pixel position, full-chip un-binned, zero-based.

    Returns
    -------
    ndarray (3,)
        Position in beam-line coordinates (mm).
    """
    xp = (px - 0.5 * (d.Nx - 1)) * d.sizeX / d.Nx + d.P[0]
    yp = (py - 0.5 * (d.Ny - 1)) * d.sizeY / d.Ny + d.P[1]
    zp = d.P[2]
    return d.rho @ np.array([xp, yp, zp])


def xyz_to_pixel(
    d: DetectorGeometry,
    xyz,
    depth: float = 0.0,
    on_detector: bool = False,
) -> Tuple[float, float]:
    """
    Project a beam-line-frame ray ``xyz`` onto the detector.

    Port of Igor's ``XYZ2pixel`` (``microGeometryN.ipf:1374-1430``).
    Returns ``(NaN, NaN)`` if the ray points away from the detector or
    (when ``on_detector=True``) the intersection falls outside the chip.

    Parameters
    ----------
    d : DetectorGeometry
    xyz : array-like (3,)
        Point or direction in beam-line frame.  Magnitude does not
        matter -- only the ray ``origin + t * xyz`` is used.
    depth : float
        Optional sample depth along the beam (microns / mm depending on
        the rest of your units).  Set to 0 to ignore.
    on_detector : bool
        When True, return NaN for pixels outside the chip.

    Returns
    -------
    (px, py) : tuple of float
        Full-chip un-binned zero-based pixel coordinates.
    """
    xyz = np.asarray(xyz, dtype=float).reshape(3)
    x, y, z = xyz

    # Transform into prime (detector-rotated) space:
    #   xyz' = rho^T · xyz  -  P  (Igor uses rho^T via row indexing)
    xp = d.rho[0, 0] * x + d.rho[1, 0] * y + d.rho[2, 0] * z - d.P[0]
    yp = d.rho[0, 1] * x + d.rho[1, 1] * y + d.rho[2, 1] * z - d.P[1]
    zp = d.rho[0, 2] * x + d.rho[1, 2] * y + d.rho[2, 2] * z - d.P[2]

    dxp = -d.P[0] - xp
    dyp = -d.P[1] - yp
    dzp = -d.P[2] - zp

    if depth:
        xp += d.rho[2, 0] * depth
        yp += d.rho[2, 1] * depth
        zp += d.rho[2, 2] * depth

    if dzp == 0:
        return float("nan"), float("nan")
    t = -zp / dzp
    if t > 1:  # ray goes backwards through the origin -- not visible
        return float("nan"), float("nan")

    x_out = xp + t * dxp
    y_out = yp + t * dyp
    px = x_out / d.sizeX * d.Nx + 0.5 * (d.Nx - 1)
    py = y_out / d.sizeY * d.Ny + 0.5 * (d.Ny - 1)

    if on_detector:
        if not (0 <= px <= d.Nx - 0.5):
            px = float("nan")
        if not (0 <= py <= d.Ny - 0.5):
            py = float("nan")
    return float(px), float(py)


def q_to_pixel(
    d: DetectorGeometry,
    qvec,
    depth: float = 0.0,
    on_detector: bool = False,
) -> Tuple[float, float]:
    """
    Predict the pixel where a reflection with reciprocal-space vector
    ``qvec`` would land on detector ``d``.

    Port of Igor's ``q2pixel`` (``microGeometryN.ipf:1178-1198``).  The
    Q-vector does *not* need to be normalised; only its direction is used
    because the reflection's Bragg angle is recovered from ``qhat · ki``.

    Parameters
    ----------
    d : DetectorGeometry
    qvec : array-like (3,)
    depth : float, optional
        Sample depth along the beam (mm, optional).  ``NaN`` is accepted
        and treated as 0 to match Igor's behaviour.
    on_detector : bool
        Return NaN for predictions outside the detector chip.

    Returns
    -------
    (px, py) : tuple of float
        Full-chip un-binned zero-based pixel coordinates.  ``(NaN, NaN)``
        when the reflection cannot reach the detector (Bragg angle ≤ 0
        or ray goes backwards through the origin).
    """
    q = np.asarray(qvec, dtype=float).reshape(3)
    q_norm = np.linalg.norm(q)
    if q_norm == 0.0:
        return float("nan"), float("nan")
    qhat = q / q_norm

    # |q_full| from kf = q + ki and the Bragg condition: q · -ki > 0.
    q_len = -2.0 * float(qhat @ _KI)
    if q_len < 0:  # reflection from behind the sample -- discard
        return float("nan"), float("nan")
    kout = qhat * q_len + _KI

    if depth is None or np.isnan(depth):
        depth_eff = 0.0
    else:
        depth_eff = float(depth)
    return xyz_to_pixel(d, kout, depth=depth_eff, on_detector=on_detector)


def q_to_pixel_batch(
    d: DetectorGeometry,
    qvecs: np.ndarray,
    depth: float = 0.0,
    on_detector: bool = False,
) -> np.ndarray:
    """
    Vectorised :func:`q_to_pixel`.

    Parameters
    ----------
    d : DetectorGeometry
    qvecs : ndarray (N, 3)
        Reciprocal-space vectors.
    depth, on_detector : see :func:`q_to_pixel`.

    Returns
    -------
    ndarray (N, 2)
        Columns ``[px, py]`` in full-chip un-binned pixels.  Rows are
        ``(NaN, NaN)`` for reflections that cannot reach the detector.
    """
    qvecs = np.asarray(qvecs, dtype=float)
    if qvecs.ndim == 1:
        qvecs = qvecs[None, :]
    out = np.full((qvecs.shape[0], 2), np.nan)
    for i in range(qvecs.shape[0]):
        out[i] = q_to_pixel(d, qvecs[i], depth=depth, on_detector=on_detector)
    return out


# ---------------------------------------------------------------------------
# ROI / binning helpers
# ---------------------------------------------------------------------------


@dataclass
class ROI:
    """Detector ROI / binning, mirroring the ``<ROI .../>`` XML attributes.

    The defaults (``startx=0``, ``groupx=1`` etc.) describe the most
    common "full chip, no binning" case where the ROI / binned pixel
    system matches the full-chip system used by the geometry math.
    """

    startx: int = 0
    endx: int = 0
    groupx: int = 1
    starty: int = 0
    endy: int = 0
    groupy: int = 1

    @classmethod
    def from_attrib(cls, attrib: dict) -> "ROI":
        def _as_int(key, default):
            try:
                return int(float(attrib.get(key, default)))
            except (TypeError, ValueError):
                return int(default)

        return cls(
            startx=_as_int("startx", 0),
            endx=_as_int("endx", 0),
            groupx=_as_int("groupx", 1),
            starty=_as_int("starty", 0),
            endy=_as_int("endy", 0),
            groupy=_as_int("groupy", 1),
        )

    @property
    def is_identity(self) -> bool:
        return self.startx == 0 and self.starty == 0 and self.groupx == 1 and self.groupy == 1


def full_to_roi(px: np.ndarray, py: np.ndarray, roi: ROI) -> Tuple[np.ndarray, np.ndarray]:
    """
    Convert full-chip un-binned pixel coordinates to the ROI / binned
    coordinates used by the indexed XML ``<Xpixel>`` / ``<Ypixel>`` lists.

    Mirrors ``xmlPixelinfoForMovies`` (``xmlMultiIndex.ipf`` line block
    around the ``startx / groupx`` arithmetic): for non-trivial binning,

        roi = (full - start - (group - 1) / 2) / group

    For ``startx=0, groupx=1`` (the default) this is the identity.
    """
    px_r = (np.asarray(px, dtype=float) - roi.startx - (roi.groupx - 1) / 2.0) / roi.groupx
    py_r = (np.asarray(py, dtype=float) - roi.starty - (roi.groupy - 1) / 2.0) / roi.groupy
    return px_r, py_r


# ---------------------------------------------------------------------------
# Per-step overlay assembly (the "visualisation data prep" function)
# ---------------------------------------------------------------------------


@dataclass
class PatternOverlay:
    """
    Back-projected and measured peaks for one indexed pattern (grain).

    All pixel coordinates are in **ROI / binned** units (i.e. the same
    units as the measured ``<Xpixel>`` / ``<Ypixel>`` arrays).  See
    :func:`full_to_roi` for the conversion.
    """

    pattern_num: int = 0
    rms_error: float = float("nan")
    goodness: float = float("nan")
    n_indexed: int = 0
    # Indexed reflections (one row per (h,k,l) the indexer solved for):
    hkl: np.ndarray = field(default_factory=lambda: np.zeros((0, 3), dtype=int))
    predicted_xy: np.ndarray = field(default_factory=lambda: np.zeros((0, 2)))
    # XML PkIndex values: index into the parent measured-peaks array for each
    # indexed reflection (``-1`` if the XML did not provide a valid mapping).
    measured_index: np.ndarray = field(default_factory=lambda: np.zeros((0,), dtype=int))
    # Reserved for optional projection-residual diagnostics. Classification
    # does not use pixel proximity.
    match_distance: np.ndarray = field(default_factory=lambda: np.zeros((0,)))


@dataclass
class MissingSpotOverlay:
    """Simulated reflections not already represented by indexed peaks."""

    pattern_num: int = 0
    hkl: np.ndarray = field(default_factory=lambda: np.zeros((0, 3), dtype=int))
    predicted_xy: np.ndarray = field(default_factory=lambda: np.zeros((0, 2)))
    energy_kev: np.ndarray = field(default_factory=lambda: np.zeros((0,)))


@dataclass
class StepOverlay:
    """All data required to render the detector overlay for one step."""

    step_index: int = 0
    detector_id: str = ""
    detector_index: int = -1  # index into BeamlineGeometry.detectors, or -1
    Nx: int = 0
    Ny: int = 0
    roi: ROI = field(default_factory=ROI)
    image_path: Optional[str] = None
    # Measured peaks from <peaksXY>, in ROI / binned pixels.
    measured_xy: np.ndarray = field(default_factory=lambda: np.zeros((0, 2)))
    measured_intensity: np.ndarray = field(default_factory=lambda: np.zeros((0,)))
    # True where the measured peak is referenced by any XML PkIndex value.
    measured_indexed_mask: np.ndarray = field(default_factory=lambda: np.zeros((0,), dtype=bool))
    patterns: List[PatternOverlay] = field(default_factory=list)
    missing_spots: List[MissingSpotOverlay] = field(default_factory=list)
    # Diagnostics
    warnings: List[str] = field(default_factory=list)


def build_step_overlay(
    parsed: dict,
    step_index: int,
    geometry: BeamlineGeometry,
    match_tolerance_px: float | None = None,
    simulate_missing: bool = False,
    missing_energy_range_kev: Tuple[float, float] = (6.0, 30.0),
    missing_hkl_limit: int = 12,
) -> Optional[StepOverlay]:
    """
    Back-project indexed reflections for one step and classify measured peaks
    using the XML ``PkIndex`` assignments.

    Projection math follows Igor's ``xmlPixelinfoForMovies``
    (``xmlMultiIndex.ipf:104-260``), but measured indexed/un-indexed status is
    not inferred from nearest-neighbour pixel distance.

    Parameters
    ----------
    parsed : dict
        Output of :func:`laue_portal.analysis.xml_parser.parse_indexing_xml`.
    step_index : int
        Index of the step to process.
    geometry : BeamlineGeometry
        Detector geometry (resolved via
        :func:`laue_portal.analysis.geometry.resolve_geometry_for_indexing`).
    match_tolerance_px : float | None
        Deprecated no-op. Indexed/un-indexed measured peak classification is
        authoritative from XML ``PkIndex`` values, not pixel proximity.
    simulate_missing : bool
        When true, enumerate candidate HKLs in the indexed lattice and keep
        on-detector reflections that are not already indexed/matched.
    missing_energy_range_kev : tuple[float, float]
        Energy window used by the lightweight missing-spot enumerator.
    missing_hkl_limit : int
        Enumerate integer HKLs in ``[-limit, limit]`` for each axis.

    Returns
    -------
    StepOverlay | None
        ``None`` if the step has no measured peaks *and* no indexed
        reflections (nothing to show).
    """
    from laue_portal.analysis.xml_parser import get_step_peaks

    step_peaks = get_step_peaks(parsed, step_index)
    if step_peaks is None:
        return None

    overlay = StepOverlay(step_index=step_index)
    overlay.image_path = step_peaks.get("input_image")

    # ── Detector resolution ──────────────────────────────────────────
    detector_id = ""
    det_attr_el = parsed["_steps"][step_index].get("detector_el")
    if det_attr_el is not None:
        det_id_el = det_attr_el.find("detectorID")
        if det_id_el is not None and det_id_el.text:
            detector_id = det_id_el.text.strip()
    overlay.detector_id = detector_id

    detector: Optional[DetectorGeometry] = geometry.detector_by_id(detector_id)
    if detector is None and geometry.detectors:
        # Fall back to detector 0 -- matches Igor's behaviour when the
        # detector ID isn't found.
        detector = geometry.detectors[0]
        overlay.warnings.append(
            f"Detector ID {detector_id!r} not found in geometry; "
            f"falling back to first detector ({detector.detector_id!r})."
        )
    if detector is None:
        overlay.warnings.append("No detectors in geometry; cannot back-project.")
        return overlay

    overlay.detector_index = geometry.detectors.index(detector)
    overlay.Nx = detector.Nx
    overlay.Ny = detector.Ny

    # ── ROI ──────────────────────────────────────────────────────────
    if det_attr_el is not None:
        roi_el = det_attr_el.find("ROI")
        if roi_el is not None:
            overlay.roi = ROI.from_attrib(roi_el.attrib)

    # ── Measured peaks ───────────────────────────────────────────────
    px_meas = step_peaks.get("pixel_positions")
    if px_meas is None:
        px_meas = np.zeros((0, 2))
    overlay.measured_xy = np.asarray(px_meas, dtype=float)

    intens = step_peaks.get("intensities")
    if intens is None:
        overlay.measured_intensity = np.zeros((len(overlay.measured_xy),))
    else:
        overlay.measured_intensity = np.asarray(intens, dtype=float)

    overlay.measured_indexed_mask = np.zeros(len(overlay.measured_xy), dtype=bool)

    # ── Per-pattern back-projection ──────────────────────────────────
    depth = float(parsed["depths"][step_index])
    if np.isnan(depth):
        depth = 0.0

    for pat in step_peaks.get("patterns", []):
        recip = pat.get("recip_lattice")
        hkl = pat.get("hkl")
        if recip is None or hkl is None or len(hkl) == 0:
            continue

        # Python stores a*, b*, c* as rows of ``recip``.  q = recip.T · hkl
        # gives the Q-vector in the beam-line frame:
        #   q = h * a* + k * b* + l * c*
        hkl = np.asarray(hkl, dtype=float)
        qvecs = hkl @ recip  # (N, 3) -- recip.T applied row-wise

        # Predict in full-chip un-binned pixels, then transform to ROI
        # coordinates for display. This does not classify measured peaks.
        full_xy = q_to_pixel_batch(detector, qvecs, depth=depth)
        px_roi, py_roi = full_to_roi(full_xy[:, 0], full_xy[:, 1], overlay.roi)
        pred_xy = np.column_stack([px_roi, py_roi])

        n_idx = len(pred_xy)
        measured_index = _valid_pk_indices(pat.get("peak_indices"), n_idx, len(overlay.measured_xy))
        match_dist = np.full(n_idx, np.nan)
        if len(measured_index):
            overlay.measured_indexed_mask[measured_index[measured_index >= 0]] = True

        pattern_overlay = PatternOverlay(
            pattern_num=int(pat.get("pattern_num", 0)),
            rms_error=float(pat.get("rms_error", float("nan"))),
            goodness=float(pat.get("goodness", float("nan"))),
            n_indexed=int(pat.get("n_indexed", 0)),
            hkl=hkl.astype(int),
            predicted_xy=pred_xy,
            measured_index=measured_index,
            match_distance=match_dist,
        )
        overlay.patterns.append(pattern_overlay)

        if simulate_missing:
            missing = _simulate_missing_spots(
                pattern_overlay,
                detector,
                overlay,
                np.asarray(recip, dtype=float),
                depth=depth,
                energy_range_kev=missing_energy_range_kev,
                hkl_limit=missing_hkl_limit,
                space_group=parsed.get("space_group"),
            )
            overlay.missing_spots.append(missing)

    return overlay


def _valid_pk_indices(pk_indices, n_hkl: int, n_measured: int) -> np.ndarray:
    """Return XML PkIndex values aligned to the HKL array, with invalids as -1."""
    measured_index = -np.ones(n_hkl, dtype=int)
    if pk_indices is None:
        return measured_index
    values = np.asarray(pk_indices, dtype=int).reshape(-1)
    n = min(n_hkl, len(values))
    if n == 0:
        return measured_index
    valid = (values[:n] >= 0) & (values[:n] < n_measured)
    measured_index[:n][valid] = values[:n][valid]
    return measured_index


def _simulate_missing_spots(
    pattern: PatternOverlay,
    detector: DetectorGeometry,
    overlay: StepOverlay,
    recip: np.ndarray,
    *,
    depth: float,
    energy_range_kev: Tuple[float, float],
    hkl_limit: int,
    space_group: int | None = None,
) -> MissingSpotOverlay:
    """Lightweight candidate-reflection enumerator for missing spot display."""
    hkl_candidates = _enumerate_hkl(int(hkl_limit))
    hkl_candidates = hkl_candidates[_centering_allowed_mask(hkl_candidates, space_group)]
    if len(hkl_candidates) == 0:
        return MissingSpotOverlay(pattern_num=pattern.pattern_num)
    qvecs = hkl_candidates @ recip
    full_xy = q_to_pixel_batch(detector, qvecs, depth=depth)
    px_roi, py_roi = full_to_roi(full_xy[:, 0], full_xy[:, 1], overlay.roi)
    pred_xy = np.column_stack([px_roi, py_roi])

    q_norm = np.linalg.norm(qvecs, axis=1)
    qhat_z = np.full(len(q_norm), np.nan)
    nonzero = q_norm > 0
    qhat_z[nonzero] = qvecs[nonzero, 2] / q_norm[nonzero]
    sin_theta = -qhat_z
    energy = np.full(len(q_norm), np.nan)
    valid_theta = sin_theta > 0
    # The XML reciprocal lattice is in 1/nm; hc is keV*nm.
    energy[valid_theta] = q_norm[valid_theta] * 1.2398419739 / (4.0 * np.pi * sin_theta[valid_theta])

    emin, emax = sorted((float(energy_range_kev[0]), float(energy_range_kev[1])))
    x_max = (overlay.roi.endx - overlay.roi.startx) / overlay.roi.groupx if overlay.roi.endx else overlay.Nx
    y_max = (overlay.roi.endy - overlay.roi.starty) / overlay.roi.groupy if overlay.roi.endy else overlay.Ny
    finite = np.isfinite(pred_xy[:, 0]) & np.isfinite(pred_xy[:, 1]) & np.isfinite(energy)
    on_chip = finite & (pred_xy[:, 0] >= 0) & (pred_xy[:, 1] >= 0) & (pred_xy[:, 0] <= x_max) & (pred_xy[:, 1] <= y_max)
    in_energy = (energy >= emin) & (energy <= emax)
    keep = on_chip & in_energy

    if not np.any(keep):
        return MissingSpotOverlay(pattern_num=pattern.pattern_num)

    indexed_hkl = {tuple(map(int, hkl)) for hkl in pattern.hkl}
    missing_idx = []

    for idx in np.where(keep)[0]:
        hkl = tuple(map(int, hkl_candidates[idx]))
        if hkl in indexed_hkl:
            continue
        missing_idx.append(idx)

    if not missing_idx:
        return MissingSpotOverlay(pattern_num=pattern.pattern_num)

    idx = _deduplicate_by_direction(np.asarray(missing_idx, dtype=int), qvecs, energy)
    return MissingSpotOverlay(
        pattern_num=pattern.pattern_num,
        hkl=hkl_candidates[idx].astype(int),
        predicted_xy=pred_xy[idx],
        energy_kev=energy[idx],
    )


def _deduplicate_by_direction(indices: np.ndarray, qvecs: np.ndarray, energy: np.ndarray) -> np.ndarray:
    """Collapse harmonic reflections that share the same scattering direction."""
    by_direction: dict[tuple[int, int, int], int] = {}
    for idx in indices:
        q = qvecs[idx]
        norm = float(np.linalg.norm(q))
        if norm == 0.0 or not np.isfinite(norm):
            continue
        key = tuple(int(v) for v in np.trunc((q / norm) * 1e5))
        prev = by_direction.get(key)
        if prev is None or energy[idx] < energy[prev]:
            by_direction[key] = int(idx)
    return np.array(sorted(by_direction.values(), key=lambda i: energy[i]), dtype=int)


def _enumerate_hkl(limit: int) -> np.ndarray:
    """Return all integer HKLs in a cube around zero, excluding 000."""
    limit = max(1, int(limit))
    values = np.arange(-limit, limit + 1, dtype=int)
    grid = np.stack(np.meshgrid(values, values, values, indexing="ij"), axis=-1).reshape(-1, 3)
    return grid[np.any(grid != 0, axis=1)]


def _centering_allowed_mask(hkl: np.ndarray, space_group: int | None) -> np.ndarray:
    """Apply lattice-centering systematic absences for common space groups."""
    hkl = np.asarray(hkl, dtype=int)
    if hkl.size == 0:
        return np.zeros((0,), dtype=bool)
    try:
        sg = int(space_group)
    except (TypeError, ValueError):
        return np.ones(len(hkl), dtype=bool)

    h = hkl[:, 0]
    k = hkl[:, 1]
    l = hkl[:, 2]
    parity = np.mod(hkl, 2)

    if _space_group_is_face_centered(sg):
        return (parity[:, 0] == parity[:, 1]) & (parity[:, 1] == parity[:, 2])
    if _space_group_is_body_centered(sg):
        return np.mod(h + k + l, 2) == 0
    if _space_group_is_base_centered(sg):
        return np.mod(h + k, 2) == 0
    if _space_group_is_r_centered_hex(sg):
        return np.mod(-h + k + l, 3) == 0
    return np.ones(len(hkl), dtype=bool)


def _space_group_is_face_centered(space_group: int) -> bool:
    return space_group in {
        22,
        42,
        43,
        69,
        70,
        196,
        202,
        203,
        209,
        210,
        216,
        219,
        225,
        226,
        227,
        228,
    }


def _space_group_is_body_centered(space_group: int) -> bool:
    return space_group in {
        23,
        24,
        44,
        45,
        46,
        71,
        72,
        73,
        74,
        79,
        80,
        82,
        87,
        88,
        97,
        98,
        107,
        108,
        109,
        110,
        119,
        120,
        121,
        122,
        139,
        140,
        141,
        142,
        197,
        199,
        204,
        206,
        211,
        214,
        217,
        220,
        229,
        230,
    }


def _space_group_is_base_centered(space_group: int) -> bool:
    return space_group in {5, 8, 9, 12, 15, 20, 21, 35, 36, 37, 38, 39, 40, 41, 63, 64, 65, 66, 67, 68}


def _space_group_is_r_centered_hex(space_group: int) -> bool:
    return space_group in {146, 148, 155, 160, 161, 166, 167}


def overlay_statistics(overlay: StepOverlay) -> dict:
    """Convenience summary used by the visualisation UI."""
    n_meas = len(overlay.measured_xy)
    n_indexed = int(overlay.measured_indexed_mask.sum())
    by_pattern = []
    missing_by_pattern = {missing.pattern_num: len(missing.predicted_xy) for missing in overlay.missing_spots}
    for pat in overlay.patterns:
        n_matched = int(np.sum(pat.measured_index >= 0))
        n_predicted = len(pat.predicted_xy)
        # "On detector" count -- only finite predictions within ROI bounds.
        if n_predicted:
            px = pat.predicted_xy[:, 0]
            py = pat.predicted_xy[:, 1]
            x_max = (overlay.roi.endx - overlay.roi.startx) / overlay.roi.groupx if overlay.roi.endx else overlay.Nx
            y_max = (overlay.roi.endy - overlay.roi.starty) / overlay.roi.groupy if overlay.roi.endy else overlay.Ny
            in_bounds = np.isfinite(px) & np.isfinite(py) & (px >= 0) & (py >= 0) & (px <= x_max) & (py <= y_max)
            n_on = int(in_bounds.sum())
        else:
            n_on = 0
        by_pattern.append(
            {
                "pattern_num": pat.pattern_num,
                "n_indexed": pat.n_indexed,
                "n_predicted": n_predicted,
                "n_predicted_on_detector": n_on,
                "n_matched": n_matched,
                "n_missing": int(missing_by_pattern.get(pat.pattern_num, 0)),
                "rms_error": pat.rms_error,
                "goodness": pat.goodness,
                "n_pkindex": n_matched,
            }
        )
    return {
        "n_measured": n_meas,
        "n_indexed": n_indexed,
        "indexed_fraction": (n_indexed / n_meas) if n_meas else 0.0,
        "patterns": by_pattern,
    }
