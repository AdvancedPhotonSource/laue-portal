"""Read-only queue, job, and worker inspection helpers."""

import logging
from typing import Any, Dict, List

from rq import Worker
from rq.job import Job
from rq.registry import FailedJobRegistry, FinishedJobRegistry, StartedJobRegistry

from laue_portal.processing.queue.core import job_queue, redis_conn

logger = logging.getLogger(__name__)


def get_job_status(rq_job_id: str) -> Dict[str, Any]:
    """
    Get the status of a job by its RQ job ID.

    Returns:
        Dictionary with job status information
    """
    try:
        job = Job.fetch(rq_job_id, connection=redis_conn)

        status_info = {
            "rq_job_id": job.id,
            "status": job.get_status(),
            "created_at": job.created_at,
            "started_at": job.started_at,
            "ended_at": job.ended_at,
            "result": job.result,
            "exc_info": job.exc_info,
            "meta": job.meta,
            "is_finished": job.is_finished,
            "is_failed": job.is_failed,
            "is_started": job.is_started,
            "is_queued": job.is_queued,
        }

        # Calculate progress if available in meta
        if job.meta and "progress" in job.meta:
            status_info["progress"] = job.meta["progress"]

        return status_info

    except Exception as e:
        logger.error(f"Error fetching job {rq_job_id}: {e}")
        return {"error": str(e), "rq_job_id": rq_job_id}


def get_queue_stats() -> Dict[str, int]:
    """
    Get statistics for the job queue.

    Returns:
        Dictionary with job counts by status
    """
    started_registry = StartedJobRegistry(queue=job_queue)
    finished_registry = FinishedJobRegistry(queue=job_queue)
    failed_registry = FailedJobRegistry(queue=job_queue)

    stats = {
        "queued": len(job_queue),
        "started": len(started_registry),
        "finished": len(finished_registry),
        "failed": len(failed_registry),
        "total": len(job_queue) + len(started_registry),
    }

    return stats


def get_active_jobs() -> List[Dict[str, Any]]:
    """Get all currently active (running) jobs."""
    active_jobs = []

    registry = StartedJobRegistry(queue=job_queue)
    for job_id in registry.get_job_ids():
        job_info = get_job_status(job_id)
        # Extract job type from the job metadata if available
        if job_info.get("meta") and "job_type" in job_info["meta"]:
            job_info["job_type"] = job_info["meta"]["job_type"]
        active_jobs.append(job_info)

    return active_jobs


def get_workers_info() -> List[Dict[str, Any]]:
    """Get information about all workers."""
    workers_info = []

    workers = Worker.all(connection=redis_conn)
    for worker in workers:
        info = {
            "name": worker.name,
            "queues": [q.name for q in worker.queues],
            "state": worker.get_state(),
            "current_job_id": worker.get_current_job_id(),
            "successful_job_count": worker.successful_job_count,
            "failed_job_count": worker.failed_job_count,
            "total_working_time": worker.total_working_time,
            "birth_date": worker.birth_date,
            "last_heartbeat": worker.last_heartbeat,
        }
        workers_info.append(info)

    return workers_info
