"""Tests for migration from a test-only legacy SQLite schema."""

import hashlib
import sqlite3
import stat
from pathlib import Path

import pytest

from scripts.workflow_migration import MigrationError, migrate_database


def _sqlite_type(column: str, value) -> str:
    integer_columns = {
        "scanNumber",
        "job_id",
        "subjob_id",
        "wirerecon_id",
        "recon_id",
        "peakindex_id",
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


def _create_legacy_database(path: Path, include_ca: bool = False) -> None:
    metadata = {"scanNumber": 1}
    job = {
        "job_id": 1,
        "computer_name": "TEST_COMPUTER",
        "status": 2,
        "priority": 5,
        "submit_time": "2022-01-01 00:00:00.000000",
        "start_time": "2022-01-01 00:01:00.000000",
        "finish_time": "2022-01-01 00:02:00.000000",
        "messages": "legacy job",
    }
    subjob = {
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
    wire = _legacy_wire_row()
    indexing = _legacy_indexing_row(7, 2, 10)
    direct_indexing = _legacy_indexing_row(9, 3, None)
    recon = {"recon_id": 4, "job_id": 4}

    with sqlite3.connect(path) as connection:
        _create_table(connection, "metadata", metadata, "scanNumber")
        _create_table(connection, "job", job, "job_id")
        _create_table(connection, "subjob", subjob, "subjob_id")
        _create_table(connection, "wirerecon", wire, "wirerecon_id")
        _create_table(connection, "recon", recon, "recon_id")
        _create_table(connection, "peakindex", indexing, "peakindex_id")
        _insert(connection, "metadata", metadata)
        for job_id in range(1, 5 if include_ca else 4):
            _insert(connection, "job", {**job, "job_id": job_id})
        _insert(connection, "wirerecon", wire)
        _insert(connection, "peakindex", indexing)
        _insert(connection, "peakindex", direct_indexing)
        if include_ca:
            _insert(connection, "recon", recon)
        for subjob_id, job_id in enumerate((1, 2, 3), start=1):
            _insert(connection, "subjob", {**subjob, "subjob_id": subjob_id, "job_id": job_id})


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_migration_copies_source_and_verifies_unified_data(tmp_path):
    source = tmp_path / "legacy.db"
    destination = tmp_path / "migrated.db"
    _create_legacy_database(source)
    source_hash = _sha256(source)

    report = migrate_database(source, destination)

    assert destination.exists()
    assert _sha256(source) == source_hash
    assert stat.S_IMODE(destination.stat().st_mode) == stat.S_IMODE(source.stat().st_mode)
    assert report.reconstruction_id_map == {10: 1}
    assert report.indexing_id_map == {7: 7, 9: 9}
    assert report.legacy_counts["subjob"] == 3
    assert report.migrated_counts == {"reconstruction_run": 1, "indexing_run": 2, "subjob": 3}

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
        assert [tuple(row) for row in connection.execute("SELECT input_path, output_path FROM subjob").fetchall()] == [
            (None, None),
            (None, None),
            (None, None),
        ]
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


def test_migration_refuses_to_overwrite_destination(tmp_path):
    source = tmp_path / "legacy.db"
    destination = tmp_path / "existing.db"
    _create_legacy_database(source)
    destination.write_text("keep me")

    with pytest.raises(MigrationError, match="refusing to overwrite"):
        migrate_database(source, destination)

    assert destination.read_text() == "keep me"


def test_migration_rejects_ca_data_without_publishing_destination(tmp_path):
    source = tmp_path / "legacy-with-ca.db"
    destination = tmp_path / "migrated.db"
    _create_legacy_database(source, include_ca=True)
    source_hash = _sha256(source)

    with pytest.raises(MigrationError, match="Legacy CA reconstruction data is not supported"):
        migrate_database(source, destination)

    assert not destination.exists()
    assert _sha256(source) == source_hash
