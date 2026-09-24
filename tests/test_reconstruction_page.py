"""Test point selection, depth images, and ROI inspection through page callbacks.

Fixtures include a scan with one failed point and a per-depth export.
Expected values come from the stored pixels.
"""

from __future__ import annotations

import os
import shutil
from unittest.mock import patch

import dash
import h5py
import numpy as np
import pytest
from dash.exceptions import PreventUpdate
from lauelab.reconstruct import ScanReader, export_per_depth, prepare_scan, reconstruct_point, reconstruct_scan

import lau_dash  # noqa: F401  instantiates the Dash app so page modules can register
from laue_portal.components.visualization import depth_view
from laue_portal.pages import wire_reconstruction as page
from laue_portal.services import reconstruction_view as view
from laue_portal.workflows.execution import JobStatus, RunPhase
from laue_portal.workflows.manifest import RECONSTRUCTION_DIRECTORY
from tests.wire_support import GEOMETRY, N_DEPTHS, write_wire_scan

POINTS = ("wire_1", "wire_2", "wire_3")


def _ctx(triggered_id):
    return patch.object(dash, "ctx", type("Ctx", (), {"triggered_id": triggered_id})())


@pytest.fixture(scope="module")
def run_dirs(tmp_path_factory):
    work = tmp_path_factory.mktemp("recon_page")
    scan_dir = work / "rec_1"
    scan_dir.mkdir()
    inputs = [write_wire_scan(work / "wire_1.h5", seed=1), work / "wire_2.h5", write_wire_scan(work / "wire_3.h5")]
    result = reconstruct_scan(
        inputs,
        scan_dir / RECONSTRUCTION_DIRECTORY,
        geometry=GEOMETRY,
        detector=0,
        point_ids=list(POINTS),
        depth_range=(-25.0, 25.0),
        resolution=5.0,
        wire_edge="both",
        threads_per_worker=1,
    )
    per_depth_dir = work / "rec_0"
    export_per_depth(ScanReader(result.path).point_path("wire_1"), per_depth_dir / "wire_1_")
    return scan_dir, per_depth_dir


@pytest.fixture
def scan(run_dirs):
    view.CACHE.clear()
    return view.locate_artifact(os.fspath(run_dirs[0]))


@pytest.fixture
def per_depth(run_dirs):
    view.CACHE.clear()
    return view.locate_artifact(os.fspath(run_dirs[1]))


def _stored(artifact, point_id="wire_1"):
    with ScanReader(artifact.path) as source:
        point = source.point(point_id)
        return np.stack([point.frame(index) for index in range(point.shape[0])]), np.array(point.depth_um)


# --- Artifact and Points ---------------------------------------------------------------


def test_the_run_layout_is_found_from_the_run_directory(run_dirs, tmp_path):
    scan_dir, per_depth_dir = run_dirs
    catalog = scan_dir / RECONSTRUCTION_DIRECTORY / "scan.h5"
    assert view.locate_artifact(os.fspath(scan_dir)) == view.Artifact("scan", os.fspath(catalog))
    assert view.locate_artifact(os.fspath(per_depth_dir)) == view.Artifact("per_depth", os.fspath(per_depth_dir))
    assert view.locate_artifact(os.fspath(tmp_path)) is None
    assert view.locate_artifact(None) is None


def test_points_come_from_the_catalog_and_the_first_complete_point_is_selected(scan):
    rows, message, selected = page.load_points(scan.to_store(), None)

    assert [(row["point_id"], row["status"]) for row in rows] == [
        ("wire_1", "complete"),
        ("wire_2", "failed"),
        ("wire_3", "complete"),
    ]
    assert rows[0]["n_depths"] == N_DEPTHS and rows[0]["dtype"] == "int32" and rows[0]["shape"] == "32 x 32"
    assert rows[0]["sample_position_um"] == "1.0, 2.0, 3.0"
    assert rows[1]["n_depths"] is None and "does not exist" in rows[1]["error"]
    assert selected == "wire_1"
    assert scan.path in message and "run finished" in message
    assert len(view.CACHE) == 0  # the table reads no pixels


def test_a_failed_point_cannot_be_selected_as_an_empty_image(scan):
    rows, _, _ = page.load_points(scan.to_store(), None)
    point, message = page.select_point([rows[1]], "wire_1")
    assert point is dash.no_update
    assert message.startswith("Point wire_2 failed: ") and "does not exist" in message
    assert message.endswith("It has no images.")
    assert page.select_point([rows[2]], "wire_1") == ("wire_3", dash.no_update)
    with pytest.raises(PreventUpdate):
        page.select_point([rows[0]], "wire_1")


def test_per_depth_points_are_listed_from_their_summary_files(per_depth):
    rows, message, selected = page.load_points(per_depth.to_store(), None)
    assert [(row["point_id"], row["status"], row["n_depths"]) for row in rows] == [("wire_1", "complete", N_DEPTHS)]
    assert selected == "wire_1"
    assert "raw reference images were not recorded" in message


def _run(directory, reconstruction_id=5):
    return {"reconstruction_id": reconstruction_id, "directory": os.fspath(directory)}


def test_a_run_without_a_catalog_says_whether_results_are_still_coming(tmp_path, monkeypatch):
    job = type("Job", (), {"status": int(JobStatus.RUNNING), "phase": RunPhase.RUNNING})()
    monkeypatch.setattr(page, "get_reconstruction", lambda reconstruction_id: type("Run", (), {"job": job})())
    waiting = page.locate_run_output(_run(tmp_path), None)
    assert waiting == {"kind": None, "waiting": True, "read": 0}
    rows, message, selected = page.load_points(waiting, None)
    assert (rows, selected) == ([], None)
    assert message.startswith("Results are not ready")

    job.status, job.phase = int(JobStatus.FINISHED), RunPhase.FINISHED
    rows, message, _ = page.load_points(page.locate_run_output(_run(tmp_path), 2), None)
    assert message == "No reconstructed images were found for this run."


def test_refresh_offers_points_completed_since_and_keeps_what_is_shown(tmp_path):
    inputs = [write_wire_scan(tmp_path / f"{point}.h5", seed=index) for index, point in enumerate(POINTS, 1)]
    run_directory = tmp_path / "rec_5"
    view.CACHE.clear()
    with prepare_scan(
        inputs,
        run_directory / RECONSTRUCTION_DIRECTORY,
        geometry=GEOMETRY,
        detector=0,
        point_ids=list(POINTS),
        depth_range=(-25.0, 25.0),
        resolution=5.0,
    ) as scan:
        # Publish each transition separately to check what Refresh shows during a run.
        first, second, third = scan.tasks
        scan.record_dispatch(first)
        scan.record(reconstruct_point(first, num_threads=1))
        scan.snapshot(force=True)

        opened = page.locate_run_output(_run(run_directory), None)
        rows, message, selected = page.load_points(opened, None)
        assert [row["status"] for row in rows] == ["complete", "pending", "pending"]
        assert "run running" in message and "press Refresh" in message
        assert selected == "wire_1"
        trace = view.full_trace(view.Artifact.from_store(opened), "wire_1")

        scan.record_dispatch(second)
        scan.snapshot(force=True)
        rows, _, selected = page.load_points(page.locate_run_output(_run(run_directory), 1), "wire_1")
        assert [row["status"] for row in rows] == ["complete", "writing", "pending"]
        assert page.select_point([rows[1]], "wire_1")[1] == (
            "Point wire_2 is being reconstructed; press Refresh after it completes. It has no images."
        )

        scan.record(reconstruct_point(second, num_threads=1))
        scan.snapshot(force=True)
        refreshed = page.locate_run_output(_run(run_directory), 2)
        rows, _, selected = page.load_points(refreshed, "wire_1")
        assert [row["status"] for row in rows] == ["complete", "complete", "pending"]
        assert selected is dash.no_update  # the shown point, its ROIs, and its figures stay
        bar, grid_selection = page.show_point("wire_1", rows)
        assert "2 of 3 points complete" in str(bar) and grid_selection == [rows[0]]
        artifact = view.Artifact.from_store(refreshed)
        assert view.full_trace(artifact, "wire_1") is trace  # a new snapshot keeps the unchanged point's products
        assert page.select_point([rows[1]], "wire_1") == ("wire_2", dash.no_update)
        frame = view.stored_frame(artifact, "wire_2", 0)
        with ScanReader(artifact.path) as catalog:
            np.testing.assert_array_equal(frame, catalog.point("wire_2").frame(0))
        with pytest.raises(view.ViewError, match="point 'wire_3' is pending"):
            view.stored_frame(artifact, "wire_3", 0)
        scan.finish(cancelled=True)

    rows, message, _ = page.load_points(page.locate_run_output(_run(run_directory), 3), "wire_1")
    assert [row["status"] for row in rows] == ["complete", "complete", "unattempted"]
    assert "run cancelled" in message
    assert page.select_point([rows[2]], "wire_1")[1].startswith("Point wire_3 was not reconstructed because")


# --- Depth View -------------------------------------------------------------------------


def test_depth_view_opens_at_the_brightest_depth_and_shows_exactly_that_stored_frame(scan):
    frames, depths = _stored(scan)
    peak = int(frames.sum(axis=(1, 2), dtype=np.int64).argmax())
    with _ctx("wr-point"):
        maximum, index = page.reset_depth_index("wire_1", page.TAB_DEPTH, scan.to_store(), 0)
    assert (maximum, index) == (N_DEPTHS - 1, peak)

    figure, readout, status, _, drawn = page.show_depth_frame(
        index, "viridis", page.TAB_DEPTH, "wire_1", scan.to_store(), None
    )
    np.testing.assert_array_equal(figure.data[0].z, frames[peak])
    assert figure.data[0].z.dtype == np.int32  # signed both-edge values reach the browser unchanged
    assert len(figure.data) == 1 and np.asarray(figure.data[0].z).ndim == 2  # one frame, never the stack
    assert readout.startswith(f"{depths[peak]:.4g} µm")
    assert status == ""
    with pytest.raises(PreventUpdate):  # revisiting the tab resends nothing
        page.show_depth_frame(index, "viridis", page.TAB_DEPTH, "wire_1", scan.to_store(), drawn)

    _, _, status, _, _ = page.show_depth_frame(N_DEPTHS, "gray", page.TAB_DEPTH, "wire_1", scan.to_store(), None)
    assert status == f"Depth index must be 0 to {N_DEPTHS - 1}"


def test_switching_points_draws_the_new_points_own_frame(scan):
    _, _, _, _, drawn = page.show_depth_frame(2, "gray", page.TAB_DEPTH, "wire_1", scan.to_store(), None)
    figure, _, _, _, _ = page.show_depth_frame(2, "gray", page.TAB_DEPTH, "wire_3", scan.to_store(), drawn)
    frames, _ = _stored(scan, "wire_3")
    np.testing.assert_array_equal(figure.data[0].z, frames[2])
    assert "wire_3" in figure.layout.title.text


def test_inactive_tabs_prepare_nothing(scan):
    with pytest.raises(PreventUpdate):
        page.show_depth_frame(0, "gray", page.TAB_POINTS, "wire_1", scan.to_store(), None)
    with pytest.raises(PreventUpdate):
        page.show_roi_traces([], "depth", "linear", "sum", page.TAB_DEPTH, {}, "wire_1", scan.to_store())
    assert len(view.CACHE) == 0


# --- ROI Inspector ----------------------------------------------------------------------


def _click(x, y, curve=0):
    return {"points": [{"x": x, "y": y, "curveNumber": curve}]}


def _add(scan, state, x, y, *, size=5, selected=None):
    with _ctx("wr-roi-image"):
        return page.edit_rois("wire_1", _click(x, y), None, size, state, selected, scan.to_store())


def test_every_image_click_adds_a_square_but_never_outside_the_image(scan):
    with pytest.raises(PreventUpdate):  # a click on an ROI outline is not a placement
        with _ctx("wr-roi-image"):
            page.edit_rois("wire_1", _click(10, 10, curve=1), None, 5, {}, [], scan.to_store())

    state, rows, selected, message = _add(scan, {}, 16, 14)
    assert state["wire_1"]["rois"] == [{"id": "ROI 1", "bounds": [12, 17, 14, 19], "color": "rgb(230,90,60)"}]
    assert rows == [{"id": "ROI 1", "y": 14.0, "x": 16.0, "size": 5, "color": "rgb(230,90,60)"}]
    assert selected == rows and message == ""

    state, rows, selected, _ = _add(scan, state, 4, 4, size=4, selected=[])
    assert rows[1] == {"id": "ROI 2", "y": 3.5, "x": 3.5, "size": 4, "color": "rgb(60,140,230)"}
    assert [row["id"] for row in selected] == ["ROI 2"]  # the new ROI is selected; the deselected one stays off

    unchanged, _, _, message = _add(scan, state, 1, 1, size=5)
    assert unchanged is dash.no_update
    assert "would extend outside the 32 x 32 image; not added" in str(message)


def test_a_row_delete_removes_one_roi_and_keeps_the_others_identity_colour_and_selection(scan):
    state, rows, _, _ = _add(scan, {}, 16, 14)
    state, rows, _, _ = _add(scan, state, 8, 8, selected=rows)
    state, rows, _, _ = _add(scan, state, 24, 24, selected=rows[:1])  # ROI 2 deselected
    deleted = {"value": "ROI 1", "colId": "delete", "rowId": "ROI 1"}
    with _ctx("wr-roi-grid"):
        state, rows, selected, _ = page.edit_rois(
            "wire_1", None, deleted, 5, state, [rows[0], rows[2]], scan.to_store()
        )
    assert [row["id"] for row in rows] == ["ROI 2", "ROI 3"]
    assert rows[0] == {"id": "ROI 2", "y": 8.0, "x": 8.0, "size": 5, "color": "rgb(60,140,230)"}
    assert [row["id"] for row in selected] == ["ROI 3"]
    state, rows, _, _ = _add(scan, state, 20, 20, selected=[])
    assert rows[-1]["id"] == "ROI 4" and rows[-1]["color"] == "rgb(220,160,40)"


def test_rois_belong_to_their_point(scan):
    state, _, _, _ = _add(scan, {}, 16, 14)
    with _ctx("wr-point"):
        _, rows, selected, _ = page.edit_rois("wire_3", None, None, 5, state, [], scan.to_store())
    assert rows == [] and selected == []
    with _ctx("wr-point"):
        _, rows, _, _ = page.edit_rois("wire_1", None, None, 5, state, [], scan.to_store())
    assert [row["id"] for row in rows] == ["ROI 1"]


def test_roi_traces_are_sums_of_the_reopened_stored_pixels(scan):
    frames, depths = _stored(scan)
    state, rows, _, _ = _add(scan, {}, 16, 14)
    state, rows, _, _ = _add(scan, state, 5, 5, size=4, selected=rows)
    figure, _ = page.show_roi_traces(rows, "depth", "linear", "sum", page.TAB_ROI, state, "wire_1", scan.to_store())
    assert [trace.name for trace in figure.data] == ["ROI 1", "ROI 2"]
    assert [trace.line.color for trace in figure.data] == ["rgb(230,90,60)", "rgb(60,140,230)"]
    np.testing.assert_array_equal(figure.data[0].x, depths)
    np.testing.assert_array_equal(figure.data[0].y, frames[:, 12:17, 14:19].sum(axis=(1, 2), dtype=np.int64))
    np.testing.assert_array_equal(figure.data[1].y, frames[:, 3:7, 3:7].sum(axis=(1, 2), dtype=np.int64))

    only_second, _ = page.show_roi_traces(
        rows[1:], "index", "linear", "sum", page.TAB_ROI, state, "wire_1", scan.to_store()
    )
    assert [trace.name for trace in only_second.data] == ["ROI 2"]
    assert only_second.data[0].line.color == "rgb(60,140,230)"  # deselecting never recolours

    normalized, _ = page.show_roi_traces(
        rows, "depth", "linear", "normalized", page.TAB_ROI, state, "wire_1", scan.to_store()
    )
    expected = frames[:, 12:17, 14:19].sum(axis=(1, 2), dtype=np.int64)
    np.testing.assert_allclose(normalized.data[0].y, expected / expected.max())


def test_roi_edits_patch_the_overlays_and_keep_the_reference_image_in_the_browser(scan):
    state, rows, _, _ = _add(scan, {}, 16, 14)
    with _ctx("wr-point"):
        figure, drawn, _ = page.show_reference(
            "sum_reconstructed", state, "wire_1", page.TAB_ROI, None, scan.to_store()
        )
    frames, _ = _stored(scan)
    np.testing.assert_array_equal(figure.data[0].z, frames.sum(axis=0, dtype=np.int64))
    assert [trace.name for trace in figure.data[1:]] == ["ROI 1"]
    assert drawn["count"] == 1

    state, rows, _, _ = _add(scan, state, 5, 5, selected=rows)
    with _ctx("wr-rois"):
        patched, drawn, _ = page.show_reference(
            "sum_reconstructed", state, "wire_1", page.TAB_ROI, drawn, scan.to_store()
        )
    operations = patched.to_plotly_json()["operations"]
    assert [op["operation"] for op in operations] == ["Delete", "Extend"]
    assert operations[0]["location"] == ["data", 1]
    assert [trace["name"] for trace in operations[1]["params"]["value"]] == ["ROI 1", "ROI 2"]
    assert all("z" not in trace for trace in operations[1]["params"]["value"])  # no image in the update
    assert drawn["count"] == 2

    with _ctx("wire-recon-detail-tabs"), pytest.raises(PreventUpdate):
        page.show_reference("sum_reconstructed", state, "wire_1", page.TAB_ROI, drawn, scan.to_store())


def test_every_reference_choice_is_shown_or_honestly_unavailable(scan, per_depth):
    for kind in ("sum_reconstructed", "first_raw", "sum_raw"):
        with _ctx("wr-roi-reference"):
            figure, _, _ = page.show_reference(kind, {}, "wire_1", page.TAB_ROI, None, scan.to_store())
        assert figure.data[0].meta["kind"] == kind
    with _ctx("wr-roi-reference"):
        figure, drawn, _ = page.show_reference("first_raw", {}, "wire_1", page.TAB_ROI, None, per_depth.to_store())
    assert figure["data"] == []
    assert "First raw frame is unavailable" in figure["layout"]["annotations"][0]["text"]
    assert drawn == {"point": None, "count": 0}


def test_per_depth_points_give_the_same_frames_and_roi_traces_as_the_scan_file(scan, per_depth):
    frames, _ = _stored(scan)
    figure, _, _, _, _ = page.show_depth_frame(3, "gray", page.TAB_DEPTH, "wire_1", per_depth.to_store(), None)
    np.testing.assert_array_equal(figure.data[0].z, frames[3])
    state, rows, _, _ = _add(per_depth, {}, 16, 14)
    traces, _ = page.show_roi_traces(
        rows, "depth", "linear", "sum", page.TAB_ROI, state, "wire_1", per_depth.to_store()
    )
    np.testing.assert_array_equal(traces.data[0].y, frames[:, 12:17, 14:19].sum(axis=(1, 2), dtype=np.int64))


def test_the_cache_is_keyed_by_point_file_identity_and_bounded_by_bytes(scan, per_depth):
    first = view.full_trace(scan, "wire_1")
    assert view.full_trace(scan, "wire_1") is first
    os.utime(scan.path, ns=(0, os.stat(scan.path).st_mtime_ns + 1))  # a new catalog snapshot
    assert view.full_trace(scan, "wire_1") is first  # keeps the products of an unchanged point
    point_file = ScanReader(scan.path).point_path("wire_1")
    os.utime(point_file, ns=(0, os.stat(point_file).st_mtime_ns + 1))  # a rewritten point file is read again
    assert view.full_trace(scan, "wire_1") is not first

    trace = view.full_trace(per_depth, "wire_1")
    os.utime(per_depth.path, ns=(0, os.stat(per_depth.path).st_mtime_ns + 1))
    assert view.full_trace(per_depth, "wire_1") is not trace

    cache = view.ProductCache(max_bytes=1000)
    cache.get("a", lambda: np.zeros(100))  # 800 bytes
    cache.get("b", lambda: np.zeros(100))
    assert len(cache) == 1 and cache.nbytes == 800
    cache.get("huge", lambda: np.zeros(1000))  # larger than the budget: returned, never kept
    assert cache.nbytes == 800


def test_roi_state_helpers_reject_nonpositive_sizes():
    with pytest.raises(depth_view.RoiPlacementError, match="positive whole number"):
        depth_view.add_roi({}, "p", 0, 5, 5, (32, 32))
    with pytest.raises(depth_view.RoiPlacementError, match="positive whole number"):
        depth_view.add_roi({}, "p", None, 5, 5, (32, 32))


def test_uncached_products_share_one_catalog_snapshot(scan, monkeypatch):
    reads = []
    original = view.ScanReader

    def counted(path):
        reads.append(path)
        return original(path)

    view.CACHE.clear()
    monkeypatch.setattr(view, "ScanReader", counted)
    first = view.stored_frame(scan, "wire_1", 0)
    view.stored_frame(scan, "wire_1", 1)
    view.reference(scan, "wire_3", "sum_reconstructed")
    view.roi_trace(scan, "wire_1", "roi", (10, 15, 10, 15))
    assert reads == [scan.path]
    # Readers belong to their individual callbacks, even when the catalog is shared.
    with view._open_point(scan, "wire_1") as left:
        with view._open_point(scan, "wire_3") as right:
            left.close()
            assert right.frame(0).shape == (32, 32)
    os.utime(scan.path, ns=(0, os.stat(scan.path).st_mtime_ns + 1))
    assert view.stored_frame(scan, "wire_1", 0) is first
    view.stored_frame(scan, "wire_1", 2)
    assert reads == [scan.path, scan.path]


def test_cached_catalog_still_rejects_mismatched_point_metadata(scan, tmp_path):
    directory = tmp_path / "reconstruction"
    shutil.copytree(os.path.dirname(scan.path), directory)
    artifact = view.Artifact("scan", os.fspath(directory / "scan.h5"))
    view.stored_frame(artifact, "wire_1", 0)  # cache the original catalog
    point_path = ScanReader(artifact.path).point_path("wire_1")
    with h5py.File(point_path, "r+") as point:
        point["/entry1/reconstruction/point/manifest_index"][()] = 42
    with pytest.raises(view.ViewError, match="as the catalog describes it"):
        view.stored_frame(artifact, "wire_1", 1)
