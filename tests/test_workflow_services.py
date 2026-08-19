"""Tests for reconstruction and indexing creation services."""

import os
from datetime import datetime

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from laue_portal.database import db_schema
from laue_portal.workflows import FileResolutionError, WorkflowValidationError
from laue_portal.workflows import indexing as indexing_workflow
from laue_portal.workflows import reconstruction as reconstruction_workflow
from tests.conftest import create_test_metadata


@pytest.fixture
def workflow_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'services.db'}")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

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


def _subjobs_for(engine, job_id):
    with Session(engine) as session:
        return session.scalars(
            select(db_schema.SubJob).where(db_schema.SubJob.job_id == job_id).order_by(db_schema.SubJob.subjob_id)
        ).all()


def test_create_reconstruction_persists_one_short_atomic_workflow(workflow_engine, tmp_path):
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
    assert run.job.status == 0
    assert run.job.submit_time == datetime(2026, 8, 19, 12, 0, 0)
    assert run.job.start_time is None
    assert run.job.finish_time is None
    subjobs = _subjobs_for(workflow_engine, run.job_id)
    assert [os.path.basename(subjob.input_path) for subjob in subjobs] == [
        "wire_1.h5",
        "wire_2.h5",
    ]
    assert [subjob.output_path for subjob in subjobs] == [
        os.path.join(expected_output, "wire_1_"),
        os.path.join(expected_output, "wire_2_"),
    ]
    assert all(subjob.start_time is None and subjob.finish_time is None for subjob in subjobs)
    assert subjob_inserts == [True]
    assert not (tmp_path / "analysis").exists()
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
    direct_subjobs = _subjobs_for(workflow_engine, direct.job_id)
    assert len(direct_subjobs) == 4
    assert all(subjob.output_path == direct.output_path for subjob in direct_subjobs)
    assert direct.lauego_parameters.depth_range_len == 2
    assert direct.lauego_parameters.output_xml == "merged.xml"

    assert child.id == 2
    assert child.reconstruction_id == reconstruction.id
    assert child.reconstruction.id == reconstruction.id
    assert child.scan_number == 1
    assert child.job.start_time is None
    assert child.job.finish_time is None
    loaded = indexing_workflow.get_indexing(child.id, engine=workflow_engine)
    assert loaded.reconstruction.id == reconstruction.id
    assert loaded.lauego_parameters.crystal_file == "/config/Al.xtal"
    assert indexing_workflow.get_indexing(999, engine=workflow_engine) is None


def test_requests_require_an_id_placeholder_in_the_output_path(tmp_path):
    with pytest.raises(WorkflowValidationError, match="exactly one %d"):
        _wire_request(tmp_path, tmp_path / "fixed-output")


def test_file_resolution_finishes_before_the_creation_transaction(workflow_engine, tmp_path, monkeypatch):
    _add_metadata(workflow_engine, 1)
    transaction_begins = 0

    @event.listens_for(workflow_engine, "begin")
    def count_transaction_begins(connection):
        nonlocal transaction_begins
        transaction_begins += 1

    def resolve_before_transaction(*args, **kwargs):
        assert transaction_begins == 0
        return (os.fspath(tmp_path / "wire_1.h5"),)

    monkeypatch.setattr(reconstruction_workflow, "resolve_input_files", resolve_before_transaction)
    reconstruction_workflow.create_reconstruction(
        _wire_request(tmp_path / "unlisted", tmp_path / "rec_%d", scan_points="1"),
        engine=workflow_engine,
    )

    assert transaction_begins >= 1


def test_large_resolved_run_bulk_inserts_subjobs_in_bounded_batches(workflow_engine, tmp_path, monkeypatch):
    _add_metadata(workflow_engine, 1)
    input_files = tuple(os.fspath(tmp_path / f"wire_{index}.h5") for index in range(20_001))
    monkeypatch.setattr(
        reconstruction_workflow,
        "resolve_input_files",
        lambda *args, **kwargs: input_files,
    )
    subjob_inserts = []

    @event.listens_for(workflow_engine, "before_cursor_execute")
    def observe_subjob_insert(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO subjob"):
            subjob_inserts.append((executemany, len(parameters)))

    reconstruction_workflow.create_reconstruction(
        _wire_request(tmp_path / "unlisted", tmp_path / "rec_%d", scan_points="1"),
        engine=workflow_engine,
    )

    assert _count(workflow_engine, db_schema.SubJob) == 20_001
    assert subjob_inserts == [(True, 10_000), (True, 10_000), (False, 6)]


def test_resolution_failure_writes_no_database_rows(workflow_engine, tmp_path):
    _add_metadata(workflow_engine, 1)
    input_path = tmp_path / "wire-input"
    _create_files(input_path, ["wire_1.h5"])

    with pytest.raises(FileResolutionError, match="for 2"):
        reconstruction_workflow.create_reconstruction(
            _wire_request(input_path, tmp_path / "rec_%d"), engine=workflow_engine
        )

    assert _count(workflow_engine, db_schema.Job) == 0
    assert _count(workflow_engine, db_schema.ReconstructionRun) == 0
    assert _count(workflow_engine, db_schema.SubJob) == 0


def test_database_failure_rolls_back_job_run_parameters_and_subjobs(workflow_engine, tmp_path):
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
    assert _count(workflow_engine, db_schema.SubJob) == 0


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
