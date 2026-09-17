"""Run-level queue controls: cancellation and reprioritization."""

from __future__ import annotations

import logging
from typing import Any

from rq.job import Job as RQJob
from sqlalchemy import Engine
from sqlalchemy.orm import Session

import laue_portal.database.session_utils as session_utils
from laue_portal.database import db_schema
from laue_portal.processing.queue.core import STATUS_MAPPING, job_queue, redis_conn
from laue_portal.workflows import execution
from laue_portal.workflows.execution import JobStatus, RunPhase

logger = logging.getLogger(__name__)


def _fetch_queue_entry(queue_job_id: str | None):
    if not queue_job_id:
        return None
    try:
        return RQJob.fetch(queue_job_id, connection=redis_conn)
    except Exception as error:
        logger.warning("Could not fetch queue entry %s: %s", queue_job_id, error)
        return None


def cancel_run(job_id: int, *, engine: Engine | None = None) -> dict[str, Any]:
    """Cancel a run.

    A run that has not started is removed from the queue and finalized as
    Cancelled at once. A running run gets a persisted cancellation request; its
    executor stops admitting inputs, drains work in flight, keeps completed
    results, and finalizes as Cancelled itself.

    Returns ``state`` in {"cancelled", "requested", "already_done", "not_found",
    "error"}, ``message``, and ``n_pending``: the inputs that had not been
    processed when the request was made.
    """

    engine = engine or session_utils.get_engine()
    result: dict[str, Any] = {"success": False, "state": "error", "message": "", "n_pending": 0}
    try:
        with Session(engine) as session, session.begin():
            job = session.get(db_schema.Job, job_id)
            if job is None:
                result.update(state="not_found", message=f"Job {job_id} not found")
                return result
            if execution.is_terminal(job):
                result.update(
                    state="already_done",
                    message=f"Job {job_id} is already {STATUS_MAPPING.get(job.status, job.status)}",
                )
                return result
            execution.request_cancellation(job, reason="user")
            queue_job_id = job.queue_job_id
            if job.status == JobStatus.QUEUED:
                entry = _fetch_queue_entry(queue_job_id)
                if entry is not None:
                    try:
                        entry.cancel()
                    except Exception as error:
                        logger.warning("Could not cancel queue entry %s: %s", queue_job_id, error)
                execution.finalize(job, status=JobStatus.CANCELLED, message="Cancelled before the run started")
                result.update(
                    success=True,
                    state="cancelled",
                    n_pending=job.n_inputs,
                    message=f"Job {job_id} removed from the queue before it started; {job.n_inputs} input(s) not run.",
                )
                return result
            pending = job.n_inputs - job.n_succeeded - job.n_failed
            result.update(
                success=True,
                state="requested",
                n_pending=pending,
                message=(
                    f"Job {job_id}: stop requested. The run stops admitting inputs, finishes work in flight, "
                    f"and keeps completed results ({pending} input(s) pending)."
                ),
            )
            return result
    except Exception as error:
        logger.exception("Error cancelling job %s", job_id)
        result.update(message=f"Error: {error}")
        return result


def move_run_to_front(job_id: int, *, engine: Engine | None = None) -> dict[str, Any]:
    """Move a queued run ahead of other queued runs. Active work is never preempted."""

    engine = engine or session_utils.get_engine()
    result: dict[str, Any] = {"success": False, "message": ""}
    try:
        with Session(engine) as session:
            job = session.get(db_schema.Job, job_id)
            if job is None:
                result["message"] = f"Job {job_id} not found"
                return result
            if job.status != JobStatus.QUEUED or job.phase != RunPhase.QUEUED:
                result["message"] = (
                    f"Job {job_id} is {STATUS_MAPPING.get(job.status, job.status)} ({job.phase}); nothing to move"
                )
                return result
            queue_job_id = job.queue_job_id
        entry = _fetch_queue_entry(queue_job_id)
        if entry is None or not entry.is_queued:
            result["message"] = f"Job {job_id} has no queued entry to move"
            return result
        job_queue.remove(queue_job_id)
        job_queue.push_job_id(queue_job_id, at_front=True)
        result.update(success=True, message=f"Moved job {job_id} ahead of the other queued runs")
        return result
    except Exception as error:
        logger.exception("Error moving job %s to front", job_id)
        result["message"] = f"Error: {error}"
        return result
