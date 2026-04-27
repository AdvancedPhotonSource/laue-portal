"""
Peak Indexing Form — Variant B: "Blueprint Panels"

Card-based layout with clear visual hierarchy. Each section is a
self-contained panel with a tinted left-border accent. Fields use
stacked label-above-input blocks in a responsive grid within each card.
Clean whitespace, soft shadows, and color-coded section accents.

All fields from the production form are present with matching IDs suffixed
with '-vb' to avoid collisions with the live page.
"""

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html

import laue_portal.components.navbar as navbar
from laue_portal.components.validation_alerts import validation_alerts

dash.register_page(__name__, path="/create-peakindexing-b")

# ---------------------------------------------------------------------------
# Helpers — label-above-input field builders for the card layout
# ---------------------------------------------------------------------------


def _field(label_text, field_id, placeholder="", input_type="text", wide=False):
    """Stacked label/input field block."""
    cls = "pi-vb-field pi-vb-field-wide" if wide else "pi-vb-field"
    return html.Div(
        [
            html.Label(label_text, htmlFor=field_id),
            dbc.Input(
                id=field_id,
                type=input_type,
                placeholder=placeholder,
                className="form-control",
            ),
        ],
        className=cls,
    )


def _field_select(label_text, field_id, options, placeholder="Select:", wide=False):
    cls = "pi-vb-field pi-vb-field-wide" if wide else "pi-vb-field"
    return html.Div(
        [
            html.Label(label_text, htmlFor=field_id),
            dbc.Select(
                id=field_id,
                options=options,
                placeholder=placeholder,
                className="form-select",
            ),
        ],
        className=cls,
    )


def _field_check(label_text, field_id):
    return html.Div(
        [
            html.Label(""),
            dbc.Checkbox(id=field_id, label=label_text, className="form-check"),
        ],
        className="pi-vb-field",
    )


def _field_textarea(label_text, field_id, placeholder=""):
    return html.Div(
        [
            html.Label(label_text, htmlFor=field_id),
            dbc.Textarea(
                id=field_id,
                placeholder=placeholder,
                className="form-control",
                style={"minHeight": "80px"},
            ),
        ],
        className="pi-vb-field pi-vb-field-wide",
    )


def _field_with_btn(label_text, field_id, btn_id, btn_label, placeholder="", datalist_id=None):
    """Field with an inline action button to its right."""
    input_el = dbc.Input(
        id=field_id,
        placeholder=placeholder,
        className="form-control",
        **({"list": datalist_id} if datalist_id else {}),
    )
    children = [
        html.Div(
            [html.Label(label_text, htmlFor=field_id), input_el],
            className="pi-vb-field",
            style={"flex": "1"},
        ),
        dbc.Button(
            btn_label,
            id=btn_id,
            color="success",
            size="sm",
            style={"height": "36px", "whiteSpace": "nowrap", "fontSize": ".82rem", "alignSelf": "flex-end"},
        ),
    ]
    if datalist_id:
        children.append(html.Datalist(id=datalist_id, children=[]))
    return html.Div(children, className="pi-vb-field-inline pi-vb-field-wide")


def _card(title, children, accent="teal", badge=None):
    """Section card with colored left border."""
    accent_class = f"pi-vb-card pi-vb-card--{accent}"
    head_children = [html.H3(title)]
    if badge:
        head_children.append(html.Span(badge, className="pi-card-badge"))
    return html.Div(
        [
            html.Div(head_children, className="pi-vb-card-head"),
            html.Div(children, className="pi-vb-card-body"),
        ],
        className=accent_class,
    )


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

layout = html.Div(
    [
        navbar.navbar,
        dcc.Location(id="url-create-peakindexing-vb", refresh=False),
        # Hidden alerts
        dbc.Alert(id="alert-upload-vb", is_open=False, dismissable=True),
        dbc.Alert(id="alert-submit-vb", is_open=False, dismissable=True),
        dbc.Alert(id="alert-scan-loaded-vb", is_open=False, dismissable=True, color="success"),
        html.Div(
            className="pi-variant-b",
            children=[
                # ── Masthead ──
                html.Div(
                    className="pi-vb-masthead",
                    children=[
                        html.Div(
                            [
                                html.Div("Indexations / New", className="pi-breadcrumb"),
                                html.H2("New Peak Indexing"),
                            ]
                        ),
                        html.Div(
                            className="pi-actions",
                            children=[
                                dbc.Button(
                                    [html.I(className="bi bi-check2-circle me-1"), "Validate"],
                                    id="peakindex-validate-btn-vb",
                                    color="secondary",
                                    outline=True,
                                ),
                                dbc.Button(
                                    [html.I(className="bi bi-send me-1"), "Submit Job"],
                                    id="submit_peakindexing-vb",
                                    color="success",
                                ),
                            ],
                        ),
                    ],
                ),
                # ── Validation ──
                html.Div(validation_alerts, className="pi-vb-validation"),
                # ══════════════════════════════════════════════════════════
                # Card 1: Identity
                # ══════════════════════════════════════════════════════════
                _card(
                    "Identity",
                    html.Div(
                        className="pi-vb-field-grid",
                        children=[
                            _field_with_btn(
                                "ID Number",
                                "IDnumber-vb",
                                "peakindex-update-path-fields-btn-vb",
                                "Update Paths",
                                placeholder="SN123456 | WR1 | MR3 | PI4",
                            ),
                            _field("Author", "author-vb", placeholder="Enter author or tag", wide=True),
                        ],
                    ),
                    accent="slate",
                    badge="Required",
                ),
                # ══════════════════════════════════════════════════════════
                # Card 2: File Paths
                # ══════════════════════════════════════════════════════════
                _card(
                    "File Paths",
                    html.Div(
                        className="pi-vb-field-grid",
                        children=[
                            _field("Root Path", "root_path-vb", wide=True),
                            _field("Folder Path", "data_path-vb", wide=True),
                            _field("Geometry File", "geoFile-vb", wide=True),
                            _field("Crystal Structure File", "crystFile-vb", wide=True),
                            _field("Output Path", "outputFolder-vb", wide=True),
                            _field(
                                "Output XML", "outputXML-vb", placeholder="e.g. output.xml or /absolute/path/output.xml"
                            ),
                            _field("Mask File", "maskFile-vb"),
                        ],
                    ),
                    accent="teal",
                ),
                # ══════════════════════════════════════════════════════════
                # Card 3: Scan Configuration
                # ══════════════════════════════════════════════════════════
                _card(
                    "Scan Configuration",
                    html.Div(
                        className="pi-vb-field-grid",
                        children=[
                            _field_with_btn(
                                "Filename",
                                "filenamePrefix-vb",
                                "peakindex-check-filenames-btn-vb",
                                "Find Files",
                                placeholder="e.g. Si_%d.h5 or Si_*%d.h5",
                                datalist_id="peakindex-filename-templates-vb",
                            ),
                            _field("Scan Indices", "scanPoints-vb", placeholder="e.g. 1-10 or 1,5,8,9 or 1-4,10-21"),
                            _field("Depth Indices", "depthRange-vb", placeholder="e.g. 1-10 or 1,5,8,9 or 1-4,10-21"),
                            html.Div(
                                dbc.Button(
                                    [html.I(className="bi bi-file-earmark-arrow-up me-1"), "Load indices from file"],
                                    id="peakindex-load-file-indices-btn-vb",
                                    color="secondary",
                                    size="sm",
                                    outline=True,
                                ),
                                className="pi-vb-field-wide",
                                style={"display": "flex", "justifyContent": "flex-end", "paddingTop": ".25rem"},
                            ),
                        ],
                    ),
                    accent="blue",
                ),
                # ══════════════════════════════════════════════════════════
                # Card 4: Peak Search Parameters
                # ══════════════════════════════════════════════════════════
                _card(
                    "Peak Search Parameters",
                    html.Div(
                        className="pi-vb-field-grid--three",
                        style={"display": "grid", "gap": ".75rem 1.25rem"},
                        children=[
                            _field("Box Size [pixels]", "boxsize-vb"),
                            _field("Max R-factor", "maxRfactor-vb"),
                            _field("Threshold", "threshold-vb", placeholder="empty → auto"),
                            _field("Threshold Ratio", "thresholdRatio-vb", placeholder="empty → auto"),
                            _field("Min Spot Size [px]", "min_size-vb"),
                            _field("Min Spot Sep. [px]", "min_separation-vb"),
                            _field("Max No. of Spots", "max_number-vb", placeholder="empty for all"),
                            _field_select(
                                "Peak Shape",
                                "peakShape-vb",
                                [
                                    {"label": "Lorentzian", "value": "Lorentzian"},
                                    {"label": "Gaussian", "value": "Gaussian"},
                                ],
                            ),
                            html.Div(),  # spacer to align checkboxes
                            html.Div(
                                className="pi-vb-check-row",
                                children=[
                                    dbc.Checkbox(id="smooth-vb", label="Smooth peak before fitting"),
                                    dbc.Checkbox(id="cosmicFilter-vb", label="Cosmic Filter"),
                                ],
                            ),
                        ],
                    ),
                    accent="teal",
                    badge="Tuning",
                ),
                # ══════════════════════════════════════════════════════════
                # Card 5: Indexing Parameters
                # ══════════════════════════════════════════════════════════
                _card(
                    "Indexing Parameters",
                    html.Div(
                        className="pi-vb-field-grid--three",
                        style={"display": "grid", "gap": ".75rem 1.25rem"},
                        children=[
                            _field("Max Calc Energy [keV]", "indexKeVmaxCalc-vb"),
                            _field("Max Test Energy [keV]", "indexKeVmaxTest-vb"),
                            _field("Angle Tolerance [°]", "indexAngleTolerance-vb"),
                            _field("Central HKL", "indexHKL-vb"),
                            _field("Cone Angle [°]", "indexCone-vb"),
                            _field("Max No. of Spots", "max_peaks-vb", placeholder="empty: 200"),
                            _field("Depth [µm]", "depth-vb", placeholder="empty → auto"),
                        ],
                    ),
                    accent="blue",
                ),
                # ══════════════════════════════════════════════════════════
                # Card 6: Notes
                # ══════════════════════════════════════════════════════════
                _card(
                    "Notes",
                    html.Div(
                        className="pi-vb-field-grid",
                        children=[
                            _field_textarea(
                                "Notes",
                                "notes-vb",
                                placeholder="Optional notes about this indexing run...",
                            ),
                        ],
                    ),
                    accent="warn",
                ),
                # bottom spacer
                html.Div(style={"height": "3rem"}),
            ],
        ),
        dcc.Store(id="peakindex-data-loaded-signal-vb"),
    ],
)
