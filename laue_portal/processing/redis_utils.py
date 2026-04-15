"""
Redis Queue (RQ) utilities for job management in Laue Portal.
Provides functions for enqueueing jobs, checking status, and managing the job queue.
"""

import glob
import json
import logging
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Dict, List

import redis
from laueanalysis.indexing import index
from laueanalysis.reconstruct import reconstruct as wire_reconstruct
from redis import Redis
from rq import Queue, Worker
from rq.job import Job
from rq.registry import FailedJobRegistry, FinishedJobRegistry, StartedJobRegistry
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import Session

import laue_portal.database.session_utils as session_utils
from laue_portal.config import REDIS_CONFIG
from laue_portal.database import db_schema

# Import Laue Analysis functions

logger = logging.getLogger(__name__)

# Redis connection
redis_conn = Redis(host="localhost", port=REDIS_CONFIG["port"], decode_responses=False)

# Single queue for all job types
job_queue = Queue("laue_jobs", connection=redis_conn)

# Global variable to store startup status
REDIS_CONNECTED_AT_STARTUP = None


def check_redis_connection():
    """Check if Redis server is accessible and responding."""
    try:
        return redis_conn.ping()
    except (redis.ConnectionError, redis.TimeoutError, Exception):
        return False


def init_redis_status():
    """Initialize Redis status check on startup."""
    global REDIS_CONNECTED_AT_STARTUP
    REDIS_CONNECTED_AT_STARTUP = check_redis_connection()
    logger.info(f"Redis connection status at startup: {'Connected' if REDIS_CONNECTED_AT_STARTUP else 'Disconnected'}")
    return REDIS_CONNECTED_AT_STARTUP


# Job status mapping
STATUS_MAPPING = {0: "Queued", 1: "Running", 2: "Finished", 3: "Failed", 4: "Cancelled"}

# Reverse mapping for converting status names to integers
STATUS_REVERSE_MAPPING = {v: k for k, v in STATUS_MAPPING.items()}


# Generic helper for enqueueing jobs
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
    """
    Generic function to enqueue any job type.

    Args:
        job_id: Database job ID (can be Job.job_id or SubJob.subjob_id)
        job_type: Type of job (e.g., 'wire_reconstruction', 'reconstruction', 'peakindexing')
        execute_func: The execution function to call
        at_front: Whether to add job at front of queue (default: False)
        depends_on: Optional RQ job ID or Job object to depend on
        table: Database table class (db_schema.Job or db_schema.SubJob)
        *args, **kwargs: Arguments to pass to the execution function

    Returns:
        RQ job ID
    """
    # Extract timeout from kwargs if present
    timeout = kwargs.get("timeout", 7200)  # Default to 2 hours if not specified

    # Add job metadata
    job_meta = {
        "db_job_id": job_id,
        "job_type": job_type,
        "table": table.__tablename__,
        "enqueued_at": datetime.now().isoformat(),
    }

    # Note: Status is already set to Queued when Job/SubJob records are created
    # in the submission pages (create_peakindexing.py, create_wire_reconstruction.py, etc.)
    # so we skip the redundant DB update here to avoid 5000+ individual DB sessions
    # for large batch jobs.

    # Enqueue the job with optional dependency
    rq_job = job_queue.enqueue(
        execute_func,
        job_id,  # First parameter for all execute functions
        *args,
        **kwargs,
        job_id=f"{job_type}_{job_id}",
        meta=job_meta,
        at_front=at_front,
        depends_on=depends_on,
        job_timeout=timeout,
        result_ttl=86400,  # Keep result for 24 hours
        failure_ttl=86400,  # Keep failed job info for 24 hours
    )

    logger.info(f"Enqueued {job_type} job {job_id} with RQ ID: {rq_job.id} (timeout: {timeout}s)")

    return rq_job.id


def merge_xml_files(xml_dir: str, output_xml_path: str) -> Dict[str, Any]:
    """
    Merge multiple XML files from a directory into a single XML file.

    Each individual XML file has an <AllSteps> root with one or more <step> elements.
    The merged file will have a single <AllSteps> root containing all <step> elements
    from all input files.

    Args:
        xml_dir: Directory containing the individual XML files
        output_xml_path: Path for the merged output XML file

    Returns:
        Dict with merge status information:
        - success: bool
        - files_merged: int
        - output_path: str
        - error: str (if failed)
    """
    result = {"success": False, "files_merged": 0, "output_path": output_xml_path, "error": None}

    try:
        # Find all XML files in the directory
        xml_pattern = os.path.join(xml_dir, "*.xml")
        xml_files = sorted(glob.glob(xml_pattern))

        if not xml_files:
            result["error"] = f"No XML files found in {xml_dir}"
            logger.warning(result["error"])
            return result

        # Create the merged root element
        merged_root = ET.Element("AllSteps")

        # Process each XML file
        for xml_file in xml_files:
            try:
                tree = ET.parse(xml_file)
                root = tree.getroot()

                # Find all <step> elements and add them to the merged root.
                # Use a match that handles both namespaced and non-namespaced
                # step elements. ElementTree represents namespaced tags as
                # {namespace_uri}localname, so a plain findall('.//step') will
                # miss elements like <step xmlns="...">.
                found_steps = root.findall(".//step")
                if not found_steps:
                    # Try wildcard namespace match: .//{*}step matches
                    # <step> in any namespace (Python 3.8+)
                    found_steps = root.findall(".//{*}step")

                for step in found_steps:
                    # Deep copy the step element to avoid issues with element ownership
                    merged_root.append(step)

            except ET.ParseError as e:
                logger.warning(f"Failed to parse XML file {xml_file}: {e}")
                continue
            except Exception as e:
                logger.warning(f"Error processing XML file {xml_file}: {e}")
                continue

        # Check if we have any steps (handle both namespaced and non-namespaced)
        steps = list(merged_root)
        if not steps:
            result["error"] = f"No valid <step> elements found in XML files from {xml_dir}"
            logger.warning(result["error"])
            return result

        # Create the output directory if it doesn't exist
        output_dir = os.path.dirname(output_xml_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        # Format and write the merged XML file
        ET.indent(merged_root, space="    ")
        tree = ET.ElementTree(merged_root)

        with open(output_xml_path, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" ?>\n')
            tree.write(f, encoding="unicode", xml_declaration=False)

        result["success"] = True
        result["files_merged"] = len(xml_files)
        logger.info(f"Successfully merged {len(xml_files)} XML files into {output_xml_path}")

        return result

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Error merging XML files: {e}")
        return result


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


# Generic batch handler
def _enqueue_batch(
    job_id: int,
    job_type: str,
    execute_func,
    at_front: bool = False,
    input_files: List[str] = None,
    output_files: List[str] = None,
    *args,
    **kwargs,
) -> str:
    """
    Generic batch handler that enqueues subjobs in parallel with a coordinator.

    Args:
        job_id: Database job ID (the main/batch job)
        job_type: Type of job (e.g., 'wire_reconstruction', 'reconstruction')
        execute_func: The execution function to call for each subjob
        at_front: Whether to add jobs at front of queue (default: False)
        input_files: Optional list of input files (one per subjob)
        output_files: Optional list of output files (one per subjob)
        *args, **kwargs: Arguments to pass to the execution function

    Returns:
        RQ job ID of the batch coordinator
    """
    # Query for subjobs
    with Session(session_utils.get_engine()) as session:
        subjob_data = (
            session.query(db_schema.SubJob)
            .filter(db_schema.SubJob.job_id == job_id)
            .order_by(db_schema.SubJob.subjob_id)
            .all()
        )

        if not subjob_data:
            raise ValueError(f"No subjobs found for job_id {job_id}. {job_type} requires subjobs to be created first.")

    # Validate file lists if provided
    if input_files is not None:
        if len(input_files) != len(subjob_data):
            raise ValueError(
                f"Number of input files ({len(input_files)}) does not match number of subjobs ({len(subjob_data)})"
            )
    if output_files is not None:
        if len(output_files) != len(subjob_data):
            raise ValueError(
                f"Number of output files ({len(output_files)}) does not match number of subjobs ({len(subjob_data)})"
            )

    # Set up the batch completion counter — coordinator will be enqueued
    # automatically when all subjobs finish (O(1) per completion, not O(N^2))
    setup_batch_counter(job_id, len(subjob_data), "execute_batch_coordinator", job_type=job_type)

    # Enqueue each subjob in parallel (no dependencies between them)
    for i, subjob in enumerate(subjob_data):
        # Build subjob-specific args based on what file lists are provided
        subjob_args = []
        if input_files is not None:
            subjob_args.append(input_files[i])
        if output_files is not None:
            subjob_args.append(output_files[i])
        subjob_args.extend(args)

        enqueue_job(
            subjob.subjob_id,
            job_type,
            execute_func,
            at_front,
            None,  # No dependencies - run in parallel
            db_schema.SubJob,  # Specify SubJob table
            *subjob_args,
            **kwargs,
        )

    logger.info(f"Enqueued batch {job_type} job {job_id} with {len(subjob_data)} parallel subjobs")
    return f"batch_{job_id}"


def enqueue_wire_reconstruction(
    job_id: int,
    input_files: List[str],
    output_files: List[str],
    geometry_file: str,
    depth_range: tuple,
    resolution: float,
    at_front: bool = False,
    **kwargs,
) -> str:
    """
    Enqueue a wire reconstruction batch job.
    Always expects subjobs to exist for the given job_id.

    Args:
        job_id: Database job ID
        input_files: List of paths to input files (one per subjob)
        output_files: List of paths to output files (one per subjob)
        geometry_file: Path to geometry file
        depth_range: Tuple of (start, end) depths
        resolution: Resolution parameter
        at_front: Whether to add job at front of queue (default: False)
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
        RQ job ID of the batch coordinator
    """
    return _enqueue_batch(
        job_id,
        "wire_reconstruction",
        execute_wire_reconstruction_job,
        at_front,
        input_files,
        output_files,
        geometry_file,
        depth_range,
        resolution,
        **kwargs,
    )


def enqueue_reconstruction(job_id: int, config_dict: Dict[str, Any], at_front: bool = False) -> str:
    """
    Enqueue a reconstruction batch job (CA reconstruction).
    Always expects subjobs to exist for the given job_id.

    Args:
        job_id: Database job ID
        config_dict: Configuration dictionary for CA reconstruction
        at_front: Whether to add job at front of queue (default: False)

    Returns:
        RQ job ID of the batch coordinator
    """
    return _enqueue_batch(job_id, "reconstruction", execute_reconstruction_job, at_front, config_dict)


def enqueue_peakindexing(
    job_id: int,
    input_files: List[str],
    output_files: List[str],
    geometry_file: str,
    crystal_file: str,
    boxsize: int,
    max_rfactor: float,
    min_size: int,
    min_separation: int,
    threshold: int,
    peak_shape: str,
    max_peaks: int,
    smooth: bool,
    index_kev_max_calc: float,
    index_kev_max_test: float,
    index_angle_tolerance: float,
    index_cone: float,
    index_h: int,
    index_k: int,
    index_l: int,
    at_front: bool = False,
    output_xml: str = "output.xml",
    **kwargs,
) -> str:
    """
    Enqueue a peakindexing batch job.
    Always expects subjobs to exist for the given job_id.
    Uses a specialized batch coordinator that merges XML output files on completion.

    Args:
        job_id: Database job ID
        input_files: List of paths to input files (one per subjob)
        output_files: List of output directories (one per subjob)
        geometry_file: Path to geometry file
        crystal_file: Path to crystal file
        boxsize: Box size for peak detection
        max_rfactor: Maximum R-factor
        min_size: Minimum peak size
        min_separation: Minimum separation between peaks
        threshold: Threshold for peak detection
        peak_shape: Peak shape ('L' for Lorentzian, 'G' for Gaussian)
        max_peaks: Maximum number of peaks to find
        smooth: Whether to smooth the image
        index_kev_max_calc: Maximum keV for indexing calculation
        index_kev_max_test: Maximum keV for indexing test
        index_angle_tolerance: Angle tolerance for indexing
        index_cone: Cone angle for indexing
        index_h: H index
        index_k: K index
        index_l: L index
        at_front: Whether to add job at front of queue (default: False)
        output_xml: Output XML filename or path (default: 'output.xml')
            - If absolute path: saves directly to that path
            - If relative path or filename: saves to output_files directory
        **kwargs: Additional optional arguments

    Returns:
        RQ job ID of the batch coordinator
    """
    # Query for subjobs
    with Session(session_utils.get_engine()) as session:
        subjob_data = (
            session.query(db_schema.SubJob)
            .filter(db_schema.SubJob.job_id == job_id)
            .order_by(db_schema.SubJob.subjob_id)
            .all()
        )

        if not subjob_data:
            raise ValueError(
                f"No subjobs found for job_id {job_id}. peakindexing requires subjobs to be created first."
            )

    # Validate file lists
    if len(input_files) != len(subjob_data):
        raise ValueError(
            f"Number of input files ({len(input_files)}) does not match number of subjobs ({len(subjob_data)})"
        )
    if len(output_files) != len(subjob_data):
        raise ValueError(
            f"Number of output files ({len(output_files)}) does not match number of subjobs ({len(subjob_data)})"
        )

    # All output directories should be the same for peakindexing
    # (individual XML files go to output_dir/xml/, merged goes to output_dir)
    output_dir = output_files[0] if output_files else ""

    # Set up the batch completion counter — coordinator will be enqueued
    # automatically when all subjobs finish (O(1) per completion, not O(N^2))
    setup_batch_counter(
        job_id,
        len(subjob_data),
        "execute_peakindexing_batch_coordinator",
        coordinator_args=[output_dir, output_xml],
        job_type="peakindexing",
    )

    # Enqueue each subjob in parallel (no dependencies between them)
    for i, subjob in enumerate(subjob_data):
        enqueue_job(
            subjob.subjob_id,
            "peakindexing",
            execute_peakindexing_job,
            at_front,
            None,  # No dependencies - run in parallel
            db_schema.SubJob,  # Specify SubJob table
            input_files[i],
            output_files[i],
            geometry_file,
            crystal_file,
            boxsize,
            max_rfactor,
            min_size,
            min_separation,
            threshold,
            peak_shape,
            max_peaks,
            smooth,
            index_kev_max_calc,
            index_kev_max_test,
            index_angle_tolerance,
            index_cone,
            index_h,
            index_k,
            index_l,
            **kwargs,
        )

    logger.info(
        f"Enqueued peakindexing batch job {job_id} with {len(subjob_data)} parallel subjobs, output_xml={output_xml}"
    )
    return f"batch_{job_id}"


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
            for _ in cancelled_subjob_ids:
                notify_subjob_completed(db_job_id)
        else:
            # No running subjobs — clean up counter keys, coordinator not needed
            redis_conn.delete(_batch_counter_key(db_job_id), _batch_meta_key(db_job_id))

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


# --- Batch completion counter (replaces RQ Dependency for O(N) instead of O(N^2)) ---


def _batch_counter_key(job_id: int) -> str:
    """Redis key for the batch completion counter."""
    return f"laue:batch:{job_id}:completed"


def _batch_meta_key(job_id: int) -> str:
    """Redis key for batch metadata (total count, coordinator info)."""
    return f"laue:batch:{job_id}:meta"


def setup_batch_counter(
    job_id: int, total_subjobs: int, coordinator_func_name: str, coordinator_args: list = None, job_type: str = ""
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
    """
    meta = {
        "total": total_subjobs,
        "coordinator_func": coordinator_func_name,
        "coordinator_args": coordinator_args or [],
        "job_type": job_type,
    }
    redis_conn.set(_batch_meta_key(job_id), json.dumps(meta))
    redis_conn.set(_batch_counter_key(job_id), 0)
    logger.info(f"Set up batch counter for job {job_id}: {total_subjobs} subjobs, coordinator={coordinator_func_name}")


def notify_subjob_completed(parent_job_id: int):
    """
    Increment the batch completion counter for a parent job.
    If all subjobs are done, enqueue the coordinator job directly.

    Called from execute_with_status_updates() after a subjob finishes, fails, or is cancelled.
    This is O(1) per subjob — no dependency checking.

    Args:
        parent_job_id: Database job ID of the parent/batch job
    """
    counter_key = _batch_counter_key(parent_job_id)
    meta_key = _batch_meta_key(parent_job_id)

    # Atomic increment
    completed = redis_conn.incr(counter_key)

    # Read metadata to check total
    meta_raw = redis_conn.get(meta_key)
    if not meta_raw:
        logger.warning(f"No batch metadata found for job {parent_job_id}, skipping coordinator check")
        return

    meta = json.loads(meta_raw)
    total = meta["total"]

    if completed >= total:
        # All subjobs are done — enqueue the coordinator
        coordinator_func_name = meta["coordinator_func"]
        coordinator_args = meta.get("coordinator_args", [])

        # Look up the coordinator function by name
        coordinator_funcs = {
            "execute_batch_coordinator": execute_batch_coordinator,
            "execute_peakindexing_batch_coordinator": execute_peakindexing_batch_coordinator,
        }
        coordinator_func = coordinator_funcs.get(coordinator_func_name)

        if coordinator_func is None:
            logger.error(f"Unknown coordinator function: {coordinator_func_name}")
            # Fall back: run the coordinator inline so the job doesn't hang
            logger.info(f"Falling back to inline coordinator execution for job {parent_job_id}")
            try:
                execute_batch_coordinator(parent_job_id)
            except Exception as e2:
                logger.error(f"Inline coordinator also failed for job {parent_job_id}: {e2}")
            redis_conn.delete(counter_key, meta_key)
            return

        # Enqueue the coordinator directly (no Dependency needed)
        try:
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
            # If enqueue fails, run the coordinator inline so the job doesn't hang
            logger.error(f"Failed to enqueue coordinator for job {parent_job_id}: {e}")
            logger.info(f"Falling back to inline coordinator execution for job {parent_job_id}")
            try:
                coordinator_func(parent_job_id, *coordinator_args)
            except Exception as e2:
                logger.error(f"Inline coordinator also failed for job {parent_job_id}: {e2}")

        # Clean up counter keys
        redis_conn.delete(counter_key, meta_key)


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
            notify_subjob_completed(parent_job_id)

        raise


# Job execution functions that will be called by RQ workers
def execute_reconstruction_job(job_id: int, config_dict: Dict[str, Any]):
    """Execute a reconstruction job (subjob)."""

    def _do_reconstruction():
        # return analysis_recon.run_analysis(config_dict)
        # Testing: sleep for 5 seconds instead
        time.sleep(5)
        return {"status": "test_completed", "message": "Slept for 5 seconds instead of running analysis"}

    return execute_with_status_updates(
        job_id,
        "CA Reconstruction",
        _do_reconstruction,
        db_schema.SubJob,  # This is called for subjobs
    )


def execute_wire_reconstruction_job(
    job_id: int, input_file: str, output_file: str, geometry_file: str, depth_range: tuple, resolution: float, **kwargs
):
    """Execute a wire reconstruction job (subjob)."""

    def _do_wire_reconstruction():
        return wire_reconstruct(input_file, output_file, geometry_file, depth_range, resolution, **kwargs)

    return execute_with_status_updates(
        job_id,
        "Wire reconstruction",
        _do_wire_reconstruction,
        db_schema.SubJob,  # This is called for subjobs
    )


def execute_peakindexing_job(
    job_id: int,
    input_file: str,
    output_dir: str,
    geometry_file: str,
    crystal_file: str,
    boxsize: int,
    max_rfactor: float,
    min_size: int,
    min_separation: int,
    threshold: int,
    peak_shape: str,
    max_peaks: int,
    smooth: bool,
    index_kev_max_calc: float,
    index_kev_max_test: float,
    index_angle_tolerance: float,
    index_cone: float,
    index_h: int,
    index_k: int,
    index_l: int,
    **kwargs,
):
    """Execute a peakindexing job (subjob)."""

    def _do_peakindexing():
        return index(
            input_image=input_file,
            output_dir=output_dir,
            geo_file=geometry_file,
            crystal_file=crystal_file,
            boxsize=boxsize,
            max_rfactor=max_rfactor,
            min_size=min_size,
            min_separation=min_separation,
            threshold=threshold,
            peak_shape=peak_shape,
            max_peaks=max_peaks,
            smooth=smooth,
            index_kev_max_calc=index_kev_max_calc,
            index_kev_max_test=index_kev_max_test,
            index_angle_tolerance=index_angle_tolerance,
            index_cone=index_cone,
            index_h=index_h,
            index_k=index_k,
            index_l=index_l,
            **kwargs,
        )

    return execute_with_status_updates(
        job_id,
        "Peakindexing",
        _do_peakindexing,
        db_schema.SubJob,  # This is called for subjobs
    )
