import dash
import dash_ag_grid as dag
import dash_bootstrap_components as dbc
import pandas as pd
from dash import Input, Output, State, dcc, html
from dash.exceptions import PreventUpdate
from sqlalchemy.orm import Session

import laue_portal.components.navbar as navbar
import laue_portal.database.db_schema as db_schema
import laue_portal.database.session_utils as session_utils
from laue_portal.components import live_rows
from laue_portal.workflows.progress import active_or_changed_since, progress_columns

dash.register_page(__name__, path="/peakindexings")

layout = html.Div(
    [
        navbar.navbar,
        dcc.Location(id="peakindexings-url", refresh=True),
        # Secondary action bar aligned to right
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Nav(
                            [
                                dbc.Button(
                                    "New Recon",
                                    id="peakindexings-page-wire-recon-btn",
                                    style={"backgroundColor": "#6c757d", "borderColor": "#6c757d"},
                                    className="me-2",
                                ),
                                dbc.Button(
                                    "New Index",
                                    id="peakindexings-page-peakindex-btn",
                                    style={"backgroundColor": "#6c757d", "borderColor": "#6c757d"},
                                    className="me-2",
                                ),
                                dbc.Button(
                                    "New Recon + Index",
                                    id="peakindexings-page-recon-index-btn-placeholder",
                                    style={"backgroundColor": "#6c757d", "borderColor": "#6c757d"},
                                    className="me-2",
                                ),
                            ],
                            className="bg-light px-2 py-2 d-flex justify-content-end w-100",
                        )
                    ],
                    width=12,
                )
            ],
            className="mb-3 mt-0",
        ),
        # Timed refresh sends only active or newly finalized runs as a row transaction.
        dcc.Interval(id="peakindexings-refresh-interval", interval=live_rows.REFRESH_SECONDS * 1000, n_intervals=0),
        dcc.Store(id="peakindexings-refresh-state"),
        dbc.Container(
            fluid=True,
            className="p-0",
            children=[
                dag.AgGrid(
                    id="peakindexing-table",
                    columnSize="responsiveSizeToFit",
                    getRowId="params.data.indexing_id",
                    defaultColDef={
                        "filter": True,
                    },
                    dashGridOptions={
                        "pagination": True,
                        "paginationPageSize": 20,
                        "domLayout": "autoHeight",
                        "rowSelection": "multiple",
                        "suppressRowClickSelection": True,
                        "animateRows": False,
                        "rowHeight": 32,
                    },
                    style={"height": "calc(100vh - 150px)", "width": "100%"},
                    className="ag-theme-alpine",
                )
            ],
        ),
    ],
)

VISIBLE_COLS = [
    db_schema.IndexingRun.id.label("indexing_id"),
    db_schema.IndexingRun.scan_number,
    db_schema.LaueGoIndexingParameters.scan_points_len,
    db_schema.IndexingRun.author,
    db_schema.IndexingRun.notes,
    db_schema.IndexingRun.reconstruction_id,
    db_schema.LaueGoIndexingParameters.box_size,
    db_schema.Job.submit_time,
    db_schema.Job.status,
]

# Columns to condense into the single "Source" column
SOURCE_COLS = {"scan_number", "reconstruction_id"}

CUSTOM_HEADER_NAMES = {
    "indexing_id": "Indexing ID",
    "scan_points_len": "Points",
    "box_size": "Box",
    "submit_time": "Date",
}


def _peakindexing_rows(criterion=None) -> list[dict]:
    """Rows for the indexing list; ``criterion`` restricts the query for a partial refresh."""

    with Session(session_utils.get_engine()) as session:
        # Progress comes from the run counters stored on the job; no per-frame rows are joined.
        query = (
            session.query(
                *VISIBLE_COLS,
                db_schema.IndexingRun.method,
                db_schema.ReconstructionRun.method.label("reconstruction_method"),
                db_schema.Catalog.aperture,
                *progress_columns(),
            )
            .join(db_schema.LaueGoIndexingParameters)
            .join(db_schema.Job, db_schema.IndexingRun.job_id == db_schema.Job.job_id)
            .outerjoin(
                db_schema.ReconstructionRun,
                db_schema.IndexingRun.reconstruction_id == db_schema.ReconstructionRun.id,
            )
            .outerjoin(db_schema.Catalog, db_schema.IndexingRun.scan_number == db_schema.Catalog.scanNumber)
            .filter(db_schema.IndexingRun.method == "lauego")
        )
        if criterion is not None:
            query = query.filter(criterion)
        peakindexings = pd.read_sql(query.statement, session.bind)
    return live_rows.add_status_progress(peakindexings).to_dict("records")


def _get_peakindexings():
    cols = []
    source_col_inserted = False

    # Add explicit checkbox column as the first column
    cols.append(
        {
            "headerName": "",
            "field": "checkbox",
            "checkboxSelection": True,
            "headerCheckboxSelection": True,
            "width": 60,
            "pinned": "left",
            "sortable": False,
            "filter": False,
            "resizable": False,
            "suppressMenu": True,
            "floatingFilter": False,
            "cellClass": "ag-checkbox-cell",
            "headerClass": "ag-checkbox-header",
        }
    )

    for col in VISIBLE_COLS:
        field_key = col.key

        # Replace scan and parent reconstruction IDs with a single source column.
        if field_key in SOURCE_COLS:
            if not source_col_inserted:
                cols.append(
                    {
                        "headerName": "Source",
                        "field": "source",
                        "cellRenderer": "SourceLinksRenderer",
                        "filter": True,
                        "sortable": True,
                        "resizable": True,
                        "floatingFilter": True,
                        "unSortIcon": True,
                        "valueGetter": {
                            "function": """
                        (params.data.scan_number != null ? 'SN' + params.data.scan_number : '') +
                        (params.data.reconstruction_id != null ? ' R' + params.data.reconstruction_id : '')
                        || 'Unlinked'
                    """
                        },
                    }
                )
                source_col_inserted = True
            continue

        header_name = CUSTOM_HEADER_NAMES.get(field_key, field_key.replace("_", " ").title())

        col_def = {
            "headerName": header_name,
            "field": field_key,
            "filter": True,
            "sortable": True,
            "resizable": True,
            "floatingFilter": True,
            "unSortIcon": True,
        }
        if field_key == "indexing_id":
            col_def["cellRenderer"] = "IndexingLinkRenderer"
            col_def["sort"] = "desc"
        elif field_key == "dataset_id":
            col_def["cellRenderer"] = "DatasetIdScanLinkRenderer"
        elif field_key in ["submit_time", "start_time", "finish_time"]:
            col_def["cellRenderer"] = "DateFormatter"
        elif field_key == "status":
            col_def["cellRenderer"] = "StatusRenderer"
        cols.append(col_def)

    return cols, _peakindexing_rows()


@dash.callback(
    Output("peakindexing-table", "columnDefs", allow_duplicate=True),
    Output("peakindexing-table", "rowData", allow_duplicate=True),
    Output("peakindexings-refresh-state", "data"),
    Input("peakindexings-url", "pathname"),
    prevent_initial_call="initial_duplicate",
)
def get_peakindexings(path):
    if path == "/peakindexings":
        cols, peakindexings_records = _get_peakindexings()
        return cols, peakindexings_records, live_rows.initial_state(peakindexings_records, "indexing_id")
    else:
        raise PreventUpdate


@dash.callback(
    Output("peakindexing-table", "rowTransaction"),
    Output("peakindexings-refresh-state", "data", allow_duplicate=True),
    Input("peakindexings-refresh-interval", "n_intervals"),
    State("peakindexings-refresh-state", "data"),
    State("peakindexings-url", "pathname"),
    running=[(Output("peakindexings-refresh-interval", "disabled"), True, False)],
    prevent_initial_call=True,
)
def refresh_peakindexings(n_intervals, state, path):
    """Send only active or newly finalized runs; the grid keeps its selection, sort, filters, and page."""

    if path != "/peakindexings" or state is None:
        raise PreventUpdate
    rows = _peakindexing_rows(active_or_changed_since(live_rows.since_from_state(state)))
    transaction, next_state = live_rows.transaction(rows, "indexing_id", state)
    return transaction if transaction else dash.no_update, next_state


@dash.callback(
    Output("peakindexings-page-wire-recon-btn", "disabled"),
    Output("peakindexings-page-wire-recon-btn", "style"),
    Output("peakindexings-page-peakindex-btn", "disabled"),
    Output("peakindexings-page-peakindex-btn", "style"),
    Output("peakindexings-page-recon-index-btn-placeholder", "disabled"),
    Output("peakindexings-page-recon-index-btn-placeholder", "style"),
    Input("peakindexing-table", "selectedRows"),
    prevent_initial_call=False,
)
def update_button_states(selected_rows):
    enabled_style = {"backgroundColor": "#1abc9c", "borderColor": "#1abc9c"}
    disabled_style = {"backgroundColor": "#6c757d", "borderColor": "#6c757d"}

    has_selection = selected_rows and len(selected_rows) > 0

    if has_selection:
        return (
            False,
            enabled_style,  # New Recon
            False,
            enabled_style,  # New Index
            True,
            disabled_style,  # New Recon + Index (placeholder)
        )
    else:
        return (
            True,
            disabled_style,  # New Recon
            True,
            disabled_style,  # New Index
            True,
            disabled_style,  # New Recon + Index (placeholder)
        )


def _query_id(value):
    """Format an AG Grid numeric ID, treating pandas NaN as missing."""
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return str(int(value))
    return str(value)


@dash.callback(
    Output("peakindexings-url", "href"),
    Input("peakindexings-page-wire-recon-btn", "n_clicks"),
    State("peakindexing-table", "selectedRows"),
    prevent_initial_call=True,
)
def handle_recon_button(n_clicks, rows):
    if not n_clicks:
        return dash.no_update

    base_href = "/create-wire-reconstruction"

    if not rows:
        return base_href

    scan_ids, reconstruction_ids = [], []

    for row in rows:
        scan_id = _query_id(row.get("scan_number"))
        reconstruction_id = _query_id(row.get("reconstruction_id"))
        if not scan_id and not reconstruction_id:
            return dash.no_update
        scan_ids.append(scan_id or "")
        method = row.get("reconstruction_method")
        if method is None and row.get("aperture") is not None and pd.notna(row["aperture"]):
            aperture = str(row["aperture"]).lower()
            method = "wire" if "wire" in aperture else "ca"
        # Do not ask the wire form to copy a CA reconstruction.  The scan still
        # provides a valid source for the new wire reconstruction.
        reconstruction_ids.append(reconstruction_id if method in (None, "wire") else "")

    query_params = []
    if any(scan_ids):
        query_params.append(f"scan_id={','.join(scan_ids)}")
    if any(reconstruction_ids):
        query_params.append(f"reconstruction_id={','.join(reconstruction_ids)}")

    return f"{base_href}?{'&'.join(query_params)}"


@dash.callback(
    Output("peakindexings-url", "href", allow_duplicate=True),
    Input("peakindexings-page-peakindex-btn", "n_clicks"),
    State("peakindexing-table", "selectedRows"),
    prevent_initial_call=True,
)
def handle_peakindex_button(n_clicks, rows):
    if not n_clicks:
        return dash.no_update

    base_href = "/create-peakindexing"

    if not rows:
        return base_href

    scan_ids, reconstruction_ids, indexing_ids = [], [], []

    for row in rows:
        scan_ids.append(_query_id(row.get("scan_number")) or "")
        reconstruction_ids.append(_query_id(row.get("reconstruction_id")) or "")
        indexing_ids.append(_query_id(row.get("indexing_id")) or "")

    # Build query params - only include non-empty lists
    query_params = []
    if any(scan_ids):
        query_params.append(f"scan_id={','.join(scan_ids)}")
    if any(reconstruction_ids):
        query_params.append(f"reconstruction_id={','.join(reconstruction_ids)}")
    if any(indexing_ids):
        query_params.append(f"indexing_id={','.join(indexing_ids)}")

    # If no query params at all, return base href
    if not query_params:
        return base_href

    return f"{base_href}?{'&'.join(query_params)}"
