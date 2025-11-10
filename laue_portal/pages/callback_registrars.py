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

import glob
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
from laue_portal.database.db_utils import get_data_from_id, parse_parameter
from laue_portal.config import DEFAULT_VARIABLES, VALID_HDF_EXTENSIONS
from laue_portal.components.peakindex_form import parse_IDnumber
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


def register_update_path_fields_callback(
    button_id: str,
    alert_id: str,
    data_path_id: str,
    filename_prefix_id: str,
    root_path_id: str,
    catalog_defaults: dict,
    id_number_id: str = None
):
    """
    Register a callback to update path fields (data_path, filenamePrefix) by querying
    the database for catalog data based on the ID number.
    
    Parameters:
    - button_id: ID of the button that triggers the update
    - alert_id: ID of the alert component for status messages
    - data_path_id: ID of the data path field to update
    - filename_prefix_id: ID of the filename prefix field to update
    - root_path_id: ID of the root path field to update
    - catalog_defaults: Dictionary of catalog default values
    - id_number_id: ID of the ID number input field (optional, for IDnumber field)
    
    Returns:
    - The registered callback function
    """
    
    # Validate that id_number_id is provided
    if not id_number_id:
        raise ValueError("id_number_id must be provided")
    
    @dash.callback(
        Input(button_id, 'n_clicks'),
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
                    # If multiple IDs, merge the data
                    if len(id_data_list) == 1:
                        merged_data = id_data_list[0]
                    else:
                        # Merge data paths and filename prefixes
                        data_paths = [d['data_path'] for d in id_data_list]
                        filename_prefixes = [d['filenamePrefix'] for d in id_data_list]
                        
                        # Check if all values are the same
                        if all(dp == data_paths[0] for dp in data_paths):
                            merged_data_path = data_paths[0]
                        else:
                            merged_data_path = "; ".join(data_paths)
                        
                        if all(fp == filename_prefixes[0] for fp in filename_prefixes):
                            merged_filename_prefix = filename_prefixes[0]
                        else:
                            merged_filename_prefix = "; ".join([','.join(fp) if isinstance(fp, list) else str(fp) for fp in filename_prefixes])
                        
                        merged_data = {
                            'data_path': merged_data_path,
                            'filenamePrefix': merged_filename_prefix
                        }
                    
                    # Update the form fields
                    set_props(root_path_id, {'value': root_path})
                    set_props(data_path_id, {'value': merged_data['data_path']})
                    
                    # Handle filenamePrefix - convert list to comma-separated string
                    if isinstance(merged_data['filenamePrefix'], list):
                        filename_str = ','.join(merged_data['filenamePrefix'])
                    else:
                        filename_str = str(merged_data['filenamePrefix']) if merged_data['filenamePrefix'] else ''
                    
                    set_props(filename_prefix_id, {'value': filename_str})
                    
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
    data_loaded_trigger_id: str,
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
    - data_loaded_trigger_id: ID of the data loaded trigger
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
        Input(data_loaded_trigger_id, 'data'),
        State(data_path_id, 'value'),
        State(filename_prefix_id, 'value'),
        prevent_initial_call=True,
    )
    def load_file_indices(n_clicks, data_loaded_trigger, data_path, filenamePrefix):
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
    check_button_id: str,
    update_button_id: str,
    data_loaded_trigger_id: str,
    data_path_id: str,
    filename_prefix_id: str,
    filename_templates_id: str,
    num_indices: int = 1
):
    """
    Register a callback to scan directory and suggest common filename patterns.
    Replaces numeric sequences with %d to find templates and shows index ranges.
    
    Parameters:
    - check_button_id: ID of the check filenames button
    - update_button_id: ID of the update path fields button
    - data_loaded_trigger_id: ID of the data loaded trigger
    - data_path_id: ID of the data path field
    - filename_prefix_id: ID of the filename prefix field to auto-set
    - filename_templates_id: ID of the filename templates dropdown to populate with patterns
    - num_indices: Maximum number of rightmost numeric indices to capture (will try this and fewer)
    
    Returns:
    - The registered callback function
    """
    
    @dash.callback(
        Output(filename_templates_id, 'children'),
        Input(check_button_id, 'n_clicks'),
        Input(update_button_id, 'n_clicks'),
        Input(data_loaded_trigger_id, 'data'),
        State(data_path_id, 'value'),
        prevent_initial_call=True,
    )
    def check_filenames(n_check, n_update, data_loaded_trigger, data_path):
        """Scan directory and suggest common filename patterns."""
        
        if not data_path:
            return [html.Option(value="", label="No data path provided")]
        
        # Parse data_path first to get the number of inputs
        data_path_list = parse_parameter(data_path)
        num_inputs = len(data_path_list)
        
        root_path = DEFAULT_VARIABLES["root_path"]
        
        # Dictionary to store pattern -> list of indices
        pattern_files = {}

        for i in range(num_inputs):
            # Get filefolder
            current_data_path = data_path_list[i]

            # Build full path
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
            current_pattern_files = _extract_indices_from_files(files, num_indices)
            
            # Merge into main pattern_files dictionary
            for pattern, indices_list in current_pattern_files.items():
                pattern_files.setdefault(pattern, []).extend(indices_list)
        
        if not pattern_files:
            return [html.Option(value="", label="No files found in specified path(s)")]
        
        # Sort by file count and create options for top 10 patterns
        sorted_patterns = sorted(pattern_files.items(), key=lambda x: len(x[1]), reverse=True)[:10]
        pattern_options = []
        
        for pattern, indices_list in sorted_patterns:
            if indices_list and indices_list[0]:
                # Determine actual number of indices in this pattern
                actual_num_indices = len(indices_list[0])
                
                if actual_num_indices == 1:
                    # Single index: show simple range
                    label = f"{pattern} (files {str(srange(set(idx[0] for idx in indices_list)))})"
                elif actual_num_indices > 1:
                    # Multiple indices: show ranges for each dimension
                    range_labels = []
                    dim_names = ['scanPoints', 'depths'] if actual_num_indices == 2 else [f"dim{i+1}" for i in range(actual_num_indices)]
                    
                    for dim in range(actual_num_indices):
                        dim_values = sorted(set(idx[dim] for idx in indices_list if len(idx) > dim))
                        if dim_values:
                            range_labels.append(f"{dim_names[dim]}: {str(srange(dim_values))}")
                    
                    if range_labels:
                        label = f"{pattern} ({', '.join(range_labels)})"
                    else:
                        label = f"{pattern} ({len(indices_list)} file{'s' if len(indices_list) != 1 else ''})"
                else:
                    # No indices (shouldn't happen with our logic, but handle it)
                    label = f"{pattern} ({len(indices_list)} file{'s' if len(indices_list) != 1 else ''})"
            else:
                label = f"{pattern} ({len(indices_list)} file{'s' if len(indices_list) != 1 else ''})"
            pattern_options.append(html.Option(value=pattern, label=label))
        
        # Generate combined wildcard patterns for similar patterns
        # Use smart wildcard detection: preserve %d when both patterns have it
        if len(sorted_patterns) > 1:
            seen_wildcards = set()
            
            for (pattern1, indices1), (pattern2, indices2) in combinations(sorted_patterns, 2):
                # Find matching and differing sections
                matcher = SequenceMatcher(None, pattern1, pattern2)
                wildcard_parts = []
                last_pos = 0
                
                for match_start1, match_start2, match_length in matcher.get_matching_blocks():
                    # Handle the gap before this match (differences)
                    if match_start1 > last_pos:
                        wildcard_parts.append('*')
                    
                    # Add the matching section
                    if match_length > 0:
                        wildcard_parts.append(pattern1[match_start1:match_start1 + match_length])
                    
                    last_pos = match_start1 + match_length
                
                # Create wildcard pattern if it has differences and hasn't been seen
                wildcard_pattern = ''.join(wildcard_parts)
                if '*' in wildcard_pattern and wildcard_pattern not in seen_wildcards:
                    seen_wildcards.add(wildcard_pattern)
                    
                    # Combine indices from both patterns for label
                    if num_indices == 1:
                        combined_indices = sorted(set(idx[0] for idx in indices1 + indices2 if idx))
                        label = f"{wildcard_pattern} (files {str(srange(combined_indices))})"
                    else:
                        # Multiple indices: show ranges for each dimension
                        combined_indices_list = indices1 + indices2
                        range_labels = []
                        dim_names = ['scanPoints', 'depths'] if num_indices == 2 else [f"dim{i+1}" for i in range(num_indices)]
                        
                        for dim in range(num_indices):
                            dim_values = sorted(set(idx[dim] for idx in combined_indices_list if len(idx) > dim))
                            if dim_values:
                                range_labels.append(f"{dim_names[dim]}: {str(srange(dim_values))}")
                        
                        if range_labels:
                            label = f"{wildcard_pattern} ({', '.join(range_labels)})"
                        else:
                            label = f"{wildcard_pattern} ({len(combined_indices_list)} files)"
                    
                    pattern_options.append(html.Option(value=wildcard_pattern, label=label))
        
        # Get the trigger that caused this callback
        ctx = dash.callback_context
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None
        
        # Smart pattern selection: prefer patterns with * (captures all files), then %d, then plain
        # Only set filenamePrefix if triggered by the check-filenames button
        if pattern_options and trigger_id == check_button_id:
            # Separate patterns by type
            patterns_with_asterisk = [opt for opt in pattern_options if '*' in opt.value]
            patterns_with_percent_d = [opt for opt in pattern_options if '%d' in opt.value and '*' not in opt.value]
            patterns_plain = [opt for opt in pattern_options if '*' not in opt.value and '%d' not in opt.value]
            
            # Decision tree: prefer * patterns (captures all files), then %d, then plain
            if patterns_with_asterisk:
                selected_pattern = min(patterns_with_asterisk, key=lambda opt: len(opt.value)).value
            elif patterns_with_percent_d:
                selected_pattern = min(patterns_with_percent_d, key=lambda opt: len(opt.value)).value
            else:
                selected_pattern = min(patterns_plain, key=lambda opt: len(opt.value)).value
            
            set_props(filename_prefix_id, {'value': selected_pattern})
        
        return pattern_options
    
    return check_filenames
