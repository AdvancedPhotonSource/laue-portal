"""Standalone support for copying and migrating a Laue Portal database.

The source database is opened read-only and copied with SQLite's backup API. The
copy is migrated in a temporary file and moved to the requested destination only
after all verification succeeds. Two stages exist:

1. legacy -> unified: the peakindex/wirerecon tables become the unified run
   tables. Its verification asserts that the subjob table is unchanged.
2. unified -> compact: per-input SubJob rows are aggregated into run counters
   on the job table, diagnostics are exported next to the destination, and the
   rows and then the subjob table are removed after verification.

A legacy source runs both stages; a unified source runs only the second. An
already compacted source gets the ``upgrade`` stage: missing nullable columns
are added and an empty leftover subjob table is dropped.
"""

import argparse
import contextlib
import json
import os
import shutil
import sqlite3
import stat
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import MetaData
from sqlalchemy.dialects import sqlite as sqlalchemy_sqlite
from sqlalchemy.schema import CreateColumn, CreateIndex, CreateTable

from laue_portal.database.models.indexing_run import IndexingRun, LaueGoIndexingParameters
from laue_portal.database.models.job import Job
from laue_portal.database.models.reconstruction_run import ReconstructionRun, WireReconstructionParameters
from laue_portal.workflows.execution import STATUS_NAMES, JobStatus, RunPhase
from laue_portal.workflows.manifest import (
    CATEGORY_CANCELLED,
    CATEGORY_ERROR,
    CATEGORY_INTERRUPTED,
    FAILURE_REPORT_FILENAME,
    input_identity,
)


class MigrationError(RuntimeError):
    """Raised when a database cannot be safely migrated."""


@dataclass(frozen=True)
class JobCompaction:
    """Run counters derived from one job's SubJob rows."""

    job_id: int
    original_status: int
    status: int
    phase: str
    n_inputs: int
    n_succeeded: int
    n_failed: int
    n_not_run: int
    failure_report: str | None


@dataclass(frozen=True)
class CompactionReport:
    """Results of the SubJob compaction stage."""

    jobs: tuple[JobCompaction, ...]
    subjobs_removed: int
    interrupted_job_ids: tuple[int, ...]
    export_directory: Path
    calibration_subjobs: int

    def totals(self) -> dict[str, int]:
        return {
            "jobs": len(self.jobs),
            "n_inputs": sum(job.n_inputs for job in self.jobs),
            "n_succeeded": sum(job.n_succeeded for job in self.jobs),
            "n_failed": sum(job.n_failed for job in self.jobs),
            "n_not_run": sum(job.n_not_run for job in self.jobs),
            "failure_reports": sum(1 for job in self.jobs if job.failure_report),
        }


@dataclass(frozen=True)
class MigrationReport:
    """Verification results and identifier mappings from a migration."""

    source: Path
    destination: Path
    reconstruction_id_map: dict[int, int]
    indexing_id_map: dict[int, int]
    legacy_counts: dict[str, int]
    migrated_counts: dict[str, int]
    warnings: tuple[str, ...]
    stages: tuple[str, ...] = ("legacy",)
    compaction: CompactionReport | None = None
    added_columns: tuple[str, ...] = ()
    dropped_tables: tuple[str, ...] = ()
    relaxed_columns: tuple[str, ...] = ()

    def format_text(self) -> str:
        lines = [
            f"Source preserved: {self.source}",
            f"Migrated database: {self.destination}",
            f"Stages: {', '.join(self.stages)}",
        ]
        if "legacy" in self.stages:
            lines.extend(
                [
                    "Verified row counts:",
                    f"  wirerecon: {self.legacy_counts['wirerecon']} -> "
                    f"reconstruction_run: {self.migrated_counts['reconstruction_run']}",
                    f"  peakindex: {self.legacy_counts['peakindex']} -> "
                    f"indexing_run: {self.migrated_counts['indexing_run']}",
                    f"  subjob: {self.legacy_counts['subjob']} -> {self.migrated_counts['subjob']}",
                    "ID mappings:",
                ]
            )
            lines.extend(f"  WR{legacy_id} -> R{new_id}" for legacy_id, new_id in self.reconstruction_id_map.items())
            lines.extend(f"  PI{legacy_id} -> I{new_id}" for legacy_id, new_id in self.indexing_id_map.items())
        if self.compaction is not None:
            totals = self.compaction.totals()
            interrupted = ", ".join(f"job {job_id}" for job_id in self.compaction.interrupted_job_ids) or "none"
            lines.extend(
                [
                    "Compaction:",
                    f"  jobs: {totals['jobs']}; subjob rows removed: {self.compaction.subjobs_removed}",
                    f"  counters: inputs {totals['n_inputs']}, succeeded {totals['n_succeeded']}, "
                    f"failed {totals['n_failed']}, not run {totals['n_not_run']}",
                    f"  interrupted (were Queued/Running): {interrupted}",
                    f"  calibration-owned subjob rows: {self.compaction.calibration_subjobs}",
                    f"  diagnostics exported to: {self.compaction.export_directory} "
                    f"({totals['failure_reports']} failure reports)",
                ]
            )
        if "upgrade" in self.stages:
            lines.append("Schema upgrade:")
            lines.extend(f"  added column {name}" for name in self.added_columns)
            lines.extend(f"  made nullable {name}" for name in self.relaxed_columns)
            lines.extend(f"  dropped empty table {name}" for name in self.dropped_tables)
        if self.warnings:
            lines.append("Warnings:")
            lines.extend(f"  {warning}" for warning in self.warnings)
        else:
            lines.append("Warnings: none")
        return "\n".join(lines)

    def as_json(self) -> dict:
        document = {
            "source": os.fspath(self.source),
            "destination": os.fspath(self.destination),
            "stages": list(self.stages),
            "reconstruction_id_map": {str(k): v for k, v in self.reconstruction_id_map.items()},
            "indexing_id_map": {str(k): v for k, v in self.indexing_id_map.items()},
            "legacy_counts": self.legacy_counts,
            "migrated_counts": self.migrated_counts,
            "warnings": list(self.warnings),
            "added_columns": list(self.added_columns),
            "dropped_tables": list(self.dropped_tables),
            "relaxed_columns": list(self.relaxed_columns),
        }
        if self.compaction is not None:
            document["compaction"] = {
                "export_directory": os.fspath(self.compaction.export_directory),
                "subjobs_removed": self.compaction.subjobs_removed,
                "interrupted_job_ids": list(self.compaction.interrupted_job_ids),
                "calibration_subjobs": self.compaction.calibration_subjobs,
                "totals": self.compaction.totals(),
                "jobs": [asdict(job) for job in self.compaction.jobs],
            }
        return document


_REQUIRED_LEGACY_COLUMNS = {
    "metadata": {"scanNumber"},
    "job": {"job_id", "submit_time"},
    "subjob": {
        "subjob_id",
        "job_id",
        "computer_name",
        "status",
        "priority",
        "start_time",
        "finish_time",
        "messages",
        "command",
    },
    "wirerecon": {
        "wirerecon_id",
        "scanNumber",
        "job_id",
        "filefolder",
        "filenamePrefix",
        "author",
        "notes",
        "geoFile",
        "percent_brightest",
        "wire_edges",
        "depth_start",
        "depth_end",
        "depth_resolution",
        "num_threads",
        "memory_limit_mb",
        "scanPoints",
        "scanPointslen",
        "outputFolder",
        "verbose",
    },
    "recon": {"recon_id", "job_id"},
    "peakindex": {
        "peakindex_id",
        "scanNumber",
        "job_id",
        "filefolder",
        "filenamePrefix",
        "author",
        "notes",
        "recon_id",
        "wirerecon_id",
        "threshold",
        "thresholdRatio",
        "maxRfactor",
        "boxsize",
        "max_number",
        "min_separation",
        "peakShape",
        "scanPoints",
        "scanPointslen",
        "depthRange",
        "depthRangelen",
        "detectorCropX1",
        "detectorCropX2",
        "detectorCropY1",
        "detectorCropY2",
        "min_size",
        "max_peaks",
        "smooth",
        "maskFile",
        "indexKeVmaxCalc",
        "indexKeVmaxTest",
        "indexAngleTolerance",
        "indexH",
        "indexK",
        "indexL",
        "indexCone",
        "energyUnit",
        "exposureUnit",
        "cosmicFilter",
        "recipLatticeUnit",
        "latticeParametersUnit",
        "outputFolder",
        "outputXML",
        "geoFile",
        "crystFile",
        "depth",
        "beamline",
    },
}

_TARGET_TABLES = (
    ReconstructionRun.__table__,
    WireReconstructionParameters.__table__,
    IndexingRun.__table__,
    LaueGoIndexingParameters.__table__,
)


def _table_names(connection: sqlite3.Connection) -> set[str]:
    return {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def _column_names(connection: sqlite3.Connection, table_name: str) -> set[str]:
    return {row[1] for row in connection.execute(f'PRAGMA table_info("{table_name}")')}


def _scalar(connection: sqlite3.Connection, query: str, parameters=()) -> int:
    row = connection.execute(query, parameters).fetchone()
    if row is None:
        raise MigrationError(f"Validation query returned no result: {query}")
    return int(row[0])


def _validate_legacy_schema(connection: sqlite3.Connection) -> dict[str, int]:
    existing_tables = _table_names(connection)
    target_names = {table.name for table in _TARGET_TABLES}
    already_present = target_names & existing_tables
    if already_present:
        names = ", ".join(sorted(already_present))
        raise MigrationError(f"Database is not a supported legacy schema; target tables already exist: {names}")

    missing_tables = set(_REQUIRED_LEGACY_COLUMNS) - existing_tables
    if missing_tables:
        names = ", ".join(sorted(missing_tables))
        raise MigrationError(f"Database is not a supported legacy schema; missing tables: {names}")

    for table_name, required_columns in _REQUIRED_LEGACY_COLUMNS.items():
        missing_columns = required_columns - _column_names(connection, table_name)
        if missing_columns:
            names = ", ".join(sorted(missing_columns))
            raise MigrationError(f"Legacy table {table_name} is missing required columns: {names}")

    subjob_columns = _column_names(connection, "subjob")
    unexpected_path_columns = {"input_path", "output_path"} & subjob_columns
    if unexpected_path_columns:
        names = ", ".join(sorted(unexpected_path_columns))
        raise MigrationError(f"Legacy subjob table already contains target columns: {names}")

    counts = {
        table_name: _scalar(connection, f'SELECT COUNT(*) FROM "{table_name}"')
        for table_name in ("wirerecon", "recon", "peakindex", "job", "subjob")
    }
    if counts["recon"]:
        raise MigrationError(f"Legacy CA reconstruction data is not supported: found {counts['recon']} row(s) in recon")

    if _scalar(
        connection,
        "SELECT COUNT(*) FROM peakindex WHERE recon_id IS NOT NULL AND wirerecon_id IS NOT NULL",
    ):
        raise MigrationError("A legacy indexing row references both reconstruction types")

    if _scalar(connection, "SELECT COUNT(*) FROM peakindex WHERE recon_id IS NOT NULL"):
        raise MigrationError("A legacy indexing row references unsupported CA reconstruction data")

    missing_jobs_or_times = _scalar(
        connection,
        """
        SELECT COUNT(*)
        FROM (
            SELECT w.job_id
            FROM wirerecon AS w
            LEFT JOIN job AS j ON j.job_id = w.job_id
            WHERE j.job_id IS NULL OR j.submit_time IS NULL
            UNION ALL
            SELECT p.job_id
            FROM peakindex AS p
            LEFT JOIN job AS j ON j.job_id = p.job_id
            WHERE j.job_id IS NULL OR j.submit_time IS NULL
        )
        """,
    )
    if missing_jobs_or_times:
        raise MigrationError(
            f"Cannot populate created_at: {missing_jobs_or_times} processing run(s) have no job submission time"
        )

    duplicate_job_ids = connection.execute(
        """
        SELECT job_id
        FROM (
            SELECT job_id FROM wirerecon
            UNION ALL
            SELECT job_id FROM peakindex
        )
        GROUP BY job_id
        HAVING COUNT(*) > 1
        ORDER BY job_id
        """
    ).fetchall()
    if duplicate_job_ids:
        ids = ", ".join(str(row[0]) for row in duplicate_job_ids)
        raise MigrationError(f"Processing jobs are reused by more than one legacy run: {ids}")

    missing_wire_parents = _scalar(
        connection,
        """
        SELECT COUNT(*)
        FROM peakindex AS p
        LEFT JOIN wirerecon AS w ON w.wirerecon_id = p.wirerecon_id
        WHERE p.wirerecon_id IS NOT NULL AND w.wirerecon_id IS NULL
        """,
    )
    if missing_wire_parents:
        raise MigrationError(f"Found {missing_wire_parents} indexing row(s) with a missing wire parent")

    conflicting_scans = _scalar(
        connection,
        """
        SELECT COUNT(*)
        FROM peakindex AS p
        JOIN wirerecon AS w ON w.wirerecon_id = p.wirerecon_id
        WHERE p.scanNumber IS NOT NULL
          AND w.scanNumber IS NOT NULL
          AND p.scanNumber != w.scanNumber
        """,
    )
    if conflicting_scans:
        raise MigrationError(
            f"Found {conflicting_scans} indexing row(s) whose scan disagrees with the reconstruction scan"
        )

    foreign_key_issues = connection.execute("PRAGMA foreign_key_check").fetchall()
    if foreign_key_issues:
        raise MigrationError(f"Legacy database has {len(foreign_key_issues)} foreign-key violation(s)")

    return counts


def _create_target_tables(connection: sqlite3.Connection) -> None:
    dialect = sqlalchemy_sqlite.dialect()
    for table in _TARGET_TABLES:
        connection.execute(str(CreateTable(table).compile(dialect=dialect)))
        for index in sorted(table.indexes, key=lambda item: item.name or ""):
            connection.execute(str(CreateIndex(index).compile(dialect=dialect)))


def _insert(connection: sqlite3.Connection, table_name: str, values: dict) -> None:
    columns = ", ".join(f'"{column}"' for column in values)
    placeholders = ", ".join("?" for _ in values)
    connection.execute(
        f'INSERT INTO "{table_name}" ({columns}) VALUES ({placeholders})',
        tuple(values.values()),
    )


def _migrate_reconstructions(connection: sqlite3.Connection, warnings: list[str]) -> dict[int, int]:
    rows = connection.execute(
        """
        SELECT w.*, j.submit_time AS created_at
        FROM wirerecon AS w
        JOIN job AS j ON j.job_id = w.job_id
        ORDER BY w.wirerecon_id
        """
    ).fetchall()
    id_map: dict[int, int] = {}
    for new_id, row in enumerate(rows, start=1):
        legacy_id = row["wirerecon_id"]
        id_map[legacy_id] = new_id
        _insert(
            connection,
            "reconstruction_run",
            {
                "id": new_id,
                "scan_number": row["scanNumber"],
                "job_id": row["job_id"],
                "method": "wire",
                "input_path": row["filefolder"],
                "output_path": row["outputFolder"],
                "author": row["author"],
                "notes": row["notes"],
                "algorithm_version": None,
                "created_at": row["created_at"],
            },
        )
        _insert(
            connection,
            "wire_reconstruction_parameters",
            {
                "reconstruction_id": new_id,
                "filename_prefixes": row["filenamePrefix"],
                "geometry_file": row["geoFile"],
                "percent_brightest": row["percent_brightest"],
                "wire_edges": row["wire_edges"],
                "depth_start": row["depth_start"],
                "depth_end": row["depth_end"],
                "depth_resolution": row["depth_resolution"],
                "num_threads": row["num_threads"],
                "memory_limit_mb": row["memory_limit_mb"],
                "scan_points": row["scanPoints"],
                "scan_points_len": row["scanPointslen"],
                "verbose": row["verbose"],
            },
        )
        if row["scanNumber"] is None:
            warnings.append(f"R{new_id} (formerly WR{legacy_id}) has no scan number")
    return id_map


def _migrate_indexing(
    connection: sqlite3.Connection,
    reconstruction_id_map: dict[int, int],
    warnings: list[str],
) -> dict[int, int]:
    reconstruction_scans = {
        row["id"]: row["scan_number"] for row in connection.execute("SELECT id, scan_number FROM reconstruction_run")
    }
    rows = connection.execute(
        """
        SELECT p.*, j.submit_time AS created_at
        FROM peakindex AS p
        JOIN job AS j ON j.job_id = p.job_id
        ORDER BY p.peakindex_id
        """
    ).fetchall()
    id_map: dict[int, int] = {}
    for row in rows:
        legacy_id = row["peakindex_id"]
        new_id = legacy_id
        id_map[legacy_id] = new_id
        reconstruction_id = None
        if row["wirerecon_id"] is not None:
            reconstruction_id = reconstruction_id_map[row["wirerecon_id"]]

        scan_number = row["scanNumber"]
        if scan_number is None and reconstruction_id is not None:
            scan_number = reconstruction_scans[reconstruction_id]

        _insert(
            connection,
            "indexing_run",
            {
                "id": new_id,
                "scan_number": scan_number,
                "reconstruction_id": reconstruction_id,
                "job_id": row["job_id"],
                "method": "lauego",
                "input_path": row["filefolder"],
                "output_path": row["outputFolder"],
                "author": row["author"],
                "notes": row["notes"],
                "algorithm_version": None,
                "created_at": row["created_at"],
            },
        )
        _insert(
            connection,
            "lauego_indexing_parameters",
            {
                "indexing_id": new_id,
                "filename_prefixes": row["filenamePrefix"],
                "threshold": row["threshold"],
                "threshold_ratio": row["thresholdRatio"],
                "max_rfactor": row["maxRfactor"],
                "box_size": row["boxsize"],
                "max_number": row["max_number"],
                "min_separation": row["min_separation"],
                "peak_shape": row["peakShape"],
                "scan_points": row["scanPoints"],
                "scan_points_len": row["scanPointslen"],
                "depth_range": row["depthRange"],
                "depth_range_len": row["depthRangelen"],
                "detector_crop_x1": row["detectorCropX1"],
                "detector_crop_x2": row["detectorCropX2"],
                "detector_crop_y1": row["detectorCropY1"],
                "detector_crop_y2": row["detectorCropY2"],
                "min_size": row["min_size"],
                "max_peaks": row["max_peaks"],
                "smooth": row["smooth"],
                "mask_file": row["maskFile"],
                "index_kev_max_calc": row["indexKeVmaxCalc"],
                "index_kev_max_test": row["indexKeVmaxTest"],
                "index_angle_tolerance": row["indexAngleTolerance"],
                "index_h": row["indexH"],
                "index_k": row["indexK"],
                "index_l": row["indexL"],
                "index_cone": row["indexCone"],
                "energy_unit": row["energyUnit"],
                "exposure_unit": row["exposureUnit"],
                "cosmic_filter": row["cosmicFilter"],
                "reciprocal_lattice_unit": row["recipLatticeUnit"],
                "lattice_parameters_unit": row["latticeParametersUnit"],
                "output_xml": row["outputXML"],
                "geometry_file": row["geoFile"],
                "crystal_file": row["crystFile"],
                "depth": row["depth"],
                "beamline": row["beamline"],
            },
        )
        if scan_number is None:
            warnings.append(f"I{new_id} (formerly PI{legacy_id}) has no scan number")
    return id_map


def _verify_migration(connection: sqlite3.Connection, legacy_counts: dict[str, int]) -> dict[str, int]:
    migrated_counts = {
        table_name: _scalar(connection, f'SELECT COUNT(*) FROM "{table_name}"')
        for table_name in (
            "reconstruction_run",
            "wire_reconstruction_parameters",
            "indexing_run",
            "lauego_indexing_parameters",
            "subjob",
        )
    }
    expected_counts = {
        "reconstruction_run": legacy_counts["wirerecon"],
        "wire_reconstruction_parameters": legacy_counts["wirerecon"],
        "indexing_run": legacy_counts["peakindex"],
        "lauego_indexing_parameters": legacy_counts["peakindex"],
        "subjob": legacy_counts["subjob"],
    }
    if migrated_counts != expected_counts:
        raise MigrationError(
            f"Migrated row-count verification failed: expected {expected_counts}, found {migrated_counts}"
        )

    if _scalar(connection, "SELECT COUNT(*) FROM reconstruction_run WHERE method != 'wire'"):
        raise MigrationError("Migrated reconstruction methods failed verification")
    if _scalar(connection, "SELECT COUNT(*) FROM indexing_run WHERE method != 'lauego'"):
        raise MigrationError("Migrated indexing methods failed verification")

    foreign_key_issues = connection.execute("PRAGMA foreign_key_check").fetchall()
    if foreign_key_issues:
        raise MigrationError(f"Migrated database has {len(foreign_key_issues)} foreign-key violation(s)")
    integrity_result = connection.execute("PRAGMA integrity_check").fetchone()
    if integrity_result is None or integrity_result[0] != "ok":
        raise MigrationError(f"SQLite integrity check failed: {integrity_result}")
    return migrated_counts


def _migrate_copy(database_path: Path) -> tuple[dict, dict, dict, tuple[str, ...]]:
    warnings: list[str] = []
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        legacy_counts = _validate_legacy_schema(connection)
        connection.execute("BEGIN IMMEDIATE")
        _create_target_tables(connection)
        connection.execute("ALTER TABLE subjob ADD COLUMN input_path VARCHAR")
        connection.execute("ALTER TABLE subjob ADD COLUMN output_path VARCHAR")
        reconstruction_id_map = _migrate_reconstructions(connection, warnings)
        indexing_id_map = _migrate_indexing(connection, reconstruction_id_map, warnings)
        migrated_counts = _verify_migration(connection, legacy_counts)

        connection.execute("DROP TABLE peakindex")
        connection.execute("DROP TABLE recon")
        connection.execute("DROP TABLE wirerecon")
        connection.commit()

        foreign_key_issues = connection.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_key_issues:
            raise MigrationError(
                f"Migrated database has {len(foreign_key_issues)} foreign-key violation(s) after legacy cleanup"
            )
        connection.execute("VACUUM")
        journal_mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
        if str(journal_mode).lower() != "wal":
            raise MigrationError(f"Could not enable WAL journal mode; SQLite returned {journal_mode!r}")
        return (
            reconstruction_id_map,
            indexing_id_map,
            {**legacy_counts, **migrated_counts},
            tuple(warnings),
        )
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


# --- compaction stage ---------------------------------------------------------

_UNIFIED_TABLES = {
    "job",
    "indexing_run",
    "lauego_indexing_parameters",
    "reconstruction_run",
    "wire_reconstruction_parameters",
}
_LEGACY_TABLES = {"peakindex", "wirerecon", "recon"}
_PHASE_FOR_STATUS = {
    JobStatus.FINISHED: RunPhase.FINISHED,
    JobStatus.FAILED: RunPhase.FAILED,
    JobStatus.CANCELLED: RunPhase.CANCELLED,
}
_HISTORY_FILENAME = "history.json"
_REPORT_FILENAME = "report.json"


def detect_schema_stage(connection: sqlite3.Connection) -> str:
    """Return ``legacy``, ``unified``, or ``compact`` for the database behind ``connection``."""

    tables = _table_names(connection)
    if _LEGACY_TABLES & tables:
        return "legacy"
    if not _UNIFIED_TABLES <= tables:
        missing = ", ".join(sorted(_UNIFIED_TABLES - tables))
        raise MigrationError(f"Database is not a supported Laue Portal schema; missing tables: {missing}")
    if "n_inputs" in _column_names(connection, "job"):
        return "compact"
    if "subjob" not in tables:
        raise MigrationError("Database is not a supported Laue Portal schema; missing tables: subjob")
    return "unified"


def _validate_unified_schema(connection: sqlite3.Connection) -> None:
    stage = detect_schema_stage(connection)
    if stage == "compact":
        raise MigrationError("Database is already compacted; the job table has run counters")
    if stage != "unified":
        raise MigrationError(f"Compaction needs the unified schema; found {stage}")
    subjob_columns = _column_names(connection, "subjob")
    missing = {"input_path", "output_path", "status", "job_id", "messages", "command"} - subjob_columns
    if missing:
        raise MigrationError(f"Unified subjob table is missing columns: {', '.join(sorted(missing))}")
    foreign_key_issues = connection.execute("PRAGMA foreign_key_check").fetchall()
    if foreign_key_issues:
        raise MigrationError(f"Database has {len(foreign_key_issues)} foreign-key violation(s) before compaction")


def _audit_subjob_owners(connection: sqlite3.Connection) -> int:
    """Refuse to compact when any SubJob row belongs to a job outside the adopted workflows."""

    has_calibration = "calib" in _table_names(connection)
    calibration_test = "EXISTS(SELECT 1 FROM calib AS c WHERE c.job_id = s.job_id)" if has_calibration else "0"
    foreign = connection.execute(
        f"""
        SELECT s.job_id, COUNT(*) AS n, {calibration_test} AS is_calibration
        FROM subjob AS s
        WHERE s.job_id NOT IN (SELECT job_id FROM indexing_run)
          AND s.job_id NOT IN (SELECT job_id FROM reconstruction_run)
        GROUP BY s.job_id
        ORDER BY s.job_id
        """
    ).fetchall()
    if foreign:
        owners = ", ".join(
            f"job {row['job_id']} ({row['n']} rows{', calibration' if row['is_calibration'] else ''})"
            for row in foreign
        )
        raise MigrationError(
            f"Refusing to compact: subjob rows belong to jobs outside the adopted indexing/reconstruction "
            f"workflows: {owners}"
        )
    if not has_calibration:
        return 0
    return _scalar(connection, "SELECT COUNT(*) FROM subjob WHERE job_id IN (SELECT job_id FROM calib)")


def _rebuild_table(connection: sqlite3.Connection, table, *, force: bool = False) -> list[str]:
    """Recreate ``table`` with the ORM definition, copying the columns that already exist.

    SQLite cannot add table-level constraints with ALTER TABLE, so this follows
    the documented recreate-copy-drop-rename recipe. Foreign keys must already
    be disabled on the connection and the caller owns the transaction.
    """

    existing = _column_names(connection, table.name)
    added = [column.name for column in table.columns if column.name not in existing]
    if not added and not force:
        return []
    temporary_name = f"_{table.name}_compacting"
    dialect = sqlalchemy_sqlite.dialect()
    metadata = MetaData()
    for source_table in table.metadata.tables.values():
        source_table.to_metadata(metadata)
    replacement = table.to_metadata(metadata, name=temporary_name)
    connection.execute(str(CreateTable(replacement).compile(dialect=dialect)))
    common = ", ".join(f'"{column.name}"' for column in table.columns if column.name in existing)
    connection.execute(f'INSERT INTO "{temporary_name}" ({common}) SELECT {common} FROM "{table.name}"')
    connection.execute(f'DROP TABLE "{table.name}"')
    connection.execute(f'ALTER TABLE "{temporary_name}" RENAME TO "{table.name}"')
    for index in sorted(table.indexes, key=lambda item: item.name or ""):
        connection.execute(str(CreateIndex(index).compile(dialect=dialect)))
    return added


def _add_missing_columns(connection: sqlite3.Connection, table) -> list[str]:
    existing = _column_names(connection, table.name)
    dialect = sqlalchemy_sqlite.dialect()
    added = []
    for column in table.columns:
        if column.name in existing:
            continue
        specification = str(CreateColumn(column).compile(dialect=dialect))
        connection.execute(f'ALTER TABLE "{table.name}" ADD COLUMN {specification}')
        added.append(column.name)
    return added


def _message_class(message: str | None) -> str:
    if not message:
        return "(none)"
    first_line = message.strip().splitlines()[0]
    for prefix in ("IndexingResult(success=True", "IndexingResult(success=False"):
        if first_line.startswith(prefix):
            return prefix + ")"
    return first_line[:80]


def _failure_category(status: int, message: str | None) -> str:
    if status == JobStatus.CANCELLED:
        return CATEGORY_CANCELLED
    if status in (JobStatus.QUEUED, JobStatus.RUNNING):
        return CATEGORY_INTERRUPTED
    if message and message.startswith("Marked as failed: stale job"):
        return CATEGORY_INTERRUPTED
    return CATEGORY_ERROR


def _export_job_diagnostics(
    connection: sqlite3.Connection, export_dir: Path, job_row, counters: dict, *, final_export_dir: Path | None = None
) -> tuple[str | None, dict]:
    """Write ``failures.jsonl`` and ``history.json`` for one job; return the failure report path."""

    job_id = job_row["job_id"]
    job_dir = export_dir / "jobs" / f"job_{job_id}"
    job_dir.mkdir(parents=True, exist_ok=True)
    failure_path = job_dir / FAILURE_REPORT_FILENAME
    message_classes: dict[str, int] = {}
    representative_command = None
    exported = 0
    with open(failure_path, "w", encoding="utf-8", newline="\n") as handle:
        rows = connection.execute(
            """
            SELECT subjob_id, status, computer_name, input_path, output_path, start_time, finish_time,
                   messages, command
            FROM subjob WHERE job_id = ? ORDER BY subjob_id
            """,
            (job_id,),
        )
        for row in rows:
            message = row["messages"]
            klass = _message_class(message)
            message_classes[klass] = message_classes.get(klass, 0) + 1
            if representative_command is None and row["command"]:
                representative_command = row["command"]
            if row["status"] == JobStatus.FINISHED:
                continue
            record = {
                "index": None,
                "input_id": input_identity(row["input_path"]) if row["input_path"] else None,
                "source": row["input_path"],
                "category": _failure_category(row["status"], message),
                "message": message or "",
                "error_type": None,
                "context": {
                    "subjob_id": row["subjob_id"],
                    "status": STATUS_NAMES.get(row["status"], str(row["status"])),
                    "computer_name": row["computer_name"],
                    "output_path": row["output_path"],
                    "command": row["command"],
                    "start_time": row["start_time"],
                    "finish_time": row["finish_time"],
                },
                "recorded_at": row["finish_time"] or row["start_time"],
            }
            handle.write(json.dumps(record, separators=(",", ":"), ensure_ascii=False) + "\n")
            exported += 1
    if exported == 0:
        failure_path.unlink()
        failure_report = None
    else:
        recorded_dir = final_export_dir or export_dir
        failure_report = os.fspath(recorded_dir / failure_path.relative_to(export_dir))
    history = {
        "job_id": job_id,
        "original_status": job_row["status"],
        "original_status_name": STATUS_NAMES.get(job_row["status"], str(job_row["status"])),
        "submit_time": job_row["submit_time"],
        "start_time": job_row["start_time"],
        "finish_time": job_row["finish_time"],
        "messages": job_row["messages"],
        "counters": counters,
        "subjob_time_range": [counters.pop("_first_start"), counters.pop("_last_finish")],
        "representative_command": representative_command,
        "message_classes": message_classes,
        "failure_report": failure_report,
    }
    history["counters"] = dict(counters)
    with open(job_dir / _HISTORY_FILENAME, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(history, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return failure_report, history


def _count_lines(path: str) -> int:
    with open(path, "rb") as handle:
        return sum(1 for _ in handle)


def _compact_copy(
    database_path: Path, export_dir: Path, warnings: list[str], *, final_export_dir: Path | None = None
) -> CompactionReport:
    """Aggregate SubJob rows into job counters, export diagnostics, and remove the rows.

    Files are written under ``export_dir``; paths stored in the database and report
    refer to ``final_export_dir`` (the directory ``export_dir`` will be renamed to).
    """

    final_export_dir = final_export_dir or export_dir

    migrated_at = datetime.now().isoformat(timespec="seconds")
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys=OFF")  # required by the table rebuild; checked explicitly below
        _validate_unified_schema(connection)
        calibration_subjobs = _audit_subjob_owners(connection)
        subjobs_before = _scalar(connection, "SELECT COUNT(*) FROM subjob")

        connection.execute("BEGIN IMMEDIATE")
        _rebuild_table(connection, Job.__table__)
        _add_missing_columns(connection, IndexingRun.__table__)
        if required_nullable_columns(connection):
            for table in _orm_tables():
                if table.name == "lauego_indexing_parameters":
                    _rebuild_table(connection, table, force=True)

        run_directories = {
            row["job_id"]: row["output_path"]
            for row in connection.execute(
                "SELECT job_id, output_path FROM indexing_run UNION ALL SELECT job_id, output_path FROM reconstruction_run"
            )
        }
        statistics = {
            row["job_id"]: row
            for row in connection.execute(
                """
                SELECT job_id, COUNT(*) AS n,
                       SUM(status = 2) AS finished, SUM(status = 3) AS failed, SUM(status = 4) AS cancelled,
                       SUM(status = 0) AS queued, SUM(status = 1) AS running,
                       MIN(start_time) AS first_start, MAX(finish_time) AS last_finish
                FROM subjob GROUP BY job_id
                """
            )
        }
        jobs = connection.execute(
            "SELECT job_id, status, submit_time, start_time, finish_time, messages FROM job ORDER BY job_id"
        ).fetchall()

        compactions = []
        interrupted = []
        for job_row in jobs:
            job_id = job_row["job_id"]
            stat_row = statistics.get(job_id)
            n_inputs = stat_row["n"] if stat_row else 0
            n_succeeded = stat_row["finished"] if stat_row else 0
            n_failed = stat_row["failed"] if stat_row else 0
            n_not_run = (stat_row["cancelled"] + stat_row["queued"] + stat_row["running"]) if stat_row else 0
            if n_succeeded + n_failed + n_not_run != n_inputs:
                raise MigrationError(f"Job {job_id} has subjob rows with an unknown status")

            original_status = job_row["status"]
            status = original_status
            messages = job_row["messages"]
            try:
                phase = _PHASE_FOR_STATUS[JobStatus(original_status)]
            except (KeyError, ValueError):
                phase = None
            if original_status in (JobStatus.QUEUED, JobStatus.RUNNING):
                status = int(JobStatus.FAILED)
                phase = RunPhase.INTERRUPTED
                note = (
                    f"Interrupted: recorded as {STATUS_NAMES[JobStatus(original_status)]} when the database was "
                    f"migrated on {migrated_at}; historical work is not re-run"
                )
                messages = f"{messages}\n{note}" if messages else note
                interrupted.append(job_id)
                warnings.append(
                    f"job {job_id} was {STATUS_NAMES[JobStatus(original_status)]}; classified as interrupted"
                )
            elif phase is None:
                raise MigrationError(f"Job {job_id} has an unknown status {original_status}")

            counters = {
                "n_inputs": n_inputs,
                "n_succeeded": n_succeeded,
                "n_failed": n_failed,
                "n_not_run": n_not_run,
                "_first_start": stat_row["first_start"] if stat_row else None,
                "_last_finish": stat_row["last_finish"] if stat_row else None,
            }
            failure_report = None
            if stat_row is not None:
                failure_report, _ = _export_job_diagnostics(
                    connection, export_dir, job_row, counters, final_export_dir=final_export_dir
                )
            updated_at = job_row["finish_time"] or job_row["start_time"] or job_row["submit_time"]
            connection.execute(
                """
                UPDATE job
                SET status = ?, phase = ?, updated_at = ?, messages = ?,
                    n_inputs = ?, n_succeeded = ?, n_failed = ?, n_not_run = ?,
                    run_directory = ?, failure_report_path = ?
                WHERE job_id = ?
                """,
                (
                    status,
                    str(phase),
                    updated_at,
                    messages,
                    n_inputs,
                    n_succeeded,
                    n_failed,
                    n_not_run,
                    run_directories.get(job_id),
                    failure_report,
                    job_id,
                ),
            )
            compactions.append(
                JobCompaction(
                    job_id=job_id,
                    original_status=original_status,
                    status=status,
                    phase=str(phase),
                    n_inputs=n_inputs,
                    n_succeeded=n_succeeded,
                    n_failed=n_failed,
                    n_not_run=n_not_run,
                    failure_report=failure_report,
                )
            )

        # Verification before any row is removed.
        if sum(job.n_inputs for job in compactions) != subjobs_before:
            raise MigrationError("Compaction counters do not account for every subjob row")
        for job in compactions:
            if job.n_succeeded + job.n_failed + job.n_not_run != job.n_inputs:
                raise MigrationError(f"Job {job.job_id} counters are inconsistent")
            expected_failures = job.n_failed + job.n_not_run
            exported = (
                _count_lines(os.fspath(export_dir / Path(job.failure_report).relative_to(final_export_dir)))
                if job.failure_report
                else 0
            )
            if exported != expected_failures:
                raise MigrationError(
                    f"Job {job.job_id} exported {exported} failure records but has {expected_failures} non-finished inputs"
                )
        stored = connection.execute(
            "SELECT job_id, n_inputs, n_succeeded, n_failed, n_not_run FROM job ORDER BY job_id"
        ).fetchall()
        if [tuple(row) for row in stored] != [
            (job.job_id, job.n_inputs, job.n_succeeded, job.n_failed, job.n_not_run) for job in compactions
        ]:
            raise MigrationError("Stored job counters do not match the computed compaction")
        if _scalar(connection, "SELECT COUNT(*) FROM job WHERE status IN (0, 1)"):
            raise MigrationError("A job is still Queued/Running after interrupted-run classification")

        connection.execute("DELETE FROM subjob")
        if _scalar(connection, "SELECT COUNT(*) FROM subjob"):
            raise MigrationError("Subjob rows remain after compaction")
        connection.execute("DROP TABLE subjob")
        if "subjob" in _table_names(connection):
            raise MigrationError("The subjob table remains after compaction")
        foreign_key_issues = connection.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_key_issues:
            raise MigrationError(f"Compacted database has {len(foreign_key_issues)} foreign-key violation(s)")
        connection.commit()

        connection.execute("PRAGMA foreign_keys=ON")
        integrity_result = connection.execute("PRAGMA integrity_check").fetchone()
        if integrity_result is None or integrity_result[0] != "ok":
            raise MigrationError(f"SQLite integrity check failed after compaction: {integrity_result}")
        connection.execute("VACUUM")
        journal_mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
        if str(journal_mode).lower() != "wal":
            raise MigrationError(f"Could not enable WAL journal mode; SQLite returned {journal_mode!r}")
        return CompactionReport(
            jobs=tuple(compactions),
            subjobs_removed=subjobs_before,
            interrupted_job_ids=tuple(interrupted),
            export_directory=final_export_dir,
            calibration_subjobs=calibration_subjobs,
        )
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


# Tables this migration owns; scan metadata, catalog, and calibration tables are outside its scope.
_WORKFLOW_TABLES = _UNIFIED_TABLES | {"lauego_indexing_parameters", "wire_reconstruction_parameters"}


def _orm_tables():
    import laue_portal.database.models  # noqa: F401  registers every model on Base.metadata
    from laue_portal.database.base import Base

    return [table for table in Base.metadata.sorted_tables if table.name in _WORKFLOW_TABLES]


def missing_columns(connection: sqlite3.Connection) -> list[str]:
    """``table.column`` names the ORM defines but the database lacks, for existing tables."""

    existing_tables = _table_names(connection)
    missing = []
    for table in _orm_tables():
        if table.name not in existing_tables:
            continue
        present = _column_names(connection, table.name)
        missing.extend(f"{table.name}.{column.name}" for column in table.columns if column.name not in present)
    return missing


def required_nullable_columns(connection: sqlite3.Connection) -> list[str]:
    """Known constraints that must be relaxed to accept the current form contract."""
    return [
        "lauego_indexing_parameters.max_number"
        for row in connection.execute('PRAGMA table_info("lauego_indexing_parameters")')
        if row[1] == "max_number" and row[3]
    ]


def _drop_empty_subjob_table(connection: sqlite3.Connection) -> list[str]:
    """Drop the per-input table left by an earlier compaction; refuse if it still holds rows."""

    if "subjob" not in _table_names(connection):
        return []
    remaining = _scalar(connection, "SELECT COUNT(*) FROM subjob")
    if remaining:
        raise MigrationError(f"The subjob table still holds {remaining} row(s); compaction did not finish")
    connection.execute("DROP TABLE subjob")
    return ["subjob"]


def _upgrade_copy(database_path: Path) -> tuple[list[str], list[str], list[str]]:
    """Bring an already compacted copy up to the current ORM: add nullable columns, drop the empty subjob table.

    Returns ``(added_columns, dropped_tables, relaxed_columns)``.
    """

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys=OFF")  # checked after the table rebuild
        before = missing_columns(connection)
        relaxed = required_nullable_columns(connection)
        leftover_subjob = "subjob" in _table_names(connection)
        if not before and not leftover_subjob and not relaxed:
            return [], [], []
        connection.execute("BEGIN IMMEDIATE")
        existing_tables = _table_names(connection)
        for table in _orm_tables():
            if table.name in existing_tables:
                for column in table.columns:
                    if column.name not in _column_names(connection, table.name) and not column.nullable:
                        raise MigrationError(
                            f"Cannot add NOT NULL column {table.name}.{column.name} by upgrade; a new compaction stage is needed"
                        )
                _add_missing_columns(connection, table)
                if relaxed and table.name == "lauego_indexing_parameters":
                    _rebuild_table(connection, table, force=True)
        remaining = missing_columns(connection)
        if remaining:
            raise MigrationError(f"Schema upgrade left columns missing: {', '.join(remaining)}")
        dropped = _drop_empty_subjob_table(connection)
        foreign_key_issues = connection.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_key_issues:
            raise MigrationError(f"Upgraded database has {len(foreign_key_issues)} foreign-key violation(s)")
        connection.commit()
        integrity_result = connection.execute("PRAGMA integrity_check").fetchone()
        if integrity_result is None or integrity_result[0] != "ok":
            raise MigrationError(f"SQLite integrity check failed after upgrade: {integrity_result}")
        if dropped:
            connection.execute("VACUUM")
        journal_mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
        if str(journal_mode).lower() != "wal":
            raise MigrationError(f"Could not enable WAL journal mode; SQLite returned {journal_mode!r}")
        return before, dropped, relaxed
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _unified_counts(database_path: Path) -> dict[str, int]:
    with contextlib.closing(sqlite3.connect(database_path)) as connection:
        tables = _table_names(connection)
        return {
            table_name: _scalar(connection, f'SELECT COUNT(*) FROM "{table_name}"')
            for table_name in ("reconstruction_run", "indexing_run", "subjob")
            if table_name in tables
        }


def _checkpoint_copy(database_path: Path) -> None:
    """Fold the WAL into the main file so the published file alone is complete."""

    with contextlib.closing(sqlite3.connect(database_path)) as connection:
        busy, log_frames, checkpointed = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        if busy or log_frames != checkpointed:
            raise MigrationError(
                f"Could not checkpoint the migrated copy (busy={busy}, frames={log_frames}, done={checkpointed})"
            )
    wal = Path(f"{database_path}-wal")
    if wal.exists() and wal.stat().st_size:
        raise MigrationError("The migrated copy still has write-ahead-log content after checkpointing")


def _remove_temporary_database(path: Path) -> None:
    for candidate in (path, Path(f"{path}-wal"), Path(f"{path}-shm")):
        try:
            candidate.unlink()
        except FileNotFoundError:
            pass


def default_export_directory(destination: str | Path) -> Path:
    destination = Path(destination)
    return destination.with_name(destination.name + ".migration")


def migrate_database(
    source: str | Path,
    destination: str | Path,
    *,
    compact: bool = True,
    export_dir: str | Path | None = None,
) -> MigrationReport:
    """Copy ``source`` and migrate the copy into a new ``destination`` file.

    A legacy source is first migrated to the unified schema. With ``compact``
    (the default) the SubJob rows are then aggregated into run counters and
    their diagnostics exported to ``export_dir`` (default ``<destination>.migration``).
    """

    source_path = Path(source).expanduser().resolve()
    destination_path = Path(destination).expanduser().resolve()
    if not source_path.is_file():
        raise MigrationError(f"Source database does not exist or is not a file: {source_path}")
    if source_path == destination_path:
        raise MigrationError("Source and destination must be different files")
    if destination_path.exists():
        raise MigrationError(f"Destination already exists; refusing to overwrite it: {destination_path}")
    if not destination_path.parent.is_dir():
        raise MigrationError(f"Destination directory does not exist: {destination_path.parent}")
    export_path = None
    if compact:
        export_path = (
            Path(export_dir).expanduser().resolve()
            if export_dir is not None
            else default_export_directory(destination_path)
        )
        if export_path.exists():
            raise MigrationError(f"Export directory already exists; refusing to overwrite it: {export_path}")
        if not export_path.parent.is_dir():
            raise MigrationError(f"Export directory parent does not exist: {export_path.parent}")

    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination_path.name}.", suffix=".migrating", dir=destination_path.parent
    )
    os.close(file_descriptor)
    temporary_path = Path(temporary_name)
    temporary_export = None
    try:
        source_uri = f"{source_path.as_uri()}?mode=ro"
        with sqlite3.connect(source_uri, uri=True) as source_connection:
            with sqlite3.connect(temporary_path) as destination_connection:
                source_connection.backup(destination_connection)

        with contextlib.closing(sqlite3.connect(temporary_path)) as probe:
            stage = detect_schema_stage(probe)
        if stage == "unified" and not compact:
            raise MigrationError("Source database already has the unified schema; only compaction remains")

        stages: list[str] = []
        warnings: list[str] = []
        reconstruction_id_map: dict[int, int] = {}
        indexing_id_map: dict[int, int] = {}
        legacy_counts: dict[str, int] = {}
        added_columns: list[str] = []
        dropped_tables: list[str] = []
        relaxed_columns: list[str] = []
        if stage == "compact":
            added_columns, dropped_tables, relaxed_columns = _upgrade_copy(temporary_path)
            if not added_columns and not dropped_tables and not relaxed_columns:
                raise MigrationError("Source database is already compacted and up to date; nothing to migrate")
            stages.append("upgrade")
            compact = False  # counters already exist; only the schema changed
        if stage == "legacy":
            reconstruction_id_map, indexing_id_map, counts, legacy_warnings = _migrate_copy(temporary_path)
            warnings.extend(legacy_warnings)
            legacy_counts = {name: counts[name] for name in ("wirerecon", "recon", "peakindex", "job", "subjob")}
            stages.append("legacy")
        migrated_counts = _unified_counts(temporary_path)

        compaction = None
        if compact:
            temporary_export = Path(
                tempfile.mkdtemp(prefix=f".{export_path.name}.", suffix=".migrating", dir=export_path.parent)
            )
            compaction = _compact_copy(temporary_path, temporary_export, warnings, final_export_dir=export_path)
            stages.append("compact")

        report = MigrationReport(
            source=source_path,
            destination=destination_path,
            reconstruction_id_map=reconstruction_id_map,
            indexing_id_map=indexing_id_map,
            legacy_counts=legacy_counts,
            migrated_counts=migrated_counts,
            warnings=tuple(warnings),
            stages=tuple(stages),
            compaction=compaction,
            added_columns=tuple(added_columns),
            dropped_tables=tuple(dropped_tables),
            relaxed_columns=tuple(relaxed_columns),
        )
        if temporary_export is not None:
            with open(temporary_export / _REPORT_FILENAME, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(report.as_json(), handle, indent=2, sort_keys=True)
                handle.write("\n")
            os.chmod(temporary_export, stat.S_IMODE(export_path.parent.stat().st_mode))
            os.rename(temporary_export, export_path)  # fails if export_path appeared meanwhile
            temporary_export = None

        _checkpoint_copy(temporary_path)
        os.chmod(temporary_path, stat.S_IMODE(source_path.stat().st_mode))
        try:
            os.link(temporary_path, destination_path)
        except FileExistsError as error:
            if export_path is not None:
                shutil.rmtree(export_path, ignore_errors=True)
            raise MigrationError(
                f"Destination was created during migration; refusing to overwrite it: {destination_path}"
            ) from error
        _remove_temporary_database(temporary_path)
    except Exception:
        _remove_temporary_database(temporary_path)
        if temporary_export is not None:
            shutil.rmtree(temporary_export, ignore_errors=True)
        raise
    return report


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Copy a Laue Portal SQLite database and migrate the copy: legacy schemas become the unified "
            "workflow schema, per-input SubJob rows are compacted into run counters, and an already "
            "compacted database gains any columns the current models define."
        )
    )
    parser.add_argument("source", type=Path, help="Existing database; opened read-only and never modified")
    parser.add_argument("destination", type=Path, help="New database path; must not already exist")
    parser.add_argument(
        "--no-compact",
        action="store_true",
        help="Stop after the legacy-to-unified stage and keep SubJob rows (legacy sources only)",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=None,
        help="Where compaction writes report.json and per-job diagnostics (default: <destination>.migration)",
    )
    return parser


def main() -> int:
    args = _build_argument_parser().parse_args()
    try:
        report = migrate_database(
            args.source, args.destination, compact=not args.no_compact, export_dir=args.export_dir
        )
    except MigrationError as error:
        raise SystemExit(f"Migration failed: {error}") from error
    print(report.format_text())
    return 0


if __name__ == "__main__":
    main()
