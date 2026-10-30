"""Submit a read-only infrastructure check; no PBS allocation or analysis."""

import argparse
import json


def endpoint_probe(workspace, analysis_python, qsub="/opt/pbs/bin/qsub"):
    import os
    import pathlib
    import socket
    import sys

    return {
        "host": socket.gethostname(),
        "uid": os.getuid(),
        "python": sys.executable,
        "workspace_exists": pathlib.Path(workspace).is_dir(),
        "analysis_python_exists": pathlib.Path(analysis_python).is_file(),
        "qsub_exists": pathlib.Path(qsub).is_file(),
    }


if __name__ == "__main__":
    import time

    from globus_compute_sdk import Client

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("endpoint_id")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--analysis-python", required=True)
    parser.add_argument("--qsub", default="/opt/pbs/bin/qsub")
    args = parser.parse_args()
    client = Client()
    function_id = client.register_function(endpoint_probe)
    task_id = client.run(
        endpoint_id=args.endpoint_id,
        function_id=function_id,
        workspace=args.workspace,
        analysis_python=args.analysis_python,
        qsub=args.qsub,
    )
    print(json.dumps({"function_id": function_id, "task_id": task_id}), flush=True)
    for _attempt in range(60):
        status = client.get_task(task_id)
        if status.get("pending") is False:
            result = client.get_result(task_id)
            print(json.dumps(result, indent=2))
            assert result["workspace_exists"] and result["analysis_python_exists"] and result["qsub_exists"]
            break
        time.sleep(2)
    else:
        raise TimeoutError(f"Endpoint task {task_id} did not finish within two minutes")
