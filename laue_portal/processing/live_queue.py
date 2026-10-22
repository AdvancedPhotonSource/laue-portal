"""Queue one controller alongside ordinary local runs; resume is explicit."""

import uuid

from sqlalchemy.orm import Session

from laue_portal.database import db_schema as db
from laue_portal.database import session_utils
from laue_portal.processing.queue.core import RUN_POLICY, job_queue
from laue_portal.workflows import execution
from laue_portal.workflows.live import get_live, writer_lock


def enqueue_live(session_id, *, resume=False, engine=None):
    from laue_portal.processing.live import execute_live

    engine = engine or session_utils.get_engine()
    live = get_live(session_id, engine=engine)
    if live is None:
        raise ValueError("Live session does not exist")
    with writer_lock(live.control_directory):
        with Session(engine) as session, session.begin():
            row = session.get(db.LiveSession, session_id)
            if resume:
                if row.state != "recovery":
                    raise ValueError("Only an interrupted live session can be resumed")
                row.state, row.error = "queued", None
            elif row.state != "queued":
                raise ValueError("Live session is already queued or running")
            job_id = f"live_{session_id}_{uuid.uuid4().hex}"
            for identity in (row.reconstruction_job_id, row.indexing_job_id):
                if identity:
                    job = session.get(db.Job, identity)
                    if not resume and job.queue_job_id != f"live_{session_id}":
                        raise ValueError("Live session was already submitted")
                    job.queue_job_id = job_id
                    job.status, job.phase = int(execution.JobStatus.QUEUED), execution.RunPhase.QUEUED
                    job.n_not_run, job.finish_time, job.cancel_requested_at = 0, None, None
    try:
        job_queue.enqueue(
            execute_live,
            session_id,
            job_id=job_id,
            job_timeout=RUN_POLICY.job_timeout_seconds,
            result_ttl=86400,
            failure_ttl=86400,
            meta={"job_type": "live", "db_job_id": live.reconstruction_job_id or live.indexing_job_id},
        )
    except Exception as error:
        with Session(engine) as session, session.begin():
            session.get(db.LiveSession, session_id).state = "recovery"
            session.get(db.LiveSession, session_id).error = f"Queue submission failed: {error}"
        raise
    return job_id


def reconcile_live(engine, *, queue_entry_exists=None):
    """A released writer lock is required before recording a lost controller."""
    from sqlalchemy import select

    with Session(engine) as session:
        candidates = session.scalars(
            select(db.LiveSession).where(
                db.LiveSession.active_slot == 1,
                db.LiveSession.state.in_(("queued", "running", "waiting", "finishing", "stopping")),
            )
        ).all()
    for live in candidates:
        if live.state == "queued":
            with Session(engine) as session:
                job = session.get(db.Job, live.reconstruction_job_id or live.indexing_job_id)
                if queue_entry_exists is None or queue_entry_exists(job.queue_job_id):
                    continue
        try:
            with writer_lock(live.control_directory):
                with Session(engine) as session, session.begin():
                    row = session.get(db.LiveSession, live.id)
                    row.state, row.error = "recovery", "Controller stopped; resume after reconciling outstanding work"
        except ValueError:
            pass  # A living controller still owns the session.
