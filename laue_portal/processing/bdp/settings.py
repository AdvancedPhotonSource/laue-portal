"""Explicit storage mappings and independently deployable launcher settings."""

from __future__ import annotations

import os
from pathlib import PurePosixPath

import yaml


def load_settings(path):
    with open(path, encoding="utf-8") as handle:
        settings = yaml.safe_load(handle)
    if not isinstance(settings, dict):
        raise ValueError("BDP settings must be a YAML mapping")
    return settings


def portal_settings(values=None):
    if values is None:
        from laue_portal.config import BDP

        values = BDP
    if values.get("enabled") and values.get("settings_file"):
        return {**load_settings(values["settings_file"]), "enabled": True}
    return values


def child_path(root, path):
    """Reject prefix lookalikes, parent traversal, and symlinks leaving the root."""
    from pathlib import Path

    root, path = Path(root).resolve(), Path(path).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError(f"{path} must be inside {root}")
    return path


def collection_path(storage, path):
    relative = child_path(storage["filesystem_root"], path).relative_to(os.path.realpath(storage["filesystem_root"]))
    return str(PurePosixPath(storage["collection_root"]) / relative.as_posix())


def map_path(path, mappings):
    """Translate an absolute path with the longest matching directory prefix."""
    p = PurePosixPath(path)
    for source, destination in sorted(mappings.items(), key=lambda pair: len(pair[0]), reverse=True):
        try:
            relative = p.relative_to(source)
        except ValueError:
            continue
        return str(PurePosixPath(destination) / relative)
    raise ValueError(f"No storage mapping for {path}")


def available_backends(settings=None):
    settings = portal_settings(settings)
    targets = settings.get("targets", {}) if settings.get("enabled") else {}
    # APS has one UI choice. Redis serves it until the DM target is enabled.
    aps_backend = "aps" if targets.get("aps", {}).get("enabled", False) else "local"
    options = [{"label": "APS", "value": aps_backend}]
    if targets.get("crux", {}).get("enabled", False):
        options.append({"label": "ALCF", "value": "crux"})
    return options


def execution_computer(backend, settings=None):
    """Use private display names without embedding deployment hostnames in source."""
    from laue_portal.config import DEFAULT_VARIABLES

    default = DEFAULT_VARIABLES.get("computer_name") if backend in {"local", "aps"} else None
    if backend == "local":
        value = default
    else:
        value = portal_settings(settings).get("targets", {}).get(backend, {}).get("computer_name") or default
    fallback = {"local": "APS", "aps": "APS", "crux": "ALCF"}.get(backend, backend)
    return str(value or "").strip() or fallback


def require_backend(name, settings=None):
    if name not in {item["value"] for item in available_backends(settings)}:
        raise ValueError(f"Execution target {name!r} is not enabled")
