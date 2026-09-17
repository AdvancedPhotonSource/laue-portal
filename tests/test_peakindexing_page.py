"""Callback-level tests of the result page against a cached native results file."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import dash
import pytest
from dash.exceptions import PreventUpdate
from sqlalchemy.orm import Session

import lau_dash  # noqa: F401  instantiates the Dash app so page modules can register
from laue_portal.components.visualization.scope_bar import DEFAULT_SCOPE
from laue_portal.database import db_schema
from laue_portal.pages import peakindexing
from laue_portal.services import dataset_cache
from tests.conftest import create_test_lauego_parameters, create_test_metadata
from tests.run_support import make_engine

MAP_DEFAULTS = dict(
    rgb_symmetry="auto",
    rgb_reference_mode="lab",
    rgb_reference_step=0,
    ref_a0=None,
    ref_a1=None,
    ref_a2=None,
    ref_b0=None,
    ref_b1=None,
    ref_b2=None,
    ref_c0=None,
    ref_c1=None,
    ref_c2=None,
    surface="normal",
    surface_tilt_x=1,
    surface_tilt_y=0,
    surface_tilt_z=0,
    surface_roll_x=0,
    surface_roll_y=1,
    surface_roll_z=0,
    surface_normal_x=0,
    surface_normal_y=0,
    surface_normal_z=1,
    input_size=20,
    nonindexed_style="gray",
    view_mode="2d",
    selected_patterns=[],
    pole_center=None,
    pole_hkl=[1, 0, 0],
    pole_color_rad_deg=22.5,
    pole_surface="normal",
    pole_surface_tilt_x=1,
    pole_surface_tilt_y=0,
    pole_surface_tilt_z=0,
    pole_surface_roll_x=0,
    pole_surface_roll_y=1,
    pole_surface_roll_z=0,
    pole_surface_normal_x=0,
    pole_surface_normal_y=0,
    pole_surface_normal_z=1,
    palette="Viridis",
    reverse_palette=False,
    user_vmin=None,
    user_vmax=None,
    x_axis="X",
    y_axis="Y",
    x_axis_3d="X",
    y_axis_3d="Y",
    z_axis="Z",
)


@pytest.fixture
def engine(tmp_path, monkeypatch):
    yield make_engine(tmp_path, monkeypatch)


def _add_run(engine, run_id, results_path, output_dir):
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
            output_path=str(output_dir),
            created_at=datetime(2026, 1, 1),
            results_path=str(results_path),
        )
        run.lauego_parameters = create_test_lauego_parameters()
        session.add(run)
        session.commit()


def _map(source, scope=DEFAULT_SCOPE, color_by="cubic_ipf", **overrides):
    values = dict(MAP_DEFAULTS)
    values.update(overrides)
    with patch.object(dash, "ctx", type("Ctx", (), {"triggered_id": "peakindexing-source"})()):
        return peakindexing.update_orientation_map(source, scope, color_by, *values.values())


def test_page_loads_results_source_and_renders_every_view(engine, synthetic_results):
    results_path, _ = synthetic_results
    _add_run(engine, 5, results_path, results_path.parent)
    dataset_cache.CACHE.clear()

    with patch.object(peakindexing, "set_peakindex_form_props"):
        _, source, context, artifacts = peakindexing.load_peakindexing_data(
            "http://localhost/peakindexing?indexing_id=5"
        )
    assert source == {"path": str(results_path), "kind": "results"}
    assert artifacts["status"] == "results" and artifacts["results_summary"]["n_frames"] == 4

    figure, marker, sentinel, status = _map(source)
    assert marker == 20 and sentinel == "" and status == ""
    assert {trace.meta["role"] for trace in figure.data} == {"data"}
    figure, *_ = _map(source, scope={"pattern0_only": True, "min_peaks": 0})
    assert {trace.meta["role"] for trace in figure.data} == {"data", "unindexed"}
    misses_after_map = dataset_cache.CACHE.misses

    pole, _, style, _, pole_status = peakindexing.update_pole_figure(
        source, DEFAULT_SCOPE, [1, 1, 0], 9, "hsv_position", 22.5, "normal", 1, 0, 0, 0, 1, 0, 0, 0, 1, None, []
    )
    assert pole_status == "" and style["display"] == "flex"
    assert dataset_cache.CACHE.misses == misses_after_map  # every callback reused the cached dataset

    peaks = peakindexing.update_peak_table(source, DEFAULT_SCOPE)
    patterns = peakindexing.update_pattern_table(source, DEFAULT_SCOPE)
    assert "Indexed Peaks" in str(peaks) and "Indexed Patterns (3 total)" in str(patterns)

    step_min, step_max, default_step, text = peakindexing.populate_detector_step_input(source, DEFAULT_SCOPE)
    assert (step_min, step_max, default_step) == (0, 3, 0) and text.startswith("Eligible steps: 3")
    options, values = peakindexing.populate_detector_pattern_checklist(source, DEFAULT_SCOPE, 1)
    assert [option["value"] for option in options] == [0, 1] and values == [0, 1]

    detector, summary, _, detector_status = peakindexing.update_detector_view(
        source, DEFAULT_SCOPE, context, 1, True, True, True, True, 10, 10, [0, 1], False, "gray", None, None, 0.8
    )
    roles = {trace.meta["role"] for trace in detector.data}
    assert {"detected", "indexed"} <= roles  # simulation ran; the synthetic frame has no missing reflections
    assert "Step #1" in str(summary) and detector_status == ""

    with pytest.raises(PreventUpdate):
        peakindexing.populate_detector_pattern_checklist(source, DEFAULT_SCOPE, 2)  # the empty frame is out of scope

    auto = peakindexing.compute_orientation_auto_range("goodness", source, DEFAULT_SCOPE)
    assert auto["mode"] == "goodness" and auto["min"] <= auto["max"]
    assert peakindexing.compute_orientation_auto_range("cubic_ipf", source, DEFAULT_SCOPE) is None


def test_invalid_inputs_keep_the_last_plot_and_explain(engine, synthetic_results):
    results_path, _ = synthetic_results
    source = {"path": str(results_path), "kind": "results"}

    figure, _, _, status = _map(source, color_by="misorientation")
    assert figure is dash.no_update
    assert "click one in the pole figure" in str(status)

    figure, _, _, status = _map(source, color_by="rodrigues", rgb_reference_mode="step", rgb_reference_step=42)
    assert figure is dash.no_update and "Step must be an integer" in str(status)

    figure, _, _, status = _map(source, surface="custom", surface_normal_z=-1)
    assert figure is dash.no_update and "right-handed" in str(status)

    figure, _, _, status = _map(source, x_axis="depth")  # no depth recorded for these frames
    assert figure is dash.no_update and "Not updated" in str(status)

    pole, _, _, _, pole_status = peakindexing.update_pole_figure(
        source, DEFAULT_SCOPE, [1, 0, 0], 9, "hsv_position", 22.5, "custom", 1, 0, 0, 0, 1, 0, 0, 0, None, None, []
    )
    assert pole is dash.no_update and "all nine" in str(pole_status)


def test_pole_click_and_selection_use_stable_identities(engine, synthetic_results):
    results_path, _ = synthetic_results
    source = {"path": str(results_path), "kind": "results"}
    pole, *_ = peakindexing.update_pole_figure(
        source, DEFAULT_SCOPE, [1, 0, 0], 9, "hsv_position", 22.5, "normal", 1, 0, 0, 0, 1, 0, 0, 0, 1, None, []
    )
    data = next(trace for trace in pole.data if trace.meta["role"] == "data")
    click = {"points": [{"customdata": list(data.customdata[0]), "x": float(data.x[0]), "y": float(data.y[0])}]}

    with patch.object(dash, "ctx", type("Ctx", (), {"triggered_id": "stereo-plot-graph"})()):
        center, info, style, color = peakindexing.handle_pole_figure_click(click, None, None, "cubic_ipf")
    assert center["frame_id"] == "frame_1" and center["pattern_index"] == 0 and color == "pole_hsv"
    assert center["prev_color_by"] == "cubic_ipf" and style["display"] == "flex"
    with patch.object(dash, "ctx", type("Ctx", (), {"triggered_id": "stereo-plot-graph"})()):
        cleared = peakindexing.handle_pole_figure_click(click, None, center, "pole_hsv")
    assert cleared[0] is None and cleared[3] == "cubic_ipf"

    figure, _, _, status = _map(source, color_by="misorientation", pole_center=center)
    assert status == "" and figure is not dash.no_update

    selected_data = {"points": [{"customdata": list(row), "x": 0.0, "y": 0.0} for row in data.customdata]}
    selected, card = peakindexing.handle_pole_selection(selected_data, source)
    assert selected and all(len(item) == 2 for item in selected)
    assert "Misorientation" in str(card)
    figure, _, _, status = _map(source, selected_patterns=selected)
    assert any(trace.meta["role"] == "highlight" for trace in figure.data)
    assert peakindexing.handle_pole_selection(None, source)[0] == []


def test_point_details_from_a_map_click(engine, synthetic_results):
    results_path, _ = synthetic_results
    source = {"path": str(results_path), "kind": "results"}
    figure, *_ = _map(source)
    data = next(trace for trace in figure.data if trace.meta["role"] == "data")
    click = {"points": [{"customdata": list(data.customdata[0]), "x": 0, "y": 0}]}
    card = peakindexing.show_point_details(click, source)
    text = str(card)
    assert "Step #0" in text and "frame frame_1" in text and "Indexed:" in text
    figure, *_ = _map(source, scope={"pattern0_only": True, "min_peaks": 0})
    unindexed = next(trace for trace in figure.data if trace.meta["role"] == "unindexed")
    card = peakindexing.show_point_details({"points": [{"customdata": list(unindexed.customdata[0])}]}, source)
    assert "no indexed pattern" in str(card)
