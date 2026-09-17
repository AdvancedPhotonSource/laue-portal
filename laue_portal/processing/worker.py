#!/usr/bin/env python
"""
RQ worker that executes whole runs for the Laue Portal.

One worker processes one run at a time; run one worker per host unless the
host is provisioned for more. Before taking work the worker reconciles runs
that can no longer be alive (stale heartbeat, lost queue entry). On the first
stop signal it asks the running horse to stop cooperatively, waits for it to
drain and finalize, then exits; a second signal is RQ's cold shutdown, which
kills the horse's whole process group. After a horse exits abnormally, anything
left in its process group is killed so compute descendants never outlive a run.

Usage:
    python -m laue_portal.processing.worker
    python -m laue_portal.processing.worker --burst  # Process jobs and exit
    python -m laue_portal.processing.worker --name custom-worker-1
"""

import argparse
import logging
import os
import socket
import sys

from rq import Worker
from rq.job import Job as RQJob

import laue_portal.database.session_utils as session_utils
from laue_portal.processing.queue.core import RUN_POLICY, job_queue, redis_conn
from laue_portal.processing.queue.lifecycle import SHUTDOWN_SIGNAL, reconcile_interrupted_runs, sweep_process_group

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


WORKER_NAME_PREFIX = "laue-run"


def default_worker_name() -> str:
    """``laue-run-<host>-<pid>``: the prefix marks a whole-run worker for the cutover check."""

    return f"{WORKER_NAME_PREFIX}-{socket.gethostname()}-{os.getpid()}"


class LaueWorker(Worker):
    """RQ worker with cooperative run shutdown and process-group cleanup."""

    def request_stop(self, signum, frame):
        if self.horse_pid:
            try:
                os.kill(self.horse_pid, SHUTDOWN_SIGNAL)
                self.log.warning(
                    "Worker %s: asked run process %s to stop; waiting up to %s s for it to drain",
                    self.name,
                    self.horse_pid,
                    RUN_POLICY.shutdown_grace_seconds,
                )
            except ProcessLookupError:
                pass
        super().request_stop(signum, frame)

    def monitor_work_horse(self, job, queue):
        horse_pid = self.horse_pid
        try:
            super().monitor_work_horse(job, queue)
        finally:
            if sweep_process_group(horse_pid):
                self.log.warning("Worker %s: killed processes left behind by run process %s", self.name, horse_pid)


def queue_entry_exists(queue_job_id: str) -> bool:
    return RQJob.exists(queue_job_id, connection=redis_conn)


def reconcile_on_startup() -> list[int]:
    reconciled = reconcile_interrupted_runs(
        session_utils.get_engine(),
        stale_after_seconds=RUN_POLICY.stale_heartbeat_seconds,
        queue_entry_exists=queue_entry_exists,
    )
    if reconciled:
        logger.warning("Reconciled %d interrupted run(s): %s", len(reconciled), reconciled)
    return reconciled


def main():
    """Main worker entry point."""
    parser = argparse.ArgumentParser(description="Start an RQ worker for Laue Portal runs")
    parser.add_argument("--burst", action="store_true", help="Run in burst mode (process all jobs and exit)")
    parser.add_argument("--name", type=str, default=None, help="Custom name for this worker")
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level",
    )

    args = parser.parse_args()

    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    reconcile_on_startup()

    worker = LaueWorker(
        [job_queue],
        connection=redis_conn,
        name=args.name or default_worker_name(),
        log_job_description=True,
        disable_default_exception_handler=False,
    )

    logger.info(f"Starting worker: {worker.name}")
    logger.info(f"Listening on queue: {job_queue.name}")
    logger.info("Run policy: %s", RUN_POLICY)

    try:
        worker.work(burst=args.burst, with_scheduler=True)
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Worker error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
