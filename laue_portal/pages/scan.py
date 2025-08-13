import dash
from dash import html, dcc, callback, Input, Output, State, set_props
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
import laue_portal.database.db_utils as db_utils
import laue_portal.database.db_schema as db_schema
from sqlalchemy.orm import Session
import laue_portal.components.navbar as navbar
from dash.exceptions import PreventUpdate
from sqlalchemy import asc # Import asc for ordering
from laue_portal.components.metadata_form import metadata_form, set_metadata_form_props, make_scan_accordion, set_scaninfo_form_props
import urllib.parse
import pandas as pd

dash.register_page(__name__, path="/scan") # Simplified path

layout = html.Div([
        navbar.navbar,
        dcc.Location(id='url-scan-page', refresh=False),
        html.Div(
                [
                    # Scan Info
                    html.H1(children=["Scan ID: ", html.Div(id="ScanID_print")],
                            style={"display":"flex", "gap":"10px", "align-items":"flex-end"},
                            className="mb-4"
                    ),
                    # html.H1(
                    #     html.Div(id="ScanID_print"),
                    #     className="mb-4"
                    # ),

                    dbc.Card([
                        dbc.CardHeader(
                            dbc.Row([
                                dbc.Col(html.H4("ScanLog Info", className="mb-0"), width="auto"),
                                dbc.Col(
                                    html.Div([
                                        dbc.Button("ScanLogPlot", id="scanlog-plot-btn", color="success", size="sm", className="me-2"),
                                        dbc.Button("Show more", id="show-more-btn", color="success", size="sm")
                                    ], className="d-flex justify-content-end"),
                                    width=True
                                )
                            ], align="center", justify="between"),
                            className="bg-light"
                        ),
                        dbc.CardBody([
                            
                            html.P(children=[html.Strong("User: "), html.Div(id="User_print")],
                                   style={"display":"flex", "gap":"5px", "align-items":"flex-end"}
                                   ),
                            html.P(children=[html.Strong("Date: "), html.Div(id="Date_print")],
                                   style={"display":"flex", "gap":"5px", "align-items":"flex-end"}
                                   ),
                            html.P(children=[html.Strong("Scan Type: "), html.Div(id="ScanType_print")],
                                   style={"display":"flex", "gap":"5px", "align-items":"flex-end"}
                                   ),
                            html.P(children=[html.Strong("Technique: "), html.Div(id="Technique_print")],
                                   style={"display":"flex", "gap":"5px", "align-items":"flex-end"}
                                   ),
                            html.P(children=[html.Strong("Sample: "), html.Div(id="Sample_print")],
                                   style={"display":"flex", "gap":"5px", "align-items":"flex-end"}
                                   ),
                            # html.P(html.Div(id="User_print")),
                            # html.P(html.Div(id="Date_print")),
                            # html.P(html.Div(id="ScanType_print")),
                            # html.P(html.Div(id="Technique_print")),
                            # html.P(html.Div(id="Sample_print")),

                            dbc.Row([
                                dbc.Col([
                                    html.P(html.Strong("Comment:")),
                                    dbc.Button("Add to DB", id="save-comment-btn", color="success", size="sm", className="mt-2")
                                ], width="auto", align="start"),
                                dbc.Col(
                                    dbc.Textarea(
                                        id="Comment_print",
                                        #id='scan-comment',
                                        #value=scan["comment"] or "—",
                                        style={"width": "100%", "minHeight": "100px"},
                                    )
                                )
                            ], className="mb-3", align="start")

                        ])
                    ], className="mb-4 shadow-sm border",
                    style={"width": "100%"}),

                    # Recon Table
                    dbc.Card([
                        dbc.CardHeader(
                            dbc.Row([
                                dbc.Col(html.H4("Reconstructions", className="mb-0"), width="auto"),
                                dbc.Col(
                                    html.Div([
                                        dbc.Button("New Recon+Index", id="scanlog-plot-btn", color="success", size="sm", className="me-2"),
                                        dbc.Button("New Recon", id="show-more-btn", color="success", size="sm")
                                    ], className="d-flex justify-content-end"),
                                    width=True
                                )
                            ], align="center", justify="between"),
                            className="bg-light"
                        ),
                        dbc.CardBody([
                            dag.AgGrid(
                                id='scan-recon-table',
                                columnSize="responsiveSizeToFit",
                                dashGridOptions={"pagination": True, "paginationPageSize": 20, "domLayout": 'autoHeight', "rowHeight": 32},
                                #style={'height': 'calc(100vh - 150px)', 'width': '100%'},
                                className="ag-theme-alpine"
                            )
                        ])
                    ], className="mb-4 shadow-sm border"),

                    # Peak Index Table
                    dbc.Card([
                        dbc.CardHeader(
                            dbc.Row([
                                dbc.Col(html.H4("Indexing", className="mb-0"), width="auto"),
                                dbc.Col(
                                    html.Div([
                                        dbc.Button("New Index", id="show-more-btn", color="success", size="sm")
                                    ], className="d-flex justify-content-end"),
                                    width=True
                                )
                            ], align="center", justify="between"),
                            className="bg-light"
                        ),
                        dbc.CardBody([
                            dag.AgGrid(
                                id='scan-peakindex-table',
                                columnSize="responsiveSizeToFit",
                                dashGridOptions={"pagination": True, "paginationPageSize": 20, "domLayout": 'autoHeight', "rowHeight": 32},
                                #style={'height': 'calc(100vh - 150px)', 'width': '100%'},
                                className="ag-theme-alpine"
                            )
                        ])
                    ], className="mb-4 shadow-sm border"),
                    #####
                    # dbc.Accordion(
                    #     [
                    #     dbc.AccordionItem(
                    #     # dbc.Container(id='metadata-content-container', fluid=True, className="mt-4",
                    #     #               children=[
                    #     #                     metadata_form
                    #     #         ]),
                    #         [
                    #             metadata_form
                    #         ],
                    #         title="Scan",
                    #     ),
                    #     dbc.Button("New Reconstruction", id="new-recon_button", className="me-2", n_clicks=0),
                    #     dbc.AccordionItem(
                    #         [
                    #             dash_table.DataTable(
                    #                 id='scan-recon-table',
                    #                 filter_action="native",
                    #                 sort_action="native",
                    #                 sort_mode="multi",
                    #                 page_action="native",
                    #                 page_current= 0,
                    #                 page_size= 20,
                    #             )
                    #         ],
                    #         title="Reconstructions",
                    #     ),
                    #     dbc.Button("New Indexation", id="new-peakindex_button", className="me-2", n_clicks=0),
                    #     dbc.AccordionItem(
                    #         [
                    #             dash_table.DataTable(
                    #                 id='peakindex-table',
                    #                 filter_action="native",
                    #                 sort_action="native",
                    #                 sort_mode="multi",
                    #                 page_action="native",
                    #                 page_current= 0,
                    #                 page_size= 20,
                    #             )
                    #         ],
                    #         title="Indexations",
                    #     ),
                    #     ],
                    #     always_open=True
                    # ),
                ],
            style={'width': '100%', 'overflow-x': 'auto'}
        ),
#         dbc.Modal(
#             [
#                 dbc.ModalHeader(dbc.ModalTitle("Header"), id="modal-details-header"),
#                 dbc.ModalBody(metadata_form),
#             ],
#             id="modal-details",
#             size="xl",
#             is_open=False,
#         ),
#         dbc.Modal(
#             [
#                 dbc.ModalHeader(dbc.ModalTitle("Header"), id="modal-scan-header"),
#                 dbc.ModalBody(html.H1("TODO: Scan Display")),
#                 # html.Div(children=[
                    
#                 # ])
#                 dash_table.DataTable(
#                     id='scan-table',
#                     # columns=[{"name": i, "id": i}
#                     #         for i in df.columns],
#                     # data=df.to_dict('records'),
#                     style_cell=dict(textAlign='left'),
#                     #style_header=dict(backgroundColor="paleturquoise"),
#                     #style_data=dict(backgroundColor="lavender")
#             )
#             ],
#             id="modal-scan",
#             size="xl",
#             is_open=False,
#         ),
    ],
)

"""
=======================
Scan Info
=======================
"""

# VISIBLE_COLS_Metadata = [
#     db_schema.Metadata.scanNumber,
    
#     db_schema.Metadata.date,
#     db_schema.Metadata.calib_id,
#     db_schema.Metadata.dataset_id,
#     db_schema.Metadata.notes,
# ]

# VISIBLE_COLS_Scan = [
#     db_schema.Scan.scanNumber,

#     db_schema.Scan.scan_dim,
#     db_schema.Scan.scan_npts,
#     db_schema.Scan.scan_after,
#     db_schema.Scan.scan_positioner1_PV,
#     db_schema.Scan.scan_positioner1_ar,
#     db_schema.Scan.scan_positioner1_mode,
#     db_schema.Scan.scan_positioner1,
#     db_schema.Scan.scan_positioner2_PV,
#     db_schema.Scan.scan_positioner2_ar,
#     db_schema.Scan.scan_positioner2_mode,
#     db_schema.Scan.scan_positioner2,
#     db_schema.Scan.scan_positioner3_PV,
#     db_schema.Scan.scan_positioner3_ar,
#     db_schema.Scan.scan_positioner3_mode,
#     db_schema.Scan.scan_positioner3,
#     db_schema.Scan.scan_positioner4_PV,
#     db_schema.Scan.scan_positioner4_ar,
#     db_schema.Scan.scan_positioner4_mode,
#     db_schema.Scan.scan_positioner4,
#     db_schema.Scan.scan_detectorTrig1_PV,
#     db_schema.Scan.scan_detectorTrig1_VAL,
#     db_schema.Scan.scan_detectorTrig2_PV,
#     db_schema.Scan.scan_detectorTrig2_VAL,
#     db_schema.Scan.scan_detectorTrig3_PV,
#     db_schema.Scan.scan_detectorTrig3_VAL,
#     db_schema.Scan.scan_detectorTrig4_PV,
#     db_schema.Scan.scan_detectorTrig4_VAL,
#     db_schema.Scan.scan_cpt,
# ]

@callback(
    Input('url-scan-page', 'href'),
    prevent_initial_call=True
)
def load_scan_metadata(href):
    if not href:
        raise PreventUpdate

    parsed_url = urllib.parse.urlparse(href)
    query_params = urllib.parse.parse_qs(parsed_url.query)
    
    scan_id = query_params.get('id', [None])[0]

    if scan_id:
        try:
            scan_id = int(scan_id)
            with Session(db_utils.ENGINE) as session:
                metadata = session.query(db_schema.Metadata).filter(db_schema.Metadata.scanNumber == scan_id).first()
                scans = session.query(db_schema.Scan).filter(db_schema.Scan.scanNumber == scan_id)
                catalog = session.query(db_schema.Catalog).filter(db_schema.Catalog.scanNumber == scan_id).first()
                if metadata:
                    scan_accordions = [make_scan_accordion(i) for i,_ in enumerate(scans)]
                    set_props("scan_accordions", {'children': scan_accordions})
                    set_metadata_form_props(metadata, scans, read_only=True)
                    set_scaninfo_form_props(metadata, scans, catalog, read_only=True)
        except Exception as e:
            print(f"Error loading scan data: {e}")


# def _get_metadatas():
#     with Session(db_utils.ENGINE) as session:
#         metadatas = pd.read_sql(session.query(*VISIBLE_COLS_Metadata).statement, session.bind)

#     cols = [{'name': str(col), 'id': str(col)} for col in metadatas.columns]
#     cols.append({'name': 'Parameters', 'id': 'Parameters', 'presentation': 'markdown'})
#     cols.append({'name': 'Measurement Info', 'id': 'Measurement Info', 'presentation': 'markdown'})

#     metadatas['id'] = metadatas['scanNumber']

#     metadatas['Parameters'] = '**Parameters**'
#     metadatas['Measurement Info'] = '**Measurement Info**'
    
#     return cols, metadatas.to_dict('records')



# @dash.callback(
#     Output('metadata-table', 'columns', allow_duplicate=True),
#     Output('metadata-table', 'data', allow_duplicate=True),
#     Input('upload-metadata-log', 'contents'),
#     prevent_initial_call=True,
# )
# def upload_log(contents):
#     try:
#         content_type, content_string = contents.split(',')
#         decoded = base64.b64decode(content_string)
#         log, scan = db_utils.parse_metadata(decoded) #yaml.safe_load(decoded)
#         metadata_row = db_utils.import_metadata_row(log)
#         scan_cards = []; scan_rows = []
#         for i,scan in enumerate(scan):
#             scan_cards.append(ui_shared.make_scan_card(i))
#             scan_rows.append(db_utils.import_scan_row(scan))
#         set_props("scan_cards", {'children': scan_cards})
        
#         metadata_row.date = datetime.datetime.now()
#         metadata_row.commit_id = ''
#         metadata_row.calib_id = ''
#         metadata_row.runtime = ''
#         metadata_row.computer_name = ''
#         metadata_row.dataset_id = 0
#         metadata_row.notes = ''

#         with Session(db_utils.ENGINE) as session:
#             session.add(metadata_row)
#             session.commit()
#             for scan_row in scan_rows:
#                 session.add(scan_row)
#                 session.commit()

#     except Exception as e:
#         print('Unable to parse log')
#         print(e)
    
#     cols, metadatas = _get_metadatas()
#     return cols, metadatas






# @dash.callback(
#     Output('metadata-table', 'columns', allow_duplicate=True),
#     Output('metadata-table', 'data', allow_duplicate=True),
#     Input('url-scan-page', 'pathname'),
#     prevent_initial_call=True,
# )
# def get_metadatas(path):
#     if 'scan' in path: #if path == '/':
#         cols, metadatas = _get_metadatas()
#         return cols, metadatas
#     else:
#         raise PreventUpdate


# @dash.callback(
#     Input("metadata-table", "active_cell"),
# )
# def cell_clicked(active_cell):
#     if active_cell is None:
#         return dash.no_update

#     print(active_cell)
#     row = active_cell["row"]
#     row_id = active_cell["row_id"]
#     col = active_cell["column"]

#     if col == 5:
#         with Session(db_utils.ENGINE) as session:
#             metadata = session.query(db_schema.Metadata).filter(db_schema.Metadata.scanNumber == row_id).first()
#             scan = session.query(db_schema.Scan).filter(db_schema.Scan.scanNumber == row_id)

#         set_props("modal-details", {'is_open':True})
#         set_props("modal-details-header", {'children':dbc.ModalTitle(f"Details for Peak Index {row_id} (Read Only)")})
        
#         set_metadata_form_props(metadata, scan, read_only=True)


    
#     elif col == 6:
#         with Session(db_utils.ENGINE) as session:
#             df = pd.read_sql(session.query(*VISIBLE_COLS_Scan).filter(db_schema.Scan.scanNumber == row_id).statement, session.bind)

#         set_props("modal-scan", {'is_open':True})
#         set_props("modal-scan-header", {'children':dbc.ModalTitle(f"Scan for {row_id}")})

#         set_props("scan-table",
#                     {
#                         'columns':[{"name": i, "id": i} for i in df.columns],
#                         'data':df.to_dict('records'),
#                     }
#         )

#     print(f"Row {row} and Column {col} was clicked")


# @dash.callback(
#     Output("example-output", "children"), [Input("new-recon_button", "n_clicks")]
# )
# def on_button_click(n):
#     if n is None:
#         return "Not clicked."
#     else:
#         return f"Clicked {n} times."


# @dash.callback(
#     Output("example-output2", "children"), [Input("new-peakindex_button", "n_clicks")]
# )
# def on_button_click(n):
#     if n is None:
#         return "Not clicked."
#     else:
#         return f"Clicked {n} times."

"""
=======================
Recon Table
=======================
"""

# VISIBLE_COLS_Recon = [
#     db_schema.Recon.recon_id,
#     db_schema.Recon.date,
#     db_schema.Recon.calib_id,
#     # db_schema.Recon.dataset_id,
#     db_schema.Recon.scanNumber,
#     db_schema.Recon.notes,
# ]

# CUSTOM_HEADER_NAMES_Recon = {
#     'recon_id': 'Recon ID',
#     'scanNumber': 'Scan ID',
#     #'dataset_id': 'Scan ID',
# }

VISIBLE_COLS_Recon = [
    db_schema.Recon.recon_id,
    db_schema.Recon.author,
    db_schema.Recon.notes,
    #db_schema.Recon.pxl_recon,
    db_schema.Job.submit_time,
    db_schema.Job.start_time,
    db_schema.Job.finish_time,
    db_schema.Job.status,
]

CUSTOM_HEADER_NAMES_Recon = {
    'recon_id': 'Recon ID', #'ReconID',
    #'pxl_recon': 'Pixels'
    'submit_time': 'Date',
}

CUSTOM_COLS_Recon_dict = {
    1:[
        db_schema.Catalog.aperture, #db_schema.Recon.depth_technique, #presently does not exist
        db_schema.Recon.calib_id, #Calib.calib_id,
    ],
    2:[#db_schema.Recon
        #db_schema.PeakIndex.scanPointStart,
        #db_schema.PeakIndex.scanPointEnd,
        #db_schema.PeakIndex.filefolder,
    ],
    3:[
        db_schema.Recon.geo_source_offset,
        db_schema.Recon.geo_source_grid,
    ],
    4:[
        db_schema.Job.computer_name, #placeholder item
    ],
}

ALL_COLS_Recon = VISIBLE_COLS_Recon + [ii for i in CUSTOM_COLS_Recon_dict.values() for ii in i]

VISIBLE_COLS_WireRecon = [
    db_schema.WireRecon.wirerecon_id,
    db_schema.WireRecon.author,
    db_schema.WireRecon.notes,
    #db_schema.WireRecon.pxl_recon,
    db_schema.Job.submit_time,
    db_schema.Job.start_time,
    db_schema.Job.finish_time,
    db_schema.Job.status,
]

CUSTOM_HEADER_NAMES_WireRecon = {
    'wirerecon_id': 'Recon ID (Wire)', #'Wire Recon ID',
    #'pxl_recon': 'Pixels'
    'submit_time': 'Date',
}

CUSTOM_COLS_WireRecon_dict = {
    1:[
        db_schema.Catalog.aperture, #db_schema.Recon.depth_technique, #presently does not exist
        # db_schema.WireRecon.calib_id, #Calib.calib_id,
    ],
    2:[#db_schema.Recon
        #db_schema.PeakIndex.scanPointStart,
        #db_schema.PeakIndex.scanPointEnd,
        #db_schema.PeakIndex.filefolder,
    ],
    3:[
        # db_schema.Recon.geo_source_offset,
        # db_schema.Recon.geo_source_grid,
        db_schema.WireRecon.depth_start,
        db_schema.WireRecon.depth_end,
        db_schema.WireRecon.depth_resolution,
    ],
    4:[
        db_schema.Job.computer_name, #placeholder item
    ],
}

ALL_COLS_WireRecon = VISIBLE_COLS_WireRecon + [ii for i in CUSTOM_COLS_WireRecon_dict.values() for ii in i]

def _get_scan_recons(scan_id):
    try:
        scan_id = int(scan_id)
        with Session(db_utils.ENGINE) as session:
            aperture = pd.read_sql(session.query(db_schema.Catalog.aperture).filter(db_schema.Catalog.scanNumber == scan_id).statement, session.bind).at[0,'aperture']
            if 'wire' in aperture:
                scan_recons = pd.read_sql(session.query(*ALL_COLS_WireRecon)
                                .join(db_schema.Metadata.catalog_)
                                .join(db_schema.Metadata.wirerecon_)
                                # .join(db_schema.Catalog, db_schema.Metadata.scanNumber == db_schema.Catalog.scanNumber)
                                # .join(db_schema.WireRecon, db_schema.Metadata.scanNumber == db_schema.WireRecon.scanNumber)
                                .join(db_schema.Job, db_schema.WireRecon.job_id == db_schema.Job.job_id)
                                .filter(db_schema.Metadata.scanNumber == scan_id).statement, session.bind)
                
                # Format columns for ag-grid
                cols = []
                for col in VISIBLE_COLS_WireRecon:
                    field_key = col.key
                    header_name = CUSTOM_HEADER_NAMES_WireRecon.get(field_key, field_key.replace('_', ' ').title())
                    
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
                    elif field_key in ['scanNumber','dataset_id']:
                        col_def['cellRenderer'] = 'DatasetIdScanLinkRenderer'
                    elif field_key == 'scanNumber':
                        col_def['cellRenderer'] = 'ScanLinkRenderer'  # Use the custom JS renderer
                    elif field_key in ['submit_time', 'start_time', 'finish_time']:
                        col_def['cellRenderer'] = 'DateFormatter'  # Use the date formatter for datetime fields
                    elif field_key == 'status':
                        col_def['cellRenderer'] = 'StatusRenderer'  # Use custom status renderer
                    
                    cols.append(col_def)

                # # Add the custom actions column
                # cols.append({
                #     'headerName': 'Actions',
                #     'field': 'actions',  # This field doesn't need to exist in the data
                #     'cellRenderer': 'ActionButtonsRenderer',
                #     'sortable': False,
                #     'filter': False,
                #     'resizable': True, # Or False, depending on preference
                #     'suppressMenu': True, # Or False
                #     'width': 200 # Adjusted width for DBC buttons
                # })

                # Add combined fields columns
                for col_num in CUSTOM_COLS_WireRecon_dict.keys():
                    if col_num == 1:
                        col_def = {
                            'headerName': 'Calib ID',
                            'valueGetter': {"function":
                                "params.data.aperture + ': ' + params.data.calib_id"
                            },
                        }
                    elif col_num == 2:
                        col_def = {
                            'headerName': 'Points', #'points_to_index'
                            'valueGetter': {"function":
                                "50 + ' / ' + '2000'"
                                #"50*(params.data.scanPointEnd - params.data.scanPointStart) + ' / ' + '2000'"
                                # "f'{params.data.scanPointEnd - params.data.scanPointStart} out of 2000'", #len(Path(db_schema.PeakIndex.filefolder).glob("*"))
                            },
                        }
                    elif col_num == 3:
                        col_def = {
                            'headerName': 'Depth [µm]', # 'Depth [${\mu}m$]',
                            'valueGetter': {"function":
                                "params.data.depth_start \
                                + ' to ' + \
                                params.data.depth_end"
                            },
                        }
                    elif col_num == 4:
                        col_def = {
                            'headerName': 'Pixels',
                            'valueGetter': {"function":
                                "100" # "params.data.Recon.pxl_recon"
                            },
                        }
                    col_def.update({
                        'filter': True, 
                        'sortable': True, 
                        'resizable': True,
                        'suppressMenuHide': True
                    })
                    cols.insert(col_num,col_def)

                # recons['id'] = recons['scanNumber'] # This was for dash_table and is not directly used by ag-grid unless getRowId is configured
                
                return cols, scan_recons.to_dict('records')
            else:
                scan_recons = pd.read_sql(session.query(*ALL_COLS_Recon)
                                .join(db_schema.Metadata.catalog_)
                                .join(db_schema.Metadata.recon_)
                                # .join(db_schema.Catalog, db_schema.Metadata.scanNumber == db_schema.Catalog.scanNumber)
                                # .join(db_schema.Recon, db_schema.Metadata.scanNumber == db_schema.Recon.scanNumber)
                                .join(db_schema.Job, db_schema.Recon.job_id == db_schema.Job.job_id)
                                .filter(db_schema.Metadata.scanNumber == scan_id).statement, session.bind)
                # Format columns for ag-grid
                cols = []
                for col in VISIBLE_COLS_Recon:
                    field_key = col.key
                    header_name = CUSTOM_HEADER_NAMES_Recon.get(field_key, field_key.replace('_', ' ').title())
                    
                    col_def = {
                        'headerName': header_name,
                        'field': field_key,
                        'filter': True, 
                        'sortable': True, 
                        'resizable': True,
                        'suppressMenuHide': True
                    }

                    if field_key == 'recon_id':
                        col_def['cellRenderer'] = 'ReconLinkRenderer'
                    elif field_key in ['scanNumber','dataset_id']:
                        col_def['cellRenderer'] = 'DatasetIdScanLinkRenderer'
                    elif field_key == 'scanNumber':
                        col_def['cellRenderer'] = 'ScanLinkRenderer'  # Use the custom JS renderer
                    elif field_key in ['submit_time', 'start_time', 'finish_time']:
                        col_def['cellRenderer'] = 'DateFormatter'  # Use the date formatter for datetime fields
                    elif field_key == 'status':
                        col_def['cellRenderer'] = 'StatusRenderer'  # Use custom status renderer
                    
                    cols.append(col_def)

                # # Add the custom actions column
                # cols.append({
                #     'headerName': 'Actions',
                #     'field': 'actions',  # This field doesn't need to exist in the data
                #     'cellRenderer': 'ActionButtonsRenderer',
                #     'sortable': False,
                #     'filter': False,
                #     'resizable': True, # Or False, depending on preference
                #     'suppressMenu': True, # Or False
                #     'width': 200 # Adjusted width for DBC buttons
                # })

                # Add a combined fields columns
                for col_num in CUSTOM_COLS_Recon_dict.keys():
                    if col_num == 2:
                        col_def = {
                            'headerName': 'Method',
                            'valueGetter': {"function":
                                "params.data.aperture + ', calib: ' + params.data.calib_id" # "'CA, calib: ' + params.data.calib_id"
                            },
                        }
                    elif col_num == 3:
                        col_def = {
                            'headerName': 'Points', #'points_to_index'
                            'valueGetter': {"function":
                                "50 + ' / ' + '2000'"
                                #"50*(params.data.scanPointEnd - params.data.scanPointStart) + ' / ' + '2000'"
                                # "f'{params.data.scanPointEnd - params.data.scanPointStart} out of 2000'", #len(Path(db_schema.PeakIndex.filefolder).glob("*"))
                            },
                        }
                    elif col_num == 4:
                        col_def = {
                            'headerName': 'Depth [µm]', # 'Depth [${\mu}m$]',
                            'valueGetter': {"function":
                                "1000*(params.data.geo_source_grid[0] + params.data.geo_source_offset) \
                                + ' to ' + \
                                1000*(params.data.geo_source_grid[1] + params.data.geo_source_offset)"
                            },
                        }
                    elif col_num == 5:
                        col_def = {
                            'headerName': 'Pixels',
                            'valueGetter': {"function":
                                "100" # "params.data.Recon.pxl_recon"
                            },
                        }
                    col_def.update({
                        'filter': True, 
                        'sortable': True, 
                        'resizable': True,
                        'suppressMenuHide': True
                    })
                    cols.insert(col_num,col_def)

                # recons['id'] = recons['scanNumber'] # This was for dash_table and is not directly used by ag-grid unless getRowId is configured
                
                return cols, scan_recons.to_dict('records')
    
    except Exception as e:
        print(f"Error loading reconstruction data: {e}")


@callback(
    Output('scan-recon-table', 'columnDefs'),
    Output('scan-recon-table', 'rowData'),
    Input('url-scan-page', 'href'),
    prevent_initial_call=True,
)
def get_scan_recons(href):
    if not href:
        raise PreventUpdate

    parsed_url = urllib.parse.urlparse(href)
    path = parsed_url.path
    
    if path == '/scan':
        query_params = urllib.parse.parse_qs(parsed_url.query)
        scan_id = query_params.get('id', [None])[0]

        if scan_id:
            cols, recons = _get_scan_recons(scan_id)
            return cols, recons
    else:
        raise PreventUpdate

"""
=======================
Peak Index Table
=======================
"""

# VISIBLE_COLS_PeakIndex = [
#     db_schema.PeakIndex.peakindex_id,
#     db_schema.PeakIndex.date,
#     db_schema.PeakIndex.calib_id,
#     # db_schema.PeakIndex.dataset_id,
#     db_schema.PeakIndex.scanNumber,
#     db_schema.PeakIndex.notes,
# ]

# CUSTOM_HEADER_NAMES_PeakIndex = {
#     'peakindex_id': 'PeakIndex ID',
#     'scanNumber': 'Scan ID',
#     # 'dataset_id': 'Scan ID',
# }

VISIBLE_COLS_PeakIndex = [
    db_schema.PeakIndex.peakindex_id,
    db_schema.PeakIndex.recon_id,
    db_schema.PeakIndex.author,
    db_schema.PeakIndex.notes,
    db_schema.PeakIndex.boxsize,
    db_schema.PeakIndex.threshold,
    # db_schema.PeakIndexResults.structure,
    db_schema.Job.submit_time,
    db_schema.Job.start_time,
    db_schema.Job.finish_time,
    db_schema.Job.status,
]

CUSTOM_HEADER_NAMES_PeakIndex = {
    'peakindex_id': 'Index ID', #'Peak Index ID',
    'recon_id': 'Recon ID', #'ReconID',
    'wirerecon_id': 'Recon ID (Wire)', #'Wire Recon ID',
    #'': 'Points',
    'boxsize': 'Box',
    'submit_time': 'Date',
}

CUSTOM_COLS_PeakIndex_dict = {
    4:[
        db_schema.PeakIndex.scanPointEnd,
        db_schema.PeakIndex.scanPointStart,
        db_schema.PeakIndex.filefolder,
    ],
}

ALL_COLS_PeakIndex = VISIBLE_COLS_PeakIndex + [ii for i in CUSTOM_COLS_PeakIndex_dict.values() for ii in i]

def _get_scan_peakindexs(scan_id):
    try:
        scan_id = int(scan_id)
        with Session(db_utils.ENGINE) as session:
            aperture = pd.read_sql(session.query(db_schema.Catalog.aperture).filter(db_schema.Catalog.scanNumber == scan_id).statement, session.bind).at[0,'aperture']
            if 'wire' in aperture:
                VISIBLE_COLS_PeakIndex[1] = db_schema.PeakIndex.wirerecon_id
                ALL_COLS_PeakIndex = VISIBLE_COLS_PeakIndex + [ii for i in CUSTOM_COLS_PeakIndex_dict.values() for ii in i]
            scan_peakindexs = pd.read_sql(session.query(*ALL_COLS_PeakIndex)
                            .join(db_schema.Metadata.peakindex_)
                            # .join(db_schema.PeakIndex.peakindexresults_)
                            # .join(db_schema.PeakIndex, db_schema.Metadata.scanNumber == db_schema.PeakIndex.scanNumber)
                            # .join(db_schema.PeakIndexResults, db_schema.PeakIndex.scanNumber == db_schema.PeakIndexResults.scanNumber)
                            .join(db_schema.Job, db_schema.PeakIndex.job_id == db_schema.Job.job_id)
                            .filter(db_schema.Metadata.scanNumber == scan_id).statement, session.bind)
            # Format columns for ag-grid
            cols = []
            for col in VISIBLE_COLS_PeakIndex:
                field_key = col.key
                header_name = CUSTOM_HEADER_NAMES_PeakIndex.get(field_key, field_key.replace('_', ' ').title())
                
                col_def = {
                    'headerName': header_name,
                    'field': field_key,
                    'filter': True, 
                    'sortable': True, 
                    'resizable': True,
                    'suppressMenuHide': True
                }

                if field_key == 'peakindex_id':
                    col_def['cellRenderer'] = 'PeakIndexLinkRenderer'
                elif field_key == 'recon_id':
                    col_def['cellRenderer'] = 'ReconLinkRenderer'
                elif field_key == 'wirerecon_id':
                    col_def['cellRenderer'] = 'WireReconLinkRenderer'
                elif field_key in ['scanNumber','dataset_id']:
                    col_def['cellRenderer'] = 'DatasetIdScanLinkRenderer'
                elif field_key == 'scanNumber':
                    col_def['cellRenderer'] = 'ScanLinkRenderer'  # Use the custom JS renderer
                elif field_key in ['submit_time', 'start_time', 'finish_time']:
                    col_def['cellRenderer'] = 'DateFormatter'  # Use the date formatter for datetime fields
                elif field_key == 'status':
                    col_def['cellRenderer'] = 'StatusRenderer'  # Use custom status renderer
                
                cols.append(col_def)

            # # Add the custom actions column
            # cols.append({
            #     'headerName': 'Actions',
            #     'field': 'actions',  # This field doesn't need to exist in the data
            #     'cellRenderer': 'ActionButtonsRenderer',
            #     'sortable': False,
            #     'filter': False,
            #     'resizable': True, # Or False, depending on preference
            #     'suppressMenu': True, # Or False
            #     'width': 200 # Adjusted width for DBC buttons
            # })

            # Add a combined fields columns
            for col_num in CUSTOM_COLS_PeakIndex_dict.keys():
                if col_num == 4:
                    col_def = {
                        'headerName': 'Points', #'points_to_index'
                        'valueGetter': {"function":
                            "50*(params.data.scanPointEnd - params.data.scanPointStart) + ' / ' + '2000'"
                            # "f'{params.data.scanPointEnd - params.data.scanPointStart} out of 2000'", #len(Path(db_schema.PeakIndex.filefolder).glob("*"))
                        },
                    }
                col_def.update({
                    'filter': True, 
                    'sortable': True, 
                    'resizable': True,
                    'suppressMenuHide': True
                })
                cols.insert(col_num,col_def)

            # peakindexs['id'] = peakindexs['scanNumber'] # This was for dash_table and is not directly used by ag-grid unless getRowId is configured
            
            return cols, scan_peakindexs.to_dict('records')
    
    except Exception as e:
        print(f"Error loading peak index data: {e}")


@callback(
    Output('scan-peakindex-table', 'columnDefs'),
    Output('scan-peakindex-table', 'rowData'),
    Input('url-scan-page', 'href'),
    prevent_initial_call=True,
)
def get_scan_peakindexs(href):
    if not href:
        raise PreventUpdate

    parsed_url = urllib.parse.urlparse(href)
    path = parsed_url.path
    
    if path == '/scan':
        query_params = urllib.parse.parse_qs(parsed_url.query)
        scan_id = query_params.get('id', [None])[0]

        if scan_id:
            cols, peakindexs = _get_scan_peakindexs(scan_id)
            return cols, peakindexs
    else:
        raise PreventUpdate
