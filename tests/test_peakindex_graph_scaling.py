"""Regression checks for full-height peak-indexing graphs."""

from pathlib import Path

CSS = Path(__file__).parents[1] / "assets" / "05-peakindex-viz.css"
PAGE = Path(__file__).parents[1] / "laue_portal" / "pages" / "peakindexing.py"


def test_page_grid_reserves_the_last_row_for_tab_content():
    css = CSS.read_text()

    assert "grid-template-rows: auto auto auto auto minmax(0, 1fr)" in css
    assert ".pi-page > .tab-content {" in css
    assert ".pi-page > .tab-content > .tab-pane.active {" in css
    assert ".pi-page > .lp-detail-tabs {" not in css


def test_dash_tab_child_wrapper_continues_height_chain():
    css = CSS.read_text()

    assert ".pi-page > .tab-content > .tab-pane.active > div {" in css


def test_graph_height_is_passed_through_loading_wrappers():
    css = CSS.read_text()

    assert ".pi-viz-main > div:not(.pi-viz-details) > div { height: 100%; }" in css
    assert ".pi-viz-main > div:not(.pi-viz-details) > div > div { height: 100%; }" in css


def test_graphs_have_no_fixed_minimum_height():
    source = PAGE.read_text()

    assert source.count('style={"height": "100%", "minHeight": 0}') == 3
    assert 'style={"height": "100%", "minHeight": "400px"}' not in source
    assert 'style={"height": "100%", "minHeight": "500px"}' not in source
