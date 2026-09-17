"""Tests for the result page's artifact discovery and conversion button."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import dash
import pytest
from dash.exceptions import PreventUpdate
from sqlalchemy.orm import Session

import lau_dash  # noqa: F401  instantiates the Dash app so page modules can register
from laue_portal.database import db_schema
from laue_portal.pages import peakindexing
from laue_portal.services import indexing_results as service
from tests.conftest import create_test_lauego_parameters, create_test_metadata
from tests.run_support import make_engine

FIXTURE_XML = Path(__file__).parent / "fixtures" / "test_indexing.xml"


@pytest.fixture
def engine(tmp_path, monkeypatch):
    yield make_engine(tmp_path, monkeypatch)


def _add_run(engine, run_id, output_path, xml_name="output.xml"):
    with Session(engine) as session:
        session.add(create_test_metadata(1))
        session.add(
            db_schema.Job(job_id=run_id, computer_name="h", status=2, priority=0, submit_time=datetime(2026, 1, 1))
        )
        run = db_schema.IndexingRun(
            id=run_id,
            job_id=run_id,
            scan_number=1,
            method="lauego",
            input_path="/data",
            output_path=str(output_path),
            created_at=datetime(2026, 1, 1),
        )
        parameters = create_test_lauego_parameters()
        parameters.output_xml = xml_name
        run.lauego_parameters = parameters
        session.add(run)
        session.commit()


def test_page_loader_reports_xml_only_then_results_after_conversion(engine, tmp_path):
    directory = tmp_path / "index_7"
    directory.mkdir()
    shutil.copy(FIXTURE_XML, directory / "output.xml")
    _add_run(engine, 7, directory)
    href = "http://localhost/peakindexing?indexing_id=7"

    with patch.object(peakindexing, "set_peakindex_form_props"):
        header, source, context, artifacts = peakindexing.load_peakindexing_data(href)

    assert source == {"path": str(directory / "output.xml"), "kind": "xml", "geometry": None}
    assert artifacts["status"] == service.STATUS_XML_ONLY
    assert artifacts["indexing_id"] == 7
    text, convertible = peakindexing.artifact_status_text(artifacts)
    assert text == "XML only:" and convertible is True
    assert peakindexing.render_artifact_status(artifacts) == (
        text,
        {},
        "lp-artifact-bar d-flex align-items-center gap-2 px-3 py-1",
    )

    message, icon, is_open, new_href = peakindexing.convert_results(1, artifacts, href)
    assert (icon, is_open, new_href) == ("success", True, href)
    assert message.startswith("I7: converted: 4 frames")
    with Session(engine) as session:
        assert session.get(db_schema.IndexingRun, 7).results_path == str(directory / "output.h5")

    with patch.object(peakindexing, "set_peakindex_form_props"):
        _, source, _, artifacts = peakindexing.load_peakindexing_data(href)
    assert source == {"path": str(directory / "output.h5"), "kind": "results"}  # results preferred once present
    assert artifacts["status"] == service.STATUS_RESULTS
    assert artifacts["results_summary"]["n_frames"] == 4
    text, convertible = peakindexing.artifact_status_text(artifacts)
    assert text == "" and convertible is False
    assert peakindexing.render_artifact_status(artifacts)[1] == {"display": "none"}
    assert peakindexing.render_artifact_status(artifacts)[2] == "lp-artifact-bar d-none"


def test_page_loader_never_guesses_between_xml_files(engine, tmp_path):
    directory = tmp_path / "index_8"
    directory.mkdir()
    shutil.copy(FIXTURE_XML, directory / "a.xml")
    shutil.copy(FIXTURE_XML, directory / "b.xml")
    _add_run(engine, 8, directory, xml_name="missing.xml")

    with patch.object(peakindexing, "set_peakindex_form_props"):
        _, source, _, artifacts = peakindexing.load_peakindexing_data("http://localhost/peakindexing?indexing_id=8")

    assert source is None
    assert artifacts["status"] == service.STATUS_AMBIGUOUS
    text, convertible = peakindexing.artifact_status_text(artifacts)
    assert "choose one manually: a.xml, b.xml" in text and convertible is False
    with pytest.raises(PreventUpdate):
        peakindexing.convert_results(1, artifacts, "http://localhost/peakindexing?indexing_id=8")


def test_conversion_button_reports_a_malformed_document(engine, tmp_path):
    directory = tmp_path / "index_9"
    directory.mkdir()
    (directory / "output.xml").write_text("<AllSteps>\n")
    _add_run(engine, 9, directory)
    href = "http://localhost/peakindexing?indexing_id=9"
    with patch.object(peakindexing, "set_peakindex_form_props"):
        _, _, _, artifacts = peakindexing.load_peakindexing_data(href)

    message, icon, is_open, new_href = peakindexing.convert_results(1, artifacts, href)

    assert (icon, is_open, new_href) == ("danger", True, dash.no_update)
    assert message.startswith("I9: malformed: ParseError")
    assert peakindexing.artifact_status_text(None) == ("", False)
    assert peakindexing.artifact_status_text({"status": service.STATUS_MISSING})[0].startswith("No results file")
