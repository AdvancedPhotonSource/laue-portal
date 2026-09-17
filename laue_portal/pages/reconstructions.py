"""Unified reconstruction-run list page."""

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

dash.register_page(__name__, path="/reconstructions", redirect_from=["/wire-reconstructions"])

layout = html.Div(
    [
        navbar.navbar,
        dcc.Location(id="recons-url", refresh=True),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Nav(
                            [
                                dbc.Button(
                                    "New Wire Recon",
                                    id="recons-page-wire-recon-btn",
                                    style={"backgroundColor": "#6c757d", "borderColor": "#6c757d"},
                                    className="me-2",
                                ),
                                dbc.Button(
                                    "New Index",
                                    id="recons-page-peakindex-btn",
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
        dcc.Interval(id="recons-refresh-interval", interval=live_rows.REFRESH_SECONDS * 1000, n_intervals=0),
        dcc.Store(id="recons-refresh-state"),
        dbc.Container(
            fluid=True,
            className="p-0",
            children=[
                dag.AgGrid(
                    id="recon-table",
                    columnSize="responsiveSizeToFit",
                    getRowId="params.data.reconstruction_id",
                    defaultColDef={"filter": True},
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
    db_schema.ReconstructionRun.id.label("reconstruction_id"),
    db_schema.ReconstructionRun.method,
    db_schema.ReconstructionRun.scan_number,
    db_schema.WireReconstructionParameters.scan_points_len,
    db_schema.ReconstructionRun.author,
    db_schema.ReconstructionRun.notes,
    db_schema.Job.submit_time,
    db_schema.Job.start_time,
    db_schema.Job.finish_time,
    db_schema.Job.status,
]

SOURCE_COLS = {"scan_number"}

CUSTOM_HEADER_NAMES = {
    "reconstruction_id": "Reconstruction ID",
    "scan_points_len": "Points",
    "submit_time": "Date",
}


def _reconstruction_rows(criterion=None) -> list[dict]:
    """Rows for every reconstruction method; ``criterion`` restricts the query for a partial refresh."""

    with Session(session_utils.get_engine()) as session:
        # Progress comes from the run counters stored on the job; no per-frame rows are joined.
        query = (
            session.query(*VISIBLE_COLS, *progress_columns())
            .outerjoin(
                db_schema.WireReconstructionParameters,
                db_schema.WireReconstructionParameters.reconstruction_id == db_schema.ReconstructionRun.id,
            )
            .join(db_schema.Job, db_schema.ReconstructionRun.job_id == db_schema.Job.job_id)
        )
        if criterion is not None:
            query = query.filter(criterion)
        reconstructions = pd.read_sql(query.statement, session.bind)
    return live_rows.add_status_progress(reconstructions).to_dict("records")


def _get_recons():
    """Return all reconstruction methods with run-counter progress."""
    cols = [
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
    ]

    source_col_inserted = False
    for col in VISIBLE_COLS:
        field_key = col.key
        if field_key in SOURCE_COLS:
            if not source_col_inserted:
                cols.append(
                    {
                        "headerName": "Source",
                        "field": "source",
                        "cellRenderer": "ScanSourceLinkRenderer",
                        "filter": True,
                        "sortable": True,
                        "resizable": True,
                        "floatingFilter": True,
                        "unSortIcon": True,
                        "valueGetter": {
                            "function": "params.data.scan_number != null ? 'SN' + params.data.scan_number : 'Unlinked'"
                        },
                    }
                )
                source_col_inserted = True
            continue

        col_def = {
            "headerName": CUSTOM_HEADER_NAMES.get(field_key, field_key.replace("_", " ").title()),
            "field": field_key,
            "filter": True,
            "sortable": True,
            "resizable": True,
            "floatingFilter": True,
            "unSortIcon": True,
        }
        if field_key == "reconstruction_id":
            col_def["cellRenderer"] = "ReconstructionLinkRenderer"
            col_def["sort"] = "desc"
        elif field_key in ["submit_time", "start_time", "finish_time"]:
            col_def["cellRenderer"] = "DateFormatter"
        elif field_key == "status":
            col_def["cellRenderer"] = "StatusRenderer"
        cols.append(col_def)

    return cols, _reconstruction_rows()


@dash.callback(
    Output("recon-table", "columnDefs"),
    Output("recon-table", "rowData"),
    Output("recons-refresh-state", "data"),
    Input("recons-url", "pathname"),
    prevent_initial_call=True,
)
def get_recons(path):
    if path == "/reconstructions":
        cols, rows = _get_recons()
        return cols, rows, live_rows.initial_state(rows, "reconstruction_id")
    raise PreventUpdate


@dash.callback(
    Output("recon-table", "rowTransaction"),
    Output("recons-refresh-state", "data", allow_duplicate=True),
    Input("recons-refresh-interval", "n_intervals"),
    State("recons-refresh-state", "data"),
    State("recons-url", "pathname"),
    running=[(Output("recons-refresh-interval", "disabled"), True, False)],
    prevent_initial_call=True,
)
def refresh_recons(n_intervals, state, path):
    """Send only active or newly finalized runs; the grid keeps its selection, sort, filters, and page."""

    if path != "/reconstructions" or state is None:
        raise PreventUpdate
    rows = _reconstruction_rows(active_or_changed_since(live_rows.since_from_state(state)))
    transaction, next_state = live_rows.transaction(rows, "reconstruction_id", state)
    return transaction if transaction else dash.no_update, next_state


@dash.callback(
    Output("recons-page-wire-recon-btn", "disabled"),
    Output("recons-page-wire-recon-btn", "style"),
    Output("recons-page-peakindex-btn", "disabled"),
    Output("recons-page-peakindex-btn", "style"),
    Input("recon-table", "selectedRows"),
    prevent_initial_call=False,
)
def update_button_states(selected_rows):
    enabled_style = {"backgroundColor": "#1abc9c", "borderColor": "#1abc9c"}
    disabled_style = {"backgroundColor": "#6c757d", "borderColor": "#6c757d"}
    has_single_selection = bool(selected_rows and len(selected_rows) == 1)
    can_copy_wire = has_single_selection and selected_rows[0].get("method") == "wire"
    return (
        not can_copy_wire,
        enabled_style if can_copy_wire else disabled_style,
        not has_single_selection,
        enabled_style if has_single_selection else disabled_style,
    )


def _query_id(value):
    """Format an AG Grid numeric ID without a possible pandas ``.0`` suffix."""
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return str(int(value))
    return str(value)


def _selected_run_href(rows, base_href):
    if not rows:
        return base_href
    row = rows[0]
    reconstruction_id = _query_id(row.get("reconstruction_id"))
    if not reconstruction_id:
        return dash.no_update
    query_params = [f"reconstruction_id={reconstruction_id}"]
    scan_id = _query_id(row.get("scan_number"))
    if scan_id:
        query_params.insert(0, f"scan_id={scan_id}")
    return f"{base_href}?{'&'.join(query_params)}"


@dash.callback(
    Output("recons-url", "href"),
    Input("recons-page-wire-recon-btn", "n_clicks"),
    State("recon-table", "selectedRows"),
    prevent_initial_call=True,
)
def handle_recon_button(n_clicks, rows):
    if not n_clicks:
        return dash.no_update
    if not rows or rows[0].get("method") != "wire":
        return dash.no_update
    return _selected_run_href(rows, "/create-wire-reconstruction")


@dash.callback(
    Output("recons-url", "href", allow_duplicate=True),
    Input("recons-page-peakindex-btn", "n_clicks"),
    State("recon-table", "selectedRows"),
    prevent_initial_call=True,
)
def handle_peakindex_button(n_clicks, rows):
    if not n_clicks:
        return dash.no_update
    return _selected_run_href(rows, "/create-peakindexing")
