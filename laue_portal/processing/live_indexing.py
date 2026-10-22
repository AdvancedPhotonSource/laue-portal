"""Raw-frame tasks for the existing live controller and its persistent pool.

Workers return small, image-free results. The controller closes bounded shards
before recording durable receipts; it remains the only publisher.
"""

import json
import logging
import time
from dataclasses import asdict
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from lauelab.indexing import EXPECTED_INPUT_ERRORS, InputError, load_mask, validate_results_file

from laue_portal.processing.compute import RunOutcome
from laue_portal.processing.compute.lauego import build_indexer, settings_from_request
from laue_portal.workflows.live import source_identity
from laue_portal.workflows.manifest import write_json_file


@lru_cache(maxsize=1)
def raw_indexer(parameters):
    """Each pool process initializes native state once for the frozen recipe."""
    settings = settings_from_request(json.loads(parameters))
    return (
        build_indexer(settings),
        settings.depth_override,
        load_mask(settings.mask_file) if settings.mask_file else None,
    )


def index_raw_frame(parameters, source, identity):
    indexer, depth, mask = raw_indexer(parameters)
    started = time.monotonic()
    try:
        if source_identity(source) != identity:
            raise InputError("Input changed after its completed-file notification")
        result = indexer.index(source, depth=depth, mask=mask, keep_image=False)
        if source_identity(source) != identity:
            raise InputError("Input changed during indexing")
        return {
            "result": result,
            "error": None,
            "seconds": time.monotonic() - started,
            "processed_at": datetime.now().isoformat(),
        }
    except EXPECTED_INPUT_ERRORS as error:
        return {
            "result": None,
            "error": str(error),
            "seconds": time.monotonic() - started,
            "processed_at": datetime.now().isoformat(),
        }


def write_raw_shard(live, completed):
    """Persist a closed batch, then one recoverable receipt per admitted frame."""
    indexer, _, _ = raw_indexer(json.dumps(live.recipe["indexing"], sort_keys=True))
    batch_id = completed[0][0].id
    batch_points = [point.id for point, _ in completed]
    successes = [(point, item["result"]) for point, item in completed if item["result"] is not None]
    frame_ids = [point.point_id for point, _ in successes]
    artifacts = {}
    if successes:
        folder = Path(live.recipe["indexing_directory"]) / "shards" / f"batch_{batch_id}"
        folder.mkdir(parents=True, exist_ok=False)
        results = folder / "output.h5"
        indexer.write_results((result for _, result in successes), results, frame_ids=frame_ids)
        validate_results_file(results, frame_ids=frame_ids)
        artifacts["results"] = str(results)
        # XML is closed here but stitched only at Stop; live viewing uses HDF5.
        xml = folder / "output.xml"
        try:
            indexer.write_many_xml((result for _, result in successes), xml)
            artifacts["xml"] = str(xml)
        except Exception:
            logging.getLogger(__name__).warning("Live XML shard could not be written", exc_info=True)
    receipts = []
    for point, item in completed:
        success = item["result"] is not None
        outcome = RunOutcome(
            n_succeeded=int(success),
            n_failed=int(not success),
            n_indexed=int(success and item["result"].n_patterns > 0),
            artifacts=artifacts if success else {},
        )
        receipt = {
            "point_id": point.point_id,
            "n_inputs": 1,
            "frame_ids": [point.point_id] if success else [],
            "batch_id": batch_id,
            "batch_points": batch_points,
            "batch_frame_ids": frame_ids,
            "outcome": asdict(outcome),
            "error": item["error"],
            "seconds": item["seconds"],
            "processed_at": item["processed_at"],
        }
        write_json_file(Path(live.control_directory) / f"i-{point.id}.json", receipt)
        receipts.append((point, receipt))
    return receipts


def validate_raw_receipt(receipt, point, recipe):
    if receipt["point_id"] != point.point_id or point.id not in receipt["batch_points"]:
        raise ValueError("Raw indexing receipt belongs to a different input")
    outcome = RunOutcome(**receipt["outcome"])
    if receipt["n_inputs"] != 1 or outcome.n_processed != 1 or outcome.validation_error:
        raise ValueError("Raw indexing receipt has inconsistent counters")
    if outcome.n_succeeded:
        expected = Path(recipe["indexing_directory"]) / "shards" / f"batch_{receipt['batch_id']}" / "output.h5"
        if outcome.artifacts.get("results") != str(expected) or receipt["frame_ids"] != [point.point_id]:
            raise ValueError("Raw indexing receipt refers to a different shard or frame")
        if point.point_id not in receipt["batch_frame_ids"]:
            raise ValueError("Raw indexing frame is absent from its batch")
        validate_results_file(expected, frame_ids=receipt["batch_frame_ids"])
    return outcome
