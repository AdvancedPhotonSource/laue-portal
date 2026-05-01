"""RQ enqueue APIs for Laue processing jobs."""

import logging
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy.orm import Session

import laue_portal.database.session_utils as session_utils
from laue_portal.database import db_schema
from laue_portal.processing.queue.batch import setup_batch_counter
from laue_portal.processing.queue.core import PEAKINDEXING_QUEUE_BATCH_SIZE, _chunked, job_queue
from laue_portal.processing.queue.executors import (
    execute_peakindexing_chunk,
    execute_reconstruction_job,
    execute_wire_reconstruction_job,
)

logger = logging.getLogger(__name__)


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
    # Extract queue-only options from kwargs before passing args to the worker function.
    timeout = kwargs.pop("timeout", 7200)  # Default to 2 hours if not specified
    rq_job_id = kwargs.pop("rq_job_id", None)

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
        job_id=rq_job_id or f"{job_type}_{job_id}",
        meta=job_meta,
        at_front=at_front,
        depends_on=depends_on,
        job_timeout=timeout,
        result_ttl=86400,  # Keep result for 24 hours
        failure_ttl=86400,  # Keep failed job info for 24 hours
    )

    logger.info(f"Enqueued {job_type} job {job_id} with RQ ID: {rq_job.id} (timeout: {timeout}s)")

    return rq_job.id


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
    queue_batch_size = int(kwargs.pop("queue_batch_size", PEAKINDEXING_QUEUE_BATCH_SIZE))
    queue_batch_size = max(1, queue_batch_size)

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

    if len(input_files) != len(subjob_data):
        raise ValueError(
            f"Number of input files ({len(input_files)}) does not match number of subjobs ({len(subjob_data)})"
        )
    if len(output_files) != len(subjob_data):
        raise ValueError(
            f"Number of output files ({len(output_files)}) does not match number of subjobs ({len(subjob_data)})"
        )

    output_dir = output_files[0] if output_files else ""
    subjob_specs = [
        {"subjob_id": subjob.subjob_id, "input_file": input_files[i], "output_file": output_files[i]}
        for i, subjob in enumerate(subjob_data)
    ]
    chunks = list(_chunked(subjob_specs, queue_batch_size))
    rq_job_ids = [f"peakindexing_batch_{job_id}_{chunk_index}" for chunk_index in range(len(chunks))]
    chunk_subjob_ids = [[spec["subjob_id"] for spec in chunk] for chunk in chunks]

    setup_batch_counter(
        job_id,
        len(subjob_data),
        "execute_peakindexing_batch_coordinator",
        coordinator_args=[output_dir, output_xml],
        job_type="peakindexing",
        queue_mode="chunked",
        rq_job_ids=rq_job_ids,
        chunk_subjob_ids=chunk_subjob_ids,
        chunk_size=queue_batch_size,
    )

    for chunk_index, chunk_specs in enumerate(chunks):
        enqueue_job(
            job_id,
            "peakindexing_batch",
            execute_peakindexing_chunk,
            at_front,
            None,
            db_schema.Job,
            chunk_specs,
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
            rq_job_id=rq_job_ids[chunk_index],
            **kwargs,
        )

    logger.info(
        "Enqueued peakindexing batch job %s with %s subjobs in %s chunk(s), output_xml=%s",
        job_id,
        len(subjob_data),
        len(chunks),
        output_xml,
    )
    return f"batch_{job_id}"
