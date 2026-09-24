"""Run wire reconstruction with lauelab's local worker pool.

Each manifest entry supplies one point. Workers write completed point files
under ``reconstruction/points/``; ``reconstruction/scan.h5`` tracks their status.
``reconstruction_workers`` controls how many points run concurrently, and the
saved ``num_threads`` sets each worker's OpenMP thread count.

Cancellation lets active points finish. Input and reconstruction errors are
reported per point; output errors stop the run. The executor retains the
catalog path and configuration if reconstruction raises. A catalog write
failure leaves the last published snapshot available.
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
    RECONSTRUCTION_DIRECTORY,
    FailureRecord,
    ManifestEntry,
    reconstruction_catalog_path,
)

WIRE_KIND = "wire_reconstruction"
DETECTOR_INDEX = 0
WIRE_EDGES = ("leading", "trailing", "both")
ENGINE = "lauelab reconstruct_scan (local worker processes, one scan directory)"


@dataclass(frozen=True)
class WireSettings:
    geometry_file: str
    depth_range: tuple[float, float]
    resolution: float
    wire_edge: str
    percent_brightest: float
    threads_per_worker: int | None
    memory_limit_mb: int  # stripe-buffer budget of each worker
    detector_index: int = DETECTOR_INDEX


def settings_from_request(parameters: Mapping[str, Any]) -> WireSettings:
    """Map the saved wire form values to reconstruction arguments.

    The saved ``num_threads`` is each worker's OpenMP thread count.
    """

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
        threads_per_worker=None if threads in (None, 0) else int(threads),
        memory_limit_mb=int(memory) if memory not in (None, 0) else 8192,
    )


def reconstructor_options(settings: WireSettings) -> dict[str, Any]:
    """Build the reconstruction options shared by all points."""

    return {
        "depth_range": settings.depth_range,
        "resolution": settings.resolution,
        "wire_edge": settings.wire_edge,
        "percent_brightest": settings.percent_brightest,
        "memory_limit_mb": settings.memory_limit_mb,
    }


def compute_wire_reconstruction(request: RunRequest, entries: Iterable[ManifestEntry], hooks: RunHooks) -> RunOutcome:
    settings = settings_from_request(request.parameters)
    entries = list(entries)
    os.makedirs(request.run_directory, exist_ok=True)
    # The library refuses a nonempty destination, so an earlier run's output is never overwritten.
    output = os.path.join(request.run_directory, RECONSTRUCTION_DIRECTORY)

    outcome = RunOutcome(
        n_succeeded=0,
        n_failed=0,
        provenance={
            **_library_provenance(),
            "engine": ENGINE,
            "geometry_file": settings.geometry_file,
            "detector_index": settings.detector_index,
            "depth_range_um": list(settings.depth_range),
            "resolution_um": settings.resolution,
            "wire_edge": settings.wire_edge,
            "percent_brightest": settings.percent_brightest,
            "workers": request.reconstruction_workers,
            "threads_per_worker": settings.threads_per_worker,
            "memory_limit_mb": settings.memory_limit_mb,
            "output_layout": f"one point file per point with a scan catalog ({RECONSTRUCTION_DIRECTORY}/)",
        },
    )
    catalog = reconstruction_catalog_path(request.run_directory)
    catalog_existed = os.path.exists(catalog)

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

    try:
        result = reconstruct_scan(
            [entry.source for entry in entries],
            output,
            geometry=settings.geometry_file,
            detector=settings.detector_index,
            point_ids=[entry.input_id for entry in entries],
            workers=request.reconstruction_workers,
            threads_per_worker=settings.threads_per_worker,
            progress=progress,
            should_stop=hooks.should_stop,
            **reconstructor_options(settings),
        )
    finally:
        outcome.n_succeeded = counts["complete"]
        outcome.n_failed = counts["failed"]
        # Keep partial output details, but do not claim a rejected destination as this run's output.
        if not catalog_existed and os.path.isfile(catalog):
            outcome.artifacts["reconstruction"] = catalog
        hooks.report_outcome(outcome)
    outcome.stopped = result.cancelled
    for point in result.outcomes:
        if point.status == "unattempted":
            hooks.record_failure(
                FailureRecord.not_run(
                    entries[point.index], category=CATEGORY_CANCELLED, message="run stopped before this point"
                )
            )

    try:
        summary = validate_scan_file(result.path)
    except (InvalidScanFile, OSError) as error:
        outcome.validation_error = f"{result.path}: {error}"
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
        f"{summary.n_complete} of {summary.n_points} point(s) reconstructed into {RECONSTRUCTION_DIRECTORY}/"
    )
    return outcome


register_compute_function(WIRE_KIND, compute_wire_reconstruction)
