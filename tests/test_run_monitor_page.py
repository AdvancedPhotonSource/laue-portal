"""Tests for the run monitor: counter rows, transaction-based refresh, run-oriented wording."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from dash import no_update
from dash.exceptions import PreventUpdate
from sqlalchemy.orm import Session

import lau_dash  # noqa: F401  instantiates the Dash app so page modules can register
from laue_portal.components import live_rows
from laue_portal.database import db_schema
from laue_portal.pages import peakindexings, reconstructions, run_monitor
from laue_portal.workflows import execution
from laue_portal.workflows.execution import JobStatus
from tests.conftest import create_test_indexing_run, create_test_lauego_parameters
from tests.run_support import make_engine, publish_wire_run
from tests.test_job_page import _text


@pytest.fixture
def engine(tmp_path, monkeypatch):
    yield make_engine(tmp_path, monkeypatch)


def _start(engine, job_id, *, succeeded=0, failed=0):
    with Session(engine) as session, session.begin():
        job = session.get(db_schema.Job, job_id)
        execution.mark_queued(job, f"rq-{job_id}")
        execution.mark_running(job)
        execution.record_progress(job, succeeded=succeeded, failed=failed)


def _finish(engine, job_id, status=JobStatus.FINISHED):
    with Session(engine) as session, session.begin():
        execution.finalize(session.get(db_schema.Job, job_id), status=status, message="done")


def test_rows_carry_run_counters_and_the_progress_column_uses_the_run_renderer(engine, tmp_path):
    run = publish_wire_run(engine, tmp_path, count=5)
    _start(engine, run.job_id, succeeded=2, failed=1)

    columns, rows = run_monitor._get_jobs()

    assert len(rows) == 1
    row = rows[0]
    assert (row["n_inputs"], row["n_succeeded"], row["n_failed"], row["n_not_run"]) == (5, 2, 1, 0)
    assert (row["n_processed"], row["n_pending"]) == (3, 2)
    assert row["duration_display"].endswith("(running)")
    progress = next(column for column in columns if column["headerName"] == "Run Progress")
    assert progress["cellRenderer"] == "RunProgressRenderer" and progress["field"] == "n_processed"
    fields = {column.get("field") for column in columns}
    assert "SubJobs Progress" not in {column["headerName"] for column in columns}
    assert fields.isdisjoint({"manifest_path", "queue_job_id", "failure_report_path", "heartbeat_at"})


def test_refresh_sends_only_active_or_newly_finalized_rows_and_adds_new_runs(engine, tmp_path, monkeypatch):
    monkeypatch.setattr(live_rows, "POLL_OVERLAP", timedelta(0))  # polls here are microseconds apart
    first = publish_wire_run(engine, tmp_path, name="first")
    _finish(engine, first.job_id)  # terminal before the page loads: never re-sent
    second = publish_wire_run(engine, tmp_path, name="second", count=4)
    _start(engine, second.job_id, succeeded=1)

    columns, rows, state = run_monitor.get_jobs("/run-monitor")
    assert [row["job_id"] for row in rows] == [second.job_id, first.job_id]
    assert state["max_id"] == second.job_id

    transaction, state, note = run_monitor.refresh_jobs(1, None, state, "/run-monitor")
    assert [row["job_id"] for row in transaction["update"]] == [second.job_id]  # active run only
    assert "add" not in transaction
    assert "1 active run(s)" in note

    with Session(engine) as session, session.begin():
        execution.record_progress(session.get(db_schema.Job, second.job_id), succeeded=3, failed=0)
    third = publish_wire_run(engine, tmp_path, name="third")

    transaction, state, note = run_monitor.refresh_jobs(2, None, state, "/run-monitor")
    assert [row["job_id"] for row in transaction["update"]] == [second.job_id]
    assert transaction["update"][0]["n_processed"] == 3
    assert [row["job_id"] for row in transaction["add"]] == [third.job_id] and transaction["addIndex"] == 0
    assert state["max_id"] == third.job_id

    _finish(engine, second.job_id)
    _finish(engine, third.job_id, JobStatus.CANCELLED)
    transaction, state, note = run_monitor.refresh_jobs(3, None, state, "/run-monitor")
    assert sorted(row["job_id"] for row in transaction["update"]) == sorted([second.job_id, third.job_id])
    assert "0 active run(s)" in note
    assert live_rows.payload_bytes(transaction) < 4000

    # Nothing active and nothing finalized since the last poll: no transaction is sent.
    transaction, state, note = run_monitor.refresh_jobs(4, None, state, "/run-monitor")
    assert transaction is no_update
    assert "no active runs" in note

    with pytest.raises(PreventUpdate):
        run_monitor.refresh_jobs(5, None, state, "/elsewhere")
    with pytest.raises(PreventUpdate):
        run_monitor.refresh_jobs(5, None, None, "/run-monitor")
    with pytest.raises(PreventUpdate):
        run_monitor.get_jobs("/elsewhere")


def test_stop_wording_describes_runs_and_updates_only_their_rows(engine, tmp_path):
    queued = publish_wire_run(engine, tmp_path, name="queued")
    running = publish_wire_run(engine, tmp_path, name="running", count=4)
    _start(engine, running.job_id, succeeded=1)
    selected = [
        {"job_id": queued.job_id, "status": 0},
        {"job_id": running.job_id, "status": 1},
        {"job_id": 999, "status": 2},
    ]

    is_open, body = run_monitor.open_stop_confirmation(1, selected)
    text = _text(body)
    assert "Stop 2 run(s)?" in text and "keeps every completed result" in text and "subjob" not in text.lower()

    results = [
        (queued.job_id, {"success": True, "state": "cancelled", "n_pending": 3, "message": "removed"}),
        (running.job_id, {"success": True, "state": "requested", "n_pending": 3, "message": "requested"}),
        (7, {"success": False, "state": "already_done", "n_pending": 0, "message": "Job 7 is already Finished"}),
    ]
    message, icon = run_monitor.summarize_stop_results(results)
    assert "1 queued run(s) removed from the queue" in message
    assert "1 running run(s) asked to stop" in message and "3 pending input(s) will be recorded as not run" in message
    assert "Job 7 is already Finished" in message and icon == "success"
    assert run_monitor.summarize_stop_results([]) == ("No runs were stopped.", "warning")

    with (
        patch.object(run_monitor, "_fetch_queue_entry", create=True),
        patch("laue_portal.processing.queue.controls._fetch_queue_entry", return_value=None),
    ):
        is_open, message, icon, toast_open, transaction = run_monitor.execute_stop(1, selected)
    assert is_open is False and toast_open is True
    assert sorted(row["job_id"] for row in transaction["update"]) == sorted([queued.job_id, running.job_id])
    statuses = {row["job_id"]: row["status"] for row in transaction["update"]}
    assert statuses[queued.job_id] == JobStatus.CANCELLED and statuses[running.job_id] == JobStatus.RUNNING


def test_move_to_front_wording_makes_no_preemption_claim():
    is_open, body = run_monitor.open_move_front_confirmation(
        1, [{"job_id": 3, "status": 0}, {"job_id": 4, "status": 1}]
    )
    text = _text(body)
    assert "Move 1 queued run(s)" in text and "never interrupted" in text and "subjob" not in text.lower()
    with pytest.raises(PreventUpdate):
        run_monitor.open_move_front_confirmation(1, [{"job_id": 4, "status": 1}])


def test_list_pages_refresh_with_transactions_keyed_by_run_identity(engine, tmp_path, monkeypatch):
    monkeypatch.setattr(live_rows, "POLL_OVERLAP", timedelta(0))
    wire = publish_wire_run(engine, tmp_path, count=6)
    _start(engine, wire.job_id, succeeded=2, failed=1)
    with Session(engine) as session, session.begin():
        job = db_schema.Job(job_id=50, computer_name="h", status=1, phase="running", priority=0, n_inputs=3)
        session.add(job)
        indexing = create_test_indexing_run(scan_number=1, job_id=50)
        indexing.lauego_parameters = create_test_lauego_parameters()
        session.add(indexing)

    columns, rows, state = reconstructions.get_recons("/reconstructions")
    assert rows[0]["status_progress"] == "3/6" and rows[0]["n_pending"] == 3
    transaction, next_state = reconstructions.refresh_recons(1, state, "/reconstructions")
    assert [row["reconstruction_id"] for row in transaction["update"]] == [wire.id]
    _finish(engine, wire.job_id)
    transaction, next_state = reconstructions.refresh_recons(2, next_state, "/reconstructions")
    assert (
        transaction["update"][0]["status"] == JobStatus.FINISHED and transaction["update"][0]["status_progress"] is None
    )
    assert reconstructions.refresh_recons(3, next_state, "/reconstructions")[0] is no_update

    columns, rows, state = peakindexings.get_peakindexings("/peakindexings")
    assert rows[0]["indexing_id"] == 1 and rows[0]["status_progress"] == "0/3"
    transaction, next_state = peakindexings.refresh_peakindexings(1, state, "/peakindexings")
    assert [row["indexing_id"] for row in transaction["update"]] == [1]
    with pytest.raises(PreventUpdate):
        peakindexings.refresh_peakindexings(2, next_state, "/other")


def test_duration_display_handles_missing_and_running_times():
    now = datetime(2026, 1, 1, 1, 0, 0)
    assert run_monitor.calculate_duration_display(None, None, now) is None
    assert run_monitor.calculate_duration_display(datetime(2026, 1, 1), None, now) == "01:00:00 (running)"
    assert (
        run_monitor.calculate_duration_display(datetime(2026, 1, 1), datetime(2026, 1, 1, 0, 0, 5), now) == "00:00:05"
    )
