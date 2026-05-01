"""RQ worker execution functions for Laue processing jobs."""

import logging
import time
from datetime import datetime
from typing import Any, Dict, List

from laueanalysis.indexing import index
from laueanalysis.reconstruct import reconstruct as wire_reconstruct
from sqlalchemy.orm import Session

import laue_portal.database.session_utils as session_utils
from laue_portal.database import db_schema
from laue_portal.processing.queue.batch import notify_subjobs_completed
from laue_portal.processing.queue.core import STATUS_REVERSE_MAPPING, WRITE_SUCCESS_SUBJOB_DETAILS
from laue_portal.processing.queue.lifecycle import execute_with_status_updates, publish_job_update

logger = logging.getLogger(__name__)


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


def execute_peakindexing_chunk(
    job_id: int,
    chunk_specs: List[Dict[str, Any]],
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
    """Execute a chunk of peak indexing subjobs with coalesced DB writes."""
    if not chunk_specs:
        return []

    chunk_start_time = datetime.now()
    with Session(session_utils.get_engine()) as session:
        job_data = session.query(db_schema.Job).filter(db_schema.Job.job_id == job_id).first()
        if job_data and job_data.status in [
            STATUS_REVERSE_MAPPING["Finished"],
            STATUS_REVERSE_MAPPING["Failed"],
            STATUS_REVERSE_MAPPING["Cancelled"],
        ]:
            logger.info(f"Skipping peakindexing chunk for terminal job {job_id}")
            return []
        if job_data and job_data.status == STATUS_REVERSE_MAPPING["Queued"]:
            job_data.status = STATUS_REVERSE_MAPPING["Running"]
            job_data.start_time = chunk_start_time
            session.commit()

    results = []
    for spec in chunk_specs:
        subjob_id = spec["subjob_id"]
        input_file = spec["input_file"]
        output_dir = spec["output_file"]
        try:
            index_result = index(
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

            update = {
                "subjob_id": subjob_id,
                "status": STATUS_REVERSE_MAPPING["Finished"],
                "start_time": chunk_start_time,
                "finish_time": datetime.now(),
            }
            if WRITE_SUCCESS_SUBJOB_DETAILS:
                if hasattr(index_result, "command_history") and index_result.command_history:
                    update["command"] = "\n".join(index_result.command_history)
                update["messages"] = str(index_result)
            results.append(update)
        except Exception as e:
            logger.exception(f"Peakindexing subjob {subjob_id} failed inside chunk for job {job_id}")
            results.append(
                {
                    "subjob_id": subjob_id,
                    "status": STATUS_REVERSE_MAPPING["Failed"],
                    "start_time": chunk_start_time,
                    "finish_time": datetime.now(),
                    "messages": f"Error: {str(e)}",
                }
            )

    with Session(session_utils.get_engine()) as session:
        session.bulk_update_mappings(db_schema.SubJob, results)
        session.commit()

    notify_subjobs_completed(job_id, len(results))
    publish_job_update(job_id, "running", f"Peakindexing chunk completed {len(results)} subjob(s)")
    return results


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
