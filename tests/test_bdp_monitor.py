"""Monitoring stays responsive, bounded, and separate from scientific completion."""

import json
import subprocess
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from laue_portal.database import db_schema
from laue_portal.processing.bdp import monitor, poller
from tests.run_support import load_job
from tests.test_bdp import FakeDM, remote_run  # noqa: F401


@pytest.fixture
def remote_files(tmp_path, monkeypatch):
    identifier = str(uuid4())
    root = tmp_path / "runs"
    output = root / identifier / "results"
    output.mkdir(parents=True)
    monkeypatch.setenv("LAUE_BDP_OBSERVER_ROOT", str(root))
    return identifier, output


def test_observer_reads_only_known_receipts_and_queries_recorded_pbs_id(remote_files, monkeypatch):
    identifier, output = remote_files
    (output / "pbs.json").write_text(json.dumps({"job_id": "123.server", "status": "Q"}))
    (output / "progress.json").write_text(json.dumps({"heartbeat_at": monitor.utc_now(), "n_succeeded": 4}))
    response = Mock(
        returncode=0,
        stdout=json.dumps(
            {
                "Jobs": {
                    "123.server": {
                        "job_state": "R",
                        "qtime": "Wed Oct 21 12:00:00 2026",
                        "stime": "Wed Oct 21 12:03:00 2026",
                        "Variable_List": {"private": "must not return"},
                    }
                }
            }
        ),
    )
    command = Mock(return_value=response)
    monkeypatch.setattr(subprocess, "run", command)
    result = monitor.read_run_status(identifier)
    assert result["pbs"]["status"] == "R"
    assert result["pbs"]["started_at"] == "2026-10-21T12:03:00+00:00"
    assert result["progress"]["n_succeeded"] == 4
    assert "Variable_List" not in json.dumps(result)
    assert command.call_args.args[0] == ["/opt/pbs/bin/qstat", "-xf", "-F", "json", "123.server"]
    assert command.call_args.kwargs["timeout"] == 8


def test_absent_receipt_does_not_launch_pbs_or_scan_inputs(remote_files, monkeypatch):
    identifier, _ = remote_files
    command = Mock(side_effect=AssertionError("No scheduler call expected"))
    monkeypatch.setattr(subprocess, "run", command)
    result = monitor.read_run_status(identifier)
    assert result["receipt_present"] is False and result["pbs"] == {}
    command.assert_not_called()


def test_observer_can_be_deserialized_without_importing_the_portal(remote_files):
    from globus_compute_sdk.serialize import ComputeSerializer, DillCodeSource

    identifier, _ = remote_files
    serializer = ComputeSerializer(strategy_code=DillCodeSource())
    function = serializer.deserialize(serializer.serialize(monitor.read_run_status))
    assert function.__globals__ is not monitor.__dict__
    assert function(identifier)["receipt_present"] is False


def test_observer_rejects_traversal_symlinks_and_oversized_files(remote_files):
    identifier, output = remote_files
    with pytest.raises(ValueError):
        monitor.read_run_status("../other")
    outside = output.parent.parent.parent / "outside.json"
    outside.write_text("{}")
    (output / "pbs.json").symlink_to(outside)
    with pytest.raises(ValueError, match="escapes"):
        monitor.read_run_status(identifier)
    (output / "pbs.json").unlink()
    (output / "pbs.json").write_text(" " * 65537)
    with pytest.raises(ValueError, match="64 KiB"):
        monitor.read_run_status(identifier)


@pytest.mark.parametrize(
    "pbs_state,phase,detail",
    [
        ("Q", "queued", "Waiting for PBS allocation"),
        ("H", "queued", "Held in PBS"),
        ("R", "running", "Processing"),
        ("F", "downlink", "Awaiting result return"),
    ],
)
def test_scheduler_states_are_separate_from_compute_running(pbs_state, phase, detail):
    observation = {"observed_at": monitor.utc_now(), "receipt_present": True, "pbs": {"status": pbs_state}}
    result = monitor.derive_remote_phase({"state": "RunPbsJob"}, observation)
    assert (result["phase"], result["detail"]) == (phase, detail)
    # A scheduler requeue is allowed even after the UI has shown Running.
    if pbs_state == "Q":
        assert (
            monitor.derive_remote_phase({"state": "RunPbsJob"}, observation, previous={"phase": "running"})["phase"]
            == "queued"
        )


def test_stale_observation_retains_last_phase_instead_of_guessing_queue_or_failure():
    previous = {"phase": "running", "detail": "Processing", "flow_state": "RunPbsJob"}
    old = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    result = monitor.derive_remote_phase(
        {"state": "RunPbsJob"}, {"observed_at": old, "pbs": {"status": "Q"}}, previous=previous
    )
    assert result["phase"] == "running" and result["stale"]
    assert monitor.derive_remote_phase({"state": "InputTransfer"}, None)["phase"] == "uplink"
    assert monitor.derive_remote_phase({"state": "ResultTransfer"}, None)["phase"] == "downlink"
    result = monitor.derive_remote_phase(
        {"state": "RunPbsJob"}, None, previous={"phase": "uplink", "flow_state": "InputTransfer"}
    )
    assert result["phase"] == "queued" and not result.get("stale")
    result = monitor.derive_remote_phase(
        {"state": "RunPbsJob"},
        None,
        previous={"phase": "queued", "flow_state": "RunPbsJob", "phase_since": old},
    )
    assert result["phase"] == "queued" and result.get("stale")


def test_flow_api_outage_preserves_nonterminal_dm_monitoring(tmp_path, monkeypatch):
    from laue_portal.processing.bdp import stage

    identifier = str(uuid4())
    saved = tmp_path / f"{identifier}.json"
    saved.write_text(json.dumps({"status": "ACTIVE", "flow_id": "flow-run"}))
    client = Mock()
    client.get_status.side_effect = TimeoutError()
    monkeypatch.setattr(stage, "_client", lambda _: client)
    result = stage.monitor({"submission_id": identifier}, {"state_directory": str(tmp_path)})
    assert result["status"] == "ACTIVE"
    assert result["observation"]["stale"] is True
    assert json.loads(saved.read_text())["status"] == "ACTIVE"


def test_no_receipt_and_submitting_receipt_have_distinct_queue_details():
    observation = {"observed_at": monitor.utc_now(), "receipt_present": False, "pbs": {}}
    assert monitor.derive_remote_phase({"state": "RunPbsJob"}, observation)["detail"] == "Waiting for endpoint"
    observation["receipt_present"] = True
    assert monitor.derive_remote_phase({"state": "RunPbsJob"}, observation)["detail"] == "Submitting to PBS"


def test_completed_pbs_receipt_remains_valid_during_flow_handoff_delay():
    old = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    result = monitor.derive_remote_phase({"state": "RunPbsJob"}, {"observed_at": old, "pbs": {"status": "F"}})
    assert result["phase"] == "downlink" and not result.get("stale")


def test_log_query_failure_does_not_abort_dm_stage(tmp_path, monkeypatch):
    from laue_portal.processing.bdp import stage

    identifier = str(uuid4())
    (tmp_path / f"{identifier}.json").write_text(json.dumps({"status": "ACTIVE", "flow_id": "flow-run"}))
    client = Mock()
    client.get_status.return_value = {"status": "ACTIVE", "details": {}}
    client.flows_manager.flows_client.get_run_logs.side_effect = TimeoutError()
    monkeypatch.setattr(stage, "_client", lambda _: client)
    result = stage.monitor({"submission_id": identifier}, {"state_directory": str(tmp_path)})
    assert result["status"] == "ACTIVE"


def test_dm_monitor_persists_one_probe_and_reports_results_across_invocations(tmp_path, monkeypatch):
    from laue_portal.processing.bdp import stage

    identifier = str(uuid4())
    state = tmp_path / f"{identifier}.json"
    state.write_text(json.dumps({"status": "ACTIVE", "flow_id": "flow-run"}))
    settings = {
        "state_directory": str(tmp_path),
        "targets": {"crux": {"observer": {"endpoint_id": "observer", "function_id": "reader"}}},
    }
    client, compute = Mock(), Mock()
    client.get_status.return_value = {
        "status": "ACTIVE",
        "details": {"action_statuses": [{"state_name": "RunPbsJob", "status": "ACTIVE"}]},
    }
    compute.run.return_value = "probe-1"
    compute.get_task.return_value = {"pending": True}
    monkeypatch.setattr(stage, "_client", lambda _: client)
    monkeypatch.setattr(monitor, "compute_client", lambda _: compute)
    stage.monitor({"submission_id": identifier}, settings)
    assert json.loads(state.read_text())["observer_task_id"] == "probe-1"
    stage.monitor({"submission_id": identifier}, settings)
    compute.run.assert_called_once()
    compute.get_task.assert_called_once_with("probe-1")
    compute.get_task.return_value = {
        "pending": False,
        "result": {
            "submission_id": identifier,
            "observed_at": monitor.utc_now(),
            "receipt_present": True,
            "pbs": {"status": "R"},
        },
    }
    result = stage.monitor({"submission_id": identifier}, settings)
    assert result["observation"]["phase"] == "running"
    assert result["observation"]["submission_id"] == identifier
    assert "observer_task_id" not in json.loads(state.read_text())


def test_dm_output_regex_captures_monitor_snapshot(tmp_path, monkeypatch, capsys):
    import re
    from pathlib import Path

    from laue_portal.processing.bdp import stage

    identifier = str(uuid4())
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"submission_id": identifier}))
    settings = {"state_directory": str(tmp_path)}
    (tmp_path / f"{identifier}.json").write_text(
        json.dumps({"status": "ACTIVE", "flow_id": "flow-run", "url": "https://app.globus.org/runs/flow-run"})
    )
    client = Mock()
    client.get_status.return_value = {
        "status": "ACTIVE",
        "details": {"action_statuses": [{"state_name": "InputTransfer", "status": "ACTIVE"}]},
    }
    monkeypatch.setattr(stage, "_client", lambda _: client)
    monkeypatch.setattr(stage, "load_settings", lambda _: settings)
    monkeypatch.setattr(stage, "submission_path", lambda *_: plan)
    monkeypatch.setattr("sys.argv", ["stage", "--config", "private.yaml", "monitor", identifier])
    assert stage.main() == 0
    output = capsys.readouterr().out
    template = Path(__file__).parents[1] / "deploy/workflow-bdp.json.template"
    definition = json.loads(template.read_text())["stages"]["02-MONITOR"]
    fields = {}
    for expression in definition["outputVariableRegexList"]:
        fields.update(re.search(expression, output).groupdict())
    assert fields["remoteStatus"] == "ACTIVE"
    assert json.loads(fields["remoteObservation"])["phase"] == "uplink"


def test_one_probe_is_persisted_across_ticks_and_result_is_identity_checked():
    identifier = str(uuid4())
    plan = {"submission_id": identifier}
    settings = {"targets": {"crux": {"observer": {"endpoint_id": "observer", "function_id": "reader"}}}}
    client = Mock()
    client.run.return_value = "task-1"
    client.get_task.return_value = {"pending": True}
    state = {}
    monitor.refresh_observer(plan, state, settings, client)
    monitor.refresh_observer(plan, state, settings, client)
    client.run.assert_called_once()
    assert state["observer_task_id"] == "task-1"
    client.get_task.return_value = {
        "pending": False,
        "result": {"submission_id": identifier, "observed_at": monitor.utc_now(), "pbs": {"status": "R"}},
    }
    monitor.refresh_observer(plan, state, settings, client)
    assert state["observer_result"]["pbs"]["status"] == "R"
    assert "observer_task_id" not in state
    monitor.refresh_observer(plan, state, settings, client)
    client.run.assert_called_once()
    state["observer_task_id"] = "task-wrong"
    client.get_task.return_value = {
        "pending": False,
        "result": {"submission_id": str(uuid4()), "observed_at": monitor.utc_now()},
    }
    monitor.refresh_observer(plan, state, settings, client)
    assert state["observer_result"]["submission_id"] == identifier
    assert state["observer_error"] == "Status unavailable"


def test_unavailable_probe_does_not_accumulate_tasks_or_erase_latest_observation():
    from globus_compute_sdk.errors import TaskExecutionFailed

    settings = {"targets": {"crux": {"observer": {"endpoint_id": "observer", "function_id": "reader"}}}}
    plan = {"submission_id": str(uuid4())}
    previous = {"pbs": {"status": "R"}}
    state = {"observer_task_id": "task-1", "observer_result": previous}
    client = Mock()
    client.get_task.side_effect = TimeoutError()
    monitor.refresh_observer(plan, state, settings, client)
    assert state["observer_task_id"] == "task-1" and state["observer_result"] == previous
    client.run.assert_not_called()
    client.get_task.side_effect = TaskExecutionFailed("reader failed", "now")
    monitor.refresh_observer(plan, state, settings, client)
    assert "observer_task_id" not in state and state["observer_result"] == previous


def test_poller_caches_valid_observation_without_publishing_counters(remote_run):  # noqa: F811
    from laue_portal.processing.bdp import backend

    engine, run, settings = remote_run
    client = FakeDM()
    backend.submit_run(run.job_id, engine=engine, settings=settings, client=client)
    job = load_job(engine, run.job_id)
    observation = {
        "submission_id": job.submission_id,
        "phase": "running",
        "detail": "Processing",
        "observed_at": monitor.utc_now(),
        "remote_progress": {"n_succeeded": 1},
    }
    client.record.update(status="running", remoteObservation=json.dumps(observation))
    poller.poll_once(engine=engine, settings=settings, client=client)
    job = load_job(engine, run.job_id)
    assert job.remote_observation == observation
    assert job.n_succeeded == 0  # Remote computation does not publish APS outputs.
    client.record["remoteObservation"] = "broken JSON"
    poller.poll_once(engine=engine, settings=settings, client=client)
    assert load_job(engine, run.job_id).remote_observation == observation
    with Session(engine) as session:
        assert session.get(db_schema.Job, run.job_id).status == 1
