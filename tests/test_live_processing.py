"""Real native live processing, arrivals, publication and conservative recovery."""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import h5py
import numpy as np
import pytest
from lauelab.indexing import validate_results_file
from lauelab.reconstruct import ScanReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from laue_portal.database import db_schema as db
from laue_portal.processing.live import execute_live
from laue_portal.workflows import execution
from laue_portal.workflows.live import create_live, get_live, notify_ready, request_action, session_status, writer_lock
from tests.conftest import create_test_metadata
from tests.run_support import make_engine
from tests.test_workflow_services import _indexing_request, _wire_request
from tests.wire_support import GEOMETRY, OPTIONS, write_wire_scan


def thread_executor(*, max_workers, **kwargs):
    return ThreadPoolExecutor(max_workers=max_workers)


@pytest.fixture
def setup(tmp_path, monkeypatch):
    engine = make_engine(tmp_path, monkeypatch)
    with Session(engine) as session, session.begin():
        session.add(create_test_metadata())
    raw = tmp_path / "raw"
    raw.mkdir()
    r = _wire_request(raw, tmp_path / "rec_%d", geometry_file=str(GEOMETRY), wire_edges="leading", **OPTIONS)
    i = _indexing_request(
        raw,
        tmp_path / "index_%d",
        geometry_file=str(GEOMETRY),
        crystal_file=str(GEOMETRY.parent / "Ni.xml"),
        depth_range="0-1",
        depth=None,
        box_size=3,
        min_separation=2,
    )

    def create(indexing=False, points=None, reconstruction=True):
        return create_live(
            replace(r, scan_points=points) if reconstruction else None,
            replace(
                i, scan_points=None, filename_prefixes=["wire_%d.h5"], depth_range="0-1" if reconstruction else None
            )
            if indexing
            else None,
            engine=engine,
            control_root=tmp_path / "control",
            policy={
                "threads_per_worker": 1,
                "reconstruction_workers": 2,
                "indexing_workers": 1,
                "poll_seconds": 0.01,
                "publish_seconds": 0.01,
            },
        )

    return engine, raw, create


def write_raw_frame(path):
    write_wire_scan(path)
    with h5py.File(path, "r+") as output:
        frame = output["entry1/data/data"][0]
        del output["entry1/data/data"]
        output.create_dataset("entry1/data/data", data=frame)
    return path


def test_raw_indexing_only_publishes_growing_preview_and_drains_stop(setup):
    engine, raw, create = setup
    live = create(indexing=True, reconstruction=False)
    assert live.reconstruction_id is None and live.reconstruction_job_id is None
    with Session(engine) as session:
        assert session.get(db.IndexingRun, live.indexing_id).reconstruction_id is None
        assert session.get(db.Job, live.indexing_job_id).computer_name == "worker-b"
    pool, future = start(engine, live)
    try:
        for point in (2, 1):
            path = write_raw_frame(raw / f"wire_{point}.h5")
            notify_ready(live.id, path, complete=True, engine=engine)
            notify_ready(live.id, path, complete=True, engine=engine)

            def preview_ready(expected=1 if point == 2 else 2):
                if future.done():
                    future.result()
                path = Path(live.recipe["indexing_directory"]) / "output.h5"
                return path.exists() and validate_results_file(path).n_frames == expected

            wait_for(preview_ready)
        assert not future.done()
        request_action(live.id, "stop", engine=engine)
        future.result(timeout=20)
        status = session_status(live.id, engine=engine)
        assert (status["state"], status["arrived"], status["reconstructed"], status["indexed_points"]) == (
            "finished",
            2,
            0,
            2,
        )
        assert status["pending"] == status["failures"] == 0
        with Session(engine) as session:
            job = session.get(db.Job, live.indexing_job_id)
            assert (job.n_inputs, job.n_succeeded, job.n_failed) == (2, 2, 0)
            assert session.get(db.LiveCheckpoint, live.id) is None
            run = session.get(db.IndexingRun, live.indexing_id)
            assert validate_results_file(run.results_path).frame_ids == ("wire_2", "wire_1")
            assert run.lauego_parameters.scan_points in {"1,2", "1-2"}
        assert (Path(live.recipe["indexing_directory"]) / live.recipe["indexing"]["output_xml"]).is_file()
    finally:
        if not future.done():
            request_action(live.id, "stop", engine=engine)
        pool.shutdown(wait=True)


def test_raw_bad_input_is_counted_and_other_frames_finish(setup):
    engine, raw, create = setup
    live = create(indexing=True, reconstruction=False)
    bad = raw / "wire_1.h5"
    bad.write_bytes(b"not hdf5")
    for path in (bad, write_raw_frame(raw / "wire_2.h5")):
        notify_ready(live.id, path, complete=True, engine=engine)
    request_action(live.id, "stop", engine=engine)
    execute_live(live.id, engine=engine, executor_factory=thread_executor)
    status = session_status(live.id, engine=engine)
    assert (status["state"], status["indexing_succeeded"], status["indexing_failed"]) == ("failed", 1, 1)
    assert validate_results_file(live.recipe["indexing_directory"] + "/output.h5").n_frames == 1


def test_raw_recovery_imports_receipts_without_repeating_frames(setup):
    engine, raw, create = setup
    live = create(indexing=True, reconstruction=False)
    notify_ready(live.id, write_raw_frame(raw / "wire_1.h5"), complete=True, engine=engine)
    execute_live(
        live.id,
        engine=engine,
        executor_factory=thread_executor,
        should_pause=lambda: session_status(live.id, engine=engine)["indexed_points"] == 1,
    )
    assert get_live(live.id, engine=engine).state == "recovery"
    with Session(engine) as session, session.begin():
        point = session.scalar(select(db.LivePoint).where(db.LivePoint.session_id == live.id))
        shard = Path(point.indexing_receipt["outcome"]["artifacts"]["results"])
        original = shard.read_bytes()
        point.indexing_state, point.indexing_receipt = "writing", None
        session.get(db.LiveSession, live.id).state = "queued"
        job = session.get(db.Job, live.indexing_job_id)
        job.status, job.phase, job.n_not_run = 0, "queued", 0
    notify_ready(live.id, write_raw_frame(raw / "wire_2.h5"), complete=True, engine=engine)
    request_action(live.id, "stop", engine=engine)
    execute_live(live.id, engine=engine, executor_factory=thread_executor)
    status = session_status(live.id, engine=engine)
    assert (status["state"], status["indexing_succeeded"], status["pending"]) == ("finished", 2, 0)
    assert shard.read_bytes() == original
    assert validate_results_file(live.recipe["indexing_directory"] + "/output.h5").n_frames == 2


def wait_for(predicate, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("Live controller condition did not become true")


def start(engine, live, **kwargs):
    pool = ThreadPoolExecutor(max_workers=1)
    future = pool.submit(execute_live, live.id, engine=engine, executor_factory=thread_executor, **kwargs)
    return pool, future


def test_live_reserves_one_slot_without_requiring_future_inputs(setup):
    engine, raw, create = setup
    live = create()
    assert get_live(live.id, engine=engine).checkpoint is None
    assert not list(raw.iterdir())
    with pytest.raises(ValueError, match="Another live"):
        create()
    request_action(live.id, "stop", engine=engine)
    execute_live(live.id, engine=engine, executor_factory=thread_executor)
    assert get_live(live.id, engine=engine).state == "cancelled"
    assert create().id != live.id


def test_notification_is_explicit_idempotent_scoped_and_immutable(setup, tmp_path):
    engine, raw, create = setup
    live = create()
    path = write_wire_scan(raw / "wire_1.h5")
    with pytest.raises(ValueError, match="completed-stack"):
        notify_ready(live.id, path, engine=engine)
    identity = notify_ready(live.id, path, complete=True, engine=engine)
    assert notify_ready(live.id, path, complete=True, engine=engine) == identity
    with pytest.raises(ValueError, match="selected input folder"):
        notify_ready(live.id, write_wire_scan(tmp_path / "wire_2.h5"), complete=True, engine=engine)
    notify_ready(live.id, write_wire_scan(raw / "wire_10000.h5"), complete=True, engine=engine)
    with pytest.raises(ValueError, match="selected filename"):
        notify_ready(live.id, write_wire_scan(raw / "other_3.h5"), complete=True, engine=engine)
    with h5py.File(path, "r+") as source:
        source.attrs["changed"] = True
    with pytest.raises(ValueError, match="changed"):
        notify_ready(live.id, path, complete=True, engine=engine)


def test_delayed_burst_native_pipeline_publishes_partial_and_final_outputs(setup):
    engine, raw, create = setup
    live = create(indexing=True)
    pool, future = start(engine, live)
    try:
        wait_for(lambda: session_status(live.id, engine=engine)["state"] == "waiting")
        second = write_wire_scan(raw / "wire_2.h5")
        notify_ready(live.id, second, complete=True, engine=engine)
        wait_for(lambda: session_status(live.id, engine=engine)["indexed_points"] == 1)

        def preview_ready():
            with Session(engine) as session:
                return session.get(db.IndexingRun, live.indexing_id).results_path is not None

        wait_for(preview_ready)
        assert not future.done()  # An empty queue is not acquisition completion.
        rpath = live.recipe["reconstruction_directory"] + "/reconstruction/scan.h5"
        with ScanReader(rpath) as reader:
            assert reader.point_ids == ("wire_2",)
        with Session(engine) as session:
            indexing = session.get(db.IndexingRun, live.indexing_id)
            assert validate_results_file(indexing.results_path).n_frames == 2
        first = write_wire_scan(raw / "wire_1.h5")
        notify_ready(live.id, first, complete=True, engine=engine)
        notify_ready(live.id, first, complete=True, engine=engine)
        request_action(live.id, "stop", engine=engine)
        future.result(timeout=20)
        status = session_status(live.id, engine=engine)
        assert (status["state"], status["arrived"], status["reconstructed"], status["indexed_points"]) == (
            "finished",
            2,
            2,
            2,
        )
        assert status["revision"] > 1
        with ScanReader(rpath) as reader:
            assert reader.point_ids == ("wire_2", "wire_1")
            assert reader.run_status == "finished"
        with Session(engine) as session:
            for identity in (live.reconstruction_job_id, live.indexing_job_id):
                assert session.get(db.Job, identity).status == execution.JobStatus.FINISHED
            indexing = session.get(db.IndexingRun, live.indexing_id)
            assert validate_results_file(indexing.results_path).n_frames == 4
            assert indexing.n_frames_indexed == 0  # Empty patterns still count as processed frames.
    finally:
        if not future.done():
            request_action(live.id, "stop", engine=engine)
        pool.shutdown(wait=True)


def test_shutdown_and_receipt_replay_do_not_repeat_completed_points(setup):
    engine, raw, create = setup
    live = create()
    notify_ready(live.id, write_wire_scan(raw / "wire_1.h5"), complete=True, engine=engine)
    execute_live(
        live.id,
        engine=engine,
        executor_factory=thread_executor,
        should_pause=lambda: session_status(live.id, engine=engine)["reconstructed"] == 1,
    )
    saved = get_live(live.id, engine=engine)
    assert saved.state == "recovery"
    with Session(engine) as session:
        point = session.scalar(select(db.LivePoint).where(db.LivePoint.session_id == live.id))
    output = point.task["output"]
    before = open(output, "rb").read()
    # Simulate a durable child receipt landing before its DB transaction.
    with Session(engine) as session, session.begin():
        row = session.get(db.LivePoint, point.id)
        row.reconstruction_receipt, row.reconstruction_state = None, "writing"
        saved = session.get(db.LiveSession, live.id)
        saved.state = "queued"
        checkpoint = session.get(db.LiveCheckpoint, live.id)
        state = json.loads(json.dumps(checkpoint.state))
        for outcome in state["points"]:
            outcome["outcome"] = {
                "index": 0,
                "point_id": point.point_id,
                "status": "pending",
                "error": None,
                "seconds": 0.0,
                "output": None,
            }
        # JSON is immutable at the ORM boundary: assign a detached mapping.
        checkpoint.state = state
        job = session.get(db.Job, live.reconstruction_job_id)
        job.status, job.phase, job.n_not_run = 0, "queued", 0
    notify_ready(live.id, write_wire_scan(raw / "wire_2.h5"), complete=True, engine=engine)
    request_action(live.id, "stop", engine=engine)
    execute_live(live.id, engine=engine, executor_factory=thread_executor)
    assert get_live(live.id, engine=engine).state == "finished"
    assert open(output, "rb").read() == before


def test_missing_receipt_orphan_is_preserved_and_requires_reconciliation(setup):
    engine, raw, create = setup
    live = create()
    notify_ready(live.id, write_wire_scan(raw / "wire_1.h5"), complete=True, engine=engine)
    with Session(engine) as session, session.begin():
        point = session.scalar(select(db.LivePoint).where(db.LivePoint.session_id == live.id))
        point.reconstruction_state = "writing"
    with pytest.raises(ValueError, match="no receipt"):
        execute_live(live.id, engine=engine, executor_factory=thread_executor)
    assert get_live(live.id, engine=engine).state == "recovery"


def test_stop_finishes_received_points_and_rejects_late_new_arrivals(setup):
    engine, raw, create = setup
    live = create()
    notify_ready(live.id, write_wire_scan(raw / "wire_1.h5"), complete=True, engine=engine)
    request_action(live.id, "stop", engine=engine)
    with pytest.raises(ValueError, match="sealed"):
        notify_ready(live.id, write_wire_scan(raw / "wire_2.h5"), complete=True, engine=engine)
    execute_live(live.id, engine=engine, executor_factory=thread_executor)
    assert get_live(live.id, engine=engine).state == "finished"
    assert get_live(live.id, engine=engine).error is None


def test_stop_drains_sparse_arrivals_and_records_actual_metadata(setup):
    engine, raw, create = setup
    live = create(indexing=True)
    assert "expected_points" not in live.recipe
    with Session(engine) as session:
        assert session.get(db.Job, live.reconstruction_job_id).n_inputs == 0
        assert session.get(db.WireReconstructionParameters, live.reconstruction_id).scan_points == ""
    for number in (2, 10000):
        notify_ready(live.id, write_wire_scan(raw / f"wire_{number}.h5"), complete=True, engine=engine)
    # Stop before any dispatch must still drain reconstruction AND indexing.
    request_action(live.id, "stop", engine=engine)
    execute_live(live.id, engine=engine, executor_factory=thread_executor)
    status = session_status(live.id, engine=engine)
    assert status["state"] == "finished" and status["error"] is None
    assert status["arrived"] == status["reconstructed"] == status["indexed_points"] == 2
    assert status["pending"] == status["failures"] == 0
    assert "expected" not in status
    with Session(engine) as session:
        for model, identity in (
            (db.WireReconstructionParameters, live.reconstruction_id),
            (db.LaueGoIndexingParameters, live.indexing_id),
        ):
            parameters = session.get(model, identity)
            assert parameters.scan_points == "2,10000" and parameters.scan_points_len == 2
        assert session.get(db.Job, live.reconstruction_job_id).n_inputs == 2
        assert session.get(db.Job, live.indexing_job_id).n_inputs == 4
        indexing = session.get(db.IndexingRun, live.indexing_id)
        assert validate_results_file(indexing.results_path).n_frames == 4
    with ScanReader(live.recipe["reconstruction_directory"] + "/reconstruction/scan.h5") as reader:
        assert reader.point_ids == ("wire_2", "wire_10000")
        assert reader.run_status == "finished"


def test_writer_lock_cannot_be_taken_from_a_living_controller(setup):
    engine, raw, create = setup
    live = create()
    with writer_lock(live.control_directory):
        with pytest.raises(ValueError, match="still running"):
            execute_live(live.id, engine=engine, executor_factory=thread_executor)
        assert get_live(live.id, engine=engine).state == "queued"


def test_stop_during_recovery_releases_reservation_without_deleting_outputs(setup):
    engine, raw, create = setup
    live = create()
    notify_ready(live.id, write_wire_scan(raw / "wire_1.h5"), complete=True, engine=engine)
    execute_live(
        live.id,
        engine=engine,
        executor_factory=thread_executor,
        should_pause=lambda: session_status(live.id, engine=engine)["reconstructed"] == 1,
    )
    catalog = live.recipe["reconstruction_directory"] + "/reconstruction/scan.h5"
    before = open(catalog, "rb").read()
    request_action(live.id, "stop", engine=engine)
    assert get_live(live.id, engine=engine).state == "cancelled"
    assert open(catalog, "rb").read() == before
    assert create().id != live.id


def test_live_publication_matches_batch_reconstruction_pixels(setup, tmp_path):
    from lauelab.reconstruct import reconstruct_scan

    engine, raw, create = setup
    source = write_wire_scan(raw / "wire_1.h5")
    live = create(points="1")
    notify_ready(live.id, source, complete=True, engine=engine)
    request_action(live.id, "stop", engine=engine)
    execute_live(live.id, engine=engine, executor_factory=thread_executor)
    batch = reconstruct_scan(
        [source],
        tmp_path / "batch",
        geometry=GEOMETRY,
        detector=0,
        depth_range=(-25, 25),
        resolution=5,
        memory_limit_mb=256,
        threads_per_worker=1,
    )
    with (
        ScanReader(batch.path) as expected,
        ScanReader(live.recipe["reconstruction_directory"] + "/reconstruction/scan.h5") as actual,
    ):
        with expected.point("wire_1") as old, actual.point("wire_1") as new:
            np.testing.assert_array_equal(old.depth_um, new.depth_um)
            for depth in range(new.shape[0]):
                np.testing.assert_array_equal(old.frame(depth), new.frame(depth))


def test_parameter_cards_have_isolated_ids_and_reuse_existing_fields():
    from laue_portal.components.live_form import INDEX_FIELDS, WIRE_FIELDS, _walk, parameter_cards
    from laue_portal.components.request_defaults import create_default_peakindex, create_default_wirerecon

    identities = []
    for stage, mapping, defaults in (
        ("r", WIRE_FIELDS, create_default_wirerecon()),
        ("i", INDEX_FIELDS, create_default_peakindex()),
    ):
        cards = parameter_cards(stage, vars(defaults))
        ids = [component.id for card in cards for component in _walk(card) if getattr(component, "id", None)]
        assert {f"live-{stage}-{name}" for name in mapping} <= set(ids)
        identities.extend(ids)
    assert len(identities) == len(set(identities))


def test_queue_submission_is_deduplicated_and_resume_is_explicit(setup, monkeypatch):
    from laue_portal.processing import live_queue
    from tests.test_run_queue import FakeQueue

    engine, raw, create = setup
    live = create()
    queue = FakeQueue()
    monkeypatch.setattr(live_queue, "job_queue", queue)
    identity = live_queue.enqueue_live(live.id, engine=engine)
    assert identity.startswith(f"live_{live.id}_")
    with pytest.raises(ValueError, match="already submitted"):
        live_queue.enqueue_live(live.id, engine=engine)
    with pytest.raises(ValueError, match="Only an interrupted"):
        live_queue.enqueue_live(live.id, engine=engine, resume=True)


def test_unreadable_arrival_fails_that_point_and_keeps_other_results(setup):
    engine, raw, create = setup
    live = create()
    invalid = raw / "wire_1.h5"
    invalid.write_text("not HDF5")
    notify_ready(live.id, invalid, complete=True, engine=engine)
    notify_ready(live.id, write_wire_scan(raw / "wire_2.h5"), complete=True, engine=engine)
    request_action(live.id, "stop", engine=engine)
    execute_live(live.id, engine=engine, executor_factory=thread_executor)
    status = session_status(live.id, engine=engine)
    assert status["state"] == "failed" and status["reconstructed"] == 1 and status["failures"] == 1


def test_immediate_queue_dispatch_does_not_race_the_writer_lock(setup, monkeypatch):
    from laue_portal.processing import live_queue

    engine, raw, create = setup
    live = create()
    request_action(live.id, "stop", engine=engine)

    class ImmediateQueue:
        def enqueue(self, function, identity, **kwargs):
            function(identity, engine=engine, executor_factory=thread_executor)

    monkeypatch.setattr(live_queue, "job_queue", ImmediateQueue())
    live_queue.enqueue_live(live.id, engine=engine)
    assert get_live(live.id, engine=engine).state == "cancelled"


def test_missing_queue_entry_becomes_recoverable_without_releasing_reservation(setup):
    from laue_portal.processing.live_queue import reconcile_live

    engine, raw, create = setup
    live = create()
    reconcile_live(engine, queue_entry_exists=lambda _: False)
    assert get_live(live.id, engine=engine).state == "recovery"
    with pytest.raises(ValueError, match="Another live"):
        create()
