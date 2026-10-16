"""DM stage commands. Submission IDs locate plans; form values never enter shell commands."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from laue_portal.processing.bdp.plan import submission_path
from laue_portal.processing.bdp.settings import load_settings
from laue_portal.workflows.manifest import write_json_file


def configure_auth(settings):
    """Read existing credentials into this process only; never modify or print them."""
    if settings.get("auth_profile", "personal") == "personal":
        os.environ.pop("GLADIER_CLIENT_ID", None)
        os.environ.pop("GLADIER_CLIENT_SECRET", None)
        return
    path = settings["credentials_file"]
    result = subprocess.run(
        [
            "/bin/bash",
            "-c",
            'source "$1"; printf "%s\\0%s" "$GLADIER_CLIENT_ID" "$GLADIER_CLIENT_SECRET"',
            "bash",
            path,
        ],
        check=True,
        capture_output=True,
    )
    values = result.stdout.split(b"\0")
    if len(values) != 2 or not all(values):
        raise ValueError("The existing credentials file did not provide both Gladier credentials")
    os.environ["GLADIER_CLIENT_ID"], os.environ["GLADIER_CLIENT_SECRET"] = (v.decode() for v in values)


def _client(settings):
    from laue_portal.processing.bdp.flow import client_class

    configure_auth(settings)
    Path(settings["state_directory"]).mkdir(parents=True, exist_ok=True, mode=0o700)
    os.umask(0o077)
    return client_class(settings)()


def submit(plan, settings):
    state = Path(settings["state_directory"]) / f"{plan['submission_id']}.json"
    state.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if state.exists():
        raise FileExistsError("This submission was already attempted; inspect its saved state before retrying")
    # Also retain an uncertain state when a network request succeeds but its reply is lost.
    write_json_file(state, {"status": "SUBMISSION_UNCERTAIN"})
    if plan["backend"] == "crux":
        from laue_portal.processing.bdp.flow import flow_input

        client = _client(settings)
        record = client.run_flow(
            flow_input(plan),
            label=f"Laue {plan['submission_id'][:8]}",
            tags=["aps", "34IDE", "LauePortal", plan["submission_id"]],
        )
        run_id = record["action_id"]
        data = {"status": "RUNNING", "flow_id": run_id, "url": f"https://app.globus.org/runs/{run_id}"}
    else:
        import shlex

        from laue_portal.processing.bdp.pbs import build_script

        path = Path(plan["control_directory"]) / "job.pbs"
        Path(plan["output_directory"]).mkdir(parents=True, exist_ok=False)
        with open(path, "x", encoding="utf-8") as handle:
            handle.write(build_script(plan))
        command = ["/opt/pbs/bin/qsub", "-o", str(Path(plan["output_directory"]) / "pbs-output.log"), str(path)]
        host = plan["target"].get("submit_host")
        if host:
            command = ["ssh", "-T", "-o", "BatchMode=yes", host, shlex.join(command)]
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=60)
        data = {"status": "RUNNING", "pbs_id": result.stdout.strip()}
    write_json_file(state, data, overwrite=True)
    return data


def monitor(plan, settings):
    state = Path(settings["state_directory"]) / f"{plan['submission_id']}.json"
    data = json.loads(state.read_text())
    if data.get("flow_id"):
        record = _client(settings).get_status(data["flow_id"])
        data["status"] = record["status"]
    elif data.get("pbs_id"):
        import shlex

        command = ["/opt/pbs/bin/qstat", "-xf", "-F", "json", data["pbs_id"]]
        if plan["target"].get("submit_host"):
            command = ["ssh", "-T", "-o", "BatchMode=yes", plan["target"]["submit_host"], shlex.join(command)]
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
        record = next(iter(json.loads(result.stdout)["Jobs"].values()))
        if record["job_state"] == "F":
            data["status"] = "SUCCEEDED" if record.get("Exit_status") == 0 else "FAILED"
    else:
        raise ValueError("Submission has no returned remote ID; manual reconciliation is required")
    write_json_file(state, data, overwrite=True)
    return data


def cancel(plan, settings):
    if plan["backend"] == "crux":
        import globus_sdk
        from globus_sdk.scopes import TransferScopes

        client = _client(settings)
        manager = client.login_manager
        manager.add_requirements([TransferScopes.all])
        authorizer = manager.get_manager_authorizers()[str(TransferScopes.all)]
        transfer = globus_sdk.TransferClient(authorizer=authorizer)
        spec = plan["cancel_transfer"]
        payload = globus_sdk.TransferData(
            source_endpoint=spec["source_endpoint_id"],
            destination_endpoint=spec["destination_endpoint_id"],
            verify_checksum=True,
            sync_level="checksum",
        )
        for item in spec["transfer_items"]:
            payload.add_item(**item)
        result = transfer.submit_transfer(payload)
        if not transfer.task_wait(result["task_id"], timeout=45):
            raise TimeoutError("Cancellation marker transfer is still pending")
        if transfer.get_task(result["task_id"])["status"] != "SUCCEEDED":
            raise RuntimeError("Cancellation marker transfer failed")
        return {"status": "CANCEL_REQUESTED"}
    import shlex

    state = json.loads((Path(settings["state_directory"]) / f"{plan['submission_id']}.json").read_text())
    command = ["/opt/pbs/bin/qdel", state["pbs_id"]]
    if plan["target"].get("submit_host"):
        command = ["ssh", "-T", "-o", "BatchMode=yes", plan["target"]["submit_host"], shlex.join(command)]
    subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
    return {"status": "CANCEL_REQUESTED"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("action", choices=["submit", "monitor", "check", "cancel", "auth"])
    parser.add_argument("submission_id", nargs="?")
    args = parser.parse_args()
    settings = load_settings(args.config)
    if args.action == "auth":
        from laue_portal.processing.bdp.auth import authorize

        client = _client(settings)
        result = authorize(client, settings)
        print("Authorization ready.")
        print(f"Flow ID: {result['flow_id']}")
        for name, function_id in result["function_ids"].items():
            print(f"Compute function {name}: {function_id}")
        return 0
    plan = json.loads(submission_path(settings, args.submission_id).read_text())
    if args.action == "check":
        state = json.loads((Path(settings["state_directory"]) / f"{plan['submission_id']}.json").read_text())
        if state["status"] != "SUCCEEDED":
            return 1
        summary_path = Path(plan.get("incoming_directory", plan["output_directory"])) / "run.json"
        return 0 if json.loads(summary_path.read_text())["status"] == "Finished" else 1
    data = {"submit": submit, "monitor": monitor, "cancel": cancel}[args.action](plan, settings)
    print(f"Status: {data['status']}")
    if data.get("flow_id"):
        print(f"Flow Action ID: {data['flow_id']}")
        print(f"URL: {data['url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
