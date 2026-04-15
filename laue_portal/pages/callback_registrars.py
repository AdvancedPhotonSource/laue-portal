"""
Shared callback registration functions for Dash pages.

This module provides reusable callback registration functions that can be used
across multiple pages (e.g., wire reconstruction, peak indexing) with different
component IDs but identical logic.

Usage:
    from laue_portal.pages.callback_registrars import register_update_path_fields_callback

    register_update_path_fields_callback(
        button_id='wirerecon-update-path-fields-btn',
        id_number_id='IDnumber',
        alert_id='alert-scan-loaded',
        data_path_id='data_path',
        filename_prefix_id='filenamePrefix',
        root_path_id='root_path',
        catalog_defaults=CATALOG_DEFAULTS
    )
"""

import logging
import os

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, html, set_props
from dash.exceptions import PreventUpdate
from sqlalchemy.orm import Session

import laue_portal.database.session_utils as session_utils
from laue_portal.config import DEFAULT_VARIABLES, VALID_HDF_EXTENSIONS
from laue_portal.database.db_utils import get_data_from_id, parse_IDnumber, parse_parameter, resolve_path_with_root
from laue_portal.utilities.filename_patterns import (
    build_pattern_label,
    extract_index_patterns,
    filter_files_by_extension,
    scan_directory_patterns,
)
from laue_portal.utilities.srange import srange

logger = logging.getLogger(__name__)


def _merge_field_values(field_values, delimiter=";"):
    """
    Merge multiple field values, handling list types properly.

    This helper function merges values from multiple database entries, properly
    handling list-type fields (like filenamePrefix) by joining list elements with
    commas first, then joining multiple values with the specified delimiter.

    Parameters:
    - field_values: List of field values (can be lists, strings, or other types)
    - delimiter: Delimiter used to separate multiple values (default ";")

    Returns:
    - Merged value: single value if all same, or delimiter-separated string

    Examples:
    - ['path1', 'path1', 'path1'] -> 'path1'
    - ['path1', 'path2'] -> 'path1; path2'
    - [['a', 'b'], ['c', 'd']] -> 'a,b; c,d'
    - [['a', 'b'], ['a', 'b']] -> ['a', 'b']
    """
    if not field_values:
        return None

    # If all values are the same, return the first one
    if all(v == field_values[0] for v in field_values):
        return field_values[0]

    # Otherwise, merge with proper list handling
    return f"{delimiter} ".join([",".join(v) if isinstance(v, list) else str(v) for v in field_values])


def register_update_path_fields_callback(
    update_paths_id: str,
    alert_id: str,
    data_path_id: str,
    filename_prefix_id: str,
    root_path_id: str,
    catalog_defaults: dict,
    context: str,
    id_number_id: str = None,
    output_folder_id: str = None,
    build_template_func=None,
):
    """
    Register a callback to update path fields (data_path, filenamePrefix, and optionally outputFolder)
    by querying the database for catalog data based on the ID number.

    Parameters:
    - update_paths_id: ID of the update paths button
    - alert_id: ID of the alert component for status messages
    - data_path_id: ID of the data path field to update
    - filename_prefix_id: ID of the filename prefix field to update
    - root_path_id: ID of the root path field to update
    - catalog_defaults: Dictionary of catalog default values
    - context: The context for get_data_from_id ('wire_recon', 'recon', or 'peakindex')
    - id_number_id: ID of the ID number input field (optional, for IDnumber field)
    - output_folder_id: ID of the output folder field to update (optional)
    - build_template_func: Function to build output folder template (optional, signature: func(scan_num_int, data_path, **kwargs))

    Returns:
    - The registered callback function
    """

    # Validate that id_number_id is provided
    if not id_number_id:
        raise ValueError("id_number_id must be provided")

    @dash.callback(
        Input(update_paths_id, "n_clicks"),
        State(id_number_id, "value"),
        prevent_initial_call=True,
    )
    def update_path_fields_from_id(n_clicks, field_value):
        """Update path fields by querying reconstruction/catalog data based on ID number."""

        if not field_value:
            set_props(alert_id, {"is_open": True, "children": "Please enter an ID number first.", "color": "warning"})
            raise PreventUpdate

        root_path = DEFAULT_VARIABLES.get("root_path", "")

        with Session(session_utils.get_engine()) as session:
            try:
                # Parse ID number to get all IDs (handles semicolon-separated values)
                id_numbers = [s.strip() for s in str(field_value).split(";") if s]

                if not id_numbers:
                    set_props(alert_id, {"is_open": True, "children": "Invalid ID number format.", "color": "danger"})
                    raise PreventUpdate

                # Get data for each ID
                id_data_list = []
                for id_num in id_numbers:
                    try:
                        id_dict = parse_IDnumber(id_num, session)
                        id_data = get_data_from_id(session, id_dict, root_path, context, catalog_defaults)
                        if id_data and id_data.get("data_path"):
                            id_data_list.append(id_data)
                    except ValueError as e:
                        logger.warning(f"Could not parse ID number '{id_num}': {e}")
                        continue

                if id_data_list:
                    # If multiple IDs, merge the data using generic helper
                    if len(id_data_list) == 1:
                        merged_data = id_data_list[0]
                    else:
                        # Define which fields to merge
                        fields_to_merge = ["data_path", "filenamePrefix"]

                        merged_data = {}
                        for field_name in fields_to_merge:
                            field_values = [d.get(field_name) for d in id_data_list]
                            merged_data[field_name] = _merge_field_values(field_values)

                    # Update the form fields
                    set_props(root_path_id, {"value": root_path})
                    set_props(data_path_id, {"value": merged_data["data_path"]})
                    set_props(filename_prefix_id, {"value": merged_data["filenamePrefix"]})

                    # Update output folder if build_template_func and output_folder_id are provided
                    if build_template_func and output_folder_id:
                        try:
                            # Parse ID numbers to extract individual IDs for template building
                            output_folders = []
                            for id_num in id_numbers:
                                id_dict = parse_IDnumber(id_num, session)
                                scan_num_int = id_dict.get("scanNumber")

                                # Convert to int if present
                                if scan_num_int:
                                    try:
                                        scan_num_int = int(scan_num_int)
                                    except (ValueError, TypeError):
                                        scan_num_int = None

                                # Get data_path for this ID (use first one if multiple)
                                current_data_path = (
                                    merged_data["data_path"].split(";")[0].strip()
                                    if ";" in merged_data["data_path"]
                                    else merged_data["data_path"]
                                )

                                # Build template with available IDs (kwargs will contain wirerecon_id_int, recon_id_int for peakindexing)
                                template_kwargs = {}
                                if "wirerecon_id" in id_dict and id_dict["wirerecon_id"]:
                                    try:
                                        template_kwargs["wirerecon_id_int"] = int(id_dict["wirerecon_id"])
                                    except (ValueError, TypeError):
                                        pass
                                if "recon_id" in id_dict and id_dict["recon_id"]:
                                    try:
                                        template_kwargs["recon_id_int"] = int(id_dict["recon_id"])
                                    except (ValueError, TypeError):
                                        pass

                                output_folder = build_template_func(
                                    scan_num_int=scan_num_int, data_path=current_data_path, **template_kwargs
                                )
                                output_folders.append(output_folder)

                            # Merge output folders
                            merged_output_folder = _merge_field_values(output_folders)

                            set_props(output_folder_id, {"value": merged_output_folder})
                        except Exception as e:
                            logger.warning(f"Could not build output folder template: {e}")

                    set_props(
                        alert_id,
                        {
                            "is_open": True,
                            "children": f"Successfully loaded path fields from database for IDs: {field_value}",
                            "color": "success",
                        },
                    )
                else:
                    set_props(
                        alert_id,
                        {
                            "is_open": True,
                            "children": f"No data found for IDs: {field_value}. Using defaults.",
                            "color": "warning",
                        },
                    )

            except ValueError as e:
                set_props(
                    alert_id, {"is_open": True, "children": f"Invalid ID number format: {str(e)}", "color": "danger"}
                )
            except Exception as e:
                set_props(alert_id, {"is_open": True, "children": f"Error loading data: {str(e)}", "color": "danger"})

    return update_path_fields_from_id


def register_load_file_indices_callback(
    button_id: str,
    data_loaded_signal_id: str,
    data_path_id: str,
    filename_prefix_id: str,
    scan_points_id: str,
    alert_id: str,
    root_path_id: str = "root_path",
    num_indices: int = 1,
    depth_range_id: str = None,
):
    """
    Register a callback to scan the data directory and automatically populate
    the scanPoints field (and optionally depthRange field) with file indices.

    Parameters:
    - button_id: ID of the load button
    - data_loaded_signal_id: ID of the data loaded signal store
    - data_path_id: ID of the data path field
    - filename_prefix_id: ID of the filename prefix field
    - scan_points_id: ID of the scan points field to update
    - alert_id: ID of the alert component
    - root_path_id: ID of the root path form field (default 'root_path')
    - num_indices: Number of indices to extract (1 for wire recon, 2 for peak indexing)
    - depth_range_id: ID of depth range field (only for peak indexing with num_indices=2)

    Returns:
    - The registered callback function
    """

    @dash.callback(
        Input(button_id, "n_clicks"),
        Input(data_loaded_signal_id, "data"),
        State(data_path_id, "value"),
        State(filename_prefix_id, "value"),
        State(root_path_id, "value"),
        prevent_initial_call=True,
    )
    def load_file_indices(n_clicks, data_loaded_signal, data_path, filenamePrefix, root_path_value):
        """Scan directory and populate scanPoints (and optionally depthRange) fields."""

        if not data_path:
            set_props(alert_id, {"is_open": True, "children": "Please specify a data path first.", "color": "warning"})
            raise PreventUpdate

        if not filenamePrefix:
            set_props(
                alert_id, {"is_open": True, "children": "Please specify a filename prefix first.", "color": "warning"}
            )
            raise PreventUpdate

        root_path = root_path_value or DEFAULT_VARIABLES.get("root_path", "")

        try:
            # Parse data_path
            data_path_list = parse_parameter(data_path)

            # Track indices separately per data path (not merged)
            scanpoint_indices_per_path = []  # List of sets, one per data path
            depth_indices_per_path = []  # List of sets, one per data path

            for current_data_path in data_path_list:
                current_full_data_path = resolve_path_with_root(current_data_path, root_path)

                # Initialize sets for this path
                path_scanpoint_indices = set()
                path_depth_indices = set()

                # Check if directory exists
                if not os.path.exists(current_full_data_path):
                    logger.warning(f"Directory does not exist: {current_full_data_path}")
                    scanpoint_indices_per_path.append(path_scanpoint_indices)
                    depth_indices_per_path.append(path_depth_indices)
                    continue

                # List all files in directory, filtering by valid extensions
                try:
                    files = filter_files_by_extension(current_full_data_path, VALID_HDF_EXTENSIONS)
                except Exception as e:
                    logger.error(f"Error reading directory {current_full_data_path}: {e}")
                    scanpoint_indices_per_path.append(path_scanpoint_indices)
                    depth_indices_per_path.append(path_depth_indices)
                    continue

                # Extract patterns and indices using helper function
                pattern_files = extract_index_patterns(files, num_indices)

                # Extract scanpoint and depth indices from all patterns for this path
                for _pattern, indices_list in pattern_files.items():
                    for indices in indices_list:
                        if indices:  # Skip empty index lists (files without numeric patterns)
                            if len(indices) == 1:
                                # Single index: scanPoint only
                                path_scanpoint_indices.add(indices[0])
                            elif len(indices) >= 2:
                                # Two or more indices: scanPoint and depth
                                path_scanpoint_indices.add(indices[0])
                                path_depth_indices.add(indices[1])

                # Store this path's indices
                scanpoint_indices_per_path.append(path_scanpoint_indices)
                depth_indices_per_path.append(path_depth_indices)

            # Check if we found any indices
            if any(scanpoint_indices_per_path):
                # Create separate srange strings for each path
                scanpoints_ranges = []
                for path_indices in scanpoint_indices_per_path:
                    if path_indices:
                        scanpoints_ranges.append(str(srange(path_indices)))
                    else:
                        scanpoints_ranges.append("")

                # Use _merge_field_values to condense identical ranges
                scanpoints_range_str = _merge_field_values(scanpoints_ranges)

                # Update the scanPoints field
                set_props(scan_points_id, {"value": scanpoints_range_str})

                # Update depthRange field if we have depth indices
                if num_indices == 2 and any(depth_indices_per_path) and depth_range_id:
                    depth_ranges = []
                    for path_indices in depth_indices_per_path:
                        if path_indices:
                            depth_ranges.append(str(srange(path_indices)))
                        else:
                            depth_ranges.append("")

                    # Use _merge_field_values to condense identical ranges
                    depth_range_str = _merge_field_values(depth_ranges)
                    set_props(depth_range_id, {"value": depth_range_str})

                    # Count total unique indices across all paths for message
                    total_scanpoints = sum(len(s) for s in scanpoint_indices_per_path)
                    total_depths = sum(len(s) for s in depth_indices_per_path)

                    set_props(
                        alert_id,
                        {
                            "is_open": True,
                            "children": f"Successfully loaded {total_scanpoints} scan points and {total_depths} depth indices across {len(data_path_list)} path(s)",
                            "color": "success",
                        },
                    )
                else:
                    # Count total unique indices across all paths for message
                    total_scanpoints = sum(len(s) for s in scanpoint_indices_per_path)

                    set_props(
                        alert_id,
                        {
                            "is_open": True,
                            "children": f"Successfully loaded {total_scanpoints} file indices across {len(data_path_list)} path(s): {scanpoints_range_str}",
                            "color": "success",
                        },
                    )
            else:
                set_props(
                    alert_id,
                    {
                        "is_open": True,
                        "children": "No matching files found in the specified directory.",
                        "color": "warning",
                    },
                )

        except Exception as e:
            set_props(
                alert_id, {"is_open": True, "children": f"Error loading file indices: {str(e)}", "color": "danger"}
            )

    return load_file_indices


def register_check_filenames_callback(
    find_filenames_id: str,
    data_path_id: str,
    filename_prefix_id: str,
    filename_templates_id: str,
    root_path_id: str = "root_path",
    num_indices: int = 1,
    scan_points_id: str = None,
    depth_range_id: str = None,
):
    """
    Register a callback to scan directory and suggest common filename patterns.
    Replaces numeric sequences with %d to find templates and shows index ranges.
    Supports smart context-aware dropdown that adapts based on current field value.

    In Mode 1A (no current match), the first suggested pattern is auto-populated
    into the filename field.  If scan_points_id (and optionally depth_range_id)
    are provided, the corresponding index range fields are also auto-populated.

    Parameters:
    - find_filenames_id: ID of the find filenames button
    - data_path_id: ID of the data path field
    - filename_prefix_id: ID of the filename prefix field to auto-set
    - filename_templates_id: ID of the filename templates dropdown to populate with patterns
    - root_path_id: ID of the root path form field (default 'root_path')
    - num_indices: Maximum number of rightmost numeric indices to capture (will try this and fewer)
    - scan_points_id: ID of the scan points field to auto-populate in Mode 1A (optional)
    - depth_range_id: ID of the depth range field to auto-populate in Mode 1A (optional)

    Returns:
    - The registered callback function
    """

    @dash.callback(
        Output(filename_templates_id, "children"),
        Output(filename_prefix_id, "value", allow_duplicate=True),
        Input(find_filenames_id, "n_clicks"),
        State(data_path_id, "value"),
        State(filename_prefix_id, "value"),
        State(root_path_id, "value"),
        running=[
            (Output(find_filenames_id, "disabled"), True, False),
            (
                Output(find_filenames_id, "children"),
                [dbc.Spinner(size="sm", spinner_class_name="me-2"), "Scanning..."],
                "Find file names",
            ),
        ],
        prevent_initial_call=True,
    )
    def check_filenames(n_check, data_path, current_filename, root_path_value, delimiter=";"):
        """Scan directory and suggest common filename patterns with smart context-aware dropdown."""

        if not data_path:
            return [html.Option(value="", label="No data path provided")], dash.no_update

        data_path_list = parse_parameter(data_path)
        num_paths = len(data_path_list)
        root_path = root_path_value or DEFAULT_VARIABLES.get("root_path", "")

        # Scan each path independently
        patterns_by_path = {}
        for i, current_data_path in enumerate(data_path_list):
            full_path = resolve_path_with_root(current_data_path, root_path)
            patterns_by_path[i] = scan_directory_patterns(full_path, VALID_HDF_EXTENSIONS, num_indices)

        if not any(patterns_by_path.values()):
            return [html.Option(value="", label="No files found in specified path(s)")], dash.no_update

        # --- Mode detection ---
        current_filename = (
            _merge_field_values(current_filename) if isinstance(current_filename, list) else current_filename
        )
        current_parts = [s.strip() for s in (current_filename or "").split(delimiter)]
        while len(current_parts) < num_paths:
            current_parts.append("")

        has_any_match = False
        mismatch_index = None

        for i in range(num_paths):
            suggested = [p for (p, _) in patterns_by_path.get(i, [])]
            if current_parts[i] in suggested:
                has_any_match = True
            elif mismatch_index is None:
                mismatch_index = i
            if has_any_match and mismatch_index is not None:
                break

        # --- Dropdown generation ---
        if not has_any_match or mismatch_index is None:
            return _build_mode1_dropdown(
                patterns_by_path,
                num_paths,
                current_parts,
                has_any_match,
                delimiter,
                scan_points_id=scan_points_id,
                depth_range_id=depth_range_id,
            )
        else:
            return _build_mode2_dropdown(patterns_by_path, num_paths, current_parts, mismatch_index, delimiter)

    return check_filenames


# ---------------------------------------------------------------------------
# Dropdown builder helpers (used only by check_filenames)
# ---------------------------------------------------------------------------


def _populate_index_fields(pattern_indices_per_path, num_paths, delimiter, scan_points_id, depth_range_id=None):
    """
    Populate scanPoints (and optionally depthRange) fields via set_props
    using the index data from the first suggested pattern.

    Parameters:
        pattern_indices_per_path: List of indices_lists, one per path.
        num_paths: Number of data paths.
        delimiter: Delimiter for merging multi-path values.
        scan_points_id: Component ID for the scan points field.
        depth_range_id: Component ID for the depth range field (optional).
    """
    scanpoint_ranges = []
    depth_ranges = []

    for path_indices_list in pattern_indices_per_path:
        path_scanpoints = set()
        path_depths = set()
        for indices in path_indices_list:
            if not indices:
                continue
            if len(indices) >= 1:
                path_scanpoints.add(indices[0])
            if len(indices) >= 2:
                path_depths.add(indices[1])

        scanpoint_ranges.append(str(srange(path_scanpoints)) if path_scanpoints else "")
        depth_ranges.append(str(srange(path_depths)) if path_depths else "")

    scanpoints_str = _merge_field_values(scanpoint_ranges, delimiter)
    if scanpoints_str:
        set_props(scan_points_id, {"value": scanpoints_str})

    if depth_range_id:
        depth_str = _merge_field_values(depth_ranges, delimiter)
        if depth_str:
            set_props(depth_range_id, {"value": depth_str})


def _find_matched_indices(patterns_by_path, num_paths, current_parts):
    """
    For each path, find the indices_list of the pattern that matches the
    current filename part.  Returns a list of indices_lists (one per path),
    or None if no matches are found.
    """
    result = []
    found_any = False
    for i in range(num_paths):
        matched = False
        for pattern, indices_list in patterns_by_path.get(i, []):
            if pattern == current_parts[i]:
                result.append(indices_list)
                matched = True
                found_any = True
                break
        if not matched:
            result.append([])
    return result if found_any else None


def _build_mode1_dropdown(
    patterns_by_path, num_paths, current_parts, has_any_match, delimiter, scan_points_id=None, depth_range_id=None
):
    """
    Build dropdown for Mode 1A (no match -> auto-populate) or
    Mode 1B (all match -> show dropdown, keep value).

    In Mode 1A, if scan_points_id / depth_range_id are provided the
    corresponding fields are also populated via set_props using the
    index ranges from the first (best) suggested pattern.
    """
    max_patterns = max(
        (len(patterns_by_path.get(i, [])) for i in range(num_paths)),
        default=0,
    )
    if max_patterns == 0:
        return [html.Option(value="", label="No files found in specified path(s)")], dash.no_update

    dropdown_options = []
    first_option_value = None
    first_option_indices = None  # indices from the first pattern per path

    for pattern_idx in range(max_patterns):
        parts = []
        labels = []
        pattern_indices = []  # collect indices per path for this row
        for i in range(num_paths):
            patterns = patterns_by_path.get(i, [])
            if pattern_idx < len(patterns):
                pattern, indices_list = patterns[pattern_idx]
                parts.append(pattern)
                labels.append(build_pattern_label(pattern, indices_list))
                pattern_indices.append(indices_list)
            else:
                parts.append("")
                labels.append("(no more patterns)")
                pattern_indices.append([])

        if not any(parts):
            continue

        value = _merge_field_values(parts, delimiter)
        label = _merge_field_values(labels, delimiter)
        dropdown_options.append(html.Option(value=value, label=label))

        if first_option_value is None:
            first_option_value = value
            first_option_indices = pattern_indices

    # Preserve extra segments beyond num_paths
    if len(current_parts) > num_paths and first_option_value:
        extra_parts = current_parts[num_paths:]
        first_option_parts = first_option_value.split(delimiter)
        first_option_parts.extend(extra_parts)
        first_option_value = _merge_field_values(first_option_parts, delimiter)
        if dropdown_options:
            dropdown_options[0] = html.Option(value=first_option_value, label=dropdown_options[0]["props"]["label"])

    # Always populate index fields when scan_points_id is provided.
    # The user explicitly clicked "Find file names" so they expect a refresh.
    if scan_points_id:
        if not has_any_match:
            # Mode 1A: use indices from the first (best) suggestion
            indices_to_populate = first_option_indices
        else:
            # Mode 1B: filename already matches -- find indices for the
            # matched pattern in each path
            indices_to_populate = _find_matched_indices(patterns_by_path, num_paths, current_parts)

        if indices_to_populate:
            _populate_index_fields(
                indices_to_populate,
                num_paths,
                delimiter,
                scan_points_id,
                depth_range_id,
            )

    if not has_any_match:
        # Mode 1A: auto-populate filename with first suggestion
        return dropdown_options, first_option_value or ""
    else:
        # Mode 1B: keep current filename value
        return dropdown_options, dash.no_update


def _build_mode2_dropdown(patterns_by_path, num_paths, current_parts, mismatch_index, delimiter):
    """
    Build dropdown for Mode 2: suggest options only for the first mismatched
    path position, keeping the rest unchanged.
    """
    suggested_tuples = patterns_by_path.get(mismatch_index, [])
    dropdown_options = []

    for pattern, indices_list in suggested_tuples:
        parts = current_parts.copy()
        parts[mismatch_index] = pattern
        value = _merge_field_values(parts, delimiter)

        # Build label with arrow indicator on the varying position
        label_parts = []
        for i in range(num_paths):
            if i == mismatch_index:
                label_parts.append(f"→ {build_pattern_label(pattern, indices_list)}")
            else:
                label_generated = False
                for p, idx_list in patterns_by_path.get(i, []):
                    if p == current_parts[i]:
                        label_parts.append(build_pattern_label(p, idx_list))
                        label_generated = True
                        break
                if not label_generated:
                    label_parts.append(current_parts[i])

        # Use | around the varying position, ; elsewhere
        label_segments = []
        for i, part in enumerate(label_parts):
            if i == 0:
                label_segments.append(part)
            elif i == mismatch_index or i == mismatch_index + 1:
                label_segments.append(f" | {part}")
            else:
                label_segments.append(f" {delimiter} {part}")
        label = "".join(label_segments)

        dropdown_options.append(html.Option(value=value, label=label))

    return dropdown_options, dash.no_update
