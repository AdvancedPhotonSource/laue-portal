import dash
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
from dash.exceptions import PreventUpdate
import laue_portal.database.db_utils as db_utils
import laue_portal.database.db_schema as db_schema
from sqlalchemy import select, func
from sqlalchemy.orm import Session
import pandas as pd
import laue_portal.components.navbar as navbar

dash.register_page(__name__, path='/')

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
                            href="/create-wire-reconstruction",
                            active=False,
                            id="create-wire-recons"
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
                id='metadata-table',
                columnSize="responsiveSizeToFit",
                defaultColDef={
                    "filter": True,
                    "checkboxSelection": {
                        "function": 'params.column == params.columnApi.getAllDisplayedColumns()[0]'
                    },
                    "headerCheckboxSelection": {
                        "function": 'params.column == params.columnApi.getAllDisplayedColumns()[0]'
                    },
            },
                dashGridOptions={"pagination": True, "paginationPageSize": 20, "domLayout": 'autoHeight',
                                 "rowSelection": 'multiple', "suppressRowClickSelection": True, "animateRows": False, "rowHeight": 32},
                style={'height': 'calc(100vh - 150px)', 'width': '100%'},
                className="ag-theme-alpine" 
            )
        ])
    ],
)

"""
=======================
Callbacks
=======================
"""
VISIBLE_COLS = [
    db_schema.Metadata.scanNumber,
    db_schema.Catalog.sample_name,
    db_schema.Catalog.aperture,
    db_schema.Metadata.user_name,
    db_schema.Metadata.time,
    db_schema.Catalog.notes,
]

CUSTOM_HEADER_NAMES = {
    'scanNumber': 'Scan ID',
    'user_name': 'User',
    'scan_dim': 'Scan Dim',
    'time': 'Date',
}

def _get_metadatas():
    with Session(db_utils.ENGINE) as session:
        # Query with JOINs to get scan count and catalog info for each metadata record
        query = session.query(
            *VISIBLE_COLS,
            func.concat(func.count(db_schema.Scan.id), 'D').label('scan_dim') # Count dimensions and label it as 'scan_dim'
        ).outerjoin(
            db_schema.Scan, db_schema.Metadata.scanNumber == db_schema.Scan.scanNumber
        ).outerjoin(
            db_schema.Catalog, db_schema.Metadata.scanNumber == db_schema.Catalog.scanNumber
        ).group_by(db_schema.Metadata.scanNumber)
        
        metadatas = pd.read_sql(query.statement, session.bind)

    # Format columns for ag-grid
    cols = []
    # Process the visible columns first
    for col in VISIBLE_COLS:
        field_key = col.key
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

        if field_key == 'scanNumber':
            col_def['cellRenderer'] = 'ScanLinkRenderer'  # Use the custom JS renderer
        elif field_key == 'time':
            col_def['cellRenderer'] = 'DateFormatter'  # Use the date formatter for datetime fields
        
        cols.append(col_def)
    
    # Add the scan count column
    cols.insert(3, {
        'headerName': CUSTOM_HEADER_NAMES['scan_dim'],
        'field': 'scan_dim',
        'filter': True,
        'sortable': True,
        'resizable': True,
        'floatingFilter': True,
        'unSortIcon': True,
    })

    # Add the custom actions column
    cols.insert(-1, {
        'headerName': 'Actions',
        'field': 'actions',  # This field doesn't need to exist in the data
        'cellRenderer': 'ActionButtonsRenderer',
        'sortable': False,
        'filter': False,
        'resizable': True, # Or False, depending on preference
        'suppressMenu': True, # Or False
        'width': 200 # Adjusted width for DBC buttons
    })

    return cols, metadatas.to_dict('records')



@dash.callback(
    Output('metadata-table', 'columnDefs', allow_duplicate=True),
    Output('metadata-table', 'rowData', allow_duplicate=True),
    Input('url','pathname'),
    prevent_initial_call=True,
)
def get_metadatas(path):
    if path == '/':
        cols, metadatas_records = _get_metadatas()
        return cols, metadatas_records
    else:
        raise PreventUpdate


@dash.callback(
    Output('create-wire-recons', 'href'),
    Input('metadata-table','selectedRows'),
    State('create-wire-recons', 'href'),
    prevent_initial_call=True,
)
def selected_scans_href(rows,href,id_query="?scan_id=$"):
    href = href.split(id_query)[0]
    if rows:
        href += "?scan_id=$" + ','.join([str(row['scanNumber']) for row in rows]) 
    return href
