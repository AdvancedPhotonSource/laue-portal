import dash
from dash import html, dcc
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
import laue_portal.pages.ui_shared as ui_shared

dash.register_page(__name__, path="/")

# Data
base_data = [
    {"scan_id": 126745, "user": "Dina", "sample": "Cu", "scan_dim": "3D", "technique": "area-depth", "date": "2025-05-16", "status": "Collecting"},
    {"scan_id": 126746, "user": "Ross", "sample": "ZnO", "scan_dim": "2D", "technique": "area", "date": "2025-05-15", "status": "Processing"},
    {"scan_id": 126747, "user": "Jon", "sample": "Si", "scan_dim": "1D", "technique": "depth", "date": "2025-05-14", "status": "Pending"},
    {"scan_id": 126748, "user": "Dina","sample": "Si", "scan_dim": "2D", "technique": "line-depth", "date": "2025-05-14", "status": "No action"},
    {"scan_id": 126749, "user": "Dina","sample": "Si", "scan_dim": "1D", "technique": "energy-depth", "date": "2025-05-14", "status": "No action"},
    {"scan_id": 126750, "user": "Dina","sample": "Si", "scan_dim": "3D", "technique": "line-energy-depth", "date": "2025-05-14", "status": "No action"},
]

def build_table_rows(data):
    rows = []
    for i, row in enumerate(data):
        action_dropdown = dbc.ButtonGroup([
            dbc.Button("⋮", color="primary", size="sm"),
            dbc.DropdownMenu(
                children=[
                    dbc.DropdownMenuItem("new reconstruction", id=f"recon-{i}"),
                    dbc.DropdownMenuItem("new indexing", id=f"index-{i}")
                ],
                toggle_style={"borderLeft": "1px solid #ccc"},
                direction="down",
                size="sm",
                caret=True,
                color="primary",
            ),
        ])
        rows.append(html.Tr([
            html.Td(dcc.Link(str(row["scan_id"]), href=f"/scan/{row['scan_id']}", style={"textDecoration": "none"})),
            html.Td(row["user"]),
            html.Td(row["sample"]),
            html.Td(row["scan_dim"]),
            html.Td(row["technique"]),
            html.Td(row["date"]),
            html.Td(action_dropdown),
            html.Td(row["status"]),
        ]))
    return rows

layout = dbc.Container([
    ui_shared.navbar,
    dcc.Location(id='url', refresh=False),
    dcc.Store(id="sort-store", data={"column": "scan_id", "ascending": False}),
    dcc.Store(id="filter-store", data={
        "scan_id": "", "user": "", "sample": "", "scan_dim": "", "technique": "", "date": "", "status": ""
    }),
    html.Div(id="scan-table-container")
])

@dash.callback(
    Output("scan-table-container", "children"),
    Input("sort-store", "data"),
    Input("filter-store", "data")
)
def update_table(sort_data, filter_data):
    sort_data = sort_data or {"column": "scan_id", "ascending": False}
    col = sort_data.get("column", "scan_id")
    asc = sort_data.get("ascending", False)

    # Filtering
    filtered_data = []
    for row in base_data:
        match = True
        scan_id_filter = filter_data.get("scan_id", "").strip()
        if scan_id_filter:
            try:
                if "-" in scan_id_filter:
                    start, end = map(int, scan_id_filter.split("-"))
                    if not (start <= row["scan_id"] <= end):
                        match = False
                else:
                    if int(scan_id_filter) != row["scan_id"]:
                        match = False
            except:
                match = False

        for key in ["user", "sample", "scan_dim", "technique", "status", "date"]:
            val = filter_data.get(key, "")
            if val and val.lower() not in str(row[key]).lower():
                match = False

        if match:
            filtered_data.append(row)

    # Sorting
    if col:
        filtered_data.sort(key=lambda x: x[col], reverse=not asc)

    input_style = {"width": "100%", "fontSize": "14px"}

    header_row = html.Tr([
        html.Th(["Scan ID", html.Button("⇅", id="sort-scan_id", n_clicks=0,
                style={"border": "none", "background": "none", "cursor": "pointer", "paddingLeft": "6px", "fontSize": "12px"})], style={"width": "200px"}),
        html.Th(["User", html.Button("⇅", id="sort-user", n_clicks=0,
                style={"border": "none", "background": "none", "cursor": "pointer", "paddingLeft": "6px", "fontSize": "12px"})]),
        html.Th(["Sample", html.Button("⇅", id="sort-sample", n_clicks=0,
                style={"border": "none", "background": "none", "cursor": "pointer", "paddingLeft": "6px", "fontSize": "12px"})]),
        html.Th(["Scan Dim", html.Button("⇅", id="sort-scan_dim", n_clicks=0,
                style={"border": "none", "background": "none", "cursor": "pointer", "paddingLeft": "6px", "fontSize": "12px"})]),
        html.Th(["Technique", html.Button("⇅", id="sort-technique", n_clicks=0,
                style={"border": "none", "background": "none", "cursor": "pointer", "paddingLeft": "6px", "fontSize": "12px"})]),
        html.Th(["Date", html.Button("⇅", id="sort-date", n_clicks=0,
                style={"border": "none", "background": "none", "cursor": "pointer", "paddingLeft": "6px", "fontSize": "12px"})]),
        html.Th("Action"),
        html.Th(["Status", html.Button("⇅", id="sort-status", n_clicks=0,
                style={"border": "none", "background": "none", "cursor": "pointer", "paddingLeft": "6px", "fontSize": "12px"})])
    ])

    filter_row = html.Tr([
        html.Td(dcc.Input(id="filter-scan_id", value=filter_data["scan_id"], placeholder="filter", size="sm", style=input_style)),
        html.Td(dcc.Input(id="filter-user", value=filter_data["user"], placeholder="filter", size="sm", style=input_style)),
        html.Td(dcc.Input(id="filter-sample", value=filter_data["sample"], placeholder="filter", size="sm", style=input_style)),
        html.Td(dcc.Input(id="filter-scan_dim", value=filter_data["scan_dim"], placeholder="filter", size="sm", style=input_style)),
        html.Td(dcc.Input(id="filter-technique", value=filter_data["technique"], placeholder="filter", size="sm", style=input_style)),
        html.Td(dcc.Input(id="filter-date", value=filter_data["date"], placeholder="filter", size="sm", style=input_style)),
        html.Td(),
        html.Td(dcc.Input(id="filter-status", value=filter_data["status"], placeholder="filter", size="sm", style=input_style)),
    ])

    return dbc.Table([
        html.Thead([header_row, filter_row]),
        html.Tbody(build_table_rows(filtered_data))
    ], bordered=True, hover=True, responsive=True, striped=True, style={"tableLayout": "fixed", "width": "100%"})

@dash.callback(
    Output("sort-store", "data"),
    [Input(f"sort-{col}", "n_clicks") for col in ["scan_id", "user", "sample", "scan_dim", "technique", "date", "status"]],
    State("sort-store", "data"),
    prevent_initial_call=True
)
def update_sort(*args):
    ctx = dash.callback_context
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
    col = triggered_id.replace("sort-", "")
    current = args[-1]
    if current["column"] == col:
        current["ascending"] = not current["ascending"]
    else:
        current = {"column": col, "ascending": True}
    return current

@dash.callback(
    Output("filter-store", "data"),
    Input("filter-scan_id", "value"),
    Input("filter-user", "value"),
    Input("filter-sample", "value"),
    Input("filter-scan_dim", "value"),
    Input("filter-technique", "value"),
    Input("filter-date", "value"),
    Input("filter-status", "value"),
    prevent_initial_call=True
)
def update_filter(scan_id, user, sample, scan_dim, technique, date, status):
    return {
        "scan_id": scan_id or "",
        "user": user or "",
        "sample": sample or "",
        "scan_dim": scan_dim or "",
        "technique": technique or "",
        "date": date or "",
        "status": status or ""
    }
