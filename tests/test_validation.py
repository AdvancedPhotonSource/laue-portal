"""Tests for generic validation service helpers."""

import os
import sys

import pytest

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from laue_portal.services.validation import (
    add_validation_message,
    all_path_fields_are_absolute,
    format_filename_with_indices,
    safe_float,
    safe_int,
    validate_field_value,
)


def empty_validation_result():
    return {"errors": {}, "warnings": {}, "successes": {}}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("3", 3),
        (7, 7),
        ("", None),
        (None, None),
        ("3.5", None),
        ("abc", None),
    ],
)
def test_safe_int(value, expected):
    assert safe_int(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("3.5", 3.5),
        (4, 4.0),
        ("", None),
        (None, None),
        ("abc", None),
    ],
)
def test_safe_float(value, expected):
    assert safe_float(value) == expected


def test_add_validation_message_formats_defaults_and_custom_messages():
    result = empty_validation_result()

    add_validation_message(result, "errors", "data_path")
    add_validation_message(
        result,
        "warnings",
        "depth_resolution",
        input_prefix="Input 2: ",
        custom_message="%s must be <= %s",
        display_name=["Depth Resolution", "depth range"],
    )

    assert result["errors"]["data_path"] == ["Data Path is required"]
    assert result["warnings"]["depth_resolution"] == ["Input 2: Depth Resolution must be <= depth range"]


def test_validate_field_value_handles_required_optional_and_conversion():
    result = empty_validation_result()
    parsed_fields = {
        "required_missing": [""],
        "optional_missing": [""],
        "bad_number": ["abc"],
        "good_number": ["5"],
    }

    assert validate_field_value(result, parsed_fields, "required_missing", 0) is None
    assert validate_field_value(result, parsed_fields, "optional_missing", 0, required=False) is None
    assert validate_field_value(result, parsed_fields, "bad_number", 0, converter=safe_int) is None
    assert validate_field_value(result, parsed_fields, "good_number", 0, converter=safe_int) == 5

    assert "required_missing" in result["errors"]
    assert "bad_number" in result["errors"]
    assert "optional_missing" not in result["errors"]


def test_validate_field_value_respects_optional_params_when_not_required():
    result = empty_validation_result()
    parsed_fields = {"scanPoints": [""]}

    value = validate_field_value(
        result,
        parsed_fields,
        "scanPoints",
        0,
        required=False,
        optional_params=["scanPoints"],
    )

    assert value is None
    assert result["errors"] == {}


def test_all_path_fields_are_absolute_handles_semicolon_values(tmp_path):
    absolute_a = tmp_path / "a"
    absolute_b = tmp_path / "b"

    assert all_path_fields_are_absolute({"paths": f"{absolute_a}; {absolute_b}"}, ["paths"])
    assert not all_path_fields_are_absolute({"paths": f"{absolute_a}; relative/path"}, ["paths"])
    assert not all_path_fields_are_absolute({"paths": ""}, ["paths"])
    assert not all_path_fields_are_absolute({}, ["paths"])


def test_format_filename_with_indices_supports_valid_placeholder_counts():
    assert format_filename_with_indices("img.tif", None) == "img.tif"
    assert format_filename_with_indices("img_%d.tif", 3) == "img_3.tif"
    assert format_filename_with_indices("img_%d.tif", None, 4) == "img_4.tif"
    assert format_filename_with_indices("img_%d_%d.tif", 3, 4) == "img_3_4.tif"


@pytest.mark.parametrize(
    ("filename_prefix", "scan_point", "depth_range"),
    [
        ("img_%d.tif", 3, 4),
        ("img_%d.tif", None, None),
        ("img_%d_%d.tif", 3, None),
        ("img_%d_%d_%d.tif", 1, 2),
    ],
)
def test_format_filename_with_indices_rejects_invalid_placeholder_combinations(
    filename_prefix, scan_point, depth_range
):
    with pytest.raises(ValueError):
        format_filename_with_indices(filename_prefix, scan_point, depth_range)
