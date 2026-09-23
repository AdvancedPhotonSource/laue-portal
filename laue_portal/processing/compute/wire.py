"""Native wire-scan reconstruction of one run into one reconstruction-scan HDF5 file.

Each manifest entry is one wire-scan point. ``lauelab.reconstruct_scan``
reconstructs the points one at a time with the configured OpenMP thread count
into ``reconstruction.h5`` in the run directory; the point ID is the entry's
``input_id``. A stop request is honoured between points. The library writes a
private ``.partial`` file, validates it, and publishes it with honest per-point
status, so a cancelled or partly failed run still publishes its completed
points. A failure of the shared file stops the run and publishes nothing.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from lauelab.indexing import InputError, ReconstructionError
from lauelab.reconstruct import InvalidScanFile, PointOutcome, reconstruct_scan, validate_scan_file

from laue_portal.processing.compute.contract import RunHooks, RunOutcome, RunRequest, register_compute_function
from laue_portal.processing.compute.lauego import _library_provenance
from laue_portal.workflows.manifest import (
    CATEGORY_CANCELLED,
    RECONSTRUCTION_FILENAME,
    FailureRecord,
    ManifestEntry,
)

WIRE_KIND = "wire_reconstruction"
DETECTOR_INDEX = 0
WIRE_EDGES = ("leading", "trailing", "both")
ENGINE = "lauelab reconstruct_scan (in-process, one reconstruction-scan file)"


@dataclass(frozen=True)
class WireSettings:
    geometry_file: str
    depth_range: tuple[float, float]
    resolution: float
    wire_edge: str
    percent_brightest: float
    num_threads: int | None
    memory_limit_mb: int
    detector_index: int = DETECTOR_INDEX


def settings_from_request(parameters: Mapping[str, Any]) -> WireSettings:
    """Map the saved wire form values to Reconstructor arguments (plan section 7.2)."""

    edge = str(parameters["wire_edges"]).strip().lower()
    if edge not in WIRE_EDGES:
        raise InputError(f"wire edge must be one of {', '.join(WIRE_EDGES)}; received {parameters['wire_edges']!r}")
    threads = parameters.get("num_threads")
    memory = parameters.get("memory_limit_mb")
    return WireSettings(
        geometry_file=str(parameters["geometry_file"]),
        depth_range=(float(parameters["depth_start"]), float(parameters["depth_end"])),
        resolution=float(parameters["depth_resolution"]),
        wire_edge=edge,
        percent_brightest=float(parameters["percent_brightest"]),
        num_threads=None if threads in (None, 0) else int(threads),
        memory_limit_mb=int(memory) if memory not in (None, 0) else 8192,
    )


def reconstructor_options(settings: WireSettings) -> dict[str, Any]:
    """Keyword arguments for the library's ``Reconstructor``."""

    return {
        "depth_range": settings.depth_range,
        "resolution": settings.resolution,
        "wire_edge": settings.wire_edge,
        "percent_brightest": settings.percent_brightest,
        "num_threads": settings.num_threads,
        "memory_limit_mb": settings.memory_limit_mb,
    }


def compute_wire_reconstruction(request: RunRequest, entries: Iterable[ManifestEntry], hooks: RunHooks) -> RunOutcome:
    settings = settings_from_request(request.parameters)
    entries = list(entries)  # one small record per point; the library freezes the same order
    os.makedirs(request.run_directory, exist_ok=True)
    output = os.path.join(request.run_directory, RECONSTRUCTION_FILENAME)

    counts = {"complete": 0, "failed": 0}

    def progress(point: PointOutcome) -> None:
        entry = entries[point.index]
        if point.status == "failed":
            hooks.record_failure(
                FailureRecord.from_error(
                    entry,
                    ReconstructionError(point.error or "reconstruction failed"),
                    context={"seconds": point.seconds},
                )
            )
        counts[point.status] += 1
        hooks.report_progress(succeeded=counts["complete"], failed=counts["failed"])

    # Shared configuration problems and a failure of the output file raise and stop the run.
    result = reconstruct_scan(
        [entry.source for entry in entries],
        output,
        geometry=settings.geometry_file,
        detector=settings.detector_index,
        point_ids=[entry.input_id for entry in entries],
        progress=progress,
        should_stop=hooks.should_stop,
        **reconstructor_options(settings),
    )
    for point in result.outcomes:
        if point.status == "unattempted":
            hooks.record_failure(
                FailureRecord.not_run(
                    entries[point.index], category=CATEGORY_CANCELLED, message="run stopped before this point"
                )
            )

    outcome = RunOutcome(
        n_succeeded=counts["complete"],
        n_failed=counts["failed"],
        stopped=result.cancelled,
        provenance={
            **_library_provenance(),
            "engine": ENGINE,
            "geometry_file": settings.geometry_file,
            "detector_index": settings.detector_index,
            "depth_range_um": list(settings.depth_range),
            "resolution_um": settings.resolution,
            "wire_edge": settings.wire_edge,
            "percent_brightest": settings.percent_brightest,
            "num_threads": settings.num_threads,
            "memory_limit_mb": settings.memory_limit_mb,
            "output_layout": f"one reconstruction-scan HDF5 file per run ({RECONSTRUCTION_FILENAME})",
        },
    )
    try:
        summary = validate_scan_file(result.path)
    except (InvalidScanFile, OSError) as error:
        outcome.validation_error = f"{RECONSTRUCTION_FILENAME}: {error}"
        return outcome
    outcome.artifacts["reconstruction"] = os.fspath(result.path)
    outcome.provenance["reconstruction_summary"] = {
        "run_status": summary.run_status,
        "n_points": summary.n_points,
        "n_complete": summary.n_complete,
        "n_failed": summary.n_failed,
        "n_unattempted": summary.n_unattempted,
    }
    outcome.summary = (
        f"{summary.n_complete} of {summary.n_points} point(s) reconstructed into {RECONSTRUCTION_FILENAME}"
    )
    return outcome


register_compute_function(WIRE_KIND, compute_wire_reconstruction)
