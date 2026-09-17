"""Tests for run-level execution state transitions and counter consistency."""

from datetime import datetime

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from laue_portal.database import db_schema
from laue_portal.processing.queue import core
from laue_portal.workflows import execution
from laue_portal.workflows.execution import ExecutionStateError, JobStatus, RunPhase
from laue_portal.workflows.progress import RunProgress, load_progress, progress_columns

T0 = datetime(2026, 9, 16, 9, 0, 0)


def _job(n_inputs=10):
    job = db_schema.Job(job_id=1, computer_name="host", status=0, priority=0, submit_time=T0)
    execution.initialize(job, n_inputs=n_inputs, now=T0)
    return job


def _published(n_inputs=10):
    job = _job(n_inputs)
    execution.mark_published(
        job,
        run_directory="/runs/1",
        manifest_path="/runs/1/inputs.jsonl",
        manifest_digest="a" * 64,
        request_path="/runs/1/request.json",
        n_inputs=n_inputs,
        now=T0,
    )
    return job


def _running(n_inputs=10):
    job = _published(n_inputs)
    execution.mark_queued(job, "rq-1", now=T0)
    execution.mark_running(job, now=T0)
    return job


def test_status_values_match_the_queue_status_mapping():
    assert {int(status): name for status, name in execution.STATUS_NAMES.items()} == core.STATUS_MAPPING


def test_a_created_job_is_not_enqueueable_until_published():
    job = _job()
    assert (job.status, job.phase, job.n_inputs) == (JobStatus.QUEUED, RunPhase.CREATED, 10)
    with pytest.raises(ExecutionStateError, match="only published runs"):
        execution.assert_enqueueable(job)
    with pytest.raises(ExecutionStateError, match="only published runs"):
        execution.mark_queued(job, "rq-1")

    execution.mark_published(
        job,
        run_directory="/runs/1",
        manifest_path="/runs/1/inputs.jsonl",
        manifest_digest="a" * 64,
        request_path="/runs/1/request.json",
        n_inputs=10,
        now=T0,
    )
    assert job.phase == RunPhase.PUBLISHED
    assert job.manifest_digest == "a" * 64
    execution.assert_enqueueable(job)

    with pytest.raises(ExecutionStateError, match="cannot publish"):
        execution.mark_published(
            job,
            run_directory="/runs/1",
            manifest_path="x",
            manifest_digest="b" * 64,
            request_path="y",
            n_inputs=10,
        )


def test_publication_must_match_the_selected_input_count():
    job = _job(10)
    with pytest.raises(ExecutionStateError, match="holds 9 inputs"):
        execution.mark_published(
            job,
            run_directory="/runs/1",
            manifest_path="/runs/1/inputs.jsonl",
            manifest_digest="a" * 64,
            request_path="/runs/1/request.json",
            n_inputs=9,
        )


def test_queue_run_progress_and_finish_keep_counters_consistent():
    job = _published(10)
    execution.mark_queued(job, "rq-7", now=T0)
    assert (job.phase, job.queue_job_id) == (RunPhase.QUEUED, "rq-7")
    with pytest.raises(ExecutionStateError, match="only published"):
        execution.mark_queued(job, "rq-8")

    execution.mark_running(job, now=T0)
    assert (job.status, job.phase, job.start_time, job.heartbeat_at) == (JobStatus.RUNNING, RunPhase.RUNNING, T0, T0)

    later = datetime(2026, 9, 16, 9, 5, 0)
    execution.record_progress(job, succeeded=6, failed=1, now=later)
    assert (job.n_succeeded, job.n_failed, job.heartbeat_at, job.updated_at) == (6, 1, later, later)
    with pytest.raises(ExecutionStateError, match="went backwards"):
        execution.record_progress(job, succeeded=5, failed=1)
    with pytest.raises(ExecutionStateError, match="of only 10 inputs"):
        execution.record_progress(job, succeeded=9, failed=2)

    execution.mark_finalizing(job, now=later)
    execution.record_progress(job, succeeded=8, failed=1, now=later)
    execution.finalize(job, status=JobStatus.FINISHED, message="8 succeeded, 1 failed, 1 not run", now=later)
    assert (job.status, job.phase, job.finish_time) == (JobStatus.FINISHED, RunPhase.FINISHED, later)
    assert (job.n_inputs, job.n_succeeded, job.n_failed, job.n_not_run) == (10, 8, 1, 1)
    assert job.n_succeeded + job.n_failed + job.n_not_run == job.n_inputs
    assert job.messages == "8 succeeded, 1 failed, 1 not run"
    with pytest.raises(ExecutionStateError, match="already terminal"):
        execution.finalize(job, status=JobStatus.FAILED)
    with pytest.raises(ExecutionStateError, match="terminal"):
        execution.heartbeat(job)


def test_cancellation_is_requested_once_and_finalizes_with_not_run_work():
    job = _running(10)
    execution.record_progress(job, succeeded=3, failed=0, now=T0)
    assert execution.request_cancellation(job, now=T0) is True
    assert job.cancel_requested_at == T0
    later = datetime(2026, 9, 16, 9, 1, 0)
    assert execution.request_cancellation(job, now=later) is True
    assert job.cancel_requested_at == T0  # first request wins

    execution.record_progress(job, succeeded=4, failed=0, now=later)  # in-flight work drained
    execution.finalize(job, status=JobStatus.CANCELLED, message="cancelled", now=later)
    assert (job.status, job.phase) == (JobStatus.CANCELLED, RunPhase.CANCELLED)
    assert (job.n_succeeded, job.n_failed, job.n_not_run) == (4, 0, 6)
    assert execution.request_cancellation(job) is False


def test_failure_before_publication_or_start_marks_all_work_not_run():
    created = _job(5)
    execution.record_failure(created, "Run publication failed: disk full", now=T0)
    assert (created.status, created.phase, created.n_not_run, created.finish_time) == (
        JobStatus.FAILED,
        RunPhase.FAILED,
        5,
        T0,
    )
    assert created.messages == "Run publication failed: disk full"

    published = _published(5)
    execution.record_failure(published, "Enqueue failed: redis unavailable", now=T0)
    assert (published.status, published.n_not_run) == (JobStatus.FAILED, 5)
    with pytest.raises(ExecutionStateError):
        execution.assert_enqueueable(published)


def test_running_state_requires_the_queued_phase():
    job = _published()
    with pytest.raises(ExecutionStateError, match="cannot start"):
        execution.mark_running(job)
    with pytest.raises(ExecutionStateError, match="is not running"):
        execution.record_progress(job, succeeded=1, failed=0)
    with pytest.raises(ExecutionStateError, match="cannot finalize"):
        execution.mark_finalizing(job)
    with pytest.raises(ExecutionStateError, match="not a terminal status"):
        execution.finalize(_running(), status=JobStatus.RUNNING)
    with pytest.raises(ExecutionStateError, match="queue_job_id is required"):
        execution.mark_queued(_published(), "")


def test_a_cancellation_request_blocks_enqueueing():
    job = _published()
    execution.request_cancellation(job, now=T0)
    with pytest.raises(ExecutionStateError, match="pending cancellation"):
        execution.assert_enqueueable(job)


@pytest.fixture
def engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'execution.db'}")
    db_schema.Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def test_record_enqueue_failure_persists_a_failed_run(engine):
    with Session(engine) as session:
        session.add(_published(4))
        session.commit()

    assert execution.record_enqueue_failure(1, RuntimeError("redis unavailable"), engine=engine) is True
    assert execution.record_enqueue_failure(999, RuntimeError("missing"), engine=engine) is False

    with Session(engine) as session:
        job = session.get(db_schema.Job, 1)
        assert (job.status, job.phase, job.n_not_run) == (JobStatus.FAILED, RunPhase.FAILED, 4)
        assert job.messages == "Enqueue failed: redis unavailable"
        assert job.finish_time is not None
        assert job.start_time is None

    assert execution.record_enqueue_failure(1, RuntimeError("again"), engine=engine) is False
    with Session(engine) as session:
        assert session.get(db_schema.Job, 1).messages.endswith("already terminal: again")


def test_database_constraints_reject_inconsistent_counters(engine):
    with Session(engine) as session:
        job = db_schema.Job(computer_name="h", status=2, priority=0, n_inputs=3, n_succeeded=2, n_failed=2)
        session.add(job)
        with pytest.raises(IntegrityError, match="ck_job_counters_bounded"):
            session.commit()
    with Session(engine) as session:
        job = db_schema.Job(computer_name="h", status=2, priority=0, n_inputs=3, n_failed=-1)
        session.add(job)
        with pytest.raises(IntegrityError, match="ck_job_counters_non_negative"):
            session.commit()
    with Session(engine) as session:
        job = db_schema.Job(computer_name="h", status=0, priority=0)
        session.add(job)
        session.commit()
        assert (job.n_inputs, job.n_succeeded, job.n_failed, job.n_not_run) == (0, 0, 0, 0)


def test_progress_is_read_from_counters_without_per_input_rows(engine):
    with Session(engine) as session:
        job = _running(10)
        execution.record_progress(job, succeeded=6, failed=1, now=T0)
        job.failure_report_path = "/runs/1/failures.jsonl"
        job.messages = "started\nsix done"
        session.add(job)
        session.commit()

    with Session(engine) as session:
        progress = load_progress(session, 1)
        assert load_progress(session, 42) is None
        # Progress is derived from the job row alone: no per-input table exists any more.
        assert "subjob" not in inspect(engine).get_table_names()
        counters = session.query(*progress_columns()).filter(db_schema.Job.job_id == 1).one()._asdict()

    assert isinstance(progress, RunProgress)
    assert (progress.n_inputs, progress.n_succeeded, progress.n_failed, progress.n_not_run) == (10, 6, 1, 0)
    assert (progress.n_processed, progress.n_pending, progress.fraction) == (7, 3, 0.7)
    assert progress.progress_text() == "7/10"
    assert progress.status_name == "Running"
    assert progress.is_terminal is False
    assert progress.terminal_message == "six done"
    assert progress.queue_job_id == "rq-1"
    assert counters == {
        "phase": "running",
        "n_inputs": 10,
        "n_succeeded": 6,
        "n_failed": 1,
        "n_not_run": 0,
        "n_processed": 7,
        "n_pending": 3,
        "heartbeat_at": T0,
        "cancel_requested_at": None,
    }
    empty = RunProgress(job_id=2, status=0, phase=None, n_inputs=0, n_succeeded=0, n_failed=0, n_not_run=0)
    assert (empty.fraction, empty.progress_text(), empty.terminal_message) == (None, None, None)
