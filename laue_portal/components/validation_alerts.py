"""Shared validation alert layout and Dash update helpers for create pages."""

import dash_bootstrap_components as dbc
from dash import html, set_props


def apply_validation_highlights(validation_result):
    """Apply field CSS classes based on validation errors, warnings, and successes."""
    errors = validation_result["errors"]
    warnings = validation_result["warnings"]
    successes = validation_result["successes"]

    for field_id in errors:
        set_props(field_id, {"className": "is-invalid"})

    for field_id in warnings:
        if field_id not in errors:
            set_props(field_id, {"className": "border-warning"})

    for field_id in successes:
        set_props(field_id, {"className": ""})


def update_validation_alerts(
    validation_result,
    info_alert_id="alert-validation-info",
    success_alert_id="alert-validation-success",
    error_alert_id="alert-validation-error",
    warning_alert_id="alert-validation-warning",
    error_message_id="alert-validation-error-message",
    warning_message_id="alert-validation-warning-message",
):
    """Update validation alert visibility and message content."""
    errors = validation_result["errors"]
    warnings = validation_result["warnings"]

    def deduplicate_messages(messages_dict):
        unique_messages = []
        seen = set()
        for msg_list in messages_dict.values():
            for msg in msg_list:
                if msg not in seen:
                    seen.add(msg)
                    unique_messages.append(msg)
        return unique_messages

    error_messages = deduplicate_messages(errors)
    warning_messages = deduplicate_messages(warnings)

    error_message = html.Ul([html.Li(msg) for msg in error_messages], className="mb-0") if error_messages else None
    warning_message = (
        html.Ul([html.Li(msg) for msg in warning_messages], className="mb-0") if warning_messages else None
    )

    set_props(error_message_id, {"children": error_message})
    set_props(warning_message_id, {"children": warning_message})

    set_props(info_alert_id, {"is_open": False})
    set_props(success_alert_id, {"is_open": not errors and not warnings})
    set_props(error_alert_id, {"is_open": bool(errors)})
    set_props(warning_alert_id, {"is_open": bool(warnings)})


validation_alerts = html.Div(
    [
        dbc.Alert(
            dbc.Row(
                [
                    dbc.Col(html.H4("Validation: Info", className="alert-heading mb-0"), width=2),
                    dbc.Col(html.P("Click 'Validate' button to check inputs.", className="mb-0"), width="auto"),
                ],
                align="center",
            ),
            id="alert-validation-info",
            color="info",
            dismissable=False,
            is_open=True,
            className="mb-2",
        ),
        dbc.Alert(
            dbc.Row(
                [
                    dbc.Col(html.H4("Validation: Success", className="alert-heading mb-0"), width=2),
                    dbc.Col(html.P("All inputs are valid. You can submit the job.", className="mb-0"), width="auto"),
                ],
                align="center",
            ),
            id="alert-validation-success",
            color="success",
            dismissable=False,
            is_open=False,
            className="mb-2",
        ),
        dbc.Alert(
            dbc.Row(
                [
                    dbc.Col(html.H4("Validation: Error", className="alert-heading mb-0"), width=3),
                    dbc.Col(html.Div(id="alert-validation-error-message", className="mb-0"), width="auto"),
                ],
                align="center",
            ),
            id="alert-validation-error",
            color="danger",
            dismissable=False,
            is_open=False,
            className="mb-2",
        ),
        dbc.Alert(
            dbc.Row(
                [
                    dbc.Col(html.H4("Validation: Warning", className="alert-heading mb-0"), width=3),
                    dbc.Col(html.Div(id="alert-validation-warning-message", className="mb-0"), width="auto"),
                ],
                align="center",
            ),
            id="alert-validation-warning",
            color="warning",
            dismissable=False,
            is_open=False,
            className="mb-2",
        ),
    ],
    className="mb-3",
)
