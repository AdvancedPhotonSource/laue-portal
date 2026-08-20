"""RQ workers that load persisted workflows and dispatch by method."""

import logging
from datetime import datetime

from laueanalysis.indexing import index
from laueanalysis.reconstruct import reconstruct as wire_reconstruct
from sqlalchemy import select
from sqlalchemy.orm import Session

import laue_portal.database.session_utils as session_utils
from laue_portal.database import db_schema
from laue_portal.processing.queue.batch import notify_subjobs_completed
from laue_portal.processing.queue.core import STATUS_REVERSE_MAPPING, WRITE_SUCCESS_SUBJOB_DETAILS
from laue_portal.processing.queue.lifecycle import execute_with_status_updates, publish_job_update

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {
    STATUS_REVERSE_MAPPING["Finished"],
    STATUS_REVERSE_MAPPING["Failed"],
    STATUS_REVERSE_MAPPING["Cancelled"],
}


def _load_reconstruction_subjob(job_id: int, subjob_id: int):
    statement = (
        select(
            db_schema.Job,
            db_schema.ReconstructionRun,
            db_schema.WireReconstructionParameters,
            db_schema.SubJob,
        )
        .select_from(db_schema.Job)
        .join(db_schema.SubJob, db_schema.SubJob.job_id == db_schema.Job.job_id)
        .outerjoin(db_schema.ReconstructionRun, db_schema.ReconstructionRun.job_id == db_schema.Job.job_id)
        .outerjoin(
            db_schema.WireReconstructionParameters,
            db_schema.WireReconstructionParameters.reconstruction_id == db_schema.ReconstructionRun.id,
        )
        .where(db_schema.Job.job_id == job_id, db_schema.SubJob.subjob_id == subjob_id)
    )
    with Session(session_utils.get_engine()) as session:
        row = session.execute(statement).one_or_none()
    if row is None:
        raise ValueError(f"Subjob {subjob_id} does not belong to job {job_id}")
    return row


def _run_reconstruction_method(run, parameters, subjob):
    if run is None:
        raise ValueError(f"Job {subjob.job_id} is not attached to a reconstruction run")
    if run.method == "ca":
        raise NotImplementedError("CA reconstruction is not available")
    if run.method != "wire":
        raise ValueError(f"Unknown reconstruction method: {run.method}")
    if parameters is None:
        raise ValueError(f"Wire reconstruction R{run.id} has no parameters")
    if subjob.input_path is None or subjob.output_path is None:
        raise ValueError(f"Reconstruction subjob {subjob.subjob_id} has no persisted input/output paths")

    return wire_reconstruct(
        subjob.input_path,
        subjob.output_path,
        parameters.geometry_file,
        (parameters.depth_start, parameters.depth_end),
        parameters.depth_resolution,
        percent_brightest=parameters.percent_brightest,
        wire_edge=parameters.wire_edges,
        memory_limit_mb=parameters.memory_limit_mb,
        num_threads=parameters.num_threads,
        verbose=parameters.verbose,
        detector_number=0,
    )


def execute_reconstruction_subjob(job_id: int, subjob_id: int):
    """Load and execute one persisted reconstruction subjob."""
    try:
        job, run, parameters, subjob = _load_reconstruction_subjob(job_id, subjob_id)
    except Exception as load_error:

        def raise_load_error(error=load_error):
            raise error

        return execute_with_status_updates(
            subjob_id,
            "Reconstruction",
            raise_load_error,
            db_schema.SubJob,
        )

    if job.status in TERMINAL_STATUSES:
        logger.info("Skipping reconstruction subjob %s for terminal job %s", subjob_id, job_id)
        return None

    return execute_with_status_updates(
        subjob_id,
        "Wire reconstruction" if run and run.method == "wire" else "Reconstruction",
        lambda: _run_reconstruction_method(run, parameters, subjob),
        db_schema.SubJob,
    )


def _load_indexing_chunk(job_id: int, subjob_ids: tuple[int, ...]):
    statement = (
        select(
            db_schema.Job,
            db_schema.IndexingRun,
            db_schema.LaueGoIndexingParameters,
            db_schema.SubJob,
        )
        .select_from(db_schema.Job)
        .join(db_schema.SubJob, db_schema.SubJob.job_id == db_schema.Job.job_id)
        .outerjoin(db_schema.IndexingRun, db_schema.IndexingRun.job_id == db_schema.Job.job_id)
        .outerjoin(
            db_schema.LaueGoIndexingParameters,
            db_schema.LaueGoIndexingParameters.indexing_id == db_schema.IndexingRun.id,
        )
        .where(db_schema.Job.job_id == job_id, db_schema.SubJob.subjob_id.in_(subjob_ids))
    )
    with Session(session_utils.get_engine()) as session:
        rows = session.execute(statement).all()

    rows_by_subjob_id = {row[3].subjob_id: row for row in rows}
    missing = [subjob_id for subjob_id in subjob_ids if subjob_id not in rows_by_subjob_id]
    if missing:
        raise ValueError(f"Subjobs {missing} do not belong to job {job_id}")
    return [rows_by_subjob_id[subjob_id] for subjob_id in subjob_ids]


def _indexing_arguments(parameters) -> dict:
    return {
        "geo_file": parameters.geometry_file,
        "crystal_file": parameters.crystal_file,
        "boxsize": parameters.box_size,
        "max_rfactor": parameters.max_rfactor,
        "min_size": parameters.min_size,
        "min_separation": parameters.min_separation,
        "threshold": parameters.threshold,
        "peak_shape": parameters.peak_shape,
        "max_peaks": parameters.max_peaks,
        "smooth": parameters.smooth,
        "index_kev_max_calc": parameters.index_kev_max_calc,
        "index_kev_max_test": parameters.index_kev_max_test,
        "index_angle_tolerance": parameters.index_angle_tolerance,
        "index_cone": parameters.index_cone,
        "index_h": parameters.index_h,
        "index_k": parameters.index_k,
        "index_l": parameters.index_l,
        "mask_file": parameters.mask_file,
    }


def _failed_subjob_update(subjob_id: int, started_at: datetime, error: Exception) -> dict:
    return {
        "subjob_id": subjob_id,
        "status": STATUS_REVERSE_MAPPING["Failed"],
        "start_time": started_at,
        "finish_time": datetime.now(),
        "messages": f"Error: {error}",
    }


def execute_indexing_chunk(job_id: int, subjob_ids: list[int]):
    """Load and execute a chunk of persisted indexing subjobs."""
    if not subjob_ids:
        return []
    normalized_ids = tuple(int(subjob_id) for subjob_id in subjob_ids)
    if len(set(normalized_ids)) != len(normalized_ids):
        raise ValueError("An indexing chunk cannot contain duplicate subjob IDs")

    rows = _load_indexing_chunk(job_id, normalized_ids)
    job, run, parameters, _ = rows[0]
    if job.status in TERMINAL_STATUSES:
        logger.info("Skipping indexing chunk for terminal job %s", job_id)
        notify_subjobs_completed(job_id, len(normalized_ids))
        return []

    chunk_start_time = datetime.now()
    with Session(session_utils.get_engine()) as session:
        job_data = session.get(db_schema.Job, job_id)
        if job_data and job_data.status == STATUS_REVERSE_MAPPING["Queued"]:
            job_data.status = STATUS_REVERSE_MAPPING["Running"]
            job_data.start_time = chunk_start_time
            session.commit()

    dispatch_error = None
    if run is None:
        dispatch_error = ValueError(f"Job {job_id} is not attached to an indexing run")
    elif run.method == "laue_matching":
        dispatch_error = NotImplementedError("Laue-matching indexing is not available")
    elif run.method != "lauego":
        dispatch_error = ValueError(f"Unknown indexing method: {run.method}")
    elif parameters is None:
        dispatch_error = ValueError(f"LaueGo indexing I{run.id} has no parameters")

    results = []
    if dispatch_error is not None:
        results = [_failed_subjob_update(subjob_id, chunk_start_time, dispatch_error) for subjob_id in normalized_ids]
    else:
        indexing_arguments = _indexing_arguments(parameters)
        for _, _, _, subjob in rows:
            try:
                if subjob.input_path is None or subjob.output_path is None:
                    raise ValueError(f"Indexing subjob {subjob.subjob_id} has no persisted input/output paths")
                index_result = index(
                    input_image=subjob.input_path,
                    output_dir=subjob.output_path,
                    **indexing_arguments,
                )
                update = {
                    "subjob_id": subjob.subjob_id,
                    "status": STATUS_REVERSE_MAPPING["Finished"],
                    "start_time": chunk_start_time,
                    "finish_time": datetime.now(),
                }
                if WRITE_SUCCESS_SUBJOB_DETAILS:
                    if hasattr(index_result, "command_history") and index_result.command_history:
                        update["command"] = "\n".join(index_result.command_history)
                    update["messages"] = str(index_result)
                results.append(update)
            except Exception as error:
                logger.exception("Indexing subjob %s failed inside chunk for job %s", subjob.subjob_id, job_id)
                results.append(_failed_subjob_update(subjob.subjob_id, chunk_start_time, error))

    with Session(session_utils.get_engine()) as session:
        session.bulk_update_mappings(db_schema.SubJob, results)
        session.commit()

    notify_subjobs_completed(job_id, len(results))
    publish_job_update(job_id, "running", f"Indexing chunk completed {len(results)} subjob(s)")
    return results
