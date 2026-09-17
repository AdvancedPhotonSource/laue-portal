"""Tests for the cutover preflight script."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from laue_portal.database import db_schema
from laue_portal.workflows import execution
from scripts import cutover_check
from tests.run_support import make_engine, publish_wire_run


@pytest.fixture
def engine(tmp_path, monkeypatch):
    yield make_engine(tmp_path, monkeypatch)


def _db(tmp_path) -> Path:
    return tmp_path / "runs.db"


def _failed(checks):
    return [check.name for check in checks if not check.ok]


def test_fresh_compact_database_passes_the_database_checks(engine, tmp_path):
    checks = cutover_check.check_database(_db(tmp_path))
    assert _failed(checks) == []
    assert {check.name for check in checks} == {
        "schema stage",
        "model columns",
        "optional peak limit",
        "per-input table",
        "unpublished runs",
        "active runs",
    }


def test_leftover_subjob_table_unpublished_and_active_runs_fail(engine, tmp_path):
    run = publish_wire_run(engine, tmp_path)
    with Session(engine) as session, session.begin():
        execution.mark_queued(session.get(db_schema.Job, run.job_id), "rq-1")
        session.add(db_schema.Job(computer_name="h", status=0, phase="created", priority=0))
    with sqlite3.connect(_db(tmp_path)) as connection:
        connection.execute("CREATE TABLE subjob (subjob_id INTEGER PRIMARY KEY)")

    checks = cutover_check.check_database(_db(tmp_path))

    assert set(_failed(checks)) == {"per-input table", "unpublished runs", "active runs"}
    detail = next(check.detail for check in checks if check.name == "active runs")
    assert f"job {run.job_id} (queued)" in detail
    assert cutover_check.check_database(tmp_path / "missing.db")[0].ok is False


def test_unified_or_legacy_databases_are_reported_as_needing_migration(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE peakindex (id INTEGER)")
    checks = cutover_check.check_database(path)
    assert _failed(checks) == ["schema stage"] and "migrate_workflow_database" in checks[0].detail


def test_config_checks_require_an_explicit_worker_count():
    with patch("laue_portal.config.RUN_EXECUTION", {"job_timeout_seconds": 10, "workers": 4}):
        assert _failed(cutover_check.check_config()) == []
    with patch("laue_portal.config.RUN_EXECUTION", {"job_timeout_seconds": 10}):
        assert _failed(cutover_check.check_config()) == ["RUN_EXECUTION.workers"]
    with patch("laue_portal.config.RUN_EXECUTION", {}):
        assert _failed(cutover_check.check_config()) == ["RUN_EXECUTION"]


def test_queue_checks_flag_old_workers_and_per_chunk_entries():
    workers = [SimpleNamespace(name="laue-run-host-1"), SimpleNamespace(name="host.4242.abc")]
    entries = {
        "run_3": SimpleNamespace(func_name="laue_portal.processing.queue.executors.execute_run"),
        "chunk-9": SimpleNamespace(func_name="laue_portal.processing.queue.batch.execute_indexing_chunk"),
    }
    fake_queue = SimpleNamespace(job_ids=["run_3", "chunk-9"], name="laue_jobs")
    with (
        patch("laue_portal.processing.queue.core.check_redis_connection", return_value=True),
        patch("laue_portal.processing.queue.core.job_queue", fake_queue),
        patch("rq.Worker.all", return_value=workers),
        patch("rq.job.Job.fetch", side_effect=lambda rq_id, connection: entries[rq_id]),
        patch("rq.registry.StartedJobRegistry", return_value=SimpleNamespace(get_job_ids=lambda: [])),
    ):
        checks = cutover_check.check_queue("laue-run")
    assert set(_failed(checks)) == {"queue entries", "workers"}
    assert "chunk-9" in next(check.detail for check in checks if check.name == "queue entries")
    assert "host.4242.abc" in next(check.detail for check in checks if check.name == "workers")

    with patch("laue_portal.processing.queue.core.check_redis_connection", return_value=False):
        checks = cutover_check.check_queue("laue-run")
    assert _failed(checks) == ["redis"]


def test_main_prints_one_line_per_check_and_exits_nonzero_on_failure(engine, tmp_path, capsys):
    with patch("laue_portal.config.RUN_EXECUTION", {"job_timeout_seconds": 10, "workers": 4}):
        code = cutover_check.main(["--db", str(_db(tmp_path)), "--no-redis"])
    out = capsys.readouterr().out
    assert code == 0 and "Cutover preflight: ready" in out and out.count("[ok]") == 8

    with patch("laue_portal.config.RUN_EXECUTION", {}):
        code = cutover_check.main(["--db", str(_db(tmp_path)), "--no-redis"])
    assert code == 1 and "1 check(s) failed" in capsys.readouterr().out
