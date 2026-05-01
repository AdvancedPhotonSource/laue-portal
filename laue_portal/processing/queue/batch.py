"""Batch completion counters and coordinator jobs."""

import json
import logging
import os
from datetime import datetime

from sqlalchemy.orm import Session

import laue_portal.database.session_utils as session_utils
from laue_portal.database import db_schema
from laue_portal.processing.queue.core import STATUS_REVERSE_MAPPING, redis_conn
from laue_portal.processing.queue.lifecycle import publish_job_update
from laue_portal.processing.xml_merge import merge_xml_files

logger = logging.getLogger(__name__)


def execute_peakindexing_batch_coordinator(job_id: int, output_dir: str, output_xml: str):
    """
    Execute peakindexing batch coordinator logic.
    Updates the main job status based on subjob statuses and merges XML output files.

    Args:
        job_id: Database job ID
        output_dir: Output directory for the peakindexing job
        output_xml: Output XML filename or path
            - If absolute path: saves directly to that path
            - If relative path or filename: saves to output_dir
    """
    try:
        with Session(session_utils.get_engine()) as session:
            # Query for all subjobs of this job
            subjob_data = session.query(db_schema.SubJob).filter(db_schema.SubJob.job_id == job_id).all()

            if not subjob_data:
                logger.error(f"No subjobs found for job {job_id} in peakindexing batch coordinator")
                return

            # Count subjob statuses
            finished_count = sum(1 for s in subjob_data if s.status == STATUS_REVERSE_MAPPING["Finished"])
            failed_count = sum(1 for s in subjob_data if s.status == STATUS_REVERSE_MAPPING["Failed"])
            running_count = sum(1 for s in subjob_data if s.status == STATUS_REVERSE_MAPPING["Running"])
            queued_count = sum(1 for s in subjob_data if s.status == STATUS_REVERSE_MAPPING["Queued"])
            cancelled_count = sum(1 for s in subjob_data if s.status == STATUS_REVERSE_MAPPING["Cancelled"])

            all_finished = finished_count == len(subjob_data)
            any_failed = failed_count > 0
            all_complete = (finished_count + failed_count + cancelled_count) == len(subjob_data)

            # Merge XML files if we have any successful subjobs
            merge_message = ""
            if finished_count > 0:
                # Determine the output XML path
                # Individual XML files are written to output_dir/xml/
                xml_source_dir = os.path.join(output_dir, "xml")

                # Determine where to save the merged XML
                if os.path.isabs(output_xml):
                    # Absolute path - use directly
                    merged_xml_path = output_xml
                else:
                    # Relative path or filename - save to output_dir
                    merged_xml_path = os.path.join(output_dir, output_xml)

                # Perform the merge
                if os.path.exists(xml_source_dir):
                    merge_result = merge_xml_files(xml_source_dir, merged_xml_path)

                    if merge_result["success"]:
                        merge_message = f"\nMerged {merge_result['files_merged']} XML files into {merged_xml_path}"
                    else:
                        merge_message = f"\nXML merge failed: {merge_result['error']}"
                else:
                    merge_message = f"\nXML source directory not found: {xml_source_dir}"
                    logger.warning(merge_message)

            # Update job status
            job_data = session.query(db_schema.Job).filter(db_schema.Job.job_id == job_id).first()

            if job_data:
                # If the job was already cancelled by user, don't overwrite the status
                already_cancelled = job_data.status == STATUS_REVERSE_MAPPING["Cancelled"]

                if all_finished and not already_cancelled:
                    job_data.status = STATUS_REVERSE_MAPPING["Finished"]
                    message = f"All {len(subjob_data)} subjobs completed successfully{merge_message}"
                elif any_failed and all_complete and not already_cancelled:
                    job_data.status = STATUS_REVERSE_MAPPING["Failed"]
                    message = f"Batch failed: {failed_count} failed, {finished_count} succeeded out of {len(subjob_data)} subjobs{merge_message}"
                elif cancelled_count > 0 and all_complete:
                    # Keep Cancelled status (may already be set by cancel_batch_job)
                    job_data.status = STATUS_REVERSE_MAPPING["Cancelled"]
                    message = f"Batch final: {cancelled_count} cancelled, {finished_count} succeeded, {failed_count} failed{merge_message}"
                else:
                    if not already_cancelled:
                        job_data.status = STATUS_REVERSE_MAPPING["Failed"]
                    message = f"Batch coordinator: {finished_count} finished, {failed_count} failed, {running_count} running, {queued_count} queued{merge_message}"
                    logger.warning(f"Unexpected state in peakindexing batch coordinator for job {job_id}: {message}")

                if not already_cancelled:
                    job_data.finish_time = datetime.now()
                if job_data.messages:
                    job_data.messages += f"\n{message}"
                else:
                    job_data.messages = message

                session.commit()

                publish_job_update(job_id, "batch_completed", message)
                logger.info(f"Peakindexing batch job {job_id} completed: {message}")

    except Exception as e:
        logger.error(f"Error in peakindexing batch coordinator for job {job_id}: {e}")
        raise


def execute_batch_coordinator(job_id: int):
    """
    Execute batch coordinator logic.
    Updates the main job status based on subjob statuses.
    """
    try:
        with Session(session_utils.get_engine()) as session:
            # Query for all subjobs of this job
            subjob_data = session.query(db_schema.SubJob).filter(db_schema.SubJob.job_id == job_id).all()

            if not subjob_data:
                logger.error(f"No subjobs found for job {job_id} in batch coordinator")
                return

            # Count subjob statuses
            finished_count = sum(1 for s in subjob_data if s.status == STATUS_REVERSE_MAPPING["Finished"])
            failed_count = sum(1 for s in subjob_data if s.status == STATUS_REVERSE_MAPPING["Failed"])
            running_count = sum(1 for s in subjob_data if s.status == STATUS_REVERSE_MAPPING["Running"])
            queued_count = sum(1 for s in subjob_data if s.status == STATUS_REVERSE_MAPPING["Queued"])
            cancelled_count = sum(1 for s in subjob_data if s.status == STATUS_REVERSE_MAPPING["Cancelled"])

            all_finished = finished_count == len(subjob_data)
            any_failed = failed_count > 0
            all_complete = (finished_count + failed_count + cancelled_count) == len(subjob_data)

            # Update job status
            job_data = session.query(db_schema.Job).filter(db_schema.Job.job_id == job_id).first()

            if job_data:
                # If the job was already cancelled by user, don't overwrite the status —
                # just append the final subjob summary as a message
                already_cancelled = job_data.status == STATUS_REVERSE_MAPPING["Cancelled"]

                if all_finished and not already_cancelled:
                    job_data.status = STATUS_REVERSE_MAPPING["Finished"]
                    message = f"All {len(subjob_data)} subjobs completed successfully"
                elif any_failed and all_complete and not already_cancelled:
                    job_data.status = STATUS_REVERSE_MAPPING["Failed"]
                    message = f"Batch failed: {failed_count} failed, {finished_count} succeeded out of {len(subjob_data)} subjobs"
                elif cancelled_count > 0 and all_complete:
                    # Keep Cancelled status (may already be set by cancel_batch_job)
                    job_data.status = STATUS_REVERSE_MAPPING["Cancelled"]
                    message = (
                        f"Batch final: {cancelled_count} cancelled, {finished_count} succeeded, {failed_count} failed"
                    )
                else:
                    if not already_cancelled:
                        job_data.status = STATUS_REVERSE_MAPPING["Failed"]
                    message = f"Batch coordinator: {finished_count} finished, {failed_count} failed, {running_count} running, {queued_count} queued"
                    logger.warning(f"Unexpected state in batch coordinator for job {job_id}: {message}")

                if not already_cancelled:
                    job_data.finish_time = datetime.now()
                if job_data.messages:
                    job_data.messages += f"\n{message}"
                else:
                    job_data.messages = message

                session.commit()

                publish_job_update(job_id, "batch_completed", message)
                logger.info(f"Batch job {job_id} completed: {message}")

    except Exception as e:
        logger.error(f"Error in batch coordinator for job {job_id}: {e}")
        raise


# --- Batch completion counter (replaces RQ Dependency for O(N) instead of O(N^2)) ---


def _batch_counter_key(job_id: int) -> str:
    """Redis key for the batch completion counter."""
    return f"laue:batch:{job_id}:completed"


def _batch_meta_key(job_id: int) -> str:
    """Redis key for batch metadata (total count, coordinator info)."""
    return f"laue:batch:{job_id}:meta"


def _batch_coordinator_enqueued_key(job_id: int) -> str:
    """Redis key guarding duplicate batch coordinator enqueue attempts."""
    return f"laue:batch:{job_id}:coordinator_enqueued"


def setup_batch_counter(
    job_id: int,
    total_subjobs: int,
    coordinator_func_name: str,
    coordinator_args: list = None,
    job_type: str = "",
    **metadata,
):
    """
    Set up a batch completion counter in Redis.
    Called once when a batch job is enqueued.

    Args:
        job_id: Database job ID (the parent/batch job)
        total_subjobs: Total number of subjobs in the batch
        coordinator_func_name: Name of the coordinator function to call
            (e.g., 'execute_batch_coordinator' or 'execute_peakindexing_batch_coordinator')
        coordinator_args: Additional args to pass to the coordinator (beyond job_id)
        job_type: The RQ job type prefix (e.g., 'wire_reconstruction', 'peakindexing')
        **metadata: Additional batch metadata for chunked queue controls.
    """
    meta = {
        "total": total_subjobs,
        "coordinator_func": coordinator_func_name,
        "coordinator_args": coordinator_args or [],
        "job_type": job_type,
        **metadata,
    }
    redis_conn.set(_batch_meta_key(job_id), json.dumps(meta))
    redis_conn.set(_batch_counter_key(job_id), 0)
    redis_conn.delete(_batch_coordinator_enqueued_key(job_id))
    logger.info(f"Set up batch counter for job {job_id}: {total_subjobs} subjobs, coordinator={coordinator_func_name}")


def notify_subjobs_completed(parent_job_id: int, completed_count: int = 1):
    """
    Increment the batch completion counter for a parent job.
    If all subjobs are done, enqueue the coordinator job directly.
    """
    if completed_count <= 0:
        return

    counter_key = _batch_counter_key(parent_job_id)
    meta_key = _batch_meta_key(parent_job_id)

    completed = redis_conn.incrby(counter_key, completed_count)

    meta_raw = redis_conn.get(meta_key)
    if not meta_raw:
        logger.warning(f"No batch metadata found for job {parent_job_id}, skipping coordinator check")
        return

    meta = json.loads(meta_raw)
    total = meta["total"]

    if completed < total:
        return

    if not redis_conn.set(_batch_coordinator_enqueued_key(parent_job_id), 1, nx=True, ex=86400):
        logger.info(f"Coordinator already enqueued for batch job {parent_job_id}; skipping duplicate")
        return

    coordinator_func_name = meta["coordinator_func"]
    coordinator_args = meta.get("coordinator_args", [])

    coordinator_funcs = {
        "execute_batch_coordinator": execute_batch_coordinator,
        "execute_peakindexing_batch_coordinator": execute_peakindexing_batch_coordinator,
    }
    coordinator_func = coordinator_funcs.get(coordinator_func_name)

    if coordinator_func is None:
        logger.error(f"Unknown coordinator function: {coordinator_func_name}")
        logger.info(f"Falling back to inline coordinator execution for job {parent_job_id}")
        try:
            execute_batch_coordinator(parent_job_id)
        except Exception as e2:
            logger.error(f"Inline coordinator also failed for job {parent_job_id}: {e2}")
        redis_conn.delete(counter_key, meta_key)
        return

    try:
        from laue_portal.processing.queue.enqueue import enqueue_job

        enqueue_job(
            parent_job_id,
            "batch_coordinator",
            coordinator_func,
            True,  # at_front — coordinator should run ASAP
            None,  # no depends_on
            db_schema.Job,
            *coordinator_args,
        )
        logger.info(f"All {total} subjobs done for job {parent_job_id}, enqueued coordinator")
    except Exception as e:
        # If enqueue fails, run the coordinator inline so the job doesn't hang.
        logger.error(f"Failed to enqueue coordinator for job {parent_job_id}: {e}")
        logger.info(f"Falling back to inline coordinator execution for job {parent_job_id}")
        try:
            coordinator_func(parent_job_id, *coordinator_args)
        except Exception as e2:
            logger.error(f"Inline coordinator also failed for job {parent_job_id}: {e2}")

    redis_conn.delete(counter_key, meta_key)


def notify_subjob_completed(parent_job_id: int):
    """Compatibility wrapper for single-subjob completion notifications."""
    return notify_subjobs_completed(parent_job_id, 1)
