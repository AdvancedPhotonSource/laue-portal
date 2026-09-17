"""Native wire-scan reconstruction of one run through lauelab's ``Reconstructor``.

Each manifest entry is one wire-scan point. Points are reconstructed in this
process one at a time with the configured OpenMP thread count; a stop request
is honoured between points. Output follows the validated library API in the
pinned revision: one HDF5 file per depth plus a summary text file per point,
prefixed ``<input_id>_`` inside the run directory. The single-file
reconstruction output planned for the library is not in that revision, so the
file count still grows with points times depths; when the refactor lands, only
this module and its tests change.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from lauelab.indexing import InputError, ReconstructionError
from lauelab.reconstruct import Reconstructor

from laue_portal.processing.compute.contract import RunHooks, RunOutcome, RunRequest, register_compute_function
from laue_portal.processing.compute.lauego import _library_provenance
from laue_portal.workflows.manifest import CATEGORY_CANCELLED, FailureRecord, ManifestEntry

WIRE_KIND = "wire_reconstruction"
DETECTOR_INDEX = 0
WIRE_EDGES = ("leading", "trailing", "both")
ENGINE = "lauelab Reconstructor (in-process, per-depth files)"

# Errors that describe one point and let the run continue with the next.
POINT_ERRORS = (InputError, ReconstructionError, MemoryError, OSError)


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


def build_reconstructor(settings: WireSettings) -> Reconstructor:
    return Reconstructor(
        settings.geometry_file,
        settings.detector_index,
        depth_range=settings.depth_range,
        resolution=settings.resolution,
        wire_edge=settings.wire_edge,
        percent_brightest=settings.percent_brightest,
        num_threads=settings.num_threads,
        memory_limit_mb=settings.memory_limit_mb,
    )


def output_base(request: RunRequest, entry: ManifestEntry) -> str:
    return os.path.join(request.run_directory, f"{entry.input_id}_")


def compute_wire_reconstruction(request: RunRequest, entries: Iterable[ManifestEntry], hooks: RunHooks) -> RunOutcome:
    settings = settings_from_request(request.parameters)
    reconstructor = build_reconstructor(settings)  # shared configuration problems stop the run here
    os.makedirs(request.run_directory, exist_ok=True)

    succeeded = failed = 0
    stopped = False
    written: list[str] = []
    depths = None
    for entry in entries:
        if stopped or hooks.should_stop():
            stopped = True
            hooks.record_failure(
                FailureRecord.not_run(entry, category=CATEGORY_CANCELLED, message="run stopped before this point")
            )
            continue
        try:
            result = reconstructor.reconstruct(entry.source, output_base=output_base(request, entry))
        except POINT_ERRORS as error:
            failed += 1
            hooks.record_failure(FailureRecord.from_error(entry, error))
        else:
            if result.success:
                succeeded += 1
                written.extend(result.output_files)
                if depths is None and result.depth_um is not None:
                    depths = [float(value) for value in result.depth_um]
            else:
                failed += 1
                hooks.record_failure(
                    FailureRecord.from_error(
                        entry,
                        ReconstructionError(result.error or "reconstruction reported failure"),
                        context={
                            "last_completed_stripe": result.last_completed_stripe,
                            "partial_files": len(result.output_files),
                        },
                    )
                )
        hooks.report_progress(succeeded=succeeded, failed=failed)

    outcome = RunOutcome(
        n_succeeded=succeeded,
        n_failed=failed,
        stopped=stopped,
        provenance={
            **_library_provenance(),
            "engine": ENGINE,
            "geometry_file": settings.geometry_file,
            "detector_index": settings.detector_index,
            "depth_range_um": list(settings.depth_range),
            "resolution_um": settings.resolution,
            "wire_edge": settings.wire_edge,
            "percent_brightest": settings.percent_brightest,
            "num_threads": reconstructor.num_threads,
            "memory_limit_mb": settings.memory_limit_mb,
            "depths_um": depths,
            "output_layout": "one HDF5 file per depth plus <input_id>_summary.txt per point",
        },
    )
    if succeeded == 0:
        outcome.summary = "no point was reconstructed"
        return outcome

    missing = [path for path in written if not os.path.isfile(path) or os.path.getsize(path) == 0]
    if missing:
        outcome.validation_error = f"{len(missing)} reconstructed file(s) are missing or empty, first: {missing[0]}"
        return outcome
    outcome.artifacts["directory"] = request.run_directory
    outcome.provenance["n_files_written"] = len(written)
    outcome.summary = f"{succeeded} point(s) reconstructed into {len(written)} files under {request.run_directory}"
    return outcome


register_compute_function(WIRE_KIND, compute_wire_reconstruction)
