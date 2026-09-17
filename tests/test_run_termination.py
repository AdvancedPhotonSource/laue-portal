"""Hard-termination tests with real processes.

A run process (standing in for the RQ work horse) is started in its own process
group with a compute that spawns a grandchild and then blocks. The tests kill it
in the ways a worker or the OS would and check that compute descendants do not
survive and that the database never keeps a dead run Running.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import psutil
from sqlalchemy import create_engine

from laue_portal.processing.queue import lifecycle
from laue_portal.workflows.execution import JobStatus, RunPhase
from tests.run_support import load_job

PROJECT_ROOT = Path(__file__).resolve().parents[1]

RUN_SCRIPT = textwrap.dedent(
    """
    import os, subprocess, sys, time, json
    from unittest.mock import patch

    db_file, run_dir_parent, marker = sys.argv[1], sys.argv[2], sys.argv[3]
    with patch("laue_portal.config.db_file", db_file):
        from laue_portal.database import session_utils
        session_utils.init_db()
        engine = session_utils.get_engine()
        from pathlib import Path
        from laue_portal.processing.compute import RunOutcome, contract
        from laue_portal.processing.queue import enqueue, executors
        from laue_portal.workflows.manifest import FailureRecord
        from tests.run_support import FAST_POLICY, publish_wire_run
        from tests.test_run_queue import FakeQueue

        def compute(request, entries, hooks):
            child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"])
            Path(marker).write_text(json.dumps({"grandchild": child.pid, "run": os.getpid()}))
            succeeded = 0
            for entry in entries:
                while not hooks.should_stop():
                    time.sleep(0.02)  # block until cancelled, shut down, or killed
                hooks.record_failure(FailureRecord.not_run(entry, message="stopped"))
            return RunOutcome(n_succeeded=succeeded, n_failed=0, stopped=True)

        contract._REGISTRY["wire_reconstruction"] = compute
        enqueue.job_queue = FakeQueue()
        run = publish_wire_run(engine, Path(run_dir_parent), count=2)
        enqueue.enqueue_run(run.job_id, engine=engine)
        Path(marker + ".job").write_text(str(run.job_id))
        executors.execute_run(run.job_id, engine=engine, policy=FAST_POLICY)
    """
)


def _start_run(tmp_path):
    db_file = tmp_path / "termination.db"
    marker = tmp_path / "marker.json"
    process = subprocess.Popen(
        [sys.executable, "-c", RUN_SCRIPT, str(db_file), str(tmp_path), str(marker)],
        cwd=PROJECT_ROOT,
        start_new_session=True,  # like an RQ work horse: its own process group
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline and not marker.exists():
        if process.poll() is not None:
            raise AssertionError(f"run process exited early: {process.communicate()[1]}")
        time.sleep(0.05)
    assert marker.exists(), "run process never started its compute"
    import json

    info = json.loads(marker.read_text())
    job_id = int((tmp_path / "marker.json.job").read_text())
    engine = create_engine(f"sqlite:///{db_file}")
    _wait_for(lambda: load_job(engine, job_id).status == JobStatus.RUNNING)
    return process, info["grandchild"], job_id, engine


def _wait_for(condition, timeout=15.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.05)
    return condition()


def _alive(pid):
    return psutil.pid_exists(pid) and psutil.Process(pid).status() != psutil.STATUS_ZOMBIE


def _cleanup(process, grandchild):
    for pid in (grandchild, process.pid):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        process.communicate(timeout=10)
    except Exception:
        pass


def test_sigkill_of_the_run_process_is_reconciled_and_its_group_swept(tmp_path):
    process, grandchild, job_id, engine = _start_run(tmp_path)
    try:
        assert _alive(grandchild)
        os.kill(process.pid, signal.SIGKILL)
        process.wait(timeout=10)

        job = load_job(engine, job_id)
        assert job.status == JobStatus.RUNNING  # nothing could finalize it: the process is gone
        assert job.heartbeat_at is not None
        assert _alive(grandchild)  # an orphaned compute process survives the kill itself...

        # ...until the worker sweeps the horse's process group.
        assert lifecycle.sweep_process_group(process.pid) is True
        assert _wait_for(lambda: not _alive(grandchild))

        time.sleep(1.1)
        reconciled = lifecycle.reconcile_interrupted_runs(engine, stale_after_seconds=1)
        assert reconciled == [job_id]
        job = load_job(engine, job_id)
        assert (job.status, job.phase) == (JobStatus.FAILED, RunPhase.INTERRUPTED)
        assert (job.n_succeeded, job.n_failed, job.n_not_run) == (0, 0, 2)
        assert "no heartbeat since" in job.messages
        assert lifecycle.reconcile_interrupted_runs(engine, stale_after_seconds=1) == []
    finally:
        _cleanup(process, grandchild)


def test_shutdown_signal_drains_finalizes_and_kills_descendants(tmp_path):
    process, grandchild, job_id, engine = _start_run(tmp_path)
    try:
        os.kill(process.pid, lifecycle.SHUTDOWN_SIGNAL)
        stdout, stderr = process.communicate(timeout=60)
        assert process.returncode == 0, stderr
        assert not _alive(grandchild)  # terminate_descendants ran in the executor
        job = load_job(engine, job_id)
        assert (job.status, job.phase) == (JobStatus.FAILED, RunPhase.INTERRUPTED)
        assert job.n_not_run == 2
        assert job.messages.startswith("Stopped by service shutdown")
        assert os.path.exists(os.path.join(job.run_directory, "run.json"))
        assert os.path.exists(job.failure_report_path)
    finally:
        _cleanup(process, grandchild)


def test_sigterm_kills_the_run_process_without_leaving_it_running_forever(tmp_path):
    """RQ's cold shutdown kills the horse's whole group; the DB is repaired by reconciliation."""

    process, grandchild, job_id, engine = _start_run(tmp_path)
    try:
        os.killpg(process.pid, signal.SIGKILL)  # what Worker.kill_horse does
        process.wait(timeout=10)
        assert _wait_for(lambda: not _alive(grandchild))
        time.sleep(1.1)
        assert lifecycle.reconcile_interrupted_runs(engine, stale_after_seconds=1) == [job_id]
        assert load_job(engine, job_id).phase == RunPhase.INTERRUPTED
    finally:
        _cleanup(process, grandchild)


def test_sweep_never_targets_the_current_process_group():
    assert lifecycle.sweep_process_group(os.getpgid(0)) is False
    assert lifecycle.sweep_process_group(0) is False
    assert lifecycle.sweep_process_group(2**22 + 12345) is False
