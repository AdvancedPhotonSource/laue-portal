"""RQ enqueue APIs for persisted reconstruction and indexing workflows."""

import logging
import os
import shutil
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

import laue_portal.database.session_utils as session_utils
from laue_portal.database import db_schema
from laue_portal.processing.queue.batch import clear_batch_counter, setup_batch_counter
from laue_portal.processing.queue.core import (
    PEAKINDEXING_QUEUE_BATCH_SIZE,
    STATUS_REVERSE_MAPPING,
    _chunked,
    job_queue,
)
from laue_portal.processing.queue.executors import execute_indexing_chunk, execute_reconstruction_subjob
from laue_portal.processing.queue.lifecycle import publish_job_update

logger = logging.getLogger(__name__)


def enqueue_job(
    job_id: int,
    job_type: str,
    execute_func,
    at_front: bool = False,
    depends_on=None,
    table=db_schema.Job,
    *args,
    **kwargs,
) -> str:
    """Enqueue one RQ task and attach its database identity as metadata."""
    timeout = kwargs.pop("timeout", 7200)
    rq_job_id = kwargs.pop("rq_job_id", None)
    job_meta = {
        "db_job_id": job_id,
        "job_type": job_type,
        "table": table.__tablename__,
        "enqueued_at": datetime.now().isoformat(),
    }

    rq_job = job_queue.enqueue(
        execute_func,
        job_id,
        *args,
        **kwargs,
        job_id=rq_job_id or f"{job_type}_{job_id}",
        meta=job_meta,
        at_front=at_front,
        depends_on=depends_on,
        job_timeout=timeout,
        result_ttl=86400,
        failure_ttl=86400,
    )
    logger.info("Enqueued %s job %s with RQ ID %s", job_type, job_id, rq_job.id)
    return rq_job.id


def _load_reconstruction(reconstruction_id: int):
    statement = (
        select(db_schema.ReconstructionRun)
        .where(db_schema.ReconstructionRun.id == reconstruction_id)
        .options(
            joinedload(db_schema.ReconstructionRun.job),
            joinedload(db_schema.ReconstructionRun.wire_parameters),
        )
    )
    with Session(session_utils.get_engine()) as session:
        run = session.scalars(statement).one_or_none()
        if run is None:
            raise ValueError(f"Reconstruction R{reconstruction_id} does not exist")
        subjob_ids = tuple(
            session.scalars(
                select(db_schema.SubJob.subjob_id)
                .where(db_schema.SubJob.job_id == run.job_id)
                .order_by(db_schema.SubJob.subjob_id)
            )
        )
    return run, subjob_ids


def _load_indexing(indexing_id: int):
    statement = (
        select(db_schema.IndexingRun)
        .where(db_schema.IndexingRun.id == indexing_id)
        .options(
            joinedload(db_schema.IndexingRun.job),
            joinedload(db_schema.IndexingRun.lauego_parameters),
        )
    )
    with Session(session_utils.get_engine()) as session:
        run = session.scalars(statement).one_or_none()
        if run is None:
            raise ValueError(f"Indexing I{indexing_id} does not exist")
        subjob_ids = tuple(
            session.scalars(
                select(db_schema.SubJob.subjob_id)
                .where(db_schema.SubJob.job_id == run.job_id)
                .order_by(db_schema.SubJob.subjob_id)
            )
        )
    return run, subjob_ids


def _validate_queued_run(run, subjob_ids: tuple[int, ...], display_id: str) -> None:
    if run.job.status != STATUS_REVERSE_MAPPING["Queued"]:
        raise ValueError(f"{display_id} is not queued")
    if run.output_path is None:
        raise ValueError(f"{display_id} has no output path")
    if not subjob_ids:
        raise ValueError(f"{display_id} has no subjobs")


def _mark_enqueue_failed(job_id: int, error: Exception) -> None:
    message = f"Enqueue failed: {error}"
    with Session(session_utils.get_engine()) as session:
        job = session.get(db_schema.Job, job_id)
        if job is None:
            return
        job.status = STATUS_REVERSE_MAPPING["Failed"]
        job.finish_time = datetime.now()
        job.messages = f"{job.messages}\n{message}" if job.messages else message
        session.commit()
    publish_job_update(job_id, "failed", message)


def _clear_batch_counter_best_effort(job_id: int) -> None:
    try:
        clear_batch_counter(job_id)
    except Exception as error:
        logger.warning("Could not clear Redis batch state for failed job %s: %s", job_id, error)


def _prepare_indexing_output(run: db_schema.IndexingRun) -> None:
    parameters = run.lauego_parameters
    if parameters is None:
        return

    os.makedirs(run.output_path, exist_ok=True)
    params_dir = os.path.join(run.output_path, "params")
    os.makedirs(params_dir, exist_ok=True)
    shutil.copy2(parameters.geometry_file, params_dir)
    shutil.copy2(parameters.crystal_file, params_dir)


def enqueue_reconstruction(
    reconstruction_id: int,
    *,
    at_front: bool = False,
    timeout: int = 7200,
) -> str:
    """Enqueue a persisted reconstruction by its ``R{id}`` database ID."""
    run, subjob_ids = _load_reconstruction(int(reconstruction_id))
    _validate_queued_run(run, subjob_ids, f"Reconstruction R{run.id}")

    try:
        os.makedirs(run.output_path, exist_ok=True)
        setup_batch_counter(run.job_id, len(subjob_ids), "execute_batch_coordinator", job_type="wire_reconstruction")
        for subjob_id in subjob_ids:
            enqueue_job(
                run.job_id,
                "wire_reconstruction",
                execute_reconstruction_subjob,
                at_front,
                None,
                db_schema.Job,
                subjob_id,
                rq_job_id=f"wire_reconstruction_{subjob_id}",
                timeout=timeout,
            )
    except Exception as error:
        _clear_batch_counter_best_effort(run.job_id)
        _mark_enqueue_failed(run.job_id, error)
        raise

    logger.info("Enqueued reconstruction R%s as %s subjobs", run.id, len(subjob_ids))
    return f"batch_{run.job_id}"


def enqueue_indexing(
    indexing_id: int,
    *,
    at_front: bool = False,
    queue_batch_size: int = PEAKINDEXING_QUEUE_BATCH_SIZE,
    timeout: int = 7200,
) -> str:
    """Enqueue a persisted indexing run by its ``I{id}`` database ID."""
    run, subjob_ids = _load_indexing(int(indexing_id))
    _validate_queued_run(run, subjob_ids, f"Indexing I{run.id}")
    chunk_size = max(1, int(queue_batch_size))
    chunks = list(_chunked(list(subjob_ids), chunk_size))
    rq_job_ids = [f"peakindexing_batch_{run.job_id}_{index}" for index in range(len(chunks))]

    try:
        _prepare_indexing_output(run)
        setup_batch_counter(
            run.job_id,
            len(subjob_ids),
            "execute_peakindexing_batch_coordinator",
            job_type="peakindexing",
            queue_mode="chunked",
            rq_job_ids=rq_job_ids,
            chunk_subjob_ids=chunks,
            chunk_size=chunk_size,
        )
        for chunk_index, subjob_id_chunk in enumerate(chunks):
            enqueue_job(
                run.job_id,
                "peakindexing_batch",
                execute_indexing_chunk,
                at_front,
                None,
                db_schema.Job,
                subjob_id_chunk,
                rq_job_id=rq_job_ids[chunk_index],
                timeout=timeout,
            )
    except Exception as error:
        _clear_batch_counter_best_effort(run.job_id)
        _mark_enqueue_failed(run.job_id, error)
        raise

    logger.info(
        "Enqueued indexing I%s as %s subjobs in %s chunks",
        run.id,
        len(subjob_ids),
        len(chunks),
    )
    return f"batch_{run.job_id}"
