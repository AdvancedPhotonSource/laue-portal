"""Tests for the global data-scope bar on the peak-indexing page."""

import dash
import pytest
from dash import html

from laue_portal.components.visualization.scope_bar import (
    DEFAULT_SCOPE,
    SCOPE_BAR_ID,
    SCOPE_MIN_PEAKS_ID,
    SCOPE_PATTERN0_ID,
    SCOPE_STORE_ID,
    normalize_scope,
    scope_bar,
)

# ---------------------------------------------------------------------------
# normalize_scope
# ---------------------------------------------------------------------------


def test_default_scope_loads_pattern_zero_only():
    assert normalize_scope(DEFAULT_SCOPE) == {"pattern0_only": True, "min_peaks": 4}


@pytest.mark.parametrize("payload", [None, {}, {"unknown_key": 123}])
def test_normalize_scope_defaults_missing_fields(payload):
    """Stores survive reloads and may predate a schema change."""
    assert normalize_scope(payload) == DEFAULT_SCOPE


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, 4),
        ("", 4),
        ("35", 35),
        (12.7, 12),
        (-5, 0),  # negative thresholds are meaningless
        ("abc", 4),  # never raise on garbage
        (20, 20),
    ],
)
def test_normalize_scope_coerces_min_peaks(raw, expected):
    assert normalize_scope({"min_peaks": raw})["min_peaks"] == expected


def test_normalize_scope_coerces_pattern0_to_bool():
    assert normalize_scope({"pattern0_only": "yes"})["pattern0_only"] is True
    assert normalize_scope({"pattern0_only": None})["pattern0_only"] is False


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


def _walk(component):
    yield component
    children = getattr(component, "children", None)
    if children is None:
        return
    if not isinstance(children, (list, tuple)):
        children = [children]
    for child in children:
        if hasattr(child, "children") or hasattr(child, "id"):
            yield from _walk(child)


def test_scope_bar_owns_a_single_scope_store():
    ids = [getattr(c, "id", None) for c in _walk(scope_bar())]
    assert ids.count(SCOPE_STORE_ID) == 1


def test_scope_bar_is_collapsed_by_default():
    """Collapsing is delegated to dbc.Accordion -- no toggle callback."""
    import dash_bootstrap_components as dbc

    accordion = next(c for c in _walk(scope_bar()) if isinstance(c, dbc.Accordion))
    assert accordion.start_collapsed is True


def test_scope_bar_title_is_static():
    """The header carries no live state, so no callback has to maintain it."""
    import dash_bootstrap_components as dbc

    item = next(c for c in _walk(scope_bar()) if isinstance(c, dbc.AccordionItem))
    assert item.title == "Data scope"


def test_scope_bar_reflects_supplied_scope():
    bar = scope_bar({"pattern0_only": True, "min_peaks": 20}, is_open=True)
    assert bar.id == SCOPE_BAR_ID

    store = next(c for c in _walk(bar) if getattr(c, "id", None) == SCOPE_STORE_ID)
    assert store.data == {"pattern0_only": True, "min_peaks": 20}

    widgets = {getattr(c, "id", None): c for c in _walk(bar)}
    assert widgets[SCOPE_PATTERN0_ID].value is True
    assert widgets[SCOPE_MIN_PEAKS_ID].value == 19


def test_scope_bar_defaults_to_skipping_three_or_fewer_peaks():
    bar = scope_bar()
    widgets = {getattr(c, "id", None): c for c in _walk(bar)}

    assert widgets[SCOPE_MIN_PEAKS_ID].value == 3
    label = next(c for c in _walk(bar) if isinstance(c, html.Label))
    assert label.children == "Skip steps with peaks ≤"

    help_text = next(c for c in _walk(bar) if isinstance(c, html.Small))
    assert help_text.children == "0 keeps every step."


# ---------------------------------------------------------------------------
# Page integration
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def peakindexing_page():
    """Import the page module.

    ``dash.register_page`` at import time requires an instantiated app, so
    one is created first.  Module-scoped because a page may only be
    registered once per process.
    """
    dash.Dash(__name__, use_pages=True, pages_folder="")
    import laue_portal.pages.peakindexing as peakindexing

    return peakindexing


def test_scope_bar_sits_between_header_and_tabs(peakindexing_page):
    """Scope is global, so it must not be nested inside any single tab."""
    peakindexing = peakindexing_page

    children = peakindexing.layout.children
    type_names = [type(c).__name__ for c in children]

    header_idx = next(i for i, c in enumerate(children) if getattr(c, "id", None) == "peakindex-id-header")
    bar_idx = next(i for i, c in enumerate(children) if getattr(c, "id", None) == SCOPE_BAR_ID)
    tabs_idx = type_names.index("Tabs")

    assert header_idx < bar_idx < tabs_idx


def test_page_uses_flex_shell_instead_of_hardcoded_height(peakindexing_page):
    assert peakindexing_page.layout.className == "pi-page"


def test_pole_hkl_has_manual_update_state(peakindexing_page):
    widgets = {getattr(c, "id", None): c for c in _walk(peakindexing_page.layout)}

    assert widgets["stereo-applied-hkl"].data == [1, 0, 0]
    assert widgets["stereo-hkl-update-btn"].children == "Update"
    assert widgets["stereo-hkl-update-btn"].disabled is True


def test_map_graphs_have_cursor_readouts(peakindexing_page):
    widgets = {getattr(c, "id", None): c for c in _walk(peakindexing_page.layout)}

    assert widgets["orientation-cursor-readout"].children == "x: —   y: —"
    assert widgets["stereo-cursor-readout"].children == "x: —   y: —"


def test_color_map_has_nonindexed_appearance_choices(peakindexing_page):
    widgets = {getattr(c, "id", None): c for c in _walk(peakindexing_page.layout)}
    select = widgets["orientation-nonindexed-style"]

    assert select.value == "gray"
    assert [option["value"] for option in select.options] == [
        "gray",
        "red",
        "blue",
        "green",
        "transparent",
    ]


def test_apply_stereo_hkl_validates_and_stores_integer_triplet(peakindexing_page):
    assert peakindexing_page.apply_stereo_hkl(1, 3, 2, 1) == [3, 2, 1]
    with pytest.raises(dash.exceptions.PreventUpdate):
        peakindexing_page.apply_stereo_hkl(1, 0, 0, 0)


def test_peakindexing_callbacks_resolve_against_layout(peakindexing_page):
    """Catches typo'd or duplicated component IDs in the new callbacks."""
    peakindexing = peakindexing_page

    app = dash.Dash(__name__, use_pages=True, pages_folder="")
    dash.register_page("scope_bar_probe", layout=peakindexing.layout, path="/probe")
    app.layout = dash.page_container
    app.validation_layout = html.Div([peakindexing.layout, dash.page_container])

    app._setup_server()  # validates every callback id against the layout
