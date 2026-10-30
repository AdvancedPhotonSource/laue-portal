"""PBS scripts use the site's MPI launcher; the Globus task only submits and polls."""

from __future__ import annotations

import re
import shlex


def build_script(plan):
    target, pbs = plan["target"], plan["pbs"]
    nodes = int(pbs.get("nodes", 1))
    if nodes < 1 or (plan["backend"] != "crux" and nodes != 1):
        raise ValueError("Multiple nodes are supported only by the Crux MPI runner")
    ranks_per_node = (
        int(plan["execution"].get("indexing_ranks_per_node", 1)) if plan["kind"] == "lauego_indexing" else 1
    )
    if ranks_per_node < 1 or ranks_per_node > 4:
        raise ValueError("Use between one and four indexing ranks per node")
    for key in ("queue", "walltime"):
        if not re.fullmatch(r"[A-Za-z0-9_:@.+-]+", str(pbs[key])):
            raise ValueError(f"Unsafe PBS {key}")
    account = pbs.get("account")
    if plan["backend"] == "crux" and not account:
        raise ValueError("An ALCF allocation is required")
    if account and not re.fullmatch(r"[A-Za-z0-9_:@.+-]+", str(account)):
        raise ValueError("Unsafe PBS account")
    module = "laue_portal.processing.mpi_runner" if nodes * ranks_per_node > 1 else "laue_portal.processing.runner"
    command = [target["analysis_python"], "-m", module, plan["control_directory"]]
    lines = [
        "#!/bin/bash -l",
        "#PBS -N Laue",
        *([f"#PBS -A {account}"] if account else []),
        f"#PBS -q {pbs['queue']}",
        f"#PBS -l walltime={pbs['walltime']}",
        "#PBS -j oe",
    ]
    if plan["backend"] == "crux":
        lines += [f"#PBS -l select={nodes}:system=crux", "#PBS -l place=scatter", "#PBS -l filesystems=home:eagle"]
    else:
        lines += [f"#PBS -l select=1:ncpus={int(pbs.get('cpus', 32))}:ngpus=0"]
    lines += [
        "set -euo pipefail",
        ': "${PBS_JOBID:?Compute allocation required}"',
        "export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1",
        f"export PYTHONPATH={shlex.quote(target['code_directory'])}",
        f"cd {shlex.quote(plan['control_directory'])}",
    ]
    lines += list(target.get("module_commands", []))  # Administrator configuration, never form input.
    if plan["backend"] == "crux":
        # Crux's launcher must start bash, not relocate the Conda Python executable.
        launcher = [
            "mpiexec",
            "-n",
            str(nodes * ranks_per_node),
            "--ppn",
            str(ranks_per_node),
            "--cpu-bind",
            "none",
            "/bin/bash",
            "-c",
            'exec "$@"',
            "bash",
            *command,
        ]
    else:
        launcher = command
    lines.append("exec " + shlex.join(launcher))
    return "\n".join(lines) + "\n"


def run_pbs_job(*, job_directory, script, fallback_summary, cancel_file, **unused):
    """Serializable, application-independent function for the login-node endpoint.

    The task does no data processing. It submits a fixed PBS script and waits
    for the scheduler, honoring a small cancellation file while queued or running.
    """
    import json
    import pathlib
    import re
    import subprocess
    import time
    from datetime import datetime, timezone

    root = pathlib.Path(job_directory)
    output = pathlib.Path(fallback_summary["output_directory"])
    output.mkdir(parents=True, exist_ok=True)
    control = root / "control"
    script_path = control / "job.pbs"
    state_path = output / "pbs.json"
    job_id = None
    last_status = None
    submitting = False
    receipt = {"function_started_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}

    def save(path, document):
        if path == state_path:
            receipt.update(document)
            receipt["observed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            document = receipt
        partial = path.with_name(path.name + ".tmp")
        partial.write_text(json.dumps(document))
        partial.replace(path)

    try:
        save(state_path, {"status": "submitting"})
        with open(script_path, "x", encoding="utf-8") as handle:
            handle.write(script)
        submitting = True
        response = subprocess.run(
            ["/opt/pbs/bin/qsub", "-o", str(output / "pbs-output.log"), str(script_path)],
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
        submitting = False
        job_id = response.stdout.strip()
        if not re.fullmatch(r"[0-9]+(?:\.[A-Za-z0-9_.-]+)?", job_id):
            raise ValueError("PBS returned an invalid job ID")
        save(
            state_path,
            {
                "job_id": job_id,
                "status": "submitted",
                "submitted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            },
        )
        cancel_sent = False
        deadline = time.monotonic() + 48 * 3600
        while time.monotonic() < deadline:
            if pathlib.Path(cancel_file).exists() and not cancel_sent:
                subprocess.run(["/opt/pbs/bin/qdel", job_id], check=False, capture_output=True, timeout=30)
                cancel_sent = True
            state = subprocess.run(
                ["/opt/pbs/bin/qstat", "-xf", "-F", "json", job_id], capture_output=True, text=True, timeout=30
            )
            if state.returncode:
                # Never infer success from a job disappearing from scheduler history.
                raise RuntimeError(f"PBS status unavailable for {job_id}: {state.stderr[-1000:]}")
            jobs = json.loads(state.stdout)["Jobs"]
            record = next(iter(jobs.values()))
            last_status = record["job_state"]
            save(
                state_path, {"job_id": job_id, "status": record["job_state"], "exit_status": record.get("Exit_status")}
            )
            if record["job_state"] == "F":
                if not (output / "run.json").exists():
                    raise RuntimeError(
                        f"PBS job {job_id} ended with exit status {record.get('Exit_status')}; no run summary"
                    )
                return {"job_id": job_id, "exit_status": record.get("Exit_status")}
            time.sleep(5)
        subprocess.run(["/opt/pbs/bin/qdel", job_id], capture_output=True, timeout=30)
        raise TimeoutError("PBS monitoring exceeded 48 hours; cancellation was requested")
    except Exception as error:
        if isinstance(error, FileExistsError) or (submitting and isinstance(error, subprocess.TimeoutExpired)):
            save(state_path, {"status": "SUBMISSION_UNCERTAIN", "message": "Inspect PBS before any retry"})
            raise RuntimeError("PBS submission needs reconciliation; automatic resubmission is disabled") from error
        if job_id and last_status != "F":
            # Do not return a terminal summary while a previously submitted job
            # may still be writing. Request cancellation and confirm scheduler termination.
            subprocess.run(["/opt/pbs/bin/qdel", job_id], check=False, capture_output=True, timeout=30)
            confirmed = False
            for _ in range(12):
                response = subprocess.run(
                    ["/opt/pbs/bin/qstat", "-xf", "-F", "json", job_id], capture_output=True, text=True, timeout=30
                )
                if response.returncode == 0:
                    jobs = json.loads(response.stdout)["Jobs"]
                    if next(iter(jobs.values()))["job_state"] == "F":
                        confirmed = True
                        break
                time.sleep(5)
            if not confirmed:
                save(state_path, {"job_id": job_id, "status": "STATE_UNCERTAIN"})
                raise RuntimeError(f"Cannot confirm PBS job {job_id} stopped; inspect the scheduler") from error
        if not (output / "run.json").exists():
            summary = dict(fallback_summary["summary"])
            progress = output / "progress.json"
            if progress.exists():
                counts = json.loads(progress.read_text())
                succeeded, failed = counts.get("n_succeeded", 0), counts.get("n_failed", 0)
                if 0 <= succeeded + failed <= summary["counters"]["n_inputs"]:
                    summary["counters"] = {
                        **summary["counters"],
                        "n_succeeded": succeeded,
                        "n_failed": failed,
                        "n_not_run": summary["counters"]["n_inputs"] - succeeded - failed,
                    }
            summary["message"] = str(error)
            summary["status"] = "Cancelled" if pathlib.Path(cancel_file).exists() else "Failed"
            summary["phase"] = summary["status"].lower()
            # Keep the runner's final file exclusive, including races with job shutdown.
            try:
                with open(output / "run.json", "x", encoding="utf-8") as handle:
                    json.dump(summary, handle)
            except FileExistsError:
                pass
        return {"error": str(error)}  # Transfer diagnostics back even when PBS failed.


def fallback(plan):
    return {
        "output_directory": plan["output_directory"],
        "summary": {
            "format": "laue-portal-run-summary",
            "version": 1,
            "job_id": plan["job_id"],
            "submission_id": plan["submission_id"],
            "kind": plan["kind"],
            "status": "Failed",
            "phase": "failed",
            "counters": {
                "n_inputs": plan["n_inputs"],
                "n_succeeded": 0,
                "n_failed": 0,
                "n_not_run": plan["n_inputs"],
                "n_indexed": None,
            },
            "artifacts": {},
        },
    }
