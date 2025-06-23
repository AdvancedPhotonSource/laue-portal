import dash
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
from dash.exceptions import PreventUpdate
import laue_portal.database.db_utils as db_utils
import laue_portal.database.db_schema as db_schema
from sqlalchemy import select
from sqlalchemy.orm import Session
import pandas as pd 
import laue_portal.components.navbar as navbar

dash.register_page(__name__)

layout = html.Div([
        navbar.navbar,
        dcc.Location(id='url', refresh=False),
        dbc.Container(fluid=True, className="p-0", children=[
            dag.AgGrid(
                id='wire-recon-table',
                columnSize="responsiveSizeToFit",
                dashGridOptions={"pagination": True, "paginationPageSize": 20, "domLayout": 'autoHeight'},
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
    db_schema.WireRecon.date,
    db_schema.WireRecon.calib_id,
    # db_schema.WireRecon.dataset_id,
    db_schema.WireRecon.scanNumber,
    db_schema.Catalog.sample_name,
    db_schema.Catalog.aperture,
    db_schema.WireRecon.notes,
]

CUSTOM_HEADER_NAMES = {
    'scanNumber': 'Scan ID',
    'calib_id': 'Calibration ID',
    # 'dataset_id': 'Dataset ID',
    'wirerecon_id': 'Recon ID', #'Wire Recon ID', #'ReconID',
    # Add more custom names here as needed, e.g.:
    # 'date': 'Date of Scan',
}

def _get_recons():
    with Session(db_utils.ENGINE) as session:
        query = session.query(*VISIBLE_COLS).join(
            db_schema.Catalog, db_schema.WireRecon.scanNumber == db_schema.Catalog.scanNumber
        )
    wirerecons = pd.read_sql(query.statement, session.bind)

    # Format columns for ag-grid
    cols = []
    for col in VISIBLE_COLS:
        field_key = col.key
        header_name = CUSTOM_HEADER_NAMES.get(field_key, field_key.replace('_', ' ').title())
        
        col_def = {
            'headerName': header_name,
            'field': field_key,
            'filter': True, 
            'sortable': True, 
            'resizable': True,
            'suppressMenuHide': True
        }

        if field_key == 'wirerecon_id':
            col_def['cellRenderer'] = 'WireReconLinkRenderer'
        elif field_key == 'dataset_id':
            col_def['cellRenderer'] = 'DatasetIdScanLinkRenderer'
        elif field_key == 'scanNumber':
            col_def['cellRenderer'] = 'ScanLinkRenderer'  # Use the custom JS renderer
        
        if field_key != 'aperture':
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