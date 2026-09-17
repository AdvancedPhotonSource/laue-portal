"""Server-side cache of normalized lauelab visualization datasets.

Callbacks receive only an artifact path in their Dash stores; the normalized
scientific dataset lives here, keyed by the file's identity (real path, size,
modification time) so a republished file is reloaded and an unchanged one is
reused across every callback. The cache is bounded and evicts the least
recently used dataset.
"""

from __future__ import annotations

import os
import threading
from collections import OrderedDict
from dataclasses import dataclass

import lauelab
from lauelab.visualization import VisualizationDataset, load_results, load_visualization_xml

DEFAULT_CAPACITY = 6

KIND_RESULTS = "results"
KIND_XML = "xml"


@dataclass(frozen=True)
class SourceKey:
    path: str
    size: int
    mtime_ns: int
    geometry: str | None


def source_key(path: str | os.PathLike[str], geometry: str | None = None) -> SourceKey:
    real = os.path.realpath(path)
    status = os.stat(real)
    return SourceKey(real, status.st_size, status.st_mtime_ns, geometry)


def source_kind(path: str | os.PathLike[str]) -> str:
    return KIND_RESULTS if lauelab.is_results_file(path) else KIND_XML


def load_dataset(path: str | os.PathLike[str], *, geometry: str | None = None) -> VisualizationDataset:
    """Load a results file or a LaueGo XML document into the shared model (uncached)."""

    if source_kind(path) == KIND_RESULTS:
        return load_results(path, geometry=geometry) if geometry else load_results(path)
    return load_visualization_xml(path, geometry=geometry)


class DatasetCache:
    """Bounded least-recently-used cache of datasets by source identity."""

    def __init__(self, capacity: int = DEFAULT_CAPACITY):
        if capacity < 1:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self._entries: OrderedDict[SourceKey, VisualizationDataset] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def get(self, path: str | os.PathLike[str], *, geometry: str | None = None) -> VisualizationDataset:
        key = source_key(path, geometry)
        with self._lock:
            dataset = self._entries.get(key)
            if dataset is not None:
                self._entries.move_to_end(key)
                self.hits += 1
                return dataset
            self.misses += 1
            # Loading under the lock serializes concurrent callbacks on the same
            # file instead of parsing it twice; the portal runs one Dash process.
            dataset = load_dataset(key.path, geometry=geometry)
            # Any older entry for the same path is stale: the file changed.
            for stale in [entry for entry in self._entries if entry.path == key.path]:
                del self._entries[stale]
            self._entries[key] = dataset
            while len(self._entries) > self.capacity:
                self._entries.popitem(last=False)
                self.evictions += 1
            return dataset

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)

    def keys(self) -> tuple[SourceKey, ...]:
        return tuple(self._entries)


CACHE = DatasetCache()


def get_dataset(path: str | os.PathLike[str], *, geometry: str | None = None) -> VisualizationDataset:
    """The process-wide cached dataset for ``path``."""

    return CACHE.get(path, geometry=geometry)
