import urllib.parse

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, callback, dcc, html
from dash.exceptions import PreventUpdate
from sqlalchemy.orm import Session

import laue_portal.components.navbar as navbar
import laue_portal.database.session_utils as session_utils
from laue_portal.components.detail_layout import detail_header, detail_header_content
from laue_portal.components.wire_recon_form import set_wire_recon_form_props, wire_recon_readonly_form
from laue_portal.config import DEFAULT_VARIABLES
from laue_portal.database.db_utils import get_catalog_data, remove_root_path_prefix
from laue_portal.workflows.reconstruction import get_reconstruction

dash.register_page(__name__, path="/wire_reconstruction")

layout = html.Div(
    [
        navbar.navbar,
        dcc.Location(id="url-wire-recon-page", refresh=False),
        detail_header("wire-recon-id-header"),
        dbc.Tabs(
            id="wire-recon-detail-tabs",
            active_tab="wire-recon-tab-parameters",
            className="lp-detail-tabs",
            children=[
                dbc.Tab(
                    label="Parameters",
                    tab_id="wire-recon-tab-parameters",
                    children=[
                        html.Div(
                            id="wire-recon-tab-parameters-content",
                            className="pt-3 px-2",
                            children=[wire_recon_readonly_form],
                        )
                    ],
                ),
            ],
        ),
    ]
)


@callback(Output("wire-recon-id-header", "children"), Input("url-wire-recon-page", "href"), prevent_initial_call=True)
def load_wire_recon_data(href):
    if not href:
        raise PreventUpdate

    parsed_url = urllib.parse.urlparse(href)
    query_params = urllib.parse.parse_qs(parsed_url.query)

    reconstruction_id_str = query_params.get("reconstruction_id", [None])[0]

    root_path = DEFAULT_VARIABLES.get("root_path", "")

    if reconstruction_id_str:
        try:
            reconstruction_id = int(reconstruction_id_str)
            reconstruction = get_reconstruction(reconstruction_id)
            if reconstruction and reconstruction.method == "wire" and reconstruction.wire_parameters:
                with Session(session_utils.get_engine()) as session:
                    # Add root_path from DEFAULT_VARIABLES
                    root_path = DEFAULT_VARIABLES.get("root_path", "")
                    reconstruction.root_path = root_path

                    # Convert full paths back to relative paths for display
                    if reconstruction.wire_parameters.geometry_file:
                        reconstruction.wire_parameters.geometry_file = remove_root_path_prefix(
                            reconstruction.wire_parameters.geometry_file, root_path
                        )
                    if reconstruction.output_path:
                        reconstruction.output_path = remove_root_path_prefix(reconstruction.output_path, root_path)

                    reconstruction.data_path = remove_root_path_prefix(reconstruction.input_path, root_path)

                    if not reconstruction.input_path:
                        catalog_data = get_catalog_data(session, reconstruction.scan_number, root_path)
                        reconstruction.data_path = catalog_data.get("data_path", "")

                    # Populate the form with the data
                    set_wire_recon_form_props(reconstruction, read_only=True)

                    # Get related links
                    related_links = []

                    # Add job link if it exists
                    if reconstruction.job_id:
                        related_links.append(
                            (f"Job ID: {reconstruction.job_id}", f"/job?job_id={reconstruction.job_id}")
                        )

                    # Add scan link
                    if reconstruction.scan_number:
                        related_links.append(
                            (
                                f"Scan ID: {reconstruction.scan_number}",
                                f"/scan?scan_id={reconstruction.scan_number}",
                            )
                        )

                    return detail_header_content(f"Reconstruction R{reconstruction_id}", related_links)

        except Exception as e:
            print(f"Error loading wire reconstruction data: {e}")
            return detail_header_content(f"Error loading reconstruction R{reconstruction_id_str}")

    return detail_header_content("No reconstruction ID provided")
