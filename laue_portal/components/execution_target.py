"""Execution choice shared by both submission forms."""

import dash_bootstrap_components as dbc
from dash import html

from laue_portal.processing.bdp.settings import available_backends


def execution_target(kind):
    options = available_backends()
    return html.Div(
        [
            html.Label("Run on", htmlFor=f"{kind}-execution-target", className="small text-muted"),
            dbc.RadioItems(
                id=f"{kind}-execution-target",
                options=options,
                value=options[0]["value"],
                inline=True,
                className="lp-execution-options",
            ),
        ],
        id=f"{kind}-execution-selector",
        className="lp-execution-selector",
        title="ALCF includes round-trip transfer and a 15m overhead allowance.",
    )
