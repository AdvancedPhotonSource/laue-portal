import dash
from dash import html, dcc, callback, Input, Output, State, set_props, dash_table
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
import laue_portal.database.db_utils as db_utils
from laue_portal.database import db_utils, db_schema
from sqlalchemy.orm import Session
import laue_portal.components.navbar as navbar
from dash.exceptions import PreventUpdate
from sqlalchemy import func
from laue_portal.components.metadata_form import metadata_form, set_metadata_form_props, set_scan_accordions
from laue_portal.components.catalog_form import catalog_form, set_catalog_form_props
from laue_portal.components.form_base import _stack, _field
import urllib.parse
import pandas as pd
from datetime import datetime
import laue_portal.database.session_utils as session_utils
import math
import random
import plotly.graph_objects as go

import sys

dash.register_page(__name__, path="/scan")

# =============================================================================
# Helper: demo data for Role Plot tab
# =============================================================================

def build_demo_role_data():
    random.seed(7)
    nx, ny = 20, 20
    base_x = [i * 0.1 for i in range(nx)]
    base_y = [j * 0.1 for j in range(ny)]
    pts = []
    for j in range(ny):
        for i in range(nx):
            x = base_x[i] + (random.random() - 0.5) * 0.02
            y = base_y[j] + (random.random() - 0.5) * 0.02
            pts.append((x, y))
    N = len(pts)

    sampleX = [p[0] for p in pts]
    sampleY = [p[1] for p in pts]
    epoch = list(range(N))
    beam_current = [100 + 5 * math.sin(i / 40.0) + (random.random() - 0.5) * 0.8 for i in range(N)]

    def fI0(x, y, t): return 1000 + 200 * math.exp(-((x - 1.0)**2 + (y - 0.8)**2) / 0.15) + 5 * math.sin(t / 25.0)
    def fI1(x, y, t): return 800  + 150 * math.exp(-((x - 0.7)**2 + (y - 1.3)**2) / 0.10) + 4 * math.cos(t / 30.0)
    def fI2(x, y, t): return 600  + 120 * math.exp(-((x - 1.3)**2 + (y - 1.1)**2) / 0.08) + 3 * math.sin(t / 18.0)

    I0 = [fI0(sampleX[i], sampleY[i], epoch[i]) * (beam_current[i] / 100.0) for i in range(N)]
    I1 = [fI1(sampleX[i], sampleY[i], epoch[i]) * (beam_current[i] / 100.0) for i in range(N)]
    I2 = [fI2(sampleX[i], sampleY[i], epoch[i]) * (beam_current[i] / 100.0) for i in range(N)]

    return {
        "sampleX": sampleX,
        "sampleY": sampleY,
        "epoch": epoch,
        "beam_current": beam_current,
        "I0": I0,
        "I1": I1,
        "I2": I2,
    }


# =============================================================================
# Role Plot tab component
# =============================================================================

role_plot_tab = dbc.Tab(
    label="Role Plot",
    tab_id="tab-role",
    children=[
        html.Div(
            dbc.Row(
                [
                    dbc.Col(
                        dbc.InputGroup(
                            [
                                dbc.InputGroupText("MDA File"),
                                dbc.Input(id="mda_file", type="text"),
                            ],
                            className="w-100",
                        ),
                        className="flex-grow-1",
                        style={"minWidth": 0},
                    ),
                    dbc.Col(
                        dbc.Button(
                            "Load",
                            id="load-mda-file-btn",
                            color="secondary",
                            size="md",
                            style={"minWidth": "220px", "whiteSpace": "nowrap"},
                        ),
                        width="auto",
                        className="d-flex justify-content-end",
                    ),
                ],
                className="mb-3",
                align="center",
            )
        ),
        html.Div(
            dbc.Row(
                [
                    # LEFT: variable->role table
                    dbc.Col(
                        [
                            html.H6("Select roles"),
                            dash_table.DataTable(
                                id="var-role-table",
                                columns=[
                                    {"name": "Variable",      "id": "var",  "type": "text"},
                                    {"name": "X",             "id": "isX",  "type": "text", "presentation": "markdown"},
                                    {"name": "Y",             "id": "isY",  "type": "text", "presentation": "markdown"},
                                    {"name": "Z",             "id": "isZ",  "type": "text", "presentation": "markdown"},
                                    {"name": "Normalization", "id": "norm", "type": "text", "presentation": "markdown"},
                                ],
                                data=[
                                    {"var": "sampleX",      "isX": "✅", "isY": "☐", "isZ": "☐", "norm": "☐"},
                                    {"var": "sampleY",      "isX": "☐", "isY": "☐", "isZ": "☐", "norm": "☐"},
                                    {"var": "epoch",        "isX": "☐", "isY": "☐", "isZ": "☐", "norm": "☐"},
                                    {"var": "beam_current", "isX": "☐", "isY": "☐", "isZ": "☐", "norm": "☐"},
                                    {"var": "I0",           "isX": "☐", "isY": "✅", "isZ": "☐", "norm": "☐"},
                                    {"var": "I1",           "isX": "☐", "isY": "☐", "isZ": "✅", "norm": "☐"},
                                    {"var": "I2",           "isX": "☐", "isY": "☐", "isZ": "☐", "norm": "☐"},
                                ],
                                editable=False,
                                cell_selectable=True,
                                row_deletable=False,
                                style_table={"maxHeight": "520px", "overflowY": "auto"},
                                style_cell={"padding": "6px", "fontSize": 14, "textAlign": "left"},
                                style_header={"fontWeight": "600"},
                            ),
                            html.Small(
                                "Pick exactly one X and one Y. Z is optional (enables 2D colored scatter or 3D). "
                                "If a 'Normalization' is ✅, the chosen Y (1D) or Z (2D/3D) will be divided by that variable elementwise.",
                                className="text-muted",
                            ),
                        ],
                        width=5,
                    ),

                    # RIGHT: plot controls + plot
                    dbc.Col(
                        [
                            html.Label("Plot mode", className="form-label mt-3"),
                            dcc.RadioItems(
                                id="role-plot-mode",
                                options=[
                                    {"label": "1D (Y vs X)",         "value": "1d"},
                                    {"label": "2Dsurf (Z as color)", "value": "2dsurf"},
                                    {"label": "3D (X,Y,Z)",          "value": "3d"},
                                ],
                                value="2dsurf",
                                inputStyle={"marginRight": "6px"},
                                labelStyle={"display": "block", "marginBottom": "6px"},
                            ),
                            dcc.Graph(id="role-plot-graph", style={"height": "520px"}),
                        ],
                        width=7,
                    ),
                ],
                className="g-3",
            ),
            className="p-2",
        ),
    ],
)

# =============================================================================
# Layout
# =============================================================================

layout = html.Div([
    navbar.navbar,
    dcc.Location(id='url-scan-page', refresh=False),
    dcc.Store(id="plot-data"),
    dcc.Store(id="role-data", data=build_demo_role_data()),
    dbc.Container(
        id='scan-content-container', fluid=True, className="mt-4",
        children=[
            dbc.Alert(
                id="alert-note-submit",
                dismissable=True,
                duration=4000,
                is_open=False,
            ),
            html.H1(id='scan-header',
                     style={"display": "flex", "gap": "10px", "align-items": "baseline", "flexWrap": "wrap"},
                     className="mb-4"),
            html.Div(
                [
                    # Scan ID header (above tabs)
                    html.H1(
                        children=["Scan ID: ", html.Div(id="ScanID_print")],
                        style={"display": "flex", "gap": "10px", "align-items": "flex-end"},
                        className="mb-4",
                    ),

                    # =========================================================
                    # Tabs
                    # =========================================================
                    dbc.Tabs(
                        [
                            # -------------------------------------------------
                            # Tab 1: Scan Info
                            # -------------------------------------------------
                            dbc.Tab(
                                label="Scan Info",
                                children=[
                                    html.Div(
                                        [
                                            dbc.Row([
                                                dbc.Col([
                                                    html.P(children=[html.Strong("User: "), html.Div(id="User_print")],
                                                           style={"display": "flex", "gap": "5px", "align-items": "flex-end"}),
                                                    html.P(children=[html.Strong("Date: "), html.Div(id="Date_print")],
                                                           style={"display": "flex", "gap": "5px", "align-items": "flex-end"}),
                                                    html.P(children=[html.Strong("Scan Dimensions: "), html.Div(id="ScanDims_print")],
                                                           style={"display": "flex", "gap": "5px", "align-items": "flex-end"}),
                                                    html.P(children=[html.Strong("Scan Type: "), html.Div(id="Technique_print")],
                                                           style={"display": "flex", "gap": "5px", "align-items": "flex-end"}),
                                                    html.P(children=[html.Strong("Aperture: "), html.Div(id="Aperture_print")],
                                                           style={"display": "flex", "gap": "5px", "align-items": "flex-end"}),
                                                    html.P(children=[html.Strong("Sample: "), html.Div(id="Sample_print")],
                                                           style={"display": "flex", "gap": "5px", "align-items": "flex-end"}),
                                                    html.P(children=[html.Strong("Data Folder: "), html.Div(id="File_folder_print")],
                                                           style={"display": "flex", "gap": "5px", "align-items": "flex-end"}),
                                                ],
                                                    className="flex-grow-1",
                                                    style={"minWidth": 0},
                                                    width="auto"),

                                                dbc.Col(id='positioner-info-div',
                                                        className="flex-grow-1",
                                                        style={"minWidth": 0},
                                                        width="auto"),
                                            ]),

                                            dbc.Row([
                                                dbc.Col([
                                                    html.P(html.Strong("Note:")),
                                                    dbc.Button("Add to DB", id="save-note-btn", color="success", size="sm", className="mt-2")
                                                ], width="auto", align="start"),
                                                dbc.Col(
                                                    dbc.Textarea(
                                                        id="Note_print",
                                                        style={"width": "100%", "minHeight": "100px"},
                                                    )
                                                )
                                            ], className="mb-3", align="start"),
                                        ],
                                        className="custom-tab-content",
                                    )
                                ],
                            ),

                            # -------------------------------------------------
                            # Tab 2: Metadata
                            # -------------------------------------------------
                            dbc.Tab(
                                label="Metadata",
                                children=[
                                    html.Div(
                                        [
                                            html.H2("Metadata Details", className="mt-4 mb-3"),
                                            metadata_form,
                                        ],
                                        className="custom-tab-content",
                                    )
                                ],
                            ),

                            # -------------------------------------------------
                            # Tab 3: Catalog data
                            # -------------------------------------------------
                            dbc.Tab(
                                label="Catalog data",
                                children=[
                                    html.Div(
                                        [
                                            html.Div(
                                                [
                                                    html.H2("Catalog Details", className="mt-4 mb-3"),
                                                    dbc.Button(
                                                        "Save Changes to Catalog",
                                                        id="save-catalog-btn",
                                                        color="success",
                                                        className="mt-4 mb-3",
                                                        style={'margin-left': '30px'},
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
                                        ],
                                        className="custom-tab-content",
                                    )
                                ],
                            ),

                            # -------------------------------------------------
                            # Tab 4: Plot
                            # -------------------------------------------------
                            dbc.Tab(
                                label="Plot",
                                tab_id="tab-plot",
                                children=[
                                    html.Div([
                                        dbc.Row([
                                            dbc.Col([
                                                html.Label("Plot type", className="form-label"),
                                                dcc.Dropdown(
                                                    id="plot-type",
                                                    options=[
                                                        {"label": "1D", "value": "1d"},
                                                        {"label": "2Dsurf", "value": "2dsurf"},
                                                        {"label": "3D", "value": "3d"},
                                                    ],
                                                    value="1d",
                                                    clearable=False,
                                                ),
                                            ], width=3),
                                            dbc.Col([
                                                html.Label("X axis", className="form-label"),
                                                dcc.Dropdown(id="plot-x", placeholder="Select X"),
                                            ], width=3),
                                            dbc.Col([
                                                html.Label("Y axis", className="form-label"),
                                                dcc.Dropdown(id="plot-y", placeholder="Select Y"),
                                            ], width=3),
                                            dbc.Col([
                                                html.Label("Z axis", className="form-label"),
                                                dcc.Dropdown(id="plot-z", placeholder="Select Z"),
                                            ], width=3),
                                        ], className="g-2 mb-2"),
                                        dcc.Graph(id="plot-graph", style={"height": "520px"}),
                                        html.Small("Z is used for 2Dsurf (as color) and 3D; ignored for 1D.", className="text-muted"),
                                    ])
                                ],
                            ),

                            # -------------------------------------------------
                            # Tab 5: Role Plot
                            # -------------------------------------------------
                            role_plot_tab,
                        ]
                    ),

                    # Recon Table (conditionally visible based on technique)
                    html.Div(
                        id="recon-card-wrapper",
                        children=[
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
                                        defaultColDef={"filter": True},
                                        dashGridOptions={
                                            "pagination": True,
                                            "paginationPageSize": 20,
                                            "domLayout": 'autoHeight',
                                            "rowSelection": 'multiple',
                                            "suppressRowClickSelection": True,
                                            "animateRows": False,
                                            "rowHeight": 32,
                                        },
                                        className="ag-theme-alpine",
                                    )
                                ], className="p-0"),
                            ], className="mb-4 shadow-sm border"),
                        ],
                    ),

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
                                defaultColDef={"filter": True},
                                dashGridOptions={
                                    "pagination": True,
                                    "paginationPageSize": 20,
                                    "domLayout": 'autoHeight',
                                    "rowSelection": 'multiple',
                                    "suppressRowClickSelection": True,
                                    "animateRows": False,
                                    "rowHeight": 32,
                                },
                                className="ag-theme-alpine",
                            )
                        ], className="p-0"),
                    ], className="mb-4 shadow-sm border"),
                ],
                style={'width': '100%', 'overflow-x': 'auto'},
            ),
        ],
    ),
])


# =============================================================================
# Clientside callbacks
# =============================================================================

# Hide/show Aperture field based on "depth" in Technique_print
dash.clientside_callback(
    """
    function(tech_children, current_style) {
        const ap = document.getElementById('Aperture_print');
        if (!ap) { return current_style || {}; }

        const p = ap.closest('p');
        const txt = Array.isArray(tech_children) ? tech_children.join(' ') : (tech_children || '');
        const hasDepth = txt.toLowerCase().includes('depth');

        if (p) {
            p.style.display = hasDepth ? 'flex' : 'none';
        }
        return current_style || {};
    }
    """,
    Output('Aperture_print', 'style'),
    Input('Technique_print', 'children'),
    State('Aperture_print', 'style'),
)

# Hide/show recon-card-wrapper based on "depth" in Technique_print
dash.clientside_callback(
    """
    function(tech_children, current_style) {
        const txt = Array.isArray(tech_children) ? tech_children.join(' ')
                   : (tech_children || '');
        const hasDepth = txt.toLowerCase().includes('depth');

        const style = Object.assign({}, current_style || {});
        style.display = hasDepth ? 'block' : 'none';
        return style;
    }
    """,
    Output('recon-card-wrapper', 'style'),
    Input('Technique_print', 'children'),
    State('recon-card-wrapper', 'style'),
)

# Toggle checkboxes in var-role-table
dash.clientside_callback(
    """
    function(active_cell, rows) {
        if (!active_cell || !rows) return rows || [];
        const r = active_cell.row;
        const c = active_cell.column_id;
        if (!["isX","isY","isZ","norm"].includes(c)) return rows;

        const out = JSON.parse(JSON.stringify(rows));

        const clearCol = (col) => { for (let i=0; i<out.length; ++i) out[i][col] = "☐"; };
        const isChecked = (row, col) => row && row[col] === "✅";

        if (c === "isX" || c === "isY") {
            clearCol(c);
            out[r][c] = "✅";
        } else if (c === "norm") {
            if (isChecked(out[r], "norm")) {
                clearCol("norm");
            } else {
                clearCol("norm");
                out[r]["norm"] = "✅";
            }
        } else if (c === "isZ") {
            if (isChecked(out[r], "isZ")) {
                out[r]["isZ"] = "☐";
            } else {
                clearCol("isZ");
                out[r]["isZ"] = "✅";
            }
        }
        return out;
    }
    """,
    Output("var-role-table", "data"),
    Input("var-role-table", "active_cell"),
    State("var-role-table", "data"),
)


# =============================================================================
# Plot tab callback
# =============================================================================

@callback(
    Output("plot-x", "options"),
    Output("plot-x", "value"),
    Output("plot-y", "options"),
    Output("plot-y", "value"),
    Output("plot-z", "options"),
    Output("plot-z", "value"),
    Output("plot-graph", "figure"),
    Input("plot-type", "value"),
    Input("plot-x", "value"),
    Input("plot-y", "value"),
    Input("plot-z", "value"),
    prevent_initial_call=False,
)
def render_flex_plot(plot_type, x_sel, y_sel, z_sel):
    import numpy as np

    n = 60
    xv = np.linspace(-3, 3, n)
    yv = np.linspace(-2, 2, n)
    Xg, Yg = np.meshgrid(xv, yv)
    Zg = np.exp(-(Xg**2 + Yg**2)) * np.cos(2*Xg) * np.sin(2*Yg)
    df = pd.DataFrame({
        "X": Xg.ravel(),
        "Y": Yg.ravel(),
        "Z": Zg.ravel(),
        "T": np.linspace(0, 10, n*n),
    })

    num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    opts = [{"label": c, "value": c} for c in num_cols]

    def pick(idx, fallback=None):
        if len(num_cols) > idx:
            return num_cols[idx]
        return fallback if (fallback in num_cols) else (num_cols[0] if num_cols else None)

    x = x_sel if x_sel in num_cols else pick(0)
    y = y_sel if y_sel in num_cols else pick(1, x)
    z = z_sel if z_sel in num_cols else pick(2, y)

    fig = go.Figure()

    if plot_type == "1d":
        if x and y:
            dft = df[[x, y]].dropna().sort_values(by=x)
            fig.add_trace(go.Scatter(
                x=dft[x], y=dft[y],
                mode="lines+markers",
                name=f"{y} vs {x}",
                hovertemplate=f"{x}: %{{x}}<br>{y}: %{{y}}<extra></extra>",
            ))
            fig.update_layout(
                xaxis_title=x, yaxis_title=y,
                margin=dict(l=50, r=30, t=40, b=50),
            )

    elif plot_type == "2dsurf":
        if x and y and z:
            dft = df[[x, y, z]].dropna()
            try:
                dft2 = dft.copy()
                dft2["_xr"] = dft2[x].round(8)
                dft2["_yr"] = dft2[y].round(8)
                piv = dft2.pivot_table(index="_yr", columns="_xr", values=z, aggfunc="mean")
                Xvals = piv.columns.values
                Yvals = piv.index.values
                Zgrid = piv.values
                fig.add_trace(go.Heatmap(
                    x=Xvals, y=Yvals, z=Zgrid,
                    colorbar=dict(title=z),
                    hovertemplate=f"{x}: %{{x}}<br>{y}: %{{y}}<br>{z}: %{{z}}<extra></extra>",
                ))
                fig.update_layout(
                    xaxis_title=x, yaxis_title=y,
                    margin=dict(l=60, r=60, t=40, b=60),
                )
            except Exception:
                fig.add_trace(go.Scattergl(
                    x=dft[x], y=dft[y],
                    mode="markers",
                    marker=dict(color=dft[z], colorscale="Viridis", showscale=True,
                                colorbar=dict(title=z), size=6, opacity=0.8),
                    name=f"{z} on {x},{y}",
                    hovertemplate=f"{x}: %{{x}}<br>{y}: %{{y}}<br>{z}: %{{marker.color}}<extra></extra>",
                ))
                fig.update_layout(
                    xaxis_title=x, yaxis_title=y,
                    margin=dict(l=60, r=60, t=40, b=60),
                )

    elif plot_type == "3d":
        if x and y and z:
            dft = df[[x, y, z]].dropna()
            fig.add_trace(go.Scatter3d(
                x=dft[x], y=dft[y], z=dft[z],
                mode="markers",
                marker=dict(size=3.5, opacity=0.85),
                name=f"{z} vs {x},{y}",
                hovertemplate=f"{x}: %{{x}}<br>{y}: %{{y}}<br>{z}: %{{z}}<extra></extra>",
            ))
            fig.update_layout(
                scene=dict(xaxis_title=x, yaxis_title=y, zaxis_title=z),
                margin=dict(l=0, r=0, t=40, b=0),
            )

    if not fig.data:
        fig.update_layout(
            annotations=[dict(text="Select columns to plot", showarrow=False,
                              x=0.5, y=0.5, xref="paper", yref="paper")],
            margin=dict(l=50, r=30, t=40, b=50),
        )

    return opts, x, opts, y, opts, z, fig


# =============================================================================
# Role Plot callback
# =============================================================================

@callback(
    Output("role-plot-graph", "figure"),
    Input("role-plot-mode", "value"),
    Input("var-role-table", "data"),
    State("role-data", "data"),
)
def render_role_plot(mode, rows, data):
    fig = go.Figure()
    if not rows or not data:
        fig.update_layout(title="No data")
        return fig

    def pick(col):
        for row in rows:
            if row.get(col) == "✅":
                return row.get("var")
        return None

    X = pick("isX")
    Y = pick("isY")
    Z = pick("isZ")
    NORM = pick("norm")

    if not X or not Y:
        fig.update_layout(title="Pick at least one X and one Y")
        return fig

    x = data.get(X); y = data.get(Y)
    z = data.get(Z) if Z else None
    n = data.get(NORM) if NORM else None

    if not isinstance(x, list) or not isinstance(y, list) or len(x) != len(y):
        fig.update_layout(title="X and Y must be lists of equal length")
        return fig

    def safe_div(a, b):
        if b is None: return a
        L = min(len(a or []), len(b or []))
        out = []
        for i in range(L):
            denom = b[i]
            out.append(a[i] / denom if denom not in (0, None, 0.0) else None)
        return out

    y_geom = y if (isinstance(y, list) and len(y) == len(x)) else (data.get("sampleY") or data.get("epoch"))

    if mode == "1d":
        y_plot = safe_div(y, n)
        fig.add_trace(go.Scatter(x=x, y=y_plot, mode="lines+markers",
                                 name=Y + (f" / {NORM}" if NORM else "")))
        fig.update_layout(
            xaxis_title=X,
            yaxis_title=Y + (f" / {NORM}" if NORM else ""),
            title="1D: Y vs X",
            margin=dict(l=60, r=40, t=40, b=60),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        )
        return fig

    if mode == "2dsurf":
        if z is None:
            fig.add_trace(go.Scatter(
                x=x, y=y_geom, mode="markers",
                marker=dict(size=6, opacity=0.85),
                name=f"{Y} vs {X}",
            ))
            fig.update_layout(
                xaxis_title=X, yaxis_title=(pick('isY') or 'Y'),
                title="2D scatter (no Z selected for color)",
                margin=dict(l=60, r=60, t=40, b=60),
            )
            return fig

        z_plot = safe_div(z, n)
        fig.add_trace(go.Scatter(
            x=x, y=y_geom, mode="markers",
            marker=dict(
                size=7, opacity=0.85,
                color=z_plot, colorscale="Viridis", showscale=True,
                colorbar=dict(title=Z + (f"/{NORM}" if NORM else "")),
            ),
            name=Z + (f" / {NORM}" if NORM else ""),
        ))
        fig.update_layout(
            xaxis_title=X, yaxis_title=(pick('isY') or 'Y'),
            title="2Dsurf: colored scatter (non-grid positions)",
            margin=dict(l=60, r=60, t=40, b=60),
        )
        return fig

    if mode == "3d":
        if z is None:
            y_plot = safe_div(y, n)
            fig.add_trace(go.Scatter(x=x, y=y_plot, mode="lines+markers",
                                     name=Y + (f" / {NORM}" if NORM else "")))
            fig.update_layout(
                xaxis_title=X,
                yaxis_title=Y + (f" / {NORM}" if NORM else ""),
                title="3D requested, missing Z -> 1D fallback",
                margin=dict(l=60, r=40, t=40, b=60),
            )
            return fig

        z_plot = safe_div(z, n)
        fig.add_trace(go.Scatter3d(
            x=x, y=y_geom, z=z_plot, mode="markers",
            marker=dict(size=3.5, opacity=0.85,
                        color=z_plot, colorscale="Viridis", showscale=True,
                        colorbar=dict(title=Z + (f"/{NORM}" if NORM else ""))),
            name=Z + (f" / {NORM}" if NORM else ""),
        ))
        fig.update_layout(
            scene=dict(
                xaxis_title=X,
                yaxis_title=(pick('isY') or 'Y'),
                zaxis_title=Z + (f" / {NORM}" if NORM else ""),
            ),
            title="3D: X, Y, Z",
            margin=dict(l=0, r=0, t=40, b=0),
        )
        return fig

    return fig


# =============================================================================
# Scan Info
# =============================================================================

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
    motor_groups = []
    for scan in scans:
        for attr_name in dir(scan):
            if attr_name.startswith('scan_positioner') and attr_name.endswith('_PV'):
                pv_value = getattr(scan, attr_name, None)
                if pv_value:
                    motor_group = db_utils.find_motor_group(pv_value)
                    motor_groups.append(motor_group)

    all_motors_str = "; ".join(motor_groups) if motor_groups else none

    if not motor_groups:
        return none, all_motors_str

    motor_groups_lower = [g.lower() for g in motor_groups]
    sample_count = motor_groups_lower.count("sample")

    seen_groups = {none}
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
    set_props('ScanID_print', {'children': [metadata.scanNumber]})
    set_props('User_print', {'children': [metadata.user_name]})

    time_value = metadata.time
    if isinstance(time_value, datetime):
        time_value = time_value.strftime('%Y-%m-%d, %H:%M:%S')
    set_props('Date_print', {'children': [time_value]})
    set_props('ScanDims_print', {'children': [f"{len([i for i, scan in enumerate(scans)])}D"]})

    filtered_str, all_motors_str = build_technique_strings(scans)
    technique_str = f"{filtered_str}"

    set_props('Technique_print', {'children': [technique_str]})
    set_props('Aperture_print', {'children': [catalog.aperture.title()]})
    set_props('Sample_print', {'children': [catalog.sample_name]})
    set_props('Note_print', {'value': "submit indexing"})
    set_props("File_folder_print", {'children': [catalog.filefolder]})
    set_props("mda_file", {'value': metadata.mda_file, 'readonly': False})

    npts_label = "Points"
    cpt_label = "Completed"
    positioner_info = []
    motor_group_totals = {}
    if scans:
        for i, scan in enumerate(scans):
            motor_group_totals = db_utils.update_motor_group_totals(motor_group_totals, scan)

            table_rows = []
            for PV_i in range(1, 5):
                pv_attr = f'scan_positioner{PV_i}_PV'
                pos_attr = f'scan_positioner{PV_i}'

                if getattr(scan, pv_attr, None):
                    motor_group = db_utils.find_motor_group(getattr(scan, pv_attr))
                    start_val, stop_val, step_val = getattr(scan, pos_attr, '  ').split()

                    table_rows.append(
                        html.Tr([
                            html.Td(html.Strong(motor_group.capitalize()), style={"whiteSpace": "nowrap"}),
                            html.Td(start_val, style={"textAlign": "right"}),
                            html.Td(stop_val,  style={"textAlign": "right"}),
                            html.Td(step_val,  style={"textAlign": "right"}),
                        ])
                    )

            if table_rows:
                completed = scan.scan_cpt
                total = scan.scan_npts

                header_row = dbc.Row(
                    [
                        dbc.Col(
                            html.Div([
                                html.Strong(f"Dim {scan.scan_dim} | "),
                                html.Strong(f"Completed {completed}/{total}"),
                            ]),
                            width="auto",
                            className="px-2",
                            style={"minWidth": "fit-content"},
                        ),
                        dbc.Col(None, className="flex-grow-1"),
                        dbc.Col(html.Strong("Start"), width=2, className="text-end"),
                        dbc.Col(html.Strong("End"),   width=2, className="text-end"),
                        dbc.Col(html.Strong("Step"),  width=2, className="text-end"),
                    ],
                    className="bg-light py-1 mt-2",
                )

                data_rows = []
                for PV_i in range(1, 5):
                    pv_attr = f'scan_positioner{PV_i}_PV'
                    pos_attr = f'scan_positioner{PV_i}'

                    if getattr(scan, pv_attr, None):
                        motor_group = db_utils.find_motor_group(getattr(scan, pv_attr))
                        start_val, stop_val, step_val = getattr(scan, pos_attr, '  ').split()

                        data_rows.append(
                            dbc.Row(
                                [
                                    dbc.Col(
                                        html.Strong(motor_group.capitalize()),
                                        width="auto",
                                        className="px-2",
                                        style={"minWidth": "fit-content"},
                                    ),
                                    dbc.Col(None, className="flex-grow-1"),
                                    dbc.Col(start_val, width=2, className="text-end", style={"fontFamily": "monospace"}),
                                    dbc.Col(stop_val,  width=2, className="text-end", style={"fontFamily": "monospace"}),
                                    dbc.Col(step_val,  width=2, className="text-end", style={"fontFamily": "monospace"}),
                                ],
                                className="py-1 scan-pos-table",
                            )
                        )

                positioner_info.append(html.Div([header_row] + data_rows, className="mb-2"))

    total_points_fields = []
    for motor_group in db_utils.MOTOR_GROUPS:
        db_points = getattr(metadata, f'motorGroup_{motor_group}_npts_total', None)
        db_completed = getattr(metadata, f'motorGroup_{motor_group}_cpt_total', None)

        if db_points is not None:
            total_points_fields.append(
                _stack([
                    html.P(children=[html.Strong(f"{motor_group.capitalize()} {npts_label}: "), html.Div(db_points)],
                           style={"display": "flex", "gap": "5px", "align-items": "flex-end"}),
                    html.Span("|", className="mb-3"),
                    html.P(children=[html.Strong(f"{motor_group.capitalize()} {cpt_label}: "), html.Div(db_completed)],
                           style={"display": "flex", "gap": "5px", "align-items": "flex-end"}),
                ])
            )

            if motor_group in motor_group_totals:
                if (motor_group_totals[motor_group]['points'] != db_points or
                    motor_group_totals[motor_group]['completed'] != db_completed):
                    set_props('alert-upload', {'is_open': True, 'children': f'Warning: Mismatch in {motor_group} totals.', 'color': 'warning'})

    set_props('positioner-info-div', {'children': positioner_info})


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
                        scan_rows = list(scan_data)
                        set_scan_accordions(scan_rows, read_only=True)
                    else:
                        scan_rows = []
                    set_metadata_form_props(metadata_data, scan_rows, read_only=True)
                    if catalog_data:
                        set_catalog_form_props(catalog_data, read_only=False)
                        set_scaninfo_form_props(metadata_data, scan_rows, catalog_data, read_only=True)

        except Exception as e:
            print(f"Error loading scan data: {e}")


# =============================================================================
# Recon Table
# =============================================================================

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
    'recon_id': 'Recon ID',
    'percent_brightest': 'Pixels',
    'submit_time': 'Date',
}

CUSTOM_COLS_Recon_dict = {
    1: [
        db_schema.Catalog.aperture,
        db_schema.Recon.calib_id,
    ],
    4: [
        db_schema.Recon.scanPointslen,
        db_schema.Metadata.motorGroup_sample_cpt_total,
    ],
    5: [
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
    'wirerecon_id': 'Recon ID (Wire)',
    'percent_brightest': 'Pixels',
    'submit_time': 'Date',
}

CUSTOM_COLS_WireRecon_dict = {
    1: [
        db_schema.Catalog.aperture,
    ],
    4: [
        db_schema.WireRecon.scanPointslen,
        db_schema.Metadata.motorGroup_sample_cpt_total,
    ],
    5: [
        db_schema.WireRecon.depth_start,
        db_schema.WireRecon.depth_end,
    ],
}

ALL_COLS_WireRecon = VISIBLE_COLS_WireRecon + [db_schema.WireRecon.scanNumber] + [ii for i in CUSTOM_COLS_WireRecon_dict.values() for ii in i]


def _get_scan_recons(scan_id):
    try:
        scan_id = int(scan_id)
        with Session(session_utils.get_engine()) as session:
            aperture = pd.read_sql(session.query(db_schema.Catalog.aperture).filter(db_schema.Catalog.scanNumber == scan_id).statement, session.bind).at[0, 'aperture']
            aperture = str(aperture).lower()

            if 'wire' in aperture:
                scan_recons = pd.read_sql(session.query(
                    *ALL_COLS_WireRecon,
                )
                    .join(db_schema.Metadata.catalog_)
                    .join(db_schema.Metadata.wirerecon_)
                    .join(db_schema.Job, db_schema.WireRecon.job_id == db_schema.Job.job_id)
                    .outerjoin(db_schema.SubJob, db_schema.Job.job_id == db_schema.SubJob.job_id)
                    .filter(db_schema.Metadata.scanNumber == scan_id)
                    .group_by(*ALL_COLS_WireRecon)
                    .statement, session.bind)

                cols = []
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
                        'suppressMenuHide': True,
                    }
                    if field_key == 'wirerecon_id':
                        col_def['cellRenderer'] = 'WireReconLinkRenderer'
                    elif field_key in ['scanNumber', 'dataset_id']:
                        col_def['cellRenderer'] = 'DatasetIdScanLinkRenderer'
                    elif field_key == 'scanNumber':
                        col_def['cellRenderer'] = 'ScanLinkRenderer'
                    elif field_key in ['submit_time', 'start_time', 'finish_time']:
                        col_def['cellRenderer'] = 'DateFormatter'
                    elif field_key == 'status':
                        col_def['cellRenderer'] = 'StatusRenderer'
                    cols.append(col_def)

                for col_num in CUSTOM_COLS_WireRecon_dict.keys():
                    if col_num == 1:
                        col_def = {
                            'headerName': 'Calib ID',
                            'valueGetter': {"function": "params.data.aperture + ': ' + params.data.calib_id"},
                        }
                    elif col_num == 4:
                        col_def = {
                            'headerName': 'Points',
                            'valueGetter': {"function": "params.data.scanPointslen + ' / ' + params.data.motorGroup_sample_cpt_total"},
                        }
                    elif col_num == 5:
                        col_def = {
                            'headerName': 'Depth [µm]',
                            'valueGetter': {"function": "params.data.depth_start + ' to ' + params.data.depth_end"},
                        }
                    col_def.update({
                        'filter': True,
                        'sortable': True,
                        'resizable': True,
                        'suppressMenuHide': True,
                    })
                    cols.insert(col_num, col_def)

                return cols, scan_recons.to_dict('records')

            else:
                scan_recons = pd.read_sql(session.query(
                    *ALL_COLS_Recon,
                )
                    .join(db_schema.Metadata.catalog_)
                    .join(db_schema.Metadata.recon_)
                    .join(db_schema.Metadata.scan_)
                    .join(db_schema.Job, db_schema.Recon.job_id == db_schema.Job.job_id)
                    .outerjoin(db_schema.SubJob, db_schema.Job.job_id == db_schema.SubJob.job_id)
                    .filter(db_schema.Metadata.scanNumber == scan_id)
                    .group_by(*ALL_COLS_Recon)
                    .statement, session.bind)

                cols = []
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
                        'suppressMenuHide': True,
                    }
                    if field_key == 'recon_id':
                        col_def['cellRenderer'] = 'ReconLinkRenderer'
                    elif field_key in ['scanNumber', 'dataset_id']:
                        col_def['cellRenderer'] = 'DatasetIdScanLinkRenderer'
                    elif field_key == 'scanNumber':
                        col_def['cellRenderer'] = 'ScanLinkRenderer'
                    elif field_key in ['submit_time', 'start_time', 'finish_time']:
                        col_def['cellRenderer'] = 'DateFormatter'
                    elif field_key == 'status':
                        col_def['cellRenderer'] = 'StatusRenderer'
                    cols.append(col_def)

                for col_num in CUSTOM_COLS_Recon_dict.keys():
                    if col_num == 1:
                        col_def = {
                            'headerName': 'Method',
                            'valueGetter': {"function": "params.data.aperture + ', calib: ' + params.data.calib_id"},
                        }
                    elif col_num == 4:
                        col_def = {
                            'headerName': 'Points',
                            'valueGetter': {"function": "params.data.scanPointslen + ' / ' + params.data.motorGroup_sample_cpt_total"},
                        }
                    elif col_num == 5:
                        col_def = {
                            'headerName': 'Depth [µm]',
                            'valueGetter': {"function":
                                "1000*(params.data.geo_source_grid[0] + params.data.geo_source_offset) "
                                "+ ' to ' + "
                                "1000*(params.data.geo_source_grid[1] + params.data.geo_source_offset)"
                            },
                        }
                    col_def.update({
                        'filter': True,
                        'sortable': True,
                        'resizable': True,
                        'suppressMenuHide': True,
                    })
                    cols.insert(col_num, col_def)

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


# =============================================================================
# Peak Indexing Table
# =============================================================================

VISIBLE_COLS_PeakIndex = [
    db_schema.PeakIndex.peakindex_id,
    db_schema.PeakIndex.scanPointslen,
    db_schema.PeakIndex.author,
    db_schema.PeakIndex.boxsize,
    db_schema.Job.submit_time,
    db_schema.Job.status,
    db_schema.PeakIndex.notes,
]

CUSTOM_HEADER_NAMES_PeakIndex = {
    'peakindex_id': 'Index ID',
    'scanPointslen': 'Points',
    'boxsize': 'Box',
    'submit_time': 'Date',
}

CUSTOM_COLS_PeakIndex_dict = {
    5: [
        db_schema.PeakIndex.crystFile,
    ],
    6: [
        db_schema.PeakIndex.scanPointslen.label('PeakIndex_scanPointslen'),
        db_schema.PeakIndex.depthRangelen,
        db_schema.Metadata.motorGroup_sample_cpt_total,
        db_schema.Metadata.motorGroup_depth_cpt_total,
    ],
}

ALL_COLS_PeakIndex = VISIBLE_COLS_PeakIndex + [db_schema.PeakIndex.scanNumber] + [ii for i in CUSTOM_COLS_PeakIndex_dict.values() for ii in i]

VISIBLE_COLS_Recon_PeakIndex = [
    db_schema.PeakIndex.peakindex_id,
    db_schema.PeakIndex.recon_id,
    db_schema.PeakIndex.scanPointslen,
    db_schema.PeakIndex.author,
    db_schema.PeakIndex.boxsize,
    db_schema.Job.submit_time,
    db_schema.Job.status,
    db_schema.PeakIndex.notes,
]

CUSTOM_HEADER_NAMES_Recon_PeakIndex = {
    'peakindex_id': 'Index ID',
    'recon_id': 'Recon ID',
    'scanPointslen': 'Points',
    'boxsize': 'Box',
    'submit_time': 'Date',
}

CUSTOM_COLS_Recon_PeakIndex_dict = {
    6: [
        db_schema.PeakIndex.crystFile,
    ],
    7: [
        db_schema.PeakIndex.scanPointslen.label('PeakIndex_scanPointslen'),
        db_schema.PeakIndex.depthRangelen,
        db_schema.Metadata.motorGroup_depth_cpt_total,
        db_schema.Recon.scanPointslen.label('Recon_scanPointslen'),
    ],
}

ALL_COLS_Recon_PeakIndex = VISIBLE_COLS_Recon_PeakIndex + [db_schema.PeakIndex.scanNumber] + [ii for i in CUSTOM_COLS_Recon_PeakIndex_dict.values() for ii in i]

VISIBLE_COLS_WireRecon_PeakIndex = [
    db_schema.PeakIndex.peakindex_id,
    db_schema.PeakIndex.wirerecon_id,
    db_schema.PeakIndex.scanPointslen,
    db_schema.PeakIndex.author,
    db_schema.PeakIndex.boxsize,
    db_schema.Job.submit_time,
    db_schema.Job.status,
    db_schema.PeakIndex.notes,
]

CUSTOM_HEADER_NAMES_WireRecon_PeakIndex = {
    'peakindex_id': 'Index ID',
    'wirerecon_id': 'Recon ID (Wire)',
    'scanPointslen': 'Points',
    'boxsize': 'Box',
    'submit_time': 'Date',
}

CUSTOM_COLS_WireRecon_PeakIndex_dict = {
    6: [
        db_schema.PeakIndex.crystFile,
    ],
    7: [
        db_schema.PeakIndex.scanPointslen.label('PeakIndex_scanPointslen'),
        db_schema.PeakIndex.depthRangelen,
        db_schema.Metadata.motorGroup_depth_cpt_total,
        db_schema.WireRecon.scanPointslen.label('WireRecon_scanPointslen'),
    ],
}

ALL_COLS_WireRecon_PeakIndex = VISIBLE_COLS_WireRecon_PeakIndex + [db_schema.PeakIndex.scanNumber] + [ii for i in CUSTOM_COLS_WireRecon_PeakIndex_dict.values() for ii in i]


def _get_scan_peakindexings(scan_id):
    try:
        scan_id = int(scan_id)
        with Session(session_utils.get_engine()) as session:
            aperture = pd.read_sql(session.query(db_schema.Catalog.aperture).filter(db_schema.Catalog.scanNumber == scan_id).statement, session.bind).at[0, 'aperture']
            aperture = str(aperture).lower()

            if aperture == 'none':
                scan_peakindexings = pd.read_sql(session.query(
                    *ALL_COLS_PeakIndex,
                )
                    .join(db_schema.Metadata, db_schema.PeakIndex.scanNumber == db_schema.Metadata.scanNumber)
                    .join(db_schema.Job, db_schema.PeakIndex.job_id == db_schema.Job.job_id)
                    .filter(db_schema.PeakIndex.scanNumber == scan_id)
                    .group_by(*ALL_COLS_PeakIndex)
                    .statement, session.bind)

                cols = []
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
                        'suppressMenuHide': True,
                    }
                    if field_key == 'peakindex_id':
                        col_def['cellRenderer'] = 'PeakIndexLinkRenderer'
                    elif field_key in ['scanNumber', 'dataset_id']:
                        col_def['cellRenderer'] = 'DatasetIdScanLinkRenderer'
                    elif field_key == 'scanNumber':
                        col_def['cellRenderer'] = 'ScanLinkRenderer'
                    elif field_key in ['submit_time', 'start_time', 'finish_time']:
                        col_def['cellRenderer'] = 'DateFormatter'
                    elif field_key == 'status':
                        col_def['cellRenderer'] = 'StatusRenderer'
                    cols.append(col_def)

                for col_num in CUSTOM_COLS_PeakIndex_dict.keys():
                    if col_num == 5:
                        col_def = {
                            'headerName': 'Structure',
                            'valueGetter': {"function": "params.data.crystFile.slice(params.data.crystFile.lastIndexOf('/') + 1, params.data.crystFile.lastIndexOf('.'))"},
                        }
                    if col_num == 6:
                        col_def = {
                            'headerName': 'Frames',
                            'valueGetter': {"function": "params.data.PeakIndex_scanPointslen * params.data.depthRangelen + ' / ' + params.data.motorGroup_sample_cpt_total * params.data.motorGroup_depth_cpt_total"},
                        }
                    col_def.update({
                        'filter': True,
                        'sortable': True,
                        'resizable': True,
                        'suppressMenuHide': True,
                    })
                    cols.insert(col_num, col_def)

                return cols, scan_peakindexings.to_dict('records')

            elif 'wire' in aperture:
                scan_peakindexings = pd.read_sql(session.query(
                    *ALL_COLS_WireRecon_PeakIndex,
                )
                    .join(db_schema.Metadata, db_schema.PeakIndex.scanNumber == db_schema.Metadata.scanNumber)
                    .join(db_schema.Job, db_schema.PeakIndex.job_id == db_schema.Job.job_id)
                    .outerjoin(db_schema.WireRecon, db_schema.PeakIndex.wirerecon_id == db_schema.WireRecon.wirerecon_id)
                    .filter(db_schema.PeakIndex.scanNumber == scan_id)
                    .group_by(*ALL_COLS_PeakIndex)
                    .statement, session.bind)

                cols = []
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
                        'suppressMenuHide': True,
                    }
                    if field_key == 'peakindex_id':
                        col_def['cellRenderer'] = 'PeakIndexLinkRenderer'
                    elif field_key == 'recon_id':
                        col_def['cellRenderer'] = 'WireReconLinkRenderer'
                    elif field_key in ['scanNumber', 'dataset_id']:
                        col_def['cellRenderer'] = 'DatasetIdScanLinkRenderer'
                    elif field_key == 'scanNumber':
                        col_def['cellRenderer'] = 'ScanLinkRenderer'
                    elif field_key in ['submit_time', 'start_time', 'finish_time']:
                        col_def['cellRenderer'] = 'DateFormatter'
                    elif field_key == 'status':
                        col_def['cellRenderer'] = 'StatusRenderer'
                    cols.append(col_def)

                for col_num in CUSTOM_COLS_WireRecon_PeakIndex_dict.keys():
                    if col_num == 6:
                        col_def = {
                            'headerName': 'Structure',
                            'valueGetter': {"function": "params.data.crystFile.slice(params.data.crystFile.lastIndexOf('/') + 1, params.data.crystFile.lastIndexOf('.'))"},
                        }
                    if col_num == 7:
                        col_def = {
                            'headerName': 'Frames',
                            'valueGetter': {"function": "params.data.PeakIndex_scanPointslen * params.data.depthRangelen + ' / ' + params.data.WireRecon_scanPointslen * params.data.motorGroup_depth_cpt_total"},
                        }
                    col_def.update({
                        'filter': True,
                        'sortable': True,
                        'resizable': True,
                        'suppressMenuHide': True,
                    })
                    cols.insert(col_num, col_def)

                return cols, scan_peakindexings.to_dict('records')

            else:
                scan_peakindexings = pd.read_sql(session.query(
                    *ALL_COLS_Recon_PeakIndex,
                )
                    .join(db_schema.Metadata, db_schema.PeakIndex.scanNumber == db_schema.Metadata.scanNumber)
                    .join(db_schema.Job, db_schema.PeakIndex.job_id == db_schema.Job.job_id)
                    .outerjoin(db_schema.Recon, db_schema.PeakIndex.recon_id == db_schema.Recon.recon_id)
                    .filter(db_schema.PeakIndex.scanNumber == scan_id)
                    .group_by(*ALL_COLS_PeakIndex)
                    .statement, session.bind)

                cols = []
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
                        'suppressMenuHide': True,
                    }
                    if field_key == 'peakindex_id':
                        col_def['cellRenderer'] = 'PeakIndexLinkRenderer'
                    elif field_key == 'recon_id':
                        col_def['cellRenderer'] = 'ReconLinkRenderer'
                    elif field_key in ['scanNumber', 'dataset_id']:
                        col_def['cellRenderer'] = 'DatasetIdScanLinkRenderer'
                    elif field_key == 'scanNumber':
                        col_def['cellRenderer'] = 'ScanLinkRenderer'
                    elif field_key in ['submit_time', 'start_time', 'finish_time']:
                        col_def['cellRenderer'] = 'DateFormatter'
                    elif field_key == 'status':
                        col_def['cellRenderer'] = 'StatusRenderer'
                    cols.append(col_def)

                for col_num in CUSTOM_COLS_Recon_PeakIndex_dict.keys():
                    if col_num == 6:
                        col_def = {
                            'headerName': 'Structure',
                            'valueGetter': {"function": "params.data.crystFile.slice(params.data.crystFile.lastIndexOf('/') + 1, params.data.crystFile.lastIndexOf('.'))"},
                        }
                    if col_num == 7:
                        col_def = {
                            'headerName': 'Frames',
                            'valueGetter': {"function": "params.data.PeakIndex_scanPointslen * params.data.depthRangelen + ' / ' + params.data.Recon_scanPointslen * params.data.motorGroup_depth_cpt_total"},
                        }
                    col_def.update({
                        'filter': True,
                        'sortable': True,
                        'resizable': True,
                        'suppressMenuHide': True,
                    })
                    cols.insert(col_num, col_def)

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
    Output('recon-table-new-recon-btn', 'href'),
    Output('index-table-new-recon-btn', 'href'),
    Input('scan-recon-table', 'selectedRows'),
    Input('scan-peakindex-table', 'selectedRows'),
    State('recon-table-new-recon-btn', 'href'),
    prevent_initial_call=True,
)
def selected_recon_href(recon_rows, peakindex_rows, href):
    base_href = href.split("?")[0]

    recon_scan_ids, recon_wirerecon_ids, recon_recon_ids = [], [], []
    index_scan_ids, index_wirerecon_ids, index_recon_ids = [], [], []

    for row in (recon_rows or []):
        if not row.get('scanNumber'): return base_href, base_href
        scan_id, wirerecon_id, recon_id = str(row['scanNumber']), str(row.get('wirerecon_id', '')), str(row.get('recon_id', ''))
        recon_scan_ids.append(scan_id); recon_wirerecon_ids.append(wirerecon_id); recon_recon_ids.append(recon_id)

    for row in (peakindex_rows or []):
        if not row.get('scanNumber'): return base_href, base_href
        scan_id, wirerecon_id, recon_id = str(row['scanNumber']), str(row.get('wirerecon_id', '')), str(row.get('recon_id', ''))
        index_scan_ids.append(scan_id); index_wirerecon_ids.append(wirerecon_id); index_recon_ids.append(recon_id)

    def build_href(scan_ids, wirerecon_ids, recon_ids, rows, base_href):
        if not rows:
            return base_href

        any_wirerecon_scans, any_recon_scans = False, False
        for i, row in enumerate(rows):
            any_wirerecon_scans = any(wirerecon_ids)
            any_recon_scans = any(recon_ids)

            if any_wirerecon_scans and any_recon_scans:
                return base_href

            if not any_wirerecon_scans and not any_recon_scans and row.get('aperture'):
                aperture = str(row['aperture']).lower()
                if aperture == 'none':
                    return base_href
                elif 'wire' in aperture:
                    any_wirerecon_scans = True
                else:
                    any_recon_scans = True

                if any_wirerecon_scans and any_recon_scans:
                    return base_href

        if any_recon_scans:
            base_href = "/create-reconstruction"
        elif any_wirerecon_scans:
            base_href = "/create-wire-reconstruction"

        query_params = [f"scan_id={','.join(list(set(scan_ids)))}"]
        if any_wirerecon_scans: query_params.append(f"wirerecon_id={','.join(wirerecon_ids)}")
        if any_recon_scans: query_params.append(f"recon_id={','.join(recon_ids)}")

        return f"{base_href}?{'&'.join(query_params)}"

    recon_href = build_href(recon_scan_ids, recon_wirerecon_ids, recon_recon_ids, recon_rows or [], base_href)
    index_href = build_href(index_scan_ids, index_wirerecon_ids, index_recon_ids, peakindex_rows or [], base_href)

    return recon_href, index_href


@callback(
    Output('recon-table-new-index-btn', 'href'),
    Output('index-table-new-index-btn', 'href'),
    Input('scan-recon-table', 'selectedRows'),
    Input('scan-peakindex-table', 'selectedRows'),
    State('recon-table-new-index-btn', 'href'),
    prevent_initial_call=True,
)
def selected_peakindex_href(recon_rows, peakindex_rows, href):
    base_href = href.split("?")[0]

    recon_scan_ids, recon_wirerecon_ids, recon_recon_ids, recon_peakindex_ids = [], [], [], []
    index_scan_ids, index_wirerecon_ids, index_recon_ids, index_peakindex_ids = [], [], [], []

    for row in (recon_rows or []):
        if not row.get('scanNumber'): return base_href, base_href
        scan_id, wirerecon_id, recon_id, peakindex_id = str(row['scanNumber']), str(row.get('wirerecon_id', '')), str(row.get('recon_id', '')), str(row.get('peakindex_id', ''))
        recon_scan_ids.append(scan_id); recon_wirerecon_ids.append(wirerecon_id); recon_recon_ids.append(recon_id); recon_peakindex_ids.append(peakindex_id)

    for row in (peakindex_rows or []):
        if not row.get('scanNumber'): return base_href, base_href
        scan_id, wirerecon_id, recon_id, peakindex_id = str(row['scanNumber']), str(row.get('wirerecon_id', '')), str(row.get('recon_id', '')), str(row.get('peakindex_id', ''))
        index_scan_ids.append(scan_id); index_wirerecon_ids.append(wirerecon_id); index_recon_ids.append(recon_id); index_peakindex_ids.append(peakindex_id)

    def build_href(scan_ids, wirerecon_ids, recon_ids, peakindex_ids, base_href):
        if not scan_ids:
            return base_href

        query_params = [f"scan_id={','.join(list(set(scan_ids)))}"]
        if any(wirerecon_ids): query_params.append(f"wirerecon_id={','.join(wirerecon_ids)}")
        if any(recon_ids): query_params.append(f"recon_id={','.join(recon_ids)}")
        if any(peakindex_ids): query_params.append(f"peakindex_id={','.join(peakindex_ids)}")

        return f"{base_href}?{'&'.join(query_params)}"

    recon_href = build_href(recon_scan_ids, recon_wirerecon_ids, recon_recon_ids, recon_peakindex_ids, base_href)
    index_href = build_href(index_scan_ids, index_wirerecon_ids, index_recon_ids, index_peakindex_ids, base_href)

    return recon_href, index_href


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
    try:
        if isinstance(scanNumber, str):
            scanNumber = int(scanNumber)

        with Session(session_utils.get_engine()) as session:
            try:
                catalog_data = session.query(db_schema.Catalog).filter(
                    db_schema.Catalog.scanNumber == scanNumber
                ).first()

                if filenamePrefix:
                    filenamePrefix_list = [prefix.strip() for prefix in filenamePrefix.split(',') if prefix.strip()]
                else:
                    filenamePrefix_list = []

                if catalog_data:
                    catalog_data.filefolder = filefolder
                    catalog_data.filenamePrefix = filenamePrefix_list
                    catalog_data.aperture = aperture
                    catalog_data.sample_name = sample_name
                    catalog_data.notes = notes
                else:
                    catalog = db_schema.Catalog(
                        scanNumber=scanNumber,
                        filefolder=filefolder,
                        filenamePrefix=filenamePrefix_list,
                        aperture=aperture,
                        sample_name=sample_name,
                        notes=notes,
                    )
                    session.add(catalog)

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
