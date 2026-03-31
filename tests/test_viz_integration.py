"""Integration tests for visualization components using synthetic fixture."""

import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from laue_portal.analysis.xml_parser import (
    parse_indexing_xml, get_step_peaks, get_all_indexed_peaks,
)
from laue_portal.components.visualization.orientation_map import (
    make_orientation_map,
    make_orientation_map_3d,
)
from laue_portal.components.visualization.quality_map import (
    make_quality_map,
    make_quality_map_3d,
)
from laue_portal.components.visualization.peak_table import make_peak_table

FIXTURE_XML = os.path.join(os.path.dirname(__file__), "fixtures", "test_indexing.xml")


def _parsed():
    return parse_indexing_xml(FIXTURE_XML)


def test_orientation_map_creates_figure():
    fig = make_orientation_map(_parsed(), color_by="n_indexed")
    assert len(fig.data) == 1
    assert fig.data[0].type == "scattergl"


def test_orientation_map_all_color_modes():
    parsed = _parsed()
    for mode in ("n_indexed", "goodness", "rms_error", "n_patterns"):
        fig = make_orientation_map(parsed, color_by=mode)
        assert len(fig.data) >= 1


def test_quality_map_creates_figure():
    fig = make_quality_map(_parsed(), metric="goodness")
    assert len(fig.data) == 1
    assert fig.data[0].type == "scattergl"


def test_quality_map_all_metrics():
    parsed = _parsed()
    for metric in ("goodness", "rms_error", "n_indexed", "n_patterns"):
        fig = make_quality_map(parsed, metric=metric)
        assert len(fig.data) >= 1


def test_orientation_map_marker_size():
    fig = make_orientation_map(_parsed(), marker_size=25)
    assert fig.data[0].marker.size == 25


def test_orientation_map_aspect_ratio():
    fig = make_orientation_map(_parsed())
    assert fig.layout.yaxis.scaleanchor == "x"
    assert fig.layout.yaxis.scaleratio == 1


def test_quality_map_marker_size():
    fig = make_quality_map(_parsed(), marker_size=30)
    assert fig.data[0].marker.size == 30


def test_orientation_map_3d_creates_figure():
    fig = make_orientation_map_3d(_parsed(), color_by="n_indexed")
    assert len(fig.data) == 1
    assert fig.data[0].type == "scatter3d"
    assert fig.layout.scene.aspectmode == "data"


def test_orientation_map_3d_uses_all_coordinates():
    parsed = _parsed()
    fig = make_orientation_map_3d(parsed)
    trace = fig.data[0]
    n = len(parsed["positions"])
    assert len(trace.x) == n
    assert len(trace.y) == n
    assert len(trace.z) == n


def test_quality_map_3d_creates_figure():
    fig = make_quality_map_3d(_parsed(), metric="goodness")
    assert len(fig.data) == 1
    assert fig.data[0].type == "scatter3d"


def test_quality_map_3d_all_metrics():
    parsed = _parsed()
    for metric in ("goodness", "rms_error", "n_indexed", "n_patterns"):
        fig = make_quality_map_3d(parsed, metric=metric)
        assert len(fig.data) >= 1


def test_peak_table_creates_div():
    peaks = get_all_indexed_peaks(_parsed())
    table = make_peak_table(peaks)
    assert table is not None
    assert hasattr(table, "children")
