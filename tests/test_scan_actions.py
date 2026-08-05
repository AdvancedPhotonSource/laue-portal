from unittest.mock import patch

import dash
import pytest
from sqlalchemy.orm import Session

import lau_dash  # noqa: F401
import laue_portal.pages.scan as scan_page
from laue_portal.components.recon_form import set_recon_form_props
from laue_portal.pages.create_reconstruction import (
    _merge_recon_scan_updates,
    _parse_pooled_value,
    load_scan_data_from_url,
)
from laue_portal.pages.scan import render_flex_plot, render_role_plot
from laue_portal.pages.scans import handle_recon_button, layout, update_button_states


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


def test_scans_page_only_shows_implemented_actions():
    component_ids = set(_component_ids(layout))

    assert "scans-page-wire-recon-btn" in component_ids
    assert "scans-page-peakindex-btn" in component_ids
    assert "scans-page-recon-index-btn-placeholder" not in component_ids
    assert "scans-page-energy-kspace-btn-placeholder" not in component_ids


@pytest.mark.parametrize(
    ("selected_rows", "expected_disabled"),
    [([], True), ([{"scanNumber": 12}], False)],
)
def test_scan_action_buttons_follow_selection_state(selected_rows, expected_disabled):
    states = update_button_states(selected_rows)

    assert len(states) == 4
    assert states[::2] == (expected_disabled, expected_disabled)


@pytest.mark.parametrize(
    ("rows", "expected_href"),
    [
        ([], "/create-reconstruction"),
        ([{"scanNumber": 12, "aperture": "wire"}], "/create-wire-reconstruction?scan_id=12"),
        ([{"scanNumber": 12, "aperture": "mask"}], "/create-reconstruction?scan_id=12"),
        ([{"scanNumber": 13, "aperture": "none"}], "/create-reconstruction?scan_id=13"),
        ([{"scanNumber": 14, "aperture": None}], "/create-reconstruction?scan_id=14"),
        (
            [
                {"scanNumber": 12, "aperture": "wire"},
                {"scanNumber": 13, "aperture": "mask"},
            ],
            dash.no_update,
        ),
    ],
)
def test_new_recon_routes_selection(rows, expected_href):
    assert handle_recon_button(1, rows) == expected_href


def test_flexible_3d_plot_uses_opaque_square_markers():
    *_, figure = render_flex_plot("3d", "X", "Y", "Z")

    assert figure.data[0].type == "scatter3d"
    assert figure.data[0].marker.symbol == "square"
    assert figure.data[0].marker.opacity == 1.0


def test_role_3d_plot_uses_opaque_square_markers():
    rows = [
        {"var": "x", "isX": "✅"},
        {"var": "y", "isY": "✅"},
        {"var": "z", "isZ": "✅"},
    ]
    figure = render_role_plot("3d", rows, {"x": [0, 1], "y": [0, 1], "z": [0, 1]})

    assert figure.data[0].type == "scatter3d"
    assert figure.data[0].marker.symbol == "square"
    assert figure.data[0].marker.opacity == 1.0


def test_standard_reconstruction_loader_populates_scan_database_values(test_metadata_database):
    test_engine, _test_db_file, metadata, scan, catalog = test_metadata_database
    metadata.motorGroup_sample_cpt_total = 3
    metadata.motorGroup_depth_cpt_total = 4
    catalog.filefolder = "/workspace/data/scan_1"
    catalog.filenamePrefix = ["image_"]
    catalog.notes = "scan notes"
    scan.scan_positioner1_PV = "34ide:t80:c0:m1.VAL"
    scan.scan_positioner1 = "0 10 -0.5"

    with Session(test_engine) as session:
        session.add_all([metadata, scan, catalog])
        session.commit()

    updates = {}

    with (
        patch("laue_portal.pages.create_reconstruction.session_utils.get_engine", return_value=test_engine),
        patch.dict(
            "laue_portal.pages.create_reconstruction.DEFAULT_VARIABLES",
            {"root_path": "/workspace", "author": "", "notes": ""},
        ),
        patch(
            "laue_portal.pages.create_reconstruction.set_props",
            side_effect=lambda component_id, props: updates.update({component_id: props}),
        ),
    ):
        load_scan_data_from_url("http://localhost/create-reconstruction?scan_id=1")

    expected_values = {
        "scanNumber": "1",
        "file_path": "data/scan_1",
        "file_output": "analysis/scan_1/rec_%d",
        "frame_start": 0,
        "frame_end": 12,
        "step": 0.5,
        "author": "test_user",
        "notes": "scan notes",
    }
    assert {field: updates[field]["value"] for field in expected_values} == expected_values
    assert updates["alert-scan-loaded"]["color"] == "warning"
    assert "Still required:" in updates["alert-scan-loaded"]["children"]
    assert "calibration/focus geometry" in updates["alert-scan-loaded"]["children"]


def test_standard_reconstruction_pooling_preserves_per_scan_values():
    merged = _merge_recon_scan_updates(
        [
            {"scanNumber": 12, "file_path": "data/12", "frame_end": 10, "step": 0.5},
            {"scanNumber": 13, "file_path": "data/13", "frame_end": 20, "step": 0.5},
        ]
    )

    assert merged == {
        "scanNumber": "12,13",
        "file_path": "data/12; data/13",
        "frame_end": "10; 20",
        "step": 0.5,
    }
    assert _parse_pooled_value(merged["frame_end"], 2, lambda value: int(float(value))) == [10, 20]
    assert _parse_pooled_value(merged["file_path"], 2) == ["data/12", "data/13"]


def test_existing_reconstruction_uses_distance_for_ceny(test_database):
    _engine, _db_file, _metadata, _job, recon, _catalog = test_database
    updates = {}

    with patch(
        "laue_portal.components.recon_form.set_props",
        side_effect=lambda component_id, props: updates.update({component_id: props}),
    ):
        set_recon_form_props(recon)

    assert updates["calib_id"]["value"] == recon.calib_id
    assert updates["ceny"]["value"] == recon.geo_mask_focus_dist


# ---------------------------------------------------------------------------
# Scan detail page: "New Recon" / "New Index" prefill
# ---------------------------------------------------------------------------
# With nothing ticked in either table these buttons used to drop the user on
# a bare create page with no scan filled in, and "New Recon" always went to
# the coded-aperture form.  They should instead prefill the scan currently
# open on the page and route by that scan's aperture.

_SCAN_PAGE_URL = "http://host/scan?scan_id=276514"
_SCAN_PAGE_URL_NO_ID = "http://host/scan"


def _patch_aperture(aperture):
    """Force ``_recon_page_for_scan`` to resolve to *aperture*'s page."""
    page = "/create-wire-reconstruction" if "wire" in aperture else "/create-reconstruction"
    return patch.object(scan_page, "_recon_page_for_scan", return_value=page)


@pytest.mark.parametrize(
    "href, expected",
    [
        ("http://host/scan?scan_id=276514", "276514"),
        ("http://host/scan", None),
        # Only the first id of a pooled list is a meaningful default.
        ("http://host/scan?scan_id=1,2,3", "1"),
        # Non-numeric ids must not be propagated into a create URL.
        ("http://host/scan?scan_id=abc", None),
        ("http://host/scan?scan_id=", None),
        (None, None),
    ],
)
def test_scan_id_from_href(href, expected):
    assert scan_page._scan_id_from_href(href) == expected


def test_new_recon_with_no_selection_prefills_current_scan():
    with _patch_aperture("wire"):
        recon_href, index_href = scan_page.selected_recon_href([], [], "/create-wire-reconstruction", _SCAN_PAGE_URL)
    assert recon_href == "/create-wire-reconstruction?scan_id=276514"
    assert index_href == "/create-wire-reconstruction?scan_id=276514"


def test_new_recon_with_no_selection_routes_by_aperture():
    with _patch_aperture("mask"):
        recon_href, _ = scan_page.selected_recon_href([], [], "/create-wire-reconstruction", _SCAN_PAGE_URL)
    assert recon_href == "/create-reconstruction?scan_id=276514"


def test_new_recon_without_scan_in_url_falls_back_to_bare_href():
    with _patch_aperture("wire"):
        recon_href, _ = scan_page.selected_recon_href([], [], "/create-wire-reconstruction", _SCAN_PAGE_URL_NO_ID)
    assert recon_href == "/create-wire-reconstruction"


def test_new_index_with_no_selection_prefills_current_scan():
    recon_href, index_href = scan_page.selected_peakindex_href([], [], "/create-peakindexing", _SCAN_PAGE_URL)
    assert recon_href == "/create-peakindexing?scan_id=276514"
    assert index_href == "/create-peakindexing?scan_id=276514"


def test_new_index_without_scan_in_url_falls_back_to_bare_href():
    _, index_href = scan_page.selected_peakindex_href([], [], "/create-peakindexing", _SCAN_PAGE_URL_NO_ID)
    assert index_href == "/create-peakindexing"


def test_selected_rows_still_take_priority_over_page_scan():
    # A ticked row must win over the page-level fallback.
    rows = [{"scanNumber": 999, "wirerecon_id": 5, "recon_id": "", "aperture": "wire"}]
    with _patch_aperture("wire"):
        recon_href, _ = scan_page.selected_recon_href(rows, [], "/create-wire-reconstruction", _SCAN_PAGE_URL)
    assert recon_href == "/create-wire-reconstruction?scan_id=999&wirerecon_id=5"


def test_selected_index_rows_still_take_priority_over_page_scan():
    rows = [{"scanNumber": 999, "wirerecon_id": 5, "recon_id": "", "peakindex_id": 7}]
    _, index_href = scan_page.selected_peakindex_href([], rows, "/create-peakindexing", _SCAN_PAGE_URL)
    assert index_href == "/create-peakindexing?scan_id=999&wirerecon_id=5&peakindex_id=7"


def test_href_rewrite_is_idempotent():
    # The callback reads the button's own href via State and also writes it,
    # so a second firing must not accumulate query strings.
    with _patch_aperture("wire"):
        recon_href, _ = scan_page.selected_recon_href([], [], "/create-wire-reconstruction?scan_id=111", _SCAN_PAGE_URL)
    assert recon_href == "/create-wire-reconstruction?scan_id=276514"

    _, index_href = scan_page.selected_peakindex_href([], [], "/create-peakindexing?scan_id=111", _SCAN_PAGE_URL)
    assert index_href == "/create-peakindexing?scan_id=276514"


def test_recon_page_for_scan_defaults_to_wire_on_unknown_scan():
    # Missing/garbage scans must degrade to the wire form, not raise.
    assert scan_page._recon_page_for_scan(None) == "/create-wire-reconstruction"
    assert scan_page._recon_page_for_scan("not-a-number") == "/create-wire-reconstruction"


@pytest.mark.parametrize(
    "aperture, expected",
    [
        ("wire", "/create-wire-reconstruction"),
        ("Wire", "/create-wire-reconstruction"),
        ("mask", "/create-reconstruction"),
        ("CA", "/create-reconstruction"),
        # Absent / placeholder apertures default to wire rather than CA.
        (None, "/create-wire-reconstruction"),
        ("None", "/create-wire-reconstruction"),
        ("", "/create-wire-reconstruction"),
    ],
)
def test_recon_page_for_scan_maps_aperture_to_form(aperture, expected):
    # Exercises the real aperture lookup (not the _patch_aperture stub) by
    # faking only the DB read, so a routing regression can't slip through.
    class _FakeQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def scalar(self):
            return aperture

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def query(self, *_args, **_kwargs):
            return _FakeQuery()

    with patch.object(scan_page, "Session", lambda *_a, **_k: _FakeSession()):
        assert scan_page._recon_page_for_scan(276514) == expected


def test_scan_page_has_no_dead_recon_index_button():
    # "/create-reconstruction-peakindexing" is not a registered route, so the
    # button that pointed at it was a guaranteed 404 and has been removed.
    # The scan page uses dict ids for pattern-matching callbacks, so keep
    # only the plain string ids before comparing.
    component_ids = {cid for cid in _component_ids(scan_page.layout) if isinstance(cid, str)}
    assert "recon-table-new-recon-index-btn" not in component_ids
    assert "recon-table-new-recon-btn" in component_ids
    assert "recon-table-new-index-btn" in component_ids
