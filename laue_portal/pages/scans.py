import dash
from dash import html, dcc, Input, Output, State, set_props, ctx
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
        dbc.Container(fluid=True, className="p-0", children=[ 
            dag.AgGrid(
                id='metadata-table',
                columnSize="responsiveSizeToFit",
                dashGridOptions={"pagination": True, "paginationPageSize": 20, "domLayout": 'autoHeight',},
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
    db_schema.Metadata.user_name,
    db_schema.Metadata.date,
    db_schema.Metadata.notes,
]

CUSTOM_HEADER_NAMES = {
    'scanNumber': 'Scan ID',
    'user_name': 'User',
    'dataset_id': 'Dataset ID',
    'scan_dim': 'Scan Dim',
    # Add more custom names here as needed, e.g.:
    # 'date': 'Date of Scan',
}

def _get_metadatas():
    with Session(db_utils.ENGINE) as session:
        # Query with JOIN to get scan count for each metadata record
        query = session.query(
            *VISIBLE_COLS,
            func.concat(func.count(db_schema.Scan.id), 'D').label('scan_dim') # Count dimensions and label it as 'scan_dim'
        ).outerjoin(
            db_schema.Scan, db_schema.Metadata.scanNumber == db_schema.Scan.scanNumber
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
        'cellRenderer': 'CreateIndexPeaksButtonRenderer',
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
