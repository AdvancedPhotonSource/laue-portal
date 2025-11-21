import dash
from dash import html, dcc, callback, Input, Output, State, set_props
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
import laue_portal.database.db_utils as db_utils
from laue_portal.database import db_utils, db_schema
from sqlalchemy.orm import Session
import laue_portal.components.navbar as navbar
from dash.exceptions import PreventUpdate
from sqlalchemy import func # Import func for aggregation
from laue_portal.components.metadata_form import metadata_form, set_metadata_form_props, set_scan_accordions
from laue_portal.components.catalog_form import catalog_form, set_catalog_form_props
from laue_portal.components.form_base import _stack, _field
import urllib.parse
import pandas as pd
from datetime import datetime
import laue_portal.database.session_utils as session_utils

dash.register_page(__name__, path="/scan") # Simplified path

layout = html.Div([
        navbar.navbar,
        dcc.Location(id='url-scan-page', refresh=False),
        dbc.Container(id='scan-content-container', fluid=True, className="mt-4",
                  children=[
                        dbc.Alert(
                            id="alert-note-submit",
                            dismissable=True,
                            duration=4000,
                            is_open=False,
                        ),
                        html.H1(id='scan-header', 
                               style={"display":"flex", "gap":"10px", "align-items":"baseline", "flexWrap":"wrap"},
                               className="mb-4"),
                        html.Div(
                            [
                    # html.H1(
                    #     html.Div(id="ScanID_print"),
                    #     className="mb-4"
                    # ),

                    dbc.Card([
                        dbc.CardHeader(
                            dbc.Row([
                                dbc.Col(html.H4("Scan Info", className="mb-0"), width="auto"),
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
                            dbc.Row([
                                dbc.Col([
                                    html.P(children=[html.Strong("User: "), html.Div(id="User_print")],
                                           style={"display":"flex", "gap":"5px", "align-items":"flex-end"}),
                                    html.P(children=[html.Strong("Date: "), html.Div(id="Date_print")],
                                           style={"display":"flex", "gap":"5px", "align-items":"flex-end"}),
                                    html.P(children=[html.Strong("Scan Dimensions: "), html.Div(id="ScanDims_print")],
                                           style={"display":"flex", "gap":"5px", "align-items":"flex-end"}),
                                    html.P(children=[html.Strong("Technique: "), html.Div(id="Technique_print")],
                                           style={"display":"flex", "gap":"5px", "align-items":"flex-end"}),
                                    dbc.Row(id='scan-totals-row', className="mt-3"),
                                    html.P(children=[html.Strong("Aperture: "), html.Div(id="Aperture_print")],
                                           style={"display":"flex", "gap":"5px", "align-items":"flex-end"}),
                                    html.P(children=[html.Strong("Sample: "), html.Div(id="Sample_print")],
                                           style={"display":"flex", "gap":"5px", "align-items":"flex-end"}),
                                ], width=6),
                                dbc.Col(id='positioner-info-div', width=6),
                            ]),
                            dbc.Row([
                                dbc.Col([
                                    html.P(html.Strong("Note:")),
                                    dbc.Button("Add to DB", id="save-note-btn", color="success", size="sm", className="mt-2")
                                ], width="auto", align="start"),
                                dbc.Col(
                                    dbc.Textarea(
                                        id="Note_print",
                                        #id='scan-note',
                                        #value=scan["note"] or "—",
                                        style={"width": "100%", "minHeight": "100px"},
                                    )
                                )
                            ], className="mb-3", align="start")
                        ])
                    ], className="mb-4 shadow-sm border",
                    style={"width": "100%"}),

                    html.Div([
                        dbc.Button("New Recon", id="new-recon-btn", color="success", size="sm", className="ms-2", href="/create-reconstruction"),
                        dbc.Button("New Index", id="new-index-btn", color="success", size="sm", className="ms-2", href="/create-peakindexing"),
                        dbc.Button("New Recon+Index", id="new-recon-index-btn", color="success", size="sm", className="ms-2", href="/create-reconstruction-peakindexing"),
                    ], className="d-flex justify-content-start mb-2"),

                    # Recon Table
                    dbc.Card([
                        dbc.CardHeader(
                            dbc.Row([
                                dbc.Col(html.H4("Reconstructions", className="mb-0"), width="auto"),
                                dbc.Col(
                                    html.Div([
                                        dbc.Button("New Recon", id="recon-table-new-recon-btn", color="success", size="sm", className="me-2", href="/create-reconstruction"),
                                        dbc.Button("New Index", id="recon-table-new-index-btn", color="success", size="sm", className="me-2", href="/create-peakindexing"),
                                        dbc.Button("New Recon+Index", id="recon-table-new-recon-index-btn", color="success", size="sm", className="me-2", href="/create-reconstruction-peakindexing"),
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
                                #style={'height': 'calc(100vh - 150px)', 'width': '100%'},
                                className="ag-theme-alpine"
                            )
                        ])
                    ], className="mb-4 shadow-sm border"),

                    # Peak Indexing Table
                    dbc.Card([
                        dbc.CardHeader(
                            dbc.Row([
                                dbc.Col(html.H4("Peak Indexing", className="mb-0"), width="auto"),
                                dbc.Col(
                                    html.Div([
                                        dbc.Button("New Recon", id="index-table-new-recon-btn", color="success", size="sm", className="me-2", href="/create-reconstruction"),
                                        dbc.Button("New Index", id="index-table-new-index-btn", color="success", size="sm", className="me-2", href="/create-peakindexing"),
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
                                #style={'height': 'calc(100vh - 150px)', 'width': '100%'},
                                className="ag-theme-alpine"
                            )
                        ])
                    ], className="mb-4 shadow-sm border"),

                    # Metadata Form
                    html.H2("Metadata Details", className="mt-4 mb-3"),
                    metadata_form,

                    # Catalog Form
                    html.Div(
                        [
                            html.H2("Catalog Details", className="mt-4 mb-3"),
                            dbc.Button(
                                "Save Changes to Catalog",
                                id="save-catalog-btn",
                                color="success",
                                className="mt-4 mb-3",
                                style={'margin-left': '30px'}
                            ),
                        ],
                        style={"display": "flex", "align-items": "center"},
                    ),
                    dbc.Alert(
                        id="alert-catalog-submit",
                        dismissable=True,
                        duration=4000,
                        is_open=False,
                    ),
                    catalog_form,
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
                    #     dbc.Button("New Peak Indexing", id="new-peakindexing_button", className="me-2", n_clicks=0),
                    #     dbc.AccordionItem(
                    #         [
                    #             dash_table.DataTable(
                    #                 id='scan-peakindex-table',
                    #                 filter_action="native",
                    #                 sort_action="native",
                    #                 sort_mode="multi",
                    #                 page_action="native",
                    #                 page_current= 0,
                    #                 page_size= 20,
                    #             )
                    #         ],
                    #         title="Peak Indexings",
                    #     ),
                    #     ],
                    #     always_open=True
                    # ),
                            ],
                            style={'width': '100%', 'overflow-x': 'auto'}
                        ),
                  ]),
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

def build_technique_strings(scans, none="none"):
    """
    Build both filtered and all motor strings from scans.
    
    Returns a tuple of (filtered_str, all_motors_str)
    
    Rules for filtered string:
    - Do not include the same string value twice
    - Do not include any that are "none" unless all motor strings are "none"
    - If there is only one string equal to "sample" include the string "line" instead
    - If there are more than one strings equal to "sample" include the string "area" instead
    """
    # Extract motor groups from all scans
    motor_groups = []
    for scan in scans:
        # Dynamically check all scan_positioner*_PV attributes
        for attr_name in dir(scan):
            if attr_name.startswith('scan_positioner') and attr_name.endswith('_PV'):
                pv_value = getattr(scan, attr_name, None)
                if pv_value:
                    motor_group = db_utils.find_motor_group(pv_value)
                    motor_groups.append(motor_group)
    
    # Create all_motors_str - join all motor groups with "; "
    all_motors_str = "; ".join(motor_groups) if motor_groups else none
    
    # Build filtered string
    if not motor_groups:
        return none, all_motors_str
    
    # Convert to lowercase
    motor_groups_lower = [g.lower() for g in motor_groups]
    
    # Count "sample" occurrences before deduplication
    sample_count = motor_groups_lower.count("sample")
    
    # Build final list with deduplication using a set
    # Initialize with none so it gets skipped automatically
    seen_groups = {none} #"none"
    final_groups = []
    
    for group in motor_groups_lower:
        if group not in seen_groups:
            seen_groups.add(group)
            
            if group == "sample":
                if sample_count == 1:
                    final_groups.append("line")
                elif sample_count > 1:
                    final_groups.append("area")
            else:
                final_groups.append(group)
    
    filtered_str = " + ".join(final_groups) if final_groups else none
    
    return filtered_str, all_motors_str


def set_scaninfo_form_props(metadata, scans, catalog, read_only=True):
    set_props('ScanID_print', {'children':[metadata.scanNumber]})
    set_props('User_print', {'children':[metadata.user_name]})
    # Format datetime for display
    time_value = metadata.time
    if isinstance(time_value, datetime):
        time_value = time_value.strftime('%Y-%m-%d, %H:%M:%S')
    set_props('Date_print', {'children':[time_value]})
    set_props('ScanDims_print', {'children':[f"{len([i for i,scan in enumerate(scans)])}D"]})
    
    # Construct Technique_print using the new function
    filtered_str, all_motors_str = build_technique_strings(scans)
    
    # Combine filtered string and all_motors_str
    technique_str = f"{filtered_str} ({all_motors_str})"
    
    set_props('Technique_print', {'children':[technique_str]}) #depth
    set_props('Aperture_print', {'children':[catalog.aperture.title()]})
    set_props('Sample_print', {'children':[catalog.sample_name]}) #"Si"
    set_props('Note_print', {'value':"submit indexing"})

    npts_label = "Points"
    cpt_label = "Completed"
    positioner_info = []
    motor_group_totals = {}
    if scans:
        for i, scan in enumerate(scans):
            motor_group_totals = db_utils.update_motor_group_totals(motor_group_totals, scan)
            pos_fields = []
            for PV_i in range(1, 5):
                pv_attr = f'scan_positioner{PV_i}_PV'
                pos_attr = f'scan_positioner{PV_i}'
                if getattr(scan, pv_attr, None):
                    motor_group = db_utils.find_motor_group(getattr(scan, pv_attr))
                    
                    label = html.Div(f"{motor_group.capitalize()}:")
                    
                    start_val, stop_val, step_val = getattr(scan, pos_attr, '  ').split()

                    fields = [
                        _field("Start", {"type": "pos_start", "index": i, "PV": PV_i}, size='sm', kwargs={'value': start_val, 'readonly': read_only}),
                        _field("Stop", {"type": "pos_stop", "index": i, "PV": PV_i}, size='sm', kwargs={'value': stop_val, 'readonly': read_only}),
                        _field("Step", {"type": "pos_step", "index": i, "PV": PV_i}, size='sm', kwargs={'value': step_val, 'readonly': read_only}),
                    ]
                    
                    pos_fields.append(html.Div([label, _stack(fields)], style={'margin-bottom': '10px'}))

            if pos_fields:
                points_fields = _stack([
                    _field(npts_label, {"type": "points", "index": i}, size='sm', kwargs={'value': scan.scan_npts, 'readonly': read_only}),
                    _field(cpt_label, {"type": "completed", "index": i}, size='sm', kwargs={'value': scan.scan_cpt, 'readonly': read_only})
                ])

                header = _stack([
                    html.Strong(f"Scan {scan.scan_dim} Positioners", className="mb-3"),
                    points_fields
                ])
                
                positioner_info.append(html.Div([header, html.Div(pos_fields)]))

    total_points_fields = []
    for motor_group in db_utils.MOTOR_GROUPS:
        db_points = getattr(metadata, f'motorGroup_{motor_group}_npts_total', None)
        db_completed = getattr(metadata, f'motorGroup_{motor_group}_cpt_total', None)
        
        if db_points is not None:
            total_points_fields.append(
                _stack([#dbc.Col
                    html.P(children=[html.Strong(f"{motor_group.capitalize()} {npts_label}: "), html.Div(db_points)],
                           style={"display":"flex", "gap":"5px", "align-items":"flex-end"}),
                    html.Span("|", className="mb-3"),
                    html.P(children=[html.Strong(f"{motor_group.capitalize()} {cpt_label}: "), html.Div(db_completed)],
                             style={"display":"flex", "gap":"5px", "align-items":"flex-end"})
                ])#, width=6)
            )
            
            # Check for mismatch
            if motor_group in motor_group_totals:
                if (motor_group_totals[motor_group]['points'] != db_points or
                    motor_group_totals[motor_group]['completed'] != db_completed):
                    set_props('alert-upload', {'is_open': True, 'children': f'Warning: Mismatch in {motor_group} totals.', 'color': 'warning'})

    set_props('positioner-info-div', {'children': positioner_info})
    set_props('scan-totals-row', {'children': total_points_fields})


@callback(
    Input('url-scan-page', 'href'),
    prevent_initial_call=True
)
def load_scan_metadata(href):
    if not href:
        raise PreventUpdate

    parsed_url = urllib.parse.urlparse(href)
    query_params = urllib.parse.parse_qs(parsed_url.query)
    
    scan_id_str = query_params.get('scan_id', [None])[0]

    if scan_id_str:
        try:
            scan_id = int(scan_id_str)
            with Session(session_utils.get_engine()) as session:
                metadata_data = session.query(db_schema.Metadata).filter(db_schema.Metadata.scanNumber == scan_id).first()
                scan_data = session.query(db_schema.Scan).filter(db_schema.Scan.scanNumber == scan_id)
                catalog_data = session.query(db_schema.Catalog).filter(db_schema.Catalog.scanNumber == scan_id).first()
                if metadata_data:
                    if scan_data:
                        scan_rows = list(scan_data)  # Convert query to list
                        set_scan_accordions(scan_rows, read_only=True)
                    else:
                        scan_rows = []
                    set_metadata_form_props(metadata_data, scan_rows, read_only=True)
                    if catalog_data:
                        set_catalog_form_props(catalog_data, read_only=False)
                        set_scaninfo_form_props(metadata_data, scan_rows, catalog_data, read_only=True)

        except Exception as e:
            print(f"Error loading scan data: {e}")


"""
=======================
Recon Table
=======================
"""

VISIBLE_COLS_Recon = [
    db_schema.Recon.recon_id,
    db_schema.Recon.author,
    db_schema.Recon.percent_brightest,
    db_schema.Job.submit_time,
    db_schema.Job.start_time,
    db_schema.Job.finish_time,
    db_schema.Job.status,
    db_schema.Recon.notes,
]

CUSTOM_HEADER_NAMES_Recon = {
    'recon_id': 'Recon ID', #'ReconID',
    'percent_brightest': 'Pixels',
    'submit_time': 'Date',
}

CUSTOM_COLS_Recon_dict = {
    1:[
        db_schema.Catalog.aperture, #db_schema.Recon.depth_technique, #presently does not exist
        db_schema.Recon.calib_id, #Calib.calib_id,
    ],
    4:[
        db_schema.Recon.scanPointslen,
        #db_schema.Metadata.motorGroup_sample_npts_total,
        db_schema.Metadata.motorGroup_sample_cpt_total,
        # db_schema.Metadata.motorGroup_energy_npts_total,
        # db_schema.Metadata.motorGroup_energy_cpt_total,
        # db_schema.Metadata.motorGroup_depth_npts_total,
        # db_schema.Metadata.motorGroup_depth_cpt_total,
    ],
    5:[
        db_schema.Recon.geo_source_offset,
        db_schema.Recon.geo_source_grid,
    ],
}

ALL_COLS_Recon = VISIBLE_COLS_Recon + [db_schema.Recon.scanNumber] + [ii for i in CUSTOM_COLS_Recon_dict.values() for ii in i]

VISIBLE_COLS_WireRecon = [
    db_schema.WireRecon.wirerecon_id,
    db_schema.WireRecon.author,
    db_schema.WireRecon.percent_brightest,
    db_schema.Job.submit_time,
    db_schema.Job.start_time,
    db_schema.Job.finish_time,
    db_schema.Job.status,
    db_schema.WireRecon.notes,
]

CUSTOM_HEADER_NAMES_WireRecon = {
    'wirerecon_id': 'Recon ID (Wire)', #'Wire Recon ID',
    'percent_brightest': 'Pixels',
    'submit_time': 'Date',
}

CUSTOM_COLS_WireRecon_dict = {
    1:[
        db_schema.Catalog.aperture, #db_schema.Recon.depth_technique, #presently does not exist
        # db_schema.WireRecon.calib_id, #Calib.calib_id,
    ],
    4:[
        db_schema.WireRecon.scanPointslen,
        #db_schema.Metadata.motorGroup_sample_npts_total,
        db_schema.Metadata.motorGroup_sample_cpt_total,
        # db_schema.Metadata.motorGroup_energy_npts_total,
        # db_schema.Metadata.motorGroup_energy_cpt_total,
        # db_schema.Metadata.motorGroup_depth_npts_total,
        # db_schema.Metadata.motorGroup_depth_cpt_total,
    ],
    5:[
        # db_schema.Recon.geo_source_offset,
        # db_schema.Recon.geo_source_grid,
        db_schema.WireRecon.depth_start,
        db_schema.WireRecon.depth_end,
        #db_schema.WireRecon.depth_resolution,
    ],
}

ALL_COLS_WireRecon = VISIBLE_COLS_WireRecon + [db_schema.WireRecon.scanNumber] + [ii for i in CUSTOM_COLS_WireRecon_dict.values() for ii in i]

def _get_scan_recons(scan_id):
    try:
        scan_id = int(scan_id)
        with Session(session_utils.get_engine()) as session:
            aperture = pd.read_sql(session.query(db_schema.Catalog.aperture).filter(db_schema.Catalog.scanNumber == scan_id).statement, session.bind).at[0,'aperture']
            aperture = str(aperture).lower()
            
            if 'wire' in aperture:
                # Query with subjob count
                scan_recons = pd.read_sql(session.query(
                                *ALL_COLS_WireRecon,
                                # func.count(db_schema.SubJob.subjob_id).label('subjob_count')
                                )
                                .join(db_schema.Metadata.catalog_)
                                .join(db_schema.Metadata.wirerecon_)
                                # .join(db_schema.Catalog, db_schema.Metadata.scanNumber == db_schema.Catalog.scanNumber)
                                # .join(db_schema.WireRecon, db_schema.Metadata.scanNumber == db_schema.WireRecon.scanNumber)
                                .join(db_schema.Job, db_schema.WireRecon.job_id == db_schema.Job.job_id)
                                .outerjoin(db_schema.SubJob, db_schema.Job.job_id == db_schema.SubJob.job_id)
                                .filter(db_schema.Metadata.scanNumber == scan_id)
                                .group_by(*ALL_COLS_WireRecon)
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
                for col in VISIBLE_COLS_WireRecon:
                    field_key = col.key
                    header_name = CUSTOM_HEADER_NAMES_WireRecon.get(field_key, field_key.replace('_', ' ').title())
                    
                    col_def = {
                        'headerName': header_name,
                        'field': field_key,
                        'filter': True, 
                        'sortable': True, 
                        'resizable': True,
                        'floatingFilter': True,
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
                    elif col_num == 4:
                        col_def = {
                            'headerName': 'Points',
                            'valueGetter': {"function":
                                # "params.data.subjob_count + ' / ' + params.data.total_sample_points"
                                "params.data.scanPointslen + ' / ' + params.data.motorGroup_sample_cpt_total"
                            },
                        }
                    elif col_num == 5:
                        col_def = {
                            'headerName': 'Depth [µm]', # 'Depth [${\mu}m$]',
                            'valueGetter': {"function":
                                "params.data.depth_start \
                                + ' to ' + \
                                params.data.depth_end"
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
                # Query with subjob count
                scan_recons = pd.read_sql(session.query(
                                *ALL_COLS_Recon,
                                # func.count(db_schema.SubJob.subjob_id).label('subjob_count')
                                )
                                .join(db_schema.Metadata.catalog_)
                                .join(db_schema.Metadata.recon_)
                                .join(db_schema.Metadata.scan_)
                                # .join(db_schema.Catalog, db_schema.Metadata.scanNumber == db_schema.Catalog.scanNumber)
                                # .join(db_schema.Recon, db_schema.Metadata.scanNumber == db_schema.Recon.scanNumber)
                                .join(db_schema.Job, db_schema.Recon.job_id == db_schema.Job.job_id)
                                .outerjoin(db_schema.SubJob, db_schema.Job.job_id == db_schema.SubJob.job_id)
                                .filter(db_schema.Metadata.scanNumber == scan_id)
                                .group_by(*ALL_COLS_Recon)
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
                for col in VISIBLE_COLS_Recon:
                    field_key = col.key
                    header_name = CUSTOM_HEADER_NAMES_Recon.get(field_key, field_key.replace('_', ' ').title())
                    
                    col_def = {
                        'headerName': header_name,
                        'field': field_key,
                        'filter': True, 
                        'sortable': True, 
                        'resizable': True,
                        'floatingFilter': True,
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
                    if col_num == 1:
                        col_def = {
                            'headerName': 'Method',
                            'valueGetter': {"function":
                                "params.data.aperture + ', calib: ' + params.data.calib_id" # "'CA, calib: ' + params.data.calib_id"
                            },
                        }
                    elif col_num == 4:
                        col_def = {
                            'headerName': 'Points',
                            'valueGetter': {"function":
                                # "params.data.subjob_count + ' / ' + params.data.total_sample_points"
                                "params.data.scanPointslen + ' / ' + params.data.motorGroup_sample_cpt_total"
                            },
                        }
                    elif col_num == 5:
                        col_def = {
                            'headerName': 'Depth [µm]', # 'Depth [${\mu}m$]',
                            'valueGetter': {"function":
                                "1000*(params.data.geo_source_grid[0] + params.data.geo_source_offset) \
                                + ' to ' + \
                                1000*(params.data.geo_source_grid[1] + params.data.geo_source_offset)"
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
        scan_id = query_params.get('scan_id', [None])[0]

        if scan_id:
            cols, recons = _get_scan_recons(scan_id)
            return cols, recons
    else:
        raise PreventUpdate

"""
=======================
Peak Indexing Table
=======================
"""

VISIBLE_COLS_PeakIndex = [
    db_schema.PeakIndex.peakindex_id,
    db_schema.PeakIndex.author,
    db_schema.PeakIndex.boxsize,
    db_schema.PeakIndex.threshold,
    db_schema.Job.submit_time,
    db_schema.Job.start_time,
    db_schema.Job.finish_time,
    db_schema.Job.status,
    db_schema.PeakIndex.notes,
]

CUSTOM_HEADER_NAMES_PeakIndex = {
    'peakindex_id': 'Index ID', #'Peak Index ID',
    #'': 'Points',
    'boxsize': 'Box',
    'submit_time': 'Date',
}

CUSTOM_COLS_PeakIndex_dict = {
    3:[
        db_schema.PeakIndex.crystFile,
    ],
    4:[
        db_schema.PeakIndex.scanPointslen.label('PeakIndex_scanPointslen'),
        db_schema.PeakIndex.depthRangelen,
        #db_schema.Metadata.motorGroup_sample_npts_total,
        db_schema.Metadata.motorGroup_sample_cpt_total,
        # db_schema.Metadata.motorGroup_energy_npts_total,
        # db_schema.Metadata.motorGroup_energy_cpt_total,
        #db_schema.Metadata.motorGroup_depth_npts_total,
        db_schema.Metadata.motorGroup_depth_cpt_total,
    ],
}

ALL_COLS_PeakIndex = VISIBLE_COLS_PeakIndex + [db_schema.PeakIndex.scanNumber] + [ii for i in CUSTOM_COLS_PeakIndex_dict.values() for ii in i]

VISIBLE_COLS_Recon_PeakIndex = [
    db_schema.PeakIndex.peakindex_id,
    db_schema.PeakIndex.recon_id,
    db_schema.PeakIndex.author,
    db_schema.PeakIndex.boxsize,
    db_schema.PeakIndex.threshold,
    db_schema.Job.submit_time,
    db_schema.Job.start_time,
    db_schema.Job.finish_time,
    db_schema.Job.status,
    db_schema.PeakIndex.notes,
]

CUSTOM_HEADER_NAMES_Recon_PeakIndex = {
    'peakindex_id': 'Index ID', #'Peak Index ID',
    'recon_id': 'Recon ID', #'ReconID',
    #'': 'Points',
    'boxsize': 'Box',
    'submit_time': 'Date',
}

CUSTOM_COLS_Recon_PeakIndex_dict = {
    3:[
        db_schema.PeakIndex.crystFile,
    ],
    4:[
        db_schema.PeakIndex.scanPointslen.label('PeakIndex_scanPointslen'),
        db_schema.PeakIndex.depthRangelen,
        #db_schema.Metadata.motorGroup_depth_npts_total,
        db_schema.Metadata.motorGroup_depth_cpt_total,
        db_schema.Recon.scanPointslen.label('Recon_scanPointslen'),
    ],
}

ALL_COLS_Recon_PeakIndex = VISIBLE_COLS_Recon_PeakIndex + [db_schema.PeakIndex.scanNumber] + [ii for i in CUSTOM_COLS_Recon_PeakIndex_dict.values() for ii in i]

VISIBLE_COLS_WireRecon_PeakIndex = [
    db_schema.PeakIndex.peakindex_id,
    db_schema.PeakIndex.wirerecon_id,
    db_schema.PeakIndex.author,
    db_schema.PeakIndex.boxsize,
    db_schema.PeakIndex.threshold,
    db_schema.Job.submit_time,
    db_schema.Job.start_time,
    db_schema.Job.finish_time,
    db_schema.Job.status,
    db_schema.PeakIndex.notes,
]

CUSTOM_HEADER_NAMES_WireRecon_PeakIndex = {
    'peakindex_id': 'Index ID', #'Peak Index ID',
    'wirerecon_id': 'Recon ID (Wire)', #'Wire Recon ID',
    'boxsize': 'Box',
    'submit_time': 'Date',
}

CUSTOM_COLS_WireRecon_PeakIndex_dict = {
    3:[
        db_schema.PeakIndex.crystFile,
    ],
    4:[
        db_schema.PeakIndex.scanPointslen.label('PeakIndex_scanPointslen'),
        db_schema.PeakIndex.depthRangelen,
        #db_schema.Metadata.motorGroup_depth_npts_total,
        db_schema.Metadata.motorGroup_depth_cpt_total,
        db_schema.WireRecon.scanPointslen.label('WireRecon_scanPointslen'),
    ],
}

ALL_COLS_WireRecon_PeakIndex = VISIBLE_COLS_WireRecon_PeakIndex + [db_schema.PeakIndex.scanNumber] + [ii for i in CUSTOM_COLS_WireRecon_PeakIndex_dict.values() for ii in i]

def _get_scan_peakindexings(scan_id):
    try:
        scan_id = int(scan_id)
        with Session(session_utils.get_engine()) as session:
            aperture = pd.read_sql(session.query(db_schema.Catalog.aperture).filter(db_schema.Catalog.scanNumber == scan_id).statement, session.bind).at[0,'aperture']
            aperture = str(aperture).lower()
            
            if aperture == 'none':
                # Query with subjob count
                scan_peakindexings = pd.read_sql(session.query(
                                *ALL_COLS_PeakIndex,
                                # func.count(db_schema.SubJob.subjob_id).label('subjob_count')
                                )
                                .join(db_schema.Metadata, db_schema.PeakIndex.scanNumber == db_schema.Metadata.scanNumber)
                                .join(db_schema.Job, db_schema.PeakIndex.job_id == db_schema.Job.job_id)
                                .filter(db_schema.PeakIndex.scanNumber == scan_id)
                                .group_by(*ALL_COLS_PeakIndex)
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
                for col in VISIBLE_COLS_PeakIndex:
                    field_key = col.key
                    header_name = CUSTOM_HEADER_NAMES_PeakIndex.get(field_key, field_key.replace('_', ' ').title())
                    
                    col_def = {
                        'headerName': header_name,
                        'field': field_key,
                        'filter': True, 
                        'sortable': True, 
                        'resizable': True,
                        'floatingFilter': True,
                        'suppressMenuHide': True
                    }

                    if field_key == 'peakindex_id':
                        col_def['cellRenderer'] = 'PeakIndexLinkRenderer'
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
                    if col_num == 3:
                        col_def = {
                            'headerName': 'Structure',
                            'valueGetter': {"function": "params.data.crystFile.slice(params.data.crystFile.lastIndexOf('/') + 1, params.data.crystFile.lastIndexOf('.'))"},
                            # "params.data.subjob_count + ' / ' + params.data.total_frames
                        }
                    if col_num == 4:
                        col_def = {
                            'headerName': 'Frames', # frames from all points
                            'valueGetter': {"function": "params.data.PeakIndex_scanPointslen * params.data.depthRangelen + ' / ' + params.data.motorGroup_sample_cpt_total * params.data.motorGroup_depth_cpt_total"},
                            # "params.data.subjob_count + ' / ' + params.data.total_frames
                        }
                    col_def.update({
                        'filter': True, 
                        'sortable': True, 
                        'resizable': True,
                        'suppressMenuHide': True
                    })
                    cols.insert(col_num,col_def)

                # peakindexings['id'] = peakindexings['scanNumber'] # This was for dash_table and is not directly used by ag-grid unless getRowId is configured
                
                return cols, scan_peakindexings.to_dict('records')
            
            elif 'wire' in aperture:
                # Query with subjob count
                scan_peakindexings = pd.read_sql(session.query(
                                *ALL_COLS_WireRecon_PeakIndex,
                                # func.count(db_schema.SubJob.subjob_id).label('subjob_count')
                                )
                                .join(db_schema.Metadata, db_schema.PeakIndex.scanNumber == db_schema.Metadata.scanNumber)
                                .join(db_schema.Job, db_schema.PeakIndex.job_id == db_schema.Job.job_id)
                                .outerjoin(db_schema.WireRecon, db_schema.PeakIndex.wirerecon_id == db_schema.WireRecon.wirerecon_id)
                                .filter(db_schema.PeakIndex.scanNumber == scan_id)
                                .group_by(*ALL_COLS_PeakIndex)
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
                for col in VISIBLE_COLS_WireRecon_PeakIndex:
                    field_key = col.key
                    header_name = CUSTOM_HEADER_NAMES_WireRecon_PeakIndex.get(field_key, field_key.replace('_', ' ').title())
                    
                    col_def = {
                        'headerName': header_name,
                        'field': field_key,
                        'filter': True, 
                        'sortable': True, 
                        'resizable': True,
                        'floatingFilter': True,
                        'suppressMenuHide': True
                    }

                    if field_key == 'peakindex_id':
                        col_def['cellRenderer'] = 'PeakIndexLinkRenderer'
                    elif field_key == 'recon_id':
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
                for col_num in CUSTOM_COLS_WireRecon_PeakIndex_dict.keys():
                    if col_num == 3:
                        col_def = {
                            'headerName': 'Structure',
                            'valueGetter': {"function": "params.data.crystFile.slice(params.data.crystFile.lastIndexOf('/') + 1, params.data.crystFile.lastIndexOf('.'))"},
                            # "params.data.subjob_count + ' / ' + params.data.total_frames
                        }
                    if col_num == 4:
                        col_def = {
                            'headerName': 'Frames', # frames from all points
                            'valueGetter': {"function": "params.data.PeakIndex_scanPointslen * params.data.depthRangelen + ' / ' + params.data.WireRecon_scanPointslen * params.data.motorGroup_depth_cpt_total"},
                            # "params.data.subjob_count + ' / ' + params.data.total_frames
                        }
                    col_def.update({
                        'filter': True, 
                        'sortable': True, 
                        'resizable': True,
                        'suppressMenuHide': True
                    })
                    cols.insert(col_num,col_def)

                # peakindexings['id'] = peakindexings['scanNumber'] # This was for dash_table and is not directly used by ag-grid unless getRowId is configured
                
                return cols, scan_peakindexings.to_dict('records')
            
            else:
                # Query with subjob count
                scan_peakindexings = pd.read_sql(session.query(
                                *ALL_COLS_Recon_PeakIndex,
                                # func.count(db_schema.SubJob.subjob_id).label('subjob_count')
                                )
                                .join(db_schema.Metadata, db_schema.PeakIndex.scanNumber == db_schema.Metadata.scanNumber)
                                .join(db_schema.Job, db_schema.PeakIndex.job_id == db_schema.Job.job_id)
                                .outerjoin(db_schema.Recon, db_schema.PeakIndex.recon_id == db_schema.Recon.recon_id)
                                .filter(db_schema.PeakIndex.scanNumber == scan_id)
                                .group_by(*ALL_COLS_PeakIndex)
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
                for col in VISIBLE_COLS_Recon_PeakIndex:
                    field_key = col.key
                    header_name = CUSTOM_HEADER_NAMES_Recon_PeakIndex.get(field_key, field_key.replace('_', ' ').title())
                    
                    col_def = {
                        'headerName': header_name,
                        'field': field_key,
                        'filter': True, 
                        'sortable': True, 
                        'resizable': True,
                        'floatingFilter': True,
                        'suppressMenuHide': True
                    }

                    if field_key == 'peakindex_id':
                        col_def['cellRenderer'] = 'PeakIndexLinkRenderer'
                    elif field_key == 'recon_id':
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
                for col_num in CUSTOM_COLS_PeakIndex_dict.keys():
                    if col_num == 3:
                        col_def = {
                            'headerName': 'Structure',
                            'valueGetter': {"function": "params.data.crystFile.slice(params.data.crystFile.lastIndexOf('/') + 1, params.data.crystFile.lastIndexOf('.'))"},
                            # "params.data.subjob_count + ' / ' + params.data.total_frames
                        }
                    if col_num == 4:
                        col_def = {
                            'headerName': 'Frames', # frames from all points
                            'valueGetter': {"function": "params.data.PeakIndex_scanPointslen * params.data.depthRangelen + ' / ' + params.data.Recon_scanPointslen * params.data.motorGroup_depth_cpt_total"},
                            # "params.data.subjob_count + ' / ' + params.data.total_frames
                        }
                    col_def.update({
                        'filter': True, 
                        'sortable': True, 
                        'resizable': True,
                        'suppressMenuHide': True
                    })
                    cols.insert(col_num,col_def)

                # peakindexings['id'] = peakindexings['scanNumber'] # This was for dash_table and is not directly used by ag-grid unless getRowId is configured
                
                return cols, scan_peakindexings.to_dict('records')
    
    except Exception as e:
        print(f"Error loading peak indexing data: {e}")


@callback(
    Output('scan-peakindex-table', 'columnDefs'),
    Output('scan-peakindex-table', 'rowData'),
    Input('url-scan-page', 'href'),
    prevent_initial_call=True,
)
def get_scan_peakindexings(href):
    if not href:
        raise PreventUpdate

    parsed_url = urllib.parse.urlparse(href)
    path = parsed_url.path
    
    if path == '/scan':
        query_params = urllib.parse.parse_qs(parsed_url.query)
        scan_id = query_params.get('scan_id', [None])[0]

        if scan_id:
            cols, peakindexings = _get_scan_peakindexings(scan_id)
            return cols, peakindexings
    else:
        raise PreventUpdate


@callback(
    Output('new-recon-btn', 'href'),
    Output('recon-table-new-recon-btn', 'href'),
    Output('index-table-new-recon-btn', 'href'),
    Input('scan-recon-table', 'selectedRows'),
    Input('scan-peakindex-table', 'selectedRows'),
    State('new-recon-btn', 'href'),
    prevent_initial_call=True,
)
def selected_recon_href(recon_rows, peakindex_rows, href):
    base_href = href.split("?")[0]

    main_scan_ids, main_wirerecon_ids, main_recon_ids = [], [], []
    recon_scan_ids, recon_wirerecon_ids, recon_recon_ids = [], [], []
    index_scan_ids, index_wirerecon_ids, index_recon_ids = [], [], []

    for row in (recon_rows or []):
        if not row.get('scanNumber'): return base_href, base_href, base_href
        scan_id, wirerecon_id, recon_id = str(row['scanNumber']), str(row.get('wirerecon_id', '')), str(row.get('recon_id', ''))
        main_scan_ids.append(scan_id); main_wirerecon_ids.append(wirerecon_id); main_recon_ids.append(recon_id)
        recon_scan_ids.append(scan_id); recon_wirerecon_ids.append(wirerecon_id); recon_recon_ids.append(recon_id)

    for row in (peakindex_rows or []):
        if not row.get('scanNumber'): return base_href, base_href, base_href
        scan_id, wirerecon_id, recon_id = str(row['scanNumber']), str(row.get('wirerecon_id', '')), str(row.get('recon_id', ''))
        main_scan_ids.append(scan_id); main_wirerecon_ids.append(wirerecon_id); main_recon_ids.append(recon_id)
        index_scan_ids.append(scan_id); index_wirerecon_ids.append(wirerecon_id); index_recon_ids.append(recon_id)

    def build_href(scan_ids, wirerecon_ids, recon_ids, rows, base_href):
        if not rows:
            return base_href

        any_wirerecon_scans, any_recon_scans = False, False
        for i, row in enumerate(rows):
            any_wirerecon_scans = any(wirerecon_ids)
            any_recon_scans = any(recon_ids)

            # Conflict condition: mixture of wirerecon and recon
            if any_wirerecon_scans and any_recon_scans:
                return base_href

            # Missing Recon ID condition
            if not any_wirerecon_scans and not any_recon_scans and row.get('aperture'):
                aperture = str(row['aperture']).lower()
                if aperture == 'none':
                    return base_href # Conflict condition: cannot be reconstructed
                elif 'wire' in aperture:
                    any_wirerecon_scans = True
                else:
                    any_recon_scans = True
        
                # Conflict condition: mixture of wirerecon and recon (copied from above)
                if any_wirerecon_scans and any_recon_scans:
                    return base_href
        
        if any_recon_scans:
            base_href = "/create-reconstruction"
        elif any_wirerecon_scans:
            base_href = "/create-wire-reconstruction"

        query_params = [f"scan_id={','.join(list(set(scan_ids)))}"]
        if any_wirerecon_scans: query_params.append(f"wirerecon_id={','.join(filter(None, wirerecon_ids))}")
        if any_recon_scans: query_params.append(f"recon_id={','.join(filter(None, recon_ids))}")
        
        return f"{base_href}?{'&'.join(query_params)}"

    main_href = build_href(main_scan_ids, main_wirerecon_ids, main_recon_ids, (recon_rows or []) + (peakindex_rows or []), base_href)
    recon_href = build_href(recon_scan_ids, recon_wirerecon_ids, recon_recon_ids, recon_rows or [], base_href)
    index_href = build_href(index_scan_ids, index_wirerecon_ids, index_recon_ids, peakindex_rows or [], base_href)

    return main_href, recon_href, index_href


@callback(
    Output('new-index-btn', 'href'),
    Output('recon-table-new-index-btn', 'href'),
    Output('index-table-new-index-btn', 'href'),
    Input('scan-recon-table', 'selectedRows'),
    Input('scan-peakindex-table', 'selectedRows'),
    State('new-index-btn', 'href'),
    prevent_initial_call=True,
)
def selected_peakindex_href(recon_rows, peakindex_rows, href):
    base_href = href.split("?")[0]

    main_scan_ids, main_wirerecon_ids, main_recon_ids, main_peakindex_ids = [], [], [], []
    recon_scan_ids, recon_wirerecon_ids, recon_recon_ids, recon_peakindex_ids = [], [], [], []
    index_scan_ids, index_wirerecon_ids, index_recon_ids, index_peakindex_ids = [], [], [], []

    for row in (recon_rows or []):
        if not row.get('scanNumber'): return base_href, base_href, base_href
        scan_id, wirerecon_id, recon_id, peakindex_id = str(row['scanNumber']), str(row.get('wirerecon_id', '')), str(row.get('recon_id', '')), str(row.get('peakindex_id', ''))
        main_scan_ids.append(scan_id); main_wirerecon_ids.append(wirerecon_id); main_recon_ids.append(recon_id); main_peakindex_ids.append(peakindex_id)
        recon_scan_ids.append(scan_id); recon_wirerecon_ids.append(wirerecon_id); recon_recon_ids.append(recon_id); recon_peakindex_ids.append(peakindex_id)

    for row in (peakindex_rows or []):
        if not row.get('scanNumber'): return base_href, base_href, base_href
        scan_id, wirerecon_id, recon_id, peakindex_id = str(row['scanNumber']), str(row.get('wirerecon_id', '')), str(row.get('recon_id', '')), str(row.get('peakindex_id', ''))
        main_scan_ids.append(scan_id); main_wirerecon_ids.append(wirerecon_id); main_recon_ids.append(recon_id); main_peakindex_ids.append(peakindex_id)
        index_scan_ids.append(scan_id); index_wirerecon_ids.append(wirerecon_id); index_recon_ids.append(recon_id); index_peakindex_ids.append(peakindex_id)

    def build_href(scan_ids, wirerecon_ids, recon_ids, peakindex_ids, base_href):
        if not scan_ids:
            return base_href

        query_params = [f"scan_id={','.join(list(set(scan_ids)))}"]
        if any(wirerecon_ids): query_params.append(f"wirerecon_id={','.join(filter(None, wirerecon_ids))}")
        if any(recon_ids): query_params.append(f"recon_id={','.join(filter(None, recon_ids))}")
        if any(peakindex_ids): query_params.append(f"peakindex_id={','.join(filter(None, peakindex_ids))}")

        return f"{base_href}?{'&'.join(query_params)}"

    main_href = build_href(main_scan_ids, main_wirerecon_ids, main_recon_ids, main_peakindex_ids, base_href)
    recon_href = build_href(recon_scan_ids, recon_wirerecon_ids, recon_recon_ids, recon_peakindex_ids, base_href)
    index_href = build_href(index_scan_ids, index_wirerecon_ids, index_recon_ids, index_peakindex_ids, base_href)

    return main_href, recon_href, index_href


@callback(
    Input("save-note-btn", "n_clicks"),
    State("scanNumber", "value"),
    State("Note_print", "value"),
    prevent_initial_call=True,
)
def save_note(n_clicks, scanNumber, note):
    if not n_clicks:
        raise PreventUpdate

    if not scanNumber:
        set_props("alert-note-submit", {'is_open': True, 'children': 'Scan ID not found.', 'color': 'danger'})
        raise PreventUpdate

    try:
        scan_id = int(scanNumber)
        with Session(session_utils.get_engine()) as session:
            catalog_entry = (
                session.query(db_schema.Catalog)
                .filter(db_schema.Catalog.scanNumber == scan_id)
                .first()
            )

            if not catalog_entry:
                set_props("alert-note-submit", {'is_open': True, 'children': f'No catalog entry found for scan {scan_id}.', 'color': 'danger'})
                raise PreventUpdate

            if catalog_entry.notes:
                catalog_entry.notes += f"\n{note}"
            else:
                catalog_entry.notes = note

            session.commit()

            set_props("alert-note-submit", {'is_open': True, 
                                                'children': f'Note added to scan {scan_id}',
                                                'color': 'success'})

    except Exception as e:
        set_props("alert-note-submit", {'is_open': True, 'children': f'Error saving note: {e}', 'color': 'danger'})


@callback(
    Input("save-catalog-btn", "n_clicks"),
    State("scanNumber", "value"),
    State("aperture", "value"),
    State("sample_name", "value"),
    State("filefolder", "value"),
    State("filenamePrefix", "value"),
    State("notes", "value"),
    prevent_initial_call=True,
)
def update_catalog(n,
    scanNumber,
    aperture,
    sample_name,
    filefolder,
    filenamePrefix,
    notes,
):
    # TODO: Input validation and response
 
    try:
        # Convert scanNumber to int if it's a string
        if isinstance(scanNumber, str):
            scanNumber = int(scanNumber)
        
        with Session(session_utils.get_engine()) as session:
            try:
                # Check if catalog entry already exists
                catalog_data = session.query(db_schema.Catalog).filter(
                    db_schema.Catalog.scanNumber == scanNumber
                ).first()
                
                # Parse comma-separated string into list for database
                if filenamePrefix:
                    filenamePrefix_list = [prefix.strip() for prefix in filenamePrefix.split(',') if prefix.strip()]
                else:
                    filenamePrefix_list = []
                
                if catalog_data:
                    # Update existing catalog entry
                    catalog_data.filefolder = filefolder
                    catalog_data.filenamePrefix = filenamePrefix_list
                    catalog_data.aperture = aperture
                    catalog_data.sample_name = sample_name
                    catalog_data.notes = notes
                    
                else:
                    # Create new catalog entry
                    catalog = db_schema.Catalog(
                        scanNumber=scanNumber,
                        filefolder=filefolder,
                        filenamePrefix=filenamePrefix_list,
                        aperture=aperture,
                        sample_name=sample_name,
                        notes=notes,
                    )
                    
                    session.add(catalog)
                
                # Commit all changes
                session.commit()

                if catalog_data:
                    set_props("alert-catalog-submit", {'is_open': True, 
                                                'children': f'Catalog Entry Updated for scan {scanNumber}',
                                                'color': 'success'})
                else:
                    set_props("alert-catalog-submit", {'is_open': True, 
                                                'children': f'Catalog Entry Added to Database for scan {scanNumber}',
                                                'color': 'success'})
                    
            except Exception as e:
                set_props("alert-catalog-submit", {'is_open': True, 
                                            'children': f'Error creating catalog entry: {str(e)}',
                                            'color': 'danger'})
                return
                                            
    except ValueError as e:
        set_props("alert-catalog-submit", {'is_open': True, 
                                    'children': f'Error: Invalid scan number format. Please enter a valid integer.',
                                    'color': 'danger'})
