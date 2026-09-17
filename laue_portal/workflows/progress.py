"""Run progress and report queries backed by stored counters, never per-input rows."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from laue_portal.database import db_schema
from laue_portal.workflows.execution import STATUS_NAMES, TERMINAL_STATUSES, JobStatus
from laue_portal.workflows.manifest import FailureRecord, read_failure_report


@dataclass(frozen=True)
class RunProgress:
    """Counters and execution state of one job."""

    job_id: int
    status: int
    phase: str | None
    n_inputs: int
    n_succeeded: int
    n_failed: int
    n_not_run: int
    updated_at: datetime | None = None
    heartbeat_at: datetime | None = None
    cancel_requested_at: datetime | None = None
    queue_job_id: str | None = None
    failure_report_path: str | None = None
    messages: str | None = None

    @property
    def n_processed(self) -> int:
        """Inputs whose processing finished, with or without error."""

        return self.n_succeeded + self.n_failed

    @property
    def n_pending(self) -> int:
        return max(self.n_inputs - self.n_processed - self.n_not_run, 0)

    @property
    def fraction(self) -> float | None:
        return None if self.n_inputs == 0 else self.n_processed / self.n_inputs

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES

    @property
    def status_name(self) -> str:
        try:
            return STATUS_NAMES[JobStatus(self.status)]
        except ValueError:
            return f"Unknown ({self.status})"

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_STATUSES

    @property
    def terminal_message(self) -> str | None:
        if not self.messages:
            return None
        return self.messages.strip().splitlines()[-1]

    def progress_text(self) -> str | None:
        """``processed/total`` for a run in flight, or None when nothing was selected."""

        return None if self.n_inputs == 0 else f"{self.n_processed}/{self.n_inputs}"

    def counter_summary(self) -> str:
        """One line naming every counter, in the words the pages use."""

        parts = [f"{self.n_inputs} input(s)", f"{self.n_succeeded} succeeded", f"{self.n_failed} failed"]
        if self.n_not_run:
            parts.append(f"{self.n_not_run} not run")
        if self.n_pending and not self.is_terminal:
            parts.append(f"{self.n_pending} pending")
        return ", ".join(parts)

    @classmethod
    def from_job(cls, job: db_schema.Job) -> RunProgress:
        return cls(
            job_id=job.job_id,
            status=job.status,
            phase=job.phase,
            n_inputs=job.n_inputs,
            n_succeeded=job.n_succeeded,
            n_failed=job.n_failed,
            n_not_run=job.n_not_run,
            updated_at=job.updated_at,
            heartbeat_at=job.heartbeat_at,
            cancel_requested_at=job.cancel_requested_at,
            queue_job_id=job.queue_job_id,
            failure_report_path=job.failure_report_path,
            messages=job.messages,
        )


def load_progress(session: Session, job_id: int) -> RunProgress | None:
    job = session.get(db_schema.Job, job_id)
    return None if job is None else RunProgress.from_job(job)


def load_progress_many(session: Session, job_ids: Iterable[int]) -> dict[int, RunProgress]:
    ids = list(job_ids)
    if not ids:
        return {}
    jobs = session.scalars(select(db_schema.Job).where(db_schema.Job.job_id.in_(ids)))
    return {job.job_id: RunProgress.from_job(job) for job in jobs}


ACTIVE_STATUSES = (int(JobStatus.QUEUED), int(JobStatus.RUNNING))


def derived_progress_columns():
    """Processed and pending counts derived in SQL, for queries that already select the whole Job."""

    processed = db_schema.Job.n_succeeded + db_schema.Job.n_failed
    return [
        processed.label("n_processed"),
        (db_schema.Job.n_inputs - processed - db_schema.Job.n_not_run).label("n_pending"),
    ]


def progress_columns():
    """Counter and liveness columns for table queries, plus the derived processed and pending counts."""

    return [
        db_schema.Job.phase.label("phase"),
        db_schema.Job.n_inputs.label("n_inputs"),
        db_schema.Job.n_succeeded.label("n_succeeded"),
        db_schema.Job.n_failed.label("n_failed"),
        db_schema.Job.n_not_run.label("n_not_run"),
        *derived_progress_columns(),
        db_schema.Job.heartbeat_at.label("heartbeat_at"),
        db_schema.Job.cancel_requested_at.label("cancel_requested_at"),
    ]


def active_or_changed_since(since: datetime | None):
    """Filter for jobs a live table must refresh: active runs plus anything finalized since ``since``.

    Terminal jobs never change again, so once a poll has seen a run finish it
    drops out of the next poll. Rows migrated from history have no ``updated_at``
    and are never active, so they are never re-sent.
    """

    active = db_schema.Job.status.in_(ACTIVE_STATUSES)
    if since is None:
        return active
    return or_(active, db_schema.Job.updated_at >= since)


def heartbeat_age_seconds(progress: RunProgress, *, now: datetime | None = None) -> float | None:
    """Seconds since the run's last sign of life, or None for a run that never started."""

    last_sign = progress.heartbeat_at
    if last_sign is None:
        return None
    return max(((now or datetime.now()) - last_sign).total_seconds(), 0.0)


def failure_page(progress: RunProgress, *, offset: int = 0, limit: int = 100) -> tuple[list[FailureRecord], bool]:
    """One bounded page of the run's failure report; empty when no report exists."""

    if not progress.failure_report_path:
        return [], False
    try:
        return read_failure_report(progress.failure_report_path, offset=offset, limit=limit)
    except FileNotFoundError:
        return [], False
