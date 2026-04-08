import dash_bootstrap_components as dbc
import dash_ag_grid as dag
from dash import html, dcc, Input, Output, State
import dash
import base64
import json
import laue_portal.database.db_utils as db_utils
import laue_portal.components.navbar as navbar

dash.register_page(__name__)

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

layout = dbc.Container(
    [
        # Client-side stores
        dcc.Store(id='bulk-parsed-scans', data=None),  # full parsed scan data (list of dicts)

        html.Div([
            navbar.navbar,

            # Alerts
            dbc.Alert(id="alert-upload", dismissable=True, duration=4000, is_open=False),
            dbc.Alert(id="alert-import", dismissable=True, is_open=False),

            html.Hr(),

            # ---- Upload Section ----
            html.Center(
                dcc.Upload(
                    id='upload-metadata-log',
                    children=dbc.Button(
                        [html.I(className="bi bi-upload me-2"), "Upload Scan Log XML"],
                        color='primary',
                        size='lg',
                    ),
                    multiple=False,
                ),
            ),

            html.Hr(),

            # ---- Catalog Defaults Card (collapsed until scans loaded) ----
            dbc.Card(
                [
                    dbc.CardHeader(
                        html.H5("Catalog Defaults (applied to all imported scans)", className="mb-0"),
                    ),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                dbc.InputGroup([
                                    dbc.InputGroupText("Aperture"),
                                    dbc.Select(
                                        id='bulk-aperture',
                                        options=[
                                            {"label": "None", "value": ""},
                                            {"label": "Wire", "value": "wire"},
                                            {"label": "Coded Aperture", "value": "mask"},
                                        ],
                                        value='wire',
                                    ),
                                ], className="mb-2"),
                            ], md=3),
                            dbc.Col([
                                dbc.InputGroup([
                                    dbc.InputGroupText("Sample Name"),
                                    dbc.Input(id='bulk-sample-name', value='', placeholder='e.g. Si'),
                                ], className="mb-2"),
                            ], md=3),
                            dbc.Col([
                                dbc.InputGroup([
                                    dbc.InputGroupText("Files Path"),
                                    dbc.Input(id='bulk-filefolder', value='', placeholder='/path/to/data'),
                                ], className="mb-2"),
                            ], md=3),
                            dbc.Col([
                                dbc.InputGroup([
                                    dbc.InputGroupText("Filename Prefix"),
                                    dbc.Input(id='bulk-filename-prefix', value='', placeholder='prefix_%d'),
                                ], className="mb-2"),
                            ], md=3),
                        ]),
                        dbc.Row([
                            dbc.Col([
                                dbc.InputGroup([
                                    dbc.InputGroupText("Notes"),
                                    dbc.Input(id='bulk-notes', value='', placeholder='Optional notes'),
                                ], className="mb-2"),
                            ], md=12),
                        ]),
                    ]),
                ],
                id='catalog-defaults-card',
                style={'display': 'none'},
                className='mb-3',
            ),

            # ---- Action Bar ----
            dbc.Row([
                dbc.Col([
                    dbc.Nav([
                        dbc.Button(
                            [html.I(className="bi bi-check2-all me-1"), "Import Selected"],
                            id="btn-import-selected",
                            color="primary",
                            className="me-2",
                            disabled=True,
                        ),
                        html.Span(id='import-summary-text', className='align-self-center text-muted me-2'),
                    ], className="px-2 py-2 d-flex align-items-center"),
                ], width=12),
            ], id='action-bar', className="mb-3 mt-0", style={'display': 'none'}),

            # ---- AG Grid Scan Table ----
            html.Div(
                dbc.Container(fluid=True, className="p-0", children=[
                    dag.AgGrid(
                        id='bulk-scan-table',
                        columnSize="responsiveSizeToFit",
                        columnDefs=[],
                        rowData=[],
                        defaultColDef={
                            "filter": True,
                            "sortable": True,
                            "resizable": True,
                        },
                        dashGridOptions={
                            "pagination": True,
                            "paginationPageSize": 50,
                            "domLayout": 'autoHeight',
                            "rowSelection": "multiple",
                            "suppressRowClickSelection": True,
                            "animateRows": False,
                            "rowHeight": 32,
                            "isRowSelectable": {"function": "params.data && params.data.status === 'New'"},
                        },
                        style={'width': '100%'},
                        className="ag-theme-alpine",
                        getRowId="params.data.scanNumber",
                    ),
                ]),
                id='scan-table-container',
                style={'display': 'none'},
            ),
        ]),
    ],
    className='dbc',
    fluid=True,
)

# ---------------------------------------------------------------------------
# Column definitions for the bulk scan AG Grid
# ---------------------------------------------------------------------------

BULK_SCAN_COLS = [
    {
        'headerName': '',
        'field': 'checkbox',
        'checkboxSelection': True,
        'headerCheckboxSelection': True,
        'headerCheckboxSelectionFilteredOnly': True,
        'width': 50,
        'pinned': 'left',
        'sortable': False,
        'filter': False,
        'resizable': False,
        'suppressMenu': True,
        'floatingFilter': False,
    },
    {
        'headerName': 'Scan ID',
        'field': 'scanNumber',
        'sort': 'asc',
        'filter': 'agNumberColumnFilter',
        'width': 110,
    },
    {
        'headerName': 'Date / Time',
        'field': 'time',
        'width': 180,
    },
    {
        'headerName': 'User',
        'field': 'user_name',
        'width': 100,
    },
    {
        'headerName': 'Energy',
        'field': 'energy_display',
        'width': 120,
    },
    {
        'headerName': 'Sample XYZ',
        'field': 'sample_XYZ',
        'width': 200,
    },
    {
        'headerName': 'Dims',
        'field': 'num_dims',
        'width': 70,
        'filter': 'agNumberColumnFilter',
    },
    {
        'headerName': 'Status',
        'field': 'status',
        'cellRenderer': 'ScanImportStatusRenderer',
        'width': 110,
        'pinned': 'right',
    },
]


# ---------------------------------------------------------------------------
# Callback 1: Upload XML -> parse all scans -> populate table
# ---------------------------------------------------------------------------

@dash.callback(
    Output('bulk-scan-table', 'columnDefs'),
    Output('bulk-scan-table', 'rowData'),
    Output('bulk-parsed-scans', 'data'),
    Output('alert-upload', 'is_open'),
    Output('alert-upload', 'children'),
    Output('alert-upload', 'color'),
    Output('upload-metadata-log', 'contents'),
    Output('scan-table-container', 'style'),
    Output('catalog-defaults-card', 'style'),
    Output('action-bar', 'style'),
    Input('upload-metadata-log', 'contents'),
    prevent_initial_call=True,
)
def upload_and_parse(contents):
    """Decode the uploaded XML, parse every scan, check for duplicates, and populate the AG Grid."""
    if not contents:
        raise dash.exceptions.PreventUpdate

    try:
        _, content_string = contents.split(',')
        xml_bytes = base64.b64decode(content_string)
    except Exception as e:
        return (
            [], [], None,
            True, f'Failed to decode uploaded file: {e}', 'danger',
            None, {'display': 'none'}, {'display': 'none'}, {'display': 'none'},
        )

    # Parse all scans
    try:
        parsed = db_utils.parse_all_scans_from_xml(xml_bytes)
    except Exception as e:
        return (
            [], [], None,
            True, f'Failed to parse XML: {e}', 'danger',
            None, {'display': 'none'}, {'display': 'none'}, {'display': 'none'},
        )

    if not parsed:
        return (
            [], [], None,
            True, 'No scans found in the uploaded file.', 'warning',
            None, {'display': 'none'}, {'display': 'none'}, {'display': 'none'},
        )

    # Check which scan numbers already exist in the DB
    all_scan_numbers = [p['scanNumber'] for p in parsed]
    existing = db_utils.check_existing_scan_numbers(all_scan_numbers)

    # Build AG Grid row data
    row_data = []
    for p in parsed:
        sn = p['scanNumber']
        energy_str = ''
        if p.get('energy'):
            energy_str = f"{p['energy']}"
            if p.get('energy_unit'):
                energy_str += f" {p['energy_unit']}"

        row_data.append({
            'scanNumber': str(sn),
            'time': p.get('time', ''),
            'user_name': p.get('user_name', ''),
            'energy_display': energy_str,
            'sample_XYZ': p.get('sample_XYZ', ''),
            'num_dims': p.get('num_dims', 0),
            'status': 'Exists' if int(sn) in existing else 'New',
            'scan_index': p['scan_index'],
        })

    # Store full parsed data for later import (minus the large log/scans dicts to save memory)
    # We keep them because we need them for import
    store_data = json.dumps(parsed, default=str)

    num_new = sum(1 for r in row_data if r['status'] == 'New')
    num_existing = sum(1 for r in row_data if r['status'] == 'Exists')
    alert_msg = f"Parsed {len(row_data)} scans: {num_new} new, {num_existing} already in database."
    alert_color = 'success' if num_new > 0 else 'info'

    show = {'display': 'block'}
    return (
        BULK_SCAN_COLS, row_data, store_data,
        True, alert_msg, alert_color,
        None,  # clear upload contents to allow re-upload
        show, show, show,
    )


# ---------------------------------------------------------------------------
# Callback 2: Enable/disable the import button based on selection
# ---------------------------------------------------------------------------

@dash.callback(
    Output('btn-import-selected', 'disabled'),
    Output('btn-import-selected', 'children'),
    Output('import-summary-text', 'children'),
    Input('bulk-scan-table', 'selectedRows'),
    prevent_initial_call=True,
)
def update_import_button(selected_rows):
    if not selected_rows:
        return True, [html.I(className="bi bi-check2-all me-1"), "Import Selected"], ""

    importable = [r for r in selected_rows if r.get('status') == 'New']
    n = len(importable)
    label = [html.I(className="bi bi-check2-all me-1"), f"Import Selected ({n})"]
    summary = f"{n} new scan{'s' if n != 1 else ''} selected"
    return (n == 0), label, summary


# ---------------------------------------------------------------------------
# Callback 3: Import selected scans
# ---------------------------------------------------------------------------

@dash.callback(
    Output('bulk-scan-table', 'rowData', allow_duplicate=True),
    Output('alert-import', 'is_open'),
    Output('alert-import', 'children'),
    Output('alert-import', 'color'),
    Output('alert-import', 'duration'),
    Input('btn-import-selected', 'n_clicks'),
    State('bulk-scan-table', 'selectedRows'),
    State('bulk-scan-table', 'rowData'),
    State('bulk-parsed-scans', 'data'),
    # Catalog defaults
    State('bulk-aperture', 'value'),
    State('bulk-sample-name', 'value'),
    State('bulk-filefolder', 'value'),
    State('bulk-filename-prefix', 'value'),
    State('bulk-notes', 'value'),
    running=[
        (Output("btn-import-selected", "disabled"), True, False),
        (Output("btn-import-selected", "children"),
         [dbc.Spinner(size="sm", spinner_class_name="me-2"), "Importing..."],
         [html.I(className="bi bi-check2-all me-1"), "Import Selected"]),
    ],
    prevent_initial_call=True,
)
def import_selected_scans(
    n_clicks, selected_rows, current_row_data, parsed_scans_json,
    aperture, sample_name, filefolder, filename_prefix, notes,
):
    if not n_clicks or not selected_rows or not parsed_scans_json:
        raise dash.exceptions.PreventUpdate

    # Deserialize stored parsed data
    all_parsed = json.loads(parsed_scans_json)

    # Build lookup: scanNumber -> parsed entry
    parsed_lookup = {str(p['scanNumber']): p for p in all_parsed}

    # Filter to only selected NEW scans
    scans_to_import = []
    for row in selected_rows:
        if row.get('status') == 'New':
            sn = str(row['scanNumber'])
            if sn in parsed_lookup:
                scans_to_import.append(parsed_lookup[sn])

    if not scans_to_import:
        return (
            dash.no_update,
            True, 'No new scans selected for import.', 'warning', 4000,
        )

    # Build catalog defaults
    prefix_list = [s.strip() for s in filename_prefix.split(',')] if filename_prefix else []
    catalog_defaults = {
        'filefolder': filefolder or '',
        'filenamePrefix': prefix_list,
        'aperture': aperture or None,
        'sample_name': sample_name or '',
        'notes': notes or '',
    }

    # Do the bulk import
    results = db_utils.bulk_import_scans(scans_to_import, catalog_defaults)

    # Update row data with new statuses
    updated_rows = []
    for row in current_row_data:
        sn = str(row['scanNumber'])
        if sn in results:
            r = results[sn]
            if r['status'] == 'success':
                row['status'] = 'Imported'
            elif r['status'] == 'skipped':
                row['status'] = 'Exists'
            elif r['status'] == 'failed':
                row['status'] = 'Failed'
        updated_rows.append(row)

    # Build summary message
    n_success = sum(1 for r in results.values() if r['status'] == 'success')
    n_failed = sum(1 for r in results.values() if r['status'] == 'failed')
    n_skipped = sum(1 for r in results.values() if r['status'] == 'skipped')

    parts = []
    if n_success:
        parts.append(f"{n_success} imported")
    if n_skipped:
        parts.append(f"{n_skipped} skipped (already exist)")
    if n_failed:
        parts.append(f"{n_failed} failed")

    summary = f"Bulk import complete: {', '.join(parts)}."

    if n_failed:
        # Include failure details
        failures = [r['message'] for r in results.values() if r['status'] == 'failed']
        summary += " Errors: " + "; ".join(failures[:5])
        if len(failures) > 5:
            summary += f" ... and {len(failures) - 5} more"

    alert_color = 'success' if n_failed == 0 else ('warning' if n_success > 0 else 'danger')

    return updated_rows, True, summary, alert_color, None
