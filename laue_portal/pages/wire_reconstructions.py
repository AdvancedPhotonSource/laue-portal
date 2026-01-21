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
        dcc.Location(id='wire-recons-url', refresh=True),
        
        # Secondary action bar aligned to right
        dbc.Row([
            dbc.Col([
                dbc.Nav([
                    dbc.Button(
                        "New Recon",
                        id="wire-recons-page-wire-recon-btn",
                        style={"backgroundColor": "#6c757d", "borderColor": "#6c757d"},
                        className="me-2"
                    ),
                    dbc.Button(
                        "New Index",
                        id="wire-recons-page-peakindex-btn",
                        style={"backgroundColor": "#6c757d", "borderColor": "#6c757d"},
                        className="me-2"
                    ),
                    dbc.Button(
                        "New Recon + Index",
                        id="wire-recons-page-recon-index-btn-placeholder",
                        style={"backgroundColor": "#6c757d", "borderColor": "#6c757d"},
                        className="me-2"
                    ),
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
        # Use LEFT OUTER JOIN for Catalog and Scan to include unlinked wire reconstructions
        query = session.query(
            *VISIBLE_COLS,
            func.concat(func.count(db_schema.Scan.id), 'D').label('scan_dim') # Count dimensions and label it as 'scan_dim'
        ).join(
            db_schema.Job, db_schema.WireRecon.job_id == db_schema.Job.job_id
        ).outerjoin(
            db_schema.Catalog, db_schema.WireRecon.scanNumber == db_schema.Catalog.scanNumber
        ).outerjoin(
            db_schema.Scan, db_schema.WireRecon.scanNumber == db_schema.Scan.scanNumber
        ).group_by(*VISIBLE_COLS)
        
        wirerecons = pd.read_sql(query.statement, session.bind)
        
        # Add technique column by computing it for each wire reconstruction
        techniques = []
        for _, row in wirerecons.iterrows():
            scan_number = row['scanNumber']
            # Handle unlinked wire reconstructions (NULL scanNumber)
            if pd.isna(scan_number) or scan_number is None:
                techniques.append("unlinked")
            else:
                # Get all scan records for this scan number
                scans_data = session.query(db_schema.Scan).filter(db_schema.Scan.scanNumber == scan_number).all()
                
                if scans_data:
                    # Get the filtered technique string (first element of tuple)
                    filtered_str, _ = build_technique_strings(scans_data)
                    techniques.append(filtered_str)
                else:
                    techniques.append("none")
        
        wirerecons['technique'] = techniques
        
        # Fill NaN values for display purposes
        wirerecons['sample_name'] = wirerecons['sample_name'].fillna('N/A')
        wirerecons['aperture'] = wirerecons['aperture'].fillna('N/A')
        wirerecons['scan_dim'] = wirerecons['scan_dim'].fillna('0D')

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
                params.data.scanNumber == null ? 
                'Unlinked' :
                'Scan ID: ' + params.data.scanNumber + '|' +
                'Sample: ' + (params.data.sample_name || 'N/A') + '|' +
                (params.data.scan_dim || '0D') + ': ' + (params.data.technique || 'none') + ' (' + 
                (params.data.aperture && params.data.aperture.toLowerCase().includes('coded') ? 'CA' : (params.data.aperture || 'N/A')) + ')'
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
    Output('wire-recon-table', 'columnDefs', allow_duplicate=True),
    Output('wire-recon-table', 'rowData', allow_duplicate=True),
    Input('wire-recons-url','pathname'),
    prevent_initial_call='initial_duplicate',
)
def get_recons(path):
    if path == '/wire-reconstructions':
        cols, recons = _get_recons()
        return cols, recons
    else:
        raise PreventUpdate


@dash.callback(
    Output('wire-recons-page-wire-recon-btn', 'disabled'),
    Output('wire-recons-page-wire-recon-btn', 'style'),
    Output('wire-recons-page-peakindex-btn', 'disabled'),
    Output('wire-recons-page-peakindex-btn', 'style'),
    Output('wire-recons-page-recon-index-btn-placeholder', 'disabled'),
    Output('wire-recons-page-recon-index-btn-placeholder', 'style'),
    Input('wire-recon-table', 'selectedRows'),
    prevent_initial_call=False,
)
def update_button_states(selected_rows):
    enabled_style = {"backgroundColor": "#1abc9c", "borderColor": "#1abc9c"}
    disabled_style = {"backgroundColor": "#6c757d", "borderColor": "#6c757d"}

    has_selection = selected_rows and len(selected_rows) > 0

    if has_selection:
        return (
            False, enabled_style,  # New Recon
            False, enabled_style,  # New Index
            True, disabled_style,  # New Recon + Index (placeholder)
        )
    else:
        return (
            True, disabled_style,  # New Recon
            True, disabled_style,  # New Index
            True, disabled_style,  # New Recon + Index (placeholder)
        )


@dash.callback(
    Output('wire-recons-url', 'href'),
    Input('wire-recons-page-wire-recon-btn', 'n_clicks'),
    State('wire-recon-table', 'selectedRows'),
    prevent_initial_call=True,
)
def handle_recon_button(n_clicks, rows):
    if not n_clicks:
        return dash.no_update

    base_href = "/create-wire-reconstruction"

    if not rows:
        return base_href

    scan_ids, wirerecon_ids = [], []

    for row in rows:
        if row.get('scanNumber'):
            scan_ids.append(str(row['scanNumber']))
        else:
            return dash.no_update
        
        wirerecon_ids.append(str(row['wirerecon_id']) if row.get('wirerecon_id') else '')

    query_params = [f"scan_id={','.join(scan_ids)}"]
    if any(wirerecon_ids): 
        query_params.append(f"wirerecon_id={','.join(wirerecon_ids)}")
    
    return f"{base_href}?{'&'.join(query_params)}"


@dash.callback(
    Output('wire-recons-url', 'href', allow_duplicate=True),
    Input('wire-recons-page-peakindex-btn', 'n_clicks'),
    State('wire-recon-table', 'selectedRows'),
    prevent_initial_call=True,
)
def handle_peakindex_button(n_clicks, rows):
    if not n_clicks:
        return dash.no_update
    
    base_href = "/create-peakindexing"
    
    if not rows:
        return base_href
    
    scan_ids, wirerecon_ids = [], []
    
    for row in rows:
        if row.get('scanNumber'):
            scan_ids.append(str(row['scanNumber']))
        else:
            return base_href
        
        wirerecon_ids.append(str(row['wirerecon_id']) if row.get('wirerecon_id') else '')
    
    query_params = [f"scan_id={','.join(scan_ids)}"]
    if any(wirerecon_ids): 
        query_params.append(f"wirerecon_id={','.join(wirerecon_ids)}")
    
    return f"{base_href}?{'&'.join(query_params)}"
