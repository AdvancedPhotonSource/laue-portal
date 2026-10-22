"""Read-only DAQ selection and binding; acquisition remains owned by DM."""

from pathlib import Path, PurePosixPath

from laue_portal import config
from laue_portal.processing.bdp.dm import DMClient

MANUAL = "notifications"


def dm_client():
    settings = config.LIVE.get("dm", {})
    if not settings.get("enabled"):
        raise ValueError("DM live arrivals are not configured")
    return DMClient(settings)


def daq_summary(record):
    """Only expose acquisition metadata, never authentication settings."""
    return {
        key: record.get(key)
        for key in ("id", "experimentName", "dataDirectory", "storageDirectory", "destDirectory", "status")
    }


def list_daqs():
    if not config.LIVE.get("dm", {}).get("enabled"):
        return []
    return [daq_summary(record) for record in dm_client().daqs()]


def destination_root(record):
    base = Path(record.get("storageDirectory") or "")
    suffix = PurePosixPath(record.get("destDirectory") or ".")
    if not base.is_absolute() or suffix.is_absolute() or ".." in suffix.parts:
        raise ValueError("DAQ has an invalid destination directory")
    return (base / suffix).resolve()


def bind_daq(identifier, input_directory, *, client=None):
    if not identifier or identifier == MANUAL:
        return None
    record = (client or dm_client()).daq(identifier)
    if str(record.get("status")).lower() != "running":
        raise ValueError("Select a running DAQ")
    source = Path(input_directory).resolve(strict=True)
    destination = destination_root(record)
    if not source.is_relative_to(destination):
        raise ValueError(f"Input folder must be inside the DAQ destination: {destination}")
    storage = Path(record["storageDirectory"]).resolve()
    return {
        "kind": "dm_catalog",
        "daq_id": str(record["id"]),
        "experiment": str(record["experimentName"]),
        "source_directory": record["dataDirectory"],
        "storage_directory": str(storage),
        "destination_directory": str(destination),
        "relative_directory": source.relative_to(storage).as_posix(),
        "input_directory": str(source),
    }
