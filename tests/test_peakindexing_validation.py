"""Focused tests for peak indexing validation service behavior."""

import os
import sys
from unittest.mock import patch

import pytest

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from laue_portal.database import session_utils
from laue_portal.services.validation import validate_peakindexing


@pytest.fixture
def isolated_db(tmp_path):
    db_file = tmp_path / "validation.db"
    with patch("laue_portal.config.db_file", str(db_file)):
        session_utils.init_db()
        yield


def valid_peakindex_fields(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "img_1.tif").write_text("data")

    geo_file = tmp_path / "geo.yml"
    geo_file.write_text("geo")
    cryst_file = tmp_path / "crystal.yml"
    cryst_file.write_text("crystal")

    return {
        "root_path": "",
        "data_path": str(data_dir),
        "filenamePrefix": "img_1.tif",
        "scanPoints": "",
        "depthRange": "",
        "geoFile": str(geo_file),
        "crystFile": str(cryst_file),
        "outputFolder": str(tmp_path / "out"),
        "IDnumber": "",
        "author": "tester",
        "threshold": "1",
        "thresholdRatio": "1",
        "maxRfactor": "0.5",
        "boxsize": "5",
        "max_number": "10",
        "min_separation": "1",
        "min_size": "1",
        "max_peaks": "100",
        "indexKeVmaxCalc": "30",
        "indexKeVmaxTest": "30",
        "indexAngleTolerance": "1",
        "indexCone": "45",
        "indexHKL": "100",
        "detectorCropX1": "0",
        "detectorCropX2": "10",
        "detectorCropY1": "0",
        "detectorCropY2": "10",
    }


def test_valid_absolute_paths_warn_only_for_missing_idnumber(tmp_path, isolated_db):
    result = validate_peakindexing(valid_peakindex_fields(tmp_path))

    assert result["errors"] == {}
    assert "IDnumber" in result["warnings"]
    assert "root_path" not in result["errors"]


def test_blank_root_path_errors_when_paths_are_relative(tmp_path, isolated_db):
    fields = valid_peakindex_fields(tmp_path)
    fields.update(
        {
            "data_path": "data",
            "geoFile": "geo.yml",
            "crystFile": "crystal.yml",
            "outputFolder": "out",
        }
    )

    result = validate_peakindexing(fields)

    assert "root_path" in result["errors"]
    assert "data_path" in result["warnings"]


def test_relative_paths_are_valid_when_root_path_exists(tmp_path, isolated_db):
    fields = valid_peakindex_fields(tmp_path)
    fields.update(
        {
            "root_path": str(tmp_path),
            "data_path": "data",
            "geoFile": "geo.yml",
            "crystFile": "crystal.yml",
            "outputFolder": "out",
        }
    )

    result = validate_peakindexing(fields)

    assert result["errors"] == {}
    for field_name in ["data_path", "geoFile", "crystFile", "outputFolder"]:
        assert field_name not in result["warnings"]


def test_numeric_and_detector_crop_errors(tmp_path, isolated_db):
    fields = valid_peakindex_fields(tmp_path)
    fields.update(
        {
            "maxRfactor": "2",
            "boxsize": "0",
            "indexCone": "181",
            "detectorCropX1": "10",
            "detectorCropX2": "5",
        }
    )

    result = validate_peakindexing(fields)

    for field_name in ["maxRfactor", "boxsize", "indexCone", "detectorCropX1", "detectorCropX2"]:
        assert field_name in result["errors"]


def test_invalid_index_hkl_errors(tmp_path, isolated_db):
    fields = valid_peakindex_fields(tmp_path)
    fields["indexHKL"] = "not-hkl"

    result = validate_peakindexing(fields)

    assert "indexHKL" in result["errors"]


def test_invalid_idnumber_format_errors(tmp_path, isolated_db):
    fields = valid_peakindex_fields(tmp_path)
    fields["IDnumber"] = "bad-id"

    result = validate_peakindexing(fields)

    assert "IDnumber" in result["errors"]
    assert "IDnumber" not in result["warnings"]


@pytest.mark.parametrize(
    ("scan_points", "depth_range"),
    [
        ("", ""),
        ("1", "1"),
    ],
)
def test_one_placeholder_requires_exactly_one_index_range(tmp_path, isolated_db, scan_points, depth_range):
    fields = valid_peakindex_fields(tmp_path)
    (tmp_path / "data" / "img_1.tif").write_text("data")
    fields.update(
        {
            "filenamePrefix": "img_%d.tif",
            "scanPoints": scan_points,
            "depthRange": depth_range,
        }
    )

    result = validate_peakindexing(fields)

    assert "filenamePrefix" in result["errors"]
    assert "scanPoints" in result["errors"]
    assert "depthRange" in result["errors"]


def test_one_placeholder_accepts_depth_range_without_scan_points(tmp_path, isolated_db):
    fields = valid_peakindex_fields(tmp_path)
    fields.update(
        {
            "filenamePrefix": "depth_%d.tif",
            "scanPoints": "",
            "depthRange": "5",
        }
    )
    (tmp_path / "data" / "depth_5.tif").write_text("data")

    result = validate_peakindexing(fields)

    assert result["errors"] == {}


def test_indexed_file_validation_reports_missing_scan_points(tmp_path, isolated_db):
    fields = valid_peakindex_fields(tmp_path)
    fields.update(
        {
            "filenamePrefix": "img_%d.tif",
            "scanPoints": "1-3",
            "depthRange": "",
        }
    )
    (tmp_path / "data" / "img_2.tif").write_text("data")

    result = validate_peakindexing(fields)

    assert "scanPoints" in result["errors"]
    assert "indices: 3" in result["errors"]["scanPoints"][0]


def test_two_placeholders_require_scan_points_and_depth_range(tmp_path, isolated_db):
    fields = valid_peakindex_fields(tmp_path)
    fields.update(
        {
            "filenamePrefix": "img_%d_%d.tif",
            "scanPoints": "1",
            "depthRange": "",
        }
    )
    (tmp_path / "data" / "img_1_1.tif").write_text("data")

    result = validate_peakindexing(fields)

    assert "depthRange" in result["errors"]


def test_multi_input_validation_labels_the_failing_input(tmp_path, isolated_db):
    data_dir = tmp_path / "data2"
    data_dir.mkdir()
    (data_dir / "img_1.tif").write_text("data")

    fields = valid_peakindex_fields(tmp_path)
    fields.update(
        {
            "data_path": f"{tmp_path / 'data'}; {data_dir}",
            "filenamePrefix": "img_1.tif",
            "outputFolder": f"{tmp_path / 'out1'}; {tmp_path / 'out2'}",
            "maxRfactor": "0.5; 2",
            "indexHKL": "100",
        }
    )

    result = validate_peakindexing(fields)

    assert result["errors"]["maxRfactor"] == ["Input 2: Max Rfactor must be between 0 and 1"]
