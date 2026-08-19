"""Tests for the non-destructive workflow database migration."""

import hashlib
import sqlite3
import stat
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from laue_portal.database import db_schema
from scripts.workflow_migration import MigrationError, migrate_database
from tests.conftest import (
    create_test_job,
    create_test_metadata,
    create_test_peakindex,
    create_test_recon,
)

LEGACY_TABLES = [
    db_schema.Metadata.__table__,
    db_schema.Job.__table__,
    db_schema.SubJob.__table__,
    db_schema.Calib.__table__,
    db_schema.Recon.__table__,
    db_schema.WireRecon.__table__,
    db_schema.PeakIndex.__table__,
]


def _create_legacy_database(path: Path, include_ca: bool = False) -> None:
    engine = create_engine(f"sqlite:///{path}")
    db_schema.Base.metadata.create_all(engine, tables=LEGACY_TABLES)
    with engine.begin() as connection:
        connection.exec_driver_sql("ALTER TABLE subjob DROP COLUMN input_path")
        connection.exec_driver_sql("ALTER TABLE subjob DROP COLUMN output_path")
    with Session(engine) as session:
        metadata = create_test_metadata()
        wire_job = create_test_job(1)
        index_job = create_test_job(2)
        direct_index_job = create_test_job(3)
        wire = db_schema.WireRecon(
            wirerecon_id=10,
            scanNumber=1,
            job_id=1,
            filefolder="/legacy/wire/input",
            filenamePrefix=["wire_*.h5"],
            author="wire user",
            notes="wire notes",
            geoFile="/legacy/wire/geometry.xml",
            percent_brightest=5.0,
            wire_edges="0 1",
            depth_start=-5.0,
            depth_end=5.0,
            depth_resolution=0.25,
            num_threads=8,
            memory_limit_mb=2048,
            scanPoints="1-2",
            scanPointslen=2,
            outputFolder="/legacy/wire/output",
            verbose=1,
        )
        indexing = create_test_peakindex(1)
        indexing.peakindex_id = 7
        indexing.job_id = 2
        indexing.scanNumber = None
        indexing.recon_id = None
        indexing.wirerecon_id = 10
        indexing.outputXML = "merged.xml"
        direct_indexing = create_test_peakindex(1)
        direct_indexing.peakindex_id = 9
        direct_indexing.job_id = 3
        direct_indexing.scanNumber = None
        direct_indexing.recon_id = None
        direct_indexing.wirerecon_id = None
        session.add_all([metadata, wire_job, index_job, direct_index_job, wire, indexing, direct_indexing])
        if include_ca:
            ca_job = create_test_job(4)
            ca = create_test_recon()
            ca.recon_id = 4
            ca.job_id = 4
            session.add_all([ca_job, ca])
        session.commit()
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            INSERT INTO subjob (subjob_id, job_id, computer_name, status, priority)
            VALUES (1, 1, 'TEST_COMPUTER', 2, 5),
                   (2, 2, 'TEST_COMPUTER', 2, 5),
                   (3, 3, 'TEST_COMPUTER', 2, 5)
            """
        )
    engine.dispose()


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
    assert report.migrated_counts == {
        "reconstruction_run": 1,
        "indexing_run": 2,
        "subjob": 3,
    }

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
        reconstruction = connection.execute("SELECT * FROM reconstruction_run").fetchone()
        assert dict(reconstruction) == {
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
        assert indexing["id"] == 7
        assert indexing["scan_number"] == 1
        assert indexing["reconstruction_id"] == 1
        assert indexing["method"] == "lauego"
        parameters = connection.execute(
            "SELECT filename_prefixes, output_xml FROM lauego_indexing_parameters"
        ).fetchone()
        assert parameters["filename_prefixes"] == '["test_file"]'
        assert parameters["output_xml"] == "merged.xml"
        direct_indexing = connection.execute(
            "SELECT scan_number, reconstruction_id FROM indexing_run WHERE id = 9"
        ).fetchone()
        assert tuple(direct_indexing) == (None, None)
        assert "I9 (formerly PI9) has no scan number" in report.warnings
        subjob_paths = connection.execute("SELECT input_path, output_path FROM subjob ORDER BY subjob_id").fetchall()
        assert [tuple(row) for row in subjob_paths] == [
            (None, None),
            (None, None),
            (None, None),
        ]
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
