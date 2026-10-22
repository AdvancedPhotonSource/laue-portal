"""Estimate work from ranges/catalogs without detector reads or directory scans."""

import os

import pytest
from lauelab.reconstruct import ScanReader, reconstruct_scan

from laue_portal.processing.bdp.settings import available_backends, require_backend
from laue_portal.services import runtime_estimates as estimates
from tests.wire_support import GEOMETRY, write_wire_scan

APS = {"workers": 32, "max_in_flight": 256, "reconstruction_workers": 4, "threads_per_worker": 8}
CRUX = {"workers": 32, "max_in_flight": 256, "reconstruction_workers": 32, "threads_per_worker": 4}


def selection(**overrides):
    return {
        "root_path": "/not-mounted",
        "data_path": "raw",
        "filenamePrefix": "wire_%d.h5",
        "scanPoints": "1-825",
        "depth_start": -30,
        "depth_end": 90,
        "depth_resolution": 1,
        "frame_skip": 1,
        "wire_skip": 1,
        **overrides,
    }


def test_one_aps_option_switches_transport_only_after_dm_is_enabled():
    settings = {"enabled": True, "targets": {"aps": {"enabled": False}, "crux": {"enabled": True}}}
    assert available_backends(settings) == [{"label": "APS", "value": "local"}, {"label": "ALCF", "value": "crux"}]
    require_backend("local", settings)
    with pytest.raises(ValueError):
        require_backend("aps", settings)
    settings["targets"]["aps"]["enabled"] = True
    assert available_backends(settings) == [{"label": "APS", "value": "aps"}, {"label": "ALCF", "value": "crux"}]


def test_large_directory_selection_neither_expands_ranges_nor_scans_files(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Estimate enumerated inputs instead of counting the selected ranges")

    monkeypatch.setattr(os, "listdir", forbidden)
    monkeypatch.setattr(estimates.srange, "list", forbidden)
    count = estimates.count_selection(
        "indexing", selection(scanPoints="1-100000000", depthRange="0-120", filenamePrefix="wire_%d_%d.h5")
    )
    assert (count.points, count.frames) == (100_000_000, 12_100_000_000)


def test_reconstruction_825_point_estimates_match_recorded_single_node_profiles():
    local = estimates.estimate_runtime("reconstruction", "local", selection(), policy=APS)
    remote = estimates.estimate_runtime("reconstruction", "crux", selection(), policy=CRUX)
    assert (local.selection.points, local.selection.frames) == (825, 99825)
    assert 146 < local.seconds / 60 < 148
    assert 32 < remote.seconds / 60 < 34
    half = estimates.estimate_runtime("reconstruction", "local", selection(scanPoints="1-400"), policy=APS)
    assert half.seconds == pytest.approx(local.seconds * 400 / 825)
    tiny = estimates.estimate_runtime("reconstruction", "crux", selection(scanPoints="1"), policy=CRUX)
    assert tiny.seconds > 60  # A single point still needs one worker wave, not 1/32 of one.


def test_indexing_uses_the_current_single_pool_and_handles_pooled_runs():
    fields = selection(filenamePrefix="wire_%d_%d.h5", depthRange="0-120")
    result = estimates.estimate_runtime("indexing", "crux", fields, policy=CRUX)
    assert 88 < result.seconds / 60 < 89
    assert result.profile["workers"] == 32
    two = estimates.estimate_runtime("indexing", "crux", {**fields, "IDnumber": "SN1; SN2"}, policy=CRUX)
    assert two.runs == 2 and two.selection.frames == 2 * 99825
    assert two.seconds == pytest.approx(2 * result.seconds)
    with pytest.raises(ValueError):
        estimates.estimate_runtime(
            "indexing", "crux", {**fields, "IDnumber": "SN1;SN2", "data_path": "a;b;c"}, policy=CRUX
        )


def test_four_node_estimates_use_the_measured_full_scan_layout():
    policy = {**CRUX, "nodes": 4, "indexing_ranks_per_node": 4}
    recon = estimates.estimate_runtime("reconstruction", "crux", selection(), policy=policy)
    index = estimates.estimate_runtime(
        "indexing", "crux", selection(filenamePrefix="wire_%d_%d.h5", depthRange="0-120"), policy=policy
    )
    assert recon.seconds == pytest.approx(732)
    assert index.seconds == pytest.approx(385)
    assert recon.profile["nodes"] == index.profile["nodes"] == 4
    assert index.profile["ranks_per_node"] == 4


def test_bidirectional_transfer_projection_uses_measured_flow_times_for_each_direction():
    reconstruction = estimates.estimate_runtime("reconstruction", "crux", selection(), policy=CRUX)
    transfer = estimates.estimate_transfers("reconstruction", reconstruction.selection)
    assert transfer.input_bytes == pytest.approx(3529561450706)
    assert transfer.output_bytes == pytest.approx(921070099039)
    assert transfer.input_seconds == pytest.approx(941.172)
    assert transfer.output_seconds == pytest.approx(291.678)
    assert transfer.seconds == pytest.approx(1232.85)
    indexing = estimates.estimate_runtime(
        "indexing", "crux", selection(filenamePrefix="wire_%d_%d.h5", depthRange="0-120"), policy=CRUX
    )
    transfer = estimates.estimate_transfers("indexing", indexing.selection)
    assert transfer.input_bytes == pytest.approx(921101263976)
    assert transfer.output_bytes == pytest.approx(627512316)
    assert transfer.input_seconds == pytest.approx(468.087)
    assert transfer.output_seconds == pytest.approx(34.277)


def test_aps_projection_scales_four_measured_workers_to_three_eight_thread_workers():
    estimate = estimates.estimate_runtime(
        "reconstruction", "local", selection(), policy={**APS, "reconstruction_workers": 3}
    )
    assert estimate.profile["workers"] == 4 and estimate.profile["threads"] == 8
    assert estimate.seconds / 60 == pytest.approx(196.241754249, abs=0.001)
    assert any("scales the nearest measured worker pool" in note for note in estimate.notes)


def test_small_transfers_keep_a_minimum_orchestration_cost():
    estimate = estimates.estimate_runtime("reconstruction", "crux", selection(scanPoints="1"), policy=CRUX)
    transfer = estimates.estimate_transfers("reconstruction", estimate.selection)
    assert transfer.input_seconds == pytest.approx(31.575)
    assert transfer.output_seconds == pytest.approx(14.678)


def test_catalog_counts_depths_without_opening_point_files_and_reuses_snapshot(tmp_path, monkeypatch):
    source = write_wire_scan(tmp_path / "wire_1.h5")
    output = tmp_path / "reconstruction"
    reconstruct_scan(
        [source],
        output,
        geometry=GEOMETRY,
        detector=0,
        depth_range=(-25, 25),
        resolution=5,
        percent_brightest=100,
        threads_per_worker=1,
        workers=1,
    )
    fields = selection(data_path=str(output / "scan.h5"), scanPoints="1", depthRange=None)
    snapshots = []
    original = ScanReader.__init__

    def init(reader, path):
        snapshots.append(path)
        original(reader, path)

    monkeypatch.setattr(ScanReader, "__init__", init)

    def no_point_reads(*args, **kwargs):
        pytest.fail("Counting must not open a reconstructed point's pixels")

    monkeypatch.setattr(ScanReader, "point", no_point_reads)
    estimates._catalog_points.cache_clear()
    monkeypatch.setattr(estimates.time, "monotonic", lambda: 100)
    first = estimates.count_selection("indexing", fields)
    second = estimates.count_selection("indexing", {**fields, "depthRange": "0,3,10"})
    assert first.points == 1 and first.frames == 11
    assert second.frames == 3
    assert first.staged_frames == second.staged_frames == 11
    first_transfer = estimates.estimate_transfers("indexing", first)
    subset_transfer = estimates.estimate_transfers("indexing", second)
    assert subset_transfer.input_bytes == first_transfer.input_bytes
    assert subset_transfer.output_bytes == pytest.approx(first_transfer.output_bytes * 3 / 11)
    assert len(snapshots) == 1
    with pytest.raises(ValueError, match="exceed"):
        estimates.count_selection("indexing", {**fields, "depthRange": "0-11"})


@pytest.mark.parametrize(
    "values",
    [
        {"scanPoints": "1-5:0"},
        {"depth_resolution": 0},
        {"depth_start": float("nan")},
        {"filenamePrefix": "*.h5"},
    ],
)
def test_invalid_or_unknown_selections_do_not_invent_a_count(values):
    with pytest.raises(ValueError):
        estimates.count_selection("reconstruction", selection(**values))
