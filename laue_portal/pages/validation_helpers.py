"""
Shared validation helper functions for form validation across pages.

This module provides reusable validation utilities that can be used by
both wire reconstruction and peak indexing validation functions.
"""

import os
from dash import html, set_props


def format_field_name(field_name):
    """Convert field_name to display format only if it contains underscores."""
    if '_' in field_name:
        return field_name.replace('_', ' ').title()
    return field_name


def add_validation_message(validation_result, result_key, field_name, input_prefix='', custom_message=None, display_name=None):
    """
    Add a validation message to the validation_result dict.
    
    Parameters:
    - validation_result: dict with 'errors', 'warnings', 'successes' keys
    - result_key: which key to add to ('errors', 'warnings', or 'successes')
    - field_name: name of the field (base name without prefix)
    - input_prefix: optional prefix for the message (e.g., "Input 1: ")
    - custom_message: optional custom message. Supports %s placeholder(s) for field name(s).
    - display_name: optional custom display name or list of names for %s replacement.
                   If not provided with %s in custom_message, auto-generated from field_name.
    
    Example usage:
        # Global validation - auto-generated display name
        add_validation_message(validation_result, 'errors', 'data_path')
        # Adds: "Data Path is required"
        
        # Per-input validation - auto-generated display name
        add_validation_message(validation_result, 'errors', 'geoFile', input_prefix='Input 1: ')
        # Adds: "Input 1: geoFile is required"
        
        # Custom display name for special cases
        add_validation_message(validation_result, 'errors', 'geoFile', 
                              input_prefix='Input 1: ',
                              display_name='Geometry File')
        # Adds: "Input 1: Geometry File is required"
        
        # Custom message with auto-generated %s replacement
        add_validation_message(validation_result, 'errors', 'depth_start', 
                              input_prefix='Input 1: ',
                              custom_message="%s must be less than Depth End")
        # Adds: "Input 1: Depth Start must be less than Depth End"
        
        # Custom message with explicit display_name for %s
        add_validation_message(validation_result, 'errors', 'depth_start', 
                              input_prefix='Input 1: ',
                              custom_message="%s must be positive",
                              display_name="Depth Start Value")
        # Adds: "Input 1: Depth Start Value must be positive"
        
        # Custom message with multiple %s placeholders
        add_validation_message(validation_result, 'errors', 'depth_resolution', 
                              input_prefix='Input 1: ',
                              custom_message=f"%s ({depth_resolution_val} µm) must be ≤ %s ({abs(depth_span)} µm)",
                              display_name=['Depth Resolution', 'depth range'])
        # Adds: "Input 1: Depth Resolution (1.5 µm) must be ≤ depth range (200 µm)"
        
        # Custom message without %s (hard-coded display names)
        add_validation_message(validation_result, 'errors', 'depth_start', 
                              input_prefix='Input 1: ',
                              custom_message="Depth Start must be less than Depth End")
        # Adds: "Input 1: Depth Start must be less than Depth End"
    """
    if custom_message:
        # Handle %s placeholder replacement in custom messages
        if '%s' in custom_message:
            # Determine what to use for %s replacement
            if display_name is None:
                # Auto-generate from field_name
                display_name = format_field_name(field_name)
            
            # Perform replacement based on display_name type
            if isinstance(display_name, (list, tuple)):
                # Multiple %s placeholders - replace with tuple
                message = custom_message % tuple(display_name)
            else:
                # Single %s placeholder - replace with string
                message = custom_message % display_name
        else:
            # No %s in custom_message, use as-is
            message = custom_message
    else:
        # Generate default message
        if display_name is None:
            display_name = format_field_name(field_name)
        
        if result_key == 'errors':
            message = f"{display_name} is required"
        elif result_key == 'warnings':
            message = f"{display_name} is missing"
        else:  # successes
            message = ''
    
    # Prepend input_prefix to entire message
    if input_prefix:
        message = f"{input_prefix}{message}"
    
    # Append message to the list for this field_name in the appropriate result category
    validation_result[result_key].setdefault(field_name, []).append(message)


def validate_field_value(validation_result, parsed_fields, field_name, index, input_prefix='',
                         converter=None, required=True, display_name=None):
    """
    Extract, validate, and convert a field value from parsed_fields.
    
    This comprehensive helper handles the complete validation pattern:
    1. Check if field exists in parsed_fields (skip if failed global validation)
    2. Extract the value at the given index
    3. Check if value is None/empty (if required)
    4. Apply type conversion (if converter provided)
    5. Add appropriate error messages
    
    Parameters:
    - validation_result: dict with 'errors', 'warnings', 'successes' keys
    - parsed_fields: dict of parsed field value lists
    - field_name: name of the field to extract
    - index: index in the field value list
    - input_prefix: optional prefix for the message (e.g., "Input 1: ")
    - converter: optional function to convert the value (e.g., safe_int, safe_float)
    - required: whether the value is required (default True)
    - display_name: optional custom display name (if not provided, auto-generated from field_name)
    
    Returns:
    - The extracted (and optionally converted) value, or None if validation failed
    
    Example:
        # Auto-generated display name
        input_prefix = f"Input {i+1}: " if num_inputs > 1 else ""
        depth_start_val = validate_field_value(
            validation_result, parsed_fields, 'depth_start', i, input_prefix,
            converter=safe_float
        )
        
        # Custom display name for special cases
        geo_file = validate_field_value(
            validation_result, parsed_fields, 'geoFile', i, input_prefix,
            display_name='Geometry File'
        )
    """
    # Skip if field failed global validation
    if field_name not in parsed_fields:
        return None
    
    # Extract the value
    value = parsed_fields[field_name][index]
    
    # Check if value is None/empty
    if value is None or value == '':
        if required:
            add_validation_message(validation_result, 'errors', field_name, input_prefix, 
                                 display_name=display_name)
        return None
    
    # Apply converter if provided
    if converter is not None:
        converted_value = converter(value)
        if converted_value is None:
            add_validation_message(validation_result, 'errors', field_name, input_prefix,
                                 custom_message=f"{field_name} must be a valid number",
                                 display_name=display_name)
            return None
        return converted_value
    
    return value


def apply_validation_highlights(validation_result):
    """
    Apply field highlights based on validation results.
    Clears highlights for fields that passed validation.
    
    Parameters:
    - validation_result: dict returned from validation functions with keys:
        - 'errors': dict mapping param_name to list of error messages
        - 'warnings': dict mapping param_name to list of warning messages
        - 'successes': dict mapping param_name to empty string
    """
    errors = validation_result['errors']
    warnings = validation_result['warnings']
    successes = validation_result['successes']
    
    # Apply error highlights
    for field_id in errors.keys():
        set_props(field_id, {'className': 'is-invalid'})
    
    # Apply warning highlights (only if not already in error)
    for field_id in warnings.keys():
        if field_id not in errors:
            set_props(field_id, {'className': 'border-warning'})
    
    # Clear highlights for fields that passed validation
    for field_id in successes.keys():
        set_props(field_id, {'className': ''})


def update_validation_alerts(validation_result,
                            info_alert_id='alert-validation-info',
                            success_alert_id='alert-validation-success',
                            error_alert_id='alert-validation-error',
                            warning_alert_id='alert-validation-warning',
                            error_message_id='alert-validation-error-message',
                            warning_message_id='alert-validation-warning-message'):
    """
    Update validation alert components based on validation results.
    Deduplicates messages by removing input prefixes and grouping identical base messages.
    Only updates the message content of alerts, not the headings (which are defined in layout).
    
    Parameters:
    - validation_result: dict returned from validation functions
    - info_alert_id: ID of the info alert component
    - success_alert_id: ID of the success alert component
    - error_alert_id: ID of the error alert component
    - warning_alert_id: ID of the warning alert component
    - error_message_id: ID of the error message div
    - warning_message_id: ID of the warning message div
    """
    errors = validation_result['errors']
    warnings = validation_result['warnings']
    
    # Helper function to deduplicate messages
    def deduplicate_messages(messages_dict):
        """
        Deduplicate messages by removing 'Input N: ' prefixes and grouping identical messages.
        Returns a flat list of unique messages.
        """
        all_messages = []
        for field_id, msg_list in messages_dict.items():
            all_messages.extend(msg_list)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_messages = []
        for msg in all_messages:
            if msg not in seen:
                seen.add(msg)
                unique_messages.append(msg)
        
        return unique_messages
    
    # Deduplicate error and warning messages
    error_messages = deduplicate_messages(errors)
    warning_messages = deduplicate_messages(warnings)
    
    # Build message content only (headings are already in the layout)
    error_message = html.Ul([html.Li(msg) for msg in error_messages], className="mb-0") if error_messages else None
    warning_message = html.Ul([html.Li(msg) for msg in warning_messages], className="mb-0") if warning_messages else None
    
    # Update only the message divs
    set_props(error_message_id, {'children': error_message})
    set_props(warning_message_id, {'children': warning_message})
    
    # Set props for all validation alerts
    set_props(info_alert_id, {'is_open': False})  # Hide the info alert when validation runs
    set_props(success_alert_id, {'is_open': not errors and not warnings})
    set_props(error_alert_id, {'is_open': bool(errors)})
    set_props(warning_alert_id, {'is_open': bool(warnings)})


def validate_numeric_range(value, min_val=None, max_val=None, field_name="Field", allow_none=False):
    """
    Helper to validate numeric ranges.
    
    Parameters:
    - value: The value to validate
    - min_val: Minimum allowed value (optional)
    - max_val: Maximum allowed value (optional)
    - field_name: Name of the field for error messages
    - allow_none: Whether None/empty values are allowed
    
    Returns:
    - tuple: (numeric_value, errors_list, warnings_list)
    """
    errors = []
    warnings = []
    
    # Check for None/empty
    if value is None or value == '':
        if allow_none:
            return None, errors, warnings
        else:
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
    """
    Helper to validate file existence.
    
    Parameters:
    - file_path: Relative path to the file
    - root_path: Root path to prepend
    - field_name: Name of the field for error messages
    
    Returns:
    - list: Error messages (empty if file exists)
    """
    if not file_path:
        return [f"{field_name} is required"]
    
    full_path = os.path.join(root_path, file_path.lstrip('/'))
    
    if not os.path.exists(full_path):
        return [f"{field_name} not found: {file_path}"]
    
    return []


def validate_directory_exists(dir_path, root_path, field_name="Directory"):
    """
    Helper to validate directory existence.
    
    Parameters:
    - dir_path: Relative path to the directory
    - root_path: Root path to prepend
    - field_name: Name of the field for error messages
    
    Returns:
    - list: Error messages (empty if directory exists)
    """
    if not dir_path:
        return [f"{field_name} is required"]
    
    full_path = os.path.join(root_path, dir_path.lstrip('/'))
    
    if not os.path.exists(full_path):
        return [f"{field_name} not found: {dir_path}"]
    
    return []


def safe_float(value):
    """
    Safely convert a value to float.
    
    Parameters:
    - value: The value to convert
    
    Returns:
    - float or None: The converted value, or None if conversion fails
    """
    try:
        if value is None or value == '':
            return None
        return float(value)
    except (ValueError, TypeError):
        return None


def safe_int(value):
    """
    Safely convert a value to int.
    
    Parameters:
    - value: The value to convert
    
    Returns:
    - int or None: The converted value, or None if conversion fails
    """
    try:
        if value is None or value == '':
            return None
        return int(value)
    except (ValueError, TypeError):
        return None


def get_num_inputs_from_fields(fields_dict, delimiter="; "):
    """
    Determine the number of inputs by finding the maximum number of 
    semicolon-separated entries across all form fields.
    
    This handles the case where pooled data may have identical values
    that get collapsed to a single value during pooling, while other
    fields retain their semicolon-separated format.
    
    Parameters:
    - fields_dict: Dictionary of field names to values
    - delimiter: The delimiter used to separate multiple values (default "; ")
    
    Returns:
    - int: The maximum number of inputs found across all fields (minimum 1)
    
    Example:
        fields = {
            'data_path': 'data/scan_276994',  # Same for all (collapsed)
            'scanNumber': '276994; 276995; 276996',  # Different (3 entries)
            'threshold': '250'  # Same for all (collapsed)
        }
        num_inputs = get_num_inputs_from_fields(fields)  # Returns 3
    """
    num_inputs = 1  # Default to 1
    
    # Scan all fields to find the maximum number of semicolon-separated entries
    for field_name, field_value in fields_dict.items():
        if field_value is not None and field_value != '':
            # Count semicolon-separated entries
            value_str = str(field_value)
            entries = [s.strip() for s in value_str.split(delimiter)]
            num_inputs = max(num_inputs, len(entries))
    
    return num_inputs
