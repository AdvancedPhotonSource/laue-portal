"""Tests for the wire reconstruction adapter, run through lauelab on a small synthetic wire scan."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest
from lauelab.indexing import InputError
from lauelab.reconstruct import ScanReader, validate_scan_file
from lauelab.reconstruct import scan as lauelab_scan

from laue_portal.processing.compute import contract, wire
from laue_portal.services import reconstruction_view as view
from laue_portal.workflows.files import ResolvedInput
from laue_portal.workflows.manifest import (
    RECONSTRUCTION_DIRECTORY,
    build_manifest_entries,
    reconstruction_catalog_path,
)
from tests.wire_support import GEOMETRY, N_DEPTHS, OPTIONS, write_wire_scan


class Hooks:
    def __init__(self, stop_after=None):
        self.stop_after = stop_after
        self.progress = []
        self.failures = []
        self.outcome = None

    def should_stop(self):
        return self.stop_after is not None and len(self.progress) >= self.stop_after

    def report_progress(self, *, succeeded, failed):
        self.progress.append((succeeded, failed))

    def record_failure(self, record):
        self.failures.append(record)

    def report_outcome(self, outcome):
        self.outcome = outcome

    def log(self, message):
        pass


def _parameters(**overrides):
    values = {
        "geometry_file": "/calib/geoN.xml",
        "depth_start": -50.0,
        "depth_end": 150.0,
        "depth_resolution": 1.0,
        "wire_edges": "leading",
        "percent_brightest": 100.0,
        "num_threads": 4,
        "memory_limit_mb": 50000,
        "verbose": 1,
    }
    values.update(overrides)
    return values


def _request(tmp_path, count=3, workers=1, **overrides):
    run_dir = tmp_path / "rec_1" / "data"
    return contract.RunRequest(
        job_id=1,
        kind=wire.WIRE_KIND,
        display_id="Reconstruction R1",
        run_directory=os.fspath(run_dir),
        manifest_path=os.fspath(run_dir / "inputs.jsonl"),
        document={
            "kind": wire.WIRE_KIND,
            "request": _parameters(**overrides),
            "output": {"directory": os.fspath(run_dir)},
        },
        n_inputs=count,
        workers=1,
        max_in_flight=None,
        reconstruction_workers=workers,
    )


def _entries(tmp_path, count=3, missing=()):
    """Point files point_1 ... point_<count>; indices in ``missing`` are never written."""

    paths = []
    for i in range(1, count + 1):
        path = tmp_path / f"point_{i}.h5"
        if i not in missing:
            write_wire_scan(path, seed=i)
        paths.append(ResolvedInput(os.fspath(path), 0, (i,)))
    return build_manifest_entries(tuple(paths))


def test_settings_follow_the_wire_form_mapping():
    settings = wire.settings_from_request(_parameters(wire_edges=" Both "))
    assert settings == wire.WireSettings(
        geometry_file="/calib/geoN.xml",
        depth_range=(-50.0, 150.0),
        resolution=1.0,
        wire_edge="both",
        percent_brightest=100.0,
        threads_per_worker=4,
        memory_limit_mb=50000,
    )
    assert wire.settings_from_request(_parameters(num_threads=None, memory_limit_mb=0)).threads_per_worker is None
    assert wire.settings_from_request(_parameters(memory_limit_mb=None)).memory_limit_mb == 8192
    with pytest.raises(InputError, match="wire edge must be one of"):
        wire.settings_from_request(_parameters(wire_edges="0 1"))


def test_registry_resolves_the_native_adapters():
    assert contract.get_compute_function(wire.WIRE_KIND) is wire.compute_wire_reconstruction
    from laue_portal.processing.compute import lauego

    assert contract.get_compute_function(lauego.LAUEGO_KIND) is lauego.compute_lauego_indexing


def test_points_are_reconstructed_into_a_scan_directory_with_per_point_outcomes(tmp_path):
    request = _request(tmp_path, **OPTIONS, geometry_file=os.fspath(GEOMETRY), wire_edges="both")
    hooks = Hooks()

    outcome = wire.compute_wire_reconstruction(request, _entries(tmp_path, missing={2}), hooks)

    assert (outcome.n_succeeded, outcome.n_failed, outcome.stopped) == (2, 1, False)
    assert hooks.progress == [(0, 1), (1, 1), (2, 1)]  # the missing input fails while the scan is prepared
    assert [(f.index, f.input_id, f.error_type) for f in hooks.failures] == [(1, "point_2", "ReconstructionError")]
    assert "does not exist" in hooks.failures[0].message
    catalog = reconstruction_catalog_path(request.run_directory)
    assert outcome.artifacts == {"reconstruction": catalog}
    assert outcome.validation_error is None
    assert os.listdir(request.run_directory) == [RECONSTRUCTION_DIRECTORY]
    points = os.path.join(request.run_directory, RECONSTRUCTION_DIRECTORY, "points")
    assert sorted(os.listdir(points)) == ["point_1.h5", "point_3.h5"]  # a failed point publishes no file
    assert outcome.provenance["engine"].startswith("lauelab reconstruct_scan")
    assert (outcome.provenance["workers"], outcome.provenance["threads_per_worker"]) == (1, 1)
    assert outcome.provenance["reconstruction_summary"] == {
        "run_status": "finished",
        "n_points": 3,
        "n_complete": 2,
        "n_failed": 1,
        "n_unattempted": 0,
    }
    assert outcome.summary == "2 of 3 point(s) reconstructed into reconstruction/"
    with ScanReader(catalog) as scan:
        assert scan.point_ids == ("point_1", "point_2", "point_3")  # manifest input IDs, in manifest order
        assert [entry.status for entry in scan.points] == ["complete", "failed", "complete"]
        assert scan.point_path("point_3") == Path(points, "point_3.h5")
        point = scan.point("point_3")
        assert point.shape == (N_DEPTHS, 32, 32)
        assert point.dtype.kind == "i"  # both-edge output keeps its sign


def test_several_workers_give_the_same_points(tmp_path):
    one = _request(tmp_path / "one", **OPTIONS, geometry_file=os.fspath(GEOMETRY))
    two = _request(tmp_path / "two", workers=2, **OPTIONS, geometry_file=os.fspath(GEOMETRY))
    entries = _entries(tmp_path)

    first = wire.compute_wire_reconstruction(one, entries, Hooks())
    second = wire.compute_wire_reconstruction(two, entries, Hooks())

    assert (first.n_succeeded, second.n_succeeded, second.provenance["workers"]) == (3, 3, 2)
    with ScanReader(first.artifacts["reconstruction"]) as a, ScanReader(second.artifacts["reconstruction"]) as b:
        for point_id in a.point_ids:
            left, right = a.point(point_id), b.point(point_id)
            np.testing.assert_array_equal(left.depth_um, right.depth_um)
            for depth in range(left.shape[0]):
                np.testing.assert_array_equal(left.frame(depth), right.frame(depth))


def test_completed_points_can_be_viewed_while_the_run_executes(tmp_path, monkeypatch):
    # Publish every update so the test does not depend on the snapshot timer.
    monkeypatch.setattr(lauelab_scan, "_SNAPSHOT_SECONDS", 0.0)
    request = _request(tmp_path, **OPTIONS, geometry_file=os.fspath(GEOMETRY))
    seen = []

    class Watching(Hooks):
        def report_progress(self, *, succeeded, failed):
            super().report_progress(succeeded=succeeded, failed=failed)
            if succeeded == 1:
                artifact = view.locate_artifact(request.run_directory)
                assert ScanReader(artifact.path).run_status == "running"
                seen.extend((row["point_id"], row["status"]) for row in view.point_table(artifact).rows)
                seen.append(view.stored_frame(artifact, "point_1", 0).shape)

    view.CACHE.clear()
    outcome = wire.compute_wire_reconstruction(request, _entries(tmp_path), Watching())

    assert outcome.n_succeeded == 3
    assert seen == [("point_1", "complete"), ("point_2", "pending"), ("point_3", "pending"), (32, 32)]


def test_stop_between_points_publishes_completed_points_and_records_not_run(tmp_path):
    request = _request(tmp_path, **OPTIONS, geometry_file=os.fspath(GEOMETRY))
    hooks = Hooks(stop_after=1)

    outcome = wire.compute_wire_reconstruction(request, _entries(tmp_path), hooks)

    assert (outcome.n_succeeded, outcome.n_failed, outcome.stopped) == (1, 0, True)
    assert [(f.index, f.category) for f in hooks.failures] == [(1, "cancelled"), (2, "cancelled")]
    summary = validate_scan_file(outcome.artifacts["reconstruction"])
    assert (summary.run_status, summary.n_complete, summary.n_unattempted) == ("cancelled", 1, 2)


def test_a_stop_lets_running_points_finish(tmp_path):
    request = _request(tmp_path, workers=2, **OPTIONS, geometry_file=os.fspath(GEOMETRY))
    hooks = Hooks(stop_after=1)

    outcome = wire.compute_wire_reconstruction(request, _entries(tmp_path), hooks)

    # The two active points finish; cancellation skips the third.
    assert (outcome.n_succeeded, outcome.n_failed, outcome.stopped) == (2, 0, True)
    assert [(f.index, f.category) for f in hooks.failures] == [(2, "cancelled")]
    with ScanReader(outcome.artifacts["reconstruction"]) as scan:
        assert scan.run_status == "cancelled"
        assert [entry.status for entry in scan.points] == ["complete", "complete", "unattempted"]


def test_shared_configuration_problems_stop_the_run_and_publish_nothing(tmp_path):
    request = _request(tmp_path, **OPTIONS, geometry_file=os.fspath(tmp_path / "missing.xml"))
    hooks = Hooks()
    with pytest.raises(ValueError, match="Failed to load geometry"):
        wire.compute_wire_reconstruction(request, _entries(tmp_path), hooks)
    assert hooks.outcome.artifacts == {}
    assert not os.path.exists(os.path.join(request.run_directory, RECONSTRUCTION_DIRECTORY))


def test_an_existing_reconstruction_is_never_overwritten(tmp_path):
    request = _request(tmp_path, **OPTIONS, geometry_file=os.fspath(GEOMETRY))
    existing = reconstruction_catalog_path(request.run_directory)
    os.makedirs(os.path.dirname(existing))
    with open(existing, "w") as handle:
        handle.write("earlier run")
    hooks = Hooks()
    with pytest.raises(FileExistsError):
        wire.compute_wire_reconstruction(request, _entries(tmp_path), hooks)
    assert hooks.outcome.artifacts == {}
    with open(existing) as handle:
        assert handle.read() == "earlier run"
