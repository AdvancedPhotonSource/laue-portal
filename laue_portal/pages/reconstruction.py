"""Read-only detail shim for reserved CA reconstruction runs."""

import urllib.parse

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, callback, dcc, html
from dash.exceptions import PreventUpdate

import laue_portal.components.navbar as navbar
from laue_portal.components.detail_layout import detail_header, detail_header_content
from laue_portal.workflows.reconstruction import get_reconstruction

dash.register_page(__name__, path="/reconstruction")

layout = html.Div(
    [
        navbar.navbar,
        dcc.Location(id="url-recon-page", refresh=False),
        detail_header("recon-id-header"),
        dbc.Container(
            [
                dbc.Alert(
                    "CA reconstruction is recognized by the unified workflow, but its parameters and executor are unavailable.",
                    color="warning",
                    className="mt-3",
                ),
                html.Div(id="ca-reconstruction-summary"),
            ],
            fluid=True,
        ),
    ]
)


@callback(
    Output("recon-id-header", "children"),
    Output("ca-reconstruction-summary", "children"),
    Input("url-recon-page", "href"),
    prevent_initial_call=True,
)
def load_recon_data(href):
    """Load only unified reconstruction rows whose method is CA."""

    if not href:
        raise PreventUpdate

    query = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
    raw_id = query.get("reconstruction_id", [None])[0]
    if not raw_id:
        return detail_header_content("No reconstruction ID provided"), dash.no_update

    try:
        reconstruction_id = int(raw_id)
    except (TypeError, ValueError):
        return detail_header_content("Invalid reconstruction ID"), dash.no_update

    reconstruction = get_reconstruction(reconstruction_id)
    if reconstruction is None:
        return detail_header_content(f"Reconstruction R{reconstruction_id} was not found"), dash.no_update
    if reconstruction.method != "ca":
        return (
            detail_header_content(f"Reconstruction R{reconstruction_id} uses method '{reconstruction.method}'"),
            dash.no_update,
        )

    related_links = [(f"Job ID: {reconstruction.job_id}", f"/job?job_id={reconstruction.job_id}")]
    if reconstruction.scan_number is not None:
        related_links.append((f"Scan ID: {reconstruction.scan_number}", f"/scan?scan_id={reconstruction.scan_number}"))

    summary = dbc.Card(
        dbc.CardBody(
            [
                html.Dl(
                    [
                        html.Dt("Method"),
                        html.Dd("CA (unavailable)"),
                        html.Dt("Input path"),
                        html.Dd(reconstruction.input_path),
                        html.Dt("Output path"),
                        html.Dd(reconstruction.output_path or "Not assigned"),
                        html.Dt("Author"),
                        html.Dd(reconstruction.author or ""),
                        html.Dt("Notes"),
                        html.Dd(reconstruction.notes or ""),
                    ]
                )
            ]
        ),
        className="mt-3",
    )
    return detail_header_content(f"Reconstruction R{reconstruction_id}", related_links), summary
