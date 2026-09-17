"""Tests for the native LaueGo indexing adapter, including real runs on synthetic frames."""

from __future__ import annotations

import os
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import h5py
import pytest
from lauelab.indexing import InputError, PeakParams, ResultsWriter, validate_results_file
from sqlalchemy.orm import Session

from laue_portal.database import db_schema
from laue_portal.processing.compute import lauego
from laue_portal.processing.queue import enqueue, executors
from laue_portal.workflows import indexing as indexing_workflow
from laue_portal.workflows.execution import JobStatus, RunPhase
from laue_portal.workflows.manifest import read_failure_report
from tests.run_support import FAST_POLICY, load_job, make_engine
from tests.test_run_queue import FakeQueue

FIXTURES = Path(__file__).parent / "fixtures" / "lauelab"
GEOMETRY = FIXTURES / "geoN_2022-03-29_14-15-05.xml"
CRYSTAL = FIXTURES / "Ni.xml"
FRAMES = ("synthetic_ni_grain_a.h5", "synthetic_ni_two_grains.h5", "synthetic_ni_empty.h5")


def _parameters(**overrides):
    values = {
        "geometry_file": str(GEOMETRY),
        "crystal_file": str(CRYSTAL),
        "mask_file": None,
        "box_size": 18,
        "max_rfactor": 0.5,
        "min_size": 3.0,
        "min_separation": 20,
        "threshold": None,
        "threshold_ratio": -1,
        "peak_shape": "Lorentzian",
        "max_peaks": 200,
        "smooth": False,
        "index_kev_max_calc": 17.2,
        "index_kev_max_test": 35.0,
        "index_angle_tolerance": 0.1,
        "index_cone": 72.0,
        "index_h": 0,
        "index_k": 0,
        "index_l": 1,
        "max_number": 300,
        "cosmic_filter": True,
        "depth": None,
    }
    values.update(overrides)
    return values


def test_settings_follow_the_approved_form_mapping():
    settings = lauego.settings_from_request(_parameters())
    assert settings.peak_params == PeakParams(
        boxsize=18,
        max_rfactor=0.5,
        min_size=3.0,
        min_separation=20,
        threshold=None,
        threshold_ratio=None,
        peak_shape="Lorentzian",
        max_peaks=300,
        smooth=False,
    )
    assert settings.index_params.max_data == 200
    assert settings.index_params.hkl_prefer == (0, 0, 1)
    assert (settings.index_params.kev_max_calc, settings.index_params.angle_tolerance_deg) == (17.2, 0.1)
    assert settings.cosmic_filter is False
    assert settings.depth_override is None
    assert settings.detector_index == 0

    uncapped = lauego.settings_from_request(_parameters(max_peaks=None, max_number=0, threshold="", threshold_ratio=4))
    assert uncapped.peak_params.max_peaks is None
    assert uncapped.peak_params.threshold is None
    assert uncapped.peak_params.threshold_ratio == 4.0
    assert uncapped.index_params.max_data == lauego.DEFAULT_MAX_DATA

    explicit = lauego.settings_from_request(_parameters(threshold=250, depth="-49.0", mask_file=" /m.h5 "))
    assert explicit.peak_params.threshold == 250.0
    assert explicit.depth_override == -49.0
    assert explicit.mask_file == "/m.h5"


@pytest.mark.parametrize("value", [None, "", "  ", "nan", "NaN", float("nan")])
def test_blank_depth_means_automatic(value):
    assert lauego.parse_depth_override(value) is None


def test_depth_override_accepts_zero_and_rejects_text():
    assert lauego.parse_depth_override("0") == 0.0
    assert lauego.parse_depth_override(12.5) == 12.5
    with pytest.raises(InputError, match="Depth must be a number"):
        lauego.parse_depth_override("2D")
    with pytest.raises(InputError, match="Depth must be a number"):
        lauego.parse_depth_override(True)


def test_fractional_min_size_is_rejected_by_the_library_not_rounded():
    settings = lauego.settings_from_request(_parameters(min_size=1.13))
    with pytest.raises(InputError, match="min_size must be a whole number"):
        lauego.build_indexer(settings)
    lauego.build_indexer(lauego.settings_from_request(_parameters(min_size=3.0)))


@pytest.fixture
def engine(tmp_path, monkeypatch):
    yield make_engine(tmp_path, monkeypatch)


def _frames_dir(tmp_path, names=FRAMES):
    directory = tmp_path / "frames"
    directory.mkdir()
    for index, name in enumerate(names, start=1):
        shutil.copy(FIXTURES / name, directory / f"frame_{index}.h5")
    return directory


def _indexing_run(engine, tmp_path, frames_dir, *, count, monkeypatch, **overrides):
    with Session(engine) as session:
        from tests.conftest import create_test_metadata

        session.add(create_test_metadata(1))
        session.commit()
    output_xml = overrides.pop("output_xml", "output.xml")
    parameters = _parameters(**overrides)
    request = indexing_workflow.LaueGoIndexingRequest(
        scan_number=1,
        reconstruction_id=None,
        input_path=os.fspath(frames_dir),
        output_path_template=os.fspath(tmp_path / "index_%d"),
        filename_prefixes=["frame_%d.h5"],
        scan_points=f"1-{count}" if count > 1 else "1",
        depth_range=None,
        detector_crop_x1=0,
        detector_crop_x2=2047,
        detector_crop_y1=0,
        detector_crop_y2=2047,
        output_xml=output_xml,
        energy_unit="keV",
        exposure_unit="sec",
        reciprocal_lattice_unit="1/nm",
        lattice_parameters_unit="nm",
        beamline="34ID-E",
        computer_name="test-host",
        submitted_at=datetime(2026, 9, 16, 11, 0, 0),
        **parameters,
    )
    run = indexing_workflow.create_indexing(request, engine=engine)
    monkeypatch.setattr(enqueue, "job_queue", FakeQueue())
    enqueue.enqueue_run(run.job_id, engine=engine)
    return run


def test_native_indexing_run_publishes_validated_results_and_xml(engine, tmp_path, monkeypatch):
    frames_dir = _frames_dir(tmp_path)
    run = _indexing_run(engine, tmp_path, frames_dir, count=3, monkeypatch=monkeypatch)

    result = executors.execute_run(run.job_id, engine=engine, policy=FAST_POLICY)

    job = load_job(engine, run.job_id)
    assert (job.status, job.phase) == (JobStatus.FINISHED, RunPhase.FINISHED), job.messages
    assert (job.n_inputs, job.n_succeeded, job.n_failed, job.n_not_run) == (3, 3, 0, 0)
    assert result["status"] == "Finished"
    results_path = os.path.join(run.output_path, "output.h5")
    with Session(engine) as session:
        stored = session.get(db_schema.IndexingRun, run.id)
        assert stored.n_frames_indexed == 2  # the empty frame has no pattern
        assert stored.results_path == results_path  # set only after publication
    xml_path = os.path.join(run.output_path, "output.xml")
    assert sorted(os.listdir(run.output_path)) == [
        "inputs.jsonl",
        "output.h5",
        "output.xml",
        "request.json",
        "run.json",
    ]
    summary = validate_results_file(results_path, frame_ids=["frame_1", "frame_2", "frame_3"])
    assert (summary.n_frames, summary.n_patterns) == (3, 3)
    assert summary.n_peaks == 24 + 48 + 1
    with h5py.File(results_path) as source:
        assert [value.decode() if isinstance(value, bytes) else value for value in source["frames/frame_ids"][...]] == [
            "frame_1",
            "frame_2",
            "frame_3",
        ]
        assert source["run"].attrs["max_data"] == 200
        assert source["run"].attrs["max_peaks"] == 300
        assert bool(source["run"].attrs["cosmic_filter"]) is False
    steps = ET.parse(xml_path).getroot().findall("step")
    assert len(steps) == 3
    assert [step.find("detector/inputImage").text for step in steps] == [
        os.fspath(frames_dir / f"frame_{index}.h5") for index in (1, 2, 3)
    ]

    import json

    run_json = json.loads(Path(run.output_path, "run.json").read_text())
    assert run_json["artifacts"] == {"results": results_path, "xml": xml_path}
    assert run_json["counters"]["n_indexed"] == 2
    assert run_json["provenance"]["engine"].startswith("lauelab liblaue")
    assert run_json["provenance"]["lauelab_version"]
    assert run_json["provenance"]["peak_params"]["max_peaks"] == 300
    assert run_json["provenance"]["cosmic_filter"] == {"recorded": False, "applied": False}
    assert run_json["provenance"]["results_summary"]["n_frames"] == 3
    assert run_json["warnings"] == []
    assert "3 frames, 3 patterns" in job.messages


def test_missing_and_corrupt_inputs_are_recorded_and_the_run_is_incomplete(engine, tmp_path, monkeypatch):
    frames_dir = _frames_dir(tmp_path)
    (frames_dir / "frame_2.h5").write_bytes(b"not an hdf5 file")
    run = _indexing_run(engine, tmp_path, frames_dir, count=3, monkeypatch=monkeypatch)
    os.unlink(frames_dir / "frame_3.h5")  # disappears after the manifest froze it

    executors.execute_run(run.job_id, engine=engine, policy=FAST_POLICY)

    job = load_job(engine, run.job_id)
    assert job.status == JobStatus.FAILED
    assert (job.n_succeeded, job.n_failed, job.n_not_run) == (1, 2, 0)
    assert job.messages.startswith("Incomplete: 1 succeeded, 2 failed")
    records, _ = read_failure_report(job.failure_report_path)
    assert [(r.index, r.input_id, r.category) for r in records] == [(1, "frame_2", "input"), (2, "frame_3", "input")]
    # Structurally valid partial science is published; the run is incomplete, not corrupt.
    summary = validate_results_file(os.path.join(run.output_path, "output.h5"), frame_ids=["frame_1"])
    assert summary.n_frames == 1
    assert len(ET.parse(os.path.join(run.output_path, "output.xml")).getroot().findall("step")) == 1


def test_all_inputs_failing_publishes_no_results_file(engine, tmp_path, monkeypatch):
    frames_dir = _frames_dir(tmp_path, names=FRAMES[:1])
    run = _indexing_run(engine, tmp_path, frames_dir, count=1, monkeypatch=monkeypatch)
    (frames_dir / "frame_1.h5").write_bytes(b"garbage")

    executors.execute_run(run.job_id, engine=engine, policy=FAST_POLICY)

    job = load_job(engine, run.job_id)
    assert job.messages.startswith("All inputs failed")
    assert sorted(os.listdir(run.output_path)) == ["failures.jsonl", "inputs.jsonl", "request.json", "run.json"]


def test_cooperative_stop_keeps_the_frames_that_finished(engine, tmp_path, monkeypatch):
    frames_dir = _frames_dir(tmp_path, names=FRAMES * 3)
    run = _indexing_run(engine, tmp_path, frames_dir, count=9, monkeypatch=monkeypatch)
    original = lauego.compute_lauego_indexing

    def stopping_compute(request, entries, hooks):
        class StopAfterFirst:
            def __init__(self, inner):
                self.inner = inner
                self.reports = 0

            def should_stop(self):
                return self.reports >= 1

            def report_progress(self, **kwargs):
                self.reports += 1
                self.inner.report_progress(**kwargs)

            def record_failure(self, record):
                self.inner.record_failure(record)

            def log(self, message):
                self.inner.log(message)

        return original(request, entries, StopAfterFirst(hooks))

    monkeypatch.setitem(lauego.__dict__, "compute_lauego_indexing", stopping_compute)
    from laue_portal.processing.compute import contract

    monkeypatch.setitem(contract._REGISTRY, lauego.LAUEGO_KIND, stopping_compute)

    executors.execute_run(run.job_id, engine=engine, policy=FAST_POLICY)

    job = load_job(engine, run.job_id)
    assert (job.status, job.phase) == (JobStatus.CANCELLED, RunPhase.CANCELLED), job.messages
    assert job.n_succeeded >= 1
    assert job.n_succeeded + job.n_not_run == 9
    records, _ = read_failure_report(job.failure_report_path)
    assert len(records) == job.n_not_run
    assert {record.category for record in records} == {"cancelled"}
    summary = validate_results_file(os.path.join(run.output_path, "output.h5"))
    assert summary.n_frames == job.n_succeeded


def test_results_writer_failure_stops_the_run_without_publishing(engine, tmp_path, monkeypatch):
    frames_dir = _frames_dir(tmp_path)
    run = _indexing_run(engine, tmp_path, frames_dir, count=3, monkeypatch=monkeypatch)
    original_append = ResultsWriter.append

    def failing_append(self, result, frame_id=None):
        if self.count == 1:
            raise OSError("disk full")
        return original_append(self, result, frame_id=frame_id)

    monkeypatch.setattr(ResultsWriter, "append", failing_append)

    with pytest.raises(OSError, match="disk full"):
        executors.execute_run(run.job_id, engine=engine, policy=FAST_POLICY)

    job = load_job(engine, run.job_id)
    assert job.status == JobStatus.FAILED
    assert job.messages.startswith("Run failed: OSError: disk full")
    listing = sorted(os.listdir(run.output_path))
    assert "output.h5" not in listing
    assert "output.h5.partial" in listing  # kept for diagnosis, never advertised as ready
    assert "output.xml" not in listing


def test_existing_results_file_is_never_overwritten(engine, tmp_path, monkeypatch):
    frames_dir = _frames_dir(tmp_path, names=FRAMES[:1])
    run = _indexing_run(engine, tmp_path, frames_dir, count=1, monkeypatch=monkeypatch)
    Path(run.output_path, "output.h5").write_text("previous run")

    with pytest.raises(FileExistsError, match="never overwrites"):
        executors.execute_run(run.job_id, engine=engine, policy=FAST_POLICY)
    assert Path(run.output_path, "output.h5").read_text() == "previous run"
    assert load_job(engine, run.job_id).status == JobStatus.FAILED


def test_xml_destination_collision_is_a_warning_not_a_failure(engine, tmp_path, monkeypatch):
    frames_dir = _frames_dir(tmp_path, names=FRAMES[:1])
    shared_xml = tmp_path / "shared" / "index.xml"
    shared_xml.parent.mkdir()
    shared_xml.write_text("<AllSteps/>")
    run = _indexing_run(engine, tmp_path, frames_dir, count=1, monkeypatch=monkeypatch, output_xml=str(shared_xml))

    executors.execute_run(run.job_id, engine=engine, policy=FAST_POLICY)

    job = load_job(engine, run.job_id)
    assert job.status == JobStatus.FINISHED, job.messages
    assert shared_xml.read_text() == "<AllSteps/>"
    import json

    run_json = json.loads(Path(run.output_path, "run.json").read_text())
    assert run_json["artifacts"] == {"results": os.path.join(run.output_path, "output.h5")}
    assert any("XML not published" in warning for warning in run_json["warnings"])
    assert (tmp_path / "shared" / "index.xml.partial").exists()


def test_depth_override_reaches_every_frame(engine, tmp_path, monkeypatch):
    frames_dir = _frames_dir(tmp_path, names=FRAMES[:1])
    run = _indexing_run(engine, tmp_path, frames_dir, count=1, monkeypatch=monkeypatch, depth="-12.5")
    executors.execute_run(run.job_id, engine=engine, policy=FAST_POLICY)
    assert load_job(engine, run.job_id).status == JobStatus.FINISHED
    step = ET.parse(os.path.join(run.output_path, "output.xml")).getroot().find("step")
    assert float(step.find("depth").text) == -12.5
    with h5py.File(os.path.join(run.output_path, "output.h5")) as source:
        assert float(source["frames/depths"][0]) == -12.5


@pytest.mark.parametrize(("detected", "indexed"), [(7, 40), (None, 200)])
def test_saved_request_retains_distinct_spot_limits_and_disables_filter(engine, tmp_path, monkeypatch, detected, indexed):
    import json

    frames_dir = _frames_dir(tmp_path, FRAMES[:1])
    run = _indexing_run(
        engine, tmp_path, frames_dir, count=1, monkeypatch=monkeypatch,
        max_number=detected, max_peaks=indexed, cosmic_filter=True,
    )
    saved = json.loads(Path(run.output_path, "request.json").read_text())["request"]
    assert (saved["max_number"], saved["max_peaks"], saved["cosmic_filter"]) == (detected, indexed, False)
    with Session(engine) as session:
        params = session.get(db_schema.IndexingRun, run.id).lauego_parameters
        assert (params.max_number, params.max_peaks, params.cosmic_filter) == (detected, indexed, False)
    settings = lauego.settings_from_request(saved)
    assert settings.peak_params.max_peaks == detected
    assert settings.index_params.max_data == indexed
    assert settings.cosmic_filter is False
