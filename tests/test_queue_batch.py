import datetime
import json
from types import SimpleNamespace

import pytest

from laue_portal.database import db_schema, session_utils
from laue_portal.processing import redis_utils


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


def add_job_with_subjobs(session, job_id=1, subjob_count=0, status=None):
    if status is None:
        status = redis_utils.STATUS_REVERSE_MAPPING["Queued"]
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
                status=redis_utils.STATUS_REVERSE_MAPPING["Queued"],
                priority=1,
            )
        )
    session.commit()


def peakindex_args():
    return {
        "geometry_file": "geo.xml",
        "crystal_file": "crystal.xtal",
        "boxsize": 18,
        "max_rfactor": 0.5,
        "min_size": 1,
        "min_separation": 40,
        "threshold": 250,
        "peak_shape": "L",
        "max_peaks": 50,
        "smooth": False,
        "index_kev_max_calc": 17.2,
        "index_kev_max_test": 30.0,
        "index_angle_tolerance": 0.1,
        "index_cone": 72.0,
        "index_h": 1,
        "index_k": 1,
        "index_l": 1,
    }


def test_enqueue_job_supports_custom_rq_id_and_strips_queue_kwargs(monkeypatch):
    fake_queue = FakeQueue()
    monkeypatch.setattr(redis_utils, "job_queue", fake_queue)

    def worker(job_id, worker_option=None):
        return job_id, worker_option

    rq_job_id = redis_utils.enqueue_job(
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


def test_enqueue_peakindexing_creates_chunk_jobs_and_metadata(queue_db, monkeypatch):
    fake_queue = FakeQueue()
    fake_redis = FakeRedis()
    monkeypatch.setattr(redis_utils, "job_queue", fake_queue)
    monkeypatch.setattr(redis_utils, "redis_conn", fake_redis)

    with session_utils.get_session() as session:
        add_job_with_subjobs(session, job_id=1, subjob_count=10)

    result = redis_utils.enqueue_peakindexing(
        1,
        input_files=[f"input_{i}.tif" for i in range(10)],
        output_files=["/out"] * 10,
        queue_batch_size=3,
        **peakindex_args(),
    )

    assert result == "batch_1"
    assert [job["kwargs"]["job_id"] for job in fake_queue.enqueued] == [
        "peakindexing_batch_1_0",
        "peakindexing_batch_1_1",
        "peakindexing_batch_1_2",
        "peakindexing_batch_1_3",
    ]
    assert [len(job["args"][0]) for job in fake_queue.enqueued] == [3, 3, 3, 1]
    assert all(job["func"] is redis_utils.execute_peakindexing_chunk for job in fake_queue.enqueued)

    meta = json.loads(fake_redis.values[redis_utils._batch_meta_key(1)])
    assert meta["total"] == 10
    assert meta["queue_mode"] == "chunked"
    assert meta["rq_job_ids"] == [job["kwargs"]["job_id"] for job in fake_queue.enqueued]
    assert meta["chunk_subjob_ids"] == [[100, 101, 102], [103, 104, 105], [106, 107, 108], [109]]


def test_notify_subjobs_completed_batches_and_enqueues_coordinator_once(monkeypatch):
    fake_redis = FakeRedis()
    enqueued = []
    monkeypatch.setattr(redis_utils, "redis_conn", fake_redis)
    monkeypatch.setattr(
        redis_utils, "enqueue_job", lambda *args, **kwargs: enqueued.append((args, kwargs)) or "coordinator"
    )

    redis_utils.setup_batch_counter(42, 3, "execute_batch_coordinator", job_type="demo")
    redis_utils.notify_subjobs_completed(42, 2)
    assert enqueued == []

    redis_utils.notify_subjobs_completed(42, 1)
    redis_utils.notify_subjobs_completed(42, 1)

    assert len(enqueued) == 1
    assert enqueued[0][0][0:3] == (42, "batch_coordinator", redis_utils.execute_batch_coordinator)
    assert fake_redis.values[redis_utils._batch_coordinator_enqueued_key(42)] == 1
    assert redis_utils._batch_counter_key(42) in fake_redis.deleted
    assert redis_utils._batch_meta_key(42) in fake_redis.deleted


def test_execute_peakindexing_chunk_bulk_updates_success_and_failure(queue_db, monkeypatch):
    notifications = []
    calls = []

    def fake_index(input_image, **kwargs):
        calls.append(input_image)
        if input_image == "bad.tif":
            raise RuntimeError("index failed")
        return SimpleNamespace(command_history=[f"index {input_image}"])

    monkeypatch.setattr(redis_utils, "index", fake_index)
    monkeypatch.setattr(
        redis_utils, "notify_subjobs_completed", lambda job_id, count: notifications.append((job_id, count))
    )
    monkeypatch.setattr(redis_utils, "redis_conn", FakeRedis())

    with session_utils.get_session() as session:
        add_job_with_subjobs(session, job_id=2, subjob_count=3)

    result = redis_utils.execute_peakindexing_chunk(
        2,
        [
            {"subjob_id": 200, "input_file": "good_a.tif", "output_file": "/out"},
            {"subjob_id": 201, "input_file": "bad.tif", "output_file": "/out"},
            {"subjob_id": 202, "input_file": "good_b.tif", "output_file": "/out"},
        ],
        **peakindex_args(),
    )

    assert calls == ["good_a.tif", "bad.tif", "good_b.tif"]
    assert len(result) == 3
    assert notifications == [(2, 3)]

    with session_utils.get_session() as session:
        job = session.get(db_schema.Job, 2)
        subjobs = {subjob.subjob_id: subjob for subjob in session.query(db_schema.SubJob).all()}
        assert job.status == redis_utils.STATUS_REVERSE_MAPPING["Running"]
        assert subjobs[200].status == redis_utils.STATUS_REVERSE_MAPPING["Finished"]
        assert subjobs[201].status == redis_utils.STATUS_REVERSE_MAPPING["Failed"]
        assert subjobs[202].status == redis_utils.STATUS_REVERSE_MAPPING["Finished"]
        assert subjobs[200].messages is None
        assert subjobs[200].command is None
        assert "index failed" in subjobs[201].messages


def test_execute_peakindexing_chunk_marks_all_failed_without_raising(queue_db, monkeypatch):
    notifications = []

    def fail_index(input_image, **kwargs):
        raise RuntimeError(f"failed {input_image}")

    monkeypatch.setattr(redis_utils, "index", fail_index)
    monkeypatch.setattr(
        redis_utils, "notify_subjobs_completed", lambda job_id, count: notifications.append((job_id, count))
    )
    monkeypatch.setattr(redis_utils, "redis_conn", FakeRedis())

    with session_utils.get_session() as session:
        add_job_with_subjobs(session, job_id=3, subjob_count=2)

    result = redis_utils.execute_peakindexing_chunk(
        3,
        [
            {"subjob_id": 300, "input_file": "a.tif", "output_file": "/out"},
            {"subjob_id": 301, "input_file": "b.tif", "output_file": "/out"},
        ],
        **peakindex_args(),
    )

    assert [item["status"] for item in result] == [redis_utils.STATUS_REVERSE_MAPPING["Failed"]] * 2
    assert notifications == [(3, 2)]
    with session_utils.get_session() as session:
        subjobs = session.query(db_schema.SubJob).order_by(db_schema.SubJob.subjob_id).all()
        assert [subjob.status for subjob in subjobs] == [redis_utils.STATUS_REVERSE_MAPPING["Failed"]] * 2
        assert all("failed" in subjob.messages for subjob in subjobs)


def test_execute_peakindexing_chunk_skips_terminal_parent(queue_db, monkeypatch):
    calls = []
    notifications = []
    monkeypatch.setattr(redis_utils, "index", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(
        redis_utils, "notify_subjobs_completed", lambda job_id, count: notifications.append((job_id, count))
    )

    with session_utils.get_session() as session:
        add_job_with_subjobs(session, job_id=4, subjob_count=1, status=redis_utils.STATUS_REVERSE_MAPPING["Cancelled"])

    result = redis_utils.execute_peakindexing_chunk(
        4,
        [{"subjob_id": 400, "input_file": "a.tif", "output_file": "/out"}],
        **peakindex_args(),
    )

    assert result == []
    assert calls == []
    assert notifications == []
    with session_utils.get_session() as session:
        assert session.get(db_schema.SubJob, 400).status == redis_utils.STATUS_REVERSE_MAPPING["Queued"]


def test_enqueue_peakindexing_rejects_mismatched_files_before_queueing(queue_db, monkeypatch):
    fake_queue = FakeQueue()
    fake_redis = FakeRedis()
    monkeypatch.setattr(redis_utils, "job_queue", fake_queue)
    monkeypatch.setattr(redis_utils, "redis_conn", fake_redis)

    with session_utils.get_session() as session:
        add_job_with_subjobs(session, job_id=5, subjob_count=3)

    with pytest.raises(ValueError, match="Number of input files"):
        redis_utils.enqueue_peakindexing(
            5,
            input_files=["only-one.tif"],
            output_files=["/out"] * 3,
            **peakindex_args(),
        )

    assert fake_queue.enqueued == []
    assert fake_redis.values == {}


def test_notify_subjobs_completed_falls_back_inline_when_enqueue_fails(monkeypatch):
    fake_redis = FakeRedis()
    calls = []
    monkeypatch.setattr(redis_utils, "redis_conn", fake_redis)
    monkeypatch.setattr(
        redis_utils, "enqueue_job", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("rq down"))
    )
    monkeypatch.setattr(redis_utils, "execute_batch_coordinator", lambda job_id: calls.append(job_id))

    redis_utils.setup_batch_counter(6, 1, "execute_batch_coordinator", job_type="demo")
    redis_utils.notify_subjobs_completed(6, 1)

    assert calls == [6]
    assert redis_utils._batch_counter_key(6) in fake_redis.deleted
    assert redis_utils._batch_meta_key(6) in fake_redis.deleted


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
        redis_utils._batch_meta_key(7),
        json.dumps(
            {
                "total": 4,
                "coordinator_func": "execute_peakindexing_batch_coordinator",
                "coordinator_args": ["/out", "output.xml"],
                "job_type": "peakindexing",
                "queue_mode": "chunked",
                "rq_job_ids": list(rq_jobs),
                "chunk_subjob_ids": [[700, 701], [702, 703]],
            }
        ),
    )
    monkeypatch.setattr(redis_utils, "redis_conn", fake_redis)
    monkeypatch.setattr(redis_utils.Job, "fetch", lambda rq_job_id, connection=None: rq_jobs[rq_job_id])
    monkeypatch.setattr(
        redis_utils, "notify_subjobs_completed", lambda job_id, count: notifications.append((job_id, count))
    )

    with session_utils.get_session() as session:
        add_job_with_subjobs(session, job_id=7, subjob_count=4)

    result = redis_utils.cancel_batch_job(7)

    assert result["success"] is True
    assert result["cancelled_count"] == 2
    assert queued_job.cancelled is True
    assert started_job.cancelled is False
    assert notifications == [(7, 2)]

    with session_utils.get_session() as session:
        subjobs = {subjob.subjob_id: subjob for subjob in session.query(db_schema.SubJob).all()}
        assert subjobs[700].status == redis_utils.STATUS_REVERSE_MAPPING["Cancelled"]
        assert subjobs[701].status == redis_utils.STATUS_REVERSE_MAPPING["Cancelled"]
        assert subjobs[702].status == redis_utils.STATUS_REVERSE_MAPPING["Queued"]
        assert subjobs[703].status == redis_utils.STATUS_REVERSE_MAPPING["Queued"]
        assert session.get(db_schema.Job, 7).status == redis_utils.STATUS_REVERSE_MAPPING["Cancelled"]
