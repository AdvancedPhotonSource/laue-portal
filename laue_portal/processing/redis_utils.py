"""
Redis Queue (RQ) utilities for job management in Laue Portal.
Provides functions for enqueueing jobs, checking status, and managing the job queue.
"""

from redis import Redis
from rq import Queue, Worker
from rq.job import Job
from rq.registry import StartedJobRegistry, FinishedJobRegistry, FailedJobRegistry
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any
import json
import time
from laue_portal.database import db_utils, db_schema
from sqlalchemy.orm import Session

# Import Laue Analysis functions
from laue_portal.recon import analysis_recon
from laueanalysis.reconstruct import reconstruct as wire_reconstruct  # This is actually for wire reconstruction
from laueanalysis.indexing import pyLaueGo

logger = logging.getLogger(__name__)

# Redis connection
redis_conn = Redis(host='localhost', port=6379, decode_responses=False)

# Single queue for all job types
job_queue = Queue('laue_jobs', connection=redis_conn)

# Job status mapping
STATUS_MAPPING = {
    0: "Queued",
    1: "Running", 
    2: "Finished",
    3: "Failed",
    4: "Cancelled"
}

# Reverse mapping for converting status names to integers
STATUS_REVERSE_MAPPING = {v: k for k, v in STATUS_MAPPING.items()}


# Generic helper for enqueueing jobs
def enqueue_job(job_id: int, job_type: str, execute_func, priority: int = 0, *args, **kwargs) -> str:
    """
    Generic function to enqueue any job type.
    
    Args:
        job_id: Database job ID
        job_type: Type of job (e.g., 'wire_reconstruction', 'reconstruction', 'peak_indexing')
        execute_func: The execution function to call
        priority: Job priority (higher numbers = higher priority, default: 0)
        *args, **kwargs: Arguments to pass to the execution function
    
    Returns:
        RQ job ID
    """
    # Add job metadata
    job_meta = {
        'db_job_id': job_id,
        'job_type': job_type,
        'priority': priority,
        'enqueued_at': datetime.now().isoformat()
    }
    
    # Enqueue the job with priority
    rq_job = job_queue.enqueue(
        execute_func,
        job_id,  # First parameter for all execute functions
        *args,
        **kwargs,
        job_id=f"{job_type}_{job_id}",
        meta=job_meta,
        priority=priority,  # Add priority parameter
        result_ttl=86400,  # Keep result for 24 hours
        failure_ttl=86400  # Keep failed job info for 24 hours
    )
    
    logger.info(f"Enqueued {job_type} job {job_id} with RQ ID: {rq_job.id}")
    
    # Update job status in database
    with Session(db_utils.ENGINE) as session:
        job = session.query(db_schema.Job).filter(db_schema.Job.job_id == job_id).first()
        if job:
            job.status = STATUS_REVERSE_MAPPING["Queued"]
            session.commit()
    
    return rq_job.id


def enqueue_wire_reconstruction(job_id: int, input_file: str, output_file: str,
                               geometry_file: str, depth_range: tuple, 
                               resolution: float = 1.0, priority: int = 0, **kwargs) -> str:
    """
    Enqueue a wire reconstruction job.
    
    Args:
        job_id: Database job ID
        input_file: Path to input file
        output_file: Path to output file
        geometry_file: Path to geometry file
        depth_range: Tuple of (start, end) depths
        resolution: Resolution parameter (default: 1.0)
        priority: Job priority (higher numbers = higher priority, default: 0)
        **kwargs: Additional optional arguments for wire reconstruction:
            - image_range: Optional[Tuple[int, int]] - Range of images to process
            - verbose: int - Verbosity level (default: 1)
            - percent_brightest: float - Percentage of brightest pixels to use (default: 100.0)
            - wire_edge: str - Wire edge to use ('leading' or 'trailing', default: 'leading')
            - memory_limit_mb: int - Memory limit in MB (default: 128)
            - executable: Optional[str] - Path to executable
            - timeout: int - Timeout in seconds (default: 7200)
            - normalization: Optional[str] - Normalization method
            - output_pixel_type: Optional[int] - Output pixel type
            - distortion_map: Optional[str] - Path to distortion map
            - detector_number: int - Detector number (default: 0)
            - wire_depths_file: Optional[str] - Path to wire depths file
    
    Returns:
        RQ job ID
    """
    return enqueue_job(
        job_id,
        'wire_reconstruction',
        execute_wire_reconstruction_job,
        priority,
        input_file,
        output_file,
        geometry_file,
        depth_range,
        resolution,
        **kwargs
    )


def enqueue_reconstruction(job_id: int, config_dict: Dict[str, Any], priority: int = 0) -> str:
    """
    Enqueue a reconstruction job (CA reconstruction).
    
    Args:
        job_id: Database job ID
        config_dict: Configuration dictionary for CA reconstruction
        priority: Job priority (higher numbers = higher priority, default: 0)
    
    Returns:
        RQ job ID
    """
    return enqueue_job(
        job_id,
        'reconstruction',
        execute_reconstruction_job,
        priority,
        config_dict
    )


def enqueue_peak_indexing(job_id: int, config_dict: Dict[str, Any], priority: int = 0) -> str:
    """
    Enqueue a peak indexing job.
    
    Args:
        job_id: Database job ID
        config_dict: Configuration dictionary for peak indexing
        priority: Job priority (higher numbers = higher priority, default: 0)
    
    Returns:
        RQ job ID
    """
    return enqueue_job(
        job_id,
        'peak_indexing',
        execute_peak_indexing_job,
        priority,
        config_dict
    )


def get_job_status(rq_job_id: str) -> Dict[str, Any]:
    """
    Get the status of a job by its RQ job ID.
    
    Returns:
        Dictionary with job status information
    """
    try:
        job = Job.fetch(rq_job_id, connection=redis_conn)
        
        status_info = {
            'rq_job_id': job.id,
            'status': job.get_status(),
            'created_at': job.created_at,
            'started_at': job.started_at,
            'ended_at': job.ended_at,
            'result': job.result,
            'exc_info': job.exc_info,
            'meta': job.meta,
            'is_finished': job.is_finished,
            'is_failed': job.is_failed,
            'is_started': job.is_started,
            'is_queued': job.is_queued
        }
        
        # Calculate progress if available in meta
        if job.meta and 'progress' in job.meta:
            status_info['progress'] = job.meta['progress']
        
        return status_info
        
    except Exception as e:
        logger.error(f"Error fetching job {rq_job_id}: {e}")
        return {'error': str(e), 'rq_job_id': rq_job_id}


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
        job.meta['progress'] = progress
        if message:
            job.meta['progress_message'] = message
        job.meta['last_updated'] = datetime.now().isoformat()
        job.save_meta()
        
        # Publish progress update for real-time monitoring
        redis_conn.publish(
            f'job_progress:{rq_job_id}',
            f'{progress}|{message or ""}'
        )
        
    except Exception as e:
        logger.error(f"Error updating job progress {rq_job_id}: {e}")


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
        'queued': len(job_queue),
        'started': len(started_registry),
        'finished': len(finished_registry),
        'failed': len(failed_registry),
        'total': len(job_queue) + len(started_registry)
    }
    
    return stats


def get_active_jobs() -> List[Dict[str, Any]]:
    """Get all currently active (running) jobs."""
    active_jobs = []
    
    registry = StartedJobRegistry(queue=job_queue)
    for job_id in registry.get_job_ids():
        job_info = get_job_status(job_id)
        # Extract job type from the job metadata if available
        if job_info.get('meta') and 'job_type' in job_info['meta']:
            job_info['job_type'] = job_info['meta']['job_type']
        active_jobs.append(job_info)
    
    return active_jobs


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
        if job.meta and 'db_job_id' in job.meta:
            db_job_id = job.meta['db_job_id']
            with Session(db_utils.ENGINE) as session:
                db_job = session.query(db_schema.Job).filter(db_schema.Job.job_id == db_job_id).first()
                if db_job:
                    db_job.status = STATUS_REVERSE_MAPPING["Cancelled"]
                    db_job.finish_time = datetime.now()
                    if not db_job.notes:
                        db_job.notes = "Job cancelled by user"
                    else:
                        db_job.notes += "\nJob cancelled by user"
                    session.commit()
            
            publish_job_update(db_job_id, 'cancelled', 'Job cancelled by user')
        
        logger.info(f"Cancelled job {rq_job_id}")
        return True
    except Exception as e:
        logger.error(f"Error cancelling job {rq_job_id}: {e}")
        return False


def get_workers_info() -> List[Dict[str, Any]]:
    """Get information about all workers."""
    workers_info = []
    
    workers = Worker.all(connection=redis_conn)
    for worker in workers:
        info = {
            'name': worker.name,
            'queues': [q.name for q in worker.queues],
            'state': worker.get_state(),
            'current_job_id': worker.get_current_job_id(),
            'successful_job_count': worker.successful_job_count,
            'failed_job_count': worker.failed_job_count,
            'total_working_time': worker.total_working_time,
            'birth_date': worker.birth_date,
            'last_heartbeat': worker.last_heartbeat
        }
        workers_info.append(info)
    
    return workers_info


def publish_job_update(job_id: int, status: str, message: str = None):
    """
    Publish a job status update for real-time monitoring.
    
    Args:
        job_id: Database job ID
        status: Job status
        message: Optional status message
    """
    update_data = {
        'job_id': job_id,
        'status': status,
        'timestamp': datetime.now().isoformat()
    }
    if message:
        update_data['message'] = message
    
    # Publish to Redis pub/sub channel
    redis_conn.publish('laue:job_updates', json.dumps(update_data))


# Helper function that wraps job execution with status updates
def execute_with_status_updates(job_id: int, job_type: str, job_func, *args, **kwargs):
    """
    Execute a job function with automatic status updates.
    
    Args:
        job_id: Database job ID
        job_type: Type of job (for logging)
        job_func: The actual job function to execute
        *args, **kwargs: Arguments to pass to job_func
    """
    try:
        # Update job status to running
        with Session(db_utils.ENGINE) as session:
            job = session.query(db_schema.Job).filter(db_schema.Job.job_id == job_id).first()
            if job:
                job.status = STATUS_REVERSE_MAPPING["Running"]
                job.start_time = datetime.now()
                session.commit()
        
        publish_job_update(job_id, 'running', f'Starting {job_type}')
        
        # Execute the actual job function
        result = job_func(*args, **kwargs)
        
        # Update job status to finished
        with Session(db_utils.ENGINE) as session:
            job = session.query(db_schema.Job).filter(db_schema.Job.job_id == job_id).first()
            if job:
                job.status = STATUS_REVERSE_MAPPING["Finished"]
                job.finish_time = datetime.now()
                session.commit()
        
        publish_job_update(job_id, 'finished', f'{job_type} completed successfully')
        return result
        
    except Exception as e:
        # Update job status to failed
        with Session(db_utils.ENGINE) as session:
            job = session.query(db_schema.Job).filter(db_schema.Job.job_id == job_id).first()
            if job:
                job.status = STATUS_REVERSE_MAPPING["Failed"]
                job.finish_time = datetime.now()
                job.notes = f"Error: {str(e)}"
                session.commit()
        
        publish_job_update(job_id, 'failed', f'{job_type} failed: {str(e)}')
        raise


# Job execution functions that will be called by RQ workers
def execute_reconstruction_job(job_id: int, config_dict: Dict[str, Any]):
    """Execute a reconstruction job."""
    def _do_reconstruction():
        # return analysis_recon.run_analysis(config_dict)
        # Testing: sleep for 5 seconds instead
        time.sleep(5)
        return {"status": "test_completed", "message": "Slept for 5 seconds instead of running analysis"}
    
    return execute_with_status_updates(
        job_id,
        'Reconstruction analysis',
        _do_reconstruction
    )


def execute_wire_reconstruction_job(job_id: int, input_file: str, output_file: str,
                                   geometry_file: str, depth_range: tuple,
                                   resolution: float, **kwargs):
    """Execute a wire reconstruction job."""
    def _do_wire_reconstruction():
        # return wire_reconstruct(input_file, output_file, geometry_file, depth_range, resolution, **kwargs)
        # Testing: sleep for 5 seconds instead
        time.sleep(5)
        return {"status": "test_completed", "message": "Slept for 5 seconds instead of running wire reconstruction"}
    
    return execute_with_status_updates(
        job_id,
        'Wire reconstruction',
        _do_wire_reconstruction
    )


def execute_peak_indexing_job(job_id: int, config_dict: Dict[str, Any]):
    """Execute a peak indexing job."""
    def _do_peak_indexing():
        # return pyLaueGo(config_dict).run(0, 1)  # rank=0, size=1 for single process
        # Testing: sleep for 5 seconds instead
        time.sleep(5)
        return {"status": "test_completed", "message": "Slept for 5 seconds instead of running peak indexing"}
    
    return execute_with_status_updates(
        job_id,
        'Peak indexing',
        _do_peak_indexing
    )
