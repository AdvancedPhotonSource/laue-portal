"""Tests for whole-run queue admission, priority, cancellation, and reconciliation."""

from __future__ import annotations

import importlib
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from laue_portal.database import db_schema
from laue_portal.processing.queue import controls, core, enqueue, executors, lifecycle
from laue_portal.workflows import execution
from laue_portal.workflows.execution import ExecutionStateError, JobStatus, RunPhase
from tests.run_support import load_job, make_engine, publish_wire_run


class FakeQueue:
    def __init__(self):
        self.enqueued = []
        self.removed = []
        self.pushed = []

    def enqueue(self, func, *args, **kwargs):
        self.enqueued.append({"func": func, "args": args, "kwargs": kwargs})
        return SimpleNamespace(id=kwargs["job_id"])

    def remove(self, job_id):
        self.removed.append(job_id)

    def push_job_id(self, job_id, at_front=False):
        self.pushed.append((job_id, at_front))


class FakeRQJob:
    def __init__(self, is_queued=True):
        self.is_queued = is_queued
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


@pytest.fixture
def engine(tmp_path, monkeypatch):
    yield make_engine(tmp_path, monkeypatch)


def test_old_coordinator_machinery_is_gone():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("laue_portal.processing.queue.batch")
    for name in ("execute_indexing_chunk", "execute_reconstruction_subjob"):
        assert not hasattr(executors, name)
    for name in (
        "notify_subjobs_completed",
        "setup_batch_counter",
        "publish_job_update",
        "execute_with_status_updates",
    ):
        assert not hasattr(lifecycle, name)
    assert not hasattr(core, "PEAKINDEXING_QUEUE_BATCH_SIZE")
    assert not hasattr(core, "_chunked")
    assert core.STATUS_MAPPING == {0: "Queued", 1: "Running", 2: "Finished", 3: "Failed", 4: "Cancelled"}
    assert core.run_queue_id(12) == "run_12"


def test_run_policy_validates_its_settings():
    policy = core.RunPolicy.from_config({"job_timeout_seconds": 3600, "workers": 2})
    assert (policy.job_timeout_seconds, policy.workers, policy.heartbeat_seconds) == (3600, 2, 15.0)
    with pytest.raises(ValueError, match="Unknown RUN_EXECUTION"):
        core.RunPolicy.from_config({"chunk_size": 50})
    with pytest.raises(ValueError, match="job_timeout_seconds"):
        core.RunPolicy(job_timeout_seconds=0)
    with pytest.raises(ValueError, match="stale_heartbeat_seconds"):
        core.RunPolicy(heartbeat_seconds=30, stale_heartbeat_seconds=20)
    with pytest.raises(ValueError, match="max_in_flight"):
        core.RunPolicy(workers=4, max_in_flight=2)


def test_enqueue_run_is_deterministic_and_refuses_duplicates(engine, tmp_path, monkeypatch):
    fake_queue = FakeQueue()
    monkeypatch.setattr(enqueue, "job_queue", fake_queue)
    run = publish_wire_run(engine, tmp_path)

    queue_id = enqueue.enqueue_reconstruction(run.id, engine=engine)

    assert queue_id == f"run_{run.job_id}"
    assert len(fake_queue.enqueued) == 1
    queued = fake_queue.enqueued[0]
    assert queued["func"] is executors.execute_run
    assert queued["args"] == (run.job_id,)
    assert queued["kwargs"]["job_id"] == queue_id
    assert queued["kwargs"]["job_timeout"] == core.RUN_POLICY.job_timeout_seconds
    assert queued["kwargs"]["meta"]["db_job_id"] == run.job_id
    assert queued["kwargs"]["at_front"] is False
    job = load_job(engine, run.job_id)
    assert (job.phase, job.status, job.queue_job_id) == (RunPhase.QUEUED, JobStatus.QUEUED, queue_id)

    with pytest.raises(ExecutionStateError, match="only published runs"):
        enqueue.enqueue_run(run.job_id, engine=engine)
    assert len(fake_queue.enqueued) == 1

    with pytest.raises(ValueError, match="Reconstruction R999 does not exist"):
        enqueue.enqueue_reconstruction(999, engine=engine)
    with pytest.raises(ValueError, match="Indexing I999 does not exist"):
        enqueue.enqueue_indexing(999, engine=engine)


def test_enqueue_priority_places_the_run_at_the_front(engine, tmp_path, monkeypatch):
    fake_queue = FakeQueue()
    monkeypatch.setattr(enqueue, "job_queue", fake_queue)
    run = publish_wire_run(engine, tmp_path)
    enqueue.enqueue_run(run.job_id, at_front=True, engine=engine)
    assert fake_queue.enqueued[0]["kwargs"]["at_front"] is True


def test_enqueue_failure_records_a_failed_non_runnable_run(engine, tmp_path, monkeypatch):
    class OfflineQueue(FakeQueue):
        def enqueue(self, func, *args, **kwargs):
            raise RuntimeError("redis unavailable")

    monkeypatch.setattr(enqueue, "job_queue", OfflineQueue())
    run = publish_wire_run(engine, tmp_path)

    with pytest.raises(RuntimeError, match="redis unavailable"):
        enqueue.enqueue_run(run.job_id, engine=engine)

    job = load_job(engine, run.job_id)
    assert (job.status, job.phase) == (JobStatus.FAILED, RunPhase.FAILED)
    assert job.n_not_run == job.n_inputs == 3
    assert job.messages.endswith("Enqueue failed: redis unavailable")
    assert job.start_time is None
    with pytest.raises(ExecutionStateError):
        execution.assert_enqueueable(job)


def test_enqueue_refuses_a_tampered_manifest(engine, tmp_path, monkeypatch):
    fake_queue = FakeQueue()
    monkeypatch.setattr(enqueue, "job_queue", fake_queue)
    run = publish_wire_run(engine, tmp_path)
    with open(run.job.manifest_path, "a", encoding="utf-8") as handle:
        handle.write("\n")

    with pytest.raises(Exception, match="digest"):
        enqueue.enqueue_run(run.job_id, engine=engine)
    assert fake_queue.enqueued == []
    assert load_job(engine, run.job_id).phase == RunPhase.PUBLISHED


def test_cancel_a_queued_run_removes_it_and_finalizes(engine, tmp_path, monkeypatch):
    fake_queue = FakeQueue()
    fake_entry = FakeRQJob()
    monkeypatch.setattr(enqueue, "job_queue", fake_queue)
    monkeypatch.setattr(controls, "_fetch_queue_entry", lambda queue_job_id: fake_entry)
    run = publish_wire_run(engine, tmp_path)
    enqueue.enqueue_run(run.job_id, engine=engine)

    result = controls.cancel_run(run.job_id, engine=engine)

    assert (result["success"], result["state"], result["n_pending"]) == (True, "cancelled", 3)
    assert "removed from the queue" in result["message"]
    assert fake_entry.cancelled is True
    job = load_job(engine, run.job_id)
    assert (job.status, job.phase) == (JobStatus.CANCELLED, RunPhase.CANCELLED)
    assert (job.n_succeeded, job.n_failed, job.n_not_run) == (0, 0, 3)
    assert job.cancel_requested_at is not None
    assert "Cancellation requested: user" in job.messages
    assert job.finish_time is not None

    again = controls.cancel_run(run.job_id, engine=engine)
    assert (again["success"], again["state"]) == (False, "already_done")
    assert controls.cancel_run(999, engine=engine)["state"] == "not_found"
    assert not hasattr(controls, "cancel_batch_job")


def test_cancel_a_published_but_never_queued_run(engine, tmp_path, monkeypatch):
    monkeypatch.setattr(controls, "_fetch_queue_entry", lambda queue_job_id: None)
    run = publish_wire_run(engine, tmp_path)
    result = controls.cancel_run(run.job_id, engine=engine)
    assert result["state"] == "cancelled"
    assert load_job(engine, run.job_id).status == JobStatus.CANCELLED


def test_cancel_a_running_run_only_records_the_request(engine, tmp_path, monkeypatch):
    monkeypatch.setattr(enqueue, "job_queue", FakeQueue())
    run = publish_wire_run(engine, tmp_path)
    enqueue.enqueue_run(run.job_id, engine=engine)
    with Session(engine) as session, session.begin():
        job = session.get(db_schema.Job, run.job_id)
        execution.mark_running(job)
        execution.record_progress(job, succeeded=1, failed=0)

    result = controls.cancel_run(run.job_id, engine=engine)

    assert (result["success"], result["state"], result["n_pending"]) == (True, "requested", 2)
    assert "2 input(s) pending" in result["message"]
    assert "keeps completed results" in result["message"]
    job = load_job(engine, run.job_id)
    assert (job.status, job.phase) == (JobStatus.RUNNING, RunPhase.RUNNING)  # the executor finalizes
    assert job.cancel_requested_at is not None
    first_request = job.cancel_requested_at
    controls.cancel_run(run.job_id, engine=engine)
    assert load_job(engine, run.job_id).cancel_requested_at == first_request


def test_move_run_to_front_reorders_only_queued_runs(engine, tmp_path, monkeypatch):
    fake_queue = FakeQueue()
    monkeypatch.setattr(enqueue, "job_queue", fake_queue)
    monkeypatch.setattr(controls, "job_queue", fake_queue)
    first = publish_wire_run(engine, tmp_path, name="first")
    second = publish_wire_run(engine, tmp_path, name="second")
    enqueue.enqueue_run(first.job_id, engine=engine)
    enqueue.enqueue_run(second.job_id, engine=engine)
    monkeypatch.setattr(controls, "_fetch_queue_entry", lambda queue_job_id: FakeRQJob(is_queued=True))

    result = controls.move_run_to_front(second.job_id, engine=engine)

    assert result["success"] is True and "ahead of the other queued runs" in result["message"]
    assert fake_queue.removed == [f"run_{second.job_id}"]
    assert fake_queue.pushed == [(f"run_{second.job_id}", True)]

    monkeypatch.setattr(controls, "_fetch_queue_entry", lambda queue_job_id: FakeRQJob(is_queued=False))
    assert controls.move_run_to_front(first.job_id, engine=engine)["message"].endswith("no queued entry to move")
    with Session(engine) as session, session.begin():
        execution.mark_running(session.get(db_schema.Job, first.job_id))
    running = controls.move_run_to_front(first.job_id, engine=engine)
    assert running["success"] is False and "nothing to move" in running["message"]
    assert controls.move_run_to_front(999, engine=engine)["message"] == "Job 999 not found"
    assert not hasattr(controls, "move_batch_to_front")


def test_reconciliation_marks_dead_runs_interrupted_and_leaves_live_ones(engine, tmp_path, monkeypatch):
    monkeypatch.setattr(enqueue, "job_queue", FakeQueue())
    stale = publish_wire_run(engine, tmp_path, name="stale")
    alive = publish_wire_run(engine, tmp_path, name="alive")
    lost = publish_wire_run(engine, tmp_path, name="lost")
    present = publish_wire_run(engine, tmp_path, name="present")
    published_only = publish_wire_run(engine, tmp_path, name="published")
    for run in (stale, alive, lost, present):
        enqueue.enqueue_run(run.job_id, engine=engine)
    now = datetime(2026, 9, 16, 12, 0, 0)
    with Session(engine) as session, session.begin():
        stale_job = session.get(db_schema.Job, stale.job_id)
        execution.mark_running(stale_job, now=now - timedelta(minutes=30))
        execution.record_progress(stale_job, succeeded=1, failed=1, now=now - timedelta(minutes=20))
        alive_job = session.get(db_schema.Job, alive.job_id)
        execution.mark_running(alive_job, now=now - timedelta(minutes=30))
        execution.heartbeat(alive_job, now=now - timedelta(seconds=10))

    reconciled = lifecycle.reconcile_interrupted_runs(
        engine,
        stale_after_seconds=300,
        queue_entry_exists=lambda queue_job_id: queue_job_id != f"run_{lost.job_id}",
        now=now,
    )

    assert sorted(reconciled) == sorted([stale.job_id, lost.job_id])
    stale_job = load_job(engine, stale.job_id)
    assert (stale_job.status, stale_job.phase) == (JobStatus.FAILED, RunPhase.INTERRUPTED)
    assert (stale_job.n_succeeded, stale_job.n_failed, stale_job.n_not_run) == (1, 1, 1)
    assert "no heartbeat since" in stale_job.messages
    lost_job = load_job(engine, lost.job_id)
    assert (lost_job.status, lost_job.phase) == (JobStatus.FAILED, RunPhase.INTERRUPTED)
    assert lost_job.n_not_run == 3
    assert "queue entry" in lost_job.messages
    assert load_job(engine, alive.job_id).status == JobStatus.RUNNING
    assert load_job(engine, present.job_id).phase == RunPhase.QUEUED
    assert load_job(engine, published_only.job_id).phase == RunPhase.PUBLISHED

    # Reconciliation never re-enqueues or resumes: a second pass changes nothing.
    assert lifecycle.reconcile_interrupted_runs(engine, stale_after_seconds=300, now=now) == []


def test_reconciliation_skips_queue_checks_that_fail(engine, tmp_path, monkeypatch):
    monkeypatch.setattr(enqueue, "job_queue", FakeQueue())
    run = publish_wire_run(engine, tmp_path)
    enqueue.enqueue_run(run.job_id, engine=engine)

    def broken(queue_job_id):
        raise ConnectionError("redis down")

    assert lifecycle.reconcile_interrupted_runs(engine, stale_after_seconds=300, queue_entry_exists=broken) == []
    assert load_job(engine, run.job_id).phase == RunPhase.QUEUED
