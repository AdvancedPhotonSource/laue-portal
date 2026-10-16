# Portal services

Supervisor manages the Dash server, optional Redis server, and one RQ worker.
The optional `bdp_poller` reconciles DM jobs and publishes validated returns;
it is disabled by default. Web host/port and processing limits come from the
portal configuration. Keep `DASH_CONFIG.debug: false` for deployed servers.

## Setup

Install Supervisor (included in `deploy/requirements-aps.txt`). Pass an environment
name or path; its `bin/` directory must contain Python and, for managed Redis,
`redis-server`. Use `--no-redis` when Redis is provided separately.

```bash
./supervisor/setup_supervisor.sh /path/to/environment
export LAUE_PORTAL_CONFIG=/path/to/config/portal.yaml
./supervisor/start_supervisor.sh
```

Configuration is generated from `supervisord.conf.template` and
`redis.conf.template`. Generated config, sockets, PID files, and logs stay local.
The daemon inherits the selected configuration. See [deployment](../deploy/README.md)
for database cutover, DM registration, and Globus authorization before enabling
remote execution.

## Management

```bash
./supervisor/manage_supervisor.sh status
./supervisor/manage_supervisor.sh restart 'laue-portal:dash'
./supervisor/manage_supervisor.sh restart 'laue-portal:rq_worker_00'
./supervisor/manage_supervisor.sh stop 'laue-portal:*'
./supervisor/manage_supervisor.sh start 'laue-portal:*'
./supervisor/manage_supervisor.sh tail -f 'laue-portal:rq_worker_00'
# Enable only after completing DM/Globus setup:
./supervisor/manage_supervisor.sh start bdp_poller
./supervisor/manage_supervisor.sh shutdown
```

`bdp_poller` is outside the `laue-portal` group. Supervisor's `start all` also
starts disabled programs, so use the group command for portal-only operation.

## Worker lifecycle and storage

One queue item is a complete run. Keep one worker per host unless resources
support concurrent runs; `RUN_EXECUTION` bounds each run's child processes and
wall-clock lifetime. Whole-run worker names begin with `laue-run-`.

Before switching from older workers, run `python scripts/cutover_check.py`.
Old per-input workers, incompatible queue entries, and unmigrated databases must
be resolved first. Never mix worker generations against the same Redis/database.

The first stop signal drains work in flight, keeps completed output, and records
the run as interrupted. `stopwaitsecs` must cover
`RUN_EXECUTION.shutdown_grace_seconds`. A second signal or forced timeout kills
the run's process group; the next worker reconciles stale runs without resuming
or re-enqueuing them. Wait for shutdown before restarting a named worker.

Keep SQLite and Redis persistence on the host's local disk. Service logs use
`supervisor/logs/`, with 10 MiB files and five backups; the Supervisor daemon log
uses its own limits. Keep the configured log and Redis directories writable.

## Troubleshooting

Check `manage_supervisor.sh status` and the affected service's log first. Confirm
the environment binaries, selected configuration, filesystem permissions, and
Redis address. If the daemon is gone but left stale control files, use
`cleanup_supervisor.sh` before `start_supervisor.sh`; inspect active jobs before
stopping or cleaning up any running service.
