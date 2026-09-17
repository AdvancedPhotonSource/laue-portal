"""Tests for reconstruction and indexing creation services."""

import json
import os
import threading
import time
from datetime import datetime

import pytest
from sqlalchemy import create_engine, event, func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from laue_portal.database import db_schema, session_utils
from laue_portal.workflows import (
    FileResolutionError,
    RunPhase,
    RunPublicationError,
    WorkflowValidationError,
    run_records,
)
from laue_portal.workflows import indexing as indexing_workflow
from laue_portal.workflows import reconstruction as reconstruction_workflow
from laue_portal.workflows.execution import ExecutionStateError, JobStatus, assert_enqueueable
from laue_portal.workflows.files import ResolvedInput
from laue_portal.workflows.manifest import (
    MANIFEST_FILENAME,
    REQUEST_FILENAME,
    RESULTS_FILENAME,
    manifest_digest,
    read_manifest,
    read_request,
    verify_manifest,
)
from tests.conftest import create_test_metadata


@pytest.fixture
def workflow_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'services.db'}")

    @event.listens_for(engine, "connect")
    def enable_sqlite_pragmas(dbapi_connection, connection_record):
        session_utils.enable_sqlite_pragmas(dbapi_connection, connection_record)

    db_schema.Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def _wire_request(input_path, output_template, **overrides):
    values = {
        "scan_number": 1,
        "input_path": os.fspath(input_path),
        "output_path_template": os.fspath(output_template),
        "filename_prefixes": ["wire_%d.h5"],
        "geometry_file": "/config/geometry.xml",
        "percent_brightest": 5.0,
        "wire_edges": "0 1",
        "depth_start": -10.0,
        "depth_end": 10.0,
        "depth_resolution": 0.5,
        "num_threads": 4,
        "memory_limit_mb": 1024,
        "scan_points": "1-2",
        "verbose": 1,
        "author": "scientist",
        "notes": "wire test",
        "algorithm_version": "wire-v1",
        "computer_name": "worker-a",
        "priority": 3,
        "submitted_at": datetime(2026, 8, 19, 12, 0, 0),
    }
    values.update(overrides)
    return reconstruction_workflow.WireReconstructionRequest(**values)


def _indexing_request(input_path, output_template, **overrides):
    values = {
        "scan_number": 1,
        "reconstruction_id": None,
        "input_path": os.fspath(input_path),
        "output_path_template": os.fspath(output_template),
        "filename_prefixes": ["index_%d_%d.h5"],
        "threshold": 250,
        "threshold_ratio": -1,
        "max_rfactor": 0.5,
        "box_size": 18,
        "max_number": 50,
        "min_separation": 40,
        "peak_shape": "Lorentzian",
        "scan_points": "1-2",
        "depth_range": "0-1",
        "detector_crop_x1": 0,
        "detector_crop_x2": 2047,
        "detector_crop_y1": 0,
        "detector_crop_y2": 2047,
        "min_size": 1.13,
        "max_peaks": 50,
        "smooth": False,
        "mask_file": None,
        "index_kev_max_calc": 17.2,
        "index_kev_max_test": 30.0,
        "index_angle_tolerance": 0.1,
        "index_h": 1,
        "index_k": 1,
        "index_l": 1,
        "index_cone": 72.0,
        "energy_unit": "keV",
        "exposure_unit": "sec",
        "cosmic_filter": True,
        "reciprocal_lattice_unit": "1/nm",
        "lattice_parameters_unit": "nm",
        "output_xml": "merged.xml",
        "geometry_file": "/config/geometry.xml",
        "crystal_file": "/config/Al.xtal",
        "depth": "3D",
        "beamline": "34ID-E",
        "author": "scientist",
        "notes": "index test",
        "algorithm_version": "lauego-v1",
        "computer_name": "worker-b",
        "priority": 4,
        "submitted_at": datetime(2026, 8, 19, 13, 0, 0),
    }
    values.update(overrides)
    return indexing_workflow.LaueGoIndexingRequest(**values)


def _add_metadata(engine, *scan_numbers):
    with Session(engine) as session:
        session.add_all(create_test_metadata(number) for number in scan_numbers)
        session.commit()


def _create_files(directory, filenames):
    directory.mkdir()
    for filename in filenames:
        (directory / filename).write_text("")


def _count(engine, model):
    with Session(engine) as session:
        return session.scalar(select(func.count()).select_from(model))


def _row_total(engine):
    """Rows across every table; the constant-row gate counts all of them."""

    with Session(engine) as session:
        return sum(
            session.execute(select(func.count()).select_from(table)).scalar_one()
            for table in db_schema.Base.metadata.sorted_tables
        )


def _job(engine, job_id):
    with Session(engine) as session:
        return session.get(db_schema.Job, job_id)


def _fake_inputs(tmp_path, count, stem="wire"):
    return tuple(ResolvedInput(os.fspath(tmp_path / f"{stem}_{index}.h5"), 0, (index,)) for index in range(count))


def test_create_reconstruction_persists_a_run_and_publishes_its_manifest(workflow_engine, tmp_path):
    _add_metadata(workflow_engine, 1)
    input_path = tmp_path / "wire-input"
    output_template = tmp_path / "analysis" / "rec_%d" / "data"
    _create_files(input_path, ["wire_1.h5", "wire_2.h5"])
    subjob_inserts = []

    @event.listens_for(workflow_engine, "before_cursor_execute")
    def observe_subjob_insert(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO subjob"):
            subjob_inserts.append(executemany)

    run = reconstruction_workflow.create_reconstruction(
        _wire_request(input_path, output_template), engine=workflow_engine
    )

    expected_output = os.fspath(tmp_path / "analysis" / "rec_1" / "data")
    assert run.id == 1
    assert run.method == "wire"
    assert run.output_path == expected_output
    assert run.wire_parameters.scan_points_len == 2
    assert run.wire_parameters.filename_prefixes == ["wire_%d.h5"]
    assert run.job.status == JobStatus.QUEUED
    assert run.job.phase == RunPhase.PUBLISHED
    assert run.job.submit_time == datetime(2026, 8, 19, 12, 0, 0)
    assert run.job.start_time is None
    assert run.job.finish_time is None
    assert (run.job.n_inputs, run.job.n_succeeded, run.job.n_failed, run.job.n_not_run) == (2, 0, 0, 0)
    assert run.job.run_directory == expected_output
    assert run.job.manifest_path == os.path.join(expected_output, MANIFEST_FILENAME)
    assert run.job.request_path == os.path.join(expected_output, REQUEST_FILENAME)
    assert run.job.manifest_digest == manifest_digest(run.job.manifest_path)
    assert subjob_inserts == []
    assert "subjob" not in inspect(workflow_engine).get_table_names()
    assert_enqueueable(run.job)

    entries = list(read_manifest(run.job.manifest_path))
    assert [(entry.index, entry.input_id, entry.scan_point, entry.depth_point) for entry in entries] == [
        (0, "wire_1", 1, None),
        (1, "wire_2", 2, None),
    ]
    assert [os.path.basename(entry.source) for entry in entries] == ["wire_1.h5", "wire_2.h5"]
    verify_manifest(run.job.manifest_path, expected_digest=run.job.manifest_digest, expected_count=2)

    request = read_request(run.job.request_path)
    assert request["kind"] == "wire_reconstruction"
    assert request["run"] == {"reconstruction_id": 1, "job_id": 1, "scan_number": 1, "method": "wire"}
    assert request["request"]["geometry_file"] == "/config/geometry.xml"
    assert request["request"]["submitted_at"] == "2026-08-19T12:00:00"
    assert request["manifest"] == {"path": MANIFEST_FILENAME, "n_inputs": 2, "sha256": run.job.manifest_digest}
    assert sorted(os.listdir(expected_output)) == [MANIFEST_FILENAME, REQUEST_FILENAME]

    loaded = reconstruction_workflow.get_reconstruction(run.id, engine=workflow_engine)
    assert loaded.wire_parameters.geometry_file == "/config/geometry.xml"
    assert loaded.job.job_id == run.job_id
    assert reconstruction_workflow.get_reconstruction(999, engine=workflow_engine) is None


def test_create_indexing_supports_direct_and_reconstruction_parent_runs(workflow_engine, tmp_path):
    _add_metadata(workflow_engine, 1)
    wire_input = tmp_path / "wire-input"
    index_input = tmp_path / "index-input"
    _create_files(wire_input, ["wire_1.h5", "wire_2.h5"])
    _create_files(
        index_input,
        ["index_1_0.h5", "index_1_1.h5", "index_2_0.h5", "index_2_1.h5"],
    )
    reconstruction = reconstruction_workflow.create_reconstruction(
        _wire_request(wire_input, tmp_path / "analysis" / "rec_%d"),
        engine=workflow_engine,
    )

    direct = indexing_workflow.create_indexing(
        _indexing_request(index_input, tmp_path / "analysis" / "index_%d"),
        engine=workflow_engine,
    )
    child = indexing_workflow.create_indexing(
        _indexing_request(
            index_input,
            tmp_path / "analysis" / "child-index_%d",
            scan_number=None,
            reconstruction_id=reconstruction.id,
        ),
        engine=workflow_engine,
    )

    assert direct.id == 1
    assert direct.reconstruction_id is None
    assert direct.scan_number == 1
    assert direct.output_path == os.fspath(tmp_path / "analysis" / "index_1")
    assert direct.job.n_inputs == 4
    assert direct.job.phase == RunPhase.PUBLISHED
    assert direct.n_frames_indexed is None
    entries = list(read_manifest(direct.job.manifest_path))
    assert [(entry.index, entry.input_id, entry.scan_point, entry.depth_point) for entry in entries] == [
        (0, "index_1_0", 1, 0),
        (1, "index_1_1", 1, 1),
        (2, "index_2_0", 2, 0),
        (3, "index_2_1", 2, 1),
    ]
    request = read_request(direct.job.request_path)
    assert request["kind"] == "lauego_indexing"
    assert request["output"] == {"directory": direct.output_path, "results": RESULTS_FILENAME, "xml": "merged.xml"}
    assert request["request"]["max_peaks"] == 50
    assert request["request"]["min_size"] == 1.13
    assert direct.lauego_parameters.depth_range_len == 2
    assert direct.lauego_parameters.output_xml == "merged.xml"

    assert child.id == 2
    assert child.reconstruction_id == reconstruction.id
    assert child.reconstruction.id == reconstruction.id
    assert child.scan_number == 1
    assert child.job.start_time is None
    assert child.job.finish_time is None
    assert read_request(child.job.request_path)["run"]["reconstruction_id"] == reconstruction.id
    loaded = indexing_workflow.get_indexing(child.id, engine=workflow_engine)
    assert loaded.reconstruction.id == reconstruction.id
    assert loaded.lauego_parameters.crystal_file == "/config/Al.xtal"
    assert indexing_workflow.get_indexing(999, engine=workflow_engine) is None


def test_requests_require_an_id_placeholder_in_the_output_path(tmp_path):
    with pytest.raises(WorkflowValidationError, match="exactly one %d"):
        _wire_request(tmp_path, tmp_path / "fixed-output")


def test_indexing_request_rejects_reserved_support_file_names(tmp_path):
    with pytest.raises(WorkflowValidationError, match="reserved"):
        _indexing_request(tmp_path, tmp_path / "index_%d", output_xml="inputs.jsonl")
    with pytest.raises(WorkflowValidationError, match="reserved"):
        _indexing_request(tmp_path, tmp_path / "index_%d", output_xml="/elsewhere/output.h5")
    assert _indexing_request(tmp_path, tmp_path / "index_%d", output_xml=" ").output_xml is None


def test_file_resolution_finishes_before_the_creation_transaction(workflow_engine, tmp_path, monkeypatch):
    _add_metadata(workflow_engine, 1)
    transaction_begins = 0

    @event.listens_for(workflow_engine, "begin")
    def count_transaction_begins(connection):
        nonlocal transaction_begins
        transaction_begins += 1

    def resolve_before_transaction(*args, **kwargs):
        assert transaction_begins == 0
        return _fake_inputs(tmp_path, 1)

    monkeypatch.setattr(reconstruction_workflow, "resolve_inputs", resolve_before_transaction)
    reconstruction_workflow.create_reconstruction(
        _wire_request(tmp_path / "unlisted", tmp_path / "rec_%d", scan_points="1"),
        engine=workflow_engine,
    )

    assert transaction_begins >= 1


def test_100k_input_manifest_creates_a_constant_number_of_rows(workflow_engine, tmp_path, monkeypatch):
    """P1 exit gate: a 100,000-input run adds three rows, not 100,000."""

    _add_metadata(workflow_engine, 1)
    inputs = _fake_inputs(tmp_path, 100_000)
    monkeypatch.setattr(reconstruction_workflow, "resolve_inputs", lambda *args, **kwargs: inputs)
    rows_before = _row_total(workflow_engine)

    started_at = time.monotonic()
    run = reconstruction_workflow.create_reconstruction(
        _wire_request(tmp_path / "unlisted", tmp_path / "rec_%d", scan_points="1"),
        engine=workflow_engine,
    )
    elapsed = time.monotonic() - started_at

    assert _row_total(workflow_engine) - rows_before == 3  # job, reconstruction_run, wire parameters
    assert run.job.n_inputs == 100_000
    assert elapsed < 20
    with open(run.job.manifest_path, "rb") as handle:
        line_count = sum(1 for _ in handle)
    assert line_count == 100_000
    last = None
    for entry in read_manifest(run.job.manifest_path):
        last = entry
    assert (last.index, last.input_id, last.scan_point) == (99_999, "wire_99999", 99_999)
    verify_manifest(run.job.manifest_path, expected_digest=run.job.manifest_digest, expected_count=100_000)


def test_manifest_publication_keeps_database_reads_responsive(workflow_engine, tmp_path, monkeypatch):
    _add_metadata(workflow_engine, 1)
    inputs = _fake_inputs(tmp_path, 20_000)
    monkeypatch.setattr(reconstruction_workflow, "resolve_inputs", lambda *args, **kwargs: inputs)
    publication_started = threading.Event()
    allow_publication = threading.Event()
    errors = []
    real_write_manifest = run_records.write_manifest

    def paused_write_manifest(*args, **kwargs):
        publication_started.set()
        if not allow_publication.wait(timeout=10):
            raise TimeoutError("test did not release the manifest write")
        return real_write_manifest(*args, **kwargs)

    monkeypatch.setattr(run_records, "write_manifest", paused_write_manifest)

    def create_large_run():
        try:
            reconstruction_workflow.create_reconstruction(
                _wire_request(tmp_path / "unlisted", tmp_path / "rec_%d", scan_points="1"),
                engine=workflow_engine,
            )
        except Exception as error:  # pragma: no cover - reported by the main thread
            errors.append(error)

    creator = threading.Thread(target=create_large_run, daemon=True)
    creator.start()
    assert publication_started.wait(timeout=10)

    read_started_at = time.monotonic()
    assert _count(workflow_engine, db_schema.ReconstructionRun) == 1  # committed before publication
    assert _job(workflow_engine, 1).phase == RunPhase.CREATED
    read_duration = time.monotonic() - read_started_at

    allow_publication.set()
    creator.join(timeout=30)

    assert not creator.is_alive()
    assert errors == []
    assert read_duration < 2
    assert _job(workflow_engine, 1).phase == RunPhase.PUBLISHED


def test_multi_prefix_submission_records_template_identity(workflow_engine, tmp_path):
    _add_metadata(workflow_engine, 1)
    input_path = tmp_path / "wire-input"
    _create_files(input_path, ["left_1.h5", "right_1.h5"])

    run = reconstruction_workflow.create_reconstruction(
        _wire_request(
            input_path,
            tmp_path / "rec_%d",
            filename_prefixes=["left_%d.h5", "right_%d.h5"],
            scan_points="1",
        ),
        engine=workflow_engine,
    )

    entries = list(read_manifest(run.job.manifest_path))
    assert [(entry.input_id, entry.template_index, entry.scan_point) for entry in entries] == [
        ("left_1", 0, 1),
        ("right_1", 1, 1),
    ]


def test_resolution_failure_writes_no_database_rows_or_files(workflow_engine, tmp_path):
    _add_metadata(workflow_engine, 1)
    input_path = tmp_path / "wire-input"
    _create_files(input_path, ["wire_1.h5"])

    with pytest.raises(FileResolutionError, match="for 2"):
        reconstruction_workflow.create_reconstruction(
            _wire_request(input_path, tmp_path / "rec_%d"), engine=workflow_engine
        )

    assert _count(workflow_engine, db_schema.Job) == 0
    assert _count(workflow_engine, db_schema.ReconstructionRun) == 0
    assert not (tmp_path / "rec_1").exists()


def test_database_failure_rolls_back_job_run_and_parameters_without_files(workflow_engine, tmp_path):
    input_path = tmp_path / "wire-input"
    _create_files(input_path, ["wire_1.h5", "wire_2.h5"])

    with pytest.raises(IntegrityError):
        reconstruction_workflow.create_reconstruction(
            _wire_request(input_path, tmp_path / "rec_%d", scan_number=999),
            engine=workflow_engine,
        )

    assert _count(workflow_engine, db_schema.Job) == 0
    assert _count(workflow_engine, db_schema.ReconstructionRun) == 0
    assert _count(workflow_engine, db_schema.WireReconstructionParameters) == 0
    assert not (tmp_path / "rec_1").exists()


def test_publication_failure_records_a_failed_non_runnable_run(workflow_engine, tmp_path):
    _add_metadata(workflow_engine, 1)
    input_path = tmp_path / "wire-input"
    _create_files(input_path, ["wire_1.h5", "wire_2.h5"])
    blocker = tmp_path / "rec_1"
    blocker.write_text("a file where the run directory should be")

    with pytest.raises(RunPublicationError, match=r"Reconstruction R1: Run publication failed"):
        reconstruction_workflow.create_reconstruction(
            _wire_request(input_path, tmp_path / "rec_%d"), engine=workflow_engine
        )

    job = _job(workflow_engine, 1)
    assert job.status == JobStatus.FAILED
    assert job.phase == RunPhase.FAILED
    assert job.finish_time is not None
    assert job.manifest_path is None
    assert (job.n_inputs, job.n_succeeded, job.n_failed, job.n_not_run) == (2, 0, 0, 2)
    assert job.messages.startswith("Run publication failed:")
    with pytest.raises(ExecutionStateError, match="only published runs"):
        assert_enqueueable(job)
    assert blocker.read_text() == "a file where the run directory should be"


def test_a_run_directory_holding_a_manifest_is_never_reused(workflow_engine, tmp_path):
    _add_metadata(workflow_engine, 1)
    input_path = tmp_path / "wire-input"
    _create_files(input_path, ["wire_1.h5", "wire_2.h5"])
    stale = tmp_path / "rec_1"
    stale.mkdir()
    (stale / MANIFEST_FILENAME).write_text(json.dumps({"index": 0}) + "\n")

    with pytest.raises(RunPublicationError, match="never reused"):
        reconstruction_workflow.create_reconstruction(
            _wire_request(input_path, tmp_path / "rec_%d"), engine=workflow_engine
        )

    assert (stale / MANIFEST_FILENAME).read_text() == json.dumps({"index": 0}) + "\n"
    assert _job(workflow_engine, 1).status == JobStatus.FAILED


def test_indexing_rejects_a_scan_that_disagrees_with_its_parent(workflow_engine, tmp_path):
    _add_metadata(workflow_engine, 1, 2)
    wire_input = tmp_path / "wire-input"
    index_input = tmp_path / "index-input"
    _create_files(wire_input, ["wire_1.h5", "wire_2.h5"])
    _create_files(
        index_input,
        ["index_1_0.h5", "index_1_1.h5", "index_2_0.h5", "index_2_1.h5"],
    )
    parent = reconstruction_workflow.create_reconstruction(
        _wire_request(wire_input, tmp_path / "rec_%d"), engine=workflow_engine
    )
    job_count = _count(workflow_engine, db_schema.Job)

    with pytest.raises(WorkflowValidationError, match="does not match"):
        indexing_workflow.create_indexing(
            _indexing_request(
                index_input,
                tmp_path / "index_%d",
                scan_number=2,
                reconstruction_id=parent.id,
            ),
            engine=workflow_engine,
        )

    assert _count(workflow_engine, db_schema.Job) == job_count
    assert _count(workflow_engine, db_schema.IndexingRun) == 0
    assert not (tmp_path / "index_1").exists()
