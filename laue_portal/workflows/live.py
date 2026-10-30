"""Live run creation, closed-stack arrivals, and durable session controls.

Arrival notifications are explicit assertions of detector/transfer completion.
No directory watcher or quiet-period heuristic declares an input ready.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import shutil
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from sqlalchemy import case, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from laue_portal import config
from laue_portal.database import db_schema as db
from laue_portal.database import session_utils
from laue_portal.utilities.filename_patterns import compile_filename_templates
from laue_portal.workflows import execution
from laue_portal.workflows.files import format_output_path
from laue_portal.workflows.manifest import write_json_file
from laue_portal.workflows.run_records import new_job, request_document

TERMINAL = frozenset({"finished", "failed", "cancelled"})


def _engine(engine):
    return engine or session_utils.get_engine()


def _document(request):
    return json.loads(json.dumps(request_document(request), default=lambda value: value.isoformat(), allow_nan=False))


def source_identity(path):
    status = Path(path).stat()
    return {"size": status.st_size, "mtime_ns": status.st_mtime_ns, "inode": status.st_ino, "device": status.st_dev}


@contextmanager
def writer_lock(directory):
    """OS-owned lock, released after a crash; never steal a living writer's lease."""
    with open(Path(directory) / "writer.lock", "a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("The live controller is still running") from error
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def get_live(session_id=None, *, engine=None, with_checkpoint=True):
    with Session(_engine(engine)) as session:
        query = select(db.LiveSession)
        query = query.where(db.LiveSession.id == session_id) if session_id else query.order_by(db.LiveSession.id.desc())
        live = session.scalars(query).first()
        if live is not None and with_checkpoint:
            checkpoint = session.get(db.LiveCheckpoint, live.id)
            live.checkpoint = checkpoint.state if checkpoint else None
        return live


def live_for_job(job_id, *, engine=None):
    with Session(_engine(engine)) as session:
        return session.scalar(
            select(db.LiveSession).where(
                or_(db.LiveSession.reconstruction_job_id == job_id, db.LiveSession.indexing_job_id == job_id)
            )
        )


def create_live(reconstruction=None, indexing=None, *, engine=None, control_root=None, policy=None, arrivals=None):
    """Create ordinary R/I jobs and one active live reservation without resolving future files.

    Matching completed-stack notifications define the input set. Stop seals
    arrivals and drains every accepted point; there is no expected upper bound.
    """
    from lauelab.reconstruct import PreparedScan, Reconstructor

    if reconstruction and not all(
        hasattr(PreparedScan, name) for name in ("add", "outcomes", "export_state", "restore")
    ):
        raise ValueError("Install lauelab with incremental PreparedScan support in the portal and worker environments")

    from laue_portal.processing.compute.lauego import build_indexer
    from laue_portal.processing.compute.lauego import settings_from_request as indexing_settings
    from laue_portal.processing.compute.wire import reconstructor_options
    from laue_portal.processing.compute.wire import settings_from_request as wire_settings

    engine = _engine(engine)
    source_request = reconstruction or indexing
    if source_request is None:
        raise ValueError("Enable reconstruction, indexing, or both")
    if any(request.backend != "local" for request in (reconstruction, indexing) if request):
        raise ValueError("Live processing currently runs on APS")
    if len(source_request.filename_prefixes) != 1 or source_request.filename_prefixes[0].count("%d") != 1:
        raise ValueError("Live input requires one filename template with one %d point index")
    root = Path(source_request.input_path).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("The input folder must exist")
    if arrivals and (arrivals.get("kind") != "dm_catalog" or arrivals.get("input_directory") != str(root)):
        raise ValueError("DAQ binding does not match the live input folder")
    if reconstruction and indexing and indexing.scan_number != reconstruction.scan_number:
        raise ValueError("Reconstruction and indexing must belong to the same scan")
    if not reconstruction and indexing.depth_values:
        raise ValueError("Depth indices apply only to reconstructed points")
    r = _document(reconstruction) if reconstruction else None
    i = _document(indexing) if indexing else None
    # Live metadata tracks actual arrivals, including when an older caller
    # supplies a batch-style point selection. It never reserves future points.
    if r:
        r["scan_points"] = ""
    if i:
        i["scan_points"] = ""
    limits = {
        "reconstruction_workers": 2 if i else 3,
        "threads_per_worker": 8,
        "indexing_workers": 8 if r else 24,
        "poll_seconds": 0.25,
        "publish_seconds": 5.0 if r else 2.0,
    }
    limits.update(policy or {})
    if any(
        type(limits[key]) is not int or limits[key] < 1
        for key in ("reconstruction_workers", "threads_per_worker", "indexing_workers")
    ):
        raise ValueError("Live worker/thread counts must be positive integers")
    cores = limits["reconstruction_workers"] * limits["threads_per_worker"] if r else 0
    if cores + (limits["indexing_workers"] if i else 0) > 24:
        raise ValueError("Live processing must fit the shared 24-core APS budget")
    if limits["poll_seconds"] <= 0 or limits["publish_seconds"] <= 0:
        raise ValueError("Live polling/publication intervals must be positive")
    if r:
        settings = wire_settings(r)
        Reconstructor(settings.geometry_file, 0, num_threads=1, **reconstructor_options(settings))
    if i:
        build_indexer(indexing_settings(i))
        if i.get("output_xml") and Path(i["output_xml"]).name != i["output_xml"]:
            raise ValueError("Live XML output must be a filename inside the indexing run")
    control_root = Path(control_root or Path(config.db_file).resolve().parent / "live")
    directory = control_root / uuid.uuid4().hex
    moment = datetime.now()
    try:
        with Session(engine, expire_on_commit=False) as session, session.begin():
            run = rjob = None
            if r:
                rjob = new_job(
                    computer_name=reconstruction.computer_name,
                    priority=reconstruction.priority,
                    submitted_at=moment,
                    n_inputs=0,
                )
                session.add(rjob)
                session.flush()
                run = db.ReconstructionRun(
                    scan_number=reconstruction.scan_number,
                    job=rjob,
                    method="wire",
                    input_path=str(root),
                    author=reconstruction.author,
                    notes=reconstruction.notes,
                    created_at=moment,
                    algorithm_version=reconstruction.algorithm_version,
                )
                session.add(run)
                session.flush()
                run.output_path = format_output_path(reconstruction.output_path_template, run.id)
                values = {
                    column.name: r[column.name]
                    for column in db.WireReconstructionParameters.__table__.columns
                    if column.name not in ("reconstruction_id", "scan_points_len")
                }
                run.wire_parameters = db.WireReconstructionParameters(**values, scan_points_len=0)
            irun = ijob = None
            if i:
                ijob = new_job(
                    computer_name=indexing.computer_name, priority=indexing.priority, submitted_at=moment, n_inputs=0
                )
                session.add(ijob)
                session.flush()
                irun = db.IndexingRun(
                    scan_number=source_request.scan_number,
                    reconstruction=run,
                    job=ijob,
                    method="lauego",
                    input_path=run.output_path if run else str(root),
                    author=indexing.author,
                    notes=indexing.notes,
                    created_at=moment,
                    algorithm_version=indexing.algorithm_version,
                    n_frames_indexed=0,
                )
                session.add(irun)
                session.flush()
                irun.output_path = format_output_path(indexing.output_path_template, irun.id)
                values = {
                    column.name: i[column.name]
                    for column in db.LaueGoIndexingParameters.__table__.columns
                    if column.name not in ("indexing_id", "scan_points_len", "depth_range_len")
                }
                irun.lauego_parameters = db.LaueGoIndexingParameters(
                    **values,
                    scan_points_len=0,
                    depth_range_len=len(indexing.depth_values) if indexing.depth_values is not None else None,
                )
            live = db.LiveSession(
                active_slot=1,
                reconstruction_id=run.id if run else None,
                indexing_id=irun.id if irun else None,
                reconstruction_job_id=rjob.job_id if rjob else None,
                indexing_job_id=ijob.job_id if ijob else None,
                state="queued",
                control_directory=str(directory),
                created_at=moment,
                revision=0,
                recipe={},
            )
            session.add(live)
            session.flush()  # Reserve the singleton before creating files.
            directory.mkdir(parents=True, exist_ok=False)
            frozen = {}
            for name, parameters in (("reconstruction", r), ("indexing", i)):
                if parameters is None:
                    continue
                for field in ("geometry_file", "crystal_file", "mask_file"):
                    if not parameters.get(field):
                        continue
                    original = Path(parameters[field]).resolve(strict=True)
                    destination = directory / f"{name}-{field}{original.suffix}"
                    shutil.copyfile(original, destination)
                    frozen[f"{name}.{field}"] = {
                        "source": str(original),
                        "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
                    }
                    parameters[field] = str(destination)
            recipe = {
                "reconstruction": r,
                "indexing": i,
                "policy": limits,
                "input_directory": str(root),
                "reconstruction_directory": run.output_path if run else None,
                "indexing_directory": irun.output_path if irun else None,
                "calibrations": frozen,
                "arrivals": arrivals,
            }
            live.recipe = recipe
            for job, output in ((rjob, run.output_path if run else None), (ijob, irun.output_path if irun else None)):
                if job is None:
                    continue
                Path(output).mkdir(parents=True, exist_ok=False)
                job.run_directory = output
                job.request_path = str(directory / "request.json")
                job.phase = execution.RunPhase.QUEUED
                job.queue_job_id = f"live_{live.id}"
            write_json_file(directory / "request.json", recipe)
            return live
    except IntegrityError as error:
        raise ValueError("Another live session is active; stop it first") from error


def notify_ready(session_id, path, *, complete=False, engine=None):
    """Persist one closed-stack arrival. Replays are idempotent, changed files are refused."""
    if not complete:
        raise ValueError("A completed-stack/transfer signal is required; file stability alone is insufficient")
    engine = _engine(engine)
    source = Path(path).resolve(strict=True)
    identity = source_identity(source)
    with Session(engine, expire_on_commit=False) as session, session.begin():
        # This write serializes admission with Stop before reading session state.
        session.execute(update(db.LiveSession).where(db.LiveSession.id == session_id).values(id=db.LiveSession.id))
        live = session.get(db.LiveSession, session_id)
        if live is None:
            raise ValueError("Live session does not exist")
        existing = session.scalar(
            select(db.LivePoint).where(db.LivePoint.session_id == session_id, db.LivePoint.source == str(source))
        )
        if existing:
            if existing.source_identity != identity:
                raise ValueError("A previously accepted input changed")
            return existing.id
        if live.action or live.state in TERMINAL:
            raise ValueError("Live arrivals have been sealed")
        if source.parent != Path(live.recipe["input_directory"]):
            raise ValueError("The ready input must be directly inside the selected input folder")
        match = compile_filename_templates(
            (live.recipe["reconstruction"] or live.recipe["indexing"])["filename_prefixes"]
        ).match(source.name)
        if match is None or len(match.indices) != 1:
            raise ValueError("Input does not match the selected filename")
        point = db.LivePoint(
            session_id=session_id,
            point_number=match.indices[0],
            point_id=source.stem,
            source=str(source),
            source_identity=identity,
            arrived_at=datetime.now(),
            reconstruction_state="ready" if live.reconstruction_id else "disabled",
            indexing_inputs=0 if live.reconstruction_id else 1,
            indexing_state="pending" if live.indexing_id else "disabled",
        )
        session.add(point)
        session.flush()
        return point.id


def request_action(session_id, action, *, engine=None):
    # Preserve older hook callers; both names now mean a graceful Stop.
    if action == "finish":
        action = "stop"
    if action != "stop":
        raise ValueError("Action must be stop")
    engine = _engine(engine)
    current = get_live(session_id, engine=engine)
    if action == "stop" and current is not None and current.state == "recovery":
        from laue_portal.processing.live import abandon_interrupted_live

        abandon_interrupted_live(session_id, engine=engine)
        return
    with Session(engine) as session, session.begin():
        session.execute(update(db.LiveSession).where(db.LiveSession.id == session_id).values(id=db.LiveSession.id))
        live = session.get(db.LiveSession, session_id)
        if live is None:
            raise ValueError("Live session does not exist")
        if live.state in TERMINAL:
            return
        if live.action != "stop":
            live.action = action


def live_counts(session_id, *, engine=None):
    """Aggregate lightweight progress without loading tasks, receipts, or pixels."""
    p = db.LivePoint
    counters = {
        "arrived": func.count(p.id),
        "reconstructed": func.sum(case((p.reconstruction_state == "complete", 1), else_=0)),
        "reconstruction_failed": func.sum(case((p.reconstruction_state == "failed", 1), else_=0)),
        "indexed_points": func.sum(case((p.indexing_state == "complete", 1), else_=0)),
        "failures": func.sum(case((p.error.is_not(None), 1), else_=0)),
        "pending": func.sum(
            case(
                (
                    or_(
                        p.reconstruction_state.in_(("ready", "pending", "writing")),
                        p.indexing_state.in_(("pending", "writing")),
                    ),
                    1,
                ),
                else_=0,
            )
        ),
        "indexing_inputs": func.sum(p.indexing_inputs),
        "indexing_succeeded": func.sum(p.indexing_succeeded),
        "indexing_failed": func.sum(p.indexing_failed),
        "indexed_frames": func.sum(p.indexed_frames),
        "index_receipts": func.sum(case((p.indexing_state.in_(("complete", "failed")), 1), else_=0)),
    }
    with Session(_engine(engine)) as session:
        row = session.execute(
            select(*(value.label(name) for name, value in counters.items())).where(p.session_id == session_id)
        ).one()
    return {key: value or 0 for key, value in row._mapping.items()}


def session_status(session_id=None, *, engine=None):
    engine = _engine(engine)
    live = get_live(session_id, engine=engine, with_checkpoint=False)
    if live is None:
        return None
    arrival_status = None
    if live.recipe.get("arrivals"):
        path = Path(live.control_directory) / "arrival-status.json"
        try:
            if path.stat().st_size < 16384:
                arrival_status = json.loads(path.read_text())
        except (OSError, ValueError):
            pass
    return {
        "id": live.id,
        "state": live.state,
        "action": live.action,
        "error": live.error,
        "revision": live.revision,
        "published_at": live.published_at.isoformat() if live.published_at else None,
        "reconstruction_id": live.reconstruction_id,
        "indexing_id": live.indexing_id,
        "reconstruction_job_id": live.reconstruction_job_id,
        "indexing_job_id": live.indexing_job_id,
        "arrival_status": arrival_status,
        **live_counts(live.id, engine=engine),
    }
