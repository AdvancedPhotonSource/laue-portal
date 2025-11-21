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
import re
from difflib import SequenceMatcher
from itertools import combinations

import dash
from dash import html, Input, Output, State, set_props
from dash.exceptions import PreventUpdate
from sqlalchemy.orm import Session

import laue_portal.database.session_utils as session_utils
from laue_portal.database.db_utils import get_data_from_id, parse_parameter, parse_IDnumber
from laue_portal.config import DEFAULT_VARIABLES, VALID_HDF_EXTENSIONS
from srange import srange

logger = logging.getLogger(__name__)


def _filter_files_by_extension(directory_path):
    """
    List and filter files in a directory by valid HDF extensions.
    
    This helper function reads all files from a directory and filters them
    to only include files with valid HDF extensions as configured in
    VALID_HDF_EXTENSIONS.
    
    Parameters:
    - directory_path: Full path to the directory to scan
    
    Returns:
    - List of filenames that match the valid HDF extensions
    
    Raises:
    - Exception: If there's an error reading the directory
    """
    all_files = [f for f in os.listdir(directory_path) if os.path.isfile(os.path.join(directory_path, f))]
    
    # Filter by valid HDF extensions if configured
    if VALID_HDF_EXTENSIONS:
        filtered_files = [f for f in all_files if any(f.lower().endswith(ext.lower()) for ext in VALID_HDF_EXTENSIONS)]
        return filtered_files
    else:
        return all_files


def _extract_indices_from_files(files, num_indices):
    """
    Extract indices from filenames by adaptively trying to match num_indices down to 1.
    
    This helper function processes a list of filenames and extracts numeric indices
    by trying to match patterns with decreasing numbers of indices (from num_indices
    down to 1). This allows handling files with varying numbers of indices.
    
    Parameters:
    - files: List of filenames to process
    - num_indices: Maximum number of rightmost numeric indices to try matching
    
    Returns:
    - Dictionary mapping patterns to lists of indices
      e.g., {'Si-wire_%d.h5': [[7], [8], [9]], 'Si-wire_%d_%d.h5': [[7,5], [8,5]]}
    """
    pattern_files = {}
    
    for filename in files:
        base_name, extension = os.path.splitext(filename)
        
        # Try matching with num_indices, then num_indices-1, down to 1
        matched = False
        for n in range(num_indices, 0, -1):
            # Build regex pattern to capture N rightmost numbers
            if n == 1:
                regex_pattern = r'(\d+)(?!.*\d)'
            else:
                # Capture N groups of digits separated by underscores from the right
                regex_pattern = r'_'.join([r'(\d+)'] * n) + r'(?!.*\d)'
            
            match = re.search(regex_pattern, base_name)
            
            if match:
                # Extract all captured groups as integers
                indices = [int(match.group(i)) for i in range(1, n + 1)]
                
                # Create pattern with appropriate number of %d placeholders
                pattern_placeholder = '_'.join(['%d'] * n)
                pattern = base_name[:match.start()] + pattern_placeholder + base_name[match.end():] + extension
                
                pattern_files.setdefault(pattern, []).append(indices)
                matched = True
                break  # Stop trying fewer indices once we found a match
        
        if not matched:
            # No numeric pattern found
            pattern_files.setdefault(filename, []).append([])
    
    return pattern_files


def _merge_field_values(field_values, delimiter="; "):
    """
    Merge multiple field values, handling list types properly.
    
    This helper function merges values from multiple database entries, properly
    handling list-type fields (like filenamePrefix) by joining list elements with
    commas first, then joining multiple values with the specified delimiter.
    
    Parameters:
    - field_values: List of field values (can be lists, strings, or other types)
    - delimiter: Delimiter used to separate multiple values (default "; ")
    
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
    return delimiter.join([
        ','.join(v) if isinstance(v, list) else str(v) 
        for v in field_values
    ])


def _generate_dropdown_for_position(base_parts, position, pattern_tuples, delimiter="; "):
    """
    Generate dropdown options by varying the pattern at a given position.
    
    This helper function creates dropdown options where one position varies through
    different patterns while other positions remain fixed. It generates informative
    labels showing file counts/ranges for the varying pattern.
    
    Parameters:
    - base_parts: List of base pattern strings for all positions
    - position: Index of the position to vary
    - pattern_tuples: List of (pattern, indices_list) tuples for this position
    - delimiter: Delimiter to join parts (default "; ")
    
    Returns:
    - List of html.Option elements with value and informative label
    """
    dropdown_options = []
    
    for pattern, indices_list in pattern_tuples:
        # Build full delimiter-separated string with this pattern at position i
        new_parts = base_parts.copy()
        new_parts[position] = pattern
        full_value = delimiter.join(new_parts)
        
        # Build informative label for this pattern
        if indices_list and indices_list[0]:
            actual_num_indices = len(indices_list[0])
            
            if actual_num_indices == 1:
                # Single index: show simple range
                pattern_label = f"{pattern} (files {str(srange(set(idx[0] for idx in indices_list)))})"
            elif actual_num_indices > 1:
                # Multiple indices: show ranges for each dimension
                range_labels = []
                dim_names = ['scanPoints', 'depths'] if actual_num_indices == 2 else [f"dim{i+1}" for i in range(actual_num_indices)]
                
                for dim in range(actual_num_indices):
                    dim_values = sorted(set(idx[dim] for idx in indices_list if len(idx) > dim))
                    if dim_values:
                        range_labels.append(f"{dim_names[dim]}: {str(srange(dim_values))}")
                
                if range_labels:
                    pattern_label = f"{pattern} ({', '.join(range_labels)})"
                else:
                    pattern_label = f"{pattern} ({len(indices_list)} file{'s' if len(indices_list) != 1 else ''})"
            else:
                # No indices (shouldn't happen with our logic, but handle it)
                pattern_label = f"{pattern} ({len(indices_list)} file{'s' if len(indices_list) != 1 else ''})"
        else:
            # No indices available
            pattern_label = pattern
        
        # Build full label with informative label only at the varying position
        label_parts = base_parts.copy()
        label_parts[position] = pattern_label
        full_label = delimiter.join(label_parts)
        
        dropdown_options.append(html.Option(value=full_value, label=full_label))
    
    return dropdown_options


def register_update_path_fields_callback(
    update_paths_id: str,
    alert_id: str,
    data_path_id: str,
    filename_prefix_id: str,
    root_path_id: str,
    catalog_defaults: dict,
    id_number_id: str = None,
    output_folder_id: str = None,
    build_template_func = None
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
        Input(update_paths_id, 'n_clicks'),
        State(id_number_id, 'value'),
        prevent_initial_call=True,
    )
    def update_path_fields_from_id(n_clicks, field_value):
        """Update path fields by querying reconstruction/catalog data based on ID number."""
        
        if not field_value:
            set_props(alert_id, {
                'is_open': True,
                'children': 'Please enter an ID number first.',
                'color': 'warning'
            })
            raise PreventUpdate
        
        root_path = DEFAULT_VARIABLES.get("root_path", "")
        
        with Session(session_utils.get_engine()) as session:
            try:
                # Parse ID number to get all IDs (handles semicolon-separated values)
                id_numbers = [s.strip() for s in str(field_value).split(';') if s]
                
                if not id_numbers:
                    set_props(alert_id, {
                        'is_open': True,
                        'children': 'Invalid ID number format.',
                        'color': 'danger'
                    })
                    raise PreventUpdate
                
                # Get data for each ID
                id_data_list = []
                for id_num in id_numbers:
                    try:
                        id_dict = parse_IDnumber(id_num, session)
                        id_data = get_data_from_id(session, id_dict, root_path, catalog_defaults)
                        if id_data and id_data.get('data_path'):
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
                        fields_to_merge = ['data_path', 'filenamePrefix']
                        
                        merged_data = {}
                        for field_name in fields_to_merge:
                            field_values = [d.get(field_name) for d in id_data_list]
                            merged_data[field_name] = _merge_field_values(field_values)
                    
                    # Update the form fields
                    set_props(root_path_id, {'value': root_path})
                    set_props(data_path_id, {'value': merged_data['data_path']})
                    set_props(filename_prefix_id, {'value': merged_data['filenamePrefix']})
                    
                    # Update output folder if build_template_func and output_folder_id are provided
                    if build_template_func and output_folder_id:
                        try:
                            # Parse ID numbers to extract individual IDs for template building
                            output_folders = []
                            for id_num in id_numbers:
                                id_dict = parse_IDnumber(id_num, session)
                                scan_num_int = id_dict.get('scanNumber')
                                
                                # Convert to int if present
                                if scan_num_int:
                                    try:
                                        scan_num_int = int(scan_num_int)
                                    except (ValueError, TypeError):
                                        scan_num_int = None
                                
                                # Get data_path for this ID (use first one if multiple)
                                current_data_path = merged_data['data_path'].split(';')[0].strip() if ';' in merged_data['data_path'] else merged_data['data_path']
                                
                                # Build template with available IDs (kwargs will contain wirerecon_id_int, recon_id_int for peakindexing)
                                template_kwargs = {}
                                if 'wirerecon_id' in id_dict and id_dict['wirerecon_id']:
                                    try:
                                        template_kwargs['wirerecon_id_int'] = int(id_dict['wirerecon_id'])
                                    except (ValueError, TypeError):
                                        pass
                                if 'recon_id' in id_dict and id_dict['recon_id']:
                                    try:
                                        template_kwargs['recon_id_int'] = int(id_dict['recon_id'])
                                    except (ValueError, TypeError):
                                        pass
                                
                                output_folder = build_template_func(
                                    scan_num_int=scan_num_int,
                                    data_path=current_data_path,
                                    **template_kwargs
                                )
                                output_folders.append(output_folder)
                            
                            # Merge output folders
                            merged_output_folder = _merge_field_values(output_folders)
                            
                            set_props(output_folder_id, {'value': merged_output_folder})
                        except Exception as e:
                            logger.warning(f"Could not build output folder template: {e}")
                    
                    set_props(alert_id, {
                        'is_open': True,
                        'children': f'Successfully loaded path fields from database for IDs: {field_value}',
                        'color': 'success'
                    })
                else:
                    set_props(alert_id, {
                        'is_open': True,
                        'children': f'No data found for IDs: {field_value}. Using defaults.',
                        'color': 'warning'
                    })
            
            except ValueError as e:
                set_props(alert_id, {
                    'is_open': True,
                    'children': f'Invalid ID number format: {str(e)}',
                    'color': 'danger'
                })
            except Exception as e:
                set_props(alert_id, {
                    'is_open': True,
                    'children': f'Error loading data: {str(e)}',
                    'color': 'danger'
                })
    
    return update_path_fields_from_id


def register_load_file_indices_callback(
    button_id: str,
    data_loaded_signal_id: str,
    data_path_id: str,
    filename_prefix_id: str,
    scan_points_id: str,
    alert_id: str,
    num_indices: int = 1,
    depth_range_id: str = None
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
    - num_indices: Number of indices to extract (1 for wire recon, 2 for peak indexing)
    - depth_range_id: ID of depth range field (only for peak indexing with num_indices=2)
    
    Returns:
    - The registered callback function
    """
    
    @dash.callback(
        Input(button_id, 'n_clicks'),
        Input(data_loaded_signal_id, 'data'),
        State(data_path_id, 'value'),
        State(filename_prefix_id, 'value'),
        prevent_initial_call=True,
    )
    def load_file_indices(n_clicks, data_loaded_signal, data_path, filenamePrefix):
        """Scan directory and populate scanPoints (and optionally depthRange) fields."""
        
        if not data_path:
            set_props(alert_id, {
                'is_open': True,
                'children': 'Please specify a data path first.',
                'color': 'warning'
            })
            raise PreventUpdate
        
        if not filenamePrefix:
            set_props(alert_id, {
                'is_open': True,
                'children': 'Please specify a filename prefix first.',
                'color': 'warning'
            })
            raise PreventUpdate
        
        root_path = DEFAULT_VARIABLES.get("root_path", "")
        
        try:
            # Parse data_path
            data_path_list = parse_parameter(data_path)
            
            # Collect all indices from all data paths
            all_scanpoint_indices = set()
            all_depth_indices = set()
            
            for current_data_path in data_path_list:
                current_full_data_path = os.path.join(root_path, current_data_path.lstrip('/'))
                
                # Check if directory exists
                if not os.path.exists(current_full_data_path):
                    logger.warning(f"Directory does not exist: {current_full_data_path}")
                    continue
                
                # List all files in directory, filtering by valid extensions
                try:
                    files = _filter_files_by_extension(current_full_data_path)
                except Exception as e:
                    logger.error(f"Error reading directory {current_full_data_path}: {e}")
                    continue
                
                # Extract patterns and indices using helper function
                pattern_files = _extract_indices_from_files(files, num_indices)
                
                # Extract scanpoint and depth indices from all patterns
                for pattern, indices_list in pattern_files.items():
                    for indices in indices_list:
                        if indices:  # Skip empty index lists (files without numeric patterns)
                            if len(indices) == 1:
                                # Single index: scanPoint only
                                all_scanpoint_indices.add(indices[0])
                            elif len(indices) >= 2:
                                # Two or more indices: scanPoint and depth
                                all_scanpoint_indices.add(indices[0])
                                all_depth_indices.add(indices[1])
            
            if all_scanpoint_indices:
                # Create srange strings (srange handles sorting internally)
                scanpoints_range = str(srange(all_scanpoint_indices))
                
                # Update the scanPoints field
                set_props(scan_points_id, {'value': scanpoints_range})
                
                # Update depthRange field if we have depth indices
                if num_indices == 2 and all_depth_indices and depth_range_id:
                    depth_range = str(srange(all_depth_indices))
                    set_props(depth_range_id, {'value': depth_range})
                    
                    set_props(alert_id, {
                        'is_open': True,
                        'children': f'Successfully loaded {len(all_scanpoint_indices)} scan points ({scanpoints_range}) and {len(all_depth_indices)} depth indices ({depth_range})',
                        'color': 'success'
                    })
                else:
                    set_props(alert_id, {
                        'is_open': True,
                        'children': f'Successfully loaded {len(all_scanpoint_indices)} file indices: {scanpoints_range}',
                        'color': 'success'
                    })
            else:
                set_props(alert_id, {
                    'is_open': True,
                    'children': 'No matching files found in the specified directory.',
                    'color': 'warning'
                })
        
        except Exception as e:
            set_props(alert_id, {
                'is_open': True,
                'children': f'Error loading file indices: {str(e)}',
                'color': 'danger'
            })
    
    return load_file_indices


def register_check_filenames_callback(
    find_filenames_id: str,
    update_paths_id: str,
    data_loaded_signal_id: str,
    data_path_id: str,
    filename_prefix_id: str,
    filename_templates_id: str,
    cached_patterns_store_id: str,
    num_indices: int = 1
):
    """
    Register a callback to scan directory and suggest common filename patterns.
    Replaces numeric sequences with %d to find templates and shows index ranges.
    Supports smart context-aware dropdown that adapts based on current field value.
    
    Parameters:
    - find_filenames_id: ID of the find filenames button
    - update_paths_id: ID of the update paths button
    - data_loaded_signal_id: ID of the data loaded signal store
    - data_path_id: ID of the data path field
    - filename_prefix_id: ID of the filename prefix field to auto-set
    - filename_templates_id: ID of the filename templates dropdown to populate with patterns
    - cached_patterns_store_id: ID of the Store component to cache scanned patterns per path
    - num_indices: Maximum number of rightmost numeric indices to capture (will try this and fewer)
    
    Returns:
    - The registered callback function
    """
    
    @dash.callback(
        Output(filename_templates_id, 'children'),
        Output(filename_prefix_id, 'value', allow_duplicate=True),
        Output(cached_patterns_store_id, 'data'),
        Input(find_filenames_id, 'n_clicks'),
        # Input(update_paths_id, 'n_clicks'),
        # Input(data_loaded_signal_id, 'data'),
        State(data_path_id, 'value'),
        State(filename_prefix_id, 'value'),
        State(cached_patterns_store_id, 'data'),
        prevent_initial_call=True,
    )
    # def check_filenames(n_check, n_update, data_loaded_signal_id, data_path, current_filename, cached_patterns, delimiter="; "):
    def check_filenames(n_check, data_path, current_filename, cached_patterns, delimiter="; "):
        """Scan directory and suggest common filename patterns with smart context-aware dropdown."""
        
        if not data_path:
            return [html.Option(value="", label="No data path provided")], dash.no_update, {}
        
        # Parse data_path to get number of paths
        data_path_list = parse_parameter(data_path)
        num_paths = len(data_path_list)
        root_path = DEFAULT_VARIABLES["root_path"]
        
        # EARLY CACHE CHECK - avoid expensive directory scanning if we have valid cached data
        if cached_patterns and all(i in cached_patterns for i in range(num_paths)):
            # Cache hit - use cached patterns and skip directory scanning entirely
            cached_patterns_found = True
            patterns_by_path = cached_patterns
        else:
            # PATTERN SCANNING PER PATH
            # Cache miss or invalid - perform fresh directory scan
            cached_patterns_found = False
            # Scan each path independently and store patterns per path
            patterns_by_path = {}  # {path_index: [(pattern, indices_list), ...]}
            
            for i, current_data_path in enumerate(data_path_list):
                current_full_data_path = os.path.join(root_path, current_data_path.lstrip('/'))
                
                # Check if directory exists
                if not os.path.exists(current_full_data_path):
                    logger.warning(f"Directory does not exist: {current_full_data_path}")
                    patterns_by_path[i] = []
                    continue
                
                # List all files in directory, filtering by valid extensions
                try:
                    files = _filter_files_by_extension(current_full_data_path)
                except Exception as e:
                    logger.error(f"Error reading directory {current_full_data_path}: {e}")
                    patterns_by_path[i] = []
                    continue
                
                # Extract patterns and indices using helper function for this path
                path_pattern_files = _extract_indices_from_files(files, num_indices)
                
                # Sort by file count and take top 10
                sorted_path_patterns = sorted(path_pattern_files.items(), key=lambda x: len(x[1]), reverse=True)[:10]
                
                # Generate wildcards for this path's similar patterns
                # Use smart wildcard detection: preserve %d when both patterns have it
                path_wildcard_patterns = {}  # pattern -> (indices_list, num_asterisks)
                if len(sorted_path_patterns) > 1:
                    for (pattern1, indices1), (pattern2, indices2) in combinations(sorted_path_patterns, 2):
                        # Find matching and differing sections
                        matcher = SequenceMatcher(None, pattern1, pattern2)
                        wildcard_parts = []
                        last_pos = 0
                        
                        for match_start1, match_start2, match_length in matcher.get_matching_blocks():
                            # Handle the gap before this match (differences)
                            if match_start1 > last_pos:
                                wildcard_parts.append('*')

                            # Add the matching section
                            if match_length > 0:  # Matches preserved #The %d is preserved because it's in the matching section.
                                wildcard_parts.append(pattern1[match_start1:match_start1 + match_length])
                            last_pos = match_start1 + match_length
                        
                        # Create wildcard pattern if it has differences
                        wildcard_pattern = ''.join(wildcard_parts)
                        if '*' in wildcard_pattern:
                            # Combine indices from both pattern
                            combined_indices = indices1 + indices2

                            # If we've seen this pattern before, extend its indices
                            if wildcard_pattern in path_wildcard_patterns:
                                path_wildcard_patterns[wildcard_pattern][0].extend(combined_indices)
                            else:
                                num_asterisks = wildcard_pattern.count('*')
                                path_wildcard_patterns[wildcard_pattern] = [combined_indices, num_asterisks]
                
                # Sort wildcards and combine with regular patterns
                # Sort wildcard patterns by number of asterisks (ascending), then by file count (descending)
                sorted_wildcards = sorted(
                    path_wildcard_patterns.items(),
                    key=lambda x: (x[1][1], -len(x[1][0]))  # (num_asterisks, -file_count)
                )
                
                # Build final pattern list for this path as tuples: (pattern, indices_list)
                # Wildcards first, then regular patterns
                path_pattern_tuples = []
                for wc_pattern, (indices_list, num_asterisks) in sorted_wildcards:
                    path_pattern_tuples.append((wc_pattern, indices_list))
                for pattern, indices_list in sorted_path_patterns:
                    path_pattern_tuples.append((pattern, indices_list))
                
                # Take top 10 total
                patterns_by_path[i] = path_pattern_tuples[:10]
        
        if not any(patterns_by_path.values()):
            return [html.Option(value="", label="No files found in specified path(s)")], dash.no_update, {}
        
        # MODE DETECTION AND DROPDOWN GENERATION
        # # Get the trigger that caused this callback
        # ctx = dash.callback_context
        # trigger_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None
        
        # Convert list to string if needed, then split into delimiter-separated parts
        current_filename = _merge_field_values(current_filename) if isinstance(current_filename, list) else current_filename
        current_parts = [s.strip() for s in (current_filename or "").split(delimiter)]
        # Pad with empty strings if fewer than num_paths to ensure safe indexing
        while len(current_parts) < num_paths:
            current_parts.append("")
        
        # Detect if ANY matches exist AND find first mismatch from left to right
        has_any_match = False
        mismatch_index = None
        
        for i in range(num_paths):
            suggested_tuples = patterns_by_path.get(i, [])
            # Extract just the patterns from tuples for comparison
            suggested_patterns = [p for (p, _) in suggested_tuples] if suggested_tuples else []
            
            if current_parts[i] in suggested_patterns:
                has_any_match = True
            elif mismatch_index is None:  # Record first mismatch
                mismatch_index = i
            
            # Early exit optimization: if we have both a match and a mismatch, we're done
            if has_any_match and mismatch_index is not None:
                break
        
        if not has_any_match or mismatch_index is None:
            # MODE 1: No matches or only matches found
            # Auto-select the first pattern in each path's sorted list
            auto_selected = []
            for i in range(num_paths):
                path_pattern_tuples = patterns_by_path.get(i, [])
                # Select the first pattern (from tuple) in the sorted list
                auto_selected.append(path_pattern_tuples[0][0] if path_pattern_tuples else "")
            
            # Preserve any extra segments beyond num_paths
            if len(current_parts) > num_paths:
                auto_selected.extend(current_parts[num_paths:])
            
            # Generate dropdown with top patterns per path using helper function
            dropdown_options = []
            for i in range(num_paths):
                path_pattern_tuples = patterns_by_path.get(i, [])
                dropdown_options.extend(
                    _generate_dropdown_for_position(auto_selected, i, path_pattern_tuples, delimiter)
                )
            
            if not has_any_match:
                # MODE 1A: No matches found -> auto-populate field with the top dropdown value
                # Use _merge_field_values to condense if all patterns are the same
                auto_populated_value = _merge_field_values(auto_selected, delimiter)
                # Return: dropdown options, auto-populated value, patterns for caching (only if fresh scan)
                return dropdown_options, auto_populated_value, dash.no_update if cached_patterns_found else patterns_by_path
            else:
                # MODE 1B: All matches found (mismatch_index is None) -> keep current value, show dropdown
                # Return: dropdown options, keep current field value, patterns for caching (only if fresh scan)
                return dropdown_options, dash.no_update, dash.no_update if cached_patterns_found else patterns_by_path
        else:
            # MODE 2: At least one match found -> show suggestions for mismatched position, keep other positions unchanged
            suggested_tuples = patterns_by_path.get(mismatch_index, [])
            # Generate dropdown options for the mismatched position using helper
            dropdown_options = _generate_dropdown_for_position(
                current_parts, mismatch_index, suggested_tuples, delimiter
            )
            
            # Return: dropdown options, keep current field value, patterns for caching (only if fresh scan)
            return dropdown_options, dash.no_update, dash.no_update if cached_patterns_found else patterns_by_path
    
    return check_filenames
