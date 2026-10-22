"""DM completion is authoritative; polling must not block processing or lose arrivals."""

import json
import threading
from pathlib import Path
from unittest.mock import Mock

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from laue_portal import config
from laue_portal.database import db_schema as db
from laue_portal.processing import live_arrivals
from laue_portal.processing.live_arrivals import CatalogArrivals
from laue_portal.services.dm_daq import bind_daq, destination_root
from tests.test_live_processing import setup as live_setup  # noqa: F401
from tests.test_live_processing import write_raw_frame


@pytest.fixture
def acquisition(request, monkeypatch):
    engine, raw, create = request.getfixturevalue("live_setup")
    live = create(indexing=True, reconstruction=False)
    binding = {
        "kind": "dm_catalog",
        "daq_id": "demo-daq",
        "experiment": "demo",
        "storage_directory": str(raw.parent),
        "relative_directory": raw.name,
        "destination_directory": str(raw),
        "input_directory": str(raw),
    }
    live.recipe = {**live.recipe, "arrivals": binding}
    with Session(engine) as session, session.begin():
        session.get(db.LiveSession, live.id).recipe = live.recipe
    monkeypatch.setattr(config, "LIVE", {"dm": {"poll_seconds": 0.1}})
    client = Mock()
    client.arrival_files.return_value = {"daq_status": "running", "files": []}
    return engine, raw, live, client


def row(raw, point, *, timestamp=1000):
    path = write_raw_frame(raw / f"wire_{point}.h5")
    return {
        "experimentFilePath": f"{raw.name}/{path.name}",
        "storageFilePath": str(path),
        "fileSize": path.stat().st_size,
        "fileProcessingTime": timestamp,
        "daqId": "demo-daq",
        "experimentName": "demo",
    }


def complete_page(monitor):
    monitor.next_poll = 0
    monitor.poll()
    monitor.future.result(timeout=3)
    monitor.poll()


def sources(engine, live):
    with Session(engine) as session:
        return list(session.scalars(select(db.LivePoint.source).where(db.LivePoint.session_id == live.id)))


def test_directory_presence_is_not_completion_and_catalog_replays_are_deduplicated(acquisition):
    engine, raw, live, client = acquisition
    record = row(raw, 1)
    with CatalogArrivals(live, engine, client=client) as monitor:
        complete_page(monitor)
        assert sources(engine, live) == []
        client.arrival_files.return_value["files"] = [record]
        complete_page(monitor)
        complete_page(monitor)
    assert sources(engine, live) == [str(raw / "wire_1.h5")]
    query = client.arrival_files.call_args.args[1]
    assert query["daqId"] == "demo-daq"
    assert query["experimentFilePath"]["$regex"] == r"^raw/[^/]+$"


def test_paged_polling_resumes_after_ledger_admission(acquisition, monkeypatch):
    engine, raw, live, client = acquisition
    monkeypatch.setattr(live_arrivals, "PAGE_SIZE", 2)
    records = [row(raw, n) for n in (1, 2, 3)]
    client.arrival_files.side_effect = lambda binding, query, skip, limit: {
        "daq_status": "running",
        "files": records[skip : skip + limit],
    }
    with CatalogArrivals(live, engine, client=client) as monitor:
        complete_page(monitor)
    assert json.loads((Path(live.control_directory) / "arrival-cursor.json").read_text())["skip"] == 2
    with CatalogArrivals(live, engine, client=client) as resumed:
        complete_page(resumed)
    assert len(sources(engine, live)) == 3


def test_late_catalog_insertion_is_found_by_full_reconciliation(acquisition, monkeypatch):
    engine, raw, live, client = acquisition
    clock = [2000]
    monkeypatch.setattr(live_arrivals.time, "time", lambda: clock[0])
    with CatalogArrivals(live, engine, client=client) as monitor:
        client.arrival_files.return_value["files"] = [row(raw, 1, timestamp=1900)]
        complete_page(monitor)
        monitor.next_poll = 0
        monitor.poll()
        monitor.future.result(timeout=3)
        assert client.arrival_files.call_args.args[1]["fileProcessingTime"] == {"$gte": 1780}
        monitor.poll()
        clock[0] += 301
        client.arrival_files.return_value["files"] = [row(raw, 2, timestamp=1000)]
        complete_page(monitor)
        assert "fileProcessingTime" not in client.arrival_files.call_args.args[1]
    assert len(sources(engine, live)) == 2


@pytest.mark.parametrize("bad", ["other_daq", "other_experiment", "traversal", "outside", "wrong_size", "symlink"])
def test_invalid_or_incomplete_destinations_are_not_admitted(acquisition, bad):
    engine, raw, live, client = acquisition
    record = row(raw, 1)
    if bad == "other_daq":
        record["daqId"] = "another"
    elif bad == "other_experiment":
        record["experimentName"] = "another"
    elif bad == "traversal":
        record["experimentFilePath"] = "raw/../wire_1.h5"
    elif bad == "outside":
        record["storageFilePath"] = str(raw.parent / "elsewhere.h5")
    elif bad == "wrong_size":
        record["fileSize"] += 1
    else:
        (raw / "wire_1.h5").rename(raw.parent / "outside.h5")
        (raw / "wire_1.h5").symlink_to(raw.parent / "outside.h5")
    client.arrival_files.return_value["files"] = [record]
    with CatalogArrivals(live, engine, client=client) as monitor:
        complete_page(monitor)
    assert sources(engine, live) == []
    assert json.loads((Path(live.control_directory) / "arrival-status.json").read_text())["error"]
    assert not (Path(live.control_directory) / "arrival-cursor.json").exists()


def test_network_error_retries_without_losing_or_duplicating_inputs(acquisition):
    engine, raw, live, client = acquisition
    record = row(raw, 1)
    client.arrival_files.side_effect = OSError("offline")
    with CatalogArrivals(live, engine, client=client) as monitor:
        monitor.poll()
        with pytest.raises(OSError):
            monitor.future.result(timeout=3)
        monitor.poll()
        assert sources(engine, live) == []
        client.arrival_files.side_effect = None
        client.arrival_files.return_value["files"] = [record]
        complete_page(monitor)
    status = json.loads((Path(live.control_directory) / "arrival-status.json").read_text())
    assert status["error"] is None and len(sources(engine, live)) == 1


def test_slow_catalog_does_not_block_controller_and_stop_drops_unaccepted_page(acquisition):
    engine, raw, live, client = acquisition
    entered, release = threading.Event(), threading.Event()

    def slow(*args, **kwargs):
        entered.set()
        assert release.wait(3)
        return {"daq_status": "running", "files": [row(raw, 1)]}

    client.arrival_files.side_effect = slow
    with CatalogArrivals(live, engine, client=client) as monitor:
        try:
            monitor.poll()
            assert entered.wait(1) and not monitor.future.done()
            monitor.poll(accepting=False)
            release.set()
            monitor.future.result(timeout=3)
            monitor.poll(accepting=False)
            assert sources(engine, live) == []
        finally:
            release.set()


def test_binding_checks_running_daq_and_destination(tmp_path):
    raw = tmp_path / "data" / "run"
    raw.mkdir(parents=True)
    record = {
        "id": "daq",
        "status": "running",
        "experimentName": "demo",
        "storageDirectory": str(tmp_path / "data"),
        "dataDirectory": "/detector",
    }
    client = Mock()
    client.daq.return_value = record
    binding = bind_daq("daq", raw, client=client)
    assert binding["relative_directory"] == "run"
    assert binding["input_directory"] == str(raw)
    with pytest.raises(ValueError, match="inside"):
        bind_daq("daq", tmp_path, client=client)
    record["status"] = "done"
    with pytest.raises(ValueError, match="running"):
        bind_daq("daq", raw, client=client)
    record["destDirectory"] = "../outside"
    with pytest.raises(ValueError, match="invalid"):
        destination_root(record)
