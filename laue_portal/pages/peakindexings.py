import dash
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
from dash.exceptions import PreventUpdate
import laue_portal.database.db_utils as db_utils
import laue_portal.database.db_schema as db_schema
from sqlalchemy import select, func
from sqlalchemy.orm import Session, aliased
import pandas as pd
import laue_portal.components.navbar as navbar
import laue_portal.database.session_utils as session_utils

dash.register_page(__name__, path="/peakindexings")

layout = html.Div([
        navbar.navbar,
        dcc.Location(id='peakindexings-url', refresh=True),
        
        # Secondary action bar aligned to right
        dbc.Row([
            dbc.Col([
                dbc.Nav([
                    dbc.Button(
                        "New Recon",
                        id="peakindexings-page-wire-recon-btn",
                        style={"backgroundColor": "#6c757d", "borderColor": "#6c757d"},
                        className="me-2"
                    ),
                    dbc.Button(
                        "New Index",
                        id="peakindexings-page-peakindex-btn",
                        style={"backgroundColor": "#6c757d", "borderColor": "#6c757d"},
                        className="me-2"
                    ),
                    dbc.Button(
                        "New Recon + Index",
                        id="peakindexings-page-recon-index-btn-placeholder",
                        style={"backgroundColor": "#6c757d", "borderColor": "#6c757d"},
                        className="me-2"
                    ),
                ],
                className="bg-light px-2 py-2 d-flex justify-content-end w-100")
            ], width=12)
        ], className="mb-3 mt-0"),

        dbc.Container(fluid=True, className="p-0", children=[ 
            dag.AgGrid(
                id='peakindexing-table',
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
    db_schema.PeakIndex.peakindex_id,
    db_schema.PeakIndex.scanNumber,
    db_schema.PeakIndex.author,
    db_schema.PeakIndex.notes,
    db_schema.PeakIndex.recon_id,
    db_schema.PeakIndex.wirerecon_id,
    db_schema.PeakIndex.boxsize,
    db_schema.PeakIndex.threshold,
    # db_schema.PeakIndexResults.structure,
    db_schema.Job.submit_time,
    db_schema.Job.start_time,
    db_schema.Job.finish_time,
    db_schema.Job.status,
]

CUSTOM_HEADER_NAMES = {
    'peakindex_id': 'Peak Indexing ID',
    'scanNumber': 'Scan ID',
    'recon_id': 'Recon ID', #'ReconID',
    'wirerecon_id': 'Wire Recon ID', #'ReconID',
    #'': 'Points',
    'boxsize': 'Box',
    'submit_time,': 'Date',
}

def _get_peakindexings():
    with Session(session_utils.get_engine()) as session:
        catalog_recon = aliased(db_schema.Catalog)
        catalog_wirerecon = aliased(db_schema.Catalog)

        peakindexings = pd.read_sql(session.query(
                *VISIBLE_COLS,
                func.coalesce(catalog_recon.aperture, catalog_wirerecon.aperture).label('aperture')
            )
            .join(db_schema.Job, db_schema.PeakIndex.job_id == db_schema.Job.job_id)
            .outerjoin(db_schema.Recon, db_schema.PeakIndex.recon_id == db_schema.Recon.recon_id)
            .outerjoin(db_schema.WireRecon, db_schema.PeakIndex.wirerecon_id == db_schema.WireRecon.wirerecon_id)
            .outerjoin(catalog_recon, db_schema.Recon.scanNumber == catalog_recon.scanNumber)
            .outerjoin(catalog_wirerecon, db_schema.WireRecon.scanNumber == catalog_wirerecon.scanNumber)
            .statement, session.bind)

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
        if field_key == 'peakindex_id':
            col_def['cellRenderer'] = 'PeakIndexLinkRenderer'
        elif field_key == 'recon_id':
            col_def['cellRenderer'] = 'ReconLinkRenderer'
        elif field_key == 'wirerecon_id':
            col_def['cellRenderer'] = 'WireReconLinkRenderer'
        elif field_key == 'dataset_id':
            col_def['cellRenderer'] = 'DatasetIdScanLinkRenderer'
        elif field_key == 'scanNumber':
            col_def['cellRenderer'] = 'ScanLinkRenderer'  # Use the custom JS renderer
            # Handle NULL scanNumber for unlinked indexes
            col_def['valueGetter'] = {"function": "params.data.scanNumber == null ? 'Unlinked' : params.data.scanNumber"}
        elif field_key in ['submit_time', 'start_time', 'finish_time']:
            col_def['cellRenderer'] = 'DateFormatter'  # Use the date formatter for datetime fields
        elif field_key == 'status':
            col_def['cellRenderer'] = 'StatusRenderer'  # Use custom status renderer
        cols.append(col_def)

    return cols, peakindexings.to_dict('records')

@dash.callback(
    Output('peakindexing-table', 'columnDefs', allow_duplicate=True),
    Output('peakindexing-table', 'rowData', allow_duplicate=True),
    Input('peakindexings-url','pathname'),
    prevent_initial_call='initial_duplicate',
)
def get_peakindexings(path):
    if path == '/peakindexings':
        cols, peakindexings_records = _get_peakindexings()
        return cols, peakindexings_records
    else:
        raise PreventUpdate


@dash.callback(
    Output('peakindexings-page-wire-recon-btn', 'disabled'),
    Output('peakindexings-page-wire-recon-btn', 'style'),
    Output('peakindexings-page-peakindex-btn', 'disabled'),
    Output('peakindexings-page-peakindex-btn', 'style'),
    Output('peakindexings-page-recon-index-btn-placeholder', 'disabled'),
    Output('peakindexings-page-recon-index-btn-placeholder', 'style'),
    Input('peakindexing-table', 'selectedRows'),
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
    Output('peakindexings-url', 'href'),
    Input('peakindexings-page-wire-recon-btn', 'n_clicks'),
    State('peakindexing-table', 'selectedRows'),
    prevent_initial_call=True,
)
def handle_recon_button(n_clicks, rows):
    if not n_clicks:
        return dash.no_update

    base_href = "/create-wire-reconstruction"

    if not rows:
        return base_href

    scan_ids, wirerecon_ids, recon_ids = [], [], []
    any_wirerecon_scans, any_recon_scans = False, False

    for row in rows:
        if row.get('scanNumber'):
            scan_ids.append(str(row['scanNumber']))
        else:
            return dash.no_update
        
        wirerecon_ids.append(str(row['wirerecon_id']) if row.get('wirerecon_id') else '')
        any_wirerecon_scans = any(wirerecon_ids)
        recon_ids.append(str(row['recon_id']) if row.get('recon_id') else '')
        any_recon_scans = any(recon_ids)

        # Conflict condition: mixture of wirerecon and recon
        if any_wirerecon_scans and any_recon_scans:
            return dash.no_update

        # Missing Recon ID condition
        if not any_wirerecon_scans and not any_recon_scans and row.get('aperture'):
            aperture = str(row['aperture']).lower()
            if aperture == 'none':
                return dash.no_update  # Conflict condition: cannot be reconstructed
            elif 'wire' in aperture:
                any_wirerecon_scans = True
            else:
                any_recon_scans = True
    
            # Conflict condition: mixture of wirerecon and recon (copied from above)
            if any_wirerecon_scans and any_recon_scans:
                return dash.no_update
    
    if any_recon_scans:
        base_href = "/create-reconstruction"
    elif any_wirerecon_scans:
        base_href = "/create-wire-reconstruction"

    query_params = [f"scan_id={','.join(scan_ids)}"]
    if any_wirerecon_scans: 
        query_params.append(f"wirerecon_id={','.join(wirerecon_ids)}")
    if any_recon_scans: 
        query_params.append(f"recon_id={','.join(recon_ids)}")
    
    return f"{base_href}?{'&'.join(query_params)}"


@dash.callback(
    Output('peakindexings-url', 'href', allow_duplicate=True),
    Input('peakindexings-page-peakindex-btn', 'n_clicks'),
    State('peakindexing-table', 'selectedRows'),
    prevent_initial_call=True,
)
def handle_peakindex_button(n_clicks, rows):
    if not n_clicks:
        return dash.no_update
    
    base_href = "/create-peakindexing"
    
    if not rows:
        return base_href
    
    scan_ids, wirerecon_ids, recon_ids, peakindex_ids = [], [], [], []

    for row in rows:
        # scanNumber can be None for unlinked peakindexes - that's okay
        if row.get('scanNumber'):
            scan_ids.append(str(row['scanNumber']))
        # Note: We don't return base_href here anymore - unlinked peakindexes are valid
        
        wirerecon_ids.append(str(row['wirerecon_id']) if row.get('wirerecon_id') else '')
        recon_ids.append(str(row['recon_id']) if row.get('recon_id') else '')
        peakindex_ids.append(str(row['peakindex_id']) if row.get('peakindex_id') else '')

    # Build query params - only include non-empty lists
    query_params = []
    if any(scan_ids): 
        query_params.append(f"scan_id={','.join(scan_ids)}")
    if any(wirerecon_ids): 
        query_params.append(f"wirerecon_id={','.join(wirerecon_ids)}")
    if any(recon_ids): 
        query_params.append(f"recon_id={','.join(recon_ids)}")
    if any(peakindex_ids): 
        query_params.append(f"peakindex_id={','.join(peakindex_ids)}")

    # If no query params at all, return base href
    if not query_params:
        return base_href

    return f"{base_href}?{'&'.join(query_params)}"
