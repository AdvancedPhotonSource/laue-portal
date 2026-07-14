from datetime import datetime
from unittest.mock import patch

import dash
import pytest
from dash.exceptions import PreventUpdate
from sqlalchemy.orm import Session

import lau_dash  # noqa: F401
import laue_portal.database.db_schema as db_schema
from laue_portal.pages.wire_reconstructions import (
    _get_recons,
    get_recons,
    handle_peakindex_button,
    handle_recon_button,
    layout,
    update_button_states,
)
from laue_portal.processing.queue.core import STATUS_REVERSE_MAPPING


def _component_ids(component):
    component_id = getattr(component, "id", None)
    if component_id:
        yield component_id

    children = getattr(component, "children", None)
    if children is None:
        return
    if not isinstance(children, (list, tuple)):
        children = [children]
    for child in children:
        yield from _component_ids(child)


def _wire_recon(job_id=1, scan_number=12):
    return db_schema.WireRecon(
        scanNumber=scan_number,
        job_id=job_id,
        filefolder="/test/input",
        filenamePrefix=["wire_"],
        author="test user",
        notes="test notes",
        geoFile="/test/geo.xml",
        percent_brightest=0.5,
        wire_edges="leading",
        depth_start=0.0,
        depth_end=10.0,
        depth_resolution=0.5,
        num_threads=2,
        memory_limit_mb=1024,
        scanPoints="1-4",
        scanPointslen=4,
        outputFolder="/test/output",
        verbose=0,
    )


def test_wire_reconstructions_page_only_shows_implemented_actions():
    component_ids = set(_component_ids(layout))

    assert "wire-recons-page-wire-recon-btn" in component_ids
    assert "wire-recons-page-peakindex-btn" in component_ids
    assert "wire-recons-page-recon-index-btn-placeholder" not in component_ids


@pytest.mark.parametrize(
    ("selected_rows", "expected_disabled"),
    [([], True), ([{"wirerecon_id": 3, "scanNumber": 12}], False)],
)
def test_wire_recon_action_buttons_follow_selection_state(selected_rows, expected_disabled):
    states = update_button_states(selected_rows)

    assert len(states) == 4
    assert states[::2] == (expected_disabled, expected_disabled)


@pytest.mark.parametrize(
    ("rows", "expected_href"),
    [
        ([], "/create-wire-reconstruction"),
        (
            [{"wirerecon_id": 3, "scanNumber": 12}],
            "/create-wire-reconstruction?scan_id=12&wirerecon_id=3",
        ),
        (
            [
                {"wirerecon_id": 3, "scanNumber": 12},
                {"wirerecon_id": 4, "scanNumber": 13},
            ],
            "/create-wire-reconstruction?scan_id=12,13&wirerecon_id=3,4",
        ),
    ],
)
def test_new_wire_recon_routes_selection(rows, expected_href):
    assert handle_recon_button(1, rows) == expected_href


@pytest.mark.parametrize(
    ("rows", "expected_href"),
    [
        ([], "/create-peakindexing"),
        (
            [{"wirerecon_id": 3, "scanNumber": 12}],
            "/create-peakindexing?scan_id=12&wirerecon_id=3",
        ),
        (
            [
                {"wirerecon_id": 3, "scanNumber": 12},
                {"wirerecon_id": 4, "scanNumber": 13},
            ],
            "/create-peakindexing?scan_id=12,13&wirerecon_id=3,4",
        ),
    ],
)
def test_new_peakindex_routes_wire_recon_selection(rows, expected_href):
    assert handle_peakindex_button(1, rows) == expected_href


def test_wire_recon_table_matches_peakindex_columns(empty_test_database):
    test_engine, _ = empty_test_database
    running = STATUS_REVERSE_MAPPING["Running"]
    finished = STATUS_REVERSE_MAPPING["Finished"]

    with Session(test_engine) as session:
        session.add(
            db_schema.Job(
                job_id=1,
                computer_name="localhost",
                status=running,
                priority=0,
                submit_time=datetime(2026, 7, 14, 12, 0, 0),
            )
        )
        session.add(_wire_recon())
        session.add_all(
            [
                db_schema.SubJob(job_id=1, computer_name="localhost", status=finished, priority=0),
                db_schema.SubJob(job_id=1, computer_name="localhost", status=running, priority=0),
            ]
        )
        session.commit()

    with patch("laue_portal.database.session_utils.get_engine", return_value=test_engine):
        columns, rows = _get_recons()

    assert [column["headerName"] for column in columns] == [
        "",
        "Wire Reconstruction ID",
        "Source",
        "Points",
        "Author",
        "Notes",
        "Date",
        "Status",
    ]
    assert "Actions" not in {column["headerName"] for column in columns}
    assert columns[2]["cellRenderer"] == "ScanSourceLinkRenderer"
    assert rows[0]["scanNumber"] == 12
    assert rows[0]["scanPointslen"] == 4
    assert rows[0]["status_progress"] == "1/2"


def test_wire_recon_table_callback_path(empty_test_database):
    test_engine, _ = empty_test_database

    with patch("laue_portal.database.session_utils.get_engine", return_value=test_engine):
        columns, rows = get_recons("/wire-reconstructions")

    assert columns
    assert rows == []
    with pytest.raises(PreventUpdate):
        get_recons("/wrong-path")


def test_wire_recon_actions_ignore_initial_callback():
    assert handle_recon_button(0, []) is dash.no_update
    assert handle_peakindex_button(0, []) is dash.no_update
