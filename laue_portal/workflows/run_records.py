"""Shared run persistence: job creation and manifest publication.

Both workflow services follow the same sequence: create the job and run rows
in one transaction (the run ID names the run directory), then publish the
manifest and frozen request, then record the publication on the job. A run
whose publication fails is marked Failed with the reason; it is never runnable
because only ``RunPhase.PUBLISHED`` jobs may be enqueued.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import fields
from datetime import datetime
from typing import Any

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from laue_portal.database import db_schema
from laue_portal.workflows import execution
from laue_portal.workflows.files import ResolvedInput
from laue_portal.workflows.manifest import (
    MANIFEST_FILENAME,
    REQUEST_FILENAME,
    ManifestError,
    ManifestSummary,
    build_manifest_entries,
    write_manifest,
    write_request,
)


class RunPublicationError(RuntimeError):
    """Raised when a run's manifest or request could not be published; the job is marked Failed."""


def new_job(*, computer_name: str, priority: int, submitted_at: datetime, n_inputs: int) -> db_schema.Job:
    job = db_schema.Job(
        computer_name=computer_name,
        status=int(execution.JobStatus.QUEUED),
        priority=priority,
        submit_time=submitted_at,
        start_time=None,
        finish_time=None,
    )
    execution.initialize(job, n_inputs=n_inputs, now=submitted_at)
    return job


def request_document(request: Any) -> dict[str, Any]:
    """Serialize a frozen request dataclass, leaving out derived (init=False) fields."""

    return {field.name: getattr(request, field.name) for field in fields(request) if field.init}


def publish_run_inputs(
    engine: Engine,
    *,
    job_id: int,
    display_id: str,
    run_directory: str,
    inputs: Sequence[ResolvedInput],
    request_payload: Mapping[str, Any],
    depths: Mapping[int, float] | None = None,
    now: datetime | None = None,
) -> ManifestSummary:
    """Write ``inputs.jsonl`` and ``request.json`` into ``run_directory`` and record them."""

    manifest_path = os.path.join(run_directory, MANIFEST_FILENAME)
    request_path = os.path.join(run_directory, REQUEST_FILENAME)
    try:
        os.makedirs(run_directory, exist_ok=True)
        for existing in (manifest_path, request_path):
            if os.path.exists(existing):
                raise ManifestError(f"{existing} already exists; a run directory is never reused")
        entries = build_manifest_entries(inputs, depths=depths)
        summary = write_manifest(manifest_path, entries)
        payload = dict(request_payload)
        payload["manifest"] = {"path": MANIFEST_FILENAME, "n_inputs": summary.n_inputs, "sha256": summary.sha256}
        write_request(request_path, payload)
    except Exception as error:
        message = f"Run publication failed: {error}"
        with Session(engine) as session, session.begin():
            job = session.get(db_schema.Job, job_id)
            if job is not None and not execution.is_terminal(job):
                execution.record_failure(job, message, now=now)
        raise RunPublicationError(f"{display_id}: {message}") from error

    with Session(engine) as session, session.begin():
        job = session.get(db_schema.Job, job_id)
        if job is None:
            raise RunPublicationError(f"{display_id}: job {job_id} vanished before its manifest was recorded")
        execution.mark_published(
            job,
            run_directory=run_directory,
            manifest_path=manifest_path,
            manifest_digest=summary.sha256,
            request_path=request_path,
            n_inputs=summary.n_inputs,
            now=now,
        )
    return summary
