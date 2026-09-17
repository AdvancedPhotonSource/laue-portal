"""Enqueue one deterministic RQ task per persisted run."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

import laue_portal.database.session_utils as session_utils
from laue_portal.database import db_schema
from laue_portal.processing.queue.core import RUN_JOB_TYPE, RUN_POLICY, job_queue, run_queue_id
from laue_portal.processing.queue.executors import execute_run
from laue_portal.workflows import execution
from laue_portal.workflows.manifest import verify_manifest

logger = logging.getLogger(__name__)


def enqueue_run(job_id: int, *, at_front: bool = False, engine: Engine | None = None) -> str:
    """Hand a published run to the queue exactly once.

    The job moves to phase ``queued`` inside a transaction before RQ is touched,
    so a second call raises instead of producing a duplicate. The RQ job
    identity is ``run_<job_id>``. An RQ failure records the run as Failed.
    """

    engine = engine or session_utils.get_engine()
    queue_id = run_queue_id(job_id)
    with Session(engine) as session, session.begin():
        job = session.get(db_schema.Job, job_id)
        if job is None:
            raise ValueError(f"Job {job_id} does not exist")
        execution.assert_enqueueable(job)
        verify_manifest(job.manifest_path, expected_digest=job.manifest_digest or "", expected_count=job.n_inputs)
        execution.mark_queued(job, queue_id)
        priority = job.priority

    try:
        job_queue.enqueue(
            execute_run,
            job_id,
            job_id=queue_id,
            meta={
                "db_job_id": job_id,
                "job_type": RUN_JOB_TYPE,
                "priority": priority,
                "enqueued_at": datetime.now().isoformat(timespec="seconds"),
            },
            at_front=at_front,
            job_timeout=RUN_POLICY.job_timeout_seconds,
            result_ttl=86400,
            failure_ttl=86400,
        )
    except Exception as error:
        execution.record_enqueue_failure(job_id, error, engine=engine)
        raise
    logger.info("Enqueued run %s as %s", job_id, queue_id)
    return queue_id


def _job_id_for(engine: Engine, model, run_id: int, label: str) -> int:
    with Session(engine) as session:
        job_id = session.scalar(select(model.job_id).where(model.id == run_id))
    if job_id is None:
        raise ValueError(f"{label}{run_id} does not exist")
    return job_id


def enqueue_indexing(indexing_id: int, *, at_front: bool = False, engine: Engine | None = None) -> str:
    """Enqueue a persisted indexing run by its ``I{id}`` database ID."""

    engine = engine or session_utils.get_engine()
    return enqueue_run(
        _job_id_for(engine, db_schema.IndexingRun, int(indexing_id), "Indexing I"), at_front=at_front, engine=engine
    )


def enqueue_reconstruction(reconstruction_id: int, *, at_front: bool = False, engine: Engine | None = None) -> str:
    """Enqueue a persisted reconstruction by its ``R{id}`` database ID."""

    engine = engine or session_utils.get_engine()
    return enqueue_run(
        _job_id_for(engine, db_schema.ReconstructionRun, int(reconstruction_id), "Reconstruction R"),
        at_front=at_front,
        engine=engine,
    )
