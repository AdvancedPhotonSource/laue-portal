"""Exercise generic deployment tools using temporary paths and fake executables."""

import json
import os
import runpy
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def tool(name):
    return runpy.run_path(str(ROOT / "deploy" / name))


def site(tmp_path):
    root = tmp_path / "operator's installation"
    source = root / "src"
    (source / "deploy").mkdir(parents=True)
    shutil.copy2(ROOT / "deploy/dm-stage.sh", source / "deploy/dm-stage.sh")
    python = root / "envs/custom/python"
    python.parent.mkdir(parents=True)
    python.write_text(
        f"#!{sys.executable}\n"
        "import json,os,sys\n"
        "from pathlib import Path\n"
        "Path(os.environ['RECEIPT']).write_text(json.dumps({'args':sys.argv[1:],'source':os.environ['PYTHONPATH']}))\n"
    )
    python.chmod(0o700)
    return {
        "dm": {
            "owner": "test-owner",
            "user_account": "test-executor",
            "workflow": "test-analysis",
            "cancel_workflow": "test-cancel",
            "launcher_code": str(source),
            "launcher_python": str(python),
            "launcher_config": str(root / "config/private settings.yaml"),
        }
    }


def test_rendered_workflow_executes_wrapper_with_quoted_site_paths(tmp_path):
    settings = site(tmp_path)
    output = tmp_path / "private definitions"
    files = tool("render-workflows.py")["render_workflows"](settings, output)
    assert len(files) == 2
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in files)
    main = json.loads((output / "workflow-bdp.json").read_text())
    cancel = json.loads((output / "workflow-bdp-cancel.json").read_text())
    assert (main["name"], main["owner"], main["userAccount"]) == ("test-analysis", "test-owner", "test-executor")
    assert cancel["name"] == "test-cancel"
    assert "$cancelSubmissionId" in cancel["stages"]["01-CANCEL"]["command"]
    receipt = tmp_path / "receipt.json"
    identifier = "00000000-0000-0000-0000-000000000001"
    subprocess.run(
        ["bash", "-c", main["stages"]["01-SUBMIT"]["command"]],
        env={**os.environ, "submissionId": identifier, "RECEIPT": str(receipt)},
        check=True,
        capture_output=True,
        text=True,
    )
    invocation = json.loads(receipt.read_text())
    assert invocation["source"] == settings["dm"]["launcher_code"]
    assert invocation["args"] == [
        "-m",
        "laue_portal.processing.bdp.stage",
        "--config",
        settings["dm"]["launcher_config"],
        "submit",
        identifier,
    ]


def test_renderer_preserves_existing_definition_without_partial_output(tmp_path):
    settings = site(tmp_path)
    output = tmp_path / "private"
    output.mkdir()
    existing = output / "workflow-bdp-cancel.json"
    existing.write_bytes(b"existing configuration\n")
    with pytest.raises(FileExistsError):
        tool("render-workflows.py")["render_workflows"](settings, output)
    assert existing.read_bytes() == b"existing configuration\n"
    assert not (output / "workflow-bdp.json").exists()


def test_renderer_rejects_site_output_inside_checkout(tmp_path):
    with pytest.raises(ValueError, match="outside the source checkout"):
        tool("render-workflows.py")["render_workflows"](site(tmp_path), ROOT / "site-definitions")


def endpoint_environment(tmp_path):
    bin_directory = tmp_path / "endpoint env/bin"
    bin_directory.mkdir(parents=True)
    hostname = bin_directory / "hostname"
    hostname.write_text("#!/bin/sh\nprintf '%s\\n' test-node\n")
    hostname.chmod(0o700)
    endpoint = bin_directory / "globus-compute-endpoint"
    endpoint.write_text(
        f"#!{sys.executable}\n"
        "import json,os,sys\n"
        "with open(os.environ['RECEIPT'],'a') as handle: handle.write(json.dumps(sys.argv[1:])+'\\n')\n"
    )
    endpoint.chmod(0o700)
    return {
        **os.environ,
        "LAUE_ENDPOINT_ENV": str(bin_directory.parent),
        "LAUE_ENDPOINT_NAME": "test endpoint",
        "LAUE_ENDPOINT_HOST": "test-node",
        "RECEIPT": str(tmp_path / "endpoint-calls.jsonl"),
    }


def test_endpoint_control_uses_configured_environment_and_name(tmp_path):
    env = endpoint_environment(tmp_path)
    for action in ["start", "stop", "list"]:
        subprocess.run(
            ["bash", str(ROOT / "deploy/globus/endpoint.sh"), action],
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
    calls = [json.loads(line) for line in Path(env["RECEIPT"]).read_text().splitlines()]
    assert calls == [["start", "--detach", "test endpoint"], ["list"], ["stop", "test endpoint"], ["list"]]


def test_endpoint_control_rejects_another_host_before_invoking_service(tmp_path):
    env = endpoint_environment(tmp_path)
    env["LAUE_ENDPOINT_HOST"] = "another-node"
    result = subprocess.run(
        ["bash", str(ROOT / "deploy/globus/endpoint.sh"), "start"], env=env, capture_output=True, text=True
    )
    assert result.returncode != 0
    assert not Path(env["RECEIPT"]).exists()


def test_endpoint_probe_checks_supplied_paths(tmp_path):
    probe = tool("globus/endpoint_smoke.py")["endpoint_probe"]
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    python, qsub = tmp_path / "python", tmp_path / "qsub"
    python.touch()
    qsub.touch()
    assert all(
        probe(workspace, python, qsub)[key] for key in ["workspace_exists", "analysis_python_exists", "qsub_exists"]
    )
    python.unlink()
    assert probe(workspace, python, qsub)["analysis_python_exists"] is False


def test_vm_verifier_accepts_batched_flow_with_unauthenticated_state(tmp_path, monkeypatch):
    monkeypatch.delenv("GLADIER_CLIENT_ID", raising=False)
    monkeypatch.delenv("GLADIER_CLIENT_SECRET", raising=False)
    states = tool("verify-dm-vm.py")["verify_flow"]({"auth_profile": "personal"}, tmp_path)
    assert {"InitInputTransfer", "MoreInputTransfers", "InputsReady", "RunPbsJob", "ResultTransfer"} <= set(states)
