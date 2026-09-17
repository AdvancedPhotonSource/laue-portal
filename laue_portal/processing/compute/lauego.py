"""Native LaueGo indexing of one run: lauelab ``Indexer.iter_index`` feeding one HDF5 and one XML writer.

The authoritative output is ``output.h5`` in the run directory. It is written to
a private ``.partial`` name, validated structurally against the manifest
identities, and published by rename. The aggregate XML named by the run's
Output XML setting is auxiliary: its problems are warnings. A failure of the
HDF5 writer stops the run; the partial file is left for diagnosis and never
published.
"""

from __future__ import annotations

import importlib.metadata
import json
import math
import os
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from numbers import Real
from typing import Any

from lauelab.indexing import (
    FrameInput,
    Indexer,
    IndexParams,
    InputError,
    InvalidResultsFile,
    PeakParams,
    XmlResultsWriter,
    load_mask,
    validate_results_file,
)

from laue_portal.processing.compute.contract import RunHooks, RunOutcome, RunRequest, register_compute_function
from laue_portal.workflows.manifest import CATEGORY_CANCELLED, RESULTS_FILENAME, FailureRecord, ManifestEntry
from laue_portal.workflows.publication import discard_partial, partial_path, publish_file

LAUEGO_KIND = "lauego_indexing"
DEFAULT_XML_NAME = "output.xml"
DEFAULT_MAX_DATA = 200  # the displayed default for "Max spots to index"
DETECTOR_INDEX = 0  # the physical slot the old pipeline used; the UI has no detector control
ENGINE = "lauelab liblaue (in-process)"


@dataclass(frozen=True)
class IndexingSettings:
    """Validated indexing configuration derived from the frozen request."""

    geometry_file: str
    crystal_file: str
    mask_file: str | None
    peak_params: PeakParams
    index_params: IndexParams
    cosmic_filter: bool
    depth_override: float | None
    detector_index: int = DETECTOR_INDEX


def _optional_number(value: Any) -> float | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool) or not isinstance(value, Real):
        try:
            value = float(str(value).strip())
        except ValueError as error:
            raise InputError(f"{value!r} is not a number") from error
    return float(value)


def parse_depth_override(value: Any) -> float | None:
    """Depth [µm]: a finite number overrides every frame; blank or NaN means automatic."""

    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text or text.lower() == "nan":
            return None
        try:
            number = float(text)
        except ValueError as error:
            raise InputError(
                f"Depth must be a number in micrometres or blank for automatic; received {value!r}"
            ) from error
    elif isinstance(value, Real) and not isinstance(value, bool):
        number = float(value)
    else:
        raise InputError(f"Depth must be a number in micrometres or blank for automatic; received {value!r}")
    return None if math.isnan(number) else number


def settings_from_request(parameters: Mapping[str, Any]) -> IndexingSettings:
    """Map the saved form values to lauelab parameters (plan section 7.1).

    Threshold blank means automatic. A non-positive threshold ratio (the old
    ``-1`` marker) means none. ``max_number`` blank or non-positive is the
    uncapped peak search; ``max_peaks`` is the number of spots to index and
    falls back to the displayed default of 200. Integer-valued fields go to the
    library unrounded so a fractional Min Spot Size is rejected, not rounded.
    """

    threshold = _optional_number(parameters.get("threshold"))
    ratio = _optional_number(parameters.get("threshold_ratio"))
    max_peaks = _optional_number(parameters.get("max_number"))
    max_data = _optional_number(parameters.get("max_peaks"))
    peak_params = PeakParams(
        boxsize=parameters["box_size"],
        max_rfactor=float(parameters["max_rfactor"]),
        min_size=parameters["min_size"],
        min_separation=parameters["min_separation"],
        threshold=threshold,
        threshold_ratio=None if ratio is None or ratio <= 0 else ratio,
        peak_shape=str(parameters["peak_shape"]),
        max_peaks=None if max_peaks is None or max_peaks <= 0 else max_peaks,
        smooth=bool(parameters.get("smooth", False)),
    )
    index_params = IndexParams(
        kev_max_calc=float(parameters["index_kev_max_calc"]),
        kev_max_test=float(parameters["index_kev_max_test"]),
        angle_tolerance_deg=float(parameters["index_angle_tolerance"]),
        cone_deg=float(parameters["index_cone"]),
        hkl_prefer=(parameters["index_h"], parameters["index_k"], parameters["index_l"]),
        max_data=DEFAULT_MAX_DATA if max_data is None or max_data <= 0 else max_data,
    )
    mask_file = parameters.get("mask_file")
    mask_file = str(mask_file).strip() or None if mask_file is not None else None
    return IndexingSettings(
        geometry_file=str(parameters["geometry_file"]),
        crystal_file=str(parameters["crystal_file"]),
        mask_file=mask_file,
        peak_params=peak_params,
        index_params=index_params,
        cosmic_filter=False,  # disabled even when a historical request recorded True
        depth_override=parse_depth_override(parameters.get("depth")),
    )


def build_indexer(settings: IndexingSettings) -> Indexer:
    """Construct the indexer; lauelab validates parameters, geometry, and crystal here."""

    return Indexer(
        settings.geometry_file,
        settings.crystal_file,
        peak_params=settings.peak_params,
        index_params=settings.index_params,
        detector_index=settings.detector_index,
        cosmic_filter=settings.cosmic_filter,
    )


def xml_destination(request: RunRequest) -> str:
    """The configured Output XML path: absolute as given, otherwise inside the run directory."""

    name = str(request.output.get("xml") or DEFAULT_XML_NAME)
    return name if os.path.isabs(name) else os.path.join(request.run_directory, name)


def _library_provenance() -> dict[str, Any]:
    provenance: dict[str, Any] = {"engine": ENGINE}
    try:
        distribution = importlib.metadata.distribution("lauelab")
    except importlib.metadata.PackageNotFoundError:
        return provenance
    provenance["lauelab_version"] = distribution.version
    direct_url = distribution.read_text("direct_url.json")
    if direct_url:
        try:
            document = json.loads(direct_url)
        except json.JSONDecodeError:
            return provenance
        commit = document.get("vcs_info", {}).get("commit_id")
        if commit:
            provenance["lauelab_commit"] = commit
        if document.get("url"):
            provenance["lauelab_source"] = document["url"]
    return provenance


class _AdmittedEntries:
    """Hands manifest entries to ``iter_index`` lazily while remembering which were admitted."""

    def __init__(self, entries: Iterable[ManifestEntry], depth_override: float | None):
        self._entries = iter(entries)
        self._depth_override = depth_override
        self.admitted: dict[int, ManifestEntry] = {}

    def __iter__(self):
        for entry in self._entries:
            self.admitted[entry.index] = entry
            depth = entry.depth if entry.depth is not None else self._depth_override
            yield FrameInput(entry.source, input_id=entry.input_id, depth=depth)

    def remaining(self) -> Iterable[ManifestEntry]:
        """Entries never handed to the indexer (after a stop)."""

        yield from self._entries


def compute_lauego_indexing(request: RunRequest, entries: Iterable[ManifestEntry], hooks: RunHooks) -> RunOutcome:
    settings = settings_from_request(request.parameters)
    indexer = build_indexer(settings)
    mask = load_mask(settings.mask_file) if settings.mask_file else None

    os.makedirs(request.run_directory, exist_ok=True)
    results_final = os.path.join(request.run_directory, RESULTS_FILENAME)
    if os.path.exists(results_final):
        raise FileExistsError(f"{results_final} already exists; a run never overwrites a previous run's results")
    results_partial = partial_path(results_final)
    xml_final = xml_destination(request)
    xml_partial = partial_path(xml_final)

    warnings: list[str] = []
    admitted = _AdmittedEntries(entries, settings.depth_override)
    frame_ids: list[str] = []
    succeeded = failed = n_indexed = 0
    seen: set[int] = set()
    stopped = False

    xml_writer = None
    try:
        os.makedirs(os.path.dirname(xml_final) or ".", exist_ok=True)
        xml_writer = XmlResultsWriter(xml_partial, overwrite=True).__enter__()
    except Exception as error:  # the XML document is auxiliary
        warnings.append(f"XML output not started: {error}")
        xml_writer = None

    try:
        with (
            indexer.iter_index(
                admitted,
                mask=mask,
                workers=request.workers,
                max_in_flight=request.max_in_flight,
                should_stop=hooks.should_stop,
                keep_images=False,
            ) as outcomes,
            indexer.results_writer(results_partial, overwrite=True) as writer,
        ):
            for outcome in outcomes:
                entry = admitted.admitted[outcome.input_index]
                seen.add(entry.index)
                if outcome.ok:
                    writer.append(outcome.result, frame_id=entry.input_id)  # a failure here ends the run
                    frame_ids.append(entry.input_id)
                    succeeded += 1
                    if outcome.result.n_patterns > 0:
                        n_indexed += 1
                    if xml_writer is not None and not xml_writer.failed:
                        try:
                            xml_writer.append(outcome.result)
                        except Exception as error:
                            warnings.append(f"XML output stopped after {xml_writer.count} steps: {error}")
                else:
                    failed += 1
                    hooks.record_failure(
                        FailureRecord.from_error(entry, outcome.error, context={"seconds": outcome.seconds})
                    )
                hooks.report_progress(succeeded=succeeded, failed=failed)
            stopped = bool(outcomes.stopped)
    finally:
        if xml_writer is not None:
            try:
                xml_writer.__exit__(None, None, None)
            except Exception as error:
                warnings.append(f"XML output could not be closed: {error}")

    if stopped:
        for index, entry in admitted.admitted.items():
            if index not in seen:
                hooks.record_failure(
                    FailureRecord.not_run(
                        entry, category=CATEGORY_CANCELLED, message="run stopped before this input started"
                    )
                )
        for entry in admitted.remaining():
            hooks.record_failure(
                FailureRecord.not_run(
                    entry, category=CATEGORY_CANCELLED, message="run stopped before this input was admitted"
                )
            )

    if writer.failed:
        raise RuntimeError(f"results file write failed after {writer.count} frames: {writer.error}")

    outcome = RunOutcome(
        n_succeeded=succeeded,
        n_failed=failed,
        stopped=stopped,
        warnings=warnings,
        provenance={
            **_library_provenance(),
            "geometry_file": settings.geometry_file,
            "crystal_file": settings.crystal_file,
            "mask_file": settings.mask_file,
            "detector_index": indexer.detector_index,
            "detector_id": indexer.detector_id,
            "peak_params": asdict(indexer.peak_params),
            "index_params": asdict(indexer.index_params),
            "cosmic_filter": {"recorded": settings.cosmic_filter, "applied": False},
            "depth_override_um": settings.depth_override,
            "workers": request.workers,
        },
        n_indexed=n_indexed,
    )

    if succeeded == 0:
        # No frame was processed: publish no scientific file rather than an empty one.
        discard_partial(results_final)
        if xml_writer is not None:
            discard_partial(xml_final)
        outcome.summary = "no frame was processed"
        return outcome

    try:
        summary = validate_results_file(results_partial, frame_ids=frame_ids)
    except (InvalidResultsFile, OSError) as error:
        outcome.validation_error = f"{RESULTS_FILENAME}: {error}"
        outcome.summary = f"results file kept as {os.path.basename(results_partial)} for diagnosis"
        return outcome
    publish_file(results_partial, results_final)
    outcome.artifacts["results"] = results_final
    outcome.provenance["results_summary"] = {
        "n_frames": summary.n_frames,
        "n_peaks": summary.n_peaks,
        "n_patterns": summary.n_patterns,
        "n_assignments": summary.n_assignments,
    }

    if xml_writer is not None:
        if xml_writer.failed:
            warnings.append(f"XML output incomplete: {xml_writer.error}")
        elif xml_writer.count == 0:
            discard_partial(xml_final)
        else:
            try:
                publish_file(xml_partial, xml_final)
                outcome.artifacts["xml"] = xml_final
            except FileExistsError:
                warnings.append(f"XML not published: {xml_final} already exists; the run's copy is {xml_partial}")
            except OSError as error:
                warnings.append(f"XML not published: {error}")
    outcome.summary = (
        f"{summary.n_frames} frames, {summary.n_patterns} patterns, {summary.n_peaks} peaks in {RESULTS_FILENAME}"
        + (f"; {n_indexed} frames indexed" if n_indexed else "; no frame indexed")
    )
    return outcome


register_compute_function(LAUEGO_KIND, compute_lauego_indexing)
