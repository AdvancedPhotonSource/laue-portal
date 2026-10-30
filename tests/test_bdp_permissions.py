"""Permission repair is limited to one completed Globus return, via the DM API."""

import json
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest

from laue_portal.processing.bdp import stage


@pytest.fixture
def returned(tmp_path, monkeypatch):
    identifier = str(uuid4())
    experiment = tmp_path / "operator's experiment"
    run = experiment / "analysis" / "run"
    incoming = run / "incoming" / identifier
    incoming.mkdir(parents=True)
    (incoming / "probe.txt").write_text("returned output")
    state = tmp_path / "state"
    state.mkdir()
    (state / f"{identifier}.json").write_text(json.dumps({"status": "SUCCEEDED"}))
    plan = {
        "submission_id": identifier,
        "backend": "crux",
        "run_directory": str(run),
        "incoming_directory": str(incoming),
    }
    settings = {
        "experiment_directory": str(experiment),
        "state_directory": str(state),
        "dm": {"setup_file": "/config/dm.sh", "timeout_seconds": 30},
    }
    client = Mock()
    factory = Mock(return_value=client)
    monkeypatch.setattr(stage, "DMClient", factory)
    return plan, settings, client, factory


@pytest.mark.parametrize("timeout", [None, 600])
def test_permissions_restore_exact_relative_path_using_existing_dm_setup(returned, timeout):
    plan, settings, client, factory = returned
    if timeout:
        settings["dm"]["permissions_timeout_seconds"] = timeout
    assert stage.restore_permissions(plan, settings) == {"status": "PERMISSIONS_RESTORED"}
    factory.assert_called_once_with({**settings["dm"], "timeout_seconds": timeout or 300})
    experiment = Path(settings["experiment_directory"])
    incoming = Path(plan["incoming_directory"])
    client.restore_permissions.assert_called_once_with(experiment.name, incoming.relative_to(experiment).as_posix())
    assert (incoming / "probe.txt").read_text() == "returned output"


@pytest.mark.parametrize("target", ["analysis", "data", "run", "incoming", "other_submission", "symlink"])
def test_permissions_cannot_expand_to_parent_another_submission_or_symlink(returned, target):
    plan, settings, _, factory = returned
    experiment = Path(settings["experiment_directory"])
    run = Path(plan["run_directory"])
    original = Path(plan["incoming_directory"])
    paths = {
        "analysis": experiment / "analysis",
        "data": experiment / "data",
        "run": run,
        "incoming": run / "incoming",
        "other_submission": run / "incoming" / str(uuid4()),
    }
    if target == "symlink":
        (original / "probe.txt").unlink()
        original.rmdir()
        sibling = run / "unrelated"
        sibling.mkdir()
        original.symlink_to(sibling, target_is_directory=True)
    else:
        paths[target].mkdir(parents=True, exist_ok=True)
        plan["incoming_directory"] = str(paths[target])
    with pytest.raises(ValueError):
        stage.restore_permissions(plan, settings)
    factory.assert_not_called()


@pytest.mark.parametrize("status", ["ACTIVE", "INACTIVE", "FAILED", "CANCELLED"])
def test_permissions_require_finished_transfers(returned, status):
    plan, settings, _, factory = returned
    state = Path(settings["state_directory"]) / f"{plan['submission_id']}.json"
    state.write_text(json.dumps({"status": status}))
    with pytest.raises(ValueError, match="completed Globus"):
        stage.restore_permissions(plan, settings)
    factory.assert_not_called()


def test_permissions_api_failure_fails_the_stage(returned):
    plan, settings, client, _ = returned
    client.restore_permissions.side_effect = PermissionError("DM denied access")
    with pytest.raises(PermissionError, match="DM denied access"):
        stage.restore_permissions(plan, settings)


def test_permissions_cli_loads_the_saved_plan_and_preserves_remote_status(returned, tmp_path, monkeypatch, capsys):
    plan, settings, client, _ = returned
    saved = tmp_path / "plan.json"
    saved.write_text(json.dumps(plan))
    monkeypatch.setattr(stage, "load_settings", lambda _: settings)
    monkeypatch.setattr(stage, "submission_path", lambda *_: saved)
    monkeypatch.setattr("sys.argv", ["stage", "--config", "private.yaml", "permissions", plan["submission_id"]])
    assert stage.main() == 0
    assert "Status: PERMISSIONS_RESTORED" in capsys.readouterr().out
    client.restore_permissions.assert_called_once()
    state = Path(settings["state_directory"]) / f"{plan['submission_id']}.json"
    assert json.loads(state.read_text())["status"] == "SUCCEEDED"
