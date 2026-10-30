"""Add compact runtime estimates to both execution choices, including ALCF transfers."""

import dash
from dash import Input, Output

from laue_portal.config import DEFAULT_VARIABLES, RUN_EXECUTION
from laue_portal.processing.bdp.settings import available_backends, portal_settings
from laue_portal.services.runtime_estimates import estimate_runtime, estimate_transfers, format_duration

ALCF_OVERHEAD_SECONDS = 15 * 60


def compact_duration(seconds):
    if seconds < 60:
        return "<1m"
    return format_duration(seconds).replace(" h", "h").replace(" min", "m")


def register_runtime_estimate(kind):
    fields = ["root_path", "data_path", "filenamePrefix", "scanPoints", "IDnumber"]
    if kind == "indexing":
        fields += ["depthRange"]
    else:
        fields += ["depth_start", "depth_end", "depth_resolution", "frame_skip", "wire_skip"]

    @dash.callback(
        Output(f"{kind}-execution-target", "options"),
        Output(f"{kind}-execution-selector", "title"),
        *[Input(field, "value") for field in fields],
    )
    def update_estimates(*values):
        parameters = dict(zip(fields, values, strict=True))
        settings = portal_settings()
        options = available_backends(settings)
        details = ["Actual queue/startup time varies."]
        for option in options:
            backend, label = option["value"], option["label"]
            policy = {**RUN_EXECUTION, "threads_per_worker": DEFAULT_VARIABLES.get("num_threads", 1)}
            target = settings.get("targets", {}).get(backend, {})
            if backend in {"aps", "crux"}:
                policy = {**target.get("execution", {}), "nodes": target.get("pbs", {}).get("nodes", 1)}
            try:
                estimate = estimate_runtime(kind, backend, parameters, policy=policy)
            except (ValueError, OSError) as error:
                details.append(str(error))
                continue
            total_seconds = estimate.seconds
            if backend in {"local", "aps"} and kind == "reconstruction":
                details.append(
                    f"APS: {policy.get('reconstruction_workers', 1)} workers × "
                    f"{policy.get('threads_per_worker', 1)} threads; projected from profiling."
                )
            if backend == "crux":
                transfer = estimate_transfers(kind, estimate.selection)
                overhead_seconds = ALCF_OVERHEAD_SECONDS * estimate.runs
                total_seconds += transfer.seconds + overhead_seconds
                details.append(
                    f"ALCF: {compact_duration(estimate.seconds)} processing + "
                    f"{compact_duration(transfer.seconds)} round-trip transfer + "
                    f"{compact_duration(overhead_seconds)} overhead allowance; {policy.get('nodes', 1)} nodes."
                )
            option["label"] = f"{label} ({compact_duration(total_seconds)})"
            walltime = target.get("pbs", {}).get("walltime")
            if walltime:
                hours, minutes, seconds = map(int, walltime.split(":"))
                limit = hours * 3600 + minutes * 60 + seconds
                if estimate.seconds > limit:
                    details.append(f"{label}: exceeds the {compact_duration(limit)} allocation.")
        return options, "\n".join(dict.fromkeys(details))

    return update_estimates
