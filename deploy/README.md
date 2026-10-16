# DM and Globus deployment

The portal freezes a request and manifest, then submits a DM workflow. The
launcher transfers inputs, invokes Globus Compute to submit and monitor PBS,
and returns results. Science runs in the allocation; the portal validates
artifacts before publication. Local processing uses Redis/RQ unless its DM
execution target is enabled.

## Source and environments

| Component | Source |
| --- | --- |
| Requests and lifecycle | `laue_portal/workflows/` |
| DM, Globus, PBS, return publication | `laue_portal/processing/bdp/` |
| Native adapters and standalone/MPI runners | `laue_portal/processing/` |
| DM workflow templates and launcher | `deploy/workflow-bdp*.json.template`, `dm-stage.sh` |
| Compute endpoint control and probe | `deploy/globus/` |

Deploy the same reviewed source revision to the enabled execution components.
Install the appropriate recipe in each environment:

| Recipe | Purpose |
| --- | --- |
| `requirements.txt` | Portal and local processing |
| `deploy/requirements-aps.txt` | Combined portal/launcher package set with Supervisor |
| `deploy/requirements-workflows.txt` | Smaller Globus launcher environment |
| `deploy/requirements-compute.txt` | Native analysis and MPI runtime |

Use Python 3.12 and the [native build prerequisites](../README.md#setup).
Install regular lauelab wheels without editable links to a development checkout.
The launcher and portal can share a package recipe while retaining independent
installed copies. The analysis and Compute endpoint environments remain separate.

## Private configuration

Keep filled-in configuration and the site runbook outside the checkout, backed
up privately. Published templates contain example values only. YAML values are
literal; environment variables are not expanded automatically.

Copy `config.yaml.template` and `deploy/bdp.yaml.template` to private files and set:

- Portal database, experiment root, output templates, Redis, and web settings.
  Keep SQLite and Redis persistence on local SSD and Dash debug mode disabled.
- `BDP.enabled` and `BDP.settings_file` in the portal configuration; enabled
  execution targets in the BDP configuration.
- DM owner, workflow names, setup script, and launcher source/Python/config paths.
  `dm.user_account` optionally overrides the workflow owner's execution account.
- Transfer collection IDs and filesystem/collection-root mappings, Compute
  endpoint ID, workspace, module commands, and explicit PBS/worker resources.

Export `LAUE_PORTAL_CONFIG` for portal services and `LAUE_BDP_CONFIG` for launcher
commands. Use `dm.ssh_host: null` on the DM API host, or configure an SSH bridge
when needed. The portal need not have direct Globus connectivity. Input and
calibration files must lie inside the configured experiment; outputs belong
beneath its `analysis/` directory.

Keep software and small operational files under an installation root with
`src/`, `envs/`, `config/`, `state/`, and `logs/`. Scientific data belongs in the
configured experiment and compute workspace. `dm-stage.sh` derives its default
installation root from its own location and expects `src/` and
`envs/laue-portal/`; `LAUE_PORTAL_ROOT`, `LAUE_PORTAL_SOURCE`, and
`LAUE_PORTAL_PYTHON` provide overrides.

## Database and authorization

Migrate to a new database file; preserve the source:

```bash
python scripts/migrate_workflow_database.py "$SOURCE_DB" "$DESTINATION_DB"
python scripts/cutover_check.py --db "$DESTINATION_DB" --no-redis
```

Review the report before switching configuration. Drain old workers and queues,
then run the cutover check with Redis enabled before starting the new worker.
Never mix old per-input workers with whole-run workers.

Choose personal or confidential beamline authentication in private configuration.
The identity needs permission to run the endpoint and access both collections.
Reference an existing credential file for the beamline profile; never copy it
into the checkout. From the launcher installation, authorize and register the
Globus flow/function:

```bash
"$LAUE_PORTAL_SOURCE/deploy/dm-stage.sh" auth
```

This obtains service/flow/collection consent without transferring data or
submitting PBS jobs. Preserve the private auth cache, Gladier registration
files, and per-submission UUID records across source/environment updates.
Keep private state directories mode `0700`.

## DM registration and services

Render workflow JSON using the private BDP configuration:

```bash
python deploy/render-workflows.py --config "$LAUE_BDP_CONFIG" --output-dir "$LAUE_WORKFLOW_DEFINITIONS"
```

The renderer writes outside the source checkout, refuses existing definitions,
and does not register workflows. It fills owner/account, workflow names, and
quoted launcher commands. Register the rendered files using DM administrative
tooling. DM uses the frozen shared `request.json` as its input-file specification;
the manifest selects scientific inputs. Cancellation has a separate UUID argument.

Configure [Supervisor](../supervisor/README.md), then enable `bdp_poller` after
authorization, workflow registration, and database cutover. One reconciliation pass:

```bash
python -m laue_portal.processing.bdp.poller --once
```

## Endpoint tools

Keep endpoint settings in the private deployment environment:

- `LAUE_ENDPOINT_ENV`: endpoint environment prefix.
- `LAUE_ENDPOINT_NAME`: configured endpoint name.
- `LAUE_ENDPOINT_HOST`: configured short hostname, required for start/stop.
- Optional `LAUE_ENDPOINT_TMPDIR` and `LAUE_PBS_BIN`: temporary directory and PBS binaries.

`bash deploy/globus/endpoint.sh start|stop|list` uses those settings and checks
the host before starting or stopping the endpoint. The endpoint YAML template
contains generic service settings. Probe explicitly supplied paths from an
authenticated launcher without requesting nodes or transferring data:

```bash
python deploy/globus/endpoint_smoke.py "$COMPUTE_ENDPOINT_ID" --workspace "$COMPUTE_WORKSPACE" --analysis-python "$ANALYSIS_PYTHON"
```

## Execution and state

Each run uses checksummed input batches, one PBS job, and one result transfer.
Compact manifests and at most 100 files per batch bound Flows state. Node count,
walltime, allocation, queue, and worker counts are configured explicitly.

MPI distributes reconstruction points across nodes. Indexing keeps a point's
depths on one node and distributes them among its ranks. Each rank has a private
writer; the coordinator checks host distribution and validates merged outputs.
Indexing merges use lauelab's public HDF5/XML APIs. Failed shards prevent a
complete result. Estimates use numeric calibration profiles and include remote
round-trip transfer while excluding queue wait.

Run directories retain manifests, summaries, rank records, and scheduler logs.
Returned paths are translated to the originating storage before publication.
The portal shows workflow state and scientific counters after return. Cancellation
delivers a marker to the scheduler monitor, which requests `qdel`; uncertain
submissions are reconciled without automatic resubmission.

There is no automatic workspace cleanup. Retain remote run directories until
returned results are validated and retention requirements are met. Preserve
active/uncertain submission records, the portal database, queue persistence,
and private authorization state independently of source control.

## Validation

```bash
python -m pytest tests/ workflow_tests/  # Includes optional launcher dependencies.
python deploy/verify-dm-vm.py --root "$LAUE_PORTAL_ROOT" --config "$LAUE_BDP_CONFIG" --network
```

The verifier checks the installed environment against its private source
manifest and generated batched flow without authorizing or submitting jobs.
After deployment changes, run small reconstruction/indexing tests through each
enabled target and verify returned files as the portal account before scaling up.
