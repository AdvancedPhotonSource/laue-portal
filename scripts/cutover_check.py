#!/usr/bin/env python3
"""Preflight for the clean cutover to whole-run execution.

Checks, in order, and prints one line per check:

1. The database named in config.yaml (or ``--db``) has the compact schema, every
   column the current models define, and no per-input ``subjob`` table.
2. No run is left in a non-runnable intermediate phase (``created``); Queued or
   Running rows are listed so they can be drained or reconciled first.
3. ``RUN_EXECUTION`` is configured and ``workers`` is set explicitly.
4. Redis is reachable; the queue holds only whole-run entries (``run_<job_id>``
   executing ``execute_run``); every worker on the queue is a whole-run worker
   (name prefixed ``laue-run``). Any other worker is an old per-chunk worker and
   must be stopped before the new worker starts. ``--no-redis`` skips this step.

Exit status 0 when every check passes, 1 otherwise. Nothing is modified.
"""

from __future__ import annotations

import argparse
import contextlib
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str

    def line(self) -> str:
        return f"[{'ok' if self.ok else 'FAIL'}] {self.name}: {self.detail}"


def check_database(db_path: Path) -> list[Check]:
    from scripts.workflow_migration import (
        MigrationError,
        detect_schema_stage,
        missing_columns,
        required_nullable_columns,
    )

    if not db_path.is_file():
        return [Check("database", False, f"{db_path} does not exist")]
    checks = []
    with contextlib.closing(sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)) as connection:
        try:
            stage = detect_schema_stage(connection)
        except MigrationError as error:
            return [Check("schema stage", False, str(error))]
        if stage != "compact":
            checks.append(
                Check(
                    "schema stage",
                    False,
                    f"{stage}; run scripts/migrate_workflow_database.py to a new compact destination first",
                )
            )
            return checks
        checks.append(Check("schema stage", True, "compact (run counters on the job table)"))
        relaxed = required_nullable_columns(connection)
        checks.append(Check(
            "optional peak limit",
            not relaxed,
            "nullable" if not relaxed else "peak limit is NOT NULL; run the upgrade migration",
        ))
        missing = missing_columns(connection)
        checks.append(
            Check(
                "model columns",
                not missing,
                "all present" if not missing else f"missing {', '.join(missing)}; run the upgrade migration",
            )
        )
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if "subjob" in tables:
            rows = connection.execute("SELECT COUNT(*) FROM subjob").fetchone()[0]
            checks.append(
                Check("per-input table", False, f"subjob table still exists ({rows} rows); run the upgrade migration")
            )
        else:
            checks.append(Check("per-input table", True, "no subjob table"))
        created = connection.execute("SELECT COUNT(*) FROM job WHERE phase = 'created'").fetchone()[0]
        checks.append(
            Check(
                "unpublished runs",
                created == 0,
                "none" if created == 0 else f"{created} job(s) in phase 'created' can never run; fail them explicitly",
            )
        )
        active = connection.execute(
            "SELECT job_id, status, phase FROM job WHERE status IN (0, 1) ORDER BY job_id"
        ).fetchall()
        if active:
            listed = ", ".join(f"job {job_id} ({phase})" for job_id, _, phase in active)
            checks.append(
                Check(
                    "active runs",
                    False,
                    f"{len(active)} queued/running: {listed}; drain them or let the new worker reconcile them",
                )
            )
        else:
            checks.append(Check("active runs", True, "none queued or running"))
    return checks


def check_config() -> list[Check]:
    from laue_portal import config

    execution = config.RUN_EXECUTION or {}
    checks = []
    if not execution:
        checks.append(Check("RUN_EXECUTION", False, "section missing from config.yaml"))
        return checks
    workers = execution.get("workers")
    checks.append(
        Check(
            "RUN_EXECUTION.workers",
            isinstance(workers, int) and workers > 0,
            f"{workers}" if workers else "not set; set it to the host's physical cores minus two",
        )
    )
    timeout = execution.get("job_timeout_seconds")
    checks.append(Check("RUN_EXECUTION.job_timeout_seconds", bool(timeout), f"{timeout}" if timeout else "not set"))
    return checks


def check_queue(prefix: str) -> list[Check]:
    from rq import Worker
    from rq.job import Job as RQJob
    from rq.registry import StartedJobRegistry

    from laue_portal.processing.queue import core as queue_core

    if not queue_core.check_redis_connection():
        host = queue_core.REDIS_CONFIG.get("host", "localhost")
        return [Check("redis", False, f"cannot reach {host}:{queue_core.REDIS_CONFIG.get('port')}")]
    checks = [Check("redis", True, f"connected to {queue_core.REDIS_CONFIG.get('host', 'localhost')}")]

    queued_ids = queue_core.job_queue.job_ids
    started_ids = StartedJobRegistry(queue=queue_core.job_queue).get_job_ids()
    foreign = []
    for rq_id in [*queued_ids, *started_ids]:
        if not rq_id.startswith(f"{queue_core.RUN_JOB_TYPE}_"):
            foreign.append(rq_id)
            continue
        try:
            entry = RQJob.fetch(rq_id, connection=queue_core.redis_conn)
        except Exception:
            foreign.append(rq_id)
            continue
        if not (entry.func_name or "").endswith("execute_run"):
            foreign.append(f"{rq_id} ({entry.func_name})")
    checks.append(
        Check(
            "queue entries",
            not foreign,
            f"{len(queued_ids)} queued, {len(started_ids)} started, all whole-run entries"
            if not foreign
            else f"{len(foreign)} per-chunk or unknown entries: {', '.join(foreign[:10])}",
        )
    )

    workers = Worker.all(connection=queue_core.redis_conn)
    old = [worker.name for worker in workers if not worker.name.startswith(prefix)]
    new = [worker.name for worker in workers if worker.name.startswith(prefix)]
    checks.append(
        Check(
            "workers",
            not old,
            f"{len(new)} whole-run worker(s), no others"
            if not old
            else f"{len(old)} worker(s) without the '{prefix}' prefix must be stopped first: {', '.join(old[:10])}",
        )
    )
    return checks


def run_checks(*, db_path: Path, include_redis: bool, prefix: str) -> list[Check]:
    checks = check_database(db_path)
    checks.extend(check_config())
    if include_redis:
        checks.extend(check_queue(prefix))
    return checks


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, default=None, help="Database to check (default: db_file in config.yaml)")
    parser.add_argument("--no-redis", action="store_true", help="Skip the queue and worker checks")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    from laue_portal import config
    from laue_portal.processing.worker import WORKER_NAME_PREFIX

    db_path = args.db if args.db is not None else Path(config.db_file)
    checks = run_checks(db_path=db_path, include_redis=not args.no_redis, prefix=WORKER_NAME_PREFIX)
    for check in checks:
        print(check.line())
    failed = [check for check in checks if not check.ok]
    print("Cutover preflight:", "ready" if not failed else f"{len(failed)} check(s) failed")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
