"""Tests for the unified workflow database schema."""

import sqlite3
from datetime import datetime

import pytest
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from laue_portal.database import db_schema, session_utils
from tests.conftest import (
    create_test_job,
    create_test_metadata,
    create_test_reconstruction_run,
    create_test_wire_reconstruction_parameters,
)


@pytest.fixture
def workflow_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'workflow.db'}")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    db_schema.Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def test_fresh_database_contains_unified_workflow_tables_and_subjob_paths(workflow_engine):
    inspector = inspect(workflow_engine)

    assert {
        "reconstruction_run",
        "wire_reconstruction_parameters",
        "indexing_run",
        "lauego_indexing_parameters",
    } <= set(inspector.get_table_names())
    subjob_columns = {column["name"]: column for column in inspector.get_columns("subjob")}
    assert subjob_columns["input_path"]["nullable"] is True
    assert subjob_columns["output_path"]["nullable"] is True


def test_reconstruction_relationships_are_one_to_one(workflow_engine):
    with Session(workflow_engine) as session:
        metadata = create_test_metadata()
        job = create_test_job()
        run = create_test_reconstruction_run()
        run.wire_parameters = create_test_wire_reconstruction_parameters()
        session.add_all([metadata, job, run])
        session.commit()
        run_id = run.id

    with Session(workflow_engine) as session:
        run = session.get(db_schema.ReconstructionRun, run_id)
        assert run is not None
        assert run.scan.scanNumber == 1
        assert run.job.job_id == 1
        assert run.wire_parameters.reconstruction_id == run.id
        assert run.wire_parameters.reconstruction is run


@pytest.mark.parametrize(
    ("model", "method", "required_values"),
    [
        (
            db_schema.ReconstructionRun,
            "unknown",
            {
                "job_id": 1,
                "input_path": "/input",
                "created_at": datetime(2022, 1, 1),
            },
        ),
        (
            db_schema.IndexingRun,
            "unknown",
            {
                "job_id": 1,
                "input_path": "/input",
                "created_at": datetime(2022, 1, 1),
            },
        ),
    ],
)
def test_method_check_constraints_reject_unknown_values(workflow_engine, model, method, required_values):
    with Session(workflow_engine) as session:
        session.add(create_test_job())
        session.add(model(method=method, **required_values))
        with pytest.raises(IntegrityError):
            session.commit()


def test_application_engine_enables_wal_mode(tmp_path, monkeypatch):
    database_path = tmp_path / "wal.db"
    monkeypatch.setattr("laue_portal.config.db_file", str(database_path))

    engine = session_utils.get_engine()
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA journal_mode").scalar_one().lower() == "wal"
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
    finally:
        engine.dispose()

    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
