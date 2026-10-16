"""Planning estimates from measured profiles, without enumerating images or reading pixels."""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from laue_portal.database.db_utils import get_num_inputs_from_fields, parse_parameter, resolve_path_with_root
from laue_portal.utilities.filename_patterns import compile_filename_templates
from laue_portal.utilities.srange import srange


@lru_cache(maxsize=1)
def measured_profiles():
    return json.loads(Path(__file__).with_name("runtime_profiles.json").read_text())


@dataclass(frozen=True)
class Selection:
    points: int
    frames: int
    depths: int | None
    basis: str
    notes: tuple[str, ...] = ()
    staged_frames: int | None = None  # Complete point stacks are transferred for catalog inputs.


@dataclass(frozen=True)
class RuntimeEstimate:
    seconds: float
    selection: Selection
    profile: dict
    notes: tuple[str, ...]
    runs: int


@dataclass(frozen=True)
class TransferEstimate:
    input_bytes: float
    output_bytes: float
    bytes_per_second: float

    @property
    def input_seconds(self):
        return self.input_bytes / self.bytes_per_second

    @property
    def output_seconds(self):
        return self.output_bytes / self.bytes_per_second

    @property
    def seconds(self):
        return self.input_seconds + self.output_seconds


def estimate_transfers(kind, selection):
    """Project both directions from profiling sizes; never stat or read the data files."""
    reference = measured_profiles()["transfer"]
    reconstructed_frame_bytes = (
        reference["estimated_reconstruction_bytes"] / reference["reference_reconstructed_frames"]
    )
    if kind == "reconstruction":
        input_bytes = selection.points * reference["measured_input_bytes"] / reference["reference_points"]
        output_bytes = selection.frames * reconstructed_frame_bytes
    else:
        # A depth subset still stages the entire point file containing those depths.
        frames = selection.staged_frames if selection.staged_frames is not None else selection.frames
        input_bytes = frames * reconstructed_frame_bytes
        output_bytes = (
            selection.frames
            * reference["measured_indexing_result_bytes"]
            / reference["measured_indexing_result_frames"]
        )
    return TransferEstimate(
        input_bytes, output_bytes, reference["measured_input_bytes"] / reference["measured_seconds"]
    )


def integer_range(value, *, optional=False):
    if value is None or not str(value).strip():
        if optional:
            return None
        raise ValueError("Select scan points to calculate an estimate.")
    try:
        result = srange(str(value))
        if not len(result) or result.first() < 0:
            raise ValueError
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("Enter valid, nonnegative point and depth indices.") from error
    return result


@lru_cache(maxsize=32)
def _catalog_points(path, refresh_window):
    from lauelab.reconstruct import ScanReader

    # One small catalog snapshot, cached for ten seconds. Never open point files.
    try:
        with ScanReader(path) as scan:
            return scan.points
    except (OSError, ValueError) as error:
        if Path(path).name == "scan.h5":
            raise ValueError("The reconstruction catalog is unavailable; check the input path.") from error
        return None


def count_selection(kind, fields):
    templates = tuple(
        dict.fromkeys(part.strip() for part in str(fields.get("filenamePrefix") or "").split(",") if part.strip())
    )
    if not templates:
        raise ValueError("Choose a filename pattern to calculate an estimate.")
    points = integer_range(fields.get("scanPoints"), optional=kind == "indexing")
    depths = integer_range(fields.get("depthRange"), optional=True) if kind == "indexing" else None
    path = resolve_path_with_root(fields.get("data_path") or "", fields.get("root_path") or "")
    if kind == "indexing" and Path(path).suffix.lower() in {".h5", ".hdf5", ".hdf", ".he5"}:
        catalog = _catalog_points(path, int(time.monotonic() // 10))
        if catalog is not None:
            if any(template.count("%d") > 1 for template in templates):
                raise ValueError("A reconstruction catalog uses one point index; select depths separately.")
            matcher = compile_filename_templates(templates, append_suffix_wildcard=True)
            selected_points = selected_frames = staged_frames = 0
            for point in catalog:
                match = matcher.match(os.path.basename(point.source_path))
                if match is None or (points is not None and match.indices and not points.is_in_range(match.indices[0])):
                    continue
                if not point.complete:
                    raise ValueError("The selection includes incomplete reconstructed points.")
                n_depths = point.shape[0]
                if depths is not None and depths.last() >= n_depths:
                    raise ValueError(f"Selected depth indices exceed this reconstruction's 0–{n_depths - 1} range.")
                selected_points += 1
                selected_frames += len(depths) if depths is not None else n_depths
                staged_frames += n_depths
            if not selected_frames:
                raise ValueError("No reconstructed frames match this selection.")
            return Selection(
                selected_points, selected_frames, None, "Reconstruction catalog", staged_frames=staged_frames
            )
    if points is None:
        raise ValueError("Select scan points to calculate an estimate.")
    count = 0
    for template in templates:
        placeholders = template.count("%d")
        if placeholders > (2 if kind == "indexing" else 1):
            raise ValueError("The filename pattern has too many index placeholders.")
        if not placeholders and any(symbol in template for symbol in "*?["):
            raise ValueError(
                "Use an indexed filename pattern for a fast estimate; wildcard file counts need validation."
            )
        if placeholders == 2 and depths is None:
            raise ValueError("Select depth indices for the second filename placeholder.")
        if placeholders == 1 and depths is not None:
            raise ValueError("For directory inputs, depth indices need a second filename placeholder.")
        count += (len(points) if placeholders else 1) * (len(depths) if placeholders == 2 else 1)
    if kind == "indexing":
        point_count = len(points) if any("%d" in template for template in templates) else count
        return Selection(
            point_count,
            count,
            None,
            "Selected indices",
            ("Assumes one file per index/template match; validation checks actual files.",),
        )
    try:
        start, end, step = (float(fields[key]) for key in ("depth_start", "depth_end", "depth_resolution"))
        if not all(math.isfinite(value) for value in (start, end, step)) or step <= 0 or end < start:
            raise ValueError
        n_depths = math.floor((end - start) / step + 1e-9) + 1
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise ValueError("Enter a valid reconstruction depth range and positive resolution.") from error
    return Selection(
        count, count * n_depths, n_depths, "Selected indices", ("File availability is checked during validation.",)
    )


def choose_profile(kind, backend, policy):
    machine = "crux" if backend == "crux" else "aps"
    workers = int(policy.get("reconstruction_workers" if kind == "reconstruction" else "workers") or 1)
    threads = int(policy.get("threads_per_worker") or 1) if kind == "reconstruction" else 1
    window = policy.get("max_in_flight") or 2 * workers
    nodes = int(policy.get("nodes", 1))
    ranks = int(policy.get("indexing_ranks_per_node", 1)) if kind == "indexing" else 1
    candidates = [p for p in measured_profiles()["profiles"] if p["backend"] == machine and p["kind"] == kind]
    profile = min(
        candidates,
        key=lambda p: (
            abs(math.log2(p.get("nodes", 1) / nodes)),
            abs(math.log2(p.get("ranks_per_node", 1) / ranks)),
            abs(math.log2(p["workers"] / max(1, workers))),
            abs(math.log2(p["threads"] / max(1, threads))),
            abs((p.get("max_in_flight") or 2 * p["workers"]) - window),
        ),
    )
    notes = []
    if profile.get("nodes", 1) != nodes or profile.get("ranks_per_node", 1) != ranks:
        notes.append("The current node/coordinator layout differs from this measured reference configuration.")
    if profile["workers"] != workers or profile["threads"] != threads:
        notes.append("The current worker settings differ from this measured reference configuration.")
    return profile, notes


def estimate_runtime(kind, backend, fields, *, policy):
    profile, notes = choose_profile(kind, backend, policy)
    n_runs = get_num_inputs_from_fields(fields)
    if n_runs > 100:
        raise ValueError("Estimate at most 100 pooled runs at a time.")
    pooled = {key: parse_parameter(value, n_runs) for key, value in fields.items()}
    selections, seconds = [], 0.0
    rate = profile["count"] / profile["seconds"]
    for index in range(n_runs):
        current = {key: values[index] for key, values in pooled.items()}
        selection = count_selection(kind, current)
        units = selection.points if kind == "reconstruction" else selection.frames
        # A batch smaller than its worker pool still needs one wave of work.
        wave = profile["workers"] * profile.get("nodes", 1) * profile.get("ranks_per_node", 1)
        duration = max(units, wave) / rate
        if kind == "reconstruction":
            duration *= selection.depths / measured_profiles()["reference"]["depths_per_point"]
            if any(str(current.get(key) or 1) not in {"1", "1.0"} for key in ("frame_skip", "wire_skip")):
                notes.append("Skip settings differ from profiling; their speedup has not been measured.")
        seconds += duration
        selections.append(selection)
        notes.extend(selection.notes)
    notes.append(
        "Based on 2048 × 2048 reference images; image size, peak settings, and storage load can change runtime."
    )
    if kind == "reconstruction":
        notes.append(
            "Reference input: 510 raw frames per point. Depth scaling is approximate because input I/O also takes time."
        )
    selection = Selection(
        sum(s.points for s in selections),
        sum(s.frames for s in selections),
        None,
        ", ".join(dict.fromkeys(s.basis for s in selections)),
        staged_frames=sum(s.staged_frames if s.staged_frames is not None else s.frames for s in selections),
    )
    return RuntimeEstimate(seconds, selection, profile, tuple(dict.fromkeys(notes)), n_runs)


def format_duration(seconds):
    minutes = max(1, round(seconds / 60))
    if seconds < 60:
        return "under 1 min"
    if minutes < 60:
        return f"{minutes} min"
    hours, remainder = divmod(minutes, 60)
    return f"{hours} h" + (f" {remainder} min" if remainder else "")
