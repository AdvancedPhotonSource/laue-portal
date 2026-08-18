"""Integration tests for visualization components using synthetic fixture."""

import os
import sys

import numpy as np

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from laue_portal.analysis.xml_parser import (
    apply_data_scope,
    get_all_indexed_peaks,
    get_all_patterns,
    parse_indexing_xml,
)
from laue_portal.components.visualization.orientation_map import (
    _AXIS_CHOICES,
    _resolve_axis,
    apply_selection_highlight,
    make_orientation_map,
    make_orientation_map_3d,
)
from laue_portal.components.visualization.pattern_table import make_pattern_table
from laue_portal.components.visualization.peak_table import make_peak_table
from laue_portal.components.visualization.quality_map import (
    make_quality_map,
    make_quality_map_3d,
)
from laue_portal.components.visualization.stereo_plot import make_pole_figure

FIXTURE_XML = os.path.join(os.path.dirname(__file__), "fixtures", "test_indexing.xml")


def _parsed():
    return parse_indexing_xml(FIXTURE_XML)


def test_orientation_map_creates_figure():
    fig = make_orientation_map(_parsed(), color_by="n_indexed")
    assert len(fig.data) == 1
    assert fig.data[0].type == "scattergl"


def test_scoped_maps_preserve_original_step_ids():
    scoped = apply_data_scope(_parsed(), {"min_peaks": 6})
    fig = make_orientation_map(scoped, color_by="n_indexed")
    assert [int(row[0]) for row in fig.data[0].customdata] == [0, 1, 3]

    pole = make_pole_figure(scoped)
    assert set(int(row[0]) for row in pole.data[0].customdata) == {0, 1, 3}


def test_orientation_map_xh_axes():
    fig = make_orientation_map(_parsed(), color_by="n_indexed", x_axis="X", y_axis="H")
    assert fig.layout.xaxis.title.text == "X motor (um)"
    assert fig.layout.yaxis.title.text == "H (um)"


def test_orientation_map_3d_xyz_axes():
    fig = make_orientation_map_3d(_parsed(), color_by="n_indexed", x_axis="X", y_axis="Y", z_axis="Z")
    assert fig.layout.scene.xaxis.title.text == "X motor (um)"
    assert fig.layout.scene.yaxis.title.text == "Y motor (um)"
    assert fig.layout.scene.zaxis.title.text == "Z motor (um)"


def test_orientation_map_lab_axes():
    # Lab (beam-line) axes must be selectable in the 2-D map.
    fig = make_orientation_map(_parsed(), color_by="n_indexed", x_axis="Xlab", y_axis="Hlab")
    assert fig.layout.xaxis.title.text == "X lab (um)"
    assert fig.layout.yaxis.title.text == "H lab (um)"


def test_orientation_map_3d_lab_axes():
    fig = make_orientation_map_3d(_parsed(), color_by="n_indexed", x_axis="Xlab", y_axis="Ylab", z_axis="Zlab")
    assert fig.layout.scene.xaxis.title.text == "X lab (um)"
    assert fig.layout.scene.yaxis.title.text == "Y lab (um)"
    assert fig.layout.scene.zaxis.title.text == "Z lab (um)"


def test_orientation_map_mixed_sample_and_lab_axes():
    # Mixing frames on one plot is odd but must not raise.
    fig = make_orientation_map(_parsed(), color_by="goodness", x_axis="X", y_axis="Zlab")
    assert fig.layout.xaxis.title.text == "X motor (um)"
    assert fig.layout.yaxis.title.text == "Z lab (um)"


def test_lab_axis_values_are_negated_stage_positions():
    # Plotted lab values must actually be Igor's XX/YY/ZZ, not the raw stage
    # coords under a new label.
    parsed = _parsed()
    x_lab, _ = _resolve_axis(parsed, "Xlab")
    assert np.allclose(x_lab, -parsed["positions"][:, 0])


def test_resolve_axis_all_declared_choices():
    # Every advertised choice must resolve; catches a dropdown option that
    # was added without a matching branch in _resolve_axis.
    parsed = _parsed()
    n = len(parsed["positions"])
    for name in _AXIS_CHOICES:
        if name == "auto":
            continue
        vals, label = _resolve_axis(parsed, name)
        assert len(vals) == n, name
        assert label, name


def test_motor_axis_rename_is_display_only():
    # X/Y/Z were relabelled "X motor" etc. for the researchers, but the
    # underlying option *values* must stay "X"/"Y"/"Z" so existing saved
    # URLs and callback state keep resolving.
    parsed = _parsed()
    for name in ("X", "Y", "Z"):
        vals, label = _resolve_axis(parsed, name)
        assert label == f"{name} motor (um)"
        assert len(vals) == len(parsed["positions"])
    # The non-motor axes keep their original labels.
    assert _resolve_axis(parsed, "H")[1] == "H (um)"
    assert _resolve_axis(parsed, "Xlab")[1] == "X lab (um)"


def test_resolve_axis_lab_fallback_for_legacy_cache():
    # A cached parse predating positions_lab must still resolve lab axes.
    parsed = _parsed()
    legacy = {k: v for k, v in parsed.items() if k != "positions_lab"}
    vals, _ = _resolve_axis(legacy, "Zlab")
    assert np.allclose(vals, parsed["positions_lab"][:, 2])


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


def test_orientation_map_disables_aspect_ratio_above_limit():
    fig = make_orientation_map(_parsed(), aspect_ratio_point_limit=0)
    assert fig.layout.yaxis.scaleanchor is None
    assert fig.layout.yaxis.scaleratio is None
    assert any("aspect ratio scaling disabled" in annotation.text.lower() for annotation in fig.layout.annotations)


def test_quality_map_marker_size():
    fig = make_quality_map(_parsed(), marker_size=30)
    assert fig.data[0].marker.size == 30


def test_orientation_map_3d_creates_figure():
    fig = make_orientation_map_3d(_parsed(), color_by="n_indexed")
    assert len(fig.data) == 1
    assert fig.data[0].type == "scatter3d"
    assert fig.data[0].marker.symbol == "square"
    assert fig.data[0].marker.opacity == 1.0
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
    assert fig.data[0].marker.symbol == "square"
    assert fig.data[0].marker.opacity == 1.0


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


def test_peak_table_has_column_picker_and_hidden_options():
    peaks = get_all_indexed_peaks(_parsed())
    table = make_peak_table(peaks)
    layout = table.to_plotly_json()
    table_children = layout["props"]["children"]
    content = table_children[1]
    selector, grid_wrap = content.to_plotly_json()["props"]["children"]
    assert selector.to_plotly_json()["props"]["children"][0].to_plotly_json()["props"]["children"] == "Columns"

    grid = grid_wrap.to_plotly_json()["props"]["children"]
    cols = {col["field"]: col for col in grid.columnDefs}
    assert cols["hwhm_x"]["hide"] is True
    assert cols["q_magnitude"]["hide"] is True
    assert cols["step_index"].get("hide") is False


def test_pattern_table_creates_div():
    patterns = get_all_patterns(_parsed())
    table = make_pattern_table(patterns)
    assert table is not None
    assert hasattr(table, "children")


# ---------------------------------------------------------------------------
# 3-D alpha channel / un-indexed point removal
# ---------------------------------------------------------------------------
# Plotly's 3-D WebGL renderer mis-sorts markers carrying an alpha channel, so
# the 3-D path must drop un-indexed steps outright instead of fading them to
# transparent (which is what the 2-D path still does).


def _parsed_with_unindexed(bad_indices=(1, 3)):
    """Fixture copy whose *bad_indices* steps have no reciprocal lattice."""
    parsed = dict(_parsed())
    rl = parsed["recip_lattices"].copy()
    for i in bad_indices:
        rl[i] = np.nan
    parsed["recip_lattices"] = rl
    return parsed


def _rgba_count(fig):
    """Count marker colors carrying an alpha channel anywhere in *fig*."""
    total = 0
    for trace in fig.data:
        color = trace.marker.color
        if isinstance(color, str):
            total += "rgba" in color
        elif isinstance(color, (list, tuple)):
            total += sum(1 for c in color if isinstance(c, str) and "rgba" in c)
    return total


def test_3d_rodrigues_drops_unindexed_points():
    parsed = _parsed_with_unindexed()
    n_total = len(parsed["positions"])
    fig = make_orientation_map_3d(parsed, color_by="rodrigues")
    assert len(fig.data[0].x) == n_total - 2


def test_3d_rodrigues_emits_no_alpha_channel():
    fig = make_orientation_map_3d(_parsed_with_unindexed(), color_by="rodrigues")
    assert _rgba_count(fig) == 0


def test_3d_rodrigues_preserves_original_step_indices():
    # customdata[0] must still be the original step index after filtering,
    # otherwise click-to-inspect opens the wrong step.
    fig = make_orientation_map_3d(_parsed_with_unindexed((1, 3)), color_by="rodrigues")
    assert [int(row[0]) for row in fig.data[0].customdata] == [0, 2]


def test_3d_rodrigues_color_list_matches_filtered_points():
    fig = make_orientation_map_3d(_parsed_with_unindexed(), color_by="rodrigues")
    trace = fig.data[0]
    assert len(trace.marker.color) == len(trace.x)


def test_3d_keeps_all_points_when_all_indexed():
    parsed = dict(_parsed())
    n = len(parsed["positions"])
    parsed["recip_lattices"] = np.tile(np.eye(3), (n, 1, 1))
    fig = make_orientation_map_3d(parsed, color_by="rodrigues")
    assert len(fig.data[0].x) == n


def test_3d_highlight_trace_has_no_alpha():
    parsed = _parsed_with_unindexed()
    fig = make_orientation_map_3d(parsed, color_by="rodrigues")
    apply_selection_highlight(fig, parsed, [0, 2], marker_size=10, is_3d=True)
    assert len(fig.data) == 2
    assert _rgba_count(fig) == 0


def test_2d_rodrigues_still_fades_unindexed_points():
    # The 2-D Scattergl path is unaffected by the WebGL sorting bug, so it
    # keeps every point and fades un-indexed ones via alpha=0.
    parsed = _parsed_with_unindexed()
    fig = make_orientation_map(parsed, color_by="rodrigues")
    assert len(fig.data[0].x) == len(parsed["positions"])
    assert _rgba_count(fig) > 0


def test_3d_other_orientation_modes_keep_all_points():
    parsed = _parsed_with_unindexed()
    n = len(parsed["positions"])
    for mode in ("cubic_ipf", "pole_hsv"):
        fig = make_orientation_map_3d(parsed, color_by=mode)
        assert len(fig.data[0].x) == n, mode
        assert _rgba_count(fig) == 0, mode


def test_3d_scalar_mode_unaffected():
    parsed = _parsed_with_unindexed()
    fig = make_orientation_map_3d(parsed, color_by="n_indexed")
    assert len(fig.data[0].x) == len(parsed["positions"])
    assert _rgba_count(fig) == 0
