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

dash.register_page(__name__, path="/peakindexings")

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
                            id="peakindexing-page-wire-recon"
                        )
                    ),
                    html.Span("|", className="mx-2 text-muted"),
                    dbc.NavItem(
                        dbc.NavLink(
                            "New Index",
                            href="/create-peakindexing",
                            active=False,
                            id="peakindexing-page-peakindex"
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
    with Session(db_utils.ENGINE) as session:
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
        elif field_key in ['submit_time', 'start_time', 'finish_time']:
            col_def['cellRenderer'] = 'DateFormatter'  # Use the date formatter for datetime fields
        elif field_key == 'status':
            col_def['cellRenderer'] = 'StatusRenderer'  # Use custom status renderer
        cols.append(col_def)

    return cols, peakindexings.to_dict('records')

@dash.callback(
    Output('peakindexing-table', 'columnDefs'),
    Output('peakindexing-table', 'rowData'),
    Input('url','pathname'),
    prevent_initial_call=True,
)
def get_peakindexings(path):
       if path == '/peakindexings':
            cols, peakindexings_records = _get_peakindexings()
            return cols, peakindexings_records
       else:
            raise PreventUpdate


@dash.callback(
    Output('peakindexing-page-wire-recon', 'href'),
    Input('peakindexing-table','selectedRows'),
    State('peakindexing-page-wire-recon', 'href'),
    prevent_initial_call=True,
)
def selected_wirerecon_href(rows,href,id_query="?scan_id=$"):
    href = href.split(id_query)[0]
    if rows:
        scan_ids = [str(row['scanNumber']) for row in rows]
        wirerecon_ids = [str(row['wirerecon_id']) if row.get('wirerecon_id') else '' for row in rows]
        recon_ids = [str(row['recon_id']) if row.get('recon_id') else '' for row in rows]
        peakindex_ids = [str(row['peakindex_id']) for row in rows]

        wire_scans = any(wirerecon_ids)
        nonwire_scans = any(recon_ids)

        # Conflict condition: mixture of wirerecon_id and recon_id
        if any(wirerecon_ids) and any(recon_ids):
            return href

        # Missing ID condition
        if not all(wirerecon_ids) and not all(recon_ids):
            for row in rows:
                if not row.get('wirerecon_id') and not row.get('recon_id') and row.get('aperture'):
                    if 'wire' in row['aperture'].lower():
                        wire_scans = True
                    else:
                        nonwire_scans = True

        # Dynamic URL path
        # Conflict condition: mixture of wirerecon_id and recon_id( copied from above)
        if nonwire_scans and wire_scans:
            return href
        elif nonwire_scans:
            href = "/create-reconstruction"
         #else: pass # Use original href

        href += f"?scan_id=${','.join(scan_ids)}"
        if any(wirerecon_ids): href += f"&wirerecon_id={','.join(wirerecon_ids)}"
        if any(recon_ids): href += f"&recon_id={','.join(recon_ids)}"
        href += f"&peakindex_id={','.join(peakindex_ids)}"
    return href


@dash.callback(
    Output('peakindexing-page-peakindex', 'href'),
    Input('peakindexing-table','selectedRows'),
    State('peakindexing-page-peakindex', 'href'),
    prevent_initial_call=True,
)
def selected_peakindex_href(rows,href,id_query="?scan_id=$"):
    href = href.split(id_query)[0]
    if rows:
        scan_ids = [str(row['scanNumber']) for row in rows]
        wirerecon_ids = [str(row['wirerecon_id']) if row['wirerecon_id'] else '' for row in rows]
        recon_ids = [str(row['recon_id']) if row['recon_id'] else '' for row in rows]
        peakindex_ids = [str(row['peakindex_id']) for row in rows]

        href += f"?scan_id=${','.join(scan_ids)}"
        if any(wirerecon_ids): href += f"&wirerecon_id={','.join(wirerecon_ids)}"
        if any(recon_ids): href += f"&recon_id={','.join(recon_ids)}"
        href += f"&peakindex_id={','.join(peakindex_ids)}"
    return href
