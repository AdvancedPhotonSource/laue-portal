"""Small layout helpers shared by the visualization pages: sidebar sections, controls, loading graphs."""

import dash_bootstrap_components as dbc
from dash import dcc, html


def viz_sidebar_head(title, icon_class="bi bi-sliders"):
    """Section header inside a visualization sidebar."""
    return html.Div(
        [
            html.I(className=f"pi-viz-section-icon {icon_class}"),
            html.H4(title),
        ],
        className="pi-viz-sidebar-head",
    )


def viz_control(label_text, *children, help_text=None):
    """Single labelled control row inside a visualization sidebar."""
    content = [html.Label(label_text), *children]
    if help_text:
        content.append(html.Small(help_text, className="text-muted"))
    return html.Div(content, className="pi-viz-control")


def viz_graph_with_loading(graph, target_id, text="Updating\u2026", cursor_readout_id=None):
    """Wrap a dcc.Graph in a dcc.Loading overlay shown during callbacks."""
    children = [graph, html.Div(id=target_id)]
    if cursor_readout_id:
        children.append(
            html.Div(
                "x: —   y: —",
                id=cursor_readout_id,
                className="pi-viz-cursor-readout",
                **{"aria-live": "polite"},
            )
        )
    return dcc.Loading(
        type="circle",
        # Only the callback's dedicated sentinel should activate the overlay.
        # Client-side cursor-readout updates must remain visually silent.
        target_components={target_id: "children"},
        overlay_style={"visibility": "visible", "opacity": 1},
        custom_spinner=html.Div(
            [
                dbc.Spinner(size="sm", color="secondary", spinner_class_name="me-2"),
                html.Span(text, className="pi-viz-loading-text"),
            ],
            style={
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "center",
                "padding": "2rem",
            },
        ),
        children=children,
    )
