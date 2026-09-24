"""Focused tests for peak indexing validation service behavior."""

import os
import sys
from unittest.mock import patch

import pytest

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from laue_portal.database import session_utils
from laue_portal.pages.callback_registrars import _effective_data_paths, _resolve_effective_data_path
from laue_portal.services.validation import effective_data_path, validate_peakindexing


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
        "scanPoints": "1",
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


def test_blank_folder_path_uses_root_as_data_directory(tmp_path, isolated_db):
    fields = valid_peakindex_fields(tmp_path)
    fields.update(
        {
            "root_path": str(tmp_path / "data"),
            "data_path": "",
            "geoFile": str(tmp_path / "geo.yml"),
            "crystFile": str(tmp_path / "crystal.yml"),
            "outputFolder": str(tmp_path / "out"),
        }
    )

    result = validate_peakindexing(fields)

    assert result["errors"] == {}
    assert "data_path" not in result["warnings"]
    assert "outputFolder" not in result["warnings"]
    assert "geoFile" not in result["warnings"]
    assert "crystFile" not in result["warnings"]
    assert "Folder Path is blank; Root Path will be used as the data directory" in result["successes"]["data_path"]


def test_blank_folder_path_warns_for_relative_output(tmp_path, isolated_db):
    fields = valid_peakindex_fields(tmp_path)
    fields.update(
        {
            "root_path": str(tmp_path / "data"),
            "data_path": "",
            "geoFile": str(tmp_path / "geo.yml"),
            "crystFile": str(tmp_path / "crystal.yml"),
            "outputFolder": "out",
        }
    )

    result = validate_peakindexing(fields)

    assert result["errors"] == {}
    assert "outputFolder" in result["warnings"]
    assert "Folder Path is blank" in result["warnings"]["outputFolder"][0]


def test_blank_folder_path_resolves_to_root_for_submission_and_file_matching(tmp_path):
    root = str(tmp_path / "data")

    assert effective_data_path("", root) == root
    assert effective_data_path(None, root) == root
    assert _effective_data_paths("", root) == [root]
    assert _resolve_effective_data_path("", root) == root


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
    assert ("scanPoints" in result["errors"]) is (not scan_points)
    assert "depthRange" not in result["errors"]


def test_scan_points_are_required_even_when_depth_range_is_present(tmp_path, isolated_db):
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

    assert "scanPoints" in result["errors"]


def test_file_resolution_is_deferred_to_the_workflow_service(tmp_path, isolated_db):
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

    assert result["errors"] == {}


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

    assert "filenamePrefix" in result["errors"]
    assert "depthRange" not in result["errors"]


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


@pytest.mark.parametrize("value", ["3", "3.0"])
def test_minimum_spot_size_accepts_positive_whole_pixels(tmp_path, isolated_db, value):
    fields = valid_peakindex_fields(tmp_path)
    fields["min_size"] = value
    assert validate_peakindexing(fields)["errors"] == {}


@pytest.mark.parametrize("value", ["0", "-1", "3.5", "nan", "inf"])
def test_minimum_spot_size_rejects_nonpositive_or_fractional_pixels(tmp_path, isolated_db, value):
    fields = valid_peakindex_fields(tmp_path)
    fields["min_size"] = value
    assert validate_peakindexing(fields)["errors"]["min_size"] == ["Min Spot Size must be a positive integer"]


def test_both_spot_limits_may_be_blank(tmp_path, isolated_db):
    fields = valid_peakindex_fields(tmp_path)
    fields.update(max_number="", max_peaks="")
    assert validate_peakindexing(fields)["errors"] == {}


@pytest.fixture
def scan_file(tmp_path):
    """Create a scan with a failed wire_2 point."""

    from lauelab.reconstruct import reconstruct_scan

    from tests.wire_support import GEOMETRY, write_wire_scan

    inputs = [write_wire_scan(tmp_path / "wire_1.h5"), tmp_path / "wire_2.h5"]
    result = reconstruct_scan(
        inputs,
        tmp_path / "reconstruction",
        geometry=GEOMETRY,
        detector=0,
        point_ids=["wire_1", "wire_2"],
        depth_range=(-25.0, 25.0),
        resolution=5.0,
        threads_per_worker=1,
    )
    return os.fspath(result.path)


@pytest.fixture
def scan_fields(tmp_path, scan_file):
    fields = valid_peakindex_fields(tmp_path)
    fields.update({"data_path": scan_file, "filenamePrefix": "wire_%d", "scanPoints": "1", "depthRange": "0-3"})
    return fields


def test_a_scan_catalog_is_a_valid_data_path(isolated_db, scan_fields):
    result = validate_peakindexing(scan_fields)

    assert result["errors"] == {}


def test_scan_catalog_selection_problems_are_reported_before_submission(isolated_db, scan_fields):
    failed = validate_peakindexing({**scan_fields, "scanPoints": "1-2"})
    assert "point 'wire_2' is failed" in str(failed["errors"]["data_path"])

    beyond = validate_peakindexing({**scan_fields, "depthRange": "0-11"})
    assert "requested 11" in str(beyond["errors"]["data_path"])

    two_placeholders = validate_peakindexing({**scan_fields, "filenamePrefix": "wire_%d_%d"})
    assert "filenamePrefix" in two_placeholders["errors"]


def _reconstruction_with_output(output_path):
    from datetime import datetime

    from sqlalchemy.orm import Session

    from laue_portal.database import db_schema
    from laue_portal.workflows.run_records import new_job

    now = datetime(2026, 9, 24, 9, 0, 0)
    with Session(session_utils.get_engine()) as session, session.begin():
        run = db_schema.ReconstructionRun(
            job=new_job(computer_name="test-host", priority=0, submitted_at=now, n_inputs=2),
            method="wire",
            input_path="/data",
            output_path=os.fspath(output_path),
            created_at=now,
        )
        session.add(run)
        session.flush()
        return run.id


def test_a_linked_reconstruction_is_compared_with_its_scan_catalog(tmp_path, isolated_db, scan_fields):
    own = _reconstruction_with_output(tmp_path)  # the fixture's catalog is tmp_path/reconstruction/scan.h5
    other = _reconstruction_with_output(tmp_path / "elsewhere")

    warnings = validate_peakindexing({**scan_fields, "IDnumber": f"R{own}"})["warnings"]
    assert "different source path" not in str(warnings["data_path"])
    warnings = validate_peakindexing({**scan_fields, "IDnumber": f"R{other}"})["warnings"]
    assert "has a different source path" in str(warnings["data_path"])


def test_a_data_path_file_that_is_not_a_scan_catalog_is_rejected(tmp_path, isolated_db):
    fields = valid_peakindex_fields(tmp_path)
    fields["data_path"] = str(tmp_path / "data" / "img_1.tif")

    result = validate_peakindexing(fields)

    assert "must be a directory or a reconstruction scan catalog" in str(result["errors"]["data_path"])
