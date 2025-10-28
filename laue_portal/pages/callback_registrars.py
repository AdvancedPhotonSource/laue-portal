"""
Shared callback registration functions for Dash pages.

This module provides reusable callback registration functions that can be used
across multiple pages (e.g., wire reconstruction, peak indexing) with different
component IDs but identical logic.

Usage:
    from laue_portal.pages.callback_registrars import register_update_path_fields_callback
    
    register_update_path_fields_callback(
        button_id='wirerecon-update-path-fields-btn',
        scan_number_id='scanNumber',
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
from laue_portal.database.db_utils import get_catalog_data, parse_parameter
from laue_portal.config import DEFAULT_VARIABLES
from srange import srange

logger = logging.getLogger(__name__)


def register_update_path_fields_callback(
    button_id: str,
    scan_number_id: str,
    alert_id: str,
    data_path_id: str,
    filename_prefix_id: str,
    root_path_id: str,
    catalog_defaults: dict
):
    """
    Register a callback to update path fields (data_path, filenamePrefix) by querying
    the database for catalog data based on the scan number.
    
    Parameters:
    - button_id: ID of the button that triggers the update
    - scan_number_id: ID of the scan number input field
    - alert_id: ID of the alert component for status messages
    - data_path_id: ID of the data path field to update
    - filename_prefix_id: ID of the filename prefix field to update
    - root_path_id: ID of the root path field to update
    - catalog_defaults: Dictionary of catalog default values
    
    Returns:
    - The registered callback function
    """
    
    @dash.callback(
        Input(button_id, 'n_clicks'),
        State(scan_number_id, 'value'),
        prevent_initial_call=True,
    )
    def update_path_fields_from_scan(n_clicks, scanNumber):
        """Update path fields by querying catalog data based on scan number."""
        
        if not scanNumber:
            set_props(alert_id, {
                'is_open': True,
                'children': 'Please enter a scan number first.',
                'color': 'warning'
            })
            raise PreventUpdate
        
        root_path = DEFAULT_VARIABLES.get("root_path", "")
        
        with Session(session_utils.get_engine()) as session:
            try:
                # Parse scan number (handle semicolon-separated values for pooled scans)
                scan_ids = [int(sid.strip()) for sid in str(scanNumber).split(';') if sid.strip()]
                
                if not scan_ids:
                    set_props(alert_id, {
                        'is_open': True,
                        'children': 'Invalid scan number format.',
                        'color': 'danger'
                    })
                    raise PreventUpdate
                
                # Get catalog data for each scan
                catalog_data_list = []
                for scan_id in scan_ids:
                    catalog_data = get_catalog_data(session, scan_id, root_path, catalog_defaults)
                    if catalog_data:
                        catalog_data_list.append(catalog_data)
                
                if catalog_data_list:
                    # If multiple scans, merge the data
                    if len(catalog_data_list) == 1:
                        merged_data = catalog_data_list[0]
                    else:
                        # Merge data paths and filename prefixes
                        data_paths = [cd['data_path'] for cd in catalog_data_list]
                        filename_prefixes = [cd['filenamePrefix'] for cd in catalog_data_list]
                        
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
                        'children': f'Successfully loaded path fields from database for scan(s): {scanNumber}',
                        'color': 'success'
                    })
                else:
                    set_props(alert_id, {
                        'is_open': True,
                        'children': f'No catalog data found for scan(s): {scanNumber}. Using defaults.',
                        'color': 'warning'
                    })
            
            except ValueError as e:
                set_props(alert_id, {
                    'is_open': True,
                    'children': f'Invalid scan number format: {str(e)}',
                    'color': 'danger'
                })
            except Exception as e:
                set_props(alert_id, {
                    'is_open': True,
                    'children': f'Error loading catalog data: {str(e)}',
                    'color': 'danger'
                })
    
    return update_path_fields_from_scan


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
                
                # Parse filename prefix (handle comma-separated list)
                filename_prefixes = [s.strip() for s in str(filenamePrefix).split(',')] if filenamePrefix else []
                
                # Build regex pattern to capture N rightmost numbers
                if num_indices == 1:
                    regex_pattern = r'(\d+)(?!.*\d)'
                else:
                    # Capture N groups of digits separated by underscores from the right
                    regex_pattern = r'_'.join([r'(\d+)'] * num_indices) + r'(?!.*\d)'
                
                # Extract indices from files matching the prefix pattern
                for current_filename_prefix_i in filename_prefixes:
                    # Use glob to find files matching this prefix pattern
                    # Replace %d with * for glob matching
                    ext_wildcard = '*' if '.' in current_filename_prefix_i else '.*'
                    prefix_pattern = os.path.join(current_full_data_path, current_filename_prefix_i.replace('_'.join(['%d'] * num_indices), '_'.join(['*'] * num_indices)) + ext_wildcard)
                    
                    try:
                        prefix_matches = glob.glob(prefix_pattern)
                    except Exception as e:
                        logger.error(f"Error reading directory {current_full_data_path}: {e}")
                        continue
                    
                    if not prefix_matches:
                        continue  # Skip if no files match this prefix
                    
                    # Extract indices from matched files
                    for filepath in prefix_matches:
                        filename = os.path.basename(filepath)
                        base_name, extension = os.path.splitext(filename)
                        match = re.search(regex_pattern, base_name)
                        
                        if match:
                            try:
                                if num_indices == 1:
                                    # Single index: scanPoint only
                                    scanpoint_index = int(match.group(1))
                                    all_scanpoint_indices.add(scanpoint_index)
                                else:
                                    # Two indices: scanPoint and depth
                                    scanpoint_index = int(match.group(1))
                                    depth_index = int(match.group(2))
                                    all_scanpoint_indices.add(scanpoint_index)
                                    all_depth_indices.add(depth_index)
                            except (ValueError, IndexError):
                                continue
            
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
    - num_indices: Number of rightmost numeric indices to capture
    
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
            
            # List all files in directory
            try:
                files = [f for f in os.listdir(current_full_data_path) if os.path.isfile(os.path.join(current_full_data_path, f))]
            except Exception as e:
                logger.error(f"Error reading directory {current_full_data_path}: {e}")
                continue
            
            # Extract patterns and indices
            for filename in files:
                base_name, extension = os.path.splitext(filename)
                
                # Build regex pattern to capture N rightmost numbers
                if num_indices == 1:
                    regex_pattern = r'(\d+)(?!.*\d)'
                else:
                    # Capture N groups of digits separated by underscores from the right
                    regex_pattern = r'_'.join([r'(\d+)'] * num_indices) + r'(?!.*\d)'
                
                match = re.search(regex_pattern, base_name)
                
                if match:
                    # Extract all captured groups as integers
                    indices = [int(match.group(i)) for i in range(1, num_indices + 1)]
                    
                    # Create pattern with appropriate number of %d placeholders
                    pattern_placeholder = '_'.join(['%d'] * num_indices)
                    pattern = base_name[:match.start()] + pattern_placeholder + base_name[match.end():] + extension
                    
                    pattern_files.setdefault(pattern, []).append(indices)
                else:
                    # No numeric pattern found
                    pattern_files.setdefault(filename, []).append([])
        
        if not pattern_files:
            return [html.Option(value="", label="No files found in specified path(s)")]
        
        # Sort by file count and create options for top 10 patterns
        sorted_patterns = sorted(pattern_files.items(), key=lambda x: len(x[1]), reverse=True)[:10]
        pattern_options = []
        
        for pattern, indices_list in sorted_patterns:
            if indices_list and indices_list[0]:
                if num_indices == 1:
                    # Single index: show simple range
                    label = f"{pattern} (files {str(srange(set(idx[0] for idx in indices_list)))})"
                else:
                    # Multiple indices: show ranges for each dimension
                    range_labels = []
                    dim_names = ['scanPoints', 'depths'] if num_indices == 2 else [f"dim{i+1}" for i in range(num_indices)]
                    
                    for dim in range(num_indices):
                        dim_values = sorted(set(idx[dim] for idx in indices_list if len(idx) > dim))
                        if dim_values:
                            range_labels.append(f"{dim_names[dim]}: {str(srange(dim_values))}")
                    
                    if range_labels:
                        label = f"{pattern} ({', '.join(range_labels)})"
                    else:
                        label = f"{pattern} ({len(indices_list)} file{'s' if len(indices_list) != 1 else ''})"
            else:
                label = f"{pattern} ({len(indices_list)} file{'s' if len(indices_list) != 1 else ''})"
            pattern_options.append(html.Option(value=pattern, label=label))
        
        # Generate combined wildcard patterns for similar patterns
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
                        diff1 = pattern1[last_pos:match_start1]
                        diff2 = pattern2[last_pos:match_start2]
                        
                        # Skip if differences contain %d
                        if '%d' in diff1 or '%d' in diff2:
                            break
                        
                        wildcard_parts.append('*')
                    
                    # Add the matching section
                    if match_length > 0:
                        wildcard_parts.append(pattern1[match_start1:match_start1 + match_length])
                    
                    last_pos = match_start1 + match_length
                else:
                    # Only create wildcard if pattern contains wildcards and hasn't been seen before
                    wildcard_pattern = ''.join(wildcard_parts)
                    if '*' in wildcard_pattern and wildcard_pattern not in seen_wildcards:
                        seen_wildcards.add(wildcard_pattern)
                        
                        # Combine indices from both patterns
                        combined_indices = sorted(set(idx[0] for idx in indices1 + indices2 if idx))
                        label = f"{wildcard_pattern} (files {str(srange(combined_indices))})"
                        pattern_options.append(html.Option(value=wildcard_pattern, label=label))
        
        # Get the trigger that caused this callback
        ctx = dash.callback_context
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None
        
        # Find the shortest pattern from all options (including wildcards) and set it to filenamePrefix
        # Only set filenamePrefix if triggered by the check-filenames button
        if pattern_options and trigger_id == check_button_id:
            shortest_pattern = min(pattern_options, key=lambda opt: len(opt.value))
            set_props(filename_prefix_id, {'value': shortest_pattern.value})
        
        return pattern_options
    
    return check_filenames
