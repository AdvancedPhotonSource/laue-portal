"""Load reconstruction images and traces for the wire reconstruction page.

New runs use ``reconstruction/scan.h5`` to track progress and locate completed
files under ``reconstruction/points/``. Earlier runs have per-depth files
``<point_id>_<depth_index>.h5`` and ``<point_id>_summary.txt`` in the run directory.

Catalog metadata and computed products are cached on the server. Point-file
identity determines whether an image or trace can be reused after a catalog
update. Per-depth runs use directory identity instead; their first reference
image or full-frame trace requires reading every frame.

The point table reads a fresh catalog snapshot on each explicit refresh.
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

from laue_portal.workflows.manifest import reconstruction_catalog_path

KIND_SCAN = "scan"
KIND_PER_DEPTH = "per_depth"
SUMMARY_SUFFIX = "_summary.txt"
DEFAULT_CACHE_BYTES = 1024 * 1024 * 1024


class ViewError(RuntimeError):
    """An error message suitable for display on the reconstruction page."""


@dataclass(frozen=True)
class Artifact:
    """Location and format of a reconstruction."""

    kind: str
    path: str  # the scan catalog, or the run directory holding per-depth files

    def to_store(self) -> dict:
        return {"kind": self.kind, "path": self.path}

    @classmethod
    def from_store(cls, data) -> Artifact | None:
        if not data or data.get("kind") not in (KIND_SCAN, KIND_PER_DEPTH):
            return None
        return cls(data["kind"], str(data["path"]))


def locate_artifact(run_directory: str | None) -> Artifact | None:
    """Find the scan catalog or per-depth output, including catalogs of running jobs."""

    if not run_directory:
        return None
    scan = reconstruction_catalog_path(run_directory)
    if os.path.isfile(scan):
        return Artifact(KIND_SCAN, scan)
    try:
        with os.scandir(run_directory) as entries:
            if any(entry.name.endswith(SUMMARY_SUFFIX) for entry in entries):
                return Artifact(KIND_PER_DEPTH, run_directory)
    except OSError:
        return None
    return None


def _file_identity(path: str) -> tuple:
    """Use the path, inode, size, and modification time to detect file changes."""

    status = os.stat(path)
    return (os.path.realpath(path), status.st_ino, status.st_size, status.st_mtime_ns)


def _identity(artifact: Artifact) -> tuple:
    """Identify the current catalog snapshot or per-depth directory."""

    return (artifact.kind, *_file_identity(artifact.path))


def _per_depth_files(directory: str) -> dict[str, list[str]]:
    """Group per-depth files by point ID, using summary filenames to identify points."""

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


@dataclass(frozen=True)
class PointTable:
    """Point metadata for the table, with the catalog status when available."""

    rows: list[dict]
    run_status: str | None  # the catalog's run status; None for per-depth files


def point_table(artifact: Artifact) -> PointTable:
    """Read current point metadata for the table without loading images."""

    rows = []
    if artifact.kind == KIND_SCAN:
        with ScanReader(artifact.path) as scan:
            run_status = scan.run_status
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
        return PointTable(rows, run_status)
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
    return PointTable(rows, None)


class ProductCache:
    """Cache products with a byte limit; estimate memory use for metadata."""

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
    if isinstance(value, _Catalog):
        return sum(1024 + len(p.source_path) + len(p.error) + len(p.path) for p in value.scan.points)
    return 64


CACHE = ProductCache()


def _open_point(artifact: Artifact, point_id: str):
    """Open a point reader for use in a ``with`` block."""

    if artifact.kind == KIND_SCAN:
        return _catalog(artifact).point(point_id)
    reader = CACHE.get((_identity(artifact), point_id, "reader"), lambda: _per_depth_reader(artifact, point_id))
    return _Borrowed(reader)


def _per_depth_reader(artifact: Artifact, point_id: str) -> PerDepthReader:
    files = _per_depth_files(artifact.path).get(point_id)
    if not files:
        raise ViewError(f"point {point_id!r} has no per-depth files in {artifact.path}")
    return PerDepthReader(files, point_id=point_id)


class _Catalog:
    """Share catalog metadata across callbacks. Callbacks close their own point readers."""

    def __init__(self, path):
        self.scan = ScanReader(path)
        self.points = {entry.point_id: entry for entry in self.scan.points}
        self._lock = threading.Lock()

    def point(self, point_id):
        # ScanReader updates its list of open readers here. Only opening and
        # validation need this lock; callbacks can read their pixels independently.
        with self._lock:
            return self.scan.point(point_id)


class _Borrowed:
    """Lends a cached reader without closing it."""

    def __init__(self, reader):
        self._reader = reader

    def __enter__(self):
        return self._reader

    def __exit__(self, *exc):
        return None


def _catalog(artifact: Artifact) -> _Catalog:
    """Reuse the catalog metadata until a new snapshot is published."""

    return CACHE.get((_identity(artifact), "catalog"), lambda: _Catalog(artifact.path))


def _point_key(artifact: Artifact, point_id: str) -> tuple:
    """Build a cache key from the point file or per-depth directory."""

    if artifact.kind != KIND_SCAN:
        return (_identity(artifact), point_id)
    catalog = _catalog(artifact)
    entry = catalog.points.get(point_id)
    if entry is None:
        raise ViewError(f"the catalog has no point {point_id!r}")
    if entry.status != "complete":
        raise ViewError(f"point {point_id!r} is {entry.status}" + (f": {entry.error}" if entry.error else ""))
    return (KIND_SCAN, point_id, *_file_identity(catalog.scan.point_path(point_id)))


def _cached(artifact: Artifact, point_id: str, product: Hashable, compute):
    try:
        key = (_point_key(artifact, point_id), product)
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
    """Read and cache one depth frame."""

    return _cached(artifact, point_id, ("frame", int(depth_index)), lambda point: point.frame(int(depth_index)))


def full_trace(artifact: Artifact, point_id: str) -> DepthTrace:
    return _cached(artifact, point_id, "full_trace", lambda point: depth_trace(point))


def reference(artifact: Artifact, point_id: str, kind: str) -> ReferenceImage:
    return _cached(artifact, point_id, ("reference", kind), lambda point: reference_image(point, kind))


def roi_trace(artifact: Artifact, point_id: str, name: str, bounds: Bounds) -> DepthTrace:
    """Cache ROI traces by bounds so changing a label reuses the calculation."""

    bounds = tuple(int(value) for value in bounds)
    trace = _cached(artifact, point_id, ("roi", bounds), lambda point: depth_trace(point, bounds))
    return DepthTrace(trace.values, trace.depth_um, trace.point_id, trace.bounds, name)
