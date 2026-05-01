"""Queue control helpers for cancelling and reprioritizing jobs."""

import json
import logging
from datetime import datetime
from typing import Any, Dict

from rq.job import Job
from sqlalchemy.orm import Session

import laue_portal.database.session_utils as session_utils
from laue_portal.database import db_schema
from laue_portal.processing.queue.batch import (
    _batch_coordinator_enqueued_key,
    _batch_counter_key,
    _batch_meta_key,
    notify_subjobs_completed,
)
from laue_portal.processing.queue.core import STATUS_MAPPING, STATUS_REVERSE_MAPPING, job_queue, redis_conn
from laue_portal.processing.queue.lifecycle import publish_job_update

logger = logging.getLogger(__name__)


def cancel_job(rq_job_id: str) -> bool:
    """
    Cancel a queued or running job.

    Args:
        rq_job_id: RQ job ID

    Returns:
        True if cancelled successfully, False otherwise
    """
    try:
        job = Job.fetch(rq_job_id, connection=redis_conn)
        job.cancel()

        # Update job status in database to cancelled
        if job.meta and "db_job_id" in job.meta:
            db_job_id = job.meta["db_job_id"]
            with Session(session_utils.get_engine()) as session:
                job_data = session.query(db_schema.Job).filter(db_schema.Job.job_id == db_job_id).first()
                if job_data:
                    job_data.status = STATUS_REVERSE_MAPPING["Cancelled"]
                    job_data.finish_time = datetime.now()
                    if not job_data.messages:
                        job_data.messages = "Job cancelled by user"
                    else:
                        job_data.messages += "\nJob cancelled by user"
                    session.commit()

            publish_job_update(db_job_id, "cancelled", "Job cancelled by user")

        logger.info(f"Cancelled job {rq_job_id}")
        return True
    except Exception as e:
        logger.error(f"Error cancelling job {rq_job_id}: {e}")
        return False


def cancel_batch_job(db_job_id: int) -> Dict[str, Any]:
    """
    Cancel a batch job by its database job ID. Cancels all queued subjobs
    and the batch coordinator. Running subjobs are left to finish naturally.

    Works for any job type (wire_reconstruction, peakindexing, reconstruction).

    Args:
        db_job_id: Database job ID (Job.job_id)

    Returns:
        Dict with keys: success (bool), cancelled_count (int),
        skipped_running (int), already_done (int), message (str)
    """
    result = {"success": False, "cancelled_count": 0, "skipped_running": 0, "already_done": 0, "message": ""}

    try:
        with Session(session_utils.get_engine()) as session:
            # Get the parent job
            job_data = session.query(db_schema.Job).filter(db_schema.Job.job_id == db_job_id).first()

            if not job_data:
                result["message"] = f"Job {db_job_id} not found"
                return result

            # Don't cancel already-finished/failed/cancelled jobs
            if job_data.status in [
                STATUS_REVERSE_MAPPING["Finished"],
                STATUS_REVERSE_MAPPING["Failed"],
                STATUS_REVERSE_MAPPING["Cancelled"],
            ]:
                result["message"] = f"Job {db_job_id} is already {STATUS_MAPPING[job_data.status]}"
                result["already_done"] = 1
                return result

            # Get all subjobs for this job
            subjobs = session.query(db_schema.SubJob).filter(db_schema.SubJob.job_id == db_job_id).all()

            # Determine the job type — first try batch metadata in Redis,
            # then fall back to probing RQ job IDs
            job_type = None
            meta_raw = redis_conn.get(_batch_meta_key(db_job_id))
            if meta_raw:
                meta = json.loads(meta_raw)
                job_type = meta.get("job_type") or None

            if meta_raw and meta.get("queue_mode") == "chunked":
                queued_chunk_subjob_ids = []
                skipped_running_chunks = 0
                for rq_job_id, chunk_subjob_ids in zip(
                    meta.get("rq_job_ids", []), meta.get("chunk_subjob_ids", []), strict=False
                ):
                    try:
                        rq_job = Job.fetch(rq_job_id, connection=redis_conn)
                        if rq_job.is_queued:
                            rq_job.cancel()
                            queued_chunk_subjob_ids.extend(chunk_subjob_ids)
                        elif rq_job.is_started:
                            skipped_running_chunks += 1
                    except Exception as e:
                        logger.warning(f"Could not inspect chunk RQ job {rq_job_id}: {e}")

                now = datetime.now()
                if queued_chunk_subjob_ids:
                    queued_subjobs = (
                        session.query(db_schema.SubJob)
                        .filter(db_schema.SubJob.subjob_id.in_(queued_chunk_subjob_ids))
                        .filter(db_schema.SubJob.status == STATUS_REVERSE_MAPPING["Queued"])
                        .all()
                    )
                    for subjob in queued_subjobs:
                        subjob.status = STATUS_REVERSE_MAPPING["Cancelled"]
                        subjob.finish_time = now
                        subjob.messages = (
                            f"{subjob.messages}\nCancelled by user" if subjob.messages else "Cancelled by user"
                        )
                    result["cancelled_count"] = len(queued_subjobs)

                result["skipped_running"] = sum(
                    1 for subjob in subjobs if subjob.status == STATUS_REVERSE_MAPPING["Running"]
                )
                if skipped_running_chunks and result["skipped_running"] == 0:
                    result["skipped_running"] = skipped_running_chunks
                result["already_done"] = sum(
                    1
                    for subjob in subjobs
                    if subjob.status
                    in [
                        STATUS_REVERSE_MAPPING["Finished"],
                        STATUS_REVERSE_MAPPING["Failed"],
                        STATUS_REVERSE_MAPPING["Cancelled"],
                    ]
                )

                job_data.status = STATUS_REVERSE_MAPPING["Cancelled"]
                job_data.finish_time = now
                msg = (
                    f"Job cancelled by user. {result['cancelled_count']} queued subjob(s) cancelled, "
                    f"{result['skipped_running']} running chunk/subjob(s) left to finish."
                )
                job_data.messages = f"{job_data.messages}\n{msg}" if job_data.messages else msg
                session.commit()

                if result["cancelled_count"]:
                    notify_subjobs_completed(db_job_id, result["cancelled_count"])
                publish_job_update(db_job_id, "cancelled", msg)
                result["success"] = True
                result["message"] = msg
                logger.info(f"Cancelled chunked batch job {db_job_id}: {msg}")
                return result

            # Fall back: probe RQ to find the job type prefix
            if job_type is None and subjobs:
                for candidate_type in ["wire_reconstruction", "peakindexing", "reconstruction"]:
                    test_rq_id = f"{candidate_type}_{subjobs[0].subjob_id}"
                    try:
                        Job.fetch(test_rq_id, connection=redis_conn)
                        job_type = candidate_type
                        break
                    except Exception:
                        continue

            has_running = False
            cancelled_subjob_ids = []

            # Cancel queued subjobs
            for subjob in subjobs:
                if subjob.status == STATUS_REVERSE_MAPPING["Queued"]:
                    # Try to cancel the RQ job
                    if job_type:
                        rq_job_id = f"{job_type}_{subjob.subjob_id}"
                        try:
                            rq_job = Job.fetch(rq_job_id, connection=redis_conn)
                            rq_job.cancel()
                        except Exception as e:
                            logger.warning(f"Could not cancel RQ job {rq_job_id}: {e}")

                    # Update DB status regardless of RQ result
                    subjob.status = STATUS_REVERSE_MAPPING["Cancelled"]
                    subjob.finish_time = datetime.now()
                    if subjob.messages:
                        subjob.messages += "\nCancelled by user"
                    else:
                        subjob.messages = "Cancelled by user"
                    result["cancelled_count"] += 1
                    cancelled_subjob_ids.append(subjob.subjob_id)

                elif subjob.status == STATUS_REVERSE_MAPPING["Running"]:
                    # Leave running jobs alone
                    has_running = True
                    result["skipped_running"] += 1

                else:
                    # Already finished/failed/cancelled
                    result["already_done"] += 1

            # Update parent job status
            if has_running:
                # Some subjobs still running - mark as cancelled but note running ones
                job_data.status = STATUS_REVERSE_MAPPING["Cancelled"]
                job_data.finish_time = datetime.now()
                msg = (
                    f"Job cancelled by user. {result['cancelled_count']} queued subjob(s) cancelled, "
                    f"{result['skipped_running']} running subjob(s) left to finish."
                )
            else:
                # All subjobs are now done (cancelled/finished/failed)
                job_data.status = STATUS_REVERSE_MAPPING["Cancelled"]
                job_data.finish_time = datetime.now()
                msg = f"Job cancelled by user. {result['cancelled_count']} subjob(s) cancelled."

            if job_data.messages:
                job_data.messages += f"\n{msg}"
            else:
                job_data.messages = msg

            session.commit()

        # Notify the batch counter for each cancelled subjob so the coordinator
        # fires when running subjobs finish. If no running subjobs remain,
        # clean up the counter keys (coordinator is not needed).
        if has_running and cancelled_subjob_ids:
            notify_subjobs_completed(db_job_id, len(cancelled_subjob_ids))
        else:
            # No running subjobs — clean up counter keys, coordinator not needed
            redis_conn.delete(
                _batch_counter_key(db_job_id),
                _batch_meta_key(db_job_id),
                _batch_coordinator_enqueued_key(db_job_id),
            )

        publish_job_update(db_job_id, "cancelled", msg)

        result["success"] = True
        result["message"] = msg
        logger.info(f"Cancelled batch job {db_job_id}: {msg}")
        return result

    except Exception as e:
        logger.error(f"Error cancelling batch job {db_job_id}: {e}")
        result["message"] = f"Error: {str(e)}"
        return result


def move_batch_to_front(db_job_id: int) -> Dict[str, Any]:
    """
    Move all queued subjobs for a batch job to the front of the RQ queue.
    Running/finished/failed/cancelled subjobs are left unchanged.

    Args:
        db_job_id: Database job ID (Job.job_id)

    Returns:
        Dict with keys: success (bool), moved_count (int), message (str)
    """
    result = {"success": False, "moved_count": 0, "message": ""}

    try:
        with Session(session_utils.get_engine()) as session:
            # Get the parent job
            job_data = session.query(db_schema.Job).filter(db_schema.Job.job_id == db_job_id).first()

            if not job_data:
                result["message"] = f"Job {db_job_id} not found"
                return result

            # Only makes sense for Queued or Running jobs
            if job_data.status not in [STATUS_REVERSE_MAPPING["Queued"], STATUS_REVERSE_MAPPING["Running"]]:
                result["message"] = f"Job {db_job_id} is {STATUS_MAPPING[job_data.status]}, nothing to move"
                return result

            # Get all subjobs
            subjobs = session.query(db_schema.SubJob).filter(db_schema.SubJob.job_id == db_job_id).all()

            if not subjobs:
                result["message"] = f"Job {db_job_id} has no subjobs"
                return result

            # Determine job type from batch metadata
            job_type = None
            meta_raw = redis_conn.get(_batch_meta_key(db_job_id))
            if meta_raw:
                meta = json.loads(meta_raw)
                job_type = meta.get("job_type") or None

            if meta_raw and meta.get("queue_mode") == "chunked":
                for rq_job_id in reversed(meta.get("rq_job_ids", [])):
                    try:
                        rq_job = Job.fetch(rq_job_id, connection=redis_conn)
                        if rq_job.is_queued:
                            job_queue.remove(rq_job_id)
                            job_queue.push_job_id(rq_job_id, at_front=True)
                            result["moved_count"] += 1
                    except Exception as e:
                        logger.warning(f"Could not move chunk RQ job {rq_job_id} to front: {e}")

                if result["moved_count"] > 0:
                    result["success"] = True
                    result["message"] = f"Moved {result['moved_count']} chunk job(s) to front of queue"
                else:
                    result["message"] = "No queued chunk jobs found to move"
                logger.info(f"Move to front for chunked job {db_job_id}: {result['message']}")
                return result

            # Fall back: probe RQ
            if job_type is None:
                for candidate_type in ["wire_reconstruction", "peakindexing", "reconstruction"]:
                    test_rq_id = f"{candidate_type}_{subjobs[0].subjob_id}"
                    try:
                        Job.fetch(test_rq_id, connection=redis_conn)
                        job_type = candidate_type
                        break
                    except Exception:
                        continue

            if not job_type:
                result["message"] = f"Could not determine job type for job {db_job_id}"
                return result

            # Move queued subjobs to front (in reverse order so the first subjob ends up at the very front)
            queued_subjobs = [s for s in subjobs if s.status == STATUS_REVERSE_MAPPING["Queued"]]

            for subjob in reversed(queued_subjobs):
                rq_job_id = f"{job_type}_{subjob.subjob_id}"
                try:
                    # Remove from current position, push to front
                    job_queue.remove(rq_job_id)
                    job_queue.push_job_id(rq_job_id, at_front=True)
                    result["moved_count"] += 1
                except Exception as e:
                    logger.warning(f"Could not move RQ job {rq_job_id} to front: {e}")

        if result["moved_count"] > 0:
            result["success"] = True
            result["message"] = f"Moved {result['moved_count']} subjob(s) to front of queue"
        else:
            result["message"] = "No queued subjobs found to move"

        logger.info(f"Move to front for job {db_job_id}: {result['message']}")
        return result

    except Exception as e:
        logger.error(f"Error moving batch job {db_job_id} to front: {e}")
        result["message"] = f"Error: {str(e)}"
        return result
