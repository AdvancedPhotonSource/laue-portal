"""Job lifecycle updates and Redis pub/sub notifications."""

import json
import logging
from datetime import datetime

from rq.job import Job
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import Session

import laue_portal.database.session_utils as session_utils
from laue_portal.database import db_schema
from laue_portal.processing.queue.core import STATUS_REVERSE_MAPPING, redis_conn

logger = logging.getLogger(__name__)


def publish_job_update(job_id: int, status: str, message: str = None):
    """
    Publish a job status update for real-time monitoring.

    Args:
        job_id: Database job ID
        status: Job status
        message: Optional status message
    """
    update_data = {"job_id": job_id, "status": status, "timestamp": datetime.now().isoformat()}
    if message:
        update_data["message"] = message

    # Publish to Redis pub/sub channel
    redis_conn.publish("laue:job_updates", json.dumps(update_data))


def update_job_progress(rq_job_id: str, progress: int, message: str = None):
    """
    Update job progress (for long-running jobs).

    Args:
        rq_job_id: RQ job ID
        progress: Progress percentage (0-100)
        message: Optional status message
    """
    try:
        job = Job.fetch(rq_job_id, connection=redis_conn)
        job.meta["progress"] = progress
        if message:
            job.meta["progress_message"] = message
        job.meta["last_updated"] = datetime.now().isoformat()
        job.save_meta()

        # Publish progress update for real-time monitoring
        redis_conn.publish(f"job_progress:{rq_job_id}", f"{progress}|{message or ''}")

    except Exception as e:
        logger.error(f"Error updating job progress {rq_job_id}: {e}")


# Helper function that wraps job execution with status updates
def execute_with_status_updates(job_id: int, job_type: str, job_func, table=db_schema.Job, *args, **kwargs):
    """
    Execute a job function with automatic status updates.

    Args:
        job_id: Database job ID (can be Job.job_id or SubJob.subjob_id)
        job_type: Type of job (for logging)
        job_func: The actual job function to execute
        table: Database table class (db_schema.Job or db_schema.SubJob)
        *args, **kwargs: Arguments to pass to job_func
    """
    # Get the primary key column dynamically
    mapper = inspect(table)
    pk_col = list(mapper.primary_key)[0]  # Get first primary key column

    is_subjob = table == db_schema.SubJob
    parent_job_id = None  # Will be set for subjobs to trigger batch counter

    try:
        # Update job status to running
        with Session(session_utils.get_engine()) as session:
            # Query using the primary key
            job_data = session.query(table).filter(pk_col == job_id).first()
            if job_data:
                job_data.status = STATUS_REVERSE_MAPPING["Running"]
                job_start_time = datetime.now()
                job_data.start_time = job_start_time

                # If this is a subjob, also update the parent job status if it's still queued
                if is_subjob and hasattr(job_data, "job_id"):
                    parent_job_id = job_data.job_id
                    parent_job_data = session.query(db_schema.Job).filter(db_schema.Job.job_id == parent_job_id).first()
                    if parent_job_data and parent_job_data.status == STATUS_REVERSE_MAPPING["Queued"]:
                        parent_job_data.status = STATUS_REVERSE_MAPPING["Running"]
                        parent_job_data.start_time = job_start_time
                        logger.info(f"Updated parent job {parent_job_id} status to Running")

                session.commit()

        publish_job_update(job_id, "running", f"Starting {job_type}")

        # Execute the actual job function
        result = job_func(*args, **kwargs)

        # Update job status to finished
        with Session(session_utils.get_engine()) as session:
            # Query using the primary key
            job_data = session.query(table).filter(pk_col == job_id).first()
            if job_data:
                job_data.status = STATUS_REVERSE_MAPPING["Finished"]
                job_data.finish_time = datetime.now()

                # Store the CLI command(s) used
                if hasattr(job_data, "command") and result is not None:
                    # Extract command based on result type
                    if hasattr(result, "command") and result.command:
                        # Wire reconstruction - single command string
                        job_data.command = result.command
                    elif hasattr(result, "command_history") and result.command_history:
                        # Peak indexing - list of commands
                        job_data.command = "\n".join(result.command_history)

                # Store the job result directly
                if hasattr(job_data, "messages"):
                    # Format the result for display
                    if result is not None:
                        # Handle wire reconstruction results specially
                        if job_type == "Wire reconstruction":
                            result_str = ""

                            if result.success:
                                result_str += "\n".join(
                                    [
                                        "Reconstruction successful!",
                                        "\nOutput files created:",
                                        "".join([f"- {f}" for f in result.output_files]),
                                    ]
                                )
                            else:
                                result_str += "\n".join(["Reconstruction failed.", f"Error: {result.error}"])

                            if result.log:
                                result_str += "\n".join(["\nLog:", result.log])

                        else:
                            result_str = str(result)

                        if job_data.messages:
                            job_data.messages += f"\n\n{result_str}"
                        else:
                            job_data.messages = result_str

                session.commit()

        publish_job_update(job_id, "finished", f"{job_type} completed successfully")

        # Notify the batch counter that this subjob is done
        if is_subjob and parent_job_id is not None:
            from laue_portal.processing.queue.batch import notify_subjob_completed

            notify_subjob_completed(parent_job_id)

        return result

    except Exception as e:
        # Update job status to failed
        with Session(session_utils.get_engine()) as session:
            # Query using the primary key
            job_data = session.query(table).filter(pk_col == job_id).first()
            if job_data:
                job_data.status = STATUS_REVERSE_MAPPING["Failed"]
                job_data.finish_time = datetime.now()
                if hasattr(job_data, "messages"):  # Both Job and SubJob have messages field
                    job_data.messages = f"Error: {str(e)}"
                session.commit()

        publish_job_update(job_id, "failed", f"{job_type} failed: {str(e)}")

        # Notify the batch counter even on failure — coordinator needs to know
        if is_subjob and parent_job_id is not None:
            from laue_portal.processing.queue.batch import notify_subjob_completed

            notify_subjob_completed(parent_job_id)

        raise
