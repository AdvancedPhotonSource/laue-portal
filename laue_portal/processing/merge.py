"""Combine reconstruction catalogs and link closed point files without rereading pixels.

Indexing HDF5 and XML merging belongs to lauelab's public merge APIs.
"""

from __future__ import annotations

import os
from pathlib import Path

import h5py


def merge_reconstruction(catalogs, destination, entries):
    from lauelab.reconstruct import validate_scan_file
    from lauelab.reconstruct._scan_layout import POINT_COLUMNS, SCAN_DATASETS, PointStatus, RunStatus
    from lauelab.reconstruct._scan_writer import write_catalog

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    points_directory = destination.parent / "points"
    points_directory.mkdir()
    rows = {}
    template = None
    for catalog in map(Path, catalogs):
        summary = validate_scan_file(catalog)
        if summary.n_complete != summary.n_points:
            raise ValueError("Only complete reconstruction shards can be merged")
        with h5py.File(catalog, "r") as source:
            if template is None:
                template = {
                    "created": source.attrs["created"],
                    "native_version": source.attrs["native_version"],
                    "parameters": {name: source[name][()] for name in SCAN_DATASETS if name.startswith("/parameters/")},
                    "geometry_path": source["geometry"].attrs["path"],
                    "geometry_xml": source["geometry/xml"].asstr()[()],
                }
            columns = {
                name: source[name].asstr()[:] if spec.dtype.kind == "O" else source[name][:]
                for name, spec in POINT_COLUMNS.items()
            }
            for i, point_id in enumerate(columns["/points/point_ids"]):
                if point_id in rows:
                    raise ValueError(f"Duplicate reconstructed point: {point_id}")
                row = {name: values[i] for name, values in columns.items()}
                point_path = (catalog.parent / row["/points/paths"]).resolve()
                if not point_path.is_relative_to(catalog.parent.resolve()):
                    raise ValueError("Point file leaves its shard directory")
                if row["/points/statuses"] != PointStatus.COMPLETE:
                    raise ValueError("Incomplete point in reconstruction merge")
                target = points_directory / point_path.name
                os.link(point_path, target)  # Exclusive and on the same Eagle filesystem.
                row["/points/paths"] = target.relative_to(destination.parent).as_posix()
                rows[point_id] = row
    if set(rows) != {entry.input_id for entry in entries}:
        raise ValueError("Reconstruction shards do not exactly cover the manifest")
    # The library's per-rank point index becomes the original global manifest index.
    for entry in entries:
        path = destination.parent / rows[entry.input_id]["/points/paths"]
        with h5py.File(path, "r+") as point:
            point["entry1/reconstruction/manifest_index"][...] = entry.index
    points = {name: [rows[entry.input_id][name] for entry in entries] for name in POINT_COLUMNS}
    write_catalog(destination, **template, run_status=RunStatus.FINISHED, points=points, replace=False)
    return validate_scan_file(destination)
