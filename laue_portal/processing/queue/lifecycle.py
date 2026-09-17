"""Run lifecycle support for the executor: heartbeat, progress persistence, cleanup, reconciliation.

Every database write here goes through ``laue_portal.workflows.execution`` so
the counters stay consistent. The monitor thread owns its own sessions; the
progress recorder runs on the executor's thread.
"""

from __future__ import annotations

import logging
import os
import signal
import threading
import time
from collections.abc import Callable
from datetime import datetime, timedelta

import psutil
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from laue_portal.database import db_schema
from laue_portal.processing.queue.core import RunPolicy
from laue_portal.workflows import execution
from laue_portal.workflows.execution import JobStatus, RunPhase

logger = logging.getLogger(__name__)

STOP_REASON_CANCELLED = "cancelled"
STOP_REASON_SHUTDOWN = "shutdown"

# The worker sends this to its horse when the service is asked to stop; the
# executor then stops admitting inputs, drains, and finalizes as interrupted.
SHUTDOWN_SIGNAL = signal.SIGUSR1


class RunMonitor(threading.Thread):
    """Background heartbeat and cancellation polling for one running job.

    The heartbeat continues while the compute is inside a long native call, so
    a stale heartbeat always means the run process is gone. ``stop_requested``
    becomes True when the job's persisted cancellation flag is set or when the
    executor receives the shutdown signal.
    """

    def __init__(self, engine: Engine, job_id: int, policy: RunPolicy, *, clock: Callable[[], float] = time.monotonic):
        super().__init__(name=f"run-monitor-{job_id}", daemon=True)
        self._engine = engine
        self._job_id = job_id
        self._policy = policy
        self._clock = clock
        self._closed = threading.Event()
        self._cancel = threading.Event()
        self._shutdown = threading.Event()
        self.heartbeats = 0
        self.errors: list[str] = []

    @property
    def stop_requested(self) -> bool:
        return self._cancel.is_set() or self._shutdown.is_set()

    @property
    def stop_reason(self) -> str | None:
        if self._shutdown.is_set():
            return STOP_REASON_SHUTDOWN
        if self._cancel.is_set():
            return STOP_REASON_CANCELLED
        return None

    def request_shutdown(self) -> None:
        self._shutdown.set()

    def poll(self) -> None:
        """One heartbeat write plus one cancellation check; called periodically and on demand."""

        try:
            with Session(self._engine) as session, session.begin():
                job = session.get(db_schema.Job, self._job_id)
                if job is None:
                    return
                if job.cancel_requested_at is not None:
                    self._cancel.set()
                if not execution.is_terminal(job):
                    execution.heartbeat(job)
                    self.heartbeats += 1
        except Exception as error:  # the run must not die because a heartbeat write failed
            self.errors.append(str(error))
            logger.warning("Run %s heartbeat failed: %s", self._job_id, error)

    def run(self) -> None:
        interval = min(self._policy.heartbeat_seconds, self._policy.cancel_poll_seconds)
        next_heartbeat = self._clock()
        while not self._closed.is_set():
            now = self._clock()
            if now >= next_heartbeat:
                self.poll()
                next_heartbeat = now + self._policy.heartbeat_seconds
            elif not self._cancel.is_set():
                self._check_cancellation()
            self._closed.wait(interval)

    def _check_cancellation(self) -> None:
        try:
            with Session(self._engine) as session:
                flag = session.scalar(
                    select(db_schema.Job.cancel_requested_at).where(db_schema.Job.job_id == self._job_id)
                )
            if flag is not None:
                self._cancel.set()
        except Exception as error:
            self.errors.append(str(error))

    def close(self, timeout: float = 10.0) -> None:
        self._closed.set()
        if self.is_alive():
            self.join(timeout)


class ProgressRecorder:
    """Rate-limited persistence of absolute processed counts."""

    def __init__(
        self, engine: Engine, job_id: int, interval_seconds: float, *, clock: Callable[[], float] = time.monotonic
    ):
        self._engine = engine
        self._job_id = job_id
        self._interval = interval_seconds
        self._clock = clock
        self._last_flush = clock()
        self.succeeded = 0
        self.failed = 0
        self.flushes = 0
        self.errors: list[str] = []

    def report(self, *, succeeded: int, failed: int) -> None:
        if succeeded < self.succeeded or failed < self.failed:
            raise execution.ExecutionStateError(
                f"progress went backwards: {succeeded}/{failed} after {self.succeeded}/{self.failed}"
            )
        self.succeeded = int(succeeded)
        self.failed = int(failed)
        if self._clock() - self._last_flush >= self._interval:
            self.flush()

    def flush(self) -> None:
        self._last_flush = self._clock()
        try:
            with Session(self._engine) as session, session.begin():
                job = session.get(db_schema.Job, self._job_id)
                if job is not None and job.phase in (RunPhase.RUNNING, RunPhase.FINALIZING):
                    execution.record_progress(job, succeeded=self.succeeded, failed=self.failed)
                    self.flushes += 1
        except Exception as error:
            self.errors.append(str(error))
            logger.warning("Run %s progress write failed: %s", self._job_id, error)


_HELPER_MARKERS = ("multiprocessing.resource_tracker", "multiprocessing.semaphore_tracker")


def _is_helper_process(process: psutil.Process) -> bool:
    """Python's multiprocessing trackers are not compute work and exit with their parent."""

    try:
        command = " ".join(process.cmdline())
    except psutil.Error:
        return False
    return any(marker in command for marker in _HELPER_MARKERS)


def terminate_descendants(grace_seconds: float = 5.0) -> int:
    """Terminate every descendant of this process; returns how many had to be dealt with."""

    try:
        children = [child for child in psutil.Process().children(recursive=True) if not _is_helper_process(child)]
    except psutil.Error:
        return 0
    if not children:
        return 0
    for child in children:
        try:
            child.terminate()
        except psutil.Error:
            pass
    _, alive = psutil.wait_procs(children, timeout=grace_seconds)
    for child in alive:
        try:
            child.kill()
        except psutil.Error:
            pass
    psutil.wait_procs(alive, timeout=grace_seconds)
    return len(children)


def sweep_process_group(pgid: int) -> bool:
    """Kill everything left in a finished work horse's process group; True when something was there."""

    if not pgid or pgid == os.getpid() or pgid == os.getpgid(0):
        return False
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        return False
    except PermissionError:
        logger.warning("Could not sweep process group %s", pgid)
        return False
    return True


def reconcile_interrupted_runs(
    engine: Engine,
    *,
    stale_after_seconds: float,
    queue_entry_exists: Callable[[str], bool] | None = None,
    now: datetime | None = None,
) -> list[int]:
    """Mark runs that cannot still be alive as interrupted; never resumes or re-enqueues them.

    A Running job whose heartbeat is older than ``stale_after_seconds`` lost its
    process. A Queued job whose queue entry no longer exists (for example after
    a Redis restart) can never be started. Both become Failed with the
    ``interrupted`` phase and their counters account for all inputs.
    """

    moment = now or datetime.now()
    stale_before = moment - timedelta(seconds=stale_after_seconds)
    reconciled = []
    with Session(engine) as session, session.begin():
        candidates = session.scalars(
            select(db_schema.Job).where(db_schema.Job.status.in_((int(JobStatus.QUEUED), int(JobStatus.RUNNING))))
        ).all()
        for job in candidates:
            reason = None
            if job.status == JobStatus.RUNNING:
                last_sign = job.heartbeat_at or job.start_time or job.updated_at
                if last_sign is None or last_sign < stale_before:
                    reason = (
                        f"Interrupted: no heartbeat since {last_sign.isoformat(timespec='seconds') if last_sign else 'start'}; "
                        f"the run process is gone and the run is not resumed"
                    )
            elif job.phase == RunPhase.QUEUED and queue_entry_exists is not None and job.queue_job_id:
                try:
                    present = queue_entry_exists(job.queue_job_id)
                except Exception as error:
                    logger.warning("Could not check queue entry %s: %s", job.queue_job_id, error)
                    continue
                if not present:
                    reason = f"Interrupted: queue entry {job.queue_job_id} no longer exists; the run is not re-enqueued"
            if reason is None:
                continue
            execution.finalize(job, status=JobStatus.FAILED, message=reason, phase=RunPhase.INTERRUPTED, now=moment)
            reconciled.append(job.job_id)
            logger.warning("Job %s reconciled as interrupted: %s", job.job_id, reason)
    return reconciled
