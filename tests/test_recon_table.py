"""Focused tests for the unified reconstruction list."""

from datetime import datetime
from unittest.mock import patch

import pytest
from dash.exceptions import PreventUpdate
from sqlalchemy.orm import Session

import lau_dash
from laue_portal.database import db_schema
from laue_portal.pages.reconstructions import _get_recons, get_recons


def _add_ca_run(engine):
    with Session(engine) as session:
        job = db_schema.Job(
            computer_name="localhost",
            status=2,
            priority=0,
            submit_time=datetime(2026, 8, 1),
        )
        session.add(job)
        session.flush()
        run = db_schema.ReconstructionRun(
            scan_number=None,
            job_id=job.job_id,
            method="ca",
            input_path="/data/input",
            output_path="/data/output",
            author="tester",
            notes="reserved CA row",
            created_at=datetime(2026, 8, 1),
        )
        session.add(run)
        session.commit()
        return run.id


def test_reconstruction_list_reads_ca_rows_without_wire_parameters(empty_test_database):
    engine, _ = empty_test_database
    reconstruction_id = _add_ca_run(engine)

    with patch("laue_portal.database.session_utils.get_engine", return_value=engine):
        columns, rows = _get_recons()

    assert rows == [
        {
            "reconstruction_id": reconstruction_id,
            "method": "ca",
            "scan_number": None,
            "scan_points_len": None,
            "author": "tester",
            "notes": "reserved CA row",
            "submit_time": datetime(2026, 8, 1),
            "start_time": None,
            "finish_time": None,
            "status": 2,
            "completed_subjobs": 0,
            "total_subjobs": 0,
            "status_progress": None,
        }
    ]
    id_column = next(column for column in columns if column["field"] == "reconstruction_id")
    assert id_column["cellRenderer"] == "ReconstructionLinkRenderer"
    assert "Actions" not in {column["headerName"] for column in columns}


def test_reconstruction_list_includes_wire_runs(empty_test_database):
    engine, _ = empty_test_database
    with Session(engine) as session:
        job = db_schema.Job(computer_name="localhost", status=0, priority=0)
        session.add(job)
        session.flush()
        session.add(
            db_schema.ReconstructionRun(
                job_id=job.job_id,
                method="wire",
                input_path="/data/input",
                output_path="/data/output",
                created_at=datetime(2026, 8, 1),
            )
        )
        session.commit()

    with patch("laue_portal.database.session_utils.get_engine", return_value=engine):
        _, rows = _get_recons()
    assert len(rows) == 1
    assert rows[0]["method"] == "wire"


def test_reconstruction_list_callback_and_empty_database(empty_test_database):
    engine, _ = empty_test_database
    with patch("laue_portal.database.session_utils.get_engine", return_value=engine):
        columns, rows = get_recons("/reconstructions")
    assert columns
    assert rows == []

    with pytest.raises(PreventUpdate):
        get_recons("/wrong-path")


def test_legacy_wire_reconstruction_list_redirects_to_unified_page():
    routes = {str(rule) for rule in lau_dash.app.server.url_map.iter_rules()}

    assert "/wire-reconstructions" in routes
