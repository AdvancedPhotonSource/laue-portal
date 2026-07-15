import dash
import dash_ag_grid as dag
import dash_bootstrap_components as dbc
import pandas as pd
from dash import Input, Output, State, dcc, html
from dash.exceptions import PreventUpdate
from sqlalchemy import case, func
from sqlalchemy.orm import Session

import laue_portal.components.navbar as navbar
import laue_portal.database.db_schema as db_schema
import laue_portal.database.session_utils as session_utils
from laue_portal.processing.queue.core import STATUS_REVERSE_MAPPING

dash.register_page(__name__)

layout = html.Div(
    [
        navbar.navbar,
        dcc.Location(id="wire-recons-url", refresh=True),
        # Secondary action bar aligned to right
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Nav(
                            [
                                dbc.Button(
                                    "New Recon",
                                    id="wire-recons-page-wire-recon-btn",
                                    style={"backgroundColor": "#6c757d", "borderColor": "#6c757d"},
                                    className="me-2",
                                ),
                                dbc.Button(
                                    "New Index",
                                    id="wire-recons-page-peakindex-btn",
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
        dbc.Container(
            fluid=True,
            className="p-0",
            children=[
                dag.AgGrid(
                    id="wire-recon-table",
                    columnSize="responsiveSizeToFit",
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
    db_schema.WireRecon.wirerecon_id,
    db_schema.WireRecon.scanNumber,
    db_schema.WireRecon.scanPointslen,
    db_schema.WireRecon.author,
    db_schema.WireRecon.notes,
    db_schema.Job.submit_time,
    db_schema.Job.status,
]

SOURCE_COLS = {"scanNumber"}

CUSTOM_HEADER_NAMES = {
    "wirerecon_id": "Wire Reconstruction ID",
    "scanPointslen": "Points",
    "submit_time": "Date",
}


def _get_recons():
    with Session(session_utils.get_engine()) as session:
        running_status = STATUS_REVERSE_MAPPING["Running"]
        finished_status = STATUS_REVERSE_MAPPING["Finished"]

        subjob_progress = (
            session.query(
                db_schema.SubJob.job_id.label("job_id"),
                func.count(db_schema.SubJob.subjob_id).label("total_subjobs"),
                func.sum(case((db_schema.SubJob.status == finished_status, 1), else_=0)).label("completed_subjobs"),
            )
            .join(db_schema.Job, db_schema.SubJob.job_id == db_schema.Job.job_id)
            .join(db_schema.WireRecon, db_schema.WireRecon.job_id == db_schema.Job.job_id)
            .filter(db_schema.Job.status == running_status)
            .group_by(db_schema.SubJob.job_id)
            .subquery()
        )

        wirerecons = pd.read_sql(
            session.query(
                *VISIBLE_COLS,
                func.coalesce(subjob_progress.c.completed_subjobs, 0).label("completed_subjobs"),
                func.coalesce(subjob_progress.c.total_subjobs, 0).label("total_subjobs"),
            )
            .join(db_schema.Job, db_schema.WireRecon.job_id == db_schema.Job.job_id)
            .outerjoin(subjob_progress, db_schema.Job.job_id == subjob_progress.c.job_id)
            .statement,
            session.bind,
        )

        progress_cols = ["completed_subjobs", "total_subjobs"]
        wirerecons[progress_cols] = wirerecons[progress_cols].fillna(0).astype(int)
        wirerecons["status_progress"] = None
        running_rows = (wirerecons["status"] == running_status) & (wirerecons["total_subjobs"] > 0)
        wirerecons.loc[running_rows, "status_progress"] = (
            wirerecons.loc[running_rows, "completed_subjobs"].astype(str)
            + "/"
            + wirerecons.loc[running_rows, "total_subjobs"].astype(str)
        )

    # Format columns for ag-grid
    cols = []

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
                            "function": "params.data.scanNumber != null ? 'SN' + params.data.scanNumber : 'Unlinked'"
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

        if field_key == "wirerecon_id":
            col_def["cellRenderer"] = "WireReconLinkRenderer"
            col_def["sort"] = "desc"
        elif field_key in ["submit_time", "start_time", "finish_time"]:
            col_def["cellRenderer"] = "DateFormatter"
        elif field_key == "status":
            col_def["cellRenderer"] = "StatusRenderer"

        cols.append(col_def)

    return cols, wirerecons.to_dict("records")


@dash.callback(
    Output("wire-recon-table", "columnDefs", allow_duplicate=True),
    Output("wire-recon-table", "rowData", allow_duplicate=True),
    Input("wire-recons-url", "pathname"),
    prevent_initial_call="initial_duplicate",
)
def get_recons(path):
    if path == "/wire-reconstructions":
        cols, recons = _get_recons()
        return cols, recons
    else:
        raise PreventUpdate


@dash.callback(
    Output("wire-recons-page-wire-recon-btn", "disabled"),
    Output("wire-recons-page-wire-recon-btn", "style"),
    Output("wire-recons-page-peakindex-btn", "disabled"),
    Output("wire-recons-page-peakindex-btn", "style"),
    Input("wire-recon-table", "selectedRows"),
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
        )
    else:
        return (
            True,
            disabled_style,  # New Recon
            True,
            disabled_style,  # New Index
        )


def _query_id(value):
    """Format an AG Grid numeric ID without a possible pandas ``.0`` suffix."""
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return str(int(value))
    return str(value)


@dash.callback(
    Output("wire-recons-url", "href"),
    Input("wire-recons-page-wire-recon-btn", "n_clicks"),
    State("wire-recon-table", "selectedRows"),
    prevent_initial_call=True,
)
def handle_recon_button(n_clicks, rows):
    if not n_clicks:
        return dash.no_update

    base_href = "/create-wire-reconstruction"

    if not rows:
        return base_href

    row = rows[0]
    scan_id = _query_id(row.get("scanNumber"))
    wirerecon_id = _query_id(row.get("wirerecon_id"))
    if not wirerecon_id:
        return dash.no_update

    query_params = [f"wirerecon_id={wirerecon_id}"]
    if scan_id:
        query_params.insert(0, f"scan_id={scan_id}")
    return f"{base_href}?{'&'.join(query_params)}"


@dash.callback(
    Output("wire-recons-url", "href", allow_duplicate=True),
    Input("wire-recons-page-peakindex-btn", "n_clicks"),
    State("wire-recon-table", "selectedRows"),
    prevent_initial_call=True,
)
def handle_peakindex_button(n_clicks, rows):
    if not n_clicks:
        return dash.no_update

    base_href = "/create-peakindexing"

    if not rows:
        return base_href

    row = rows[0]
    scan_id = _query_id(row.get("scanNumber"))
    wirerecon_id = _query_id(row.get("wirerecon_id"))
    if not wirerecon_id:
        return dash.no_update

    query_params = [f"wirerecon_id={wirerecon_id}"]
    if scan_id:
        query_params.insert(0, f"scan_id={scan_id}")
    return f"{base_href}?{'&'.join(query_params)}"
