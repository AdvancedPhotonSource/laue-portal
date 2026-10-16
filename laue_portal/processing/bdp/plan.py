"""Plan only the selected files and new run destinations; never copy raw data locally."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path, PurePosixPath
from uuid import UUID

from laue_portal.processing.bdp.settings import child_path, collection_path
from laue_portal.workflows.manifest import read_manifest, read_request, verify_manifest, write_json_file

PLAN_NAME = "bdp.json"


def submission_path(settings, submission_id):
    submission_id = str(UUID(submission_id))
    return Path(settings["submission_directory"]) / f"{submission_id}.json"


def build_plan(job, settings, submission_id):
    """Keep request/manifest immutable, recording their digest and effective path map."""
    submission_id = str(UUID(submission_id))
    target = settings["targets"][job.backend]
    source = settings["storage"]["aps"]
    run = child_path(source["filesystem_root"], job.run_directory)
    experiment = Path(settings.get("experiment_directory", Path(source["filesystem_root"]) / "LauePortal"))
    child_path(experiment / "analysis", run)
    verify_manifest(job.manifest_path, expected_digest=job.manifest_digest, expected_count=job.n_inputs)
    document = read_request(job.request_path)
    xml = document.get("output", {}).get("xml")
    if xml and os.path.isabs(xml):
        child_path(run, xml)  # Remote jobs must publish all outputs inside their run.
    plan = {
        "version": 1,
        "submission_id": submission_id,
        "job_id": job.job_id,
        "backend": job.backend,
        "run_directory": str(run),
        "request_sha256": hashlib.sha256(Path(job.request_path).read_bytes()).hexdigest(),
        "manifest_sha256": job.manifest_digest,
        "n_inputs": job.n_inputs,
        "kind": document["kind"],
        "execution": dict(target["execution"]),
        "pbs": dict(target["pbs"]),
    }
    if job.backend == "aps":
        plan.update(
            control_directory=str(run),
            output_directory=str(run / "incoming" / submission_id),
            path_map={
                str(run): str(run / "incoming" / submission_id),
                source["filesystem_root"]: source["filesystem_root"],
            },
            target=dict(target),
        )
        return plan
    destination = settings["storage"]["eagle"]
    if not source.get("collection_id") or not destination.get("collection_id"):
        raise ValueError("APS and Eagle Transfer collection IDs must be configured")
    remote = PurePosixPath(target["workspace"]) / "runs" / submission_id
    control, output = remote / "control", remote / "results"
    mappings = {str(run): str(output), source["filesystem_root"]: str(remote / "inputs")}
    inputs = {entry.source for entry in read_manifest(job.manifest_path)}
    for key in ("geometry_file", "crystal_file", "mask_file"):
        value = document["request"].get(key)
        if value:
            inputs.add(value)
    items = []
    for path in sorted(inputs):
        local = child_path(experiment, path)
        if not local.is_file():
            raise ValueError(f"Input does not exist: {local}")
        remote_file = remote / "inputs" / local.relative_to(Path(source["filesystem_root"]).resolve()).as_posix()
        items.append(
            {
                "source_path": collection_path(source, local),
                "destination_path": collection_path(destination, remote_file),
                "recursive": False,
            }
        )
    # Only frozen control files are sent. Outputs and failure files never become inputs.
    for filename in ("request.json", "inputs.jsonl", PLAN_NAME):
        items.append(
            {
                "source_path": collection_path(source, run / filename),
                "destination_path": collection_path(destination, control / filename),
                "recursive": False,
            }
        )
    incoming = run / "incoming" / submission_id
    plan.update(
        control_directory=str(control),
        output_directory=str(output),
        incoming_directory=str(incoming),
        path_map=mappings,
        target=dict(target),
        input_transfer={
            "source_endpoint_id": source["collection_id"],
            "destination_endpoint_id": destination["collection_id"],
            "transfer_items": items,
        },
        result_transfer={
            "source_endpoint_id": destination["collection_id"],
            "destination_endpoint_id": source["collection_id"],
            "transfer_items": [
                {
                    "source_path": collection_path(destination, output),
                    "destination_path": collection_path(source, incoming),
                    "recursive": True,
                }
            ],
        },
        cancel_transfer={
            "source_endpoint_id": source["collection_id"],
            "destination_endpoint_id": destination["collection_id"],
            "transfer_items": [
                {
                    "source_path": collection_path(source, run / "cancel.request"),
                    "destination_path": collection_path(destination, control / "cancel.request"),
                    "recursive": False,
                }
            ],
        },
    )
    return plan


def save_plan(job, settings, submission_id):
    plan = build_plan(job, settings, submission_id)
    incoming = Path(plan.get("incoming_directory", plan["output_directory"]))
    if incoming.exists():
        raise FileExistsError(f"Return destination already exists: {incoming}")
    # A second process must not race the shared partial-file publisher.
    with open(Path(job.run_directory) / ".bdp-submission.lock", "x", encoding="utf-8") as lock:
        lock.write(submission_id)
    path = Path(job.run_directory) / PLAN_NAME
    write_json_file(path, plan)  # Exclusive publication; no existing file is replaced.
    inbox = submission_path(settings, submission_id)
    inbox.parent.mkdir(parents=True, exist_ok=True)
    write_json_file(inbox, plan)
    return plan
