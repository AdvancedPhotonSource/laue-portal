"""The one RQ task per run: load the frozen request, compute and write, finalize.

``execute_run`` is the only function the queue runs. It adapts the persisted job
to the plain compute function from ``laue_portal.processing.compute`` and owns
progress persistence, cooperative cancellation, cleanup of compute descendants,
and the terminal status decision. The final status depends on the authoritative
output's validation, not only on counts.
"""

from __future__ import annotations

import logging
import os
import platform
import signal
import threading
import time
from dataclasses import dataclass
from datetime import datetime

from rq.timeouts import BaseTimeoutException
from sqlalchemy import Engine
from sqlalchemy.orm import Session

import laue_portal.database.session_utils as session_utils
from laue_portal.database import db_schema
from laue_portal.processing.compute import RunOutcome, RunRequest, get_compute_function
from laue_portal.processing.queue.core import RUN_POLICY, RunPolicy
from laue_portal.processing.queue.lifecycle import (
    SHUTDOWN_SIGNAL,
    STOP_REASON_SHUTDOWN,
    ProgressRecorder,
    RunMonitor,
    terminate_descendants,
)
from laue_portal.workflows import execution
from laue_portal.workflows.execution import JobStatus, RunPhase
from laue_portal.workflows.manifest import (
    FAILURE_REPORT_FILENAME,
    RUN_SUMMARY_FILENAME,
    FailureRecord,
    FailureReportWriter,
    read_manifest,
    read_request,
    verify_manifest,
    write_json_file,
)

logger = logging.getLogger(__name__)

RUN_SUMMARY_FORMAT = "laue-portal-run-summary"
RUN_SUMMARY_VERSION = 1


class RunSetupError(RuntimeError):
    """The run could not be started from its persisted state."""


@dataclass
class _Decision:
    status: JobStatus
    message: str
    phase: RunPhase | None = None


class ExecutorHooks:
    """The hooks handed to a compute function."""

    def __init__(self, job_id: int, monitor: RunMonitor, recorder: ProgressRecorder, failures: FailureReportWriter):
        self._job_id = job_id
        self._monitor = monitor
        self._recorder = recorder
        self._failures = failures
        self.messages: list[str] = []

    def should_stop(self) -> bool:
        return self._monitor.stop_requested

    def report_progress(self, *, succeeded: int, failed: int) -> None:
        self._recorder.report(succeeded=succeeded, failed=failed)

    def record_failure(self, record: FailureRecord) -> None:
        self._failures.append(record)

    def log(self, message: str) -> None:
        self.messages.append(message)
        logger.info("Run %s: %s", self._job_id, message)


def _display_id(job: db_schema.Job) -> str:
    if job.indexing_run is not None:
        return f"Indexing I{job.indexing_run.id}"
    if job.reconstruction_run is not None:
        return f"Reconstruction R{job.reconstruction_run.id}"
    return f"Job {job.job_id}"


def _start(engine: Engine, job_id: int, policy: RunPolicy) -> tuple[RunRequest | None, str | None]:
    """Claim the job for execution; returns (request, None) or (None, reason) when nothing should run."""

    with Session(engine) as session, session.begin():
        job = session.get(db_schema.Job, job_id)
        if job is None:
            raise RunSetupError(f"job {job_id} does not exist")
        if job.status != JobStatus.QUEUED or job.phase != RunPhase.QUEUED:
            return (
                None,
                f"job {job_id} is {job.phase!r}/{execution.STATUS_NAMES.get(JobStatus(job.status), job.status)}",
            )
        if job.cancel_requested_at is not None:
            execution.finalize(job, status=JobStatus.CANCELLED, message="Cancelled before the run started")
            return None, f"job {job_id} was cancelled before it started"
        if not job.manifest_path or not job.request_path or not job.run_directory:
            execution.record_failure(job, "Run setup failed: the job has no published manifest")
            raise RunSetupError(f"job {job_id} has no published manifest")
        try:
            verify_manifest(job.manifest_path, expected_digest=job.manifest_digest or "", expected_count=job.n_inputs)
            document = read_request(job.request_path)
        except Exception as error:
            execution.record_failure(job, f"Run setup failed: {error}")
            raise RunSetupError(f"job {job_id}: {error}") from error
        request = RunRequest(
            job_id=job_id,
            kind=str(document.get("kind")),
            display_id=_display_id(job),
            run_directory=job.run_directory,
            manifest_path=job.manifest_path,
            document=document,
            n_inputs=job.n_inputs,
            workers=policy.workers,
            max_in_flight=policy.max_in_flight,
        )
        execution.mark_running(job)
    return request, None


def _decide(
    request: RunRequest,
    outcome: RunOutcome | None,
    error: BaseException | None,
    stop_reason: str | None,
    policy: RunPolicy,
    processed: tuple[int, int],
) -> _Decision:
    succeeded, failed = processed
    not_run = request.n_inputs - succeeded - failed
    counts = f"{succeeded} succeeded, {failed} failed, {not_run} not run of {request.n_inputs}"
    if isinstance(error, BaseTimeoutException):
        return _Decision(
            JobStatus.FAILED,
            f"Run exceeded the configured limit of {policy.job_timeout_seconds} s; {counts}",
        )
    if error is not None:
        return _Decision(JobStatus.FAILED, f"Run failed: {type(error).__name__}: {error}; {counts}")
    assert outcome is not None
    if outcome.validation_error:
        return _Decision(
            JobStatus.FAILED, f"Authoritative output failed validation: {outcome.validation_error}; {counts}"
        )
    if outcome.stopped and stop_reason == STOP_REASON_SHUTDOWN:
        return _Decision(
            JobStatus.FAILED, f"Stopped by service shutdown; completed results kept; {counts}", RunPhase.INTERRUPTED
        )
    if outcome.stopped:
        return _Decision(JobStatus.CANCELLED, f"Cancelled by request; completed results kept; {counts}")
    if succeeded == 0 and request.n_inputs > 0:
        return _Decision(JobStatus.FAILED, f"All inputs failed; {counts}")
    if failed > 0 or succeeded < request.n_inputs:
        return _Decision(JobStatus.FAILED, f"Incomplete: {counts}")
    summary = outcome.summary or "all inputs processed"
    return _Decision(JobStatus.FINISHED, f"Finished: {counts}; {summary}")


def _write_run_summary(
    request: RunRequest,
    decision: _Decision,
    outcome: RunOutcome | None,
    *,
    started_at: datetime,
    finished_at: datetime,
    processed: tuple[int, int],
    failure_report: str | None,
    policy: RunPolicy,
    hook_messages: list[str],
) -> str:
    succeeded, failed = processed
    document = {
        "format": RUN_SUMMARY_FORMAT,
        "version": RUN_SUMMARY_VERSION,
        "job_id": request.job_id,
        "display_id": request.display_id,
        "kind": request.kind,
        "status": execution.STATUS_NAMES[decision.status],
        "phase": str(decision.phase or execution._PHASE_FOR_STATUS[decision.status]),
        "message": decision.message,
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": finished_at.isoformat(timespec="seconds"),
        "counters": {
            "n_inputs": request.n_inputs,
            "n_succeeded": succeeded,
            "n_failed": failed,
            "n_not_run": request.n_inputs - succeeded - failed,
            "n_indexed": outcome.n_indexed if outcome else None,
        },
        "artifacts": dict(outcome.artifacts) if outcome else {},
        "warnings": list(outcome.warnings) if outcome else [],
        "validation_error": outcome.validation_error if outcome else None,
        "provenance": dict(outcome.provenance) if outcome else {},
        "failure_report": os.path.basename(failure_report) if failure_report else None,
        "policy": {
            "job_timeout_seconds": policy.job_timeout_seconds,
            "workers": policy.workers,
            "max_in_flight": policy.max_in_flight,
        },
        "host": platform.node(),
        "log": hook_messages,
    }
    path = os.path.join(request.run_directory, RUN_SUMMARY_FILENAME)
    write_json_file(path, document, overwrite=True)
    return path


def execute_run(job_id: int, *, engine: Engine | None = None, policy: RunPolicy | None = None) -> dict | None:
    """Run one persisted job to a terminal state. Returns a summary, or None when nothing ran."""

    engine = engine or session_utils.get_engine()
    policy = policy or RUN_POLICY
    request, skipped = _start(engine, job_id, policy)
    if request is None:
        logger.info("Skipping run %s: %s", job_id, skipped)
        return None

    started_at = datetime.now()
    started_clock = time.monotonic()
    monitor = RunMonitor(engine, job_id, policy)
    recorder = ProgressRecorder(engine, job_id, policy.progress_seconds)
    failures = FailureReportWriter(os.path.join(request.run_directory, FAILURE_REPORT_FILENAME), overwrite=True)
    hooks = ExecutorHooks(job_id, monitor, recorder, failures)
    previous_handler = None
    in_main_thread = threading.current_thread() is threading.main_thread()
    if in_main_thread:
        previous_handler = signal.signal(SHUTDOWN_SIGNAL, lambda signum, frame: monitor.request_shutdown())
    monitor.start()

    outcome: RunOutcome | None = None
    error: BaseException | None = None
    try:
        compute = get_compute_function(request.kind)
        outcome = compute(request, read_manifest(request.manifest_path), hooks)
        if not isinstance(outcome, RunOutcome):
            raise RunSetupError(f"compute function for {request.kind!r} returned {type(outcome).__name__}")
        if outcome.n_processed > request.n_inputs or outcome.n_succeeded < 0 or outcome.n_failed < 0:
            raise RunSetupError(
                f"compute function reported {outcome.n_processed} processed inputs of {request.n_inputs}"
            )
        recorder.report(succeeded=outcome.n_succeeded, failed=outcome.n_failed)
    except BaseException as exc:  # timeouts and interrupts must still finalize the run
        error = exc
        logger.exception("Run %s failed", job_id)
    finally:
        monitor.close()
        if in_main_thread and previous_handler is not None:
            signal.signal(SHUTDOWN_SIGNAL, previous_handler)
        swept = terminate_descendants()
        if swept:
            hooks.log(f"terminated {swept} leftover compute process(es)")
        try:
            failure_report = failures.close()
        except Exception as close_error:
            failure_report = None
            if error is None:
                error = close_error
        processed = (recorder.succeeded, recorder.failed)
        decision = _decide(request, outcome, error, monitor.stop_reason, policy, processed)
        finished_at = datetime.now()
        try:
            _write_run_summary(
                request,
                decision,
                outcome,
                started_at=started_at,
                finished_at=finished_at,
                processed=processed,
                failure_report=failure_report,
                policy=policy,
                hook_messages=hooks.messages,
            )
        except Exception as summary_error:
            if decision.status == JobStatus.FINISHED:
                decision = _Decision(JobStatus.FAILED, f"Run summary could not be written: {summary_error}")
            else:
                hooks.log(f"run summary could not be written: {summary_error}")
        _finalize(engine, job_id, decision, processed, failure_report, finished_at, outcome)
        logger.info("Run %s finished in %.1f s: %s", job_id, time.monotonic() - started_clock, decision.message)
    if error is not None:
        raise error
    return {
        "job_id": job_id,
        "status": execution.STATUS_NAMES[decision.status],
        "message": decision.message,
        "n_succeeded": processed[0],
        "n_failed": processed[1],
    }


def _finalize(
    engine: Engine,
    job_id: int,
    decision: _Decision,
    processed: tuple[int, int],
    failure_report: str | None,
    finished_at: datetime,
    outcome: RunOutcome | None,
) -> None:
    with Session(engine) as session, session.begin():
        job = session.get(db_schema.Job, job_id)
        if job is None or execution.is_terminal(job):
            return
        if outcome is not None and job.indexing_run is not None:
            if outcome.n_indexed is not None:
                job.indexing_run.n_frames_indexed = int(outcome.n_indexed)
            # Artifacts hold only published, validated paths, so the pointer is set after publication.
            if outcome.artifacts.get("results"):
                job.indexing_run.results_path = outcome.artifacts["results"]
        if job.phase == RunPhase.RUNNING:
            execution.mark_finalizing(job, now=finished_at)
        execution.record_progress(job, succeeded=processed[0], failed=processed[1], now=finished_at)
        execution.finalize(
            job,
            status=decision.status,
            message=decision.message,
            failure_report_path=failure_report,
            phase=decision.phase,
            now=finished_at,
        )
