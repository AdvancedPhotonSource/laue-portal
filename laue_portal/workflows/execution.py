"""Run-level execution state: statuses, phases, counters, and transitions.

The database ``job`` row is the authority for a run's lifecycle. Every state
change goes through one of the functions below so the counters stay
consistent: processed work is ``n_succeeded + n_failed``; ``n_not_run`` is
fixed at finalization so the three sum to ``n_inputs`` for any terminal run.
Nothing here touches Redis or the queue; the queue adapter (P2) calls these
helpers inside its own sessions.
"""

from __future__ import annotations

from datetime import datetime
from enum import IntEnum, StrEnum

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from laue_portal.database import db_schema, session_utils


class JobStatus(IntEnum):
    """Job.status values; names match the queue's STATUS_MAPPING."""

    QUEUED = 0
    RUNNING = 1
    FINISHED = 2
    FAILED = 3
    CANCELLED = 4


STATUS_NAMES = {status: status.name.capitalize() for status in JobStatus}
TERMINAL_STATUSES = frozenset({JobStatus.FINISHED, JobStatus.FAILED, JobStatus.CANCELLED})


class RunPhase(StrEnum):
    """Job.phase values, finer than status and never used for scheduling decisions alone."""

    CREATED = "created"  # database rows exist; manifest not published; never runnable
    PUBLISHED = "published"  # manifest and request are on disk; may be enqueued
    QUEUED = "queued"  # handed to the queue with a queue identity
    RUNNING = "running"
    FINALIZING = "finalizing"  # computation over; outputs being closed and validated
    FINISHED = "finished"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"  # was queued or running when the system stopped; not runnable


TERMINAL_PHASES = frozenset({RunPhase.FINISHED, RunPhase.FAILED, RunPhase.CANCELLED, RunPhase.INTERRUPTED})
_PHASE_FOR_STATUS = {
    JobStatus.FINISHED: RunPhase.FINISHED,
    JobStatus.FAILED: RunPhase.FAILED,
    JobStatus.CANCELLED: RunPhase.CANCELLED,
}


class ExecutionStateError(RuntimeError):
    """Raised when a transition is not valid from the job's current state."""


def _now(now: datetime | None) -> datetime:
    return now if now is not None else datetime.now()


def _append_message(job: db_schema.Job, message: str | None) -> None:
    if not message:
        return
    job.messages = f"{job.messages}\n{message}" if job.messages else message


def is_terminal(job: db_schema.Job) -> bool:
    return job.status in TERMINAL_STATUSES or job.phase in TERMINAL_PHASES


def initialize(job: db_schema.Job, *, n_inputs: int, now: datetime | None = None) -> None:
    """Set the state of a freshly created job before its manifest exists."""

    if n_inputs < 0:
        raise ExecutionStateError("n_inputs must not be negative")
    job.status = int(JobStatus.QUEUED)
    job.phase = RunPhase.CREATED
    job.n_inputs = int(n_inputs)
    job.n_succeeded = 0
    job.n_failed = 0
    job.n_not_run = 0
    job.updated_at = _now(now)


def mark_published(
    job: db_schema.Job,
    *,
    run_directory: str,
    manifest_path: str,
    manifest_digest: str,
    request_path: str,
    n_inputs: int,
    now: datetime | None = None,
) -> None:
    """Record that the immutable manifest and request are on disk."""

    if job.phase != RunPhase.CREATED or job.status != JobStatus.QUEUED:
        raise ExecutionStateError(f"job {job.job_id} cannot publish from phase {job.phase!r}, status {job.status}")
    if n_inputs != job.n_inputs:
        raise ExecutionStateError(
            f"job {job.job_id} manifest holds {n_inputs} inputs but the job expects {job.n_inputs}"
        )
    job.run_directory = run_directory
    job.manifest_path = manifest_path
    job.manifest_digest = manifest_digest
    job.request_path = request_path
    job.phase = RunPhase.PUBLISHED
    job.updated_at = _now(now)


def assert_enqueueable(job: db_schema.Job) -> None:
    """Refuse to enqueue anything but a published, queued, uncancelled run."""

    if job.phase != RunPhase.PUBLISHED:
        raise ExecutionStateError(f"job {job.job_id} is in phase {job.phase!r}; only published runs can be enqueued")
    if job.status != JobStatus.QUEUED:
        raise ExecutionStateError(f"job {job.job_id} has status {job.status}; only queued runs can be enqueued")
    if not job.manifest_path:
        raise ExecutionStateError(f"job {job.job_id} has no manifest")
    if job.cancel_requested_at is not None:
        raise ExecutionStateError(f"job {job.job_id} has a pending cancellation request")


def mark_queued(job: db_schema.Job, queue_job_id: str, *, now: datetime | None = None) -> None:
    assert_enqueueable(job)
    if not queue_job_id:
        raise ExecutionStateError("queue_job_id is required")
    job.queue_job_id = str(queue_job_id)
    job.phase = RunPhase.QUEUED
    job.updated_at = _now(now)


def mark_running(job: db_schema.Job, *, now: datetime | None = None) -> None:
    if job.phase != RunPhase.QUEUED or job.status != JobStatus.QUEUED:
        raise ExecutionStateError(f"job {job.job_id} cannot start from phase {job.phase!r}, status {job.status}")
    moment = _now(now)
    job.status = int(JobStatus.RUNNING)
    job.phase = RunPhase.RUNNING
    job.start_time = moment
    job.heartbeat_at = moment
    job.updated_at = moment


def heartbeat(job: db_schema.Job, *, now: datetime | None = None) -> None:
    if is_terminal(job):
        raise ExecutionStateError(f"job {job.job_id} is terminal")
    job.heartbeat_at = _now(now)


def record_progress(job: db_schema.Job, *, succeeded: int, failed: int, now: datetime | None = None) -> None:
    """Store absolute processed counts; counts never decrease or exceed n_inputs."""

    if job.phase not in (RunPhase.RUNNING, RunPhase.FINALIZING):
        raise ExecutionStateError(f"job {job.job_id} is not running (phase {job.phase!r})")
    succeeded = int(succeeded)
    failed = int(failed)
    if succeeded < 0 or failed < 0:
        raise ExecutionStateError("counts must not be negative")
    if succeeded < job.n_succeeded or failed < job.n_failed:
        raise ExecutionStateError(
            f"job {job.job_id} progress went backwards: {succeeded}/{failed} after {job.n_succeeded}/{job.n_failed}"
        )
    if succeeded + failed > job.n_inputs:
        raise ExecutionStateError(f"job {job.job_id} processed {succeeded + failed} of only {job.n_inputs} inputs")
    moment = _now(now)
    job.n_succeeded = succeeded
    job.n_failed = failed
    job.heartbeat_at = moment
    job.updated_at = moment


def mark_finalizing(job: db_schema.Job, *, now: datetime | None = None) -> None:
    if job.phase != RunPhase.RUNNING:
        raise ExecutionStateError(f"job {job.job_id} cannot finalize from phase {job.phase!r}")
    job.phase = RunPhase.FINALIZING
    job.updated_at = _now(now)


def request_cancellation(job: db_schema.Job, *, reason: str | None = None, now: datetime | None = None) -> bool:
    """Flag a cancellation request; returns False when the run is already terminal.

    Only the first request is recorded; the run's executor polls the flag and
    stops admitting inputs while completed work is kept.
    """

    if is_terminal(job):
        return False
    if job.cancel_requested_at is None:
        job.cancel_requested_at = _now(now)
        job.updated_at = job.cancel_requested_at
        _append_message(job, f"Cancellation requested: {reason}" if reason else "Cancellation requested")
    return True


def finalize(
    job: db_schema.Job,
    *,
    status: JobStatus,
    message: str | None = None,
    failure_report_path: str | None = None,
    phase: RunPhase | None = None,
    now: datetime | None = None,
) -> None:
    """Enter a terminal state and fix ``n_not_run`` so the counters sum to ``n_inputs``.

    ``phase`` may name ``RunPhase.INTERRUPTED`` for a Failed run that stopped
    because the service or worker went away rather than because the run itself failed.
    """

    status = JobStatus(status)
    if status not in TERMINAL_STATUSES:
        raise ExecutionStateError(f"{status.name} is not a terminal status")
    if phase is not None and (phase != RunPhase.INTERRUPTED or status != JobStatus.FAILED):
        raise ExecutionStateError("only a Failed run may be finalized with the interrupted phase")
    if is_terminal(job):
        raise ExecutionStateError(f"job {job.job_id} is already terminal ({job.phase!r})")
    processed = job.n_succeeded + job.n_failed
    if processed > job.n_inputs:
        raise ExecutionStateError(f"job {job.job_id} counters exceed n_inputs: {processed} > {job.n_inputs}")
    moment = _now(now)
    job.n_not_run = job.n_inputs - processed
    job.status = int(status)
    job.phase = phase or _PHASE_FOR_STATUS[status]
    job.finish_time = moment
    job.updated_at = moment
    if failure_report_path is not None:
        job.failure_report_path = failure_report_path
    _append_message(job, message)


def record_failure(job: db_schema.Job, message: str, *, now: datetime | None = None) -> None:
    """Fail a run from any non-terminal phase, including before it was runnable."""

    finalize(job, status=JobStatus.FAILED, message=message, now=now)


def record_enqueue_failure(job_id: int, error: BaseException | str, *, engine: Engine | None = None) -> bool:
    """Persist an enqueue failure so no silently runnable job is left behind."""

    database_engine = engine or session_utils.get_engine()
    with Session(database_engine) as session, session.begin():
        job = session.get(db_schema.Job, job_id)
        if job is None:
            return False
        if is_terminal(job):
            _append_message(job, f"Enqueue failed after the run was already terminal: {error}")
            return False
        record_failure(job, f"Enqueue failed: {error}")
    return True
