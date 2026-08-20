"""Unavailable CA reconstruction creation shim."""

import urllib.parse

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, dcc, html

import laue_portal.components.navbar as navbar
from laue_portal.workflows.reconstruction import get_reconstruction

dash.register_page(__name__)

layout = dbc.Container(
    [
        navbar.navbar,
        dcc.Location(id="url-create-reconstruction", refresh=False),
        html.Div(
            className="lp-form-page",
            children=[
                html.Div(
                    className="lp-form-masthead",
                    children=[
                        html.Div(
                            [
                                html.Div("CA Reconstructions / New", className="lp-form-breadcrumb"),
                                html.H2("New CA Reconstruction"),
                            ]
                        ),
                        dbc.Button(
                            [html.I(className="bi bi-slash-circle me-1"), "Unavailable"],
                            id="submit_recon",
                            color="secondary",
                            disabled=True,
                        ),
                    ],
                ),
                dbc.Alert(
                    [
                        html.Strong("CA reconstruction is not available. "),
                        "The unified workflow reserves the method, but its parameter contract and executor have not been implemented.",
                    ],
                    color="warning",
                    className="mt-3",
                ),
                html.Div(id="ca-create-source"),
            ],
        ),
    ],
    className="dbc px-0",
    fluid=True,
)


@dash.callback(
    Output("ca-create-source", "children"),
    Input("url-create-reconstruction", "href"),
)
def load_ca_source(href):
    """Show a selected CA run without exposing a legacy creation path."""

    if not href:
        return dash.no_update

    query = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
    raw_id = query.get("reconstruction_id", [None])[0]
    if not raw_id:
        return dbc.Alert("No CA reconstruction source selected.", color="secondary")

    try:
        reconstruction_id = int(raw_id.split(",")[0])
    except (TypeError, ValueError):
        return dbc.Alert("Invalid reconstruction ID.", color="danger")

    run = get_reconstruction(reconstruction_id)
    if run is None or run.method != "ca":
        return dbc.Alert(f"CA reconstruction R{reconstruction_id} was not found.", color="danger")

    source = f"SN{run.scan_number}" if run.scan_number is not None else "Unlinked"
    return dbc.Alert(
        [
            html.Span(f"Selected R{run.id} ({source}). "),
            html.A("Open details", href=f"/reconstruction?reconstruction_id={run.id}"),
        ],
        color="info",
    )
