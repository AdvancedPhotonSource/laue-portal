"""Reconstruction to indexing to detector view through one reconstruction-scan file.

A wire run reconstructs three points (one unreadable) into ``reconstruction.h5``
through the queue; an indexing run selects a nonconsecutive subset of depths of
two points from that file; the published results reopen with each frame's
source, and the detector view loads exactly that stored plane.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest
from lauelab.indexing import ScanFrame
from lauelab.reconstruct import ScanReader
from lauelab.visualization import load_results
from sqlalchemy.orm import Session

from laue_portal.analysis.detector_image import load_detector_image
from laue_portal.processing.queue import enqueue, executors
from laue_portal.workflows import indexing as indexing_workflow
from laue_portal.workflows import reconstruction as reconstruction_workflow
from laue_portal.workflows.execution import JobStatus
from laue_portal.workflows.files import FileResolutionError, ResolvedInput, resolve_request_inputs, resolve_scan_inputs
from laue_portal.workflows.manifest import (
    RECONSTRUCTION_FILENAME,
    ManifestEntry,
    build_manifest_entries,
    read_manifest,
)
from tests.conftest import create_test_metadata
from tests.run_support import FAST_POLICY, load_job, make_engine
from tests.test_compute_lauego import CRYSTAL, _parameters
from tests.test_run_queue import FakeQueue
from tests.wire_support import GEOMETRY, N_DEPTHS, OPTIONS, write_wire_scan


@pytest.fixture
def engine(tmp_path, monkeypatch):
    engine = make_engine(tmp_path, monkeypatch)
    with Session(engine) as session:
        session.add(create_test_metadata(1))
        session.commit()
    monkeypatch.setattr(enqueue, "job_queue", FakeQueue())
    yield engine


@pytest.fixture
def reconstruction(engine, tmp_path):
    """A finished-with-failures both-edge wire run; point 2 is not an HDF5 file."""

    inputs = tmp_path / "wire"
    inputs.mkdir()
    for index in (1, 3):
        write_wire_scan(inputs / f"wire_{index}.h5", seed=index)
    (inputs / "wire_2.h5").write_bytes(b"not an hdf5 file")
    request = reconstruction_workflow.WireReconstructionRequest(
        scan_number=1,
        input_path=os.fspath(inputs),
        output_path_template=os.fspath(tmp_path / "rec_%d"),
        filename_prefixes=["wire_%d"],
        geometry_file=os.fspath(GEOMETRY),
        wire_edges="both",
        scan_points="1-3",
        verbose=0,
        computer_name="test-host",
        submitted_at=datetime(2026, 9, 22, 9, 0, 0),
        **OPTIONS,
    )
    run = reconstruction_workflow.create_reconstruction(request, engine=engine)
    enqueue.enqueue_run(run.job_id, engine=engine)
    executors.execute_run(run.job_id, engine=engine, policy=FAST_POLICY)
    return run


def _index(engine, tmp_path, input_path, *, scan_points, depth_range, depth=None):
    request = indexing_workflow.LaueGoIndexingRequest(
        scan_number=1,
        reconstruction_id=None,
        input_path=os.fspath(input_path),
        output_path_template=os.fspath(tmp_path / "index_%d"),
        filename_prefixes=["wire_%d"],
        scan_points=scan_points,
        depth_range=depth_range,
        detector_crop_x1=0,
        detector_crop_x2=2047,
        detector_crop_y1=0,
        detector_crop_y2=2047,
        output_xml="output.xml",
        energy_unit="keV",
        exposure_unit="sec",
        reciprocal_lattice_unit="1/nm",
        lattice_parameters_unit="nm",
        beamline="34ID-E",
        computer_name="test-host",
        submitted_at=datetime(2026, 9, 22, 10, 0, 0),
        **_parameters(geometry_file=os.fspath(GEOMETRY), crystal_file=os.fspath(CRYSTAL), box_size=5, depth=depth),
    )
    run = indexing_workflow.create_indexing(request, engine=engine)
    enqueue.enqueue_run(run.job_id, engine=engine)
    executors.execute_run(run.job_id, engine=engine, policy=FAST_POLICY)
    return run


def test_wire_run_publishes_one_scan_file_with_honest_point_status(engine, reconstruction):
    job = load_job(engine, reconstruction.job_id)
    assert job.status == JobStatus.FAILED  # one point failed: incomplete, not corrupt
    assert (job.n_succeeded, job.n_failed, job.n_not_run) == (2, 1, 0)
    scan_path = os.path.join(reconstruction.output_path, RECONSTRUCTION_FILENAME)
    run_json = json.loads(Path(reconstruction.output_path, "run.json").read_text())
    assert run_json["artifacts"] == {"reconstruction": scan_path}
    with ScanReader(scan_path) as scan:
        assert [(entry.point_id, entry.status) for entry in scan.points] == [
            ("wire_1", "complete"),
            ("wire_2", "failed"),
            ("wire_3", "complete"),
        ]


def test_indexing_a_depth_subset_reopens_with_the_exact_source_planes(engine, tmp_path, reconstruction):
    scan_path = os.path.join(reconstruction.output_path, RECONSTRUCTION_FILENAME)
    run = _index(engine, tmp_path, scan_path, scan_points="3,1", depth_range="9,0,4")

    job = load_job(engine, run.job_id)
    assert job.status == JobStatus.FINISHED, job.messages
    # Ranges are normalized in ascending order; the selection skips the failed point and depths.
    expected = [("wire_1", 0), ("wire_1", 4), ("wire_1", 9), ("wire_3", 0), ("wire_3", 4), ("wire_3", 9)]
    entries = list(read_manifest(os.path.join(run.output_path, "inputs.jsonl")))
    assert [(entry.point_id, entry.depth_index) for entry in entries] == expected
    assert [entry.input_id for entry in entries] == [f"{point}_{depth}" for point, depth in expected]

    dataset = load_results(os.path.join(run.output_path, "output.h5"))
    assert list(dataset.frame_ids) == [f"{point}_{depth}" for point, depth in expected]
    assert list(dataset.sources) == [ScanFrame(scan_path, point, depth) for point, depth in expected]
    with ScanReader(scan_path) as scan:
        for position, (point_id, depth_index) in enumerate(expected):
            point = scan.point(point_id)
            assert dataset.depths[position] == point.depth_um[depth_index]
            assert dataset.detector_ids[position] == point.detector_id
            loaded = load_detector_image(dataset.input_images[position], source=dataset.sources[position])
            assert loaded.warning is None
            stored = point.frame(depth_index)
            assert stored.dtype.kind == "i"
            np.testing.assert_array_equal(loaded.image.data, stored)
        # Signed both-edge output reaches the viewer with its sign.
        assert any(scan.point(p).frame(d).min() < 0 for p, d in expected)


def test_an_explicit_zero_depth_overrides_every_scan_frame(engine, tmp_path, reconstruction):
    scan_path = os.path.join(reconstruction.output_path, RECONSTRUCTION_FILENAME)
    run = _index(engine, tmp_path, scan_path, scan_points="1", depth_range="2-3", depth="0")
    assert load_job(engine, run.job_id).status == JobStatus.FINISHED
    dataset = load_results(os.path.join(run.output_path, "output.h5"))
    assert list(dataset.depths) == [0.0, 0.0]


def test_scan_selection_rejects_incomplete_points_and_missing_depths(reconstruction):
    scan_path = os.path.join(reconstruction.output_path, RECONSTRUCTION_FILENAME)
    with pytest.raises(FileResolutionError, match="point 'wire_2' is failed"):
        resolve_scan_inputs(scan_path, ["wire_%d"], [1, 2])
    with pytest.raises(FileResolutionError, match=f"depth indices 0-{N_DEPTHS - 1}; requested {N_DEPTHS}"):
        resolve_scan_inputs(scan_path, ["wire_%d"], [1], depth_indices=[0, N_DEPTHS])
    with pytest.raises(FileResolutionError, match="No files matched template 'wire_%d' for 7"):
        resolve_scan_inputs(scan_path, ["wire_%d"], [7])
    with pytest.raises(FileResolutionError, match="more than one %d"):
        resolve_scan_inputs(scan_path, ["wire_%d_%d"], [1], depth_indices=[0])
    every = resolve_scan_inputs(scan_path, ["wire_%d"], [3])
    assert [item.depth_index for item in every] == list(range(N_DEPTHS))  # blank depth range = all depths


def test_a_directory_input_keeps_the_per_file_machinery(tmp_path, reconstruction):
    frames = tmp_path / "per_depth"
    frames.mkdir()
    for depth in (0, 1):
        (frames / f"wire_3_{depth}.h5").write_bytes(b"")
    resolved = resolve_request_inputs(frames, ["wire_%d_%d.h5"], [3], depth_values=[0, 1])
    assert [(os.path.basename(item.path), item.point_id) for item in resolved] == [
        ("wire_3_0.h5", None),
        ("wire_3_1.h5", None),
    ]
    scan_path = os.path.join(reconstruction.output_path, RECONSTRUCTION_FILENAME)
    assert resolve_request_inputs(scan_path, ["wire_%d"], [3], depth_values=[1])[0].point_id == "wire_3"


def test_scan_manifest_entries_round_trip_and_file_entries_keep_their_line_format():
    scan = build_manifest_entries(
        (ResolvedInput("/r/reconstruction.h5", 0, (8, 0), point_id="p8", depth_index=0),),
    )[0]
    assert (scan.input_id, scan.point_id, scan.depth_index) == ("p8_0", "p8", 0)
    assert ManifestEntry.from_dict(json.loads(scan.to_json())) == scan
    plain = build_manifest_entries((ResolvedInput("/d/a_1.h5", 0, (1,)),))[0]
    assert "point_id" not in json.loads(plain.to_json())
    assert ManifestEntry.from_dict(json.loads(plain.to_json())) == plain
