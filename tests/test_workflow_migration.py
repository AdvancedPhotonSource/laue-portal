"""Tests for migration from a test-only legacy SQLite schema and SubJob compaction."""

import hashlib
import json
import sqlite3
import stat
from pathlib import Path

import pytest
from sqlalchemy import MetaData, create_engine

from laue_portal.database import db_schema
from laue_portal.workflows.execution import JobStatus, RunPhase
from laue_portal.workflows.manifest import read_failure_report
from scripts.workflow_migration import MigrationError, default_export_directory, migrate_database


def _sqlite_type(column: str, value) -> str:
    integer_columns = {
        "scanNumber",
        "job_id",
        "subjob_id",
        "wirerecon_id",
        "recon_id",
        "peakindex_id",
        "calib_id",
        "status",
        "priority",
        "scanPointslen",
        "depthRangelen",
        "num_threads",
        "memory_limit_mb",
        "verbose",
        "threshold",
        "thresholdRatio",
        "boxsize",
        "max_number",
        "min_separation",
        "detectorCropX1",
        "detectorCropX2",
        "detectorCropY1",
        "detectorCropY2",
        "max_peaks",
        "smooth",
        "indexH",
        "indexK",
        "indexL",
        "cosmicFilter",
    }
    if column in integer_columns or isinstance(value, (bool, int)):
        return "INTEGER"
    if isinstance(value, float):
        return "REAL"
    return "TEXT"


def _create_table(connection, table_name: str, example_row: dict, primary_key: str) -> None:
    definitions = []
    for column, value in example_row.items():
        suffix = " PRIMARY KEY" if column == primary_key else ""
        definitions.append(f'"{column}" {_sqlite_type(column, value)}{suffix}')
    connection.execute(f'CREATE TABLE "{table_name}" ({", ".join(definitions)})')


def _insert(connection, table_name: str, values: dict) -> None:
    columns = ", ".join(f'"{column}"' for column in values)
    placeholders = ", ".join("?" for _ in values)
    connection.execute(
        f'INSERT INTO "{table_name}" ({columns}) VALUES ({placeholders})',
        tuple(values.values()),
    )


def _legacy_wire_row() -> dict:
    return {
        "wirerecon_id": 10,
        "scanNumber": 1,
        "job_id": 1,
        "filefolder": "/legacy/wire/input",
        "filenamePrefix": '["wire_*.h5"]',
        "author": "wire user",
        "notes": "wire notes",
        "geoFile": "/legacy/wire/geometry.xml",
        "percent_brightest": 5.0,
        "wire_edges": "0 1",
        "depth_start": -5.0,
        "depth_end": 5.0,
        "depth_resolution": 0.25,
        "num_threads": 8,
        "memory_limit_mb": 2048,
        "scanPoints": "1-2",
        "scanPointslen": 2,
        "outputFolder": "/legacy/wire/output",
        "verbose": 1,
    }


def _legacy_indexing_row(indexing_id: int, job_id: int, wire_parent: int | None) -> dict:
    return {
        "peakindex_id": indexing_id,
        "scanNumber": None,
        "job_id": job_id,
        "filefolder": "/legacy/index/input",
        "filenamePrefix": '["test_file"]',
        "author": "index user",
        "notes": "index notes",
        "recon_id": None,
        "wirerecon_id": wire_parent,
        "threshold": 250,
        "thresholdRatio": -1,
        "maxRfactor": 0.5,
        "boxsize": 18,
        "max_number": 50,
        "min_separation": 40,
        "peakShape": "Lorentzian",
        "scanPoints": "1-2",
        "scanPointslen": 2,
        "depthRange": None,
        "depthRangelen": None,
        "detectorCropX1": 0,
        "detectorCropX2": 2047,
        "detectorCropY1": 0,
        "detectorCropY2": 2047,
        "min_size": 1.13,
        "max_peaks": 50,
        "smooth": 0,
        "maskFile": None,
        "indexKeVmaxCalc": 17.2,
        "indexKeVmaxTest": 30.0,
        "indexAngleTolerance": 0.1,
        "indexH": 1,
        "indexK": 1,
        "indexL": 1,
        "indexCone": 72.0,
        "energyUnit": "keV",
        "exposureUnit": "sec",
        "cosmicFilter": 1,
        "recipLatticeUnit": "1/nm",
        "latticeParametersUnit": "nm",
        "outputFolder": f"/legacy/index/output/{indexing_id}",
        "outputXML": "merged.xml",
        "geoFile": "/legacy/index/geometry.xml",
        "crystFile": "/legacy/index/Al.xtal",
        "depth": "2D",
        "beamline": "34ID-E",
    }


_JOB_TEMPLATE = {
    "job_id": 1,
    "computer_name": "TEST_COMPUTER",
    "status": 2,
    "priority": 5,
    "submit_time": "2022-01-01 00:00:00.000000",
    "start_time": "2022-01-01 00:01:00.000000",
    "finish_time": "2022-01-01 00:02:00.000000",
    "messages": "legacy job",
}
_SUBJOB_TEMPLATE = {
    "subjob_id": 1,
    "job_id": 1,
    "computer_name": "TEST_COMPUTER",
    "status": 2,
    "priority": 5,
    "start_time": "2022-01-01 00:01:00.000000",
    "finish_time": "2022-01-01 00:02:00.000000",
    "messages": "legacy subjob",
    "command": "legacy command",
}
# (job_id, status, message, command) per subjob; job 1 is the wire run, jobs 2 and 3 are indexing runs.
_SUBJOBS = [
    (1, 2, "IndexingResult(success=True, output_files={'a': 1})", "peaksearch a.h5"),
    (1, 3, "Error: '>=' not supported between instances of 'str' and 'int'", None),
    (1, 4, "Cancelled by user", None),
    (2, 3, "Marked as failed: stale job after Redis restart/cleanup", None),
    (2, 3, "Marked as failed: stale job after Redis restart/cleanup", None),
    (3, 2, "IndexingResult(success=True, output_files={'b': 2})", "peaksearch b.h5"),
    (3, 2, "IndexingResult(success=True, output_files={'c': 3})", "peaksearch c.h5"),
]


def _create_legacy_database(path: Path, include_ca: bool = False, *, running_job: bool = False) -> None:
    metadata = {"scanNumber": 1}
    wire = _legacy_wire_row()
    indexing = _legacy_indexing_row(7, 2, 10)
    direct_indexing = _legacy_indexing_row(9, 3, None)
    recon = {"recon_id": 4, "job_id": 4}
    job_statuses = {1: 4, 2: 1 if running_job else 3, 3: 2, 4: 2}

    with sqlite3.connect(path) as connection:
        _create_table(connection, "metadata", metadata, "scanNumber")
        _create_table(connection, "job", _JOB_TEMPLATE, "job_id")
        _create_table(connection, "subjob", _SUBJOB_TEMPLATE, "subjob_id")
        _create_table(connection, "wirerecon", wire, "wirerecon_id")
        _create_table(connection, "recon", recon, "recon_id")
        _create_table(connection, "peakindex", indexing, "peakindex_id")
        _insert(connection, "metadata", metadata)
        for job_id in range(1, 5 if include_ca else 4):
            values = {**_JOB_TEMPLATE, "job_id": job_id, "status": job_statuses[job_id]}
            if running_job and job_id == 2:
                values["finish_time"] = None
            _insert(connection, "job", values)
        _insert(connection, "wirerecon", wire)
        _insert(connection, "peakindex", indexing)
        _insert(connection, "peakindex", direct_indexing)
        if include_ca:
            _insert(connection, "recon", recon)
        for subjob_id, (job_id, status, message, command) in enumerate(_SUBJOBS, start=1):
            if running_job and job_id == 2:
                status = 0  # queued when the system stopped
            _insert(
                connection,
                "subjob",
                {
                    **_SUBJOB_TEMPLATE,
                    "subjob_id": subjob_id,
                    "job_id": job_id,
                    "status": status,
                    "messages": message,
                    "command": command,
                },
            )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _columns(connection, table: str) -> dict[str, dict]:
    return {
        row[1]: {"type": row[2], "notnull": row[3], "default": row[4]}
        for row in connection.execute(f"PRAGMA table_info({table})")
    }


def _fresh_schema_tables(tmp_path: Path) -> list[str]:
    engine = create_engine(f"sqlite:///{tmp_path / 'fresh.db'}")
    db_schema.Base.metadata.create_all(engine)
    engine.dispose()
    with sqlite3.connect(tmp_path / "fresh.db") as connection:
        return [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]


def _fresh_schema_columns(tmp_path: Path, table: str) -> dict[str, dict]:
    engine = create_engine(f"sqlite:///{tmp_path / 'fresh.db'}")
    db_schema.Base.metadata.create_all(engine)
    engine.dispose()
    with sqlite3.connect(tmp_path / "fresh.db") as connection:
        return _columns(connection, table)


def test_legacy_stage_alone_copies_source_and_verifies_unified_data(tmp_path):
    source = tmp_path / "legacy.db"
    destination = tmp_path / "migrated.db"
    _create_legacy_database(source)
    source_hash = _sha256(source)

    report = migrate_database(source, destination, compact=False)

    assert destination.exists()
    assert not default_export_directory(destination).exists()
    assert _sha256(source) == source_hash
    assert stat.S_IMODE(destination.stat().st_mode) == stat.S_IMODE(source.stat().st_mode)
    assert report.stages == ("legacy",)
    assert report.compaction is None
    assert report.reconstruction_id_map == {10: 1}
    assert report.indexing_id_map == {7: 7, 9: 9}
    assert report.legacy_counts["subjob"] == 7
    assert report.migrated_counts == {"reconstruction_run": 1, "indexing_run": 2, "subjob": 7}

    with sqlite3.connect(destination) as connection:
        connection.row_factory = sqlite3.Row
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        assert {"wirerecon", "recon", "peakindex"}.isdisjoint(tables)
        assert {
            "reconstruction_run",
            "wire_reconstruction_parameters",
            "indexing_run",
            "lauego_indexing_parameters",
        } <= tables
        reconstruction = dict(connection.execute("SELECT * FROM reconstruction_run").fetchone())
        assert reconstruction == {
            "id": 1,
            "scan_number": 1,
            "job_id": 1,
            "method": "wire",
            "input_path": "/legacy/wire/input",
            "output_path": "/legacy/wire/output",
            "author": "wire user",
            "notes": "wire notes",
            "algorithm_version": None,
            "created_at": "2022-01-01 00:00:00.000000",
        }
        indexing = connection.execute("SELECT * FROM indexing_run WHERE id = 7").fetchone()
        assert indexing["scan_number"] == 1
        assert indexing["reconstruction_id"] == 1
        assert indexing["method"] == "lauego"
        parameters = connection.execute(
            "SELECT filename_prefixes, output_xml FROM lauego_indexing_parameters WHERE indexing_id = 7"
        ).fetchone()
        assert parameters["filename_prefixes"] == '["test_file"]'
        assert parameters["output_xml"] == "merged.xml"
        direct_indexing = connection.execute(
            "SELECT scan_number, reconstruction_id FROM indexing_run WHERE id = 9"
        ).fetchone()
        assert tuple(direct_indexing) == (None, None)
        assert "I9 (formerly PI9) has no scan number" in report.warnings
        # The legacy stage keeps every SubJob row: its own count assertion still holds.
        assert connection.execute("SELECT COUNT(*) FROM subjob").fetchone()[0] == 7
        assert "n_inputs" not in _columns(connection, "job")
        job_times = connection.execute(
            "SELECT submit_time, start_time, finish_time FROM job WHERE job_id = 1"
        ).fetchone()
        assert tuple(job_times) == (
            "2022-01-01 00:00:00.000000",
            "2022-01-01 00:01:00.000000",
            "2022-01-01 00:02:00.000000",
        )
        assert connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert not any(".migrating" in path.name for path in tmp_path.iterdir())


def test_full_chain_compacts_subjobs_into_counters_and_exports_diagnostics(tmp_path):
    source = tmp_path / "legacy.db"
    destination = tmp_path / "compact.db"
    _create_legacy_database(source)
    source_hash = _sha256(source)

    report = migrate_database(source, destination)

    assert _sha256(source) == source_hash
    assert report.stages == ("legacy", "compact")
    assert report.migrated_counts["subjob"] == 7  # counted after the legacy stage, before compaction
    compaction = report.compaction
    export_dir = default_export_directory(destination)
    assert compaction.export_directory == export_dir
    assert compaction.subjobs_removed == 7
    assert compaction.interrupted_job_ids == ()
    assert compaction.calibration_subjobs == 0
    assert compaction.totals() == {
        "jobs": 3,
        "n_inputs": 7,
        "n_succeeded": 3,
        "n_failed": 3,
        "n_not_run": 1,
        "failure_reports": 2,
    }
    text = report.format_text()
    assert "Stages: legacy, compact" in text
    assert "subjob rows removed: 7" in text
    assert "counters: inputs 7, succeeded 3, failed 3, not run 1" in text

    with sqlite3.connect(destination) as connection:
        connection.row_factory = sqlite3.Row
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        assert "subjob" not in tables  # per-input rows and their table are gone
        assert tables <= set(_fresh_schema_tables(tmp_path))  # the synthetic legacy source has no scan tables
        assert _columns(connection, "job") == _fresh_schema_columns(tmp_path, "job")
        assert _columns(connection, "indexing_run") == _fresh_schema_columns(tmp_path, "indexing_run")
        jobs = {
            row["job_id"]: dict(row)
            for row in connection.execute(
                "SELECT job_id, status, phase, n_inputs, n_succeeded, n_failed, n_not_run, run_directory, "
                "failure_report_path, updated_at, messages FROM job ORDER BY job_id"
            )
        }
        assert (jobs[1]["status"], jobs[1]["phase"]) == (JobStatus.CANCELLED, RunPhase.CANCELLED)
        assert (jobs[1]["n_inputs"], jobs[1]["n_succeeded"], jobs[1]["n_failed"], jobs[1]["n_not_run"]) == (3, 1, 1, 1)
        assert jobs[1]["run_directory"] == "/legacy/wire/output"
        assert jobs[1]["updated_at"] == "2022-01-01 00:02:00.000000"
        assert jobs[1]["messages"] == "legacy job"
        assert (jobs[2]["status"], jobs[2]["phase"]) == (JobStatus.FAILED, RunPhase.FAILED)
        assert (jobs[2]["n_inputs"], jobs[2]["n_succeeded"], jobs[2]["n_failed"], jobs[2]["n_not_run"]) == (2, 0, 2, 0)
        assert jobs[2]["run_directory"] == "/legacy/index/output/7"
        assert (jobs[3]["status"], jobs[3]["phase"]) == (JobStatus.FINISHED, RunPhase.FINISHED)
        assert (jobs[3]["n_inputs"], jobs[3]["n_succeeded"], jobs[3]["n_failed"], jobs[3]["n_not_run"]) == (2, 2, 0, 0)
        assert jobs[3]["failure_report_path"] is None
        for job in jobs.values():
            assert job["n_succeeded"] + job["n_failed"] + job["n_not_run"] == job["n_inputs"]
        assert connection.execute("SELECT n_frames_indexed FROM indexing_run WHERE id = 7").fetchone()[0] is None
        # The compact DB enforces the same constraints as a fresh one.
        with pytest.raises(sqlite3.IntegrityError, match="ck_job_counters_bounded"):
            connection.execute("UPDATE job SET n_succeeded = 9 WHERE job_id = 3")
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"

    assert jobs[1]["failure_report_path"] == str(export_dir / "jobs" / "job_1" / "failures.jsonl")
    records, has_more = read_failure_report(jobs[1]["failure_report_path"])
    assert has_more is False
    assert [(r.category, r.message, r.context["subjob_id"], r.context["status"]) for r in records] == [
        ("error", "Error: '>=' not supported between instances of 'str' and 'int'", 2, "Failed"),
        ("cancelled", "Cancelled by user", 3, "Cancelled"),
    ]
    stale_records, _ = read_failure_report(jobs[2]["failure_report_path"])
    assert [record.category for record in stale_records] == ["interrupted", "interrupted"]

    history = json.loads((export_dir / "jobs" / "job_1" / "history.json").read_text())
    assert history["counters"] == {"n_inputs": 3, "n_succeeded": 1, "n_failed": 1, "n_not_run": 1}
    assert history["original_status_name"] == "Cancelled"
    assert history["representative_command"] == "peaksearch a.h5"
    assert history["message_classes"] == {
        "IndexingResult(success=True)": 1,
        "Error: '>=' not supported between instances of 'str' and 'int'": 1,
        "Cancelled by user": 1,
    }
    assert history["subjob_time_range"] == ["2022-01-01 00:01:00.000000", "2022-01-01 00:02:00.000000"]
    assert not (export_dir / "jobs" / "job_3" / "failures.jsonl").exists()
    assert (export_dir / "jobs" / "job_3" / "history.json").exists()
    exported_report = json.loads((export_dir / "report.json").read_text())
    assert exported_report["stages"] == ["legacy", "compact"]
    assert exported_report["compaction"]["totals"]["n_inputs"] == 7
    assert exported_report["indexing_id_map"] == {"7": 7, "9": 9}
    assert not any(".migrating" in path.name for path in tmp_path.iterdir())


def test_compaction_of_an_already_unified_database(tmp_path):
    legacy = tmp_path / "legacy.db"
    unified = tmp_path / "unified.db"
    compact = tmp_path / "compact.db"
    _create_legacy_database(legacy)
    migrate_database(legacy, unified, compact=False)
    unified_hash = _sha256(unified)

    report = migrate_database(unified, compact, export_dir=tmp_path / "exports")

    assert _sha256(unified) == unified_hash
    assert report.stages == ("compact",)
    assert report.reconstruction_id_map == {} and report.indexing_id_map == {}
    assert report.migrated_counts == {"reconstruction_run": 1, "indexing_run": 2, "subjob": 7}
    assert report.compaction.export_directory == (tmp_path / "exports").resolve()
    assert (tmp_path / "exports" / "report.json").exists()
    assert "Verified row counts" not in report.format_text()
    with sqlite3.connect(compact) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        assert "subjob" not in tables
        assert connection.execute("SELECT SUM(n_inputs) FROM job").fetchone()[0] == 7

    with pytest.raises(MigrationError, match="already compacted"):
        migrate_database(compact, tmp_path / "again.db")
    with pytest.raises(MigrationError, match="only compaction remains"):
        migrate_database(unified, tmp_path / "again.db", compact=False)


def test_historical_queued_or_running_jobs_become_interrupted_not_runnable(tmp_path):
    source = tmp_path / "legacy.db"
    destination = tmp_path / "compact.db"
    _create_legacy_database(source, running_job=True)

    report = migrate_database(source, destination)

    assert report.compaction.interrupted_job_ids == (2,)
    assert any("job 2 was Running; classified as interrupted" in warning for warning in report.warnings)
    with sqlite3.connect(destination) as connection:
        connection.row_factory = sqlite3.Row
        job = connection.execute("SELECT * FROM job WHERE job_id = 2").fetchone()
        assert (job["status"], job["phase"]) == (JobStatus.FAILED, RunPhase.INTERRUPTED)
        assert (job["n_inputs"], job["n_succeeded"], job["n_failed"], job["n_not_run"]) == (2, 0, 0, 2)
        assert "Interrupted: recorded as Running" in job["messages"]
        assert job["updated_at"] == "2022-01-01 00:01:00.000000"
        assert connection.execute("SELECT COUNT(*) FROM job WHERE status IN (0, 1)").fetchone()[0] == 0
    compaction_job = next(job for job in report.compaction.jobs if job.job_id == 2)
    assert compaction_job.original_status == JobStatus.RUNNING
    records, _ = read_failure_report(compaction_job.failure_report)
    assert [(record.category, record.context["status"]) for record in records] == [
        ("interrupted", "Queued"),
        ("interrupted", "Queued"),
    ]


def test_compaction_refuses_subjobs_owned_outside_adopted_workflows(tmp_path):
    legacy = tmp_path / "legacy.db"
    unified = tmp_path / "unified.db"
    _create_legacy_database(legacy)
    migrate_database(legacy, unified, compact=False)
    with sqlite3.connect(unified) as connection:
        connection.execute("INSERT INTO job (job_id, computer_name, status, priority) VALUES (40, 'c', 2, 0)")
        connection.execute(
            "CREATE TABLE calib (calib_id INTEGER PRIMARY KEY, job_id INTEGER UNIQUE REFERENCES job(job_id))"
        )
        connection.execute("INSERT INTO calib (calib_id, job_id) VALUES (1, 40)")
        connection.execute(
            "INSERT INTO subjob (subjob_id, job_id, computer_name, status, priority) VALUES (99, 40, 'c', 2, 0)"
        )
    destination = tmp_path / "compact.db"

    with pytest.raises(MigrationError, match=r"job 40 \(1 rows, calibration\)"):
        migrate_database(unified, destination)

    assert not destination.exists()
    assert not default_export_directory(destination).exists()
    assert not any(".migrating" in path.name for path in tmp_path.iterdir())


def test_migration_refuses_to_overwrite_destination_or_export_directory(tmp_path):
    source = tmp_path / "legacy.db"
    destination = tmp_path / "existing.db"
    _create_legacy_database(source)
    destination.write_text("keep me")

    with pytest.raises(MigrationError, match="refusing to overwrite"):
        migrate_database(source, destination)
    assert destination.read_text() == "keep me"

    fresh = tmp_path / "fresh.db"
    default_export_directory(fresh).mkdir()
    with pytest.raises(MigrationError, match="Export directory already exists"):
        migrate_database(source, fresh)
    assert not fresh.exists()


def test_migration_rejects_ca_data_without_publishing_destination(tmp_path):
    source = tmp_path / "legacy-with-ca.db"
    destination = tmp_path / "migrated.db"
    _create_legacy_database(source, include_ca=True)
    source_hash = _sha256(source)

    with pytest.raises(MigrationError, match="Legacy CA reconstruction data is not supported"):
        migrate_database(source, destination)

    assert not destination.exists()
    assert not default_export_directory(destination).exists()
    assert _sha256(source) == source_hash


def test_compacted_database_gains_new_model_columns_by_upgrade(tmp_path):
    legacy = tmp_path / "legacy.db"
    compact = tmp_path / "compact.db"
    _create_legacy_database(legacy)
    migrate_database(legacy, compact)
    with sqlite3.connect(compact) as connection:
        connection.execute("ALTER TABLE indexing_run DROP COLUMN results_path")  # an older compaction
    upgraded = tmp_path / "upgraded.db"

    report = migrate_database(compact, upgraded)

    assert report.stages == ("upgrade",)
    assert report.added_columns == ("indexing_run.results_path",)
    assert report.compaction is None
    assert "added column indexing_run.results_path" in report.format_text()
    assert not default_export_directory(upgraded).exists()
    with sqlite3.connect(upgraded) as connection:
        assert _columns(connection, "indexing_run") == _fresh_schema_columns(tmp_path, "indexing_run")
        assert connection.execute("SELECT COUNT(*) FROM job").fetchone()[0] == 3
        assert connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    with pytest.raises(MigrationError, match="up to date"):
        migrate_database(upgraded, tmp_path / "again.db")


def test_upgrade_drops_an_empty_subjob_table_left_by_an_earlier_compaction(tmp_path):
    legacy = tmp_path / "legacy.db"
    compact = tmp_path / "compact.db"
    _create_legacy_database(legacy)
    migrate_database(legacy, compact)
    with sqlite3.connect(compact) as connection:
        connection.execute("CREATE TABLE subjob (subjob_id INTEGER PRIMARY KEY, job_id INTEGER, status INTEGER)")
    upgraded = tmp_path / "upgraded.db"

    report = migrate_database(compact, upgraded)

    assert report.stages == ("upgrade",)
    assert (report.added_columns, report.dropped_tables) == ((), ("subjob",))
    assert "dropped empty table subjob" in report.format_text()
    with sqlite3.connect(upgraded) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        assert "subjob" not in tables

    with sqlite3.connect(compact) as connection:
        connection.execute("INSERT INTO subjob (subjob_id, job_id, status) VALUES (1, 1, 2)")
    with pytest.raises(MigrationError, match="still holds 1 row"):
        migrate_database(compact, tmp_path / "refused.db")


def test_upgrade_relaxes_peak_limit_preserving_values_and_source(tmp_path):
    from laue_portal.database.models.indexing_run import LaueGoIndexingParameters
    from scripts.workflow_migration import _rebuild_table, required_nullable_columns

    legacy = tmp_path / "legacy.db"
    compact = tmp_path / "compact.db"
    _create_legacy_database(legacy)
    migrate_database(legacy, compact)
    metadata = MetaData()
    for source_table in LaueGoIndexingParameters.metadata.tables.values():
        source_table.to_metadata(metadata)
    table = metadata.tables["lauego_indexing_parameters"]
    table.c.max_number.nullable = False
    with sqlite3.connect(compact) as connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        _rebuild_table(connection, table, force=True)
        before = connection.execute("SELECT * FROM lauego_indexing_parameters").fetchall()
    upgraded = tmp_path / "upgraded.db"
    report = migrate_database(compact, upgraded)
    assert report.relaxed_columns == ("lauego_indexing_parameters.max_number",)
    assert "made nullable lauego_indexing_parameters.max_number" in report.format_text()
    with sqlite3.connect(upgraded) as connection:
        assert required_nullable_columns(connection) == []
        assert connection.execute("SELECT * FROM lauego_indexing_parameters").fetchall() == before
        connection.execute("UPDATE lauego_indexing_parameters SET max_number = NULL")
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    with sqlite3.connect(compact) as connection:
        assert required_nullable_columns(connection) == ["lauego_indexing_parameters.max_number"]
        assert connection.execute("SELECT * FROM lauego_indexing_parameters").fetchall() == before
