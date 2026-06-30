"""Detector image loading for the pixel-space detector view.

The indexing XML stores the source detector file in ``<inputImage>``.  In
practice that value may be absolute, relative to the indexing output folder,
or relative to the original data folder stored on the PeakIndex record.  This
module resolves those common locations and loads a 2-D HDF5 dataset for use as
an image background.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import h5py
import numpy as np

_DEFAULT_DATASETS = (
    "/entry1/data/data",
    "entry1/data/data",
    "/entry/data/data",
    "entry/data/data",
    "/data",
    "data",
)


@dataclass
class DetectorImage:
    """Loaded detector image and provenance metadata."""

    data: np.ndarray
    path: str
    dataset: str
    vmin: float
    vmax: float


@dataclass
class DetectorImageResult:
    """Result object that preserves warnings for the detector summary."""

    image: DetectorImage | None = None
    warning: str | None = None
    attempted_paths: tuple[str, ...] = ()


def load_detector_image(
    input_image: str | None,
    *,
    xml_path: str | None = None,
    data_folder: str | None = None,
    root_path: str | None = None,
    dataset_paths: Iterable[str] = _DEFAULT_DATASETS,
) -> DetectorImageResult:
    """Resolve and load the detector image referenced by an indexing step.

    Parameters
    ----------
    input_image:
        Value from the XML ``<inputImage>`` element.
    xml_path:
        Current indexing XML path.  Used to resolve paths relative to the
        output folder.
    data_folder:
        Original PeakIndex data folder from the DB.  Used when the XML stores
        only a detector filename.
    root_path:
        Portal workspace root from configuration.  Used for DB-relative paths.
    dataset_paths:
        Candidate HDF5 datasets to try in order.
    """
    if not input_image:
        return DetectorImageResult(warning="No inputImage is recorded for this step.")

    candidates = _candidate_paths(input_image, xml_path=xml_path, data_folder=data_folder, root_path=root_path)
    if not candidates:
        return DetectorImageResult(warning=f"Could not resolve detector image path: {input_image!r}.")

    attempted = tuple(str(path) for path in candidates)
    image_path = next((path for path in candidates if path.is_file()), None)
    if image_path is None:
        return DetectorImageResult(
            warning="Detector image file was not found. Tried: " + ", ".join(attempted),
            attempted_paths=attempted,
        )

    try:
        data, dataset = _read_hdf5_image(image_path, dataset_paths)
    except Exception as exc:
        return DetectorImageResult(
            warning=f"Could not load detector image {image_path}: {exc}",
            attempted_paths=attempted,
        )

    if data.ndim != 2:
        return DetectorImageResult(
            warning=f"Detector image dataset {dataset} in {image_path} is {data.ndim}D, expected 2D.",
            attempted_paths=attempted,
        )

    finite = data[np.isfinite(data)]
    if finite.size:
        vmin = float(np.nanpercentile(finite, 1.0))
        vmax = float(np.nanpercentile(finite, 99.5))
        if not np.isfinite(vmin) or not np.isfinite(vmax) or vmin == vmax:
            vmin = float(np.nanmin(finite))
            vmax = float(np.nanmax(finite))
    else:
        vmin, vmax = 0.0, 1.0

    return DetectorImageResult(
        image=DetectorImage(data=data, path=str(image_path), dataset=dataset, vmin=vmin, vmax=vmax),
        attempted_paths=attempted,
    )


def _candidate_paths(
    input_image: str,
    *,
    xml_path: str | None,
    data_folder: str | None,
    root_path: str | None,
) -> list[Path]:
    raw = Path(str(input_image).strip())
    candidates: list[Path] = []

    def add(path: Path) -> None:
        expanded = path.expanduser()
        if expanded not in candidates:
            candidates.append(expanded)

    if raw.is_absolute():
        add(raw)
    else:
        if xml_path:
            add(Path(xml_path).expanduser().resolve().parent / raw)
        if data_folder:
            data_path = Path(data_folder).expanduser()
            add(data_path / raw)
            if root_path and not data_path.is_absolute():
                add(Path(root_path).expanduser() / data_path / raw)
        if root_path:
            add(Path(root_path).expanduser() / raw)
        add(raw)

    return candidates


def _read_hdf5_image(path: Path, dataset_paths: Iterable[str]) -> tuple[np.ndarray, str]:
    with h5py.File(path, "r") as h5:
        for dataset_path in dataset_paths:
            key = str(dataset_path).strip()
            if not key:
                continue
            lookup = key[1:] if key.startswith("/") else key
            if lookup in h5:
                data = np.asarray(h5[lookup][()])
                return _coerce_image_2d(data), key

        found = _first_2d_dataset(h5)
        if found is not None:
            dataset, data = found
            return _coerce_image_2d(data), dataset

        raise KeyError("no 2-D detector image dataset found")


def _first_2d_dataset(group, prefix: str = "") -> tuple[str, np.ndarray] | None:
    for name, item in group.items():
        path = f"{prefix}/{name}"
        if isinstance(item, h5py.Dataset):
            if item.ndim >= 2:
                return path, np.asarray(item[()])
        elif isinstance(item, h5py.Group):
            found = _first_2d_dataset(item, path)
            if found is not None:
                return found
    return None


def _coerce_image_2d(data: np.ndarray) -> np.ndarray:
    data = np.asarray(data)
    while data.ndim > 2:
        data = data[0]
    if not np.issubdtype(data.dtype, np.number):
        raise TypeError(f"detector dataset has non-numeric dtype {data.dtype}")
    return data.astype(float, copy=False)
