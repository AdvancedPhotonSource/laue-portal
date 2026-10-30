"""One queued local live controller; workers return closed point/shard receipts.

The controller is the sole catalog/preview writer. Its durable checkpoint and
point ledger live in the portal's SSD database; child receipts are fsynced before
completion is reported. An uncertain dispatched task is never blindly retried.
"""

from __future__ import annotations

import json
import logging
import multiprocessing
import signal
import threading
import time
from concurrent.futures import ProcessPoolExecutor
from contextlib import ExitStack
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from lauelab.indexing import LaueError, merge_results_files, merge_xml_files, validate_results_file
from lauelab.reconstruct import PointOutcome, PointReader, PointTask, PreparedScan, prepare_scan, reconstruct_point
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from laue_portal.database import db_schema as db
from laue_portal.database import session_utils
from laue_portal.processing.compute import RunOutcome, RunRequest
from laue_portal.processing.compute.lauego import compute_lauego_indexing
from laue_portal.processing.compute.wire import reconstructor_options, settings_from_request
from laue_portal.processing.live_arrivals import CatalogArrivals
from laue_portal.processing.live_indexing import index_raw_frame, validate_raw_receipt, write_raw_shard
from laue_portal.processing.queue.lifecycle import SHUTDOWN_SIGNAL
from laue_portal.utilities.srange import srange
from laue_portal.workflows import execution
from laue_portal.workflows.live import get_live, live_counts, source_identity, writer_lock
from laue_portal.workflows.manifest import ManifestEntry, write_json_file
from laue_portal.workflows.publication import partial_path, publish_file


def _receipt_path(directory, point_id, stage):
    return Path(directory) / f"{stage}-{point_id}.json"


def reconstruct_live_point(task, threads, receipt_path):
    outcome = reconstruct_point(PointTask(**task), num_threads=threads)
    receipt = asdict(outcome)
    write_json_file(receipt_path, receipt)
    return receipt


class PointHooks:
    """An admitted point's indexing drains to completion."""

    def __init__(self):
        self.failures = []

    def should_stop(self):
        return False

    def report_progress(self, **counts):
        pass

    def record_failure(self, record):
        self.failures.append(asdict(record))

    def report_outcome(self, outcome):
        pass

    def log(self, message):
        pass


def index_live_point(recipe, point_id, task, receipt_path):
    parameters = recipe["indexing"]
    with PointReader(task["output"]) as point:
        depths = list(range(point.shape[0]))
        if parameters.get("depth_range"):
            from laue_portal.workflows.files import normalize_integer_range

            _, selected = normalize_integer_range(parameters["depth_range"], "depth range")
            if not set(selected) <= set(depths):
                raise ValueError("Selected indexing depth is outside the reconstructed point")
            depths = list(selected)
    entries = [
        ManifestEntry(
            index=n,
            input_id=f"{task['point_id']}_{depth}",
            source=task["output"],
            template_index=0,
            scan_point=None,
            depth_point=depth,
            point_id=task["point_id"],
            depth_index=depth,
        )
        for n, depth in enumerate(depths)
    ]
    output = str(Path(recipe["indexing_directory"]) / "shards" / str(point_id))
    request = RunRequest(
        job_id=0,
        kind="lauego_indexing",
        display_id="Live point indexing",
        run_directory=output,
        manifest_path="",
        document={"request": parameters, "output": {"xml": "output.xml"}},
        n_inputs=len(entries),
        workers=recipe["policy"]["indexing_workers"],
        max_in_flight=None,
    )
    hooks = PointHooks()
    outcome = compute_lauego_indexing(request, entries, hooks)
    if outcome.validation_error:
        raise ValueError(outcome.validation_error)
    receipt = {
        "outcome": asdict(outcome),
        "n_inputs": len(entries),
        "point_id": task["point_id"],
        "failures": hooks.failures,
        "frame_ids": [],
    }
    if outcome.artifacts.get("results"):
        receipt["frame_ids"] = list(validate_results_file(outcome.artifacts["results"]).frame_ids)
    write_json_file(receipt_path, receipt)
    return receipt


def _points(engine, session_id, *, pending=False):
    with Session(engine) as session:
        query = select(db.LivePoint).where(db.LivePoint.session_id == session_id)
        if pending:
            query = query.where(
                or_(
                    db.LivePoint.reconstruction_state.in_(("ready", "pending", "writing")),
                    db.LivePoint.indexing_state.in_(("pending", "writing")),
                )
            )
        return session.scalars(query.order_by(db.LivePoint.id)).all()


def _save_checkpoint(engine, session_id, scan):
    with Session(engine) as session, session.begin():
        session.merge(db.LiveCheckpoint(session_id=session_id, state=scan.export_state()))


def _validate_index_receipt(receipt, point, recipe):
    if not recipe["reconstruction"]:
        return validate_raw_receipt(receipt, point, recipe)
    if receipt["point_id"] != point.point_id:
        raise ValueError("Indexing receipt belongs to a different point")
    outcome = RunOutcome(**receipt["outcome"])
    if outcome.n_succeeded + outcome.n_failed != receipt["n_inputs"] or outcome.validation_error:
        raise ValueError("Indexing receipt has inconsistent counters")
    expected = Path(recipe["indexing_directory"]) / "shards" / str(point.id) / "output.h5"
    if outcome.n_succeeded:
        if outcome.artifacts.get("results") != str(expected):
            raise ValueError("Indexing receipt refers to a different shard")
        summary = validate_results_file(expected, frame_ids=receipt["frame_ids"])
        if summary.n_frames != outcome.n_succeeded:
            raise ValueError("Indexing receipt frame count differs from its shard")
    return outcome


def _recover(engine, live):
    """Import durable receipts before restoring; preserve unknown outputs/partials."""
    points = _points(engine, live.id)
    receipts = []
    with Session(engine) as session, session.begin():
        for point in points:
            row = session.get(db.LivePoint, point.id)
            for stage, field in (("r", "reconstruction_receipt"), ("i", "indexing_receipt")):
                path = _receipt_path(live.control_directory, point.id, stage)
                saved = getattr(row, field)
                if path.exists():
                    receipt = json.loads(path.read_text())
                    if saved is not None and receipt != saved:
                        raise ValueError("A durable worker receipt conflicts with the ledger")
                    setattr(row, field, receipt)
                else:
                    receipt = saved
                if receipt is None:
                    if getattr(row, "reconstruction_state" if stage == "r" else "indexing_state") == "writing":
                        raise ValueError(
                            f"Point {point.point_id}: {stage} dispatch has no receipt; reconcile its worker/output before resuming"
                        )
                    continue
                if stage == "r":
                    if row.task is None:
                        raise ValueError("Reconstruction receipt has no registered task")
                    outcome = PointOutcome(**receipt)
                    receipts.append(outcome)
                    row.reconstruction_state = outcome.status
                    if outcome.error:
                        row.error = outcome.error
                        row.indexing_state = "unattempted"
                else:
                    outcome = _validate_index_receipt(receipt, point, live.recipe)
                    row.indexing_state = "complete" if not outcome.n_failed else "failed"
                    row.indexing_succeeded, row.indexing_failed = outcome.n_succeeded, outcome.n_failed
                    row.indexed_frames = outcome.n_indexed or 0
                    if outcome.n_failed:
                        row.error = f"{outcome.n_failed} indexing frames failed"
    if not live.reconstruction_id:
        return None
    if live.checkpoint is not None:
        return PreparedScan.restore(live.checkpoint, outcomes=receipts)
    output = Path(live.recipe["reconstruction_directory"]) / "reconstruction"
    settings = settings_from_request(live.recipe["reconstruction"])
    scan = prepare_scan([], output, geometry=settings.geometry_file, detector=0, **reconstructor_options(settings))
    _save_checkpoint(engine, live.id, scan)
    return scan


def _update(engine, live, *, published=False, state=None):
    counts = live_counts(live.id, engine=engine)
    with Session(engine) as session, session.begin():
        row = session.get(db.LiveSession, live.id)
        row.heartbeat_at = datetime.now()
        if state:
            row.state = state
        if published:
            row.revision += 1
            row.published_at = datetime.now()
        primary = session.get(db.Job, row.reconstruction_job_id or row.indexing_job_id)
        if primary.n_inputs != counts["arrived"]:
            numbers = session.scalars(select(db.LivePoint.point_number).where(db.LivePoint.session_id == live.id)).all()
            selection = str(srange(",".join(map(str, sorted(numbers))))) if numbers else ""
            if row.reconstruction_id:
                params = session.get(db.WireReconstructionParameters, row.reconstruction_id)
                params.scan_points, params.scan_points_len = selection, len(numbers)
            if row.indexing_id:
                params = session.get(db.LaueGoIndexingParameters, row.indexing_id)
                params.scan_points, params.scan_points_len = selection, len(numbers)
        if row.reconstruction_job_id:
            rjob = primary
            rjob.n_inputs = counts["arrived"]
            rjob.n_succeeded = counts["reconstructed"]
            rjob.n_failed = counts["reconstruction_failed"]
            rjob.heartbeat_at = row.heartbeat_at
        if row.indexing_job_id:
            ijob = session.get(db.Job, row.indexing_job_id)
            ijob.n_inputs = counts["indexing_inputs"]
            ijob.n_succeeded = counts["indexing_succeeded"]
            ijob.n_failed = counts["indexing_failed"]
            ijob.heartbeat_at = row.heartbeat_at
            indexing = session.get(db.IndexingRun, row.indexing_id)
            indexing.n_frames_indexed = counts["indexed_frames"]


def _publish_index(engine, live, points, *, final=False):
    # Append-only publication order keeps existing viewer step indices stable
    # when reconstruction points finish out of registration order.
    ordered = sorted((p for p in points if p.indexing_receipt), key=lambda p: p.indexing_order)
    receipts = [p.indexing_receipt for p in ordered]
    paths = list(
        dict.fromkeys(
            r["outcome"]["artifacts"]["results"] for r in receipts if r["outcome"]["artifacts"].get("results")
        )
    )
    if not paths:
        return False
    output = Path(live.recipe["indexing_directory"])
    identities = [frame for r in receipts for frame in r["frame_ids"]]
    target = output / "output.h5"
    raw = not live.reconstruction_id
    if raw and target.exists():
        existing = validate_results_file(target).frame_ids
        if tuple(identities[: len(existing)]) != existing:
            raise ValueError("Published indexing frames disagree with the durable ledger")
        published_ids = set(existing)
        batches = {
            r["outcome"]["artifacts"]["results"]: set(r["batch_frame_ids"])
            for r in receipts
            if r["outcome"]["artifacts"].get("results")
        }
        pending = []
        for path in paths:
            overlap = batches[path] & published_ids
            if overlap and overlap != batches[path]:
                raise ValueError("Published indexing contains an incomplete batch")
            if not overlap:
                pending.append(path)
        if pending:
            merge_results_files([target, *pending], partial_path(target), frame_ids=identities, overwrite=True)
            publish_file(partial_path(target), target, overwrite=True)
    else:
        merge_results_files(paths, target, frame_ids=identities, overwrite=True)
    xml = list(
        dict.fromkeys(r["outcome"]["artifacts"]["xml"] for r in receipts if r["outcome"]["artifacts"].get("xml"))
    )
    if xml and (not raw or final):
        try:
            merge_xml_files(xml, output / (live.recipe["indexing"].get("output_xml") or "output.xml"), overwrite=True)
        except Exception:
            logging.getLogger(__name__).warning(
                "Live XML preview could not be merged; HDF5 remains authoritative", exc_info=True
            )
    with Session(engine) as session, session.begin():
        session.get(db.IndexingRun, live.indexing_id).results_path = str(output / "output.h5")
    return True


def _finalize(engine, live, state, error=None):
    _update(engine, live, published=True)
    with Session(engine) as session, session.begin():
        row = session.get(db.LiveSession, live.id)
        row.state, row.error = state, error
        if state != "recovery":
            row.active_slot = None
        status = {"finished": execution.JobStatus.FINISHED, "cancelled": execution.JobStatus.CANCELLED}.get(
            state, execution.JobStatus.FAILED
        )
        for job_id in (row.reconstruction_job_id, row.indexing_job_id):
            if job_id is None:
                continue
            job = session.get(db.Job, job_id)
            execution.finalize(
                job,
                status=status,
                message=error or f"Live session {row.id}: {state}; completed results kept",
                phase=execution.RunPhase.INTERRUPTED if state == "recovery" else None,
            )
            if job_id == row.indexing_job_id:
                artifacts = {"results": session.get(db.IndexingRun, row.indexing_id).results_path}
            else:
                artifacts = {"catalog": str(Path(live.recipe["reconstruction_directory"]) / "reconstruction/scan.h5")}
            write_json_file(
                Path(job.run_directory) / "run.json",
                {
                    "format": "laue-portal-run-summary",
                    "version": 1,
                    "job_id": job_id,
                    "kind": "wire_reconstruction" if job_id == row.reconstruction_job_id else "lauego_indexing",
                    "status": execution.STATUS_NAMES[status],
                    "phase": job.phase,
                    "message": job.messages,
                    "live_session_id": row.id,
                    "artifacts": {k: v for k, v in artifacts.items() if v},
                    "counters": {
                        "n_inputs": job.n_inputs,
                        "n_succeeded": job.n_succeeded,
                        "n_failed": job.n_failed,
                        "n_not_run": job.n_not_run,
                    },
                    "policy": live.recipe["policy"],
                },
                overwrite=True,
            )


def execute_live(session_id, *, engine=None, executor_factory=ProcessPoolExecutor, should_pause=None):
    """Run until Finish/Stop, or leave recoverable state after a service shutdown."""
    engine = engine or session_utils.get_engine()
    live = get_live(session_id, engine=engine)
    if live is None or live.state != "queued":
        return
    pause = threading.Event()
    prior = None
    in_main = threading.current_thread() is threading.main_thread()
    if in_main:
        prior = signal.signal(SHUTDOWN_SIGNAL, lambda *_: pause.set())
    policy = live.recipe["policy"]
    scan = None
    owned = False
    try:
        with writer_lock(live.control_directory):
            owned = True
            scan = _recover(engine, live)
            with Session(engine) as session, session.begin():
                row = session.get(db.LiveSession, live.id)
                row.state, row.error = "running", None
                for job_id in (row.reconstruction_job_id, row.indexing_job_id):
                    if job_id:
                        execution.mark_running(session.get(db.Job, job_id))
            _update(engine, live, published=True)
            context = multiprocessing.get_context("spawn")
            with ExitStack() as pools:
                arrivals = pools.enter_context(CatalogArrivals(live, engine))
                rp = (
                    pools.enter_context(
                        executor_factory(max_workers=policy["reconstruction_workers"], mp_context=context)
                    )
                    if scan
                    else None
                )
                ip = (
                    pools.enter_context(
                        executor_factory(max_workers=1 if scan else policy["indexing_workers"], mp_context=context)
                    )
                    if live.indexing_id
                    else None
                )
                running_r, running_i = {}, {}
                published_index_count = -1
                next_publish = 0
                catalog_mtime = scan.path.stat().st_mtime_ns if scan else None
                raw_parameters = json.dumps(live.recipe["indexing"], sort_keys=True)
                raw_completed = []
                next_raw_flush = time.monotonic() + min(1.0, policy["publish_seconds"])
                while True:
                    live = get_live(session_id, engine=engine, with_checkpoint=False)
                    paused = pause.is_set() or bool(should_pause and should_pause())
                    stopping = paused  # Service shutdown pauses dispatch; user Stop drains accepted work.
                    arrivals.poll(accepting=not (paused or live.action))
                    reconstructed_now = False
                    for futures, stage in ((running_r, "r"), (running_i, "i")):
                        for future, point_id in list(futures.items()):
                            if not future.done():
                                continue
                            receipt = future.result()  # A missing receipt/shared failure requires reconciliation.
                            with Session(engine, expire_on_commit=False) as session, session.begin():
                                point = session.get(db.LivePoint, point_id)
                                if stage == "r":
                                    point.reconstruction_receipt = receipt
                                    point.reconstruction_state = receipt["status"]
                                    if receipt.get("error"):
                                        point.error, point.indexing_state = receipt["error"], "unattempted"
                                elif scan is None:
                                    raw_completed.append((point, receipt))
                                else:
                                    outcome = _validate_index_receipt(receipt, point, live.recipe)
                                    point.indexing_receipt = receipt
                                    point.indexing_state = "complete" if not outcome.n_failed else "failed"
                                    point.indexing_succeeded, point.indexing_failed = (
                                        outcome.n_succeeded,
                                        outcome.n_failed,
                                    )
                                    point.indexed_frames = outcome.n_indexed or 0
                                    if outcome.n_failed:
                                        point.error = f"{outcome.n_failed} indexing frames failed"
                            if stage == "r":
                                scan.record(PointOutcome(**receipt))
                                reconstructed_now = True
                            del futures[future]
                    if raw_completed and (
                        len(raw_completed) >= policy["indexing_workers"]
                        or time.monotonic() >= next_raw_flush
                        or live.action
                        or paused
                    ):
                        receipts = write_raw_shard(live, raw_completed)
                        with Session(engine) as session, session.begin():
                            previous = session.scalar(
                                select(func.max(db.LivePoint.indexing_order)).where(db.LivePoint.session_id == live.id)
                            )
                            order = (previous if previous is not None else -1) + 1
                            for point, receipt in receipts:
                                row = session.get(db.LivePoint, point.id)
                                outcome = RunOutcome(**receipt["outcome"])
                                row.indexing_receipt, row.indexing_order = receipt, order
                                row.indexing_state = "failed" if outcome.n_failed else "complete"
                                row.indexing_succeeded, row.indexing_failed = outcome.n_succeeded, outcome.n_failed
                                row.indexed_frames, row.error = outcome.n_indexed or 0, receipt["error"]
                                order += 1
                        raw_completed.clear()
                        next_raw_flush = time.monotonic() + min(1.0, policy["publish_seconds"])
                    points = _points(engine, session_id, pending=True)
                    if reconstructed_now:
                        scan.snapshot(force=True)  # Publish validated points before enabling their indexing.
                    if not stopping:
                        for point in points if scan else []:
                            if len(running_r) >= policy["reconstruction_workers"]:
                                break
                            if point.reconstruction_state not in {"ready", "pending"}:
                                continue
                            if point.task is None:
                                try:
                                    if source_identity(point.source) != point.source_identity:
                                        raise ValueError("Input changed after its completed-stack notification")
                                    task = scan.add(point.source, point_id=point.point_id)
                                except (LaueError, ValueError, OSError) as error:
                                    with Session(engine) as session, session.begin():
                                        row = session.get(db.LivePoint, point.id)
                                        row.reconstruction_state, row.indexing_state, row.error = (
                                            "failed",
                                            "unattempted",
                                            str(error),
                                        )
                                    continue
                                with Session(engine) as session, session.begin():
                                    row = session.get(db.LivePoint, point.id)
                                    row.task = asdict(task)
                                    if live.indexing_id:
                                        from laue_portal.workflows.files import normalize_integer_range

                                        selected = live.recipe["indexing"].get("depth_range")
                                        row.indexing_inputs = (
                                            len(normalize_integer_range(selected, "depth range")[1])
                                            if selected
                                            else task.n_depths
                                        )
                                    session.merge(db.LiveCheckpoint(session_id=live.id, state=scan.export_state()))
                            else:
                                task = PointTask(**point.task)
                            with Session(engine) as session, session.begin():
                                session.get(db.LivePoint, point.id).reconstruction_state = "writing"
                            scan.record_dispatch(task)
                            future = rp.submit(
                                reconstruct_live_point,
                                asdict(task),
                                policy["threads_per_worker"],
                                str(_receipt_path(live.control_directory, point.id, "r")),
                            )
                            running_r[future] = point.id
                        if ip is not None and scan is None:
                            for point in points:
                                if len(running_i) >= policy["indexing_workers"]:
                                    break
                                if point.indexing_state != "pending":
                                    continue
                                with Session(engine) as session, session.begin():
                                    session.get(db.LivePoint, point.id).indexing_state = "writing"
                                future = ip.submit(index_raw_frame, raw_parameters, point.source, point.source_identity)
                                running_i[future] = point.id
                        if scan is not None and live.indexing_id and not running_i:
                            point = next(
                                (
                                    p
                                    for p in _points(engine, session_id, pending=True)
                                    if p.reconstruction_state == "complete" and p.indexing_state == "pending"
                                ),
                                None,
                            )
                            if point:
                                with Session(engine) as session, session.begin():
                                    session.get(db.LivePoint, point.id).indexing_state = "writing"
                                    previous = session.scalar(
                                        select(func.max(db.LivePoint.indexing_order)).where(
                                            db.LivePoint.session_id == live.id
                                        )
                                    )
                                    session.get(db.LivePoint, point.id).indexing_order = (
                                        previous if previous is not None else -1
                                    ) + 1
                                future = ip.submit(
                                    index_live_point,
                                    live.recipe,
                                    point.id,
                                    point.task,
                                    str(_receipt_path(live.control_directory, point.id, "i")),
                                )
                                running_i[future] = point.id
                    points = _points(engine, session_id, pending=True)
                    unsettled = any(
                        p.reconstruction_state in {"ready", "pending", "writing"}
                        or (
                            live.indexing_id
                            and (scan is None or p.reconstruction_state == "complete")
                            and p.indexing_state in {"pending", "writing"}
                        )
                        for p in points
                    )
                    draining = live.action is not None or paused
                    done = draining and not running_r and not running_i and (stopping or not unsettled)
                    published = scan.snapshot() if scan else False
                    current_mtime = scan.path.stat().st_mtime_ns if scan else None
                    published = published or current_mtime != catalog_mtime
                    catalog_mtime = current_mtime
                    count = live_counts(live.id, engine=engine)["index_receipts"]
                    if (
                        live.indexing_id
                        and count != published_index_count
                        and (done or time.monotonic() >= next_publish)
                    ):
                        started = time.monotonic()
                        published = _publish_index(engine, live, _points(engine, session_id)) or published
                        # Keep repeated preview stitching below roughly 10% wall time.
                        next_publish = time.monotonic() + max(
                            policy["publish_seconds"], (time.monotonic() - started) * 9
                        )
                        published_index_count = count
                    state = "stopping" if stopping or live.action else "running" if unsettled else "waiting"
                    _update(engine, live, published=published, state=state)
                    if done:
                        break
                    time.sleep(policy["poll_seconds"])
            if paused:
                if scan:
                    _save_checkpoint(engine, live.id, scan)
                    scan.snapshot(force=True)
                _finalize(
                    engine, live, "recovery", "Live service stopped; completed receipts kept. Resume to continue."
                )
                return
            points = _points(engine, session_id)
            if scan is None:
                _publish_index(engine, live, points, final=True)
            errors = sum(bool(p.error) for p in points)
            if errors:
                if scan:
                    scan.close()
                _finalize(
                    engine,
                    live,
                    "failed",
                    f"Live processing failed for {errors} point(s)",
                )
            elif not points:
                if scan:
                    scan.finish(cancelled=True)
                _finalize(engine, live, "cancelled")
            else:
                if scan:
                    scan.finish()
                _finalize(engine, live, "finished")
    except BaseException as error:
        if owned:
            _finalize(engine, live, "recovery", f"{type(error).__name__}: {error}")
        raise
    finally:
        if in_main:
            signal.signal(SHUTDOWN_SIGNAL, prior)


def abandon_interrupted_live(session_id, *, engine=None):
    """Release an interrupted session without touching its scientific files."""
    engine = engine or session_utils.get_engine()
    live = get_live(session_id, engine=engine)
    with writer_lock(live.control_directory):
        with Session(engine) as session, session.begin():
            row = session.get(db.LiveSession, session_id)
            if row.state != "recovery":
                raise ValueError("Only an interrupted session can be abandoned")
            for job_id in (row.reconstruction_job_id, row.indexing_job_id):
                if job_id:
                    job = session.get(db.Job, job_id)
                    job.status, job.phase, job.n_not_run = 1, "running", 0
        _finalize(
            engine, live, "cancelled", "Stopped during recovery; existing partial snapshots and diagnostics retained"
        )
