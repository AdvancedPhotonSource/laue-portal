"""
Peak Indexing Form — Variant A: "Instrument Console"

Dense, utilitarian data-entry layout inspired by scientific instrument panels.
Two-column CSS grid with compact inline-labelled fields, section header strips,
and tight vertical spacing to maximize information density.

All fields from the production form are present with matching IDs suffixed
with '-va' to avoid collisions with the live page.
"""

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html

import laue_portal.components.navbar as navbar
from laue_portal.components.validation_alerts import validation_alerts

dash.register_page(__name__, path="/create-peakindexing-a")

# ---------------------------------------------------------------------------
# Helpers — compact field builders for the console layout
# ---------------------------------------------------------------------------


def _cell(label_text, field_id, placeholder="", input_type="text", wide=False):
    """Single dense field cell: label | input."""
    cls = "pi-va-cell pi-va-cell--wide" if wide else "pi-va-cell"
    return html.Div(
        [
            html.Label(label_text),
            dbc.Input(
                id=field_id,
                type=input_type,
                placeholder=placeholder,
                className="form-control",
            ),
        ],
        className=cls,
    )


def _cell_select(label_text, field_id, options, placeholder="Select:", wide=False):
    cls = "pi-va-cell pi-va-cell--wide" if wide else "pi-va-cell"
    return html.Div(
        [
            html.Label(label_text),
            dbc.Select(
                id=field_id,
                options=options,
                placeholder=placeholder,
                className="form-select",
            ),
        ],
        className=cls,
    )


def _cell_check(label_text, field_id, wide=False):
    cls = "pi-va-cell pi-va-cell--wide" if wide else "pi-va-cell"
    return html.Div(
        [
            html.Label(""),
            dbc.Checkbox(id=field_id, label=label_text, className="form-check"),
        ],
        className=cls,
    )


def _file_row(label_text, field_id, btn_id=None, btn_label=None, placeholder=""):
    """Full-width row: label | text input | optional action button."""
    children = [
        html.Label(
            label_text,
            style={
                "minWidth": "160px",
                "maxWidth": "200px",
                "fontFamily": "Lato, sans-serif",
                "fontSize": ".78rem",
                "fontWeight": "700",
                "color": "#2c3e50",
                "whiteSpace": "nowrap",
            },
        ),
        dbc.Input(
            id=field_id,
            placeholder=placeholder,
            className="form-control",
            style={"height": "32px", "fontSize": ".82rem"},
        ),
    ]
    if btn_id and btn_label:
        children.append(
            dbc.Button(
                btn_label, id=btn_id, color="success", size="sm", style={"fontSize": ".78rem", "whiteSpace": "nowrap"}
            ),
        )
    return html.Div(children, className="pi-va-file-row")


def _section(title):
    """Section header strip."""
    return html.Div(title, className="pi-va-section-label")


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

layout = html.Div(
    [
        navbar.navbar,
        dcc.Location(id="url-create-peakindexing-va", refresh=False),
        # Hidden alerts (maintain functional IDs with suffix)
        dbc.Alert(id="alert-upload-va", is_open=False, dismissable=True),
        dbc.Alert(id="alert-submit-va", is_open=False, dismissable=True),
        dbc.Alert(id="alert-scan-loaded-va", is_open=False, dismissable=True, color="success"),
        html.Div(
            className="pi-variant-a",
            children=[
                # ── Header bar ──
                html.Div(
                    className="pi-va-header",
                    children=[
                        html.Div(
                            [
                                html.H2(
                                    [
                                        "New Peak Indexing",
                                        html.Span(" — LaueGo", className="pi-subtitle"),
                                    ]
                                ),
                            ]
                        ),
                        html.Div(
                            className="pi-actions",
                            children=[
                                dbc.Button(
                                    [html.I(className="bi bi-check2-circle me-1"), "Validate"],
                                    id="peakindex-validate-btn-va",
                                    color="light",
                                    size="sm",
                                    outline=True,
                                ),
                                dbc.Button(
                                    [html.I(className="bi bi-send me-1"), "Submit"],
                                    id="submit_peakindexing-va",
                                    color="success",
                                    size="sm",
                                ),
                            ],
                        ),
                    ],
                ),
                # ── Validation alerts ──
                html.Div(validation_alerts, className="pi-va-validation"),
                # ══════════════════════════════════════════════════════════
                # SECTION 1: Identity & File Paths
                # ══════════════════════════════════════════════════════════
                _section("Identity & File Paths"),
                html.Div(
                    className="pi-va-grid",
                    children=[
                        # ID + Author row
                        _cell("ID Number", "IDnumber-va", placeholder="SN123456 | WR1 | MR3 | PI4"),
                        _cell("Author", "author-va", placeholder="Enter author or tag"),
                    ],
                ),
                html.Div(
                    className="pi-va-grid pi-va-grid--single",
                    children=[
                        _file_row("Root Path", "root_path-va"),
                        _file_row("Folder Path", "data_path-va"),
                    ],
                ),
                # ID action button row
                html.Div(
                    style={
                        "padding": ".25rem .5rem",
                        "background": "#fff",
                        "borderBottom": "1px solid #ecf0f1",
                        "display": "flex",
                        "justifyContent": "flex-end",
                        "gap": ".5rem",
                    },
                    children=[
                        dbc.Button(
                            [html.I(className="bi bi-arrow-repeat me-1"), "Update path fields"],
                            id="peakindex-update-path-fields-btn-va",
                            color="secondary",
                            size="sm",
                            outline=True,
                            style={"fontSize": ".78rem"},
                        ),
                    ],
                ),
                # ══════════════════════════════════════════════════════════
                # SECTION 2: Scan Files
                # ══════════════════════════════════════════════════════════
                _section("Scan Files"),
                html.Div(
                    className="pi-va-grid pi-va-grid--single",
                    children=[
                        # Filename row with action button
                        html.Div(
                            className="pi-va-file-row",
                            children=[
                                html.Label(
                                    "Filename",
                                    style={
                                        "minWidth": "160px",
                                        "maxWidth": "200px",
                                        "fontFamily": "Lato, sans-serif",
                                        "fontSize": ".78rem",
                                        "fontWeight": "700",
                                        "color": "#2c3e50",
                                        "whiteSpace": "nowrap",
                                    },
                                ),
                                html.Div(
                                    [
                                        dbc.Input(
                                            id="filenamePrefix-va",
                                            placeholder="e.g. Si_%d.h5 or Si_*%d.h5",
                                            className="form-control",
                                            list="peakindex-filename-templates-va",
                                            style={"height": "32px", "fontSize": ".82rem"},
                                        ),
                                        html.Datalist(id="peakindex-filename-templates-va", children=[]),
                                    ],
                                    style={"flex": "1"},
                                ),
                                dbc.Button(
                                    [html.I(className="bi bi-search me-1"), "Find files"],
                                    id="peakindex-check-filenames-btn-va",
                                    color="success",
                                    size="sm",
                                    style={"fontSize": ".78rem", "whiteSpace": "nowrap"},
                                ),
                            ],
                        ),
                    ],
                ),
                html.Div(
                    className="pi-va-grid",
                    children=[
                        _cell("Scan Indices", "scanPoints-va", placeholder="e.g. 1-10 or 1,5,8,9"),
                        _cell("Depth Indices", "depthRange-va", placeholder="e.g. 1-10 or 1,5,8,9"),
                    ],
                ),
                # Load indices button row
                html.Div(
                    style={
                        "padding": ".25rem .5rem",
                        "background": "#fff",
                        "borderBottom": "1px solid #ecf0f1",
                        "display": "flex",
                        "justifyContent": "flex-end",
                    },
                    children=[
                        dbc.Button(
                            [html.I(className="bi bi-file-earmark-arrow-up me-1"), "Load indices from file"],
                            id="peakindex-load-file-indices-btn-va",
                            color="secondary",
                            size="sm",
                            outline=True,
                            style={"fontSize": ".78rem"},
                        ),
                    ],
                ),
                # ══════════════════════════════════════════════════════════
                # SECTION 3: Geometry & Output
                # ══════════════════════════════════════════════════════════
                _section("Geometry & Output"),
                html.Div(
                    className="pi-va-grid pi-va-grid--single",
                    children=[
                        _file_row("Geometry File", "geoFile-va"),
                        _file_row("Crystal Structure", "crystFile-va"),
                        _file_row("Output Path", "outputFolder-va"),
                        _file_row("Output XML", "outputXML-va", placeholder="e.g. output.xml"),
                        _file_row("Mask File", "maskFile-va"),
                    ],
                ),
                # ══════════════════════════════════════════════════════════
                # SECTION 4: Peak Search Parameters
                # ══════════════════════════════════════════════════════════
                _section("Peak Search Parameters"),
                html.Div(
                    className="pi-va-grid",
                    children=[
                        _cell("Box Size [px]", "boxsize-va"),
                        _cell("Max R-factor", "maxRfactor-va"),
                        _cell("Threshold", "threshold-va", placeholder="empty → auto"),
                        _cell("Threshold Ratio", "thresholdRatio-va", placeholder="empty → auto"),
                        _cell("Min Spot Size [px]", "min_size-va"),
                        _cell("Min Spot Sep. [px]", "min_separation-va"),
                        _cell("Max No. Spots", "max_number-va", placeholder="empty for all"),
                        _cell_select(
                            "Peak Shape",
                            "peakShape-va",
                            [
                                {"label": "Lorentzian", "value": "Lorentzian"},
                                {"label": "Gaussian", "value": "Gaussian"},
                            ],
                        ),
                        _cell_check("Smooth peak before fitting", "smooth-va"),
                        _cell_check("Cosmic Filter", "cosmicFilter-va"),
                    ],
                ),
                # ══════════════════════════════════════════════════════════
                # SECTION 5: Indexing Parameters
                # ══════════════════════════════════════════════════════════
                _section("Indexing Parameters"),
                html.Div(
                    className="pi-va-grid",
                    children=[
                        _cell("Max Calc Energy [keV]", "indexKeVmaxCalc-va"),
                        _cell("Max Test Energy [keV]", "indexKeVmaxTest-va"),
                        _cell("Angle Tolerance [°]", "indexAngleTolerance-va"),
                        _cell("Central HKL", "indexHKL-va"),
                        _cell("Cone Angle [°]", "indexCone-va"),
                        _cell("Max Spots", "max_peaks-va", placeholder="empty: 200"),
                        _cell("Depth [µm]", "depth-va", placeholder="empty → auto", wide=True),
                    ],
                ),
                # ══════════════════════════════════════════════════════════
                # SECTION 6: Notes
                # ══════════════════════════════════════════════════════════
                _section("Notes"),
                html.Div(
                    className="pi-va-grid pi-va-grid--single",
                    children=[
                        html.Div(
                            className="pi-va-notes",
                            children=[
                                dbc.Textarea(
                                    id="notes-va",
                                    placeholder="Optional notes about this indexing run...",
                                    style={"width": "100%", "minHeight": "72px"},
                                ),
                            ],
                        ),
                    ],
                ),
                # bottom spacer
                html.Div(style={"height": "2rem"}),
            ],
        ),
        dcc.Store(id="peakindex-data-loaded-signal-va"),
    ],
)
