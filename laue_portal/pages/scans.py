import dash
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
from dash.exceptions import PreventUpdate
from laue_portal.database import db_utils, db_schema
from sqlalchemy import select, func
from sqlalchemy.orm import Session
import pandas as pd
import laue_portal.components.navbar as navbar
from laue_portal.pages.scan import build_technique_strings
import laue_portal.database.session_utils as session_utils

dash.register_page(__name__, path='/scans')

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
                            id="scans-page-wire-recon"
                        )
                    ),
                    html.Span("|", className="mx-2 text-muted"),
                    dbc.NavItem(
                        dbc.NavLink(
                            "New Index",
                            href="/create-peakindexing",
                            active=False,
                            id="scans-page-peakindex"
                        )
                    ),
                    html.Span("|", className="mx-2 text-muted"),
                    dbc.NavItem(dbc.NavLink("New Recon + Index", href="#", active=False)),
                    html.Span("|", className="mx-2 text-muted"),
                    dbc.NavItem(dbc.NavLink("Energy to K-space", href="#", active=False)),
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
    with Session(session_utils.get_engine()) as session:
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
        
        # Add technique column by computing it for each scan
        techniques = []
        for _, row in metadatas.iterrows():
            scan_number = row['scanNumber']
            # Get all scan records for this scan number
            scans_data = session.query(db_schema.Scan).filter(db_schema.Scan.scanNumber == scan_number).all()
            
            if scans_data:
                # Get the filtered technique string (first element of tuple)
                filtered_str, _ = build_technique_strings(scans_data)
                techniques.append(filtered_str)
            else:
                techniques.append("none")
        
        metadatas['technique'] = techniques

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
    
    # Process the visible columns
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
    cols.insert(4, {
        'headerName': CUSTOM_HEADER_NAMES['scan_dim'],
        'field': 'scan_dim',
        'filter': True,
        'sortable': True,
        'resizable': True,
        'floatingFilter': True,
        'unSortIcon': True,
    })
    
    # Add the technique column
    cols.insert(5, {
        'headerName': 'Technique',
        'field': 'technique',
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
        'width': 200, # Adjusted width for DBC buttons
    })

    return cols, metadatas.to_dict('records')



@dash.callback(
    Output('metadata-table', 'columnDefs', allow_duplicate=True),
    Output('metadata-table', 'rowData', allow_duplicate=True),
    Input('url','pathname'),
    prevent_initial_call=True,
)
def get_metadatas(path):
    if path == '/scans':
        cols, metadatas_records = _get_metadatas()
        return cols, metadatas_records
    else:
        raise PreventUpdate


@dash.callback(
    Output('scans-page-wire-recon', 'href'),
    Input('metadata-table','selectedRows'),
    State('scans-page-wire-recon', 'href'),
    prevent_initial_call=True,
)
def selected_recon_href(rows,href):
    base_href = href.split("?")[0]
    if not rows:
        return base_href

    scan_ids = []
    any_wire_scans, any_nonwire_scans = False, False

    for row in rows:
        if row.get('scanNumber'):
            scan_ids.append(str(row['scanNumber']))
        else:
            return base_href

        if row.get('aperture'):
            aperture = str(row['aperture']).lower()
            if aperture == 'none':
                return base_href # Conflict condition: cannot be reconstructed
            if 'wire' in aperture:
                any_wire_scans = True
            else:
                any_nonwire_scans = True
        
            # Conflict condition: mixture of wirerecon and recon
            if any_wire_scans and any_nonwire_scans:
                return base_href

    if any_nonwire_scans:
        base_href = "/create-reconstruction"
    
    return f"{base_href}?scan_id={','.join(scan_ids)}"


@dash.callback(
    Output('scans-page-peakindex', 'href'),
    Input('metadata-table','selectedRows'),
    State('scans-page-peakindex', 'href'),
    prevent_initial_call=True,
)
def selected_peakindex_href(rows,href):
    base_href = href.split("?")[0]
    if not rows:
        return base_href

    scan_ids = []

    for row in rows:
        if row.get('scanNumber'):
            scan_ids.append(str(row['scanNumber']))
        else:
            return base_href

    return f"{base_href}?scan_id={','.join(scan_ids)}"
