"""
Shared validation alert components for create pages.

This module provides a standardized set of validation alert components
used across multiple create pages (wire reconstruction, peak indexing, etc.)
to ensure consistency and reduce code duplication.
"""

import dash_bootstrap_components as dbc
from dash import html


validation_alerts = html.Div([
    dbc.Alert(
        dbc.Row([
            dbc.Col(html.H4("Validation: Info", className="alert-heading mb-0"), width=2),
            dbc.Col(html.P("Click 'Validate' button to check inputs.", className="mb-0"), width="auto"),
        ], align="center"),
        id="alert-validation-info",
        color="info",
        dismissable=False,
        is_open=True,
        className="mb-2"
    ),
    dbc.Alert(
        dbc.Row([
            dbc.Col(html.H4("Validation: Success", className="alert-heading mb-0"), width=2),
            dbc.Col(html.P("All inputs are valid. You can submit the job.", className="mb-0"), width="auto"),
        ], align="center"),
        id="alert-validation-success",
        color="success",
        dismissable=False,
        is_open=False,
        className="mb-2"
    ),
    dbc.Alert(
        dbc.Row([
            dbc.Col(html.H4("Validation: Error", className="alert-heading mb-0"), width=3),
            dbc.Col(html.Div(id="alert-validation-error-message", className="mb-0"), width="auto"),
        ], align="center"),
        id="alert-validation-error",
        color="danger",
        dismissable=False,
        is_open=False,
        className="mb-2"
    ),
    dbc.Alert(
        dbc.Row([
            dbc.Col(html.H4("Validation: Warning", className="alert-heading mb-0"), width=3),
            dbc.Col(html.Div(id="alert-validation-warning-message", className="mb-0"), width="auto"),
        ], align="center"),
        id="alert-validation-warning",
        color="warning",
        dismissable=False,
        is_open=False,
        className="mb-2"
    ),
], className="mb-3")
