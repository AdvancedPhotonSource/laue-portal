"""Small independent observations of a Flow and its PBS allocation.

The DM monitor owns probe task IDs; the portal only consumes the saved snapshot.
Scientific completion and publication remain the existing poller's responsibility.
"""

from __future__ import annotations

from datetime import datetime, timezone

PHASE_LABELS = {"uplink": "Uplink", "queued": "Queued", "running": "Running", "downlink": "Downlink"}


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def age_seconds(value, now=None):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return None
        return max(0, ((now or datetime.now(timezone.utc)) - parsed).total_seconds())
    except (TypeError, ValueError):
        return None


def read_run_status(submission_id):
    """Registered on a separate login-node endpoint; never submits scientific work."""
    import json
    import os
    import pathlib
    import re
    import subprocess
    from datetime import datetime, timezone
    from uuid import UUID

    identifier = str(UUID(submission_id))
    root = pathlib.Path(os.environ["LAUE_BDP_OBSERVER_ROOT"]).resolve(strict=True)
    run = (root / identifier).resolve()
    if run.parent != root or run.name != identifier:
        raise ValueError("Run must be directly inside the configured observer root")

    def read(name):
        path = (run / "results" / name).resolve()
        if not path.is_relative_to(run):
            raise ValueError("Status file escapes its run")
        try:
            with path.open("rb") as handle:
                payload = handle.read(65537)
        except FileNotFoundError:
            return None
        if len(payload) > 65536:
            raise ValueError("Status file exceeds 64 KiB")
        result = json.loads(payload)
        if not isinstance(result, dict):
            raise ValueError("Status must be a JSON object")
        return result

    pbs = read("pbs.json")
    progress = read("progress.json")
    summary = read("run.json")
    result = {
        "submission_id": identifier,
        "observed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "receipt_present": pbs is not None,
        "pbs": {
            k: v
            for k, v in (pbs or {}).items()
            if k in {"job_id", "status", "exit_status", "function_started_at", "submitted_at", "observed_at"}
        },
    }
    if summary:
        if summary.get("submission_id") != identifier:
            raise ValueError("Run summary identity differs from the requested run")
        result["summary_status"] = summary.get("status")
    if progress:
        result["progress"] = {k: progress[k] for k in ("heartbeat_at", "n_succeeded", "n_failed") if k in progress}
    job_id = result["pbs"].get("job_id")
    if job_id:
        if not isinstance(job_id, str) or not re.fullmatch(r"[0-9]+(?:\.[A-Za-z0-9_.-]+)?", job_id):
            raise ValueError("Invalid recorded PBS ID")
        command = str(pathlib.Path(os.environ.get("LAUE_PBS_BIN", "/opt/pbs/bin")) / "qstat")
        try:
            response = subprocess.run(
                [command, "-xf", "-F", "json", job_id],
                capture_output=True,
                text=True,
                timeout=8,
                env={**os.environ, "TZ": "UTC"},
            )
            if response.returncode:
                raise RuntimeError("PBS status unavailable")
            jobs = json.loads(response.stdout)["Jobs"]
            record = jobs[job_id] if job_id in jobs else next(iter(jobs.values()))
            result["pbs"].update(status=record["job_state"], exit_status=record.get("Exit_status"))
            result["scheduler_observed_at"] = result["observed_at"]
            for source, target in (("qtime", "submitted_at"), ("stime", "started_at"), ("obittime", "finished_at")):
                value = record.get(source)
                if value:
                    if isinstance(value, (int, float)):
                        stamp = datetime.fromtimestamp(value, timezone.utc)
                    else:
                        stamp = datetime.strptime(value, "%a %b %d %H:%M:%S %Y").replace(tzinfo=timezone.utc)
                    result["pbs"][target] = stamp.isoformat(timespec="seconds")
        except (subprocess.SubprocessError, OSError, ValueError, KeyError, StopIteration, RuntimeError):
            result["scheduler_error"] = "PBS status unavailable"
    return result


def compute_client(client):
    """Reuse the DM launcher's existing personal or confidential authorization."""
    from globus_compute_sdk import Client
    from globus_compute_sdk.serialize import DillCodeSource
    from globus_sdk.scopes import ComputeScopes

    manager = client.login_manager
    options = {"code_serialization_strategy": DillCodeSource(), "do_version_check": False}
    app = getattr(manager, "globus_app", None)
    if app is not None:
        return Client(app=app, **options)
    return Client(authorizer=manager.get_manager_authorizers()[str(ComputeScopes.all)], **options)


def refresh_observer(plan, state, settings, client, *, now=None):
    """Advance one persisted probe without waiting for its execution in this call."""
    config = settings.get("targets", {}).get("crux", {}).get("observer", {})
    if not config.get("endpoint_id") or not config.get("function_id"):
        return
    now = now or datetime.now(timezone.utc)
    try:
        if state.get("observer_task_id"):
            task = client.get_task(state["observer_task_id"])
            if task.get("pending", True):
                return
            state.pop("observer_task_id")
            result = task.get("result")
            if not isinstance(result, dict) or result.get("submission_id") != plan["submission_id"]:
                raise ValueError("Observer returned an invalid run identity")
            if age_seconds(result.get("observed_at"), now) is None:
                raise ValueError("Observer returned no valid timestamp")
            previous = state.get("observer_result", {})
            if not previous or result["observed_at"] >= previous.get("observed_at", ""):
                state["observer_result"] = result
            state.pop("observer_error", None)
            return
        elapsed = age_seconds(state.get("observer_requested_at"), now)
        if elapsed is not None and elapsed < max(10, config.get("interval_seconds", 30)):
            return
        state["observer_requested_at"] = now.isoformat(timespec="seconds")
        state["observer_task_id"] = str(
            client.run(plan["submission_id"], endpoint_id=config["endpoint_id"], function_id=config["function_id"])
        )
    except Exception as error:
        # A failed observation is not evidence that scientific work has failed.
        # Task execution errors are terminal for this read-only probe; service
        # errors retain its ID so a restart does not build a probe backlog.
        import logging

        logging.getLogger(__name__).warning("Observer unavailable for %s", plan["submission_id"], exc_info=True)
        state["observer_error"] = "Status unavailable"
        from globus_compute_sdk.errors import TaskExecutionFailed

        if isinstance(error, TaskExecutionFailed):
            state.pop("observer_task_id", None)


def flow_observation(record):
    """Extract bounded fields from the Flow's current action statuses."""
    actions = record.get("details", {}).get("action_statuses", [])
    for action in reversed(actions):
        if action.get("state_name") in {"InputTransfer", "RunPbsJob", "ResultTransfer"}:
            result = {"state": action["state_name"], "action_status": action.get("status")}
            details = action.get("details", {})
            for key in ("task_id", "bytes_transferred", "files_transferred", "total_estimated_bytes"):
                if key in details:
                    result[key] = details[key]
            return result
    if record.get("status") == "SUCCEEDED":
        return {"state": "ResultTransfer", "action_status": "SUCCEEDED"}
    return {}


def derive_remote_phase(flow, observation, *, previous=None, now=None, stale_seconds=90):
    """Four display phases, independent of the job's authoritative lifecycle."""
    now = now or datetime.now(timezone.utc)
    state = flow.get("state")
    previous = previous or {}
    result = {
        "phase": previous.get("phase", "queued"),
        "detail": "Awaiting workflow",
        "observed_at": now.isoformat(timespec="seconds"),
    }
    if state == "InputTransfer":
        result.update(phase="uplink", detail="Transferring inputs")
    elif state == "ResultTransfer":
        result.update(phase="downlink", detail="Returning results")
    elif state == "RunPbsJob":
        result.update(phase="queued", detail="Waiting for endpoint")
        same_action = previous.get("flow_state") == "RunPbsJob"
        age = age_seconds((observation or {}).get("observed_at"), now)
        terminal_receipt = (observation or {}).get("pbs", {}).get("status") == "F"
        if age is None or (age > stale_seconds and not terminal_receipt):
            waiting = age_seconds(previous.get("phase_since"), now) if same_action else 0
            result.update(
                phase=previous.get("phase", "queued") if same_action else "queued",
                detail=previous.get("detail", "Waiting for status") if same_action else "Waiting for status",
                stale=age is not None or (waiting is not None and waiting > stale_seconds),
            )
        else:
            pbs = observation.get("pbs", {})
            status = pbs.get("status")
            result.update(observer_observed_at=observation["observed_at"], pbs=pbs)
            if observation.get("scheduler_error"):
                result.update(
                    phase=previous.get("phase", "queued") if same_action else "queued",
                    detail="PBS status unavailable",
                    stale=True,
                )
            elif status in {"R", "E", "B"}:
                result.update(phase="running", detail="Processing" if status == "R" else "Finishing processing")
            elif status == "F":
                result.update(phase="downlink", detail="Awaiting result return")
            elif status in {"Q", "H", "W", "T", "S", "U", "submitted"}:
                result["detail"] = "Waiting for PBS allocation"
                if status == "H":
                    result["detail"] = "Held in PBS"
            elif observation.get("receipt_present"):
                result["detail"] = "Submitting to PBS"
            if observation.get("progress"):
                result["remote_progress"] = observation["progress"]
    result["flow_state"] = state
    for key in ("task_id", "bytes_transferred", "files_transferred", "total_estimated_bytes"):
        if key in flow:
            result[key] = flow[key]
    if previous.get("phase") == result["phase"]:
        result["phase_since"] = previous.get("phase_since", result["observed_at"])
    else:
        result["phase_since"] = result["observed_at"]
    return result
