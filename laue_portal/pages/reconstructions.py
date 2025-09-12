import dash
from dash import html, dcc, ctx, Input, Output
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
from dash.exceptions import PreventUpdate
import laue_portal.database.db_utils as db_utils
import laue_portal.database.db_schema as db_schema
from sqlalchemy import select
from sqlalchemy.orm import Session
import pandas as pd
import laue_portal.components.navbar as navbar
from laue_portal.components.recon_form import recon_form, set_recon_form_props

dash.register_page(__name__)

layout = html.Div([
        navbar.navbar,
        dcc.Location(id='url', refresh=False),
        
        # Secondary action bar aligned to right
        dbc.Row([
            dbc.Col([
                dbc.Nav([
                    dbc.NavItem(
                        dbc.NavLink(
                            "New Recon",
                            href="/create-reconstruction",
                            active=False,
                            id="mask-recons-page-mask-recon"
                        )
                    ),
                    html.Span("|", className="mx-2 text-muted"),
                    dbc.NavItem(
                        dbc.NavLink(
                            "New Index",
                            href="/create-peakindexing",
                            active=False,
                            id="mask-recons-page-peakindex"
                        )
                    ),
                    html.Span("|", className="mx-2 text-muted"),
                    dbc.NavItem(dbc.NavLink("New Recon with selected (only 1 sel)", href="#", active=False)),
                    html.Span("|", className="mx-2 text-muted"),
                    dbc.NavItem(dbc.NavLink("Stop ALL", href="#", active=False)),
                    html.Span("|", className="mx-2 text-muted"),
                    dbc.NavItem(dbc.NavLink("Stop Selected", href="#", active=False)),
                    html.Span("|", className="mx-2 text-muted"),
                    dbc.NavItem(dbc.NavLink("Set high Priority for selected (only 1 sel)", href="#", active=False)),
                ],
                className="bg-light px-2 py-2 d-flex justify-content-end w-100")
            ], width=12)
        ], className="mb-3 mt-0"),

        dbc.Container(fluid=True, className="p-0", children=[ 
            dag.AgGrid(
                id='recon-table',
                columnSize="responsiveSizeToFit",
                defaultColDef={
                    "filter": True,
            },
                dashGridOptions={
                    "pagination": True, 
                    "paginationPageSize": 20, 
                    "domLayout": 'autoHeight',
                    "rowSelection": 'multiple', 
                    "suppressRowClickSelection": True, 
                    "animateRows": False, 
                    "rowHeight": 32
                },
                style={'height': 'calc(100vh - 150px)', 'width': '100%'},
                className="ag-theme-alpine"
            )
        ]),
    ],
)

"""
=======================
Callbacks
=======================
"""
VISIBLE_COLS = [
    db_schema.Recon.recon_id,
    db_schema.Recon.scanNumber,
    db_schema.Recon.calib_id,
    db_schema.Recon.author,
    db_schema.Recon.notes,
    #db_schema.Recon.pxl_recon,
    db_schema.Catalog.sample_name,
    db_schema.Catalog.aperture,
    db_schema.Job.submit_time,
    db_schema.Job.start_time,
    db_schema.Job.finish_time,
    db_schema.Job.status,
]

CUSTOM_HEADER_NAMES = {
    'recon_id': 'Recon ID', #'ReconID',
    'scanNumber': 'Scan ID',
    'calib_id': 'Calibration ID',
    #'pxl_recon': 'Pixels'
    'submit_time': 'Date',
}

def _get_recons():
    with Session(db_utils.ENGINE) as session:
        recons = pd.read_sql(session.query(*VISIBLE_COLS)
            .join(db_schema.Catalog, db_schema.Recon.scanNumber == db_schema.Catalog.scanNumber)
            .join(db_schema.Job, db_schema.Recon.job_id == db_schema.Job.job_id)
            .statement, session.bind)

    # Format columns for ag-grid
    cols = []
    
    # Add explicit checkbox column as the first column
    cols.append({
        'headerName': '',
        'field': 'checkbox',
        'checkboxSelection': True,
        'headerCheckboxSelection': True,
        'width': 60,
        'pinned': 'left',
        'sortable': False,
        'filter': False,
        'resizable': False,
        'suppressMenu': True,
        'floatingFilter': False,
        'cellClass': 'ag-checkbox-cell',
        'headerClass': 'ag-checkbox-header',
    })
    
    for col in VISIBLE_COLS:
        field_key = col.key
        if field_key != 'aperture':
            header_name = CUSTOM_HEADER_NAMES.get(field_key, field_key.replace('_', ' ').title())
            
            col_def = {
                'headerName': header_name,
                'field': field_key,
                'filter': True, 
                'sortable': True, 
                'resizable': True,
                'floatingFilter': True,
                'unSortIcon': True,
            }

            if field_key == 'recon_id':
                col_def['cellRenderer'] = 'ReconLinkRenderer'
            elif field_key == 'dataset_id':
                col_def['cellRenderer'] = 'DatasetIdScanLinkRenderer'
            elif field_key == 'scanNumber':
                col_def['cellRenderer'] = 'ScanLinkRenderer'  # Use the custom JS renderer
            elif field_key in ['submit_time', 'start_time', 'finish_time']:
                col_def['cellRenderer'] = 'DateFormatter'  # Use the date formatter for datetime fields
            elif field_key == 'status':
                col_def['cellRenderer'] = 'StatusRenderer'  # Use custom status renderer
        
            cols.append(col_def)

    # Add the custom actions column
    cols.append({
        'headerName': 'Actions',
        'field': 'actions',  # This field doesn't need to exist in the data
        'cellRenderer': 'ActionButtonsRenderer',
        'sortable': False,
        'filter': False,
        'resizable': True, # Or False, depending on preference
        'suppressMenu': True, # Or False
        'width': 200 # Adjusted width for DBC buttons
    })
    # recons['id'] = recons['scanNumber'] # This was for dash_table and is not directly used by ag-grid unless getRowId is configured
    
    return cols, recons.to_dict('records')

@dash.callback(
    Output('recon-table', 'columnDefs'),
    Output('recon-table', 'rowData'),
    Input('url','pathname'),
    prevent_initial_call=True,
)
def get_recons(path):
    if path == '/reconstructions':
        cols, recons = _get_recons()
        return cols, recons
    else:
        raise PreventUpdate


@dash.callback(
    Output('mask-recons-page-mask-recon', 'href'),
    Input('recon-table','selectedRows'),
    State('mask-recons-page-mask-recon', 'href'),
    prevent_initial_call=True,
)
def selected_recon_href(rows,href,id_query="?recon_id=$"):
    href = href.split(id_query)[0]
    if rows:
        href += "?recon_id=$" + ','.join([str(row['recon_id']) for row in rows]) 
    return href


@dash.callback(
    Output('mask-recons-page-peakindex', 'href'),
    Input('recon-table','selectedRows'),
    State('mask-recons-page-peakindex', 'href'),
    prevent_initial_call=True,
)
def selected_peakindex_href(rows,href,id_query="?recon_id=$"):
    href = href.split(id_query)[0]
    if rows:
        href += "?recon_id=$" + ','.join([str(row['recon_id']) for row in rows]) 
    return href
