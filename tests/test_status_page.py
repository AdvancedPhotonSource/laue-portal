"""Tests for the status page's active-runs card."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

import lau_dash  # noqa: F401  instantiates the Dash app so page modules can register
from laue_portal.database import db_schema
from laue_portal.pages import status as status_page
from laue_portal.workflows import execution
from tests.run_support import make_engine, publish_wire_run
from tests.test_job_page import _texts


@pytest.fixture
def engine(tmp_path, monkeypatch):
    yield make_engine(tmp_path, monkeypatch)


def test_active_runs_list_running_and_queued_jobs_with_liveness(engine, tmp_path):
    queued = publish_wire_run(engine, tmp_path, name="queued")
    running = publish_wire_run(engine, tmp_path, name="running", count=4)
    stale = publish_wire_run(engine, tmp_path, name="stale", count=2)
    finished = publish_wire_run(engine, tmp_path, name="finished")
    now = datetime(2026, 9, 16, 12, 0, 0)
    with Session(engine) as session, session.begin():
        execution.mark_queued(session.get(db_schema.Job, queued.job_id), "rq-q")
        job = session.get(db_schema.Job, running.job_id)
        execution.mark_queued(job, "rq-r")
        execution.mark_running(job, now=now - timedelta(seconds=30))
        execution.record_progress(job, succeeded=1, failed=0, now=now - timedelta(seconds=20))
        execution.request_cancellation(job, now=now - timedelta(seconds=5))
        job = session.get(db_schema.Job, stale.job_id)
        execution.mark_queued(job, "rq-s")
        execution.mark_running(job, now=now - timedelta(hours=2))
        job = session.get(db_schema.Job, finished.job_id)
        execution.mark_queued(job, "rq-f")
        execution.mark_running(job, now=now)
        execution.finalize(job, status=execution.JobStatus.FINISHED, now=now)

    rows = status_page.active_run_rows(now=now)

    by_id = {row["job_id"]: row for row in rows}
    assert set(by_id) == {queued.job_id, running.job_id, stale.job_id}
    assert by_id[queued.job_id]["status"] == "Queued" and by_id[queued.job_id]["heartbeat_age"] is None
    assert by_id[running.job_id] == {
        "job_id": running.job_id,
        "display": f"Reconstruction R{running.id}",
        "status": "Running",
        "phase": "running",
        "progress": "1/4",
        "heartbeat_age": 20,
        "stale": False,
        "cancel_requested": True,
    }
    assert by_id[stale.job_id]["stale"] is True

    text = " ".join(_texts(status_page.active_runs_content(rows)))
    assert "stop requested" in text and "reconciled as interrupted" in text and "heartbeat 20 s ago" in text
    assert "No queued or running runs" in " ".join(_texts(status_page.active_runs_content([])))
    assert "No queued or running runs" not in text
