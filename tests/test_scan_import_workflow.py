"""Tests for the staged scan-log import page workflow."""

import base64
from pathlib import Path
from unittest.mock import patch

import pytest

import lau_dash  # noqa: F401
from laue_portal.pages import create_scan


@pytest.fixture
def test_xml_data():
    return (Path(__file__).parent / "scan_logs" / "test_log.xml").read_bytes()


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


def test_scan_import_layout_exposes_staged_and_threshold_controls():
    component_ids = set(_component_ids(create_scan.layout))

    assert "bulk-scan-source-token" in component_ids
    assert "bulk-parsed-scans" not in component_ids
    assert "bulk-after-scan-id" in component_ids
    assert "bulk-after-time" in component_ids
    assert "btn-clear-scan-selection" not in component_ids


def test_scan_import_table_defaults_to_newest_first():
    columns = {column["field"]: column for column in create_scan.BULK_SCAN_COLS if "field" in column}

    assert columns["time"]["sort"] == "desc"
    assert "sort" not in columns["scanNumber"]


def test_scan_id_quick_selection_only_returns_new_rows_above_threshold():
    rows = [
        {"scanNumber": "100", "status": "New"},
        {"scanNumber": "101", "status": "Exists"},
        {"scanNumber": "102", "status": "New"},
        {"scanNumber": "bad", "status": "New"},
    ]

    assert create_scan._select_new_rows_after_scan_id(rows, 100) == [rows[2]]


def test_time_quick_selection_only_returns_new_rows_at_or_after_threshold():
    rows = [
        {"time": "2023-02-01T18:40:00", "status": "New"},
        {"time": "2023-02-01T18:41:00", "status": "New"},
        {"time": "2023-02-01T18:42:00", "status": "Exists"},
        {"time": "not-a-time", "status": "New"},
    ]

    assert create_scan._select_new_rows_at_or_after_time(rows, "2023-02-01T18:41") == [rows[1]]


def test_upload_builds_lightweight_rows_and_returns_server_token(test_xml_data):
    contents = "data:text/xml;base64," + base64.b64encode(test_xml_data).decode()

    with (
        patch.object(create_scan.scan_import, "check_existing_scan_numbers", return_value={276990}),
        patch.object(create_scan.scan_import, "stage_scan_log", return_value="a" * 32),
    ):
        result = create_scan.upload_and_parse(contents)

    rows = result[1]
    assert result[2] == "a" * 32
    assert rows[0]["status"] == "Exists"
    assert rows[1]["status"] == "New"
    assert all("log" not in row and "scans" not in row for row in rows)
    assert result[8] == {"display": "block"}


def test_import_fully_parses_only_selected_xml_indices(test_xml_data):
    index = create_scan.scan_import.index_scans_from_xml(test_xml_data)
    rows = [{**entry, "status": "New"} for entry in index]
    selected = [rows[1], rows[3]]
    parsed = create_scan.scan_import.parse_selected_scans_from_xml(test_xml_data, [3, 5])
    results = {
        scan["scanNumber"]: {
            "status": "success",
            "message": f"Scan {scan['scanNumber']} imported successfully",
        }
        for scan in parsed
    }

    with (
        patch.object(create_scan.scan_import, "load_staged_scan_log", return_value=test_xml_data),
        patch.object(
            create_scan.scan_import,
            "parse_selected_scans_from_xml",
            wraps=create_scan.scan_import.parse_selected_scans_from_xml,
        ) as parse_selected,
        patch.object(create_scan.scan_import, "bulk_import_scans", return_value=results),
    ):
        response = create_scan.import_selected_scans(
            1,
            selected,
            rows,
            "a" * 32,
            "wire",
            "sample",
            "/data",
            "scan_",
            "notes",
        )

    parse_selected.assert_called_once_with(test_xml_data, [3, 5])
    assert response[1] == []
    assert response[3] == "Bulk import complete: 2 imported."
    assert [response[0][1]["status"], response[0][3]["status"]] == ["Imported", "Imported"]
