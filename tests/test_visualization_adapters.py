"""Tests for the visualization adapters over lauelab: cache, scope, maps, poles, detector, tables."""

from __future__ import annotations

import os
import time

import numpy as np
import pytest
from lauelab.analysis import SurfaceFrame
from lauelab.visualization import DataScope, selection_from_plotly

from laue_portal.components.visualization import detector_view, orientation_map, stereo_plot
from laue_portal.components.visualization.pattern_table import make_pattern_table, pattern_rows
from laue_portal.components.visualization.peak_table import make_peak_table, peak_rows
from laue_portal.components.visualization.scope_bar import DEFAULT_SCOPE, normalize_scope, to_data_scope
from laue_portal.services import dataset_cache

SCOPE = to_data_scope(DEFAULT_SCOPE)
ALL_FRAMES = to_data_scope({"pattern0_only": True, "min_peaks": 0})  # keeps the one-peak empty frame as frame-only


def _roles(figure):
    return [trace.meta["role"] for trace in figure.data]


# --- scope ---------------------------------------------------------------------------


def test_portal_scope_is_explicit_pattern_zero_with_unindexed_frames():
    assert SCOPE == DataScope(patterns=(0,), min_indexed=0, min_detected=4, unindexed_frames=True)
    assert to_data_scope({"pattern0_only": False, "min_peaks": 0}) == DataScope(
        patterns="all", min_indexed=0, min_detected=None, unindexed_frames=True
    )
    assert to_data_scope(None) == SCOPE
    assert normalize_scope({"min_peaks": "7"})["min_peaks"] == 7


# --- cache ---------------------------------------------------------------------------


def test_dataset_cache_reuses_by_identity_and_reloads_changed_files(tmp_path, synthetic_results):
    results_path, xml_path = synthetic_results
    cache = dataset_cache.DatasetCache(capacity=2)
    first = cache.get(results_path)
    assert cache.get(results_path) is first
    assert (cache.hits, cache.misses, len(cache)) == (1, 1, 1)

    copy = tmp_path / "copy.h5"
    copy.write_bytes(results_path.read_bytes())
    second = cache.get(copy)
    assert second is not first
    os.utime(copy, ns=(time.time_ns(), time.time_ns() + 10_000_000))  # the file was republished
    third = cache.get(copy)
    assert third is not second
    assert len(cache) == 2  # the stale entry for the same path was dropped, not kept beside the new one

    xml_dataset = cache.get(xml_path)
    assert xml_dataset.n_frames == 4
    assert len(cache) == 2 and cache.evictions == 1
    assert dataset_cache.source_kind(results_path) == "results"
    assert dataset_cache.source_kind(xml_path) == "xml"
    with pytest.raises(ValueError):
        dataset_cache.DatasetCache(capacity=0)


# --- maps ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "color", ["cubic_ipf", "rodrigues", "pole_hsv", "n_indexed", "goodness", "rms_error", "n_patterns"]
)
def test_build_map_supports_every_color_mode_and_keeps_unindexed_frames(synthetic_dataset, color):
    scoped, scoped_data = orientation_map.build_map(synthetic_dataset, scope=SCOPE, axes=("X", "Y"), color=color)
    assert len(scoped_data.coordinates) == 3  # the one-peak frame is skipped by the default scope
    assert "unindexed" not in _roles(scoped)
    figure, map_data = orientation_map.build_map(
        synthetic_dataset, scope=ALL_FRAMES, axes=("X", "Y"), color=color, marker_size=12
    )
    assert len(map_data.coordinates) == 4  # three patterns plus one frame-only record
    assert int((~map_data.has_pattern).sum()) == 1
    roles = _roles(figure)
    assert "data" in roles
    if color == "n_patterns":
        # A frame-based value is real (0) for a frame-only record, so it is drawn with the data.
        assert "unindexed" not in roles and map_data.colors[~map_data.has_pattern][0] == 0
    else:
        unindexed = figure.data[roles.index("unindexed")]
        assert unindexed.marker.color == orientation_map.NONINDEXED_COLORS["gray"]
    if color in orientation_map.SCALAR_MODES:
        assert map_data.color_kind == "scalar"
        assert figure.data[roles.index("data")].marker.showscale is True
    else:
        assert map_data.color_kind == "rgb"


def test_build_map_3d_scalar_controls_and_nonindexed_styles(synthetic_dataset):
    figure, map_data = orientation_map.build_map(
        synthetic_dataset,
        scope=ALL_FRAMES,
        axes=("X", "Y", "Z"),
        color="goodness",
        palette="Plasma",
        reverse=True,
        cmin=10,
        cmax=500,
        nonindexed_style="red",
        marker_size=6,
    )
    assert all(trace.type == "scatter3d" for trace in figure.data)
    data = figure.data[_roles(figure).index("data")]
    assert data.marker.colorscale[0][1].lower().startswith("#") or data.marker.colorscale is not None
    assert (data.marker.cmin, data.marker.cmax, data.marker.reversescale) == (10, 500, True)
    assert map_data.palette == "Plasma" and map_data.color_limits == (10.0, 500.0)
    assert figure.data[_roles(figure).index("unindexed")].marker.color == orientation_map.NONINDEXED_COLORS["red"]

    transparent, _ = orientation_map.build_map(
        synthetic_dataset, scope=ALL_FRAMES, axes=("X", "Y"), color="cubic_ipf", nonindexed_style="transparent"
    )
    assert transparent.data[_roles(transparent).index("unindexed")].visible is False
    assert orientation_map.scalar_auto_range(map_data)[0] > 0
    lo, hi = orientation_map.scalar_range_for(synthetic_dataset, SCOPE, "n_indexed")
    assert lo >= 1 and hi >= lo
    assert orientation_map.scalar_range_for(synthetic_dataset, SCOPE, "cubic_ipf") == (None, None)
    assert orientation_map.scalar_range_for(synthetic_dataset, SCOPE, "n_patterns") == (1.0, 2.0)


def test_rodrigues_references_and_symmetry_choices(synthetic_dataset):
    _, lab = orientation_map.build_map(
        synthetic_dataset, scope=SCOPE, axes=("X", "Y"), color="rodrigues", symmetry="auto"
    )
    assert lab.symmetry == "cubic"
    _, none = orientation_map.build_map(
        synthetic_dataset, scope=SCOPE, axes=("X", "Y"), color="rodrigues", symmetry="none"
    )
    assert none.symmetry == "none"
    _, step = orientation_map.build_map(
        synthetic_dataset, scope=SCOPE, axes=("X", "Y"), color="rodrigues", reference_mode="step", reference_step=0
    )
    from lauelab.analysis import rodrigues_colors

    zero_color = rodrigues_colors(np.zeros((1, 3)))[0]
    zero = step.colors[np.flatnonzero(np.array(step.frame_ids, dtype=object) == "frame_1")[0]]
    # The reference pattern maps to the zero Rodrigues vector and takes that vector's color.
    assert np.allclose(zero, zero_color, atol=1e-6)
    with pytest.raises(ValueError, match="Step must be an integer between 0 and 3"):
        orientation_map.build_map(
            synthetic_dataset, scope=SCOPE, axes=("X", "Y"), color="rodrigues", reference_mode="step", reference_step=9
        )
    with pytest.raises(ValueError, match="Custom G_ref needs all nine entries"):
        orientation_map.build_map(
            synthetic_dataset,
            scope=SCOPE,
            axes=("X", "Y"),
            color="rodrigues",
            reference_mode="custom",
            reference_matrix=None,
        )
    reference = synthetic_dataset.pattern_reciprocals[0]
    _, custom = orientation_map.build_map(
        synthetic_dataset,
        scope=SCOPE,
        axes=("X", "Y"),
        color="rodrigues",
        reference_mode="custom",
        reference_matrix=reference,
    )
    assert np.allclose(custom.colors[0], zero_color, atol=1e-6)
    with pytest.raises(ValueError, match="does not describe this crystal"):
        orientation_map.build_map(
            synthetic_dataset,
            scope=SCOPE,
            axes=("X", "Y"),
            color="rodrigues",
            reference_mode="custom",
            reference_matrix=reference / 10,
        )
    assert orientation_map.parse_reference_matrix([None] * 9) is None
    assert orientation_map.parse_reference_matrix(list(range(9))).shape == (3, 3)
    with pytest.raises(ValueError, match="numbers"):
        orientation_map.parse_reference_matrix(["a"] * 9)


def test_misorientation_needs_a_reference_and_uses_stable_identities(synthetic_dataset):
    with pytest.raises(ValueError, match="click one in the pole figure"):
        orientation_map.build_map(synthetic_dataset, scope=SCOPE, axes=("X", "Y"), color="misorientation")
    _, data = orientation_map.build_map(
        synthetic_dataset, scope=SCOPE, axes=("X", "Y"), color="misorientation", misorientation_reference=("frame_1", 0)
    )
    assert data.color_kind == "rgb"
    with pytest.raises((ValueError, KeyError)):
        orientation_map.build_map(
            synthetic_dataset,
            scope=SCOPE,
            axes=("X", "Y"),
            color="misorientation",
            misorientation_reference=("missing", 0),
        )


def test_surfaces_presets_and_custom_frames(synthetic_dataset):
    assert orientation_map.resolve_surface(None) == "normal"
    custom = orientation_map.resolve_surface("custom", [1, 0, 0, 0, 1, 0, 0, 0, 1])
    assert isinstance(custom, SurfaceFrame)
    with pytest.raises(ValueError, match="all nine"):
        orientation_map.resolve_surface("custom", [1, 0, 0, 0, 1, 0, 0, 0, None])
    with pytest.raises(ValueError, match="right-handed|orthogonal"):
        orientation_map.resolve_surface("custom", [1, 0, 0, 0, 1, 0, 0, 0, -1])
    with pytest.raises(ValueError, match="unknown surface"):
        orientation_map.resolve_surface("sideways")
    normal, _ = orientation_map.build_map(
        synthetic_dataset, scope=SCOPE, axes=("X", "Y"), color="cubic_ipf", surface="normal"
    )
    z_axis, _ = orientation_map.build_map(
        synthetic_dataset, scope=SCOPE, axes=("X", "Y"), color="cubic_ipf", surface="Z"
    )
    assert normal.data[0].marker.color != z_axis.data[0].marker.color
    figure, _ = orientation_map.build_map(
        synthetic_dataset, scope=SCOPE, axes=("X", "Y"), color="cubic_ipf", surface=custom
    )
    assert len(figure.data) >= 1


def test_selection_highlight_dims_and_rings_by_identity(synthetic_dataset):
    figure, map_data = orientation_map.build_map(
        synthetic_dataset, scope=SCOPE, axes=("X", "Y"), color="cubic_ipf", marker_size=10
    )
    ringed = orientation_map.highlight_selection(figure, map_data, [["frame_2", 0], ["frame_9", 0]], marker_size=10)
    assert ringed == 1
    roles = _roles(figure)
    assert roles[-1] == orientation_map.HIGHLIGHT_ROLE
    data = figure.data[roles.index("data")]
    opacity = np.asarray(data.marker.opacity)
    assert sorted(set(opacity.tolist())) == [0.2, 1.0]
    ring = figure.data[-1]
    assert ring.marker.symbol == "circle-open" and ring.marker.size == 16
    assert orientation_map.highlight_selection(figure, map_data, [], marker_size=10) == 0

    figure3d, data3d = orientation_map.build_map(
        synthetic_dataset, scope=SCOPE, axes=("X", "Y", "Z"), color="cubic_ipf"
    )
    assert orientation_map.highlight_selection(figure3d, data3d, [["frame_1", 0]], marker_size=10) == 1
    assert figure3d.data[-1].type == "scatter3d"
    assert figure3d.data[0].marker.opacity is None  # 3-D points stay opaque for depth testing


def test_step_positions_and_point_details(synthetic_dataset):
    assert orientation_map.frame_id_at(synthetic_dataset, 2) == "frame_3"
    assert orientation_map.frame_id_at(synthetic_dataset, "1.0") == "frame_2"
    assert orientation_map.frame_position(synthetic_dataset, "frame_4") == 3
    with pytest.raises(ValueError):
        orientation_map.frame_id_at(synthetic_dataset, 4)
    with pytest.raises(ValueError):
        orientation_map.frame_id_at(synthetic_dataset, None)
    with pytest.raises(KeyError):
        orientation_map.frame_position(synthetic_dataset, "frame_99")

    details = orientation_map.point_details(synthetic_dataset, "frame_2", 0)
    assert details["step"] == 1 and details["n_patterns"] == 2 and details["n_indexed"] > 0
    assert details["sample_position"] == [5.0, 0.0, 10.0]
    empty = orientation_map.point_details(synthetic_dataset, "frame_3", None)
    assert (empty["n_patterns"], empty["pattern_index"], empty["n_indexed"]) == (0, None, None)

    # A click on the map yields the stable identities the details need.
    figure, _ = orientation_map.build_map(synthetic_dataset, scope=ALL_FRAMES, axes=("X", "Y"), color="cubic_ipf")
    trace = figure.data[_roles(figure).index("unindexed")]
    click = {"points": [{"customdata": list(trace.customdata[0]), "x": trace.x[0], "y": trace.y[0]}]}
    selection = selection_from_plotly(click)
    assert selection.frame_ids == ("frame_3",) and selection.pattern_ids == ()


# --- pole figure ----------------------------------------------------------------------------


def test_pole_figure_build_selection_and_misorientation(synthetic_dataset):
    figure, pole_data = stereo_plot.build_pole_figure(
        synthetic_dataset, scope=SCOPE, hkl=(1, 1, 0), color="hsv_position", marker_size=9
    )
    assert len(pole_data.points) > 0
    assert set(_roles(figure)) >= {"data", "boundary", "reference"}
    data = figure.data[_roles(figure).index("data")]
    event = {"points": [{"customdata": list(row), "x": 0.0, "y": 0.0} for row in data.customdata[:5]]}
    selection = selection_from_plotly(event)
    assert selection.pattern_ids
    assert (
        stereo_plot.highlight_pole_selection(figure, [list(pair) for pair in selection.pattern_ids], marker_size=9) >= 1
    )
    assert figure.data[-1].meta["role"] == orientation_map.HIGHLIGHT_ROLE

    all_ids = [list(pair) for pair in synthetic_dataset.pattern_ids(DataScope(patterns="all", min_indexed=0))]
    summary = stereo_plot.misorientation_summary(synthetic_dataset, all_ids)
    assert summary["skipped"] is False and summary["n_patterns"] == 4 and summary["n_pairs"] == 6
    assert summary["symmetry"] == "cubic" and 0 <= summary["min"] <= summary["mean"] <= summary["max"] <= 62.8
    assert stereo_plot.misorientation_summary(synthetic_dataset, all_ids[:1]) is None
    assert stereo_plot.misorientation_summary(synthetic_dataset, all_ids, max_patterns=2) == {
        "skipped": True,
        "n_patterns": 4,
        "limit": 2,
    }
    uniform, _ = stereo_plot.build_pole_figure(synthetic_dataset, scope=SCOPE, hkl=(1, 0, 0), color="uniform")
    assert len(uniform.data) >= 3


# --- detector view ---------------------------------------------------------------------------


def test_detector_view_layers_simulation_and_summary(synthetic_dataset):
    frame_id = "frame_2"
    figure, view = detector_view.build_detector_view(
        synthetic_dataset, frame_id=frame_id, patterns="all", show_simulated=False
    )
    roles = _roles(figure)
    assert "detected" in roles and "indexed" in roles and "simulated" not in roles and "image" not in roles
    assert figure.layout.yaxis.autorange == "reversed"
    assert detector_view.frame_patterns(synthetic_dataset, frame_id) == [
        (0, len(view.patterns[0].hkl)),
        (1, len(view.patterns[1].hkl)),
    ]

    # The synthetic frames carry every reflection between 6 and 30 keV, so the default window
    # finds nothing missing (a valid empty layer); a wider window predicts unrendered reflections.
    _, view_default = detector_view.build_detector_view(
        synthetic_dataset, frame_id=frame_id, patterns=(0,), show_simulated=True
    )
    assert len(view_default.simulations) == 1 and len(view_default.simulations[0].hkl) == 0
    simulated, view_sim = detector_view.build_detector_view(
        synthetic_dataset,
        frame_id=frame_id,
        patterns=(0,),
        show_simulated=True,
        show_hkl_labels=True,
        label_size=14,
        energy_range_kev=(5.0, 40.0),
    )
    assert "simulated" in _roles(simulated)
    assert len(view_sim.simulations) == 1 and len(view_sim.simulations[0].hkl) > 0
    indexed = simulated.data[_roles(simulated).index("indexed")]
    assert indexed.textfont.size == 14

    image = np.zeros(tuple(synthetic_dataset.image_shapes[1]), dtype=np.uint16)
    with_image, _ = detector_view.build_detector_view(
        synthetic_dataset,
        frame_id=frame_id,
        patterns="all",
        image=image,
        image_colormap="gray_r",
        limits=(0.0, 10.0),
        image_opacity=0.5,
    )
    heatmap = with_image.data[_roles(with_image).index("image")]
    assert (heatmap.zmin, heatmap.zmax, heatmap.opacity) == (0.0, 10.0, 0.5)

    summary = detector_view.detector_summary(synthetic_dataset, view)
    assert summary["step"] == 1 and summary["frame_id"] == frame_id and summary["n_measured"] == 48
    assert [pattern["pattern_index"] for pattern in summary["patterns"]] == [0, 1]
    assert summary["patterns"][0]["goodness"] is not None and summary["n_indexed_peaks"] > 0

    assert detector_view.image_limits(None, None, 1.0, 5.0) == (1.0, 5.0)
    assert detector_view.image_limits(9, 2, 1.0, 5.0) == (2.0, 9.0)
    assert detector_view.image_limits(3, 3, 1.0, 5.0) is None
    assert detector_view.image_colorscale("viridis") == "Viridis"
    assert isinstance(detector_view.image_colorscale("gray_r"), list)
    assert detector_view.eligible_frames(synthetic_dataset, SCOPE).tolist() == [0, 1, 3]  # the empty frame has 1 peak
    assert detector_view.eligible_frames(synthetic_dataset, to_data_scope({"min_peaks": 0})).tolist() == [0, 1, 2, 3]


def test_detector_view_without_geometry_or_crystal_reports_missing_context(tmp_path):
    from lauelab.visualization import convert_xml, load_results

    dataset = load_results(convert_xml("tests/fixtures/test_indexing.xml", tmp_path / "f.h5"))
    assert dataset.geometry is None
    with pytest.raises(ValueError, match="geometry"):
        detector_view.build_detector_view(dataset, frame_id=0, patterns="all")


# --- tables ------------------------------------------------------------------------------------


def test_tables_keep_stable_identities_and_familiar_fields(synthetic_dataset):
    patterns = pattern_rows(synthetic_dataset, SCOPE)
    assert [(row["step"], row["frame_id"], row["pattern_index"]) for row in patterns] == [
        (0, "frame_1", 0),
        (1, "frame_2", 0),
        (3, "frame_4", 0),
    ]
    assert patterns[1]["n_patterns"] == 2 and patterns[1]["n_peaks"] == 48
    assert patterns[0]["structure"] == "Ni" and patterns[0]["space_group"] == 225
    assert patterns[0]["astar"].count(" ") == 2 and patterns[0]["indexed_fraction"] > 0
    assert patterns[0]["x_um"] == 0.0 and patterns[1]["x_um"] == 5.0
    everything = pattern_rows(synthetic_dataset, to_data_scope({"pattern0_only": False}))
    assert len(everything) == 4
    div = make_pattern_table(patterns)
    assert "Indexed Patterns (3 total)" in str(div)

    peaks = peak_rows(synthetic_dataset, SCOPE)
    assert len(peaks) == sum(row["n_indexed"] for row in patterns)
    first = peaks[0]
    assert {
        "step",
        "frame_id",
        "pattern_index",
        "peak_index",
        "h",
        "k",
        "l",
        "x_pixel",
        "y_pixel",
        "intensity",
        "qx",
        "qy",
        "qz",
        "rms_error_deg",
        "goodness",
        "energy_kev",
        "hwhm_x",
        "chisq",
        "pattern_indexed_fraction",
    } <= set(first)
    assert first["frame_id"] == "frame_1" and first["pattern_index"] == 0
    grid = make_peak_table(peaks)
    assert "Indexed Peaks" in str(grid)
