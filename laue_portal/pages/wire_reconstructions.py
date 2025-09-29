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
from laue_portal.pages.scan import build_technique_strings
import laue_portal.database.session_utils as session_utils

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
                            href="/create-wire-reconstruction",
                            active=False,
                            id="wire-recons-page-wire-recon"
                        )
                    ),
                    html.Span("|", className="mx-2 text-muted"),
                    dbc.NavItem(
                        dbc.NavLink(
                            "New Index",
                            href="/create-peakindexing",
                            active=False,
                            id="wire-recons-page-peakindex"
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
                id='wire-recon-table',
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
                    "rowHeight": 64
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
    db_schema.WireRecon.wirerecon_id,
    db_schema.WireRecon.scanNumber,
    # db_schema.WireRecon.calib_id,
    db_schema.WireRecon.author,
    db_schema.WireRecon.notes,
    #db_schema.WireRecon.pxl_recon,
    db_schema.Catalog.sample_name,
    db_schema.Catalog.aperture,
    db_schema.Job.submit_time,
    db_schema.Job.start_time,
    db_schema.Job.finish_time,
    db_schema.Job.status,
]

CUSTOM_HEADER_NAMES = {
    'wirerecon_id': 'Recon ID (Wire)', #'Wire Recon ID', #'ReconID',
    'scanNumber': 'Scan Info', #'Scan ID',
    'calib_id': 'Calibration ID',
    #'pxl_recon': 'Pixels'
    'submit_time': 'Date',
}

def _get_recons():
    with Session(session_utils.get_engine()) as session:
        # Query with JOINs to get scan count and catalog info for each wire reconstruction
        query = session.query(
            *VISIBLE_COLS,
            func.concat(func.count(db_schema.Scan.id), 'D').label('scan_dim') # Count dimensions and label it as 'scan_dim'
        ).join(
            db_schema.Catalog, db_schema.WireRecon.scanNumber == db_schema.Catalog.scanNumber
        ).join(
            db_schema.Job, db_schema.WireRecon.job_id == db_schema.Job.job_id
        ).outerjoin(
            db_schema.Scan, db_schema.WireRecon.scanNumber == db_schema.Scan.scanNumber
        ).group_by(*VISIBLE_COLS)
        
        wirerecons = pd.read_sql(query.statement, session.bind)
        
        # Add technique column by computing it for each wire reconstruction
        techniques = []
        for _, row in wirerecons.iterrows():
            scan_number = row['scanNumber']
            # Get all scan records for this scan number
            scans_data = session.query(db_schema.Scan).filter(db_schema.Scan.scanNumber == scan_number).all()
            
            if scans_data:
                # Get the filtered technique string (first element of tuple)
                filtered_str, _ = build_technique_strings(scans_data)
                techniques.append(filtered_str)
            else:
                techniques.append("none")
        
        wirerecons['technique'] = techniques

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
        if field_key in ['aperture', 'sample_name']:
            continue
            
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

        if field_key == 'wirerecon_id':
            col_def['cellRenderer'] = 'WireReconLinkRenderer'
        elif field_key == 'dataset_id':
            col_def['cellRenderer'] = 'DatasetIdScanLinkRenderer'
        elif field_key == 'scanNumber':
            # Custom multi-line display for Scan ID column
            col_def['cellRenderer'] = 'WireReconScanLinkRenderer'  # Use the wire recon specific renderer
            col_def['valueGetter'] = {"function": """
                'Scan ID: ' + params.data.scanNumber + '|' +
                'Sample: ' + params.data.sample_name + '|' +
                params.data.scan_dim + ': ' + params.data.technique + ' (' + 
                (params.data.aperture.toLowerCase().includes('coded') ? 'CA' : params.data.aperture) + ')'
            """}
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
    
    return cols, wirerecons.to_dict('records')

@dash.callback(
    Output('wire-recon-table', 'columnDefs'),
    Output('wire-recon-table', 'rowData'),
    Input('url','pathname'),
    prevent_initial_call=True,
)
def get_recons(path):
    if path == '/wire-reconstructions':
        cols, recons = _get_recons()
        return cols, recons
    else:
        raise PreventUpdate


@dash.callback(
    Output('wire-recons-page-wire-recon', 'href'),
    Output('wire-recons-page-peakindex', 'href'),
    Input('wire-recon-table','selectedRows'),
    State('wire-recons-page-wire-recon', 'href'),
    State('wire-recons-page-peakindex', 'href'),
    prevent_initial_call=True,
)
def selected_hrefs(rows, wirerecon_href, peakindex_href):
    base_wirerecon_href = wirerecon_href.split("?")[0]
    base_peakindex_href = peakindex_href.split("?")[0]
    if not rows:
        return base_wirerecon_href, base_peakindex_href

    scan_ids, wirerecon_ids = [], []

    for row in rows:
        if row.get('scanNumber'):
            scan_ids.append(str(row['scanNumber']))
        else:
            return base_wirerecon_href, base_peakindex_href
        
        wirerecon_ids.append(str(row['wirerecon_id']) if row.get('wirerecon_id') else '')

    query_params = [f"scan_id=${','.join(scan_ids)}"]
    if any(wirerecon_ids): query_params.append(f"wirerecon_id={','.join(wirerecon_ids)}")
    
    query_string = "&".join(query_params)
    
    return f"{base_wirerecon_href}?{query_string}", f"{base_peakindex_href}?{query_string}"
