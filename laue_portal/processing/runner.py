"""Run a frozen request on a compute node without portal config, Redis, or a database."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import signal
import threading
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from laue_portal.processing.bdp.settings import map_path
from laue_portal.processing.compute import RunOutcome, RunRequest, get_compute_function
from laue_portal.processing.processes import terminate_descendants
from laue_portal.workflows.manifest import (
    FailureReportWriter,
    read_manifest,
    read_request,
    verify_manifest,
    write_json_file,
)


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class FileHooks:
    """Publish a heartbeat even during a long native call; cancellation drains active work."""

    def __init__(self, directory, cancel_file, *, interval=5):
        self.directory = Path(directory)
        self.cancel_file = Path(cancel_file)
        self.interval = interval
        self.succeeded = self.failed = 0
        self.messages = []
        self.outcome = None
        self.signal_received = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._heartbeat, daemon=True)
        self._error = None
        self.failures = FailureReportWriter(self.directory / "failures.jsonl")

    def should_stop(self):
        return self.signal_received is not None or self.cancel_file.exists() or self._error is not None

    def report_progress(self, *, succeeded, failed):
        with self._lock:
            if succeeded < self.succeeded or failed < self.failed:
                raise ValueError("Progress cannot go backwards")
            self.succeeded, self.failed = succeeded, failed

    def record_failure(self, record):
        self.failures.append(record)

    def report_outcome(self, outcome):
        self.outcome = outcome

    def log(self, message):
        self.messages.append(str(message))

    def publish(self):
        with self._lock:
            write_json_file(
                self.directory / "progress.json",
                {
                    "heartbeat_at": timestamp(),
                    "n_succeeded": self.succeeded,
                    "n_failed": self.failed,
                },
                overwrite=True,
            )

    def _heartbeat(self):
        while not self._stop.wait(self.interval):
            try:
                self.publish()
            except Exception as error:
                self._error = error
                return

    def start(self):
        self.publish()
        self._thread.start()

    def close(self):
        self._stop.set()
        self._thread.join()
        report = self.failures.close()
        self.publish()
        if self._error:
            raise self._error
        return report


def load_request(directory, plan):
    directory = Path(directory)
    path = directory / "request.json"
    if hashlib.sha256(path.read_bytes()).hexdigest() != plan["request_sha256"]:
        raise ValueError("Frozen request checksum does not match the submission plan")
    document = read_request(path)
    verify_manifest(
        directory / "inputs.jsonl", expected_digest=plan["manifest_sha256"], expected_count=plan["n_inputs"]
    )
    mappings = plan["path_map"]
    document = json.loads(json.dumps(document))
    for key in ("geometry_file", "crystal_file", "mask_file", "input_path"):
        if document["request"].get(key):
            document["request"][key] = map_path(document["request"][key], mappings)
    if os.path.isabs(document["output"].get("xml", "")):
        document["output"]["xml"] = map_path(document["output"]["xml"], mappings)
    policy = plan["execution"]
    document["request"]["num_threads"] = (
        policy.get("indexing_threads_per_worker", policy["threads_per_worker"])
        if document["kind"] == "lauego_indexing"
        else policy["threads_per_worker"]
    )
    if policy.get("memory_limit_mb") is not None:
        document["request"]["memory_limit_mb"] = policy["memory_limit_mb"]
    entries = [
        replace(entry, source=map_path(entry.source, mappings)) for entry in read_manifest(directory / "inputs.jsonl")
    ]
    run = document["run"]
    display_id = (
        f"Indexing I{run['indexing_id']}" if "indexing_id" in run else f"Reconstruction R{run['reconstruction_id']}"
    )
    return RunRequest(
        job_id=plan["job_id"],
        kind=document["kind"],
        display_id=display_id,
        run_directory=plan["output_directory"],
        manifest_path=str(directory / "inputs.jsonl"),
        document=document,
        n_inputs=plan["n_inputs"],
        workers=policy["workers"],
        max_in_flight=policy.get("max_in_flight"),
        reconstruction_workers=policy["reconstruction_workers"],
    ), entries


def run(directory, *, compute=None, request=None, entries=None):
    """Run once. A durable exclusive lock prevents accidental duplicate execution."""
    directory = Path(directory)
    plan = json.loads((directory / "bdp.json").read_text())
    if request is None:
        request, entries = load_request(directory, plan)
    output = Path(request.run_directory)
    output.mkdir(parents=True, exist_ok=True)
    with open(output / ".runner.lock", "x", encoding="utf-8") as lock:
        lock.write(str(os.getpid()))
    hooks = FileHooks(output, directory / "cancel.request")
    previous = {}
    for signum in (signal.SIGINT, signal.SIGTERM):
        previous[signum] = signal.signal(signum, lambda number, frame: setattr(hooks, "signal_received", number))
    started_at = timestamp()
    outcome = None
    error = None
    hooks.start()
    try:
        if not hooks.should_stop():
            outcome = (compute or get_compute_function(request.kind))(request, entries, hooks)
        else:
            outcome = RunOutcome(0, 0, stopped=True)
        if not isinstance(outcome, RunOutcome):
            raise TypeError("Compute function did not return a RunOutcome")
        hooks.report_progress(succeeded=outcome.n_succeeded, failed=outcome.n_failed)
    except BaseException as exception:
        error = exception
        outcome = hooks.outcome
    finally:
        terminate_descendants()
        for signum, handler in previous.items():
            signal.signal(signum, handler)
        try:
            report = hooks.close()
        except Exception as exception:
            report = None
            error = error or exception
    succeeded, failed = hooks.succeeded, hooks.failed
    if succeeded + failed > request.n_inputs:
        raise ValueError("Compute counters exceed the manifest")
    status = "Finished"
    message = outcome.summary if outcome else "Run failed"
    if error or hooks.signal_received or (outcome and outcome.validation_error):
        status = "Failed"
        message = str(
            error or (outcome and outcome.validation_error) or f"Interrupted by signal {hooks.signal_received}"
        )
    elif outcome and outcome.stopped:
        status, message = "Cancelled", "Cancelled by request; completed results kept"
    elif failed or succeeded != request.n_inputs:
        status, message = "Failed", "Not all inputs completed successfully"
    summary = {
        "format": "laue-portal-run-summary",
        "version": 1,
        "job_id": request.job_id,
        "submission_id": plan["submission_id"],
        "display_id": request.display_id,
        "kind": request.kind,
        "status": status,
        "phase": status.lower(),
        "message": message,
        "started_at": started_at,
        "finished_at": timestamp(),
        "host": platform.node(),
        "counters": {
            "n_inputs": request.n_inputs,
            "n_succeeded": succeeded,
            "n_failed": failed,
            "n_not_run": request.n_inputs - succeeded - failed,
            "n_indexed": outcome.n_indexed if outcome else None,
        },
        "artifacts": dict(outcome.artifacts) if outcome else {},
        "provenance": {**(outcome.provenance if outcome else {}), "path_map": plan["path_map"]},
        "warnings": outcome.warnings if outcome else [],
        "log": hooks.messages,
        "failure_report": os.path.basename(report) if report else None,
        "policy": plan["execution"],
    }
    write_json_file(output / "run.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", help="Directory containing request.json, inputs.jsonl, and bdp.json")
    args = parser.parse_args()
    summary = run(args.directory)
    print(json.dumps({"status": summary["status"], "counters": summary["counters"]}))
    return 0 if summary["status"] == "Finished" else 1


if __name__ == "__main__":
    raise SystemExit(main())
