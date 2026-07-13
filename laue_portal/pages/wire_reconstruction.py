import urllib.parse

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, callback, dcc, html
from dash.exceptions import PreventUpdate
from sqlalchemy.orm import Session

import laue_portal.components.navbar as navbar
import laue_portal.database.db_schema as db_schema
import laue_portal.database.session_utils as session_utils
from laue_portal.components.detail_layout import detail_header, detail_header_content
from laue_portal.components.wire_recon_form import set_wire_recon_form_props, wire_recon_readonly_form
from laue_portal.config import DEFAULT_VARIABLES
from laue_portal.database.db_utils import get_catalog_data, remove_root_path_prefix

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

    wirerecon_id_str = query_params.get("wirerecon_id", [None])[0]

    root_path = DEFAULT_VARIABLES.get("root_path", "")

    if wirerecon_id_str:
        try:
            wirerecon_id = int(wirerecon_id_str)
            with Session(session_utils.get_engine()) as session:
                wirerecon_data = (
                    session.query(db_schema.WireRecon).filter(db_schema.WireRecon.wirerecon_id == wirerecon_id).first()
                )
                if wirerecon_data:
                    # Add root_path from DEFAULT_VARIABLES
                    root_path = DEFAULT_VARIABLES.get("root_path", "")
                    wirerecon_data.root_path = root_path

                    # Convert full paths back to relative paths for display
                    if wirerecon_data.geoFile:
                        wirerecon_data.geoFile = remove_root_path_prefix(wirerecon_data.geoFile, root_path)
                    if wirerecon_data.outputFolder:
                        wirerecon_data.outputFolder = remove_root_path_prefix(wirerecon_data.outputFolder, root_path)

                    if wirerecon_data.filefolder:
                        wirerecon_data.data_path = remove_root_path_prefix(wirerecon_data.filefolder, root_path)

                    if any([not hasattr(wirerecon_data, field) for field in ["data_path", "filenamePrefix"]]):
                        # Retrieve data_path and filenamePrefix from catalog data
                        catalog_data = get_catalog_data(session, wirerecon_data.scanNumber, root_path)
                    if not hasattr(wirerecon_data, "data_path"):
                        wirerecon_data.data_path = catalog_data.get("data_path", "")
                    if not hasattr(wirerecon_data, "filenamePrefix"):
                        wirerecon_data.filenamePrefix = catalog_data.get("filenamePrefix", [])

                    # Populate the form with the data
                    set_wire_recon_form_props(wirerecon_data, read_only=True)

                    # Get related links
                    related_links = []

                    # Add job link if it exists
                    if wirerecon_data.job_id:
                        related_links.append(
                            (f"Job ID: {wirerecon_data.job_id}", f"/job?job_id={wirerecon_data.job_id}")
                        )

                    # Add scan link
                    if wirerecon_data.scanNumber:
                        related_links.append(
                            (
                                f"Scan ID: {wirerecon_data.scanNumber}",
                                f"/scan?scan_id={wirerecon_data.scanNumber}",
                            )
                        )

                    return detail_header_content(f"Wire Reconstruction ID: {wirerecon_id}", related_links)

        except Exception as e:
            print(f"Error loading wire reconstruction data: {e}")
            return detail_header_content(f"Error loading data for Wire Recon ID: {wirerecon_id_str}")

    return detail_header_content("No Wire Recon ID provided")
