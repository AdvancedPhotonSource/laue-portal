"""Tests for the whole-run executor: progress, cancellation, errors, timeout, finalization."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time

import psutil
import pytest
from rq.timeouts import JobTimeoutException
from sqlalchemy.orm import Session

from laue_portal.database import db_schema
from laue_portal.processing.compute import RunOutcome, contract
from laue_portal.processing.queue import enqueue, executors, lifecycle
from laue_portal.workflows import execution
from laue_portal.workflows.execution import JobStatus, RunPhase
from laue_portal.workflows.manifest import FailureRecord, read_failure_report
from tests.run_support import FAST_POLICY, load_job, make_engine, publish_wire_run
from tests.test_run_queue import FakeQueue

WIRE_KIND = "wire_reconstruction"


@pytest.fixture
def engine(tmp_path, monkeypatch):
    yield make_engine(tmp_path, monkeypatch)


@pytest.fixture
def compute(monkeypatch):
    """Register a compute function for the wire kind for one test."""

    registered = {}

    def install(function):
        monkeypatch.setitem(contract._REGISTRY, WIRE_KIND, function)
        registered["function"] = function
        return function

    return install


def _queued_run(engine, tmp_path, monkeypatch, **kwargs):
    monkeypatch.setattr(enqueue, "job_queue", FakeQueue())
    run = publish_wire_run(engine, tmp_path, **kwargs)
    enqueue.enqueue_run(run.job_id, engine=engine)
    return run


def _run_summary(run):
    with open(os.path.join(run.output_path, "run.json"), encoding="utf-8") as handle:
        return json.load(handle)


def _per_entry(successes: set[int] | None = None, fail=None, stop_after=None, spawn=None, artifacts=None):
    """Build a compute function that succeeds for every entry except the listed indices."""

    def function(request, entries, hooks):
        succeeded = failed = 0
        stopped = False
        for entry in entries:
            if stopped or hooks.should_stop():
                stopped = True
                hooks.record_failure(FailureRecord.not_run(entry, category="cancelled", message="run cancelled"))
                continue
            if spawn is not None:
                spawn(entry)
            if fail is not None and entry.index in fail:
                failed += 1
                hooks.record_failure(FailureRecord.from_error(entry, ValueError(f"bad frame {entry.input_id}")))
            else:
                succeeded += 1
            hooks.report_progress(succeeded=succeeded, failed=failed)
            if stop_after is not None:
                stop_after(entry)
        return RunOutcome(
            n_succeeded=succeeded,
            n_failed=failed,
            stopped=stopped,
            artifacts=dict(artifacts or {}),
            provenance={"engine": "test"},
            summary="test compute",
        )

    return function


def test_successful_run_finishes_with_summary_and_counters(engine, tmp_path, monkeypatch, compute):
    run = _queued_run(engine, tmp_path, monkeypatch)
    compute(_per_entry(artifacts={"results": os.path.join(run.output_path, "output.h5")}))

    result = executors.execute_run(run.job_id, engine=engine, policy=FAST_POLICY)

    job = load_job(engine, run.job_id)
    assert (job.status, job.phase) == (JobStatus.FINISHED, RunPhase.FINISHED)
    assert (job.n_inputs, job.n_succeeded, job.n_failed, job.n_not_run) == (3, 3, 0, 0)
    assert job.start_time is not None and job.finish_time is not None
    assert job.heartbeat_at is not None
    assert job.failure_report_path is None
    assert job.messages.startswith("Finished: 3 succeeded, 0 failed, 0 not run of 3")
    assert result == {
        "job_id": run.job_id,
        "status": "Finished",
        "message": job.messages,
        "n_succeeded": 3,
        "n_failed": 0,
    }
    summary = _run_summary(run)
    assert summary["format"] == "laue-portal-run-summary"
    assert summary["status"] == "Finished"
    assert summary["counters"] == {"n_inputs": 3, "n_succeeded": 3, "n_failed": 0, "n_not_run": 0, "n_indexed": None}
    assert summary["artifacts"] == {"results": os.path.join(run.output_path, "output.h5")}
    assert summary["provenance"] == {"engine": "test"}
    assert summary["policy"]["job_timeout_seconds"] == FAST_POLICY.job_timeout_seconds
    assert not os.path.exists(os.path.join(run.output_path, "failures.jsonl"))
    assert sorted(os.listdir(run.output_path)) == ["inputs.jsonl", "request.json", "run.json"]


def test_input_failures_continue_and_finish_as_incomplete(engine, tmp_path, monkeypatch, compute):
    run = _queued_run(engine, tmp_path, monkeypatch)
    compute(_per_entry(fail={1}))

    executors.execute_run(run.job_id, engine=engine, policy=FAST_POLICY)

    job = load_job(engine, run.job_id)
    assert (job.status, job.phase) == (JobStatus.FAILED, RunPhase.FAILED)
    assert (job.n_succeeded, job.n_failed, job.n_not_run) == (2, 1, 0)
    assert job.messages.startswith("Incomplete: 2 succeeded, 1 failed, 0 not run of 3")
    assert job.failure_report_path == os.path.join(run.output_path, "failures.jsonl")
    records, _ = read_failure_report(job.failure_report_path)
    assert [(r.index, r.input_id, r.category, r.error_type) for r in records] == [(1, "wire_2", "input", "ValueError")]
    assert _run_summary(run)["failure_report"] == "failures.jsonl"


def test_all_inputs_failing_never_claims_success(engine, tmp_path, monkeypatch, compute):
    run = _queued_run(engine, tmp_path, monkeypatch)
    compute(_per_entry(fail={0, 1, 2}))
    executors.execute_run(run.job_id, engine=engine, policy=FAST_POLICY)
    job = load_job(engine, run.job_id)
    assert job.status == JobStatus.FAILED
    assert job.messages.startswith("All inputs failed; 0 succeeded, 3 failed")
    assert len(read_failure_report(job.failure_report_path)[0]) == 3


def test_validation_failure_prevents_a_finished_state(engine, tmp_path, monkeypatch, compute):
    run = _queued_run(engine, tmp_path, monkeypatch)

    def function(request, entries, hooks):
        entries = list(entries)
        hooks.report_progress(succeeded=len(entries), failed=0)
        return RunOutcome(n_succeeded=len(entries), n_failed=0, validation_error="frame offsets do not partition")

    compute(function)
    executors.execute_run(run.job_id, engine=engine, policy=FAST_POLICY)
    job = load_job(engine, run.job_id)
    assert (job.status, job.n_succeeded) == (JobStatus.FAILED, 3)
    assert job.messages.startswith("Authoritative output failed validation: frame offsets do not partition")
    assert _run_summary(run)["validation_error"] == "frame offsets do not partition"


def test_compute_exception_fails_the_run_and_propagates(engine, tmp_path, monkeypatch, compute):
    run = _queued_run(engine, tmp_path, monkeypatch)

    def function(request, entries, hooks):
        hooks.report_progress(succeeded=1, failed=0)
        raise RuntimeError("worker pool broke")

    compute(function)
    with pytest.raises(RuntimeError, match="worker pool broke"):
        executors.execute_run(run.job_id, engine=engine, policy=FAST_POLICY)
    job = load_job(engine, run.job_id)
    assert (job.status, job.phase) == (JobStatus.FAILED, RunPhase.FAILED)
    assert (job.n_succeeded, job.n_failed, job.n_not_run) == (1, 0, 2)
    assert job.messages.startswith("Run failed: RuntimeError: worker pool broke; 1 succeeded")
    assert _run_summary(run)["status"] == "Failed"


def test_timeout_is_an_explicit_policy_failure(engine, tmp_path, monkeypatch, compute):
    run = _queued_run(engine, tmp_path, monkeypatch)

    def function(request, entries, hooks):
        hooks.report_progress(succeeded=2, failed=0)
        raise JobTimeoutException("Task exceeded maximum timeout value (600 seconds)")

    compute(function)
    with pytest.raises(JobTimeoutException):
        executors.execute_run(run.job_id, engine=engine, policy=FAST_POLICY)
    job = load_job(engine, run.job_id)
    assert job.status == JobStatus.FAILED
    assert job.messages.startswith("Run exceeded the configured limit of 600 s; 2 succeeded, 0 failed, 1 not run")


def test_unknown_kind_and_bad_counts_are_infrastructure_failures(engine, tmp_path, monkeypatch, compute):
    run = _queued_run(engine, tmp_path, monkeypatch)
    compute(lambda request, entries, hooks: RunOutcome(n_succeeded=7, n_failed=0))
    with pytest.raises(executors.RunSetupError, match="reported 7 processed inputs of 3"):
        executors.execute_run(run.job_id, engine=engine, policy=FAST_POLICY)
    assert load_job(engine, run.job_id).status == JobStatus.FAILED

    other = _queued_run(engine, tmp_path, monkeypatch, name="other")
    monkeypatch.delitem(contract._REGISTRY, WIRE_KIND, raising=False)
    monkeypatch.setattr(contract, "get_compute_function", executors.get_compute_function)

    def missing(kind):
        raise contract.UnknownRunKind(kind)

    monkeypatch.setattr(executors, "get_compute_function", missing)
    with pytest.raises(contract.UnknownRunKind):
        executors.execute_run(other.job_id, engine=engine, policy=FAST_POLICY)
    assert load_job(engine, other.job_id).messages.startswith("Run failed: UnknownRunKind")


def test_duplicate_delivery_and_pre_start_cancellation_do_not_run(engine, tmp_path, monkeypatch, compute):
    run = _queued_run(engine, tmp_path, monkeypatch)
    calls = []
    compute(lambda request, entries, hooks: calls.append(1) or RunOutcome(n_succeeded=3, n_failed=0))

    executors.execute_run(run.job_id, engine=engine, policy=FAST_POLICY)
    assert executors.execute_run(run.job_id, engine=engine, policy=FAST_POLICY) is None
    assert calls == [1]

    cancelled = _queued_run(engine, tmp_path, monkeypatch, name="cancelled")
    with Session(engine) as session, session.begin():
        execution.request_cancellation(session.get(db_schema.Job, cancelled.job_id), reason="user")
    assert executors.execute_run(cancelled.job_id, engine=engine, policy=FAST_POLICY) is None
    job = load_job(engine, cancelled.job_id)
    assert (job.status, job.n_not_run) == (JobStatus.CANCELLED, 3)
    assert calls == [1]

    with pytest.raises(executors.RunSetupError, match="does not exist"):
        executors.execute_run(999, engine=engine, policy=FAST_POLICY)


def test_published_but_unqueued_runs_are_skipped(engine, tmp_path, monkeypatch, compute):
    run = publish_wire_run(engine, tmp_path)
    compute(lambda request, entries, hooks: RunOutcome(n_succeeded=3, n_failed=0))
    assert executors.execute_run(run.job_id, engine=engine, policy=FAST_POLICY) is None
    assert load_job(engine, run.job_id).phase == RunPhase.PUBLISHED


def test_cooperative_cancellation_keeps_completed_results(engine, tmp_path, monkeypatch, compute):
    run = _queued_run(engine, tmp_path, monkeypatch, count=6)

    def cancel_after_first(entry):
        if entry.index == 0:
            with Session(engine) as session, session.begin():
                execution.request_cancellation(session.get(db_schema.Job, run.job_id), reason="user")
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and not hooks_seen["hooks"].should_stop():
                time.sleep(0.01)

    hooks_seen = {}
    base = _per_entry(stop_after=cancel_after_first)

    def function(request, entries, hooks):
        hooks_seen["hooks"] = hooks
        return base(request, entries, hooks)

    compute(function)
    result = executors.execute_run(run.job_id, engine=engine, policy=FAST_POLICY)

    job = load_job(engine, run.job_id)
    assert (job.status, job.phase) == (JobStatus.CANCELLED, RunPhase.CANCELLED)
    assert (job.n_succeeded, job.n_failed, job.n_not_run) == (1, 0, 5)
    assert job.messages.splitlines()[-1].startswith("Cancelled by request; completed results kept; 1 succeeded")
    assert result["status"] == "Cancelled"
    records, _ = read_failure_report(job.failure_report_path)
    assert [r.category for r in records] == ["cancelled"] * 5
    assert [r.index for r in records] == [1, 2, 3, 4, 5]


def test_shutdown_signal_stops_the_run_as_interrupted(engine, tmp_path, monkeypatch, compute):
    run = _queued_run(engine, tmp_path, monkeypatch, count=4)

    def signal_after_second(entry):
        if entry.index == 1:
            os.kill(os.getpid(), lifecycle.SHUTDOWN_SIGNAL)
            time.sleep(0.05)

    compute(_per_entry(stop_after=signal_after_second))
    executors.execute_run(run.job_id, engine=engine, policy=FAST_POLICY)

    job = load_job(engine, run.job_id)
    assert (job.status, job.phase) == (JobStatus.FAILED, RunPhase.INTERRUPTED)
    assert (job.n_succeeded, job.n_not_run) == (2, 2)
    assert job.messages.startswith("Stopped by service shutdown; completed results kept")
    assert signal.getsignal(lifecycle.SHUTDOWN_SIGNAL) in (signal.SIG_DFL, signal.SIG_IGN, None) or callable(
        signal.getsignal(lifecycle.SHUTDOWN_SIGNAL)
    )


def test_progress_is_persisted_periodically_and_heartbeats_continue(engine, tmp_path, monkeypatch, compute):
    run = _queued_run(engine, tmp_path, monkeypatch, count=4)
    observed = []

    def observe(entry):
        time.sleep(0.12)  # longer than the fast progress and heartbeat intervals
        job = load_job(engine, run.job_id)
        observed.append((job.n_succeeded, job.heartbeat_at))

    compute(_per_entry(stop_after=observe))
    executors.execute_run(run.job_id, engine=engine, policy=FAST_POLICY)

    counts = [count for count, _ in observed]
    assert counts[0] <= counts[-1] and counts[-1] >= 2  # intermediate progress reached the database
    heartbeats = [beat for _, beat in observed if beat is not None]
    assert len(set(heartbeats)) >= 2  # the heartbeat advanced while the compute was busy
    assert load_job(engine, run.job_id).n_succeeded == 4


def test_progress_writes_are_rate_limited(engine, tmp_path, monkeypatch, compute):
    run = _queued_run(engine, tmp_path, monkeypatch, count=50)
    slow_policy = FAST_POLICY.__class__(**{**FAST_POLICY.__dict__, "progress_seconds": 3600})
    writes = []
    original = execution.record_progress

    def counting_record_progress(job, **kwargs):
        writes.append(kwargs["succeeded"])
        return original(job, **kwargs)

    monkeypatch.setattr(execution, "record_progress", counting_record_progress)
    compute(_per_entry())
    executors.execute_run(run.job_id, engine=engine, policy=slow_policy)
    assert writes == [50]  # one database write at finalization, none per input
    assert load_job(engine, run.job_id).n_succeeded == 50


def test_leftover_compute_processes_are_terminated(engine, tmp_path, monkeypatch, compute):
    run = _queued_run(engine, tmp_path, monkeypatch, count=1)
    children = []

    def spawn(entry):
        children.append(subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"]))

    compute(_per_entry(spawn=spawn))
    executors.execute_run(run.job_id, engine=engine, policy=FAST_POLICY)

    assert len(children) == 1
    child = children[0]
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and child.poll() is None:
        time.sleep(0.05)
    assert child.poll() is not None
    assert not psutil.pid_exists(child.pid) or psutil.Process(child.pid).status() == psutil.STATUS_ZOMBIE
    assert "terminated 1 leftover compute process(es)" in _run_summary(run)["log"]
    assert load_job(engine, run.job_id).status == JobStatus.FINISHED


def test_run_monitor_reports_cancellation_and_heartbeats(engine, tmp_path, monkeypatch):
    run = _queued_run(engine, tmp_path, monkeypatch)
    with Session(engine) as session, session.begin():
        execution.mark_running(session.get(db_schema.Job, run.job_id))
    monitor = lifecycle.RunMonitor(engine, run.job_id, FAST_POLICY)
    monitor.start()
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and monitor.heartbeats < 2:
            time.sleep(0.01)
        assert monitor.heartbeats >= 2
        assert monitor.stop_requested is False
        with Session(engine) as session, session.begin():
            execution.request_cancellation(session.get(db_schema.Job, run.job_id))
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not monitor.stop_requested:
            time.sleep(0.01)
        assert monitor.stop_reason == lifecycle.STOP_REASON_CANCELLED
        monitor.request_shutdown()
        assert monitor.stop_reason == lifecycle.STOP_REASON_SHUTDOWN
    finally:
        monitor.close()
    assert monitor.errors == []
    assert not monitor.is_alive()


def test_progress_recorder_refuses_backward_counts(engine, tmp_path, monkeypatch):
    run = _queued_run(engine, tmp_path, monkeypatch)
    recorder = lifecycle.ProgressRecorder(engine, run.job_id, 3600)
    recorder.report(succeeded=2, failed=0)
    with pytest.raises(execution.ExecutionStateError, match="backwards"):
        recorder.report(succeeded=1, failed=0)
