"""Dash-independent validation helpers for create-page workflows."""

import glob
import os

from sqlalchemy.orm import Session

import laue_portal.database.session_utils as session_utils
from laue_portal.database.db_utils import (
    get_data_from_id,
    get_num_inputs_from_fields,
    parse_IDnumber,
    parse_parameter,
    resolve_path_with_root,
)
from laue_portal.utilities.hkl_parse import str2hkl
from laue_portal.utilities.srange import srange

PEAKINDEX_FIELD_IDS = [
    "data_path",
    "filenamePrefix",
    "scanPoints",
    "depthRange",
    "geoFile",
    "crystFile",
    "outputFolder",
    "root_path",
    "IDnumber",
    "author",
    "threshold",
    "thresholdRatio",
    "maxRfactor",
    "boxsize",
    "max_number",
    "min_separation",
    "min_size",
    "max_peaks",
    "indexKeVmaxCalc",
    "indexKeVmaxTest",
    "indexAngleTolerance",
    "indexCone",
    "indexHKL",
    "detectorCropX1",
    "detectorCropX2",
    "detectorCropY1",
    "detectorCropY2",
]

PEAKINDEX_OPTIONAL_FIELDS = [
    "scanPoints",
    "depthRange",
    "threshold",
    "thresholdRatio",
    "max_peaks",
    "scanNumber",
    "wirerecon_id",
    "recon_id",
]

PEAKINDEX_NUMERIC_FIELDS = [
    "threshold",
    "thresholdRatio",
    "maxRfactor",
    "boxsize",
    "max_number",
    "min_separation",
    "min_size",
    "max_peaks",
    "indexKeVmaxCalc",
    "indexKeVmaxTest",
    "indexAngleTolerance",
    "indexCone",
    "detectorCropX1",
    "detectorCropX2",
    "detectorCropY1",
    "detectorCropY2",
]


def format_field_name(field_name):
    """Convert field_name to display format only if it contains underscores."""
    if "_" in field_name:
        return field_name.replace("_", " ").title()
    return field_name


def add_validation_message(
    validation_result, result_key, field_name, input_prefix="", custom_message=None, display_name=None
):
    """Add a validation message to the validation_result dict."""
    if custom_message:
        if "%s" in custom_message:
            if display_name is None:
                display_name = format_field_name(field_name)

            if isinstance(display_name, (list, tuple)):
                message = custom_message % tuple(display_name)
            else:
                message = custom_message % display_name
        else:
            message = custom_message
    else:
        if display_name is None:
            display_name = format_field_name(field_name)

        if result_key == "errors":
            message = f"{display_name} is required"
        elif result_key == "warnings":
            message = f"{display_name} is missing"
        else:
            message = ""

    if input_prefix:
        message = f"{input_prefix}{message}"

    validation_result[result_key].setdefault(field_name, []).append(message)


def validate_field_value(
    validation_result,
    parsed_fields,
    field_name,
    index,
    input_prefix="",
    converter=None,
    required=True,
    display_name=None,
    optional_params=None,
):
    """Extract, validate, and optionally convert a parsed field value."""
    if optional_params is not None and field_name in optional_params and not required:
        required = False

    if field_name not in parsed_fields:
        return None

    value = parsed_fields[field_name][index]

    if value is None or value == "":
        if required:
            add_validation_message(validation_result, "errors", field_name, input_prefix, display_name=display_name)
        return None

    if converter is not None:
        converted_value = converter(value)
        if converted_value is None:
            add_validation_message(
                validation_result,
                "errors",
                field_name,
                input_prefix,
                custom_message=f"{field_name} must be a valid number",
                display_name=display_name,
            )
            return None
        return converted_value

    return value


def validate_numeric_range(value, min_val=None, max_val=None, field_name="Field", allow_none=False):
    """Validate a numeric value and optional min/max bounds."""
    errors = []
    warnings = []

    if value is None or value == "":
        if allow_none:
            return None, errors, warnings
        errors.append(f"{field_name} is required")
        return None, errors, warnings

    try:
        num_val = float(value)

        if min_val is not None and num_val < min_val:
            errors.append(f"{field_name} must be >= {min_val}")

        if max_val is not None and num_val > max_val:
            errors.append(f"{field_name} must be <= {max_val}")

        return num_val, errors, warnings
    except (ValueError, TypeError):
        errors.append(f"{field_name} must be a valid number")
        return None, errors, warnings


def validate_file_exists(file_path, root_path, field_name="File"):
    """Return validation errors if a file path is missing or does not exist."""
    if not file_path:
        return [f"{field_name} is required"]

    full_path = resolve_path_with_root(file_path, root_path)

    if not os.path.exists(full_path):
        return [f"{field_name} not found: {file_path}"]

    return []


def validate_directory_exists(dir_path, root_path, field_name="Directory"):
    """Return validation errors if a directory path is missing or does not exist."""
    if not dir_path:
        return [f"{field_name} is required"]

    full_path = resolve_path_with_root(dir_path, root_path)

    if not os.path.exists(full_path):
        return [f"{field_name} not found: {dir_path}"]

    return []


def safe_float(value):
    """Safely convert a value to float, returning None on failure."""
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (ValueError, TypeError):
        return None


def safe_int(value):
    """Safely convert a value to int, returning None on failure."""
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (ValueError, TypeError):
        return None


def all_path_fields_are_absolute(all_fields, path_field_names):
    """Return True when all listed semicolon-aware path fields are absolute."""
    for field_name in path_field_names:
        raw_value = all_fields.get(field_name, "")
        if not raw_value:
            return False

        individual_values = [v.strip() for v in str(raw_value).split(";") if v.strip()]
        if not individual_values:
            return False

        for val in individual_values:
            if not os.path.isabs(val):
                return False

    return True


def format_filename_with_indices(filename_prefix, scanPoint_num, depthRange_num=None):
    """Format a peak indexing filename prefix with scan/depth indices."""
    num_placeholders = filename_prefix.count("%d")

    if num_placeholders == 0:
        file_str = filename_prefix
    elif num_placeholders == 1:
        if scanPoint_num is not None and depthRange_num is None:
            file_str = filename_prefix % scanPoint_num
        elif depthRange_num is not None and scanPoint_num is None:
            file_str = filename_prefix % depthRange_num
        elif scanPoint_num is not None and depthRange_num is not None:
            raise ValueError(
                f"Filename prefix '{filename_prefix}' has 1 %d placeholder "
                f"but both Scan Points and Depth Range were provided (only one allowed)"
            )
        else:
            raise ValueError(
                f"Filename prefix '{filename_prefix}' has 1 %d placeholder "
                f"but neither Scan Points nor Depth Range was provided"
            )
    elif num_placeholders == 2:
        if depthRange_num is not None:
            file_str = filename_prefix % (scanPoint_num, depthRange_num)
        else:
            raise ValueError(f"Filename prefix '{filename_prefix}' has 2 %d placeholders but no Depth Range specified")
    else:
        raise ValueError(
            f"Filename prefix '{filename_prefix}' has {num_placeholders} %d placeholders (max 2 supported)"
        )

    return file_str


def validate_peakindexing(fields, catalog_defaults=None):
    """Validate peak indexing form fields without depending on Dash callback context."""
    validation_result = {"errors": {}, "warnings": {}, "successes": {}}
    parsed_fields = {}
    all_fields = {field_name: fields[field_name] for field_name in PEAKINDEX_FIELD_IDS if field_name in fields}

    num_inputs = get_num_inputs_from_fields(all_fields)
    root_path = all_fields.get("root_path", "")
    IDnumber = all_fields.get("IDnumber", "")

    root_path_dependent_fields = ["data_path", "outputFolder", "geoFile", "crystFile"]
    if not root_path:
        if all_path_fields_are_absolute(all_fields, root_path_dependent_fields):
            parsed_fields["root_path"] = root_path
            add_validation_message(
                validation_result,
                "successes",
                "root_path",
                custom_message="Root Path is blank but all path fields are absolute",
            )
        else:
            add_validation_message(
                validation_result,
                "errors",
                "root_path",
                custom_message="Root Path is required when any path field is relative",
            )
            field_display_names = {
                "data_path": "Data Path",
                "outputFolder": "Output Folder",
                "geoFile": "Geometry File",
                "crystFile": "Crystal File",
            }
            for field_name in root_path_dependent_fields:
                raw_value = all_fields.get(field_name, "")
                if not raw_value:
                    continue
                values = [v.strip() for v in str(raw_value).split(";") if v.strip()]
                for val in values:
                    if not os.path.isabs(val):
                        display = field_display_names.get(field_name, field_name)
                        add_validation_message(
                            validation_result,
                            "warnings",
                            field_name,
                            custom_message=f"{display} is relative but Root Path is blank - use an absolute path",
                        )
                        break
    elif not os.path.exists(root_path):
        add_validation_message(validation_result, "errors", "root_path", custom_message="Root Path does not exist")
    else:
        parsed_fields["root_path"] = root_path
        add_validation_message(validation_result, "successes", "root_path")

    parsed_fields["IDnumber"] = IDnumber

    with Session(session_utils.get_engine()) as session:
        if IDnumber:
            try:
                id_dict = parse_IDnumber(IDnumber, session)
                for key, value in id_dict.items():
                    if value is not None:
                        parsed_fields[key] = parse_parameter(value, num_inputs)
                add_validation_message(validation_result, "successes", "IDnumber")
            except ValueError as e:
                error_message = str(e)
                if "not found in database" in error_message:
                    add_validation_message(
                        validation_result,
                        "warnings",
                        "IDnumber",
                        custom_message=f"ID Number warning: {error_message}. This will create an unlinked peak indexing.",
                    )
                else:
                    add_validation_message(
                        validation_result,
                        "errors",
                        "IDnumber",
                        custom_message=f"ID Number parsing error: {error_message}",
                    )
        else:
            add_validation_message(
                validation_result,
                "warnings",
                "IDnumber",
                custom_message="No ID Number provided. This will create an unlinked peak indexing.",
            )

        for field_name, field_value in all_fields.items():
            if field_name in parsed_fields:
                continue

            is_missing = False
            if field_name in PEAKINDEX_NUMERIC_FIELDS:
                if field_value is None or field_value == "":
                    is_missing = True
            elif not field_value:
                is_missing = True

            if is_missing:
                if field_name == "scanNumber":
                    add_validation_message(validation_result, "warnings", field_name, display_name="Scan Number")
                    continue
                elif field_name in PEAKINDEX_OPTIONAL_FIELDS:
                    continue
                else:
                    add_validation_message(validation_result, "errors", field_name)
                    continue

            try:
                parsed_list = parse_parameter(field_value, num_inputs)
            except ValueError as e:
                if field_name == "scanNumber":
                    add_validation_message(
                        validation_result, "warnings", field_name, custom_message=f"Scan Number parsing error: {str(e)}"
                    )
                    continue
                else:
                    add_validation_message(
                        validation_result, "errors", field_name, custom_message=f"%s parsing error: {str(e)}"
                    )
                    continue

            if len(parsed_list) != num_inputs:
                if field_name == "scanNumber":
                    add_validation_message(
                        validation_result,
                        "warnings",
                        field_name,
                        custom_message=f"Scan Number count ({len(parsed_list)}) does not match number of inputs ({num_inputs})",
                    )
                else:
                    add_validation_message(
                        validation_result,
                        "errors",
                        field_name,
                        custom_message=f"%s count ({len(parsed_list)}) does not match number of inputs ({num_inputs})",
                    )

            parsed_fields[field_name] = parsed_list

        def validate_for_input(field_name, index, input_prefix, **kwargs):
            return validate_field_value(
                validation_result,
                parsed_fields,
                field_name,
                index,
                input_prefix,
                optional_params=PEAKINDEX_OPTIONAL_FIELDS,
                **kwargs,
            )

        for i in range(num_inputs):
            input_prefix = f"Input {i + 1}: " if num_inputs > 1 else ""

            def validate_field(field_name, _i=i, _input_prefix=input_prefix, **kwargs):
                return validate_for_input(field_name, _i, _input_prefix, **kwargs)

            scan_num_int = None
            if "scanNumber" in parsed_fields:
                current_scanNumber = validate_field("scanNumber", required=False, display_name="Scan Number")
                if current_scanNumber:
                    try:
                        scan_num_int = int(current_scanNumber)
                    except (ValueError, TypeError):
                        add_validation_message(
                            validation_result,
                            "warnings",
                            "IDnumber",
                            input_prefix,
                            custom_message="Scan Number is not a valid integer",
                        )

            wirerecon_id_int = None
            if "wirerecon_id" in parsed_fields:
                wirerecon_val = validate_field("wirerecon_id", required=False, display_name="Wire Recon ID")
                if wirerecon_val:
                    try:
                        wirerecon_id_int = int(wirerecon_val)
                    except (ValueError, TypeError):
                        add_validation_message(
                            validation_result,
                            "warnings",
                            "IDnumber",
                            input_prefix,
                            custom_message="Wire Recon ID is not a valid integer",
                        )

            recon_id_int = None
            if "recon_id" in parsed_fields:
                recon_val = validate_field("recon_id", required=False, display_name="Recon ID")
                if recon_val:
                    try:
                        recon_id_int = int(recon_val)
                    except (ValueError, TypeError):
                        add_validation_message(
                            validation_result,
                            "warnings",
                            "IDnumber",
                            input_prefix,
                            custom_message="Recon ID is not a valid integer",
                        )

            if "root_path" not in validation_result["errors"]:
                current_data_path = validate_field("data_path")
                if current_data_path is not None:
                    if os.path.isabs(current_data_path):
                        add_validation_message(
                            validation_result,
                            "warnings",
                            "data_path",
                            input_prefix,
                            custom_message="Data Path is absolute - Root Path will be ignored",
                        )

                    current_full_data_path = resolve_path_with_root(current_data_path, root_path)

                    if not os.path.exists(current_full_data_path):
                        add_validation_message(
                            validation_result,
                            "errors",
                            "data_path",
                            input_prefix,
                            custom_message="Data Path directory not found",
                        )
                    else:
                        if any([scan_num_int, wirerecon_id_int, recon_id_int]):
                            id_dict = {
                                "scanNumber": scan_num_int,
                                "wirerecon_id": wirerecon_id_int,
                                "recon_id": recon_id_int,
                            }
                            id_data = get_data_from_id(session, id_dict, root_path, "peakindex", catalog_defaults)

                            if id_data and id_data.get("data_path"):
                                id_full_data_path = resolve_path_with_root(id_data["data_path"], root_path)
                                if id_full_data_path != current_full_data_path:
                                    add_validation_message(
                                        validation_result,
                                        "warnings",
                                        "data_path",
                                        input_prefix,
                                        custom_message=f"{id_data['source']} database entry has different path ({id_data['data_path']})",
                                    )
                            else:
                                add_validation_message(
                                    validation_result,
                                    "warnings",
                                    "IDnumber",
                                    input_prefix,
                                    custom_message=f"{id_data.get('source', 'Data')} database entry not found",
                                )

                        all_files = [
                            f
                            for f in os.listdir(current_full_data_path)
                            if os.path.isfile(os.path.join(current_full_data_path, f))
                        ]
                        if not all_files:
                            add_validation_message(
                                validation_result,
                                "errors",
                                "data_path",
                                input_prefix,
                                custom_message="Data Path directory contains no files",
                            )
                        else:
                            current_filename_prefix_str = validate_field(
                                "filenamePrefix", display_name="Filename Prefix"
                            )
                            if current_filename_prefix_str is not None:
                                current_filename_prefix = (
                                    [s.strip() for s in current_filename_prefix_str.split(",")]
                                    if current_filename_prefix_str
                                    else []
                                )

                                for current_filename_prefix_i in current_filename_prefix:
                                    prefix_pattern = os.path.join(
                                        current_full_data_path, current_filename_prefix_i.replace("%d", "*")
                                    )
                                    prefix_matches = glob.glob(prefix_pattern)

                                    if not prefix_matches:
                                        add_validation_message(
                                            validation_result,
                                            "errors",
                                            "filenamePrefix",
                                            input_prefix,
                                            custom_message=f"No files match Filename prefix pattern '{current_filename_prefix_i}'",
                                        )
                                    else:
                                        num_placeholders = current_filename_prefix_i.count("%d")

                                        if num_placeholders == 0:
                                            continue

                                        if num_placeholders == 1:
                                            current_scanPoints = validate_field(
                                                "scanPoints", required=False, display_name="Scan Points"
                                            )
                                            current_depthRange = validate_field(
                                                "depthRange", required=False, display_name="Depth Range"
                                            )

                                            has_scanPoints = current_scanPoints is not None
                                            has_depthRange = current_depthRange is not None

                                            if has_scanPoints and has_depthRange:
                                                error_msg = f"Filename prefix '{current_filename_prefix_i}' has 1 %d placeholder but both Scan Points and Depth Range were provided (only one allowed)"
                                                add_validation_message(
                                                    validation_result,
                                                    "errors",
                                                    "filenamePrefix",
                                                    input_prefix,
                                                    custom_message=error_msg,
                                                )
                                                add_validation_message(
                                                    validation_result,
                                                    "errors",
                                                    "scanPoints",
                                                    input_prefix,
                                                    custom_message=error_msg,
                                                )
                                                add_validation_message(
                                                    validation_result,
                                                    "errors",
                                                    "depthRange",
                                                    input_prefix,
                                                    custom_message=error_msg,
                                                )
                                                continue
                                            elif not has_scanPoints and not has_depthRange:
                                                error_msg = f"Filename prefix '{current_filename_prefix_i}' has 1 %d placeholder but neither Scan Points nor Depth Range was provided"
                                                add_validation_message(
                                                    validation_result,
                                                    "errors",
                                                    "filenamePrefix",
                                                    input_prefix,
                                                    custom_message=error_msg,
                                                )
                                                add_validation_message(
                                                    validation_result,
                                                    "errors",
                                                    "scanPoints",
                                                    input_prefix,
                                                    custom_message=error_msg,
                                                )
                                                add_validation_message(
                                                    validation_result,
                                                    "errors",
                                                    "depthRange",
                                                    input_prefix,
                                                    custom_message=error_msg,
                                                )
                                                continue

                                            if has_scanPoints:
                                                try:
                                                    scanPoints_srange = srange(current_scanPoints)
                                                    scanPoint_nums = scanPoints_srange.list()
                                                    if not scanPoint_nums:
                                                        add_validation_message(
                                                            validation_result,
                                                            "errors",
                                                            "scanPoints",
                                                            input_prefix,
                                                            custom_message="Scan Points range is empty",
                                                        )
                                                        continue
                                                    depthRange_nums = [None]
                                                except Exception:
                                                    add_validation_message(
                                                        validation_result,
                                                        "errors",
                                                        "scanPoints",
                                                        input_prefix,
                                                        custom_message="Scan Points entry has invalid format",
                                                    )
                                                    continue
                                            else:
                                                try:
                                                    depthRange_srange = srange(current_depthRange)
                                                    depthRange_nums = depthRange_srange.list()
                                                    if not depthRange_nums:
                                                        add_validation_message(
                                                            validation_result,
                                                            "errors",
                                                            "depthRange",
                                                            input_prefix,
                                                            custom_message="Depth Range is empty",
                                                        )
                                                        continue
                                                    scanPoint_nums = [None]
                                                except Exception:
                                                    add_validation_message(
                                                        validation_result,
                                                        "errors",
                                                        "depthRange",
                                                        input_prefix,
                                                        custom_message="Depth Range entry has invalid format",
                                                    )
                                                    continue

                                        elif num_placeholders == 2:
                                            current_scanPoints = validate_field(
                                                "scanPoints", display_name="Scan Points"
                                            )
                                            current_depthRange = validate_field(
                                                "depthRange", required=True, display_name="Depth Range"
                                            )

                                            if current_scanPoints is None:
                                                if "scanPoints" not in validation_result["errors"]:
                                                    add_validation_message(
                                                        validation_result,
                                                        "errors",
                                                        "scanPoints",
                                                        input_prefix,
                                                        display_name="Scan Points",
                                                    )
                                                continue

                                            if current_depthRange is None:
                                                if "depthRange" not in validation_result["errors"]:
                                                    add_validation_message(
                                                        validation_result,
                                                        "errors",
                                                        "depthRange",
                                                        input_prefix,
                                                        display_name="Depth Range",
                                                    )
                                                continue

                                            try:
                                                scanPoints_srange = srange(current_scanPoints)
                                                scanPoint_nums = scanPoints_srange.list()
                                                if not scanPoint_nums:
                                                    add_validation_message(
                                                        validation_result,
                                                        "errors",
                                                        "scanPoints",
                                                        input_prefix,
                                                        custom_message="Scan Points range is empty",
                                                    )
                                                    continue
                                            except Exception:
                                                add_validation_message(
                                                    validation_result,
                                                    "errors",
                                                    "scanPoints",
                                                    input_prefix,
                                                    custom_message="Scan Points entry has invalid format",
                                                )
                                                continue

                                            try:
                                                depthRange_srange = srange(current_depthRange)
                                                depthRange_nums = depthRange_srange.list()
                                                if not depthRange_nums:
                                                    add_validation_message(
                                                        validation_result,
                                                        "errors",
                                                        "depthRange",
                                                        input_prefix,
                                                        custom_message="Depth Range is empty",
                                                    )
                                                    continue
                                            except Exception:
                                                add_validation_message(
                                                    validation_result,
                                                    "errors",
                                                    "depthRange",
                                                    input_prefix,
                                                    custom_message="Depth Range entry has invalid format",
                                                )
                                                continue

                                        else:
                                            continue

                                        missing_files = []
                                        for scanPoint_num in scanPoint_nums:
                                            for depthRange_num in depthRange_nums:
                                                try:
                                                    file_str = format_filename_with_indices(
                                                        current_filename_prefix_i, scanPoint_num, depthRange_num
                                                    )
                                                except ValueError as e:
                                                    add_validation_message(
                                                        validation_result,
                                                        "errors",
                                                        "filenamePrefix",
                                                        input_prefix,
                                                        custom_message=str(e),
                                                    )
                                                    break

                                                scanpoint_pattern = os.path.join(current_full_data_path, file_str)
                                                scanpoint_matches = glob.glob(scanpoint_pattern)

                                                if not scanpoint_matches:
                                                    if depthRange_num is not None:
                                                        missing_files.append(f"{scanPoint_num}_{depthRange_num}")
                                                    else:
                                                        missing_files.append(str(scanPoint_num))

                                        if missing_files:
                                            if len(missing_files) <= 5:
                                                files_str = ", ".join(missing_files)
                                            else:
                                                files_str = (
                                                    ", ".join(missing_files[:5])
                                                    + f", ... and {len(missing_files) - 5} more"
                                                )

                                            add_validation_message(
                                                validation_result,
                                                "errors",
                                                "scanPoints",
                                                input_prefix,
                                                custom_message=f"Missing files for Filename prefix '{current_filename_prefix_i}' (indices: {files_str})",
                                            )

            current_outputFolder = validate_field("outputFolder", display_name="Output Folder")
            if current_outputFolder is not None:
                if "root_path" not in validation_result["errors"]:
                    if os.path.isabs(current_outputFolder):
                        add_validation_message(
                            validation_result,
                            "warnings",
                            "outputFolder",
                            input_prefix,
                            custom_message="Output Folder is absolute - Root Path will be ignored",
                        )

                    if "%d" not in current_outputFolder:
                        full_output_path = resolve_path_with_root(current_outputFolder, root_path)
                        if os.path.exists(full_output_path):
                            add_validation_message(
                                validation_result,
                                "warnings",
                                "outputFolder",
                                input_prefix,
                                custom_message="Output Folder already exists",
                            )

            current_geoFile = validate_field("geoFile", display_name="Geometry File")
            if current_geoFile is not None:
                if "root_path" not in validation_result["errors"]:
                    if os.path.isabs(current_geoFile):
                        add_validation_message(
                            validation_result,
                            "warnings",
                            "geoFile",
                            input_prefix,
                            custom_message="Geometry File is absolute - Root Path will be ignored",
                        )

                    full_geo_path = resolve_path_with_root(current_geoFile, root_path)
                    if not os.path.exists(full_geo_path):
                        add_validation_message(
                            validation_result,
                            "errors",
                            "geoFile",
                            input_prefix,
                            custom_message="Geometry File not found",
                        )

            current_crystFile = validate_field("crystFile", display_name="Crystal File")
            if current_crystFile is not None:
                if "root_path" not in validation_result["errors"]:
                    if os.path.isabs(current_crystFile):
                        add_validation_message(
                            validation_result,
                            "warnings",
                            "crystFile",
                            input_prefix,
                            custom_message="Crystal File is absolute - Root Path will be ignored",
                        )

                    full_cryst_path = resolve_path_with_root(current_crystFile, root_path)
                    if not os.path.exists(full_cryst_path):
                        add_validation_message(
                            validation_result,
                            "errors",
                            "crystFile",
                            input_prefix,
                            custom_message="Crystal File not found",
                        )

            x1_val = validate_field("detectorCropX1", converter=safe_int)
            x2_val = validate_field("detectorCropX2", converter=safe_int)
            y1_val = validate_field("detectorCropY1", converter=safe_int)
            y2_val = validate_field("detectorCropY2", converter=safe_int)

            if x1_val is not None and x2_val is not None and x1_val >= x2_val:
                add_validation_message(
                    validation_result,
                    "errors",
                    "detectorCropX1",
                    input_prefix,
                    custom_message="Detector Crop X1 must be less than X2",
                )
                add_validation_message(
                    validation_result,
                    "errors",
                    "detectorCropX2",
                    input_prefix,
                    custom_message="Detector Crop X1 must be less than X2",
                )

            if y1_val is not None and y2_val is not None and y1_val >= y2_val:
                add_validation_message(
                    validation_result,
                    "errors",
                    "detectorCropY1",
                    input_prefix,
                    custom_message="Detector Crop Y1 must be less than Y2",
                )
                add_validation_message(
                    validation_result,
                    "errors",
                    "detectorCropY2",
                    input_prefix,
                    custom_message="Detector Crop Y1 must be less than Y2",
                )

            threshold_val = validate_field("threshold", converter=safe_int)
            if threshold_val is not None and threshold_val < 0:
                add_validation_message(
                    validation_result,
                    "errors",
                    "threshold",
                    input_prefix,
                    custom_message="Threshold must be non-negative",
                )

            thresholdRatio_val = validate_field("thresholdRatio", converter=safe_int)
            if thresholdRatio_val is not None and thresholdRatio_val < 0:
                add_validation_message(
                    validation_result,
                    "errors",
                    "thresholdRatio",
                    input_prefix,
                    custom_message="Threshold Ratio must be non-negative",
                )

            maxRfactor_val = validate_field("maxRfactor", converter=safe_float)
            if maxRfactor_val is not None and (maxRfactor_val < 0 or maxRfactor_val > 1):
                add_validation_message(
                    validation_result,
                    "errors",
                    "maxRfactor",
                    input_prefix,
                    custom_message="Max Rfactor must be between 0 and 1",
                )

            boxsize_val = validate_field("boxsize", converter=safe_int)
            if boxsize_val is not None and boxsize_val <= 0:
                add_validation_message(
                    validation_result, "errors", "boxsize", input_prefix, custom_message="Boxsize must be positive"
                )

            max_number_val = validate_field("max_number", converter=safe_int)
            if max_number_val is not None and max_number_val <= 0:
                add_validation_message(
                    validation_result,
                    "errors",
                    "max_number",
                    input_prefix,
                    custom_message="Max Number must be positive",
                )

            min_separation_val = validate_field("min_separation", converter=safe_float)
            if min_separation_val is not None and min_separation_val < 0:
                add_validation_message(
                    validation_result,
                    "errors",
                    "min_separation",
                    input_prefix,
                    custom_message="Min Separation must be non-negative",
                )

            min_size_val = validate_field("min_size", converter=safe_float)
            if min_size_val is not None and min_size_val < 0:
                add_validation_message(
                    validation_result,
                    "errors",
                    "min_size",
                    input_prefix,
                    custom_message="Min Size must be non-negative",
                )

            max_peaks_val = validate_field("max_peaks", converter=safe_int)
            if max_peaks_val is not None and max_peaks_val <= 0:
                add_validation_message(
                    validation_result, "errors", "max_peaks", input_prefix, custom_message="Max Peaks must be positive"
                )

            indexKeVmaxCalc_val = validate_field("indexKeVmaxCalc", converter=safe_float)
            if indexKeVmaxCalc_val is not None and indexKeVmaxCalc_val <= 0:
                add_validation_message(
                    validation_result,
                    "errors",
                    "indexKeVmaxCalc",
                    input_prefix,
                    custom_message="Index Ke Vmax Calc must be positive",
                )

            indexKeVmaxTest_val = validate_field("indexKeVmaxTest", converter=safe_float)
            if indexKeVmaxTest_val is not None and indexKeVmaxTest_val <= 0:
                add_validation_message(
                    validation_result,
                    "errors",
                    "indexKeVmaxTest",
                    input_prefix,
                    custom_message="Index Ke Vmax Test must be positive",
                )

            indexAngleTolerance_val = validate_field("indexAngleTolerance", converter=safe_float)
            if indexAngleTolerance_val is not None and indexAngleTolerance_val < 0:
                add_validation_message(
                    validation_result,
                    "errors",
                    "indexAngleTolerance",
                    input_prefix,
                    custom_message="Index Angle Tolerance must be non-negative",
                )

            indexCone_val = validate_field("indexCone", converter=safe_float)
            if indexCone_val is not None and (indexCone_val < 0 or indexCone_val > 180):
                add_validation_message(
                    validation_result,
                    "errors",
                    "indexCone",
                    input_prefix,
                    custom_message="Index Cone must be between 0 and 180 degrees",
                )

            if "indexHKL" not in validation_result["errors"]:
                current_indexHKL_str = str(parsed_fields["indexHKL"][i])
                try:
                    str2hkl(current_indexHKL_str, Nmin=3, Nmax=3)
                except (TypeError, ValueError) as e:
                    add_validation_message(
                        validation_result,
                        "errors",
                        "indexHKL",
                        input_prefix,
                        custom_message=f"Index HKL parsing error: {str(e)}",
                    )

    for field_name in PEAKINDEX_FIELD_IDS:
        if field_name not in validation_result["errors"] and field_name not in validation_result["warnings"]:
            add_validation_message(validation_result, "successes", field_name)

    return validation_result
