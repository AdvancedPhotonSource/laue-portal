"""Remote execution boundaries: immutable inputs, duplicate prevention, and validated return."""

from __future__ import annotations

import copy
import io
import json
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import h5py
import pytest
from sqlalchemy.orm import Session

from laue_portal.database import db_schema
from laue_portal.processing import runner
from laue_portal.processing.bdp import backend, plan, poller
from laue_portal.processing.bdp.pbs import build_script
from laue_portal.processing.bdp.settings import collection_path, execution_computer
from laue_portal.processing.queue import controls, lifecycle
from laue_portal.workflows import indexing
from laue_portal.workflows.execution import ExecutionStateError, JobStatus, RunPhase
from laue_portal.workflows.manifest import ManifestError, read_manifest, read_request, write_request
from tests.run_support import load_job, make_engine, publish_wire_run
from tests.test_compute_lauego import CRYSTAL, _frames_dir, _parameters
from tests.wire_support import GEOMETRY, OPTIONS, write_wire_scan


class FakeDM:
    def __init__(self, *, timeout=False):
        self.submissions = []
        self.timeout = timeout
        self.record = {"id": "dm-001", "status": "pending"}

    def submit(self, document):
        self.submissions.append(document)
        if self.timeout:
            raise TimeoutError("response lost")
        return self.record

    def get(self, job_id):
        assert job_id == "dm-001"
        return self.record

    def find(self, submission_id):
        return [self.record]


@pytest.mark.parametrize("backend,label", [("local", "APS"), ("aps", "APS"), ("crux", "ALCF")])
def test_execution_computer_defaults_are_generic(backend, label, monkeypatch):
    from laue_portal import config

    monkeypatch.setattr(config, "DEFAULT_VARIABLES", {})
    assert execution_computer(backend, settings={}) == label


def test_execution_computer_uses_private_config_without_network_calls(monkeypatch):
    from laue_portal import config

    monkeypatch.setattr(config, "DEFAULT_VARIABLES", {"computer_name": "local-worker"})
    settings = {"targets": {"aps": {"computer_name": "aps-worker"}, "crux": {"computer_name": "remote-worker"}}}
    assert execution_computer("local", settings=settings) == "local-worker"
    assert execution_computer("aps", settings=settings) == "aps-worker"
    assert execution_computer("crux", settings=settings) == "remote-worker"


@pytest.fixture
def remote_run(tmp_path, monkeypatch):
    engine = make_engine(tmp_path, monkeypatch)
    root = tmp_path / "aps"
    work = root / "LauePortal" / "analysis" / "portal_workspace"
    work.mkdir(parents=True)
    run = publish_wire_run(engine, work, count=2)
    request_path = Path(run.output_path) / "request.json"
    document = read_request(request_path)
    geometry = root / "LauePortal" / "geometry.xml"
    shutil.copyfile(GEOMETRY, geometry)
    document["request"]["geometry_file"] = str(geometry)
    document["request"].update(OPTIONS)
    write_request(request_path, document, overwrite=True)
    for i in (1, 2):
        write_wire_scan(work / "wire-input" / f"wire_{i}.h5", seed=i)
    with Session(engine) as session, session.begin():
        session.get(db_schema.Job, run.job_id).backend = "crux"
    eagle = tmp_path / "eagle"
    settings = {
        "enabled": True,
        "submission_directory": str(work / "submissions"),
        "dm": {},
        "storage": {
            "aps": {"filesystem_root": str(root), "collection_root": "/", "collection_id": "aps"},
            "eagle": {"filesystem_root": str(eagle), "collection_root": "/", "collection_id": "eagle"},
        },
        "targets": {
            "crux": {
                "enabled": True,
                "workspace": str(eagle / "work"),
                "compute_endpoint": "compute-id",
                "analysis_python": "/env/python",
                "code_directory": "/software/code",
                "execution": {"workers": 1, "reconstruction_workers": 1, "threads_per_worker": 1},
                "pbs": {"account": "test-allocation", "queue": "test-queue", "nodes": 1, "walltime": "00:05:00"},
            }
        },
    }
    return engine, run, settings


def stage_fixture(document, settings):
    """Emulate collection paths on two independent temporary filesystems."""
    source, destination = settings["storage"]["aps"], settings["storage"]["eagle"]
    for item in document["input_transfer"]["transfer_items"]:
        src = Path(source["filesystem_root"]) / item["source_path"].lstrip("/")
        dst = Path(destination["filesystem_root"]) / item["destination_path"].lstrip("/")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)


def test_collection_roots_match_the_supplied_transfer_paths(tmp_path):
    storage = {"filesystem_root": str(tmp_path / "gdata"), "collection_root": "/"}
    assert collection_path(storage, tmp_path / "gdata/LauePortal/data/point.h5") == "/LauePortal/data/point.h5"
    with pytest.raises(ValueError):
        collection_path(storage, tmp_path / "gdata_other/file")
    (tmp_path / "gdata").mkdir()
    (tmp_path / "gdata/link").symlink_to(tmp_path)
    with pytest.raises(ValueError):
        collection_path(storage, tmp_path / "gdata/link/secret")


def test_successful_submission_is_not_repeated(remote_run):
    engine, run, settings = remote_run
    client = FakeDM()
    assert backend.submit_run(run.job_id, engine=engine, settings=settings, client=client) == "dm-001"
    with pytest.raises(ExecutionStateError):
        backend.submit_run(run.job_id, engine=engine, settings=settings, client=client)
    assert len(client.submissions) == 1
    job = load_job(engine, run.job_id)
    assert job.external_id == "dm-001" and job.phase == RunPhase.QUEUED
    assert lifecycle.reconcile_interrupted_runs(engine, stale_after_seconds=1, queue_entry_exists=lambda _: False) == []
    assert controls.move_run_to_front(run.job_id, engine=engine)["success"] is False


def test_lost_submit_response_is_reconciled_without_resubmission(remote_run):
    engine, run, settings = remote_run
    client = FakeDM(timeout=True)
    with pytest.raises(TimeoutError):
        backend.submit_run(run.job_id, engine=engine, settings=settings, client=client)
    assert load_job(engine, run.job_id).external_state == "submission_uncertain"
    poller.poll_once(engine=engine, settings=settings, client=client)
    assert load_job(engine, run.job_id).external_id == "dm-001"
    assert len(client.submissions) == 1


def test_real_wire_runner_and_return_publication_preserve_original_inputs(remote_run):
    engine, run, settings = remote_run
    request_path, manifest_path = Path(run.output_path) / "request.json", Path(run.output_path) / "inputs.jsonl"
    original = request_path.read_bytes(), manifest_path.read_bytes()
    client = FakeDM()
    backend.submit_run(run.job_id, engine=engine, settings=settings, client=client)
    document = client.submissions[0]
    stage_fixture(document, settings)
    summary = runner.run(document["control_directory"])
    assert summary["status"] == "Finished"
    assert summary["counters"]["n_succeeded"] == 2
    shutil.copytree(document["output_directory"], document["incoming_directory"])
    # A late cancel must not block collection of an already completed DM result.
    controls.cancel_run(run.job_id, engine=engine)
    client.record["status"] = "done"
    assert poller.poll_once(engine=engine, settings=settings, client=client) == [run.job_id]
    job = load_job(engine, run.job_id)
    assert (job.status, job.n_succeeded, job.n_not_run) == (JobStatus.FINISHED, 2, 0)
    assert (Path(run.output_path) / "reconstruction/scan.h5").exists()
    assert original == (request_path.read_bytes(), manifest_path.read_bytes())
    assert poller.publish_returned(document)["status"] == "Finished"
    with pytest.raises(FileExistsError):
        runner.run(document["control_directory"])


def test_real_indexing_runner_returns_results_xml_and_catalog_counts(remote_run):
    engine, wire_run, settings = remote_run
    work = Path(wire_run.output_path).parent
    frames = _frames_dir(work)
    crystal = work / "Ni.xml"
    shutil.copyfile(CRYSTAL, crystal)
    request = indexing.LaueGoIndexingRequest(
        backend="crux",
        scan_number=1,
        reconstruction_id=None,
        input_path=str(frames),
        output_path_template=str(work / "index_%d"),
        filename_prefixes=["frame_%d.h5"],
        scan_points="1-3",
        depth_range=None,
        detector_crop_x1=0,
        detector_crop_x2=2047,
        detector_crop_y1=0,
        detector_crop_y2=2047,
        output_xml="output.xml",
        energy_unit="keV",
        exposure_unit="sec",
        reciprocal_lattice_unit="1/nm",
        lattice_parameters_unit="nm",
        beamline="34ID-E",
        **_parameters(geometry_file=str(work.parent.parent / "geometry.xml"), crystal_file=str(crystal)),
    )
    run = indexing.create_indexing(request, engine=engine)
    client = FakeDM()
    backend.submit_run(run.job_id, engine=engine, settings=settings, client=client)
    document = client.submissions[0]
    stage_fixture(document, settings)
    summary = runner.run(document["control_directory"])
    assert summary["status"] == "Finished"
    assert summary["counters"]["n_succeeded"] == 3
    shutil.copytree(document["output_directory"], document["incoming_directory"])
    client.record["status"] = "done"
    poller.poll_once(engine=engine, settings=settings, client=client)
    assert load_job(engine, run.job_id).status == JobStatus.FINISHED
    with Session(engine) as session:
        stored = session.get(db_schema.IndexingRun, run.id)
        assert stored.n_frames_indexed == 2
        assert Path(stored.results_path).is_file()
    assert (Path(run.output_path) / "output.xml").is_file()
    expected_sources = [entry.source for entry in read_manifest(Path(run.output_path) / "inputs.jsonl")]
    with h5py.File(Path(run.output_path) / "output.h5", "r") as handle:
        assert handle["frames/input_images"].asstr()[:].tolist() == expected_sources
        assert all(
            str(Path(document["control_directory"]).parent / "inputs") in value
            for value in handle["provenance/remote_input_images"].asstr()[:]
        )
    xml = ET.parse(Path(run.output_path) / "output.xml")
    assert [node.text for node in xml.iter("inputImage")] == expected_sources


@pytest.mark.parametrize("bad_fields", [{"job_id": -1}, {"counters": {"n_inputs": "2"}}])
def test_invalid_return_finishes_failed_without_publishing_output(remote_run, bad_fields):
    engine, run, settings = remote_run
    client = FakeDM()
    backend.submit_run(run.job_id, engine=engine, settings=settings, client=client)
    document = client.submissions[0]
    incoming = Path(document["incoming_directory"])
    incoming.mkdir(parents=True)
    (incoming / "run.json").write_text(
        json.dumps(
            {
                "job_id": run.job_id,
                "submission_id": document["submission_id"],
                "kind": document["kind"],
                **bad_fields,
            }
        )
    )
    client.record["status"] = "done"
    poller.poll_once(engine=engine, settings=settings, client=client)
    assert load_job(engine, run.job_id).status == JobStatus.FAILED
    assert not (Path(run.output_path) / "run.json").exists()


def test_tampered_manifest_is_rejected_before_compute(remote_run):
    engine, run, settings = remote_run
    job = load_job(engine, run.job_id)
    document = plan.save_plan(job, settings, str(uuid4()))
    stage_fixture(document, settings)
    with open(Path(document["control_directory"]) / "inputs.jsonl", "a") as handle:
        handle.write("{}\n")
    with pytest.raises(ManifestError):
        runner.run(document["control_directory"])
    assert not (Path(document["output_directory"]) / "reconstruction").exists()


def test_return_does_not_overwrite_an_existing_result(remote_run):
    engine, run, settings = remote_run
    document = plan.save_plan(load_job(engine, run.job_id), settings, str(uuid4()))
    stage_fixture(document, settings)
    runner.run(document["control_directory"])
    shutil.copytree(document["output_directory"], document["incoming_directory"])
    old = Path(run.output_path) / "reconstruction"
    old.mkdir()
    (old / "keep.txt").write_text("existing data")
    with pytest.raises(FileExistsError):
        poller.publish_returned(document)
    assert (old / "keep.txt").read_text() == "existing data"


@pytest.mark.parametrize("existing", [False, True])
def test_return_publication_handles_foreign_owned_files_without_overwriting(tmp_path, monkeypatch, existing):
    source, destination = tmp_path / "incoming.json", tmp_path / "published.json"
    source.write_bytes(b"complete returned output")
    if existing:
        destination.write_bytes(b"existing data")
    link = poller.os.link

    def protected_link(src, dst):
        if Path(src) == source:
            raise PermissionError("protected hard link to another account's file")
        return link(src, dst)

    monkeypatch.setattr(poller.os, "link", protected_link)
    if existing:
        with pytest.raises(FileExistsError):
            poller._publish_returned_file(source, destination)
        assert source.read_bytes() == b"complete returned output"
        assert destination.read_bytes() == b"existing data"
    else:
        poller._publish_returned_file(source, destination)
        assert destination.read_bytes() == b"complete returned output"
        assert not source.exists()
        assert destination.stat().st_mode & 0o777 == 0o660
    assert not list(tmp_path.glob(".bdp-return-*"))


def test_failed_return_copy_leaves_no_partially_published_file(tmp_path, monkeypatch):
    source, destination = tmp_path / "incoming", tmp_path / "published"
    source.write_bytes(b"complete returned output")
    monkeypatch.setattr(poller.os, "link", Mock(side_effect=PermissionError("protected hard link")))

    def interrupted_copy(incoming, outgoing):
        outgoing.write(b"partial")
        raise OSError("write interrupted")

    monkeypatch.setattr(poller.shutil, "copyfileobj", interrupted_copy)
    with pytest.raises(OSError, match="write interrupted"):
        poller._publish_returned_file(source, destination)
    assert not destination.exists()
    assert source.read_bytes() == b"complete returned output"
    assert not list(tmp_path.glob(".bdp-return-*"))


def test_cancel_before_compute_returns_a_cancelled_summary(remote_run):
    engine, run, settings = remote_run
    document = plan.save_plan(load_job(engine, run.job_id), settings, str(uuid4()))
    stage_fixture(document, settings)
    (Path(document["control_directory"]) / "cancel.request").touch()
    summary = runner.run(document["control_directory"], compute=lambda *_: pytest.fail("compute ran"))
    assert summary["status"] == "Cancelled" and summary["counters"]["n_not_run"] == 2


def test_pbs_script_uses_allocation_and_bash_launcher(remote_run):
    engine, run, settings = remote_run
    document = plan.build_plan(load_job(engine, run.job_id), settings, str(uuid4()))
    script = build_script(document)
    assert "#PBS -N Laue\n#PBS -A test-allocation" in script
    assert "#PBS -q test-queue\n" in script
    assert "mpiexec" in script and "/bin/bash" in script and "--cpu-bind none" in script
    subprocess.run(["bash", "-n"], input=script, text=True, check=True)
    unsafe = copy.deepcopy(document)
    unsafe["pbs"]["queue"] = "test-queue; touch /tmp/wrong"
    with pytest.raises(ValueError):
        build_script(unsafe)


def test_compute_imports_never_load_database_or_portal_configuration():
    script = """
import sys
class Block:
    def find_spec(self, fullname, *args):
        if fullname.split('.')[0] in {'sqlalchemy', 'redis', 'rq'} or fullname == 'laue_portal.config':
            raise AssertionError('Unexpected remote dependency: ' + fullname)
sys.meta_path.insert(0, Block())
from laue_portal.processing.compute import get_compute_function
get_compute_function('wire_reconstruction')
get_compute_function('lauego_indexing')
"""
    subprocess.run([sys.executable, "-c", script], check=True)


@pytest.mark.parametrize("launcher_host", [None, "test-user@workflow.example.invalid"])
def test_cancellation_uses_launcher_host_independently_of_dm_api_bridge(tmp_path, launcher_host):
    from laue_portal.processing.bdp.dm import launcher_command

    source = tmp_path / "source files"
    source.mkdir()
    interpreter = tmp_path / "python launcher"
    interpreter.write_text(f"#!{sys.executable}\nimport json, sys\nprint(json.dumps(sys.argv[1:]))\n")
    interpreter.chmod(0o700)
    config = tmp_path / "config ' $(touch unexpected).yaml"
    settings = {
        "ssh_host": "test-user@bridge.example.invalid",
        "launcher_ssh_host": launcher_host,
        "launcher_python": str(interpreter),
        "launcher_code": str(source),
        "launcher_config": str(config),
    }
    submission_id = str(uuid4())
    command = launcher_command(settings, "cancel", submission_id)
    if launcher_host:
        assert command[:6] == ["ssh", "-T", "-o", "BatchMode=yes", launcher_host, command[-1]]
        # Execute the remote shell payload locally, without making an SSH call.
        command = ["/bin/bash", "-c", command[-1]]
    else:
        assert command[:2] == ["/bin/bash", "-c"]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    assert json.loads(result.stdout) == [
        "-m",
        "laue_portal.processing.bdp.stage",
        "--config",
        str(config),
        "cancel",
        submission_id,
    ]
    assert not (source / "unexpected").exists()


def test_dm_cancellation_waits_for_delivery_without_repeated_submissions(tmp_path):
    job = SimpleNamespace(run_directory=str(tmp_path), submission_id=str(uuid4()), cancel_requested_at="now")
    client = Mock()
    client.cancel.return_value = {"id": "cancel-1"}
    client.get.return_value = {"id": "cancel-1", "status": "running"}
    settings = {"dm": {"cancel_workflow": "laue-portal-bdp-cancel"}}
    poller.request_cancellation(job, settings, client)
    poller.request_cancellation(job, settings, client)
    client.cancel.assert_called_once_with(job.submission_id)
    assert not (tmp_path / ".cancel-sent").exists()
    client.get.return_value = {"id": "cancel-1", "status": "done"}
    poller.request_cancellation(job, settings, client)
    assert (tmp_path / ".cancel-sent").exists()


def test_failed_dm_cancellation_is_reported_and_not_marked_delivered(tmp_path):
    job = SimpleNamespace(run_directory=str(tmp_path), submission_id=str(uuid4()), cancel_requested_at="now")
    client = Mock()
    client.cancel.return_value = {"id": "cancel-1"}
    client.get.return_value = {"id": "cancel-1", "status": "failed"}
    with pytest.raises(ValueError, match="DM cancellation job"):
        poller.request_cancellation(job, {"dm": {"cancel_workflow": "cancel"}}, client)
    assert not (tmp_path / ".cancel-sent").exists()


def test_dm_cancel_argument_does_not_conflict_with_parent_submission_lookup():
    from laue_portal.processing.bdp.dm import DMClient

    client = DMClient({"owner": "test-user", "cancel_workflow": "laue-cancel", "launcher_config": "/config/bdp.yaml"})
    client._call = Mock(return_value={"id": "cancel-1"})
    submission_id = str(uuid4())
    client.cancel(submission_id)
    client._call.assert_called_once_with(
        "submit",
        owner="test-user",
        workflow="laue-cancel",
        arguments={
            "cancelSubmissionId": submission_id,
            "source": "laue-portal",
            "filePath": "/config/bdp.yaml",
        },
    )
    with pytest.raises(ValueError):
        client.cancel("invalid-id")


def test_dm_submission_uses_one_frozen_shared_file_without_remote_file_iteration():
    from laue_portal.processing.bdp.dm import DMClient

    client = DMClient({"owner": "test-user", "workflow": "laue-workflow"})
    client._call = Mock(return_value={"id": "dm-1"})
    submission_id = str(uuid4())
    client.submit(
        {
            "submission_id": submission_id,
            "backend": "crux",
            "control_directory": "/compute/control",
            "run_directory": "/experiment/analysis/run",
        }
    )
    args = client._call.call_args.kwargs["arguments"]
    assert args["submissionId"] == submission_id
    assert args["filePath"] == "/experiment/analysis/run/request.json"


@pytest.mark.parametrize("operation", ["submit", "get", "find"])
def test_dm_bridge_preserves_processing_job_objects_as_structured_json(operation, monkeypatch, capsys):
    from laue_portal.processing.bdp.dm import _API_SCRIPT

    record = {"id": "dm-1", "status": "pending", "submissionId": "submission-1"}
    job = SimpleNamespace(data=record)
    api = Mock()
    api.startProcessingJob.return_value = job
    api.getProcessingJobById.return_value = job
    api.listProcessingJobRecords.return_value = [job]
    for name in ("dm", "dm.proc_web_service", "dm.proc_web_service.api"):
        monkeypatch.setitem(sys.modules, name, SimpleNamespace())
    monkeypatch.setitem(
        sys.modules, "dm.proc_web_service.api.workflowProcApi", SimpleNamespace(WorkflowProcApi=lambda: api)
    )
    arguments = {
        "owner": "test-user",
        "workflow": "laue",
        "arguments": {},
        "id": "dm-1",
        "submission_id": "submission-1",
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"operation": operation, "args": arguments})))
    exec(_API_SCRIPT, {})
    assert json.loads(capsys.readouterr().out) == ([record] if operation == "find" else record)
