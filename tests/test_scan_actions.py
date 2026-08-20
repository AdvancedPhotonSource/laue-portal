import pytest

import lau_dash  # noqa: F401
import laue_portal.pages.scan as scan_page
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
        ([], "/create-wire-reconstruction"),
        ([{"scanNumber": 12, "aperture": "wire"}], "/create-wire-reconstruction?scan_id=12"),
        ([{"scanNumber": 12, "aperture": "mask"}], "/create-wire-reconstruction?scan_id=12"),
        ([{"scanNumber": 13, "aperture": "none"}], "/create-wire-reconstruction?scan_id=13"),
        ([{"scanNumber": 14, "aperture": None}], "/create-wire-reconstruction?scan_id=14"),
        (
            [
                {"scanNumber": 12, "aperture": "wire"},
                {"scanNumber": 13, "aperture": "mask"},
            ],
            "/create-wire-reconstruction?scan_id=12,13",
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


def test_ca_creation_page_is_an_unavailable_shim():
    from laue_portal.pages.create_reconstruction import layout as ca_layout

    submit_button = next(
        component for component in ca_layout._traverse() if getattr(component, "id", None) == "submit_recon"
    )
    assert submit_button.disabled is True


# ---------------------------------------------------------------------------
# Scan detail page: "New Recon" / "New Index" prefill
# ---------------------------------------------------------------------------
# With nothing ticked in either table these buttons used to drop the user on
# a bare create page with no scan filled in, and "New Recon" always went to
# the coded-aperture form.  They should instead prefill the scan currently
# open on the page and use the standard wire form.

_SCAN_PAGE_URL = "http://host/scan?scan_id=276514"
_SCAN_PAGE_URL_NO_ID = "http://host/scan"


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
    recon_href, index_href = scan_page.selected_recon_href([], [], _SCAN_PAGE_URL, "/create-wire-reconstruction")
    assert recon_href == "/create-wire-reconstruction?scan_id=276514"
    assert index_href == "/create-wire-reconstruction?scan_id=276514"


def test_new_recon_without_scan_in_url_falls_back_to_bare_href():
    recon_href, _ = scan_page.selected_recon_href([], [], _SCAN_PAGE_URL_NO_ID, "/create-wire-reconstruction")
    assert recon_href == "/create-wire-reconstruction"


def test_new_index_with_no_selection_prefills_current_scan():
    recon_href, index_href = scan_page.selected_peakindex_href([], [], _SCAN_PAGE_URL, "/create-peakindexing")
    assert recon_href == "/create-peakindexing?scan_id=276514"
    assert index_href == "/create-peakindexing?scan_id=276514"


def test_new_index_without_scan_in_url_falls_back_to_bare_href():
    _, index_href = scan_page.selected_peakindex_href([], [], _SCAN_PAGE_URL_NO_ID, "/create-peakindexing")
    assert index_href == "/create-peakindexing"


def test_selected_rows_still_take_priority_over_page_scan():
    # A ticked row must win over the page-level fallback.
    rows = [{"scan_number": 999, "reconstruction_id": 5, "method": "wire"}]
    recon_href, _ = scan_page.selected_recon_href(rows, [], _SCAN_PAGE_URL, "/create-wire-reconstruction")
    assert recon_href == "/create-wire-reconstruction?scan_id=999&reconstruction_id=5"


def test_selected_ca_row_uses_scan_without_copying_incompatible_run():
    rows = [{"scan_number": 999, "reconstruction_id": 5, "method": "ca"}]
    recon_href, _ = scan_page.selected_recon_href(rows, [], _SCAN_PAGE_URL, "/create-wire-reconstruction")
    assert recon_href == "/create-wire-reconstruction?scan_id=999"


def test_selected_index_rows_still_take_priority_over_page_scan():
    rows = [{"scan_number": 999, "reconstruction_id": 5, "indexing_id": 7}]
    _, index_href = scan_page.selected_peakindex_href([], rows, _SCAN_PAGE_URL, "/create-peakindexing")
    assert index_href == "/create-peakindexing?scan_id=999&reconstruction_id=5&indexing_id=7"


def test_href_rewrite_is_idempotent():
    # The callback reads the button's own href via State and also writes it,
    # so a second firing must not accumulate query strings.
    recon_href, _ = scan_page.selected_recon_href([], [], _SCAN_PAGE_URL, "/create-wire-reconstruction?scan_id=111")
    assert recon_href == "/create-wire-reconstruction?scan_id=276514"

    _, index_href = scan_page.selected_peakindex_href([], [], _SCAN_PAGE_URL, "/create-peakindexing?scan_id=111")
    assert index_href == "/create-peakindexing?scan_id=276514"


@pytest.mark.parametrize(
    "scan_id",
    [None, "not-a-number", 276514],
)
def test_recon_page_for_scan_always_uses_wire(scan_id):
    assert scan_page._recon_page_for_scan(scan_id) == "/create-wire-reconstruction"


@pytest.mark.parametrize(
    "button_id",
    [
        "recon-table-new-recon-btn",
        "recon-table-new-index-btn",
    ],
)
def test_href_callbacks_listen_to_page_url_as_input(button_id):
    """
    The page URL must be an Input on the href callbacks.

    Regression guard: these callbacks are otherwise triggered only by
    ``selectedRows``.  If the user never ticks a row those Inputs never
    fire, so with the URL as State the callback never runs at all and the
    button keeps its static href with no ``scan_id`` -- the buttons route
    to the right page but fail to prefill.  Calling the callback functions
    directly cannot catch this, so assert the wiring itself.
    """
    from dash._callback import GLOBAL_CALLBACK_MAP

    spec = next(spec for key, spec in GLOBAL_CALLBACK_MAP.items() if button_id in str(key))
    input_ids = {inp["id"] for inp in spec["inputs"]}
    state_ids = {st["id"] for st in spec["state"]}

    assert "url-scan-page" in input_ids, f"{button_id}: page URL must be an Input so the callback fires on page load"
    assert "url-scan-page" not in state_ids


def test_scan_page_has_no_dead_recon_index_button():
    # "/create-reconstruction-peakindexing" is not a registered route, so the
    # button that pointed at it was a guaranteed 404 and has been removed.
    # The scan page uses dict ids for pattern-matching callbacks, so keep
    # only the plain string ids before comparing.
    component_ids = {cid for cid in _component_ids(scan_page.layout) if isinstance(cid, str)}
    assert "recon-table-new-recon-index-btn" not in component_ids
    assert "recon-table-new-recon-btn" in component_ids
    assert "recon-table-new-index-btn" in component_ids
