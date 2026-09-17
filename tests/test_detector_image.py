"""Tests for external detector-image discovery and its missing-image handling."""

from pathlib import Path

import h5py
import numpy as np

from laue_portal.analysis import detector_image


def _write_image(path):
    with h5py.File(path, "w") as handle:
        handle.create_dataset("entry1/data/data", data=np.arange(16, dtype=np.uint16).reshape(4, 4))


def test_image_is_resolved_through_the_portal_search_rules(tmp_path):
    frame = tmp_path / "data" / "frame_1.h5"
    frame.parent.mkdir()
    _write_image(frame)
    xml_path = tmp_path / "run" / "output.xml"
    xml_path.parent.mkdir()

    # A relative inputImage is searched next to the XML, in the run's data folder, and under the root.
    result = detector_image.load_detector_image(
        "frame_1.h5", xml_path=str(xml_path), data_folder=str(frame.parent), root_path=str(tmp_path)
    )

    assert result.image is not None
    assert result.image.path == str(frame) and result.image.dataset.endswith("entry1/data/data")
    assert result.image.data.shape == (4, 4) and result.image.vmin <= result.image.vmax
    assert result.warning is None


def test_missing_and_unreadable_locations_become_a_warning_not_an_error(tmp_path, monkeypatch):
    real_is_file = Path.is_file

    def denied(self):
        if "forbidden" in str(self):
            raise PermissionError(13, "Permission denied", str(self))
        return real_is_file(self)

    monkeypatch.setattr(Path, "is_file", denied)
    result = detector_image.load_detector_image(
        "/forbidden/frame_2.h5", xml_path=str(tmp_path / "output.xml"), data_folder=str(tmp_path), root_path=None
    )

    assert result.image is None
    assert result.warning.startswith("Detector image file was not found.")
    assert "Not accessible: /forbidden/frame_2.h5 (Permission denied)" in result.warning
    assert result.attempted_paths
    assert detector_image.load_detector_image(None).warning.startswith("No inputImage")
