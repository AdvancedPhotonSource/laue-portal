"""Tests for the native wire reconstruction adapter (Reconstructor is faked; the library tests its numerics)."""

from __future__ import annotations

import os
from types import SimpleNamespace

import numpy as np
import pytest
from lauelab.indexing import InputError

from laue_portal.processing.compute import contract, wire
from laue_portal.workflows.files import ResolvedInput
from laue_portal.workflows.manifest import build_manifest_entries


class Hooks:
    def __init__(self, stop_after=None):
        self.stop_after = stop_after
        self.progress = []
        self.failures = []

    def should_stop(self):
        return self.stop_after is not None and len(self.progress) >= self.stop_after

    def report_progress(self, *, succeeded, failed):
        self.progress.append((succeeded, failed))

    def record_failure(self, record):
        self.failures.append(record)

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


def _request(tmp_path, count=3, **overrides):
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
    )


def _entries(tmp_path, count=3):
    return build_manifest_entries(
        tuple(ResolvedInput(os.fspath(tmp_path / f"point_{i}.h5"), 0, (i,)) for i in range(1, count + 1))
    )


class FakeReconstructor:
    instances = []

    def __init__(self, geometry, detector, **options):
        self.geometry = geometry
        self.detector = detector
        self.options = options
        self.num_threads = options.get("num_threads") or 8
        self.calls = []
        FakeReconstructor.instances.append(self)

    def reconstruct(self, path, output_base=None, *, return_images=False):
        self.calls.append((path, output_base))
        stem = os.path.basename(path)
        if "point_2" in stem:
            raise InputError("input file has 3 stored slices; at least 5 are needed")
        if "point_3" in stem:
            return SimpleNamespace(
                success=False,
                output_files=[f"{output_base}0.h5"],
                error="write failed",
                last_completed_stripe=1,
                depth_um=None,
            )
        os.makedirs(os.path.dirname(output_base), exist_ok=True)
        files = [f"{output_base}{k}.h5" for k in range(3)] + [f"{output_base}summary.txt"]
        for name in files:
            with open(name, "w") as handle:
                handle.write("data")
        return SimpleNamespace(
            success=True, output_files=files, error=None, last_completed_stripe=2, depth_um=np.array([-1.0, 0.0, 1.0])
        )


@pytest.fixture(autouse=True)
def fake_reconstructor(monkeypatch):
    FakeReconstructor.instances = []
    monkeypatch.setattr(wire, "Reconstructor", FakeReconstructor)


def test_settings_follow_the_wire_form_mapping():
    settings = wire.settings_from_request(_parameters(wire_edges=" Both "))
    assert settings == wire.WireSettings(
        geometry_file="/calib/geoN.xml",
        depth_range=(-50.0, 150.0),
        resolution=1.0,
        wire_edge="both",
        percent_brightest=100.0,
        num_threads=4,
        memory_limit_mb=50000,
    )
    assert wire.settings_from_request(_parameters(num_threads=None, memory_limit_mb=0)).num_threads is None
    assert wire.settings_from_request(_parameters(memory_limit_mb=None)).memory_limit_mb == 8192
    with pytest.raises(InputError, match="wire edge must be one of"):
        wire.settings_from_request(_parameters(wire_edges="0 1"))


def test_registry_resolves_the_native_adapters():
    assert contract.get_compute_function(wire.WIRE_KIND) is wire.compute_wire_reconstruction
    from laue_portal.processing.compute import lauego

    assert contract.get_compute_function(lauego.LAUEGO_KIND) is lauego.compute_lauego_indexing


def test_points_are_reconstructed_in_manifest_order_with_per_point_outcomes(tmp_path):
    request = _request(tmp_path)
    hooks = Hooks()

    outcome = wire.compute_wire_reconstruction(request, _entries(tmp_path), hooks)

    reconstructor = FakeReconstructor.instances[0]
    assert (reconstructor.geometry, reconstructor.detector) == ("/calib/geoN.xml", 0)
    assert reconstructor.options == {
        "depth_range": (-50.0, 150.0),
        "resolution": 1.0,
        "wire_edge": "leading",
        "percent_brightest": 100.0,
        "num_threads": 4,
        "memory_limit_mb": 50000,
    }
    assert [os.path.basename(base) for _, base in reconstructor.calls] == ["point_1_", "point_2_", "point_3_"]
    assert (outcome.n_succeeded, outcome.n_failed, outcome.stopped) == (1, 2, False)
    assert hooks.progress == [(1, 0), (1, 1), (1, 2)]
    assert [(f.index, f.category, f.error_type) for f in hooks.failures] == [
        (1, "input", "InputError"),
        (2, "error", "ReconstructionError"),
    ]
    assert hooks.failures[1].context == {"last_completed_stripe": 1, "partial_files": 1}
    assert outcome.artifacts == {"directory": request.run_directory}
    assert outcome.validation_error is None
    assert outcome.provenance["depths_um"] == [-1.0, 0.0, 1.0]
    assert outcome.provenance["n_files_written"] == 4
    assert outcome.provenance["engine"].startswith("lauelab Reconstructor")
    assert sorted(os.listdir(request.run_directory)) == [
        "point_1_0.h5",
        "point_1_1.h5",
        "point_1_2.h5",
        "point_1_summary.txt",
    ]


def test_stop_between_points_records_not_run(tmp_path):
    hooks = Hooks(stop_after=1)
    outcome = wire.compute_wire_reconstruction(_request(tmp_path), _entries(tmp_path), hooks)
    assert (outcome.n_succeeded, outcome.n_failed, outcome.stopped) == (1, 0, True)
    assert [(f.index, f.category) for f in hooks.failures] == [(1, "cancelled"), (2, "cancelled")]
    assert len(FakeReconstructor.instances[0].calls) == 1


def test_missing_output_files_fail_validation(tmp_path):
    request = _request(tmp_path, count=1)
    hooks = Hooks()

    class Vanishing(FakeReconstructor):
        def reconstruct(self, path, output_base=None, *, return_images=False):
            result = super().reconstruct(path, output_base=output_base)
            os.unlink(result.output_files[1])
            return result

    wire.Reconstructor = Vanishing
    outcome = wire.compute_wire_reconstruction(request, _entries(tmp_path, count=1), hooks)
    assert outcome.n_succeeded == 1
    assert outcome.validation_error.startswith("1 reconstructed file(s) are missing or empty")
    assert outcome.artifacts == {}


def test_shared_configuration_problems_stop_the_run_before_any_point(tmp_path):
    class Refusing(FakeReconstructor):
        def __init__(self, *args, **kwargs):
            raise InputError("geometry has no complete wire section")

    wire.Reconstructor = Refusing
    with pytest.raises(InputError, match="no complete wire section"):
        wire.compute_wire_reconstruction(_request(tmp_path), _entries(tmp_path), Hooks())
