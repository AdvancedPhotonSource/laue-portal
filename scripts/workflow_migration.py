"""Standalone support for copying and migrating a legacy Laue Portal database.

The source database is opened read-only and copied with SQLite's backup API. The
copy is migrated in a temporary file and moved to the requested destination only
after all verification succeeds.
"""

import argparse
import os
import sqlite3
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.dialects import sqlite as sqlalchemy_sqlite
from sqlalchemy.schema import CreateIndex, CreateTable

from laue_portal.database.models.indexing_run import IndexingRun, LaueGoIndexingParameters
from laue_portal.database.models.reconstruction_run import ReconstructionRun, WireReconstructionParameters


class MigrationError(RuntimeError):
    """Raised when a database cannot be safely migrated."""


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

    def format_text(self) -> str:
        lines = [
            f"Source preserved: {self.source}",
            f"Migrated database: {self.destination}",
            "Verified row counts:",
            f"  wirerecon: {self.legacy_counts['wirerecon']} -> "
            f"reconstruction_run: {self.migrated_counts['reconstruction_run']}",
            f"  peakindex: {self.legacy_counts['peakindex']} -> indexing_run: {self.migrated_counts['indexing_run']}",
            f"  subjob: {self.legacy_counts['subjob']} -> {self.migrated_counts['subjob']}",
            "ID mappings:",
        ]
        lines.extend(f"  WR{legacy_id} -> R{new_id}" for legacy_id, new_id in self.reconstruction_id_map.items())
        lines.extend(f"  PI{legacy_id} -> I{new_id}" for legacy_id, new_id in self.indexing_id_map.items())
        if self.warnings:
            lines.append("Warnings:")
            lines.extend(f"  {warning}" for warning in self.warnings)
        else:
            lines.append("Warnings: none")
        return "\n".join(lines)


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


def _remove_temporary_database(path: Path) -> None:
    for candidate in (path, Path(f"{path}-wal"), Path(f"{path}-shm")):
        try:
            candidate.unlink()
        except FileNotFoundError:
            pass


def migrate_database(source: str | Path, destination: str | Path) -> MigrationReport:
    """Copy ``source`` and migrate the copy into a new ``destination`` file."""

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

    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination_path.name}.", suffix=".migrating", dir=destination_path.parent
    )
    os.close(file_descriptor)
    temporary_path = Path(temporary_name)
    try:
        source_uri = f"{source_path.as_uri()}?mode=ro"
        with sqlite3.connect(source_uri, uri=True) as source_connection:
            with sqlite3.connect(temporary_path) as destination_connection:
                source_connection.backup(destination_connection)

        reconstruction_id_map, indexing_id_map, counts, warnings = _migrate_copy(temporary_path)
        os.chmod(temporary_path, stat.S_IMODE(source_path.stat().st_mode))
        try:
            os.link(temporary_path, destination_path)
        except FileExistsError as error:
            raise MigrationError(
                f"Destination was created during migration; refusing to overwrite it: {destination_path}"
            ) from error
        _remove_temporary_database(temporary_path)
    except Exception:
        _remove_temporary_database(temporary_path)
        raise

    legacy_counts = {name: counts[name] for name in ("wirerecon", "recon", "peakindex", "job", "subjob")}
    migrated_counts = {name: counts[name] for name in ("reconstruction_run", "indexing_run", "subjob")}
    return MigrationReport(
        source=source_path,
        destination=destination_path,
        reconstruction_id_map=reconstruction_id_map,
        indexing_id_map=indexing_id_map,
        legacy_counts=legacy_counts,
        migrated_counts=migrated_counts,
        warnings=warnings,
    )


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Copy a legacy Laue Portal SQLite database and migrate the copy to the unified workflow schema."
    )
    parser.add_argument("source", type=Path, help="Existing legacy database; opened read-only and never modified")
    parser.add_argument("destination", type=Path, help="New database path; must not already exist")
    return parser


def main() -> int:
    args = _build_argument_parser().parse_args()
    try:
        report = migrate_database(args.source, args.destination)
    except MigrationError as error:
        raise SystemExit(f"Migration failed: {error}") from error
    print(report.format_text())
    return 0


if __name__ == "__main__":
    main()
