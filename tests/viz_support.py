"""Shared fixtures for visualization tests: a real native results file from the synthetic frames."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from lauelab.indexing import Indexer, IndexParams, PeakParams, XmlResultsWriter
from lauelab.visualization import load_results

FIXTURES = Path(__file__).parent / "fixtures" / "lauelab"
GEOMETRY = FIXTURES / "geoN_2022-03-29_14-15-05.xml"
CRYSTAL = FIXTURES / "Ni.xml"
FRAMES = ("synthetic_ni_grain_a.h5", "synthetic_ni_two_grains.h5", "synthetic_ni_empty.h5", "synthetic_ni_grain_a.h5")

PEAKS = PeakParams(
    boxsize=18, max_rfactor=0.5, min_size=3, min_separation=20, threshold=None, threshold_ratio=4.0, max_peaks=200
)
INDEXING = IndexParams(
    kev_max_calc=17.2, kev_max_test=35.0, angle_tolerance_deg=0.1, cone_deg=72.0, hkl_prefer=(0, 0, 1), max_data=300
)


def write_synthetic_results(directory: Path) -> tuple[Path, Path]:
    """Index the synthetic frames natively into ``output.h5`` and ``output.xml`` under ``directory``.

    Frames get sample positions on a 2 x 2 grid so spatial maps have coordinates. The
    third frame has no pattern, so scopes with unindexed frames are exercised.
    """

    directory.mkdir(parents=True, exist_ok=True)
    frames_dir = directory / "frames"
    frames_dir.mkdir(exist_ok=True)
    indexer = Indexer(str(GEOMETRY), str(CRYSTAL), peak_params=PEAKS, index_params=INDEXING)
    results_path = directory / "output.h5"
    xml_path = directory / "output.xml"
    positions = [(0.0, 0.0, 10.0), (5.0, 0.0, 10.0), (0.0, 5.0, 10.0), (5.0, 5.0, 10.0)]
    with indexer.results_writer(results_path) as writer, XmlResultsWriter(xml_path) as xml:
        for index, (name, position) in enumerate(zip(FRAMES, positions, strict=True), start=1):
            frame = frames_dir / f"frame_{index}.h5"
            shutil.copy(FIXTURES / name, frame)
            result = indexer.index(str(frame), keep_image=False, metadata={"sample_position": position})
            writer.append(result, frame_id=f"frame_{index}")
            xml.append(result)
    return results_path, xml_path


@pytest.fixture(scope="session")
def synthetic_results(tmp_path_factory):
    results_path, xml_path = write_synthetic_results(tmp_path_factory.mktemp("viz"))
    return results_path, xml_path


@pytest.fixture(scope="session")
def synthetic_dataset(synthetic_results):
    return load_results(synthetic_results[0])
