"""Reconcile DM jobs and publish returned results into the portal database."""

from __future__ import annotations

import argparse
import html
import json
import logging
import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
from functools import partial
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from laue_portal.database import db_schema, session_utils
from laue_portal.processing.bdp.dm import DMClient, launcher_command
from laue_portal.processing.bdp.settings import child_path, map_path, portal_settings
from laue_portal.workflows import execution
from laue_portal.workflows.execution import JobStatus, RunPhase
from laue_portal.workflows.manifest import read_manifest, write_json_file

logger = logging.getLogger(__name__)


def _read(path):
    path = Path(path)
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError(f"Control document is too large: {path}")
    return json.loads(path.read_text())


def request_cancellation(job, settings, client):
    run = Path(job.run_directory)
    marker = run / ".cancel-sent"
    if marker.exists():
        return
    write_json_file(run / "cancel.request", {"requested_at": str(job.cancel_requested_at)}, overwrite=True)
    if settings["dm"].get("cancel_workflow"):
        pending = run / ".cancel-job.json"
        if not pending.exists():
            record = client.cancel(job.submission_id)
            write_json_file(pending, {"id": record["id"]})
        record = client.get(_read(pending)["id"])
        state = str(record["status"]).lower()
        if state in {"failed", "aborted"}:
            raise ValueError(f"DM cancellation job {record['id']} {state}; inspect its stage diagnostics")
        if state != "done":
            return
    else:
        subprocess.run(
            launcher_command(settings["dm"], "cancel", job.submission_id),
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    marker.touch()


def _restore_input_paths(path, plan, kind):
    """Make returned image references usable at APS; retain remote provenance."""
    inverse = {
        **{source: source for source in plan["path_map"]},
        **{destination: source for source, destination in plan["path_map"].items()},
    }
    if kind == "results":
        import h5py

        with h5py.File(path, "r+") as handle:
            images = handle["frames/input_images"]
            original = images.asstr()[:].tolist()
            restored = [map_path(value, inverse) for value in original]
            if restored != original:
                handle.require_group("provenance").create_dataset(
                    "remote_input_images", data=original, dtype=h5py.string_dtype()
                )
                images[:] = restored
    else:
        # The native XML writer puts each inputImage element on one line.
        # Stream it so restoring references does not load a full run's XML.
        pattern = re.compile(r"(<inputImage(?:\s[^>]*)?>)([^<]*)(</inputImage>)")

        def restore(match):
            try:
                value = map_path(html.unescape(match[2]), inverse)
            except ValueError:
                return match[0]
            return match[1] + html.escape(value, quote=False) + match[3]

        rewritten = path.with_name(path.name + ".xml")
        try:
            with path.open() as source, rewritten.open("x") as target:
                for line in source:
                    target.write(pattern.sub(restore, line))
            rewritten.chmod(0o660)
            rewritten.replace(path)
        finally:
            rewritten.unlink(missing_ok=True)


def _publish_returned_file(source, destination, transform=None):
    """Publish exclusively even when Globus files belong to another account."""
    if transform is None:
        try:
            os.link(source, destination)
        except PermissionError:
            pass
        else:
            source.unlink()
            return
    temporary = None
    try:
        # Protected hard links can reject a readable file owned by the mapped
        # Transfer user. Link an owned, complete copy instead; the destination
        # never exists partially and an existing destination is never replaced.
        with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".bdp-return-", delete=False) as handle:
            temporary = Path(handle.name)
            with source.open("rb") as incoming:
                shutil.copyfileobj(incoming, handle)
            os.fchmod(handle.fileno(), 0o660)
            handle.flush()
            os.fsync(handle.fileno())
        if transform:
            transform(temporary)
        os.link(temporary, destination)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
    source.unlink()


def publish_returned(plan):
    """Validate outputs before publication; repeated reconciliation is idempotent."""
    run = Path(plan["run_directory"])
    incoming = child_path(run / "incoming", plan.get("incoming_directory", plan["output_directory"]))
    summary = _read(incoming / "run.json")
    if not isinstance(summary, dict):
        raise ValueError("Returned summary must be a JSON object")
    if (summary.get("job_id"), summary.get("submission_id")) != (plan["job_id"], plan["submission_id"]):
        raise ValueError("Returned results belong to a different submission")
    if summary.get("kind") != plan["kind"]:
        raise ValueError("Returned analysis kind disagrees with the submission")
    counts = summary.get("counters")
    if not isinstance(counts, dict) or any(
        type(counts.get(key)) is not int for key in ("n_inputs", "n_succeeded", "n_failed", "n_not_run")
    ):
        raise ValueError("Returned counters must be integers")
    if counts["n_inputs"] != plan["n_inputs"] or any(counts[k] < 0 for k in ("n_succeeded", "n_failed", "n_not_run")):
        raise ValueError("Returned counters disagree with the submission")
    if sum(counts[k] for k in ("n_succeeded", "n_failed", "n_not_run")) != plan["n_inputs"]:
        raise ValueError("Returned counters do not sum to the manifest size")
    indexed = counts.get("n_indexed")
    if indexed is not None and (type(indexed) is not int or not 0 <= indexed <= counts["n_succeeded"]):
        raise ValueError("Returned indexing count is invalid")
    status = summary.get("status")
    if status not in {"Finished", "Failed", "Cancelled"}:
        raise ValueError(f"Invalid returned status: {status}")
    if status == "Finished" and (counts["n_succeeded"] != plan["n_inputs"] or summary.get("validation_error")):
        raise ValueError("Returned success contradicts its counters or output validation")
    if status == "Finished" and (incoming / "pbs.json").exists():
        if _read(incoming / "pbs.json").get("exit_status") not in (None, 0):
            raise ValueError("PBS reported a nonzero exit status after the runner finished")
    artifacts = summary.get("artifacts", {})
    if not isinstance(artifacts, dict) or any(not isinstance(path, str) for path in artifacts.values()):
        raise ValueError("Returned artifacts must map names to file paths")
    existing_summary = run / "run.json"
    if existing_summary.exists() and _read(existing_summary).get("submission_id") != plan["submission_id"]:
        raise FileExistsError(existing_summary)
    mapped = {}
    for name, path in artifacts.items():
        relative = child_path(plan["output_directory"], path).relative_to(Path(plan["output_directory"]).resolve())
        returned = child_path(incoming, incoming / relative)
        mapped[name] = str(run / relative)
        check = returned if returned.exists() else run / relative
        if name == "results":
            import h5py
            from lauelab.indexing import validate_results_file

            result = validate_results_file(check)
            if result.n_frames != counts["n_succeeded"]:
                raise ValueError("Returned indexing frame count disagrees with the run summary")
            expected_ids = {entry.input_id for entry in read_manifest(run / "inputs.jsonl")}
            with h5py.File(check, "r") as handle:
                if not set(handle["frames/frame_ids"].asstr()[...]).issubset(expected_ids):
                    raise ValueError("Returned indexing file contains frames outside this run")
        elif name == "reconstruction":
            from lauelab.reconstruct import validate_scan_file

            result = validate_scan_file(check)
            if result.n_points != plan["n_inputs"] or result.n_complete != counts["n_succeeded"]:
                raise ValueError("Returned reconstruction counters disagree with the run summary")
    if status == "Finished":
        expected = "results" if plan["kind"] == "lauego_indexing" else "reconstruction"
        if expected not in mapped:
            raise ValueError(f"Returned success has no {expected} artifact")
    marker = run / ".bdp-publication.json"
    if marker.exists():
        if _read(marker)["submission_id"] != plan["submission_id"]:
            raise FileExistsError("This run already contains a different publication")
    else:
        names = [p.name for p in incoming.iterdir() if p.name not in {"run.json", ".runner.lock"}]
        for name in names:
            if (run / name).exists():
                raise FileExistsError(f"Publication would overwrite {run / name}")
        write_json_file(marker, {"submission_id": plan["submission_id"], "files": names})
    for name in _read(marker)["files"]:
        if Path(name).name != name or name in {"request.json", "inputs.jsonl", "bdp.json"}:
            raise ValueError(f"Unexpected returned control file: {name}")
        source, destination = incoming / name, run / name
        if not source.exists():
            if destination.exists():
                continue  # Already moved by this publication before a poller restart.
            raise FileNotFoundError(source)
        if destination.exists():
            raise FileExistsError(destination)
        if source.is_symlink():
            raise ValueError(f"Returned symlink is not an output: {source}")
        if source.is_dir():
            # No HDF5 external link outside this tree is accepted by validation.
            if any(p.is_symlink() for p in source.rglob("*")):
                raise ValueError("Returned output directory contains symlinks")
            source.rename(destination)
        else:
            transform = None
            if plan["kind"] == "lauego_indexing":
                if mapped.get("results") == str(destination):
                    transform = partial(_restore_input_paths, plan=plan, kind="results")
                elif source.suffix.lower() == ".xml":
                    transform = partial(_restore_input_paths, plan=plan, kind="xml")
            _publish_returned_file(source, destination, transform)
    summary["artifacts"] = mapped
    summary.setdefault("provenance", {})["remote_output_directory"] = plan["output_directory"]
    if (run / "run.json").exists():
        if _read(run / "run.json").get("submission_id") != plan["submission_id"]:
            raise FileExistsError(run / "run.json")
    else:
        write_json_file(run / "run.json", summary)
    return summary


def poll_once(*, engine=None, settings=None, client=None):
    engine = engine or session_utils.get_engine()
    settings = portal_settings(settings)
    if not settings.get("enabled"):
        return []
    client = client or DMClient(settings["dm"])
    with Session(engine) as session:
        jobs = session.scalars(
            select(db_schema.Job).where(
                db_schema.Job.backend.in_(("aps", "crux")),
                db_schema.Job.status.in_((int(JobStatus.QUEUED), int(JobStatus.RUNNING))),
            )
        ).all()
        session.expunge_all()
    updated = []
    for job in jobs:
        state = None
        try:
            plan = _read(Path(job.run_directory) / "bdp.json")
            external_id = job.external_id
            if not external_id:
                records = client.find(job.submission_id)
                if len(records) != 1:
                    if len(records) > 1:
                        raise ValueError(
                            "Multiple DM jobs have the same submission identity; manual reconciliation required"
                        )
                    continue
                external_id = records[0]["id"]
            record = client.get(external_id)
            state = str(record["status"]).lower()
            if (
                job.cancel_requested_at
                and state not in {"done", "failed", "aborted"}
                and not (Path(job.run_directory) / ".cancel-sent").exists()
            ):
                request_cancellation(job, settings, client)
            summary = None
            if state in {"done", "failed", "aborted"}:
                incoming = Path(plan.get("incoming_directory", plan["output_directory"]))
                if (incoming / "run.json").exists():
                    summary = publish_returned(plan)
                elif state == "done":
                    raise ValueError("DM completed without returning a run summary")
            with Session(engine) as session, session.begin():
                current = session.get(db_schema.Job, job.job_id)
                if execution.is_terminal(current):
                    continue
                current.external_id = external_id
                current.external_state = state
                current.external_url = record.get("url") or current.external_url
                if current.phase == RunPhase.QUEUED and state != "pending":
                    execution.mark_running(current)
                if current.phase == RunPhase.RUNNING:
                    execution.heartbeat(current)
                if summary:
                    counts = summary["counters"]
                    execution.record_progress(current, succeeded=counts["n_succeeded"], failed=counts["n_failed"])
                    if current.indexing_run:
                        current.indexing_run.results_path = summary["artifacts"].get("results")
                        current.indexing_run.n_frames_indexed = counts.get("n_indexed")
                    execution.finalize(
                        current,
                        status=JobStatus[summary["status"].upper()],
                        message=summary.get("message"),
                        failure_report_path=str(Path(job.run_directory) / "failures.jsonl"),
                    )
                elif state in {"failed", "aborted"}:
                    execution.finalize(
                        current,
                        status=JobStatus.CANCELLED if current.cancel_requested_at else JobStatus.FAILED,
                        message=f"DM job {external_id} {state}; inspect DM stage diagnostics",
                    )
                updated.append(job.job_id)
        except Exception as error:
            if state in {"done", "failed", "aborted"} and isinstance(
                error, (ValueError, FileExistsError, FileNotFoundError)
            ):
                with Session(engine) as session, session.begin():
                    current = session.get(db_schema.Job, job.job_id)
                    if not execution.is_terminal(current):
                        execution.finalize(
                            current,
                            status=JobStatus.FAILED,
                            message=f"Returned output could not be validated/published: {error}",
                        )
                        updated.append(job.job_id)
            # A transient DM/filesystem failure is not evidence that remote work stopped.
            logger.exception("Could not reconcile remote job %s", job.job_id)
    return updated


def main():
    import fcntl

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    settings = portal_settings()
    if not settings.get("enabled"):
        if args.once:
            return
    else:
        lock_path = Path(settings["submission_directory"]) / ".poller.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with open(lock_path, "a", encoding="utf-8") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            stop = threading.Event()
            for signum in (signal.SIGINT, signal.SIGTERM):
                signal.signal(signum, lambda number, frame: stop.set())
            while True:
                poll_once()
                if args.once or stop.wait(settings.get("poll_seconds", 10)):
                    return


if __name__ == "__main__":
    main()
