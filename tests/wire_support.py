"""A small deterministic 34-ID-E wire scan for exercising reconstruction end to end.

The layout follows lauelab's synthetic reconstruction input
(``tests/data/reconstruction/generate_reference.py`` in the library): stored
slice 0 is the intensity map, the wire vectors hold two more entries than
there are scan images, and the geometry is the library's
``geoN_2022-03-29_14-15-05.xml`` copied into ``tests/fixtures/lauelab``. The
image is 32 x 32 (64x binned) with 20 scan images so a run takes well under a
second. The spot switches off part-way through the sweep; the numbers are not
a physical simulation, only valid input for the reconstruction and indexing
paths the portal drives.
"""

from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np

GEOMETRY = Path(__file__).parent / "fixtures" / "lauelab" / "geoN_2022-03-29_14-15-05.xml"
FULL_PIXELS = 2048
BINNING = 64
N_SCAN_IMAGES = 20
WIRE_Y_UM = 1000.0
WIRE_Z_START_UM = -80.0
WIRE_Z_STEP_UM = 8.0

# Reconstructor options for these inputs: 11 depths from -25 to 25 µm.
OPTIONS = {
    "depth_start": -25.0,
    "depth_end": 25.0,
    "depth_resolution": 5.0,
    "percent_brightest": 100.0,
    "num_threads": 1,
    "memory_limit_mb": 256,
}
N_DEPTHS = 11


def write_wire_scan(path: str | Path, *, seed: int = 7, scan_number: int = 1) -> Path:
    """Write one wire-scan point file and return its path."""

    path = Path(path)
    n = FULL_PIXELS // BINNING
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:n, 0:n]
    spot = 3000.0 * np.exp(-((x - 16.0) ** 2 + (y - 14.0) ** 2) / (2.0 * 2.0**2))
    images = np.empty((N_SCAN_IMAGES + 1, n, n), dtype=np.uint16)
    for k in range(N_SCAN_IMAGES + 1):
        on = 1.0 if k == 0 or k < N_SCAN_IMAGES // 2 else 0.0
        images[k] = np.clip(rng.poisson(20.0 + on * spot), 0, 65535).astype(np.uint16)
    z = WIRE_Z_START_UM + WIRE_Z_STEP_UM * (np.arange(N_SCAN_IMAGES + 3, dtype=float) - 1.0)
    with h5py.File(path, "w") as f:
        entry = f.create_group("entry1")
        entry.create_group("data").create_dataset("data", data=images)
        entry.create_dataset("depth", data=np.array([0.0]))
        entry.create_dataset("scanNum", data=np.array([scan_number], dtype=np.int32))
        detector = entry.create_group("detector")
        for name, value in (
            ("Nx", FULL_PIXELS),
            ("Ny", FULL_PIXELS),
            ("startx", 0),
            ("starty", 0),
            ("endx", FULL_PIXELS - 1),
            ("endy", FULL_PIXELS - 1),
            ("binx", BINNING),
            ("biny", BINNING),
        ):
            detector.create_dataset(name, data=np.array([value], dtype=np.int32))
        detector.create_dataset("exposure", data=np.array([1.0]))
        detector.create_dataset("ID", data=np.array([b"PE1621 723-3335"], dtype="S15"))
        sample = entry.create_group("sample")
        sample.create_dataset("incident_energy", data=np.array([20.0]))
        for name, value in (("sampleX", 1.0), ("sampleY", 2.0), ("sampleZ", 3.0)):
            sample.create_dataset(name, data=np.array([value]))
        wire = entry.create_group("wire")
        wire.create_dataset("wireX", data=np.zeros_like(z))
        wire.create_dataset("wireY", data=np.full_like(z, WIRE_Y_UM))
        wire.create_dataset("wireZ", data=z)
        wire.create_dataset("wirescan", data=z)
    return path
