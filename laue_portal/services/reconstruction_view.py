"""Server-side access to a wire reconstruction's points for the reconstruction page.

A run's pixels are found in one of two layouts:

* ``reconstruction.h5`` in the run directory, a lauelab reconstruction-scan
  file (runs from this portal version onward);
* per-depth files ``<point_id>_<depth_index>.h5`` next to one
  ``<point_id>_summary.txt`` per point (earlier runs).

Callbacks keep only small identities in the browser (artifact path, point ID,
ROI bounds). Scientific products -- a stored frame, a reference image, a
depth trace -- are computed by lauelab and kept here in a byte-bounded
least-recently-used cache whose keys carry the artifact's identity, so a
changed file is never served from the cache. Axis, scale, and colour changes
reuse cached products. Per-depth points have no embedded reductions, so their
first full-frame trace or reference reads every frame once.
"""

from __future__ import annotations

import os
import re
import threading
from collections import OrderedDict
from collections.abc import Callable, Hashable
from dataclasses import dataclass

import numpy as np
from lauelab.indexing import InputError
from lauelab.reconstruct import PerDepthReader, ScanReader
from lauelab.reconstruct.inspection import Bounds, DepthTrace, ReferenceImage, depth_trace, reference_image

from laue_portal.workflows.manifest import RECONSTRUCTION_FILENAME

KIND_SCAN = "scan"
KIND_PER_DEPTH = "per_depth"
SUMMARY_SUFFIX = "_summary.txt"
DEFAULT_CACHE_BYTES = 1024 * 1024 * 1024


class ViewError(RuntimeError):
    """A point or product cannot be shown; the message is meant for the page."""


@dataclass(frozen=True)
class Artifact:
    """Where a run's reconstructed pixels live."""

    kind: str
    path: str  # the scan file, or the run directory holding per-depth files

    def to_store(self) -> dict:
        return {"kind": self.kind, "path": self.path}

    @classmethod
    def from_store(cls, data) -> Artifact | None:
        if not data or data.get("kind") not in (KIND_SCAN, KIND_PER_DEPTH):
            return None
        return cls(data["kind"], str(data["path"]))


def locate_artifact(run_directory: str | None) -> Artifact | None:
    """The run's scan file, else its per-depth files, else None."""

    if not run_directory:
        return None
    scan = os.path.join(run_directory, RECONSTRUCTION_FILENAME)
    if os.path.isfile(scan):
        return Artifact(KIND_SCAN, scan)
    try:
        with os.scandir(run_directory) as entries:
            if any(entry.name.endswith(SUMMARY_SUFFIX) for entry in entries):
                return Artifact(KIND_PER_DEPTH, run_directory)
    except OSError:
        return None
    return None


def _identity(artifact: Artifact) -> tuple:
    """Changes whenever the artifact is rewritten; part of every cache key."""

    status = os.stat(artifact.path)
    return (artifact.kind, os.path.realpath(artifact.path), status.st_size, status.st_mtime_ns)


def _per_depth_files(directory: str) -> dict[str, list[str]]:
    """Point ID to its per-depth HDF5 files, from one directory listing.

    Points are the prefixes of ``<point_id>_summary.txt``; a point's frames are
    exactly the names ``<point_id>_<digits>.h5``.
    """

    names = os.listdir(directory)
    points = sorted(name[: -len(SUMMARY_SUFFIX)] for name in names if name.endswith(SUMMARY_SUFFIX))
    patterns = {point: re.compile(re.escape(point) + r"_(\d+)\.h5") for point in points}
    files: dict[str, list[str]] = {point: [] for point in points}
    for name in names:
        if not name.endswith(".h5"):
            continue
        for point, pattern in patterns.items():
            if pattern.fullmatch(name):
                files[point].append(os.path.join(directory, name))
                break
    return files


def _finite(values) -> list[float] | None:
    values = [float(value) for value in values]
    return values if all(np.isfinite(values)) else None


def point_rows(artifact: Artifact) -> list[dict]:
    """One lightweight row per point, from the catalog or a directory listing; reads no pixels."""

    rows = []
    if artifact.kind == KIND_SCAN:
        with ScanReader(artifact.path) as scan:
            for entry in scan.points:
                complete = entry.status == "complete"
                rows.append(
                    {
                        "point_id": entry.point_id,
                        "index": entry.index,
                        "status": entry.status,
                        "source": entry.source_path,
                        "sample_position_um": _finite(entry.sample_position),
                        "n_depths": entry.shape[0] if complete else None,
                        "depth_first_um": entry.depth_bounds_um[0] if complete else None,
                        "depth_last_um": entry.depth_bounds_um[1] if complete else None,
                        "shape": f"{entry.shape[1]} x {entry.shape[2]}" if complete else "",
                        "dtype": str(entry.dtype) if complete and entry.dtype is not None else "",
                        "error": entry.error,
                    }
                )
        return rows
    for index, (point_id, files) in enumerate(_per_depth_files(artifact.path).items()):
        rows.append(
            {
                "point_id": point_id,
                "index": index,
                "status": "complete" if files else "no frames",
                "source": "",
                "sample_position_um": None,
                "n_depths": len(files) or None,
                "depth_first_um": None,  # known once the point is opened
                "depth_last_um": None,
                "shape": "",
                "dtype": "",
                "error": "" if files else "no per-depth files next to the summary",
            }
        )
    return rows


class ProductCache:
    """Least-recently-used cache bounded by the bytes of the arrays it holds."""

    def __init__(self, max_bytes: int = DEFAULT_CACHE_BYTES):
        self.max_bytes = max_bytes
        self._entries: OrderedDict[Hashable, tuple[object, int]] = OrderedDict()
        self._bytes = 0
        self._lock = threading.Lock()

    @property
    def nbytes(self) -> int:
        return self._bytes

    def __len__(self) -> int:
        return len(self._entries)

    def get(self, key: Hashable, compute: Callable[[], object]):
        with self._lock:
            if key in self._entries:
                self._entries.move_to_end(key)
                return self._entries[key][0]
        value = compute()  # outside the lock: a slow read must not stall other callbacks
        size = _nbytes(value)
        with self._lock:
            if key in self._entries:
                self._bytes -= self._entries.pop(key)[1]
            if size <= self.max_bytes:
                self._entries[key] = (value, size)
                self._bytes += size
                while self._bytes > self.max_bytes:
                    self._bytes -= self._entries.popitem(last=False)[1][1]
        return value

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._bytes = 0


def _nbytes(value) -> int:
    if isinstance(value, np.ndarray):
        return value.nbytes
    if isinstance(value, ReferenceImage):
        return value.image.nbytes
    if isinstance(value, DepthTrace):
        return value.values.nbytes + value.depth_um.nbytes
    if isinstance(value, PerDepthReader):
        return 64 * len(value.paths)  # metadata only; pixels are read per operation
    return 64


CACHE = ProductCache()


def _open_point(artifact: Artifact, point_id: str):
    """A context manager yielding the point's reader."""

    if artifact.kind == KIND_SCAN:
        return _ScanPoint(artifact.path, point_id)
    reader = CACHE.get((_identity(artifact), point_id, "reader"), lambda: _per_depth_reader(artifact, point_id))
    return _Borrowed(reader)


def _per_depth_reader(artifact: Artifact, point_id: str) -> PerDepthReader:
    files = _per_depth_files(artifact.path).get(point_id)
    if not files:
        raise ViewError(f"point {point_id!r} has no per-depth files in {artifact.path}")
    return PerDepthReader(files, point_id=point_id)


class _ScanPoint:
    def __init__(self, path: str, point_id: str):
        self._path = path
        self._point_id = point_id
        self._scan = None

    def __enter__(self):
        self._scan = ScanReader(self._path)
        try:
            return self._scan.point(self._point_id)
        except BaseException:
            self._scan.close()
            raise

    def __exit__(self, *exc):
        self._scan.close()


class _Borrowed:
    """Lends a cached reader without closing it."""

    def __init__(self, reader):
        self._reader = reader

    def __enter__(self):
        return self._reader

    def __exit__(self, *exc):
        return None


def _cached(artifact: Artifact, point_id: str, product: Hashable, compute):
    try:
        key = (_identity(artifact), point_id, product)
        return CACHE.get(key, lambda: _with_point(artifact, point_id, compute))
    except (InputError, KeyError, OSError, ValueError) as error:
        raise ViewError(str(error) or type(error).__name__) from error


def _with_point(artifact: Artifact, point_id: str, compute):
    with _open_point(artifact, point_id) as point:
        return compute(point)


@dataclass(frozen=True)
class PointSummary:
    point_id: str
    shape: tuple[int, int, int]
    dtype: str
    depth_um: np.ndarray


def point_summary(artifact: Artifact, point_id: str) -> PointSummary:
    return _cached(
        artifact,
        point_id,
        "summary",
        lambda point: PointSummary(point_id, tuple(point.shape), str(point.dtype), np.array(point.depth_um)),
    )


def stored_frame(artifact: Artifact, point_id: str, depth_index: int) -> np.ndarray:
    """One stored frame, read alone."""

    return _cached(artifact, point_id, ("frame", int(depth_index)), lambda point: point.frame(int(depth_index)))


def full_trace(artifact: Artifact, point_id: str) -> DepthTrace:
    return _cached(artifact, point_id, "full_trace", lambda point: depth_trace(point))


def reference(artifact: Artifact, point_id: str, kind: str) -> ReferenceImage:
    return _cached(artifact, point_id, ("reference", kind), lambda point: reference_image(point, kind))


def roi_trace(artifact: Artifact, point_id: str, name: str, bounds: Bounds) -> DepthTrace:
    """One ROI's trace; cached by bounds so adding an ROI reduces only that ROI."""

    bounds = tuple(int(value) for value in bounds)
    trace = _cached(artifact, point_id, ("roi", bounds), lambda point: depth_trace(point, bounds))
    return DepthTrace(trace.values, trace.depth_um, trace.point_id, trace.bounds, name)
