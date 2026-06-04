"""
Detector geometry: parse the LaueGo ``geoN_*.xml`` file format and compute
the rotation matrix ``rho`` used by the back-projection math.

This module is the Python equivalent of Igor Pro's ``detectorGeometry``
struct (LaueGo ``microGeometryN.ipf:594-660``) and the
``DetectorUpdateCalc`` routine (``microGeometryN.ipf:1674-1701``).

Zero Dash / Plotly dependencies.

Coordinate convention (beam-line frame, matching LaueGo):
    +X = outboard (away from storage ring centre)
    +Y = vertically up
    +Z = downstream (along the incident beam)

The detector R vector is an axis-angle rotation 3-vector: its direction
is the rotation axis and its magnitude is the rotation angle in radians.
``rho`` is the resulting 3x3 rotation matrix that maps detector-frame
coordinates ``(x', y', z') + P`` into beam-line coordinates ``(X, Y, Z)``:

    XYZ = rho · ((x', y', z') + P)

i.e. detector pixels are first translated by ``P`` (mm) then rotated by
``rho``.  See LaueGo ``microGeometryN.ipf:1353-1371`` (``pixel2XYZ``).
"""

from __future__ import annotations

import functools
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class DetectorGeometry:
    """
    Geometry for one detector panel.

    Mirrors the relevant fields of Igor's ``detectorGeometry`` struct
    (LaueGo ``microGeometryN.ipf:594-660``).  Pixel coordinates throughout
    are **full-chip, un-binned, zero-based** -- the same convention used by
    ``XYZ2pixel`` / ``pixel2XYZ`` in LaueGo and by the ``<Xpixel>`` /
    ``<Ypixel>`` arrays inside the indexed XML.
    """

    # Identity ------------------------------------------------------------
    detector_id: str = ""  # XML <ID> / <detectorID>
    used: bool = True  # XML "used" flag (defaults to True)

    # Physical size -------------------------------------------------------
    Nx: int = 2048  # number of un-binned pixels in X
    Ny: int = 2048  # number of un-binned pixels in Y
    sizeX: float = 409.6  # detector outer size X (mm)
    sizeY: float = 409.6  # detector outer size Y (mm)

    # Pose: rotation + translation (in beam-line frame) -------------------
    R: np.ndarray = field(default_factory=lambda: np.zeros(3))  # axis-angle (rad)
    P: np.ndarray = field(default_factory=lambda: np.zeros(3))  # translation (mm)

    # Derived 3x3 rotation matrix.  Populated by ``update_rho()`` which
    # must be called after assigning R.
    rho: np.ndarray = field(default_factory=lambda: np.eye(3))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def update_rho(self) -> None:
        """Recompute ``rho`` from the axis-angle vector ``R``.

        Port of Igor Pro's ``DetectorUpdateCalc`` (LaueGo
        ``microGeometryN.ipf:1674-1701``) -- standard Rodrigues' rotation
        formula.
        """
        self.rho = rho_from_R(self.R)

    def __post_init__(self) -> None:
        self.R = np.asarray(self.R, dtype=float).reshape(3)
        self.P = np.asarray(self.P, dtype=float).reshape(3)
        self.update_rho()


@dataclass
class BeamlineGeometry:
    """Top-level container for one or more detectors plus sample/wire info.

    Only the fields required by the back-projection visualisation are
    populated; sample/wire fields are kept for forward compatibility but
    are currently unused by ``back_projection.q2pixel``.
    """

    detectors: List[DetectorGeometry] = field(default_factory=list)
    sample_origin: np.ndarray = field(default_factory=lambda: np.zeros(3))
    sample_R: np.ndarray = field(default_factory=lambda: np.zeros(3))

    def detector_by_id(self, detector_id: str) -> Optional[DetectorGeometry]:
        """Return the detector whose ``<ID>`` matches the indexed-XML
        ``<detectorID>`` field, or ``None`` if not found.

        Comparison is case-insensitive and ignores surrounding whitespace
        -- the indexed XML occasionally adds trailing spaces.
        """
        if not detector_id:
            return None
        key = detector_id.strip().lower()
        for d in self.detectors:
            if d.detector_id.strip().lower() == key:
                return d
        return None


# ---------------------------------------------------------------------------
# Rotation helpers
# ---------------------------------------------------------------------------


def rho_from_R(R) -> np.ndarray:
    """
    Build a 3x3 rotation matrix from an axis-angle 3-vector ``R``.

    The direction of ``R`` is the rotation axis; its magnitude is the
    rotation angle in radians.  Identical to Igor Pro's Rodrigues
    formula at LaueGo ``microGeometryN.ipf:1697-1699``.

    Parameters
    ----------
    R : array-like (3,)
        Axis-angle vector (rad).

    Returns
    -------
    ndarray (3, 3)
    """
    R = np.asarray(R, dtype=float).reshape(3)
    theta = float(np.linalg.norm(R))
    if theta == 0.0:
        return np.eye(3)
    c = np.cos(theta)
    s = np.sin(theta)
    c1 = 1.0 - c
    Rx, Ry, Rz = R / theta
    return np.array(
        [
            [c + Rx * Rx * c1, Rx * Ry * c1 - Rz * s, Ry * s + Rx * Rz * c1],
            [Rz * s + Rx * Ry * c1, c + Ry * Ry * c1, -Rx * s + Ry * Rz * c1],
            [-Ry * s + Rx * Rz * c1, Rx * s + Ry * Rz * c1, c + Rz * Rz * c1],
        ]
    )


# ---------------------------------------------------------------------------
# XML parsing (LaueGo geoN_*.xml format)
# ---------------------------------------------------------------------------


# The 34ID-E geoN files use an XML default namespace; ElementTree returns
# tags as ``{uri}localname``.  Strip the namespace so callers can use the
# bare tag names.
def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _find_local(parent, name: str):
    """Find a direct child by local tag name (namespace-agnostic)."""
    for child in parent:
        if _strip_ns(child.tag) == name:
            return child
    return None


def _findall_local(parent, name: str):
    return [c for c in parent if _strip_ns(c.tag) == name]


def _floats(text: str) -> np.ndarray:
    """Parse whitespace-separated floats; empty / None → empty array."""
    if not text:
        return np.array([])
    return np.fromstring(text.strip(), sep=" ")


def _text_of(parent, name: str) -> Optional[str]:
    el = _find_local(parent, name)
    if el is None or el.text is None:
        return None
    return el.text.strip() or None


@functools.lru_cache(maxsize=8)
def _cached_parse_geometry(path: str, mtime_ns: int) -> BeamlineGeometry:
    """LRU-cached implementation; ``mtime_ns`` is purely a cache key."""
    return _parse_geometry_xml_impl(path)


def parse_geometry_xml(xml_path: str) -> BeamlineGeometry:
    """
    Parse a LaueGo ``geoN_*.xml`` file into a :class:`BeamlineGeometry`.

    Cached in-process on ``(path, mtime)`` so multiple visualisation
    callbacks pointing at the same geometry only pay the parse cost once.

    Parameters
    ----------
    xml_path : str
        Path to a geoN-style XML file (default-namespaced
        ``http://sector34.xray.aps.anl.gov/34ide/geoN``).

    Returns
    -------
    BeamlineGeometry
    """
    xml_path = str(xml_path)
    try:
        mtime_ns = os.stat(xml_path).st_mtime_ns
    except OSError:
        return _parse_geometry_xml_impl(xml_path)
    return _cached_parse_geometry(xml_path, mtime_ns)


def _parse_geometry_xml_impl(xml_path: str) -> BeamlineGeometry:
    tree = ET.parse(xml_path)
    root = tree.getroot()

    geom = BeamlineGeometry()

    # ── Sample ────────────────────────────────────────────────────────
    sample_el = _find_local(root, "Sample")
    if sample_el is not None:
        origin = _floats(_text_of(sample_el, "Origin") or "")
        if origin.size == 3:
            geom.sample_origin = origin
        rvec = _floats(_text_of(sample_el, "R") or "")
        if rvec.size == 3:
            geom.sample_R = rvec

    # ── Detectors ─────────────────────────────────────────────────────
    detectors_el = _find_local(root, "Detectors")
    if detectors_el is None:
        return geom

    for det_el in _findall_local(detectors_el, "Detector"):
        d = DetectorGeometry()

        npix = _floats(_text_of(det_el, "Npixels") or "")
        if npix.size >= 2:
            d.Nx, d.Ny = int(npix[0]), int(npix[1])

        size = _floats(_text_of(det_el, "size") or "")
        if size.size >= 2:
            d.sizeX, d.sizeY = float(size[0]), float(size[1])

        rvec = _floats(_text_of(det_el, "R") or "")
        if rvec.size == 3:
            d.R = rvec

        pvec = _floats(_text_of(det_el, "P") or "")
        if pvec.size == 3:
            d.P = pvec

        det_id = _text_of(det_el, "ID")
        if det_id:
            d.detector_id = det_id

        # "used" attribute: Igor's struct defaults to True; honor an
        # explicit "used" tag if present, else assume True.
        used_text = _text_of(det_el, "used")
        if used_text is not None:
            d.used = used_text.strip() not in ("0", "false", "False")

        d.update_rho()
        geom.detectors.append(d)

    return geom


# ---------------------------------------------------------------------------
# Geometry resolution from the indexed XML
# ---------------------------------------------------------------------------


def extract_geo_paths_from_indexing_xml(indexed_xml_path: str) -> List[str]:
    """
    Read the ``<geoFile>`` paths embedded in an indexed (AllSteps) XML.

    LaueGo's indexer copies the geometry file path into every ``<detector>``
    block, so we can usually resolve the geometry without consulting the
    database.  Returns the unique non-empty paths in encounter order.
    """
    out: List[str] = []
    seen = set()
    # Pull-parse so we don't have to load 10+ MB into ET for the few
    # bytes we need.  But for simplicity we just walk the tree; the
    # caller can cache the parsed result via parse_indexing_xml.
    tree = ET.parse(indexed_xml_path)
    root = tree.getroot()
    for step in root.findall("step"):
        for det in step.findall("detector"):
            geo_el = det.find("geoFile")
            if geo_el is None or not geo_el.text:
                continue
            path = geo_el.text.strip()
            if path and path not in seen:
                seen.add(path)
                out.append(path)
    return out


def resolve_geometry_for_indexing(
    indexed_xml_path: str,
    db_geo_file: Optional[str] = None,
) -> Optional[BeamlineGeometry]:
    """
    Resolve and parse the detector geometry associated with one indexed
    AllSteps XML file.

    Resolution order:
      1. ``db_geo_file`` if provided and the file exists.
      2. The first ``<geoFile>`` embedded inside the indexed XML
         (``extract_geo_paths_from_indexing_xml``) that exists on disk.

    Returns
    -------
    BeamlineGeometry | None
        ``None`` if no readable geometry file could be located.
    """
    candidates: List[str] = []
    if db_geo_file:
        candidates.append(str(db_geo_file))
    try:
        candidates.extend(extract_geo_paths_from_indexing_xml(indexed_xml_path))
    except (ET.ParseError, OSError):
        # If the indexed XML itself is unreadable, fall through with
        # only the DB candidate (which already failed os.path.isfile or
        # we'll just return None below).
        pass

    for path in candidates:
        try:
            if os.path.isfile(path):
                return parse_geometry_xml(path)
        except OSError:
            continue
    return None
