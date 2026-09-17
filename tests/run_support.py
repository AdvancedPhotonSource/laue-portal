"""Shared helpers for whole-run queue tests: a published run in a temporary database."""

from __future__ import annotations

import os
from datetime import datetime

from sqlalchemy.orm import Session

from laue_portal.database import db_schema, session_utils
from laue_portal.processing.queue.core import RunPolicy
from laue_portal.workflows import reconstruction as reconstruction_workflow
from tests.conftest import create_test_metadata

FAST_POLICY = RunPolicy(
    job_timeout_seconds=600,
    heartbeat_seconds=0.05,
    progress_seconds=0.05,
    cancel_poll_seconds=0.02,
    stale_heartbeat_seconds=1,
    shutdown_grace_seconds=5,
    workers=1,
)


def publish_wire_run(engine, tmp_path, *, count: int = 3, name: str = "wire", scan_number: int = 1):
    """Create a published wire reconstruction run with ``count`` fake input files."""

    with Session(engine) as session:
        if session.get(db_schema.Metadata, scan_number) is None:
            session.add(create_test_metadata(scan_number))
            session.commit()
    input_dir = tmp_path / f"{name}-input"
    input_dir.mkdir(exist_ok=True)
    for index in range(1, count + 1):
        (input_dir / f"{name}_{index}.h5").write_text("")
    request = reconstruction_workflow.WireReconstructionRequest(
        scan_number=scan_number,
        input_path=os.fspath(input_dir),
        output_path_template=os.fspath(tmp_path / f"{name}-run_%d"),
        filename_prefixes=[f"{name}_%d.h5"],
        geometry_file="/config/geometry.xml",
        percent_brightest=5.0,
        wire_edges="leading",
        depth_start=-10.0,
        depth_end=10.0,
        depth_resolution=0.5,
        num_threads=1,
        memory_limit_mb=256,
        scan_points=f"1-{count}" if count > 1 else "1",
        verbose=0,
        computer_name="test-host",
        submitted_at=datetime(2026, 9, 16, 10, 0, 0),
    )
    return reconstruction_workflow.create_reconstruction(request, engine=engine)


def load_job(engine, job_id):
    with Session(engine) as session:
        return session.get(db_schema.Job, job_id)


def make_engine(tmp_path, monkeypatch):
    """Point the application config at a fresh database file and return its engine."""

    db_file = tmp_path / "runs.db"
    monkeypatch.setattr("laue_portal.config.db_file", str(db_file))
    session_utils.init_db()
    return session_utils.get_engine()
