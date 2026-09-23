"""Immutable run input manifests, frozen requests, and run-level failure reports.

Each run has a constant number of support files in its run directory:

~~~text
inputs.jsonl    ordered identity/source manifest, one JSON object per input
request.json    the frozen execution request (paths, validated settings, identities)
failures.jsonl  one JSON object per failed or unattempted input, only when needed
~~~

Identity convention (characterized 2026-09-16, plan section 3.3):

* Historical merged ``output.xml`` files were assembled by ``merge_xml_files``
  from one XML per frame, in ``sorted()`` order of the per-frame XML filenames.
  That order is lexicographic, so ``..._10.xml`` precedes ``..._2.xml``. The
  portal's ``step_index`` / "Step #" is the 0-based position in that merged
  file, and a step's frame identity is ``<detector><inputImage>`` (a path).
* A manifest ``index`` is the 0-based position in run order: filename
  templates in form order, then requested scan points in requested order, then
  depth points. ``input_id`` is the source file stem, which is what lauelab
  HDF5 results store as ``frames/frame_ids`` for new runs.
* A frame of a reconstruction-scan file has ``source`` = the scan file plus
  ``point_id`` and zero-based ``depth_index``. Its ``input_id`` is
  ``<point_id>_<depth_index>``, the stem the same frame had as a per-depth
  file ``<point_id>_<depth_index>.h5``.
* Historical positions and manifest positions therefore differ. Anything that
  refers to a frame must use ``input_id`` (or the ``inputImage`` stem of an
  old step), never a position, so no selection acquires an off-by-one change.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from laue_portal.workflows.files import ResolvedInput
from laue_portal.workflows.publication import discard_partial, partial_path, publish_file

MANIFEST_FORMAT = "laue-portal-input-manifest"
MANIFEST_VERSION = 1
REQUEST_FORMAT = "laue-portal-run-request"
REQUEST_VERSION = 1
FAILURE_REPORT_FORMAT = "laue-portal-failure-report"
FAILURE_REPORT_VERSION = 1

MANIFEST_FILENAME = "inputs.jsonl"
REQUEST_FILENAME = "request.json"
FAILURE_REPORT_FILENAME = "failures.jsonl"
RUN_SUMMARY_FILENAME = "run.json"
RESULTS_FILENAME = "output.h5"
RECONSTRUCTION_FILENAME = "reconstruction.h5"
LOG_FILENAME = "run.log"

# Names a run directory reserves for support and authoritative files. A user
# supplied XML destination may not take one of these names.
RESERVED_RUN_FILENAMES = frozenset(
    {
        MANIFEST_FILENAME,
        REQUEST_FILENAME,
        FAILURE_REPORT_FILENAME,
        RUN_SUMMARY_FILENAME,
        RESULTS_FILENAME,
        RECONSTRUCTION_FILENAME,
        LOG_FILENAME,
    }
)


class ManifestError(RuntimeError):
    """Raised when a manifest cannot be built, written, or read."""


@dataclass(frozen=True)
class ManifestEntry:
    """One input in run order with a stable identity and its selection provenance."""

    index: int
    input_id: str
    source: str
    template_index: int
    scan_point: int | None
    depth_point: int | None
    depth: float | None = None  # physical depth override in micrometres; None = from file
    point_id: str | None = None  # reconstruction-scan point; source is then the scan file
    depth_index: int | None = None  # zero-based frame of that point

    def to_json(self) -> str:
        values = asdict(self)
        if self.point_id is None:  # file inputs keep the original line format
            del values["point_id"], values["depth_index"]
        return json.dumps(values, separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def from_dict(cls, values: Mapping[str, Any]) -> ManifestEntry:
        try:
            return cls(
                index=int(values["index"]),
                input_id=str(values["input_id"]),
                source=str(values["source"]),
                template_index=int(values["template_index"]),
                scan_point=None if values.get("scan_point") is None else int(values["scan_point"]),
                depth_point=None if values.get("depth_point") is None else int(values["depth_point"]),
                depth=None if values.get("depth") is None else float(values["depth"]),
                point_id=None if values.get("point_id") is None else str(values["point_id"]),
                depth_index=None if values.get("depth_index") is None else int(values["depth_index"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ManifestError(f"malformed manifest entry: {error}") from error


@dataclass(frozen=True)
class ManifestSummary:
    path: str
    n_inputs: int
    sha256: str


def input_identity(path: str | os.PathLike[str]) -> str:
    """The identity a source file carries in results: its filename without extension."""

    return Path(path).stem


def scan_frame_identity(point_id: str, depth_index: int) -> str:
    """The identity of one reconstruction-scan frame: the stem of its per-depth file."""

    return f"{point_id}_{depth_index}"


def build_manifest_entries(
    inputs: Sequence[ResolvedInput],
    *,
    depths: Mapping[int, float] | None = None,
) -> tuple[ManifestEntry, ...]:
    """Assign manifest indices and unique identities to resolved inputs.

    Identities are file stems. If two inputs share a stem (for example ``a.h5``
    and ``a.tif``), every identity in the run falls back to the full filename so
    one rule applies to the whole manifest. Duplicate filenames are an error.
    A reconstruction-scan frame's identity is ``<point_id>_<depth_index>``.
    """

    if not inputs:
        raise ManifestError("a run needs at least one input")
    stems = [
        input_identity(entry.path) if entry.point_id is None else scan_frame_identity(entry.point_id, entry.depth_index)
        for entry in inputs
    ]
    if len(set(stems)) == len(stems):
        identities = stems
    elif any(entry.point_id is not None for entry in inputs):
        duplicate = next(name for name in stems if stems.count(name) > 1)
        raise ManifestError(f"input identity {duplicate!r} is not unique within the run")
    else:
        identities = [os.path.basename(entry.path) for entry in inputs]
        if len(set(identities)) != len(identities):
            duplicate = next(name for name in identities if identities.count(name) > 1)
            raise ManifestError(f"input identity {duplicate!r} is not unique within the run")
    depths = depths or {}
    return tuple(
        ManifestEntry(
            index=index,
            input_id=identity,
            source=entry.path,
            template_index=entry.template_index,
            scan_point=entry.scan_point,
            depth_point=entry.depth_point,
            depth=depths.get(index),
            point_id=entry.point_id,
            depth_index=entry.depth_index,
        )
        for index, (entry, identity) in enumerate(zip(inputs, identities, strict=True))
    )


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def write_manifest(
    path: str | os.PathLike[str],
    entries: Iterable[ManifestEntry],
    *,
    overwrite: bool = False,
) -> ManifestSummary:
    """Stream entries to ``path`` through a partial file; publish only when complete."""

    final = Path(path)
    partial = partial_path(final)
    digest = hashlib.sha256()
    count = 0
    try:
        with open(partial, "w", encoding="utf-8", newline="\n") as handle:
            for expected_index, entry in enumerate(entries):
                if entry.index != expected_index:
                    raise ManifestError(
                        f"manifest entry {entry.input_id!r} has index {entry.index}, expected {expected_index}"
                    )
                line = entry.to_json() + "\n"
                handle.write(line)
                digest.update(line.encode("utf-8"))
                count += 1
            handle.flush()
            os.fsync(handle.fileno())
        if count == 0:
            raise ManifestError("a manifest must contain at least one input")
        publish_file(partial, final, overwrite=overwrite)
    except BaseException:
        discard_partial(final)
        raise
    _fsync_directory(final.parent)
    return ManifestSummary(path=os.fspath(final), n_inputs=count, sha256=digest.hexdigest())


def read_manifest(path: str | os.PathLike[str]) -> Iterator[ManifestEntry]:
    """Stream manifest entries, checking that indices run 0, 1, 2, ..."""

    with open(path, encoding="utf-8") as handle:
        for expected_index, line in enumerate(handle):
            if not line.strip():
                raise ManifestError(f"{path}: blank line at entry {expected_index}")
            try:
                values = json.loads(line)
            except json.JSONDecodeError as error:
                raise ManifestError(f"{path}: entry {expected_index} is not JSON: {error}") from error
            entry = ManifestEntry.from_dict(values)
            if entry.index != expected_index:
                raise ManifestError(f"{path}: entry {expected_index} carries index {entry.index}")
            yield entry


def manifest_digest(path: str | os.PathLike[str]) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def count_manifest_entries(path: str | os.PathLike[str]) -> int:
    count = 0
    with open(path, "rb") as handle:
        for _ in handle:
            count += 1
    return count


def verify_manifest(path: str | os.PathLike[str], *, expected_digest: str, expected_count: int) -> None:
    """Confirm a manifest is the one recorded for a run before anything consumes it."""

    if not os.path.isfile(path):
        raise ManifestError(f"manifest {path} is missing")
    digest = manifest_digest(path)
    if digest != expected_digest:
        raise ManifestError(f"manifest {path} digest {digest} does not match recorded {expected_digest}")
    count = count_manifest_entries(path)
    if count != expected_count:
        raise ManifestError(f"manifest {path} holds {count} inputs; the run recorded {expected_count}")


def _json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return os.fspath(value)
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_ready(item) for item in value]
    return value


def write_json_file(path: str | os.PathLike[str], payload: Mapping[str, Any], *, overwrite: bool = False) -> str:
    """Write a JSON document through a partial file; returns its sha256."""

    final = Path(path)
    partial = partial_path(final)
    text = json.dumps(_json_ready(payload), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    try:
        with open(partial, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        publish_file(partial, final, overwrite=overwrite)
    except BaseException:
        discard_partial(final)
        raise
    _fsync_directory(final.parent)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_request(path: str | os.PathLike[str], payload: Mapping[str, Any], *, overwrite: bool = False) -> str:
    """Freeze an execution request; the document carries its format marker."""

    document = {"format": REQUEST_FORMAT, "version": REQUEST_VERSION, **payload}
    return write_json_file(path, document, overwrite=overwrite)


def read_request(path: str | os.PathLike[str]) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        document = json.load(handle)
    if not isinstance(document, dict) or document.get("format") != REQUEST_FORMAT:
        raise ManifestError(f"{path} is not a {REQUEST_FORMAT} document")
    if document.get("version") != REQUEST_VERSION:
        raise ManifestError(f"{path} has request version {document.get('version')!r}; expected {REQUEST_VERSION}")
    return document


# --- failure report -----------------------------------------------------------

# Categories are stable strings for grouping in the UI; ``error_type`` keeps
# the exact exception class for diagnosis.
CATEGORY_INPUT = "input"  # the input itself is unreadable or malformed
CATEGORY_NUMERICAL = "numerical"  # native processing failed for this input
CATEGORY_MEMORY = "memory"
CATEGORY_CANCELLED = "cancelled"  # not attempted because the run was cancelled
CATEGORY_INTERRUPTED = "interrupted"  # not attempted because the system stopped
CATEGORY_NOT_RUN = "not_run"  # not attempted for another recorded reason
CATEGORY_ERROR = "error"  # anything else

_CLASS_CATEGORIES = (
    ("NumericalIndexingError", CATEGORY_NUMERICAL),
    ("InputError", CATEGORY_INPUT),
    ("MemoryError", CATEGORY_MEMORY),
    ("FileNotFoundError", CATEGORY_INPUT),
    ("PermissionError", CATEGORY_INPUT),
    ("IsADirectoryError", CATEGORY_INPUT),
    ("KeyError", CATEGORY_INPUT),
    ("ValueError", CATEGORY_INPUT),
    ("OSError", CATEGORY_INPUT),
)


def classify_error(error: BaseException) -> str:
    """Map an exception to a report category without importing lauelab."""

    names = {klass.__name__ for klass in type(error).__mro__}
    for class_name, category in _CLASS_CATEGORIES:
        if class_name in names:
            return category
    return CATEGORY_ERROR


@dataclass(frozen=True)
class FailureRecord:
    """One failed or unattempted input."""

    index: int | None
    input_id: str | None
    source: str | None
    category: str
    message: str
    error_type: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    recorded_at: str | None = None

    @classmethod
    def from_error(
        cls,
        entry: ManifestEntry,
        error: BaseException,
        *,
        context: Mapping[str, Any] | None = None,
        now: datetime | None = None,
    ) -> FailureRecord:
        return cls(
            index=entry.index,
            input_id=entry.input_id,
            source=entry.source,
            category=classify_error(error),
            message=str(error) or type(error).__name__,
            error_type=type(error).__name__,
            context=dict(context or {}),
            recorded_at=(now or datetime.now()).isoformat(timespec="seconds"),
        )

    @classmethod
    def not_run(
        cls,
        entry: ManifestEntry,
        *,
        category: str = CATEGORY_NOT_RUN,
        message: str = "not attempted",
        now: datetime | None = None,
    ) -> FailureRecord:
        return cls(
            index=entry.index,
            input_id=entry.input_id,
            source=entry.source,
            category=category,
            message=message,
            recorded_at=(now or datetime.now()).isoformat(timespec="seconds"),
        )

    def to_json(self) -> str:
        return json.dumps(_json_ready(asdict(self)), separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def from_dict(cls, values: Mapping[str, Any]) -> FailureRecord:
        try:
            return cls(
                index=None if values.get("index") is None else int(values["index"]),
                input_id=values.get("input_id"),
                source=values.get("source"),
                category=str(values["category"]),
                message=str(values["message"]),
                error_type=values.get("error_type"),
                context=dict(values.get("context") or {}),
                recorded_at=values.get("recorded_at"),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ManifestError(f"malformed failure record: {error}") from error


class FailureReportWriter:
    """Append-only JSONL failure report that creates no file when nothing failed.

    Records go to the partial file as they arrive and are published on
    ``close()``; a crash leaves the partial in place for diagnosis without ever
    presenting an unfinished report as complete.
    """

    def __init__(self, path: str | os.PathLike[str], *, overwrite: bool = False) -> None:
        self._final = Path(path)
        self._overwrite = overwrite
        self._handle = None
        self._count = 0
        self._closed = False
        if not overwrite and self._final.exists():
            raise FileExistsError(f"failure report {self._final} already exists")

    @property
    def count(self) -> int:
        return self._count

    @property
    def path(self) -> str:
        return os.fspath(self._final)

    def append(self, record: FailureRecord) -> None:
        if self._closed:
            raise RuntimeError("failure report is closed")
        if self._handle is None:
            self._handle = open(partial_path(self._final), "w", encoding="utf-8", newline="\n")
        self._handle.write(record.to_json() + "\n")
        self._handle.flush()
        self._count += 1

    def close(self) -> str | None:
        """Publish the report and return its path, or None when nothing was recorded."""

        if self._closed:
            return self.path if self._count else None
        self._closed = True
        if self._handle is None:
            return None
        try:
            os.fsync(self._handle.fileno())
            self._handle.close()
            publish_file(partial_path(self._final), self._final, overwrite=self._overwrite)
        except BaseException:
            discard_partial(self._final)
            raise
        _fsync_directory(self._final.parent)
        return self.path

    def __enter__(self) -> FailureReportWriter:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        if exc_type is None:
            self.close()
            return
        self._closed = True
        if self._handle is not None:
            try:
                self._handle.close()
            finally:
                pass  # keep the partial file for diagnosis


def count_failure_records(path: str | os.PathLike[str]) -> int:
    return count_manifest_entries(path)


def read_failure_report(
    path: str | os.PathLike[str],
    *,
    offset: int = 0,
    limit: int = 100,
) -> tuple[list[FailureRecord], bool]:
    """Read one bounded page of records; returns ``(records, has_more)``."""

    if offset < 0 or limit <= 0:
        raise ValueError("offset must be >= 0 and limit > 0")
    records: list[FailureRecord] = []
    has_more = False
    with open(path, encoding="utf-8") as handle:
        for position, line in enumerate(handle):
            if position < offset:
                continue
            if len(records) == limit:
                has_more = True
                break
            if not line.strip():
                continue
            try:
                records.append(FailureRecord.from_dict(json.loads(line)))
            except json.JSONDecodeError as error:
                raise ManifestError(f"{path}: record {position} is not JSON: {error}") from error
    return records, has_more
