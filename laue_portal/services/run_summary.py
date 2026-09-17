"""Run-level details for the job page: counters, configuration, versions, artifacts, diagnostics.

Everything here reads the run's constant set of artifacts (``request.json``,
``run.json``, ``failures.jsonl``) and the migration export of a historical run.
Nothing enumerates inputs: the failure report is read one bounded page at a time
and the run log is truncated to its tail.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from laue_portal.database import db_schema
from laue_portal.workflows.manifest import RUN_SUMMARY_FILENAME, FailureRecord
from laue_portal.workflows.progress import RunProgress, failure_page

MAX_LOG_LINES = 50
MAX_JSON_BYTES = 4 * 1024 * 1024
FAILURE_PAGE_SIZE = 50
HISTORY_FILENAME = "history.json"


@dataclass(frozen=True)
class RunDetails:
    """What the job page shows besides the job row itself."""

    progress: RunProgress
    kind: str | None
    display_id: str | None
    run_directory: str | None
    request: dict[str, Any] | None  # request.json: the frozen submission
    summary: dict[str, Any] | None  # run.json: effective execution, versions, artifacts
    history: dict[str, Any] | None  # migration export of a historical per-input run
    results_path: str | None
    problems: tuple[str, ...] = field(default_factory=tuple)

    @property
    def artifacts(self) -> dict[str, str]:
        artifacts = dict((self.summary or {}).get("artifacts") or {})
        if self.results_path and "results" not in artifacts:
            artifacts["results"] = self.results_path
        return artifacts

    @property
    def is_historical(self) -> bool:
        return self.summary is None and self.request is None and self.history is not None

    @property
    def log_tail(self) -> list[str]:
        lines = list((self.summary or {}).get("log") or [])
        return [str(line) for line in lines[-MAX_LOG_LINES:]]

    @property
    def log_truncated(self) -> int:
        lines = (self.summary or {}).get("log") or []
        return max(len(lines) - MAX_LOG_LINES, 0)


def _read_json(path: str | None, problems: list[str], label: str) -> dict[str, Any] | None:
    if not path:
        return None
    try:
        if os.path.getsize(path) > MAX_JSON_BYTES:
            problems.append(f"{label} at {path} is larger than {MAX_JSON_BYTES // (1024 * 1024)} MB and was not read")
            return None
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as error:
        problems.append(f"{label} at {path} could not be read: {error}")
        return None
    if not isinstance(document, dict):
        problems.append(f"{label} at {path} is not a JSON object")
        return None
    return document


def _history_path(progress: RunProgress) -> str | None:
    """The migration export's history.json sits next to the exported failure report."""

    if not progress.failure_report_path:
        return None
    candidate = os.path.join(os.path.dirname(progress.failure_report_path), HISTORY_FILENAME)
    return candidate if os.path.exists(candidate) else None


def load_run_details(session: Session, job_id: int) -> RunDetails | None:
    job = session.get(db_schema.Job, job_id)
    if job is None:
        return None
    progress = RunProgress.from_job(job)
    problems: list[str] = []
    request = _read_json(job.request_path, problems, "request.json")
    summary_path = os.path.join(job.run_directory, RUN_SUMMARY_FILENAME) if job.run_directory else None
    summary = _read_json(summary_path, problems, "run.json")
    history = None if summary is not None else _read_json(_history_path(progress), problems, HISTORY_FILENAME)

    kind = (summary or {}).get("kind") or (request or {}).get("kind")
    display_id = (summary or {}).get("display_id")
    results_path = None
    if job.indexing_run is not None:
        results_path = job.indexing_run.results_path
        kind = kind or "lauego_indexing"
        display_id = display_id or f"Indexing I{job.indexing_run.id}"
    elif job.reconstruction_run is not None:
        kind = kind or f"{job.reconstruction_run.method}_reconstruction"
        display_id = display_id or f"Reconstruction R{job.reconstruction_run.id}"
    return RunDetails(
        progress=progress,
        kind=kind,
        display_id=display_id,
        run_directory=job.run_directory,
        request=request,
        summary=summary,
        history=history,
        results_path=results_path,
        problems=tuple(problems),
    )


def _format_value(value: Any) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (list, tuple)):
        return ", ".join(_format_value(item) for item in value) if value else "—"
    if isinstance(value, dict):
        return json.dumps(value, default=str)
    return str(value)


def request_rows(details: RunDetails) -> list[tuple[str, str]]:
    """``(label, value)`` pairs describing the submitted configuration, in submission order."""

    document = details.request or {}
    rows: list[tuple[str, str]] = []
    for key, value in (document.get("request") or {}).items():
        if key in ("submitted_at", "computer_name", "priority"):
            continue
        rows.append((key.replace("_", " "), _format_value(value)))
    output = document.get("output") or {}
    for key, value in output.items():
        rows.append((f"output {key}", _format_value(value)))
    manifest = document.get("manifest") or {}
    if manifest:
        rows.append(("manifest", f"{manifest.get('path', '—')} ({manifest.get('n_inputs', '?')} inputs)"))
        if manifest.get("sha256"):
            rows.append(("manifest sha256", str(manifest["sha256"])))
    return rows


def execution_rows(details: RunDetails) -> list[tuple[str, str]]:
    """``(label, value)`` pairs for the effective execution: versions, policy, host, artifacts."""

    summary = details.summary or {}
    rows: list[tuple[str, str]] = []
    provenance = summary.get("provenance") or {}
    for key, value in provenance.items():
        rows.append((key.replace("_", " "), _format_value(value)))
    policy = summary.get("policy") or {}
    for key, value in policy.items():
        rows.append((key.replace("_", " "), _format_value(value)))
    if summary.get("host"):
        rows.append(("host", str(summary["host"])))
    if summary.get("started_at") or summary.get("finished_at"):
        rows.append(("executed", f"{summary.get('started_at', '—')} to {summary.get('finished_at', '—')}"))
    counters = summary.get("counters") or {}
    if counters.get("n_indexed") is not None:
        rows.append(("frames indexed", str(counters["n_indexed"])))
    return rows


def history_rows(details: RunDetails) -> list[tuple[str, str]]:
    """``(label, value)`` pairs for a run migrated from per-input records."""

    history = details.history or {}
    rows: list[tuple[str, str]] = []
    if history.get("original_status_name"):
        rows.append(("recorded status", str(history["original_status_name"])))
    time_range = history.get("subjob_time_range") or [None, None]
    if any(time_range):
        rows.append(("per-input work", f"{time_range[0] or '—'} to {time_range[1] or '—'}"))
    classes = history.get("message_classes") or {}
    for message, count in sorted(classes.items(), key=lambda item: -item[1])[:10]:
        rows.append((f"{count} input(s)", str(message)))
    return rows


def failure_records(
    details: RunDetails, *, offset: int, limit: int = FAILURE_PAGE_SIZE
) -> tuple[list[FailureRecord], bool]:
    """One bounded page of failed or unattempted inputs."""

    return failure_page(details.progress, offset=max(offset, 0), limit=limit)


def failure_total(details: RunDetails) -> int:
    """How many records the failure report holds for a terminal run: failed plus not-run inputs."""

    progress = details.progress
    return progress.n_failed + (progress.n_not_run if progress.is_terminal else 0)
