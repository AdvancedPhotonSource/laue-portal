"""
Shared validation helper functions for form validation across pages.

This module provides reusable validation utilities that can be used by
both wire reconstruction and peak indexing validation functions.
"""

import os
from dash import html, set_props


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
