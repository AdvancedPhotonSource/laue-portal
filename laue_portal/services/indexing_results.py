"""Discovery and conversion of indexing results, shared by page callbacks and the CLI.

Resolution order for one indexing run (plan section 5, P4):

1. The run's explicit ``results_path`` reference, validated as an indexing-results file.
2. The canonical ``output.h5`` in the run directory, validated the same way.
3. The recorded historical XML, or the single XML in the run directory when the recorded
   name is absent. Several candidates are ambiguous and never chosen silently.

An HDF5 file is accepted only when it carries the lauelab results format marker and passes
structural validation: detector frames share the extension and an interrupted write still
carries the marker. Conversion goes through ``lauelab.visualization.convert_xml``, which
writes privately, validates, and publishes by rename; the database pointer is updated only
after that publication. Identical XML documents shared by several historical records are
converted once and every record is linked to the same file.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import lauelab
from lauelab.indexing import InvalidResultsFile, ResultsFileSummary, validate_results_file
from lauelab.visualization import convert_xml
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, joinedload

from laue_portal.database import db_schema, session_utils
from laue_portal.workflows.manifest import RESULTS_FILENAME

logger = logging.getLogger(__name__)

# Resolution statuses
STATUS_RESULTS = "results"  # a validated results file is available
STATUS_XML_ONLY = "xml_only"  # only a historical XML document; conversion possible
STATUS_AMBIGUOUS = "ambiguous"  # several XML candidates; a person must choose
STATUS_MISSING = "missing"  # nothing usable found

# Conversion outcomes
OUTCOME_ALREADY_CONVERTED = "already_converted"
OUTCOME_CONVERTED = "converted"
OUTCOME_LINKED = "linked"  # identical source already converted for another record
OUTCOME_WOULD_CONVERT = "would_convert"  # dry run
OUTCOME_MISSING = "missing"
OUTCOME_MALFORMED = "malformed"
OUTCOME_AMBIGUOUS = "ambiguous"
OUTCOME_INVALID_EXISTING = "invalid_existing"  # destination exists but is not a valid results file
OUTCOME_FAILED = "failed"
OUTCOME_ORDER = (
    OUTCOME_CONVERTED,
    OUTCOME_LINKED,
    OUTCOME_ALREADY_CONVERTED,
    OUTCOME_WOULD_CONVERT,
    OUTCOME_MISSING,
    OUTCOME_MALFORMED,
    OUTCOME_AMBIGUOUS,
    OUTCOME_INVALID_EXISTING,
    OUTCOME_FAILED,
)


@dataclass(frozen=True)
class ArtifactResolution:
    """What one indexing run has on disk, found in the documented order."""

    indexing_id: int
    run_directory: str | None
    status: str
    results_path: str | None = None
    results_source: str | None = None  # "recorded" or "canonical"
    results_summary: ResultsFileSummary | None = None
    xml_path: str | None = None
    xml_candidates: tuple[str, ...] = ()
    problems: tuple[str, ...] = ()

    @property
    def convertible(self) -> bool:
        return self.status == STATUS_XML_ONLY

    def as_dict(self) -> dict:
        """JSON-safe form for a Dash store or a report."""

        summary = None
        if self.results_summary is not None:
            summary = {
                "n_frames": self.results_summary.n_frames,
                "n_peaks": self.results_summary.n_peaks,
                "n_patterns": self.results_summary.n_patterns,
                "has_crystal": self.results_summary.has_crystal,
                "has_geometry_text": self.results_summary.has_geometry_text,
                "source": self.results_summary.source,
                "lauelab_version": self.results_summary.lauelab_version,
            }
        return {
            "indexing_id": self.indexing_id,
            "run_directory": self.run_directory,
            "status": self.status,
            "results_path": self.results_path,
            "results_source": self.results_source,
            "results_summary": summary,
            "xml_path": self.xml_path,
            "xml_candidates": list(self.xml_candidates),
            "problems": list(self.problems),
        }


def validate_results(path: str | os.PathLike[str]) -> tuple[ResultsFileSummary | None, str | None]:
    """Return (summary, None) for a valid results file, else (None, reason)."""

    path = Path(path)
    if not path.is_file():
        return None, f"{path} does not exist"
    if not lauelab.is_results_file(path):
        return None, f"{path} is not a lauelab indexing-results file"
    try:
        return validate_results_file(path), None
    except (InvalidResultsFile, OSError) as error:
        return None, f"{path} failed validation: {error}"


def _xml_candidates(run: db_schema.IndexingRun) -> tuple[str | None, tuple[str, ...]]:
    """The recorded XML if it exists, otherwise the XML files found in the run directory."""

    parameters = run.lauego_parameters
    output_xml = parameters.output_xml if parameters is not None else None
    if output_xml:
        candidate = Path(output_xml)
        if candidate.is_file():
            return str(candidate), ()
        if run.output_path:
            candidate = Path(run.output_path) / output_xml
            if candidate.is_file():
                return str(candidate), ()
    if run.output_path and Path(run.output_path).is_dir():
        found = tuple(sorted(str(path) for path in Path(run.output_path).glob("*.xml")))
        if len(found) == 1:
            return found[0], ()
        return None, found
    return None, ()


def deterministic_xml_path(run: db_schema.IndexingRun) -> str | None:
    """The historical XML of a run when it can be named without guessing, else None."""

    xml_path, _ = _xml_candidates(run)
    return xml_path


def resolve_indexing_artifacts(run: db_schema.IndexingRun) -> ArtifactResolution:
    """Apply the resolution order to one loaded run (parameters must be loaded)."""

    problems: list[str] = []
    run_directory = run.output_path

    if run.results_path:
        summary, reason = validate_results(run.results_path)
        if summary is not None:
            return ArtifactResolution(
                run.id, run_directory, STATUS_RESULTS, run.results_path, "recorded", summary, problems=tuple(problems)
            )
        problems.append(f"recorded results reference unusable: {reason}")

    if run_directory:
        canonical = os.path.join(run_directory, RESULTS_FILENAME)
        if os.path.exists(canonical):
            summary, reason = validate_results(canonical)
            if summary is not None:
                return ArtifactResolution(
                    run.id, run_directory, STATUS_RESULTS, canonical, "canonical", summary, problems=tuple(problems)
                )
            problems.append(f"canonical results file unusable: {reason}")

    xml_path, candidates = _xml_candidates(run)
    if xml_path is not None:
        return ArtifactResolution(run.id, run_directory, STATUS_XML_ONLY, xml_path=xml_path, problems=tuple(problems))
    if len(candidates) > 1:
        problems.append(f"{len(candidates)} XML files in the run directory and the recorded name is absent")
        return ArtifactResolution(
            run.id, run_directory, STATUS_AMBIGUOUS, xml_candidates=candidates, problems=tuple(problems)
        )
    problems.append("no results file and no XML document found")
    return ArtifactResolution(run.id, run_directory, STATUS_MISSING, problems=tuple(problems))


def load_indexing_run(session: Session, indexing_id: int) -> db_schema.IndexingRun | None:
    return session.scalars(
        select(db_schema.IndexingRun)
        .where(db_schema.IndexingRun.id == indexing_id)
        .options(joinedload(db_schema.IndexingRun.lauego_parameters))
    ).one_or_none()


def resolve_for_indexing_id(indexing_id: int, *, engine: Engine | None = None) -> ArtifactResolution | None:
    engine = engine or session_utils.get_engine()
    with Session(engine) as session:
        run = load_indexing_run(session, indexing_id)
        return None if run is None else resolve_indexing_artifacts(run)


# --- conversion ----------------------------------------------------------------


@dataclass(frozen=True)
class ConversionOutcome:
    indexing_id: int
    outcome: str
    message: str
    source: str | None = None
    destination: str | None = None
    n_frames: int | None = None
    linked_to: int | None = None  # indexing id whose conversion this record shares


@dataclass
class ConversionReport:
    dry_run: bool
    started_at: str
    outcomes: list[ConversionOutcome] = field(default_factory=list)
    finished_at: str | None = None

    def counts(self) -> dict[str, int]:
        counts = {name: 0 for name in OUTCOME_ORDER}
        for outcome in self.outcomes:
            counts[outcome.outcome] = counts.get(outcome.outcome, 0) + 1
        return counts

    def as_json(self) -> dict:
        return {
            "format": "laue-portal-conversion-report",
            "version": 1,
            "dry_run": self.dry_run,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "counts": self.counts(),
            "outcomes": [asdict(outcome) for outcome in self.outcomes],
        }

    def format_text(self) -> str:
        lines = [f"{'DRY RUN: ' if self.dry_run else ''}{len(self.outcomes)} indexing run(s) examined"]
        for name, count in self.counts().items():
            if count:
                lines.append(f"  {name}: {count}")
        for outcome in self.outcomes:
            extra = (
                f" -> {outcome.destination}"
                if outcome.destination and outcome.outcome != OUTCOME_ALREADY_CONVERTED
                else ""
            )
            lines.append(f"I{outcome.indexing_id}: {outcome.outcome}: {outcome.message}{extra}")
        return "\n".join(lines)


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def conversion_destination(run: db_schema.IndexingRun, destination_root: str | None) -> str | None:
    """Canonical ``output.h5`` in the run directory, or under an explicit root per run."""

    if destination_root:
        return os.path.join(destination_root, f"index_{run.id}", RESULTS_FILENAME)
    if run.output_path:
        return os.path.join(run.output_path, RESULTS_FILENAME)
    return None


def _set_results_path(engine: Engine, indexing_id: int, path: str) -> None:
    with Session(engine) as session, session.begin():
        run = session.get(db_schema.IndexingRun, indexing_id)
        if run is not None:
            run.results_path = path


def convert_indexing_results(
    indexing_ids: Sequence[int] | None = None,
    *,
    engine: Engine | None = None,
    dry_run: bool = False,
    destination_root: str | None = None,
    geometry: str | None = None,
    replace_invalid: bool = False,
    progress: Callable[[ConversionOutcome], None] | None = None,
) -> ConversionReport:
    """Convert historical XML results to results files for the given runs (all when None).

    Safe to rerun: a valid destination is reported as already converted and its
    pointer recorded; an existing invalid destination is reported, not replaced,
    unless ``replace_invalid`` is set. One failure never stops the batch.
    """

    engine = engine or session_utils.get_engine()
    report = ConversionReport(dry_run=dry_run, started_at=datetime.now().isoformat(timespec="seconds"))
    converted_by_digest: dict[str, tuple[int, str]] = {}

    with Session(engine) as session:
        statement = select(db_schema.IndexingRun).options(joinedload(db_schema.IndexingRun.lauego_parameters))
        if indexing_ids is not None:
            statement = statement.where(db_schema.IndexingRun.id.in_([int(value) for value in indexing_ids]))
        runs = session.scalars(statement.order_by(db_schema.IndexingRun.id)).unique().all()
        session.expunge_all()
    found = {run.id for run in runs}
    for missing_id in sorted(set(int(value) for value in (indexing_ids or ())) - found):
        report.outcomes.append(ConversionOutcome(missing_id, OUTCOME_MISSING, "no such indexing run"))

    for run in runs:
        outcome = _convert_one(run, engine, dry_run, destination_root, geometry, replace_invalid, converted_by_digest)
        report.outcomes.append(outcome)
        if progress is not None:
            progress(outcome)
    report.finished_at = datetime.now().isoformat(timespec="seconds")
    return report


def _convert_one(
    run: db_schema.IndexingRun,
    engine: Engine,
    dry_run: bool,
    destination_root: str | None,
    geometry: str | None,
    replace_invalid: bool,
    converted_by_digest: dict[str, tuple[int, str]],
) -> ConversionOutcome:
    resolution = resolve_indexing_artifacts(run)
    if resolution.status == STATUS_RESULTS:
        if not dry_run and run.results_path != resolution.results_path:
            _set_results_path(engine, run.id, resolution.results_path)
        if resolution.results_summary is not None and resolution.results_summary.source:
            digest_source = resolution.results_summary.source
            if os.path.isfile(digest_source):
                converted_by_digest.setdefault(_sha256(digest_source), (run.id, resolution.results_path))
        return ConversionOutcome(
            run.id,
            OUTCOME_ALREADY_CONVERTED,
            f"valid results file ({resolution.results_source})",
            destination=resolution.results_path,
            n_frames=resolution.results_summary.n_frames if resolution.results_summary else None,
        )
    if resolution.status == STATUS_AMBIGUOUS:
        return ConversionOutcome(
            run.id, OUTCOME_AMBIGUOUS, "; ".join(resolution.problems) + ": " + ", ".join(resolution.xml_candidates)
        )
    if resolution.status != STATUS_XML_ONLY:
        return ConversionOutcome(run.id, OUTCOME_MISSING, "; ".join(resolution.problems))

    xml_path = resolution.xml_path
    destination = conversion_destination(run, destination_root)
    if destination is None:
        return ConversionOutcome(
            run.id, OUTCOME_MISSING, "run has no output directory to receive output.h5", source=xml_path
        )

    try:
        digest = _sha256(xml_path)
    except OSError as error:
        return ConversionOutcome(run.id, OUTCOME_MISSING, f"cannot read {xml_path}: {error}", source=xml_path)
    if digest in converted_by_digest:
        owner_id, shared_path = converted_by_digest[digest]
        if not dry_run:
            _set_results_path(engine, run.id, shared_path)
        return ConversionOutcome(
            run.id,
            OUTCOME_LINKED,
            f"identical XML already converted for I{owner_id}",
            source=xml_path,
            destination=shared_path,
            linked_to=owner_id,
        )

    if os.path.exists(destination):
        existing, reason = validate_results(destination)
        if existing is not None:  # a concurrent conversion finished first
            if not dry_run:
                _set_results_path(engine, run.id, destination)
            return ConversionOutcome(
                run.id,
                OUTCOME_ALREADY_CONVERTED,
                "valid results file (canonical)",
                xml_path,
                destination,
                existing.n_frames,
            )
        if not replace_invalid:
            return ConversionOutcome(
                run.id,
                OUTCOME_INVALID_EXISTING,
                f"destination exists but is not a valid results file: {reason}",
                xml_path,
                destination,
            )

    if dry_run:
        return ConversionOutcome(run.id, OUTCOME_WOULD_CONVERT, "would convert", xml_path, destination)

    try:
        published = convert_xml(xml_path, destination, geometry=geometry, overwrite=replace_invalid)
    except FileNotFoundError as error:
        return ConversionOutcome(
            run.id, OUTCOME_MISSING, f"XML vanished before conversion: {error}", xml_path, destination
        )
    except InvalidResultsFile as error:
        # The document parsed but the converter's output does not satisfy the results layout: a
        # historical variant the library cannot represent, not a broken file. Reported as failed.
        return ConversionOutcome(
            run.id,
            OUTCOME_FAILED,
            f"converter output failed validation: {error}{diagnose_xml(xml_path)}",
            xml_path,
            destination,
        )
    except (ET.ParseError, ValueError) as error:
        return ConversionOutcome(run.id, OUTCOME_MALFORMED, f"{type(error).__name__}: {error}", xml_path, destination)
    except FileExistsError:
        existing, reason = validate_results(destination)  # another converter published meanwhile
        if existing is not None:
            _set_results_path(engine, run.id, destination)
            return ConversionOutcome(
                run.id, OUTCOME_ALREADY_CONVERTED, "published concurrently", xml_path, destination, existing.n_frames
            )
        return ConversionOutcome(
            run.id,
            OUTCOME_FAILED,
            f"destination appeared during conversion and is invalid: {reason}",
            xml_path,
            destination,
        )
    except (OSError, MemoryError) as error:
        return ConversionOutcome(run.id, OUTCOME_FAILED, f"{type(error).__name__}: {error}", xml_path, destination)
    except Exception as error:  # one bad document must not stop the batch
        logger.exception("Conversion of I%s failed", run.id)
        return ConversionOutcome(run.id, OUTCOME_FAILED, f"{type(error).__name__}: {error}", xml_path, destination)

    summary, reason = validate_results(published)
    if summary is None:
        return ConversionOutcome(
            run.id, OUTCOME_FAILED, f"published file failed re-validation: {reason}", xml_path, str(published)
        )
    _set_results_path(engine, run.id, str(published))
    converted_by_digest[digest] = (run.id, str(published))
    return ConversionOutcome(
        run.id,
        OUTCOME_CONVERTED,
        f"{summary.n_frames} frames, {summary.n_patterns} patterns"
        + ("" if summary.has_crystal else "; no crystal context in the XML"),
        xml_path,
        str(published),
        summary.n_frames,
    )


def diagnose_xml(xml_path: str) -> str:
    """A hint about known historical XML variants the converter cannot represent."""

    try:
        root = ET.parse(xml_path).getroot()
    except (ET.ParseError, OSError):
        return ""
    patterns = root.findall("step/indexing/pattern")
    without_peak_indices = 0
    count_disagreements = 0
    for pattern in patterns:
        hkl = pattern.find("hkl_s")
        peak_indices = hkl.find("PkIndex") if hkl is not None else None
        if peak_indices is None:
            without_peak_indices += 1
            continue
        listed = len(peak_indices.text.split()) if peak_indices.text else 0
        recorded = pattern.get("Nindexed")
        if recorded is not None and recorded.strip().isdigit() and int(recorded) != listed:
            count_disagreements += 1
    hints = []
    if without_peak_indices:
        hints.append(
            f"{without_peak_indices} of {len(patterns)} patterns have hkl assignments without PkIndex, so the "
            f"indexed peaks cannot be identified"
        )
    if count_disagreements:
        hints.append(
            f"{count_disagreements} of {len(patterns)} patterns have an Nindexed attribute that disagrees with the "
            f"number of hkl assignments listed"
        )
    if not hints:
        return ""
    return "; " + "; ".join(hints) + " (a historical variant the converter does not yet handle)"


def write_report(report: ConversionReport, path: str | os.PathLike[str]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(report.as_json(), handle, indent=2, sort_keys=True)
        handle.write("\n")


def all_indexing_ids(engine: Engine | None = None) -> list[int]:
    engine = engine or session_utils.get_engine()
    with Session(engine) as session:
        return list(session.scalars(select(db_schema.IndexingRun.id).order_by(db_schema.IndexingRun.id)))


def iter_ids(values: Iterable[str]) -> list[int]:
    """Parse ``I12``, ``12``, and ``3-7`` style identifiers."""

    ids: list[int] = []
    for value in values:
        text = str(value).strip().upper().lstrip("I")
        if "-" in text:
            start, end = text.split("-", 1)
            ids.extend(range(int(start), int(end) + 1))
        elif text:
            ids.append(int(text))
    return ids
