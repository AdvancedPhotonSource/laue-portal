"""Focused smoke tests for unified indexing list retrieval."""

from datetime import datetime
from unittest.mock import patch

import dash
import pytest
from dash.exceptions import PreventUpdate
from sqlalchemy.orm import Session

import lau_dash  # noqa: F401
from laue_portal.database import db_schema
from laue_portal.pages.peakindexings import (
    _get_peakindexings,
    get_peakindexings,
    handle_peakindex_button,
    handle_recon_button,
)
from tests.conftest import create_test_indexing_run, create_test_lauego_parameters


def _add_indexing(engine):
    with Session(engine) as session:
        job = db_schema.Job(
            job_id=2,
            computer_name="localhost",
            status=2,
            priority=0,
            submit_time=datetime(2026, 8, 1),
        )
        run = create_test_indexing_run(scan_number=None, job_id=2)
        run.lauego_parameters = create_test_lauego_parameters()
        session.add_all([job, run])
        session.commit()
        return run.id


def test_get_indexings_uses_canonical_fields(empty_test_database):
    engine, _ = empty_test_database
    indexing_id = _add_indexing(engine)

    with patch("laue_portal.database.session_utils.get_engine", return_value=engine):
        columns, rows = _get_peakindexings()

    assert len(rows) == 1
    assert rows[0]["indexing_id"] == indexing_id
    assert rows[0]["scan_number"] is None
    assert rows[0]["reconstruction_id"] is None
    assert rows[0]["method"] == "lauego"
    assert "peakindex_id" not in rows[0]
    assert "wirerecon_id" not in rows[0]
    assert "recon_id" not in rows[0]

    id_column = next(column for column in columns if column["field"] == "indexing_id")
    assert id_column["cellRenderer"] == "IndexingLinkRenderer"


def test_get_indexings_callback(empty_test_database):
    engine, _ = empty_test_database
    _add_indexing(engine)

    with patch("laue_portal.database.session_utils.get_engine", return_value=engine):
        columns, rows = get_peakindexings("/peakindexings")
    assert columns
    assert len(rows) == 1

    with pytest.raises(PreventUpdate):
        get_peakindexings("/wrong-path")


def test_get_indexings_handles_empty_database(empty_test_database):
    engine, _ = empty_test_database
    with patch("laue_portal.database.session_utils.get_engine", return_value=engine):
        columns, rows = _get_peakindexings()

    assert columns
    assert rows == []


def test_actions_do_not_serialize_pandas_nan_as_an_id():
    direct_indexing = {
        "scan_number": float("nan"),
        "reconstruction_id": float("nan"),
        "indexing_id": 7.0,
        "reconstruction_method": None,
        "aperture": None,
    }
    assert handle_recon_button(1, [direct_indexing]) is dash.no_update
    assert handle_peakindex_button(1, [direct_indexing]) == "/create-peakindexing?indexing_id=7"
