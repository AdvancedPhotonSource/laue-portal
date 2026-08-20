import datetime
import importlib
import json
from types import SimpleNamespace

import pytest

from laue_portal.database import db_schema, session_utils
from laue_portal.processing.queue import batch, controls, core, enqueue, executors, lifecycle


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.published = []
        self.deleted = []

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    def get(self, key):
        return self.values.get(key)

    def incrby(self, key, amount):
        self.values[key] = int(self.values.get(key, 0)) + amount
        return self.values[key]

    def delete(self, *keys):
        self.deleted.extend(keys)
        for key in keys:
            self.values.pop(key, None)

    def publish(self, channel, message):
        self.published.append((channel, message))


class FakeQueue:
    def __init__(self):
        self.enqueued = []

    def enqueue(self, func, db_job_id, *args, **kwargs):
        rq_job_id = kwargs["job_id"]
        self.enqueued.append({"func": func, "db_job_id": db_job_id, "args": args, "kwargs": kwargs})
        return SimpleNamespace(id=rq_job_id)


class FakeRQJob:
    def __init__(self, is_queued=False, is_started=False):
        self.is_queued = is_queued
        self.is_started = is_started
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


@pytest.fixture
def queue_db(tmp_path, monkeypatch):
    db_file = tmp_path / "queue.db"
    monkeypatch.setattr("laue_portal.config.db_file", str(db_file))
    session_utils.init_db()
    yield session_utils.get_engine()
    session_utils.get_engine().dispose()


def add_job_with_subjobs(session, job_id=1, subjob_count=0, status=None, input_paths=None, output_path=None):
    if status is None:
        status = core.STATUS_REVERSE_MAPPING["Queued"]
    session.add(
        db_schema.Job(
            job_id=job_id,
            computer_name="TEST",
            status=status,
            priority=1,
            submit_time=datetime.datetime(2026, 1, 1),
        )
    )
    for i in range(subjob_count):
        session.add(
            db_schema.SubJob(
                subjob_id=job_id * 100 + i,
                job_id=job_id,
                computer_name="TEST",
                status=core.STATUS_REVERSE_MAPPING["Queued"],
                priority=1,
                input_path=input_paths[i] if input_paths else None,
                output_path=output_path,
            )
        )
    session.commit()


def add_reconstruction_workflow(session, tmp_path, *, run_id=51, job_id=1, count=2, method="wire"):
    output_dir = tmp_path / f"reconstruction_{run_id}"
    geometry_file = tmp_path / f"wire_{run_id}.xml"
    geometry_file.write_text("geometry", encoding="utf-8")
    input_paths = [str(tmp_path / f"wire_input_{i}.h5") for i in range(count)]
    add_job_with_subjobs(
        session,
        job_id=job_id,
        subjob_count=count,
        input_paths=input_paths,
        output_path=str(output_dir / "wire_"),
    )
    run = db_schema.ReconstructionRun(
        id=run_id,
        job_id=job_id,
        method=method,
        input_path=str(tmp_path),
        output_path=str(output_dir),
        created_at=datetime.datetime(2026, 1, 1),
    )
    if method == "wire":
        run.wire_parameters = db_schema.WireReconstructionParameters(
            filename_prefixes=["wire_%d.h5"],
            geometry_file=str(geometry_file),
            percent_brightest=12.5,
            wire_edges="0 1",
            depth_start=-5.0,
            depth_end=5.0,
            depth_resolution=0.25,
            num_threads=4,
            memory_limit_mb=512,
            scan_points="0-1",
            scan_points_len=count,
            verbose=2,
        )
    session.add(run)
    session.commit()
    return run_id, job_id, [job_id * 100 + i for i in range(count)], output_dir


def add_indexing_workflow(session, tmp_path, *, run_id=61, job_id=2, count=3, method="lauego"):
    output_dir = tmp_path / f"indexing_{run_id}"
    geometry_file = tmp_path / f"geo_{run_id}.xml"
    crystal_file = tmp_path / f"crystal_{run_id}.xtal"
    geometry_file.write_text("geometry", encoding="utf-8")
    crystal_file.write_text("crystal", encoding="utf-8")
    input_paths = [str(tmp_path / f"index_input_{i}.tif") for i in range(count)]
    add_job_with_subjobs(
        session,
        job_id=job_id,
        subjob_count=count,
        input_paths=input_paths,
        output_path=str(output_dir),
    )
    run = db_schema.IndexingRun(
        id=run_id,
        job_id=job_id,
        method=method,
        input_path=str(tmp_path),
        output_path=str(output_dir),
        created_at=datetime.datetime(2026, 1, 1),
    )
    if method == "lauego":
        run.lauego_parameters = db_schema.LaueGoIndexingParameters(
            filename_prefixes=["index_%d.tif"],
            threshold=250,
            threshold_ratio=10,
            max_rfactor=0.5,
            box_size=18,
            max_number=100,
            min_separation=40,
            peak_shape="L",
            scan_points="0-2",
            scan_points_len=count,
            depth_range=None,
            depth_range_len=None,
            detector_crop_x1=0,
            detector_crop_x2=2048,
            detector_crop_y1=0,
            detector_crop_y2=2048,
            min_size=1,
            max_peaks=50,
            smooth=False,
            mask_file="mask.tif",
            index_kev_max_calc=17.2,
            index_kev_max_test=30.0,
            index_angle_tolerance=0.1,
            index_h=1,
            index_k=1,
            index_l=1,
            index_cone=72.0,
            energy_unit="keV",
            exposure_unit="s",
            cosmic_filter=False,
            reciprocal_lattice_unit="1/nm",
            lattice_parameters_unit="nm",
            output_xml="merged.xml",
            geometry_file=str(geometry_file),
            crystal_file=str(crystal_file),
            depth=None,
            beamline="34-ID-E",
        )
    session.add(run)
    session.commit()
    return run_id, job_id, [job_id * 100 + i for i in range(count)], output_dir, geometry_file, crystal_file


def test_queue_modules_are_importable_and_redis_utils_is_removed():
    module_names = [
        "laue_portal.processing.queue.core",
        "laue_portal.processing.queue.enqueue",
        "laue_portal.processing.queue.batch",
        "laue_portal.processing.queue.executors",
        "laue_portal.processing.queue.controls",
        "laue_portal.processing.queue.inspection",
        "laue_portal.processing.queue.lifecycle",
        "laue_portal.processing.xml_merge",
    ]

    for module_name in module_names:
        assert importlib.import_module(module_name)

    assert hasattr(enqueue, "enqueue_reconstruction")
    assert hasattr(enqueue, "enqueue_indexing")
    assert hasattr(batch, "notify_subjobs_completed")
    assert hasattr(executors, "execute_reconstruction_subjob")
    assert hasattr(executors, "execute_indexing_chunk")
    assert hasattr(controls, "cancel_batch_job")
    assert hasattr(lifecycle, "execute_with_status_updates")

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("laue_portal.processing.redis_utils")


def test_enqueue_job_supports_custom_rq_id_and_strips_queue_kwargs(monkeypatch):
    fake_queue = FakeQueue()
    monkeypatch.setattr(enqueue, "job_queue", fake_queue)

    def worker(job_id, worker_option=None):
        return job_id, worker_option

    rq_job_id = enqueue.enqueue_job(
        7,
        "demo",
        worker,
        db_schema.Job,
        worker_option="kept",
        timeout=12,
        rq_job_id="custom-demo-7",
    )

    assert rq_job_id == "custom-demo-7"
    assert len(fake_queue.enqueued) == 1
    queued_kwargs = fake_queue.enqueued[0]["kwargs"]
    assert queued_kwargs["job_id"] == "custom-demo-7"
    assert queued_kwargs["job_timeout"] == 12
    assert queued_kwargs["worker_option"] == "kept"
    assert "timeout" not in queued_kwargs
    assert "rq_job_id" not in queued_kwargs


def test_enqueue_reconstruction_uses_only_job_and_subjob_identifiers(queue_db, monkeypatch, tmp_path):
    fake_queue = FakeQueue()
    fake_redis = FakeRedis()
    monkeypatch.setattr(enqueue, "job_queue", fake_queue)
    monkeypatch.setattr(batch, "redis_conn", fake_redis)

    with session_utils.get_session() as session:
        run_id, job_id, subjob_ids, output_dir = add_reconstruction_workflow(session, tmp_path)

    result = enqueue.enqueue_reconstruction(run_id)

    assert result == f"batch_{job_id}"
    assert output_dir.is_dir()
    assert [queued["db_job_id"] for queued in fake_queue.enqueued] == [job_id, job_id]
    assert [queued["args"] for queued in fake_queue.enqueued] == [(subjob_ids[0],), (subjob_ids[1],)]
    assert all(queued["func"] is executors.execute_reconstruction_subjob for queued in fake_queue.enqueued)
    assert all(
        set(queued["kwargs"])
        == {"job_id", "meta", "at_front", "depends_on", "job_timeout", "result_ttl", "failure_ttl"}
        for queued in fake_queue.enqueued
    )


def test_enqueue_indexing_preserves_chunks_with_identifier_only_payloads(queue_db, monkeypatch, tmp_path):
    fake_queue = FakeQueue()
    fake_redis = FakeRedis()
    monkeypatch.setattr(enqueue, "job_queue", fake_queue)
    monkeypatch.setattr(batch, "redis_conn", fake_redis)

    with session_utils.get_session() as session:
        run_id, job_id, subjob_ids, output_dir, geometry_file, crystal_file = add_indexing_workflow(
            session, tmp_path, count=10
        )

    result = enqueue.enqueue_indexing(run_id, queue_batch_size=3)

    assert result == f"batch_{job_id}"
    assert [job["kwargs"]["job_id"] for job in fake_queue.enqueued] == [
        f"peakindexing_batch_{job_id}_0",
        f"peakindexing_batch_{job_id}_1",
        f"peakindexing_batch_{job_id}_2",
        f"peakindexing_batch_{job_id}_3",
    ]
    assert [len(job["args"][0]) for job in fake_queue.enqueued] == [3, 3, 3, 1]
    assert [job["args"][0] for job in fake_queue.enqueued] == [
        subjob_ids[0:3],
        subjob_ids[3:6],
        subjob_ids[6:9],
        subjob_ids[9:10],
    ]
    assert all(len(job["args"]) == 1 for job in fake_queue.enqueued)
    assert all(job["func"] is executors.execute_indexing_chunk for job in fake_queue.enqueued)

    meta = json.loads(fake_redis.values[batch._batch_meta_key(job_id)])
    assert meta["total"] == 10
    assert meta["queue_mode"] == "chunked"
    assert meta["rq_job_ids"] == [job["kwargs"]["job_id"] for job in fake_queue.enqueued]
    assert meta["coordinator_args"] == []
    assert meta["chunk_subjob_ids"] == [subjob_ids[0:3], subjob_ids[3:6], subjob_ids[6:9], subjob_ids[9:10]]
    assert (output_dir / "params" / geometry_file.name).read_text(encoding="utf-8") == "geometry"
    assert (output_dir / "params" / crystal_file.name).read_text(encoding="utf-8") == "crystal"


def test_enqueue_failure_marks_persisted_job_failed(queue_db, monkeypatch, tmp_path):
    class PartialQueue(FakeQueue):
        def enqueue(self, func, db_job_id, *args, **kwargs):
            if self.enqueued:
                raise RuntimeError("redis unavailable")
            return super().enqueue(func, db_job_id, *args, **kwargs)

    fake_redis = FakeRedis()
    partial_queue = PartialQueue()
    monkeypatch.setattr(batch, "redis_conn", fake_redis)
    monkeypatch.setattr(lifecycle, "redis_conn", fake_redis)
    monkeypatch.setattr(enqueue, "job_queue", partial_queue)

    with session_utils.get_session() as session:
        run_id, job_id, _, _ = add_reconstruction_workflow(session, tmp_path)

    with pytest.raises(RuntimeError, match="redis unavailable"):
        enqueue.enqueue_reconstruction(run_id)

    with session_utils.get_session() as session:
        job = session.get(db_schema.Job, job_id)
        assert job.status == core.STATUS_REVERSE_MAPPING["Failed"]
        assert job.finish_time is not None
        assert job.start_time is None
        assert job.messages == "Enqueue failed: redis unavailable"
    assert fake_redis.values == {}
    assert len(partial_queue.enqueued) == 1

    reconstruction_calls = []
    monkeypatch.setattr(executors, "wire_reconstruct", lambda *args, **kwargs: reconstruction_calls.append(args))
    queued = partial_queue.enqueued[0]
    assert queued["func"](queued["db_job_id"], *queued["args"]) is None
    assert reconstruction_calls == []


def test_redis_setup_failure_still_marks_job_failed(queue_db, monkeypatch, tmp_path):
    class OfflineRedis:
        def set(self, *args, **kwargs):
            raise RuntimeError("redis offline")

        def delete(self, *args, **kwargs):
            raise RuntimeError("redis offline")

        def publish(self, *args, **kwargs):
            raise RuntimeError("redis offline")

    monkeypatch.setattr(batch, "redis_conn", OfflineRedis())
    monkeypatch.setattr(lifecycle, "redis_conn", OfflineRedis())

    with session_utils.get_session() as session:
        run_id, job_id, _, _ = add_reconstruction_workflow(session, tmp_path)

    with pytest.raises(RuntimeError, match="redis offline"):
        enqueue.enqueue_reconstruction(run_id)

    with session_utils.get_session() as session:
        job = session.get(db_schema.Job, job_id)
        assert job.status == core.STATUS_REVERSE_MAPPING["Failed"]
        assert job.finish_time is not None
        assert job.messages == "Enqueue failed: redis offline"


def test_notify_subjobs_completed_batches_and_enqueues_coordinator_once(monkeypatch):
    fake_redis = FakeRedis()
    enqueued = []
    monkeypatch.setattr(batch, "redis_conn", fake_redis)
    monkeypatch.setattr(
        enqueue, "enqueue_job", lambda *args, **kwargs: enqueued.append((args, kwargs)) or "coordinator"
    )

    batch.setup_batch_counter(42, 3, "execute_batch_coordinator", job_type="demo")
    batch.notify_subjobs_completed(42, 2)
    assert enqueued == []

    batch.notify_subjobs_completed(42, 1)
    batch.notify_subjobs_completed(42, 1)

    assert len(enqueued) == 1
    assert enqueued[0][0][0:3] == (42, "batch_coordinator", batch.execute_batch_coordinator)
    assert fake_redis.values[batch._batch_coordinator_enqueued_key(42)] == 1
    assert batch._batch_counter_key(42) in fake_redis.deleted
    assert batch._batch_meta_key(42) in fake_redis.deleted


def test_execute_indexing_chunk_loads_paths_and_parameters(queue_db, monkeypatch, tmp_path):
    notifications = []
    calls = []

    def fake_index(input_image, **kwargs):
        calls.append((input_image, kwargs))
        if input_image == "bad.tif":
            raise RuntimeError("index failed")
        return SimpleNamespace(command_history=[f"index {input_image}"])

    monkeypatch.setattr(executors, "index", fake_index)
    monkeypatch.setattr(
        executors, "notify_subjobs_completed", lambda job_id, count: notifications.append((job_id, count))
    )
    monkeypatch.setattr(lifecycle, "redis_conn", FakeRedis())

    with session_utils.get_session() as session:
        _, job_id, subjob_ids, _, _, _ = add_indexing_workflow(session, tmp_path)
        subjobs = session.query(db_schema.SubJob).order_by(db_schema.SubJob.subjob_id).all()
        subjobs[0].input_path = "good_a.tif"
        subjobs[1].input_path = "bad.tif"
        subjobs[2].input_path = "good_b.tif"
        session.commit()

    result = executors.execute_indexing_chunk(job_id, subjob_ids)

    assert [input_image for input_image, _ in calls] == ["good_a.tif", "bad.tif", "good_b.tif"]
    assert all(kwargs["mask_file"] == "mask.tif" for _, kwargs in calls)
    assert all(kwargs["boxsize"] == 18 for _, kwargs in calls)
    assert all(kwargs["geo_file"].endswith("geo_61.xml") for _, kwargs in calls)
    assert len(result) == 3
    assert notifications == [(job_id, 3)]

    with session_utils.get_session() as session:
        job = session.get(db_schema.Job, job_id)
        subjobs = {subjob.subjob_id: subjob for subjob in session.query(db_schema.SubJob).all()}
        assert job.status == core.STATUS_REVERSE_MAPPING["Running"]
        assert subjobs[subjob_ids[0]].status == core.STATUS_REVERSE_MAPPING["Finished"]
        assert subjobs[subjob_ids[1]].status == core.STATUS_REVERSE_MAPPING["Failed"]
        assert subjobs[subjob_ids[2]].status == core.STATUS_REVERSE_MAPPING["Finished"]
        assert subjobs[subjob_ids[0]].messages is None
        assert subjobs[subjob_ids[0]].command is None
        assert "index failed" in subjobs[subjob_ids[1]].messages


def test_execute_indexing_chunk_marks_all_method_failures_without_raising(queue_db, monkeypatch, tmp_path):
    notifications = []

    calls = []
    monkeypatch.setattr(executors, "index", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(
        executors, "notify_subjobs_completed", lambda job_id, count: notifications.append((job_id, count))
    )
    monkeypatch.setattr(lifecycle, "redis_conn", FakeRedis())

    with session_utils.get_session() as session:
        _, job_id, subjob_ids, _, _, _ = add_indexing_workflow(
            session, tmp_path, run_id=62, job_id=3, count=2, method="laue_matching"
        )

    result = executors.execute_indexing_chunk(job_id, subjob_ids)

    assert [item["status"] for item in result] == [core.STATUS_REVERSE_MAPPING["Failed"]] * 2
    assert notifications == [(job_id, 2)]
    assert calls == []
    with session_utils.get_session() as session:
        subjobs = session.query(db_schema.SubJob).order_by(db_schema.SubJob.subjob_id).all()
        assert [subjob.status for subjob in subjobs] == [core.STATUS_REVERSE_MAPPING["Failed"]] * 2
        assert all("Laue-matching indexing is not available" in subjob.messages for subjob in subjobs)


def test_execute_indexing_chunk_skips_terminal_parent_and_notifies_counter(queue_db, monkeypatch, tmp_path):
    calls = []
    notifications = []
    monkeypatch.setattr(executors, "index", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(
        executors, "notify_subjobs_completed", lambda job_id, count: notifications.append((job_id, count))
    )

    with session_utils.get_session() as session:
        _, job_id, subjob_ids, _, _, _ = add_indexing_workflow(session, tmp_path, run_id=63, job_id=4, count=1)
        session.get(db_schema.Job, job_id).status = core.STATUS_REVERSE_MAPPING["Cancelled"]
        session.commit()

    result = executors.execute_indexing_chunk(job_id, subjob_ids)

    assert result == []
    assert calls == []
    assert notifications == [(job_id, 1)]
    with session_utils.get_session() as session:
        assert session.get(db_schema.SubJob, subjob_ids[0]).status == core.STATUS_REVERSE_MAPPING["Queued"]


def test_indexing_coordinator_loads_output_settings_from_database(queue_db, monkeypatch, tmp_path):
    fake_redis = FakeRedis()
    merge_calls = []
    monkeypatch.setattr(lifecycle, "redis_conn", fake_redis)
    monkeypatch.setattr(
        batch,
        "merge_xml_files",
        lambda source, destination: merge_calls.append((source, destination)) or {"success": True, "files_merged": 2},
    )

    with session_utils.get_session() as session:
        _, job_id, _, output_dir, _, _ = add_indexing_workflow(session, tmp_path, run_id=64, job_id=5, count=2)
        (output_dir / "xml").mkdir(parents=True)
        for subjob in session.query(db_schema.SubJob).all():
            subjob.status = core.STATUS_REVERSE_MAPPING["Finished"]
        session.commit()

    batch.execute_peakindexing_batch_coordinator(job_id)

    assert merge_calls == [(str(output_dir / "xml"), str(output_dir / "merged.xml"))]
    with session_utils.get_session() as session:
        job = session.get(db_schema.Job, job_id)
        assert job.status == core.STATUS_REVERSE_MAPPING["Finished"]
        assert job.finish_time is not None
        assert "Merged 2 XML files" in job.messages


def test_enqueue_rejects_missing_run_before_queueing(queue_db, monkeypatch):
    fake_queue = FakeQueue()
    fake_redis = FakeRedis()
    monkeypatch.setattr(enqueue, "job_queue", fake_queue)
    monkeypatch.setattr(batch, "redis_conn", fake_redis)

    with pytest.raises(ValueError, match="Indexing I999 does not exist"):
        enqueue.enqueue_indexing(999)

    assert fake_queue.enqueued == []
    assert fake_redis.values == {}


def test_notify_subjobs_completed_falls_back_inline_when_enqueue_fails(monkeypatch):
    fake_redis = FakeRedis()
    calls = []
    monkeypatch.setattr(batch, "redis_conn", fake_redis)
    monkeypatch.setattr(enqueue, "enqueue_job", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("rq down")))
    monkeypatch.setattr(batch, "execute_batch_coordinator", lambda job_id: calls.append(job_id))

    batch.setup_batch_counter(6, 1, "execute_batch_coordinator", job_type="demo")
    batch.notify_subjobs_completed(6, 1)

    assert calls == [6]
    assert batch._batch_counter_key(6) in fake_redis.deleted
    assert batch._batch_meta_key(6) in fake_redis.deleted


def test_cancel_batch_job_cancels_only_queued_chunks(queue_db, monkeypatch):
    fake_redis = FakeRedis()
    queued_job = FakeRQJob(is_queued=True)
    started_job = FakeRQJob(is_started=True)
    rq_jobs = {
        "peakindexing_batch_7_0": queued_job,
        "peakindexing_batch_7_1": started_job,
    }
    notifications = []

    fake_redis.set(
        batch._batch_meta_key(7),
        json.dumps(
            {
                "total": 4,
                "coordinator_func": "execute_peakindexing_batch_coordinator",
                "coordinator_args": [],
                "job_type": "peakindexing",
                "queue_mode": "chunked",
                "rq_job_ids": list(rq_jobs),
                "chunk_subjob_ids": [[700, 701], [702, 703]],
            }
        ),
    )
    monkeypatch.setattr(controls, "redis_conn", fake_redis)
    monkeypatch.setattr(controls.Job, "fetch", lambda rq_job_id, connection=None: rq_jobs[rq_job_id])
    monkeypatch.setattr(
        controls, "notify_subjobs_completed", lambda job_id, count: notifications.append((job_id, count))
    )

    with session_utils.get_session() as session:
        add_job_with_subjobs(session, job_id=7, subjob_count=4)

    result = controls.cancel_batch_job(7)

    assert result["success"] is True
    assert result["cancelled_count"] == 2
    assert queued_job.cancelled is True
    assert started_job.cancelled is False
    assert notifications == [(7, 2)]

    with session_utils.get_session() as session:
        subjobs = {subjob.subjob_id: subjob for subjob in session.query(db_schema.SubJob).all()}
        assert subjobs[700].status == core.STATUS_REVERSE_MAPPING["Cancelled"]
        assert subjobs[701].status == core.STATUS_REVERSE_MAPPING["Cancelled"]
        assert subjobs[702].status == core.STATUS_REVERSE_MAPPING["Queued"]
        assert subjobs[703].status == core.STATUS_REVERSE_MAPPING["Queued"]
        assert session.get(db_schema.Job, 7).status == core.STATUS_REVERSE_MAPPING["Cancelled"]


def test_execute_reconstruction_subjob_loads_and_dispatches_wire_method(queue_db, monkeypatch, tmp_path):
    fake_redis = FakeRedis()
    notifications = []
    calls = []
    result = SimpleNamespace(success=True, output_files=["result.h5"], log=None, command="wire command")
    monkeypatch.setattr(executors, "wire_reconstruct", lambda *args, **kwargs: calls.append((args, kwargs)) or result)
    monkeypatch.setattr(lifecycle, "redis_conn", fake_redis)
    monkeypatch.setattr(batch, "notify_subjob_completed", lambda job_id: notifications.append(job_id))

    with session_utils.get_session() as session:
        _, job_id, subjob_ids, _ = add_reconstruction_workflow(session, tmp_path)

    returned = executors.execute_reconstruction_subjob(job_id, subjob_ids[0])

    assert returned is result
    assert notifications == [job_id]
    positional, keyword = calls[0]
    assert positional[0].endswith("wire_input_0.h5")
    assert positional[1].endswith("wire_")
    assert positional[3:] == ((-5.0, 5.0), 0.25)
    assert keyword == {
        "percent_brightest": 12.5,
        "wire_edge": "0 1",
        "memory_limit_mb": 512,
        "num_threads": 4,
        "verbose": 2,
        "detector_number": 0,
    }
    with session_utils.get_session() as session:
        subjob = session.get(db_schema.SubJob, subjob_ids[0])
        assert subjob.status == core.STATUS_REVERSE_MAPPING["Finished"]
        assert subjob.command == "wire command"


def test_execute_reconstruction_subjob_fails_explicitly_for_ca(queue_db, monkeypatch, tmp_path):
    fake_redis = FakeRedis()
    notifications = []
    monkeypatch.setattr(lifecycle, "redis_conn", fake_redis)
    monkeypatch.setattr(batch, "notify_subjob_completed", lambda job_id: notifications.append(job_id))

    with session_utils.get_session() as session:
        _, job_id, subjob_ids, _ = add_reconstruction_workflow(
            session, tmp_path, run_id=52, job_id=8, count=1, method="ca"
        )

    with pytest.raises(NotImplementedError, match="CA reconstruction is not available"):
        executors.execute_reconstruction_subjob(job_id, subjob_ids[0])

    assert notifications == [8]
    with session_utils.get_session() as session:
        subjob = session.get(db_schema.SubJob, subjob_ids[0])
        assert subjob.status == core.STATUS_REVERSE_MAPPING["Failed"]
        assert "CA reconstruction is not available" in subjob.messages


def test_execute_with_status_updates_skips_terminal_job_before_running(queue_db):
    calls = []

    with session_utils.get_session() as session:
        add_job_with_subjobs(session, job_id=10, subjob_count=1)
        subjob = session.get(db_schema.SubJob, 1000)
        subjob.status = core.STATUS_REVERSE_MAPPING["Cancelled"]
        session.commit()

    result = lifecycle.execute_with_status_updates(
        1000,
        "Demo subjob",
        lambda: calls.append("ran"),
        db_schema.SubJob,
    )

    assert result is None
    assert calls == []
    with session_utils.get_session() as session:
        subjob = session.get(db_schema.SubJob, 1000)
        assert subjob.status == core.STATUS_REVERSE_MAPPING["Cancelled"]
        assert subjob.start_time is None


def test_execute_with_status_updates_failure_marks_subjob_and_notifies_parent(queue_db, monkeypatch):
    notifications = []
    fake_redis = FakeRedis()
    monkeypatch.setattr(lifecycle, "redis_conn", fake_redis)
    monkeypatch.setattr(batch, "notify_subjob_completed", lambda job_id: notifications.append(job_id))

    with session_utils.get_session() as session:
        add_job_with_subjobs(session, job_id=8, subjob_count=1)

    def fail_job():
        raise RuntimeError("worker exploded")

    with pytest.raises(RuntimeError, match="worker exploded"):
        lifecycle.execute_with_status_updates(
            800,
            "Demo subjob",
            fail_job,
            db_schema.SubJob,
        )

    assert notifications == [8]
    assert fake_redis.published[-1][0] == "laue:job_updates"

    with session_utils.get_session() as session:
        subjob = session.get(db_schema.SubJob, 800)
        parent = session.get(db_schema.Job, 8)
        assert subjob.status == core.STATUS_REVERSE_MAPPING["Failed"]
        assert subjob.messages == "Error: worker exploded"
        assert parent.status == core.STATUS_REVERSE_MAPPING["Running"]


def test_batch_coordinator_preserves_cancelled_parent_status(queue_db, monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(lifecycle, "redis_conn", fake_redis)

    with session_utils.get_session() as session:
        add_job_with_subjobs(session, job_id=9, subjob_count=2, status=core.STATUS_REVERSE_MAPPING["Cancelled"])
        job = session.get(db_schema.Job, 9)
        original_finish_time = datetime.datetime(2026, 1, 2, 12, 0, 0)
        job.finish_time = original_finish_time
        subjobs = session.query(db_schema.SubJob).order_by(db_schema.SubJob.subjob_id).all()
        subjobs[0].status = core.STATUS_REVERSE_MAPPING["Finished"]
        subjobs[1].status = core.STATUS_REVERSE_MAPPING["Cancelled"]
        session.commit()

    batch.execute_batch_coordinator(9)

    with session_utils.get_session() as session:
        job = session.get(db_schema.Job, 9)
        assert job.status == core.STATUS_REVERSE_MAPPING["Cancelled"]
        assert job.finish_time == original_finish_time
        assert "Batch final: 1 cancelled, 1 succeeded, 0 failed" in job.messages
