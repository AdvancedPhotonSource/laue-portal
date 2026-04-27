"""
Peak Indexing Form — Variant C: "Sidebar Navigator"

Left sidebar with section navigation, main scrollable content area on the right.
Each section is visible in a continuous scroll with the sidebar providing
quick-jump anchors and visual orientation. Inspired by IDE settings panels
with a professional, tool-like feel.

All fields from the production form are present with matching IDs suffixed
with '-vc' to avoid collisions with the live page.
"""

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html

import laue_portal.components.navbar as navbar
from laue_portal.components.validation_alerts import validation_alerts

dash.register_page(__name__, path="/create-peakindexing-c")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _field(label_text, field_id, placeholder="", input_type="text", wide=False):
    cls = "pi-vc-field pi-vc-field-wide" if wide else "pi-vc-field"
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


def _field_select(label_text, field_id, options, placeholder="Select:"):
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
        className="pi-vc-field",
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
        className="pi-vc-field pi-vc-field-wide",
    )


def _field_with_btn(
    label_text, field_id, btn_id, btn_label, placeholder="", datalist_id=None, btn_icon="bi bi-arrow-right"
):
    input_el = dbc.Input(
        id=field_id,
        placeholder=placeholder,
        className="form-control",
        **({"list": datalist_id} if datalist_id else {}),
    )
    children = [
        html.Div(
            [html.Label(label_text, htmlFor=field_id), input_el],
            className="pi-vc-field",
        ),
        dbc.Button(
            [html.I(className=f"{btn_icon} me-1"), btn_label],
            id=btn_id,
            color="success",
            size="sm",
            style={"height": "34px", "alignSelf": "flex-end"},
        ),
    ]
    if datalist_id:
        children.append(html.Datalist(id=datalist_id, children=[]))
    return html.Div(children, className="pi-vc-field-inline")


def _section_head(title, icon_class, color="teal"):
    return html.Div(
        className="pi-vc-section-head",
        children=[
            html.Div(
                html.I(className=icon_class),
                className=f"pi-vc-section-icon pi-vc-section-icon--{color}",
            ),
            html.H3(title),
        ],
    )


def _nav_item(label, icon_class="bi bi-circle", href="#"):
    return html.A(
        [html.Span(className=f"pi-vc-nav-icon {icon_class}"), label],
        className="pi-vc-nav-item",
        href=href,
    )


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

sidebar = html.Div(
    className="pi-vc-sidebar",
    children=[
        html.Div(
            className="pi-vc-nav-group",
            children=[
                html.Div("Configuration", className="pi-vc-nav-group-title"),
                _nav_item("Identity", "bi bi-person-badge", "#sec-identity"),
                _nav_item("File Paths", "bi bi-folder2-open", "#sec-files"),
                _nav_item("Scan Data", "bi bi-grid-3x3-gap", "#sec-scan"),
            ],
        ),
        html.Div(
            className="pi-vc-nav-group",
            children=[
                html.Div("Parameters", className="pi-vc-nav-group-title"),
                _nav_item("Geometry & Output", "bi bi-bounding-box", "#sec-geo"),
                _nav_item("Peak Search", "bi bi-bullseye", "#sec-peaks"),
                _nav_item("Indexing", "bi bi-diagram-3", "#sec-index"),
            ],
        ),
        html.Div(
            className="pi-vc-nav-group",
            children=[
                html.Div("Other", className="pi-vc-nav-group-title"),
                _nav_item("Notes", "bi bi-journal-text", "#sec-notes"),
            ],
        ),
    ],
)


# ---------------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------------

main_content = html.Div(
    className="pi-vc-main",
    children=[
        # ── Validation ──
        html.Div(validation_alerts, className="pi-vc-validation"),
        # ══════════════════════════════════════════════════════════════
        # Section 1: Identity
        # ══════════════════════════════════════════════════════════════
        html.Div(
            id="sec-identity",
            className="pi-vc-section",
            children=[
                _section_head("Identity", "bi bi-person-badge", "slate"),
                html.Div(
                    className="pi-vc-field-grid",
                    children=[
                        _field_with_btn(
                            "ID Number",
                            "IDnumber-vc",
                            "peakindex-update-path-fields-btn-vc",
                            "Update Paths",
                            placeholder="SN123456 | WR1 | MR3 | PI4",
                            btn_icon="bi bi-arrow-repeat",
                        ),
                        _field("Author", "author-vc", placeholder="Enter author or tag", wide=True),
                    ],
                ),
            ],
        ),
        # ══════════════════════════════════════════════════════════════
        # Section 2: File Paths
        # ══════════════════════════════════════════════════════════════
        html.Div(
            id="sec-files",
            className="pi-vc-section",
            children=[
                _section_head("File Paths", "bi bi-folder2-open", "teal"),
                html.Div(
                    className="pi-vc-field-grid",
                    children=[
                        _field("Root Path", "root_path-vc", wide=True),
                        _field("Folder Path", "data_path-vc", wide=True),
                    ],
                ),
            ],
        ),
        # ══════════════════════════════════════════════════════════════
        # Section 3: Scan Data
        # ══════════════════════════════════════════════════════════════
        html.Div(
            id="sec-scan",
            className="pi-vc-section",
            children=[
                _section_head("Scan Data", "bi bi-grid-3x3-gap", "blue"),
                html.Div(
                    className="pi-vc-field-grid",
                    children=[
                        _field_with_btn(
                            "Filename",
                            "filenamePrefix-vc",
                            "peakindex-check-filenames-btn-vc",
                            "Find Files",
                            placeholder="e.g. Si_%d.h5 or Si_*%d.h5",
                            datalist_id="peakindex-filename-templates-vc",
                            btn_icon="bi bi-search",
                        ),
                        _field("Scan Indices", "scanPoints-vc", placeholder="e.g. 1-10 or 1,5,8,9 or 1-4,10-21"),
                        _field("Depth Indices", "depthRange-vc", placeholder="e.g. 1-10 or 1,5,8,9 or 1-4,10-21"),
                        html.Div(
                            dbc.Button(
                                [html.I(className="bi bi-file-earmark-arrow-up me-1"), "Load indices from file"],
                                id="peakindex-load-file-indices-btn-vc",
                                color="secondary",
                                size="sm",
                                outline=True,
                            ),
                            className="pi-vc-field-wide",
                            style={"display": "flex", "justifyContent": "flex-end", "paddingTop": ".25rem"},
                        ),
                    ],
                ),
            ],
        ),
        # ══════════════════════════════════════════════════════════════
        # Section 4: Geometry & Output
        # ══════════════════════════════════════════════════════════════
        html.Div(
            id="sec-geo",
            className="pi-vc-section",
            children=[
                _section_head("Geometry & Output", "bi bi-bounding-box", "teal"),
                html.Div(
                    className="pi-vc-field-grid",
                    children=[
                        _field("Geometry File", "geoFile-vc", wide=True),
                        _field("Crystal Structure File", "crystFile-vc", wide=True),
                        _field("Output Path", "outputFolder-vc", wide=True),
                        _field(
                            "Output XML", "outputXML-vc", placeholder="e.g. output.xml or /absolute/path/output.xml"
                        ),
                        _field("Mask File", "maskFile-vc"),
                    ],
                ),
            ],
        ),
        # ══════════════════════════════════════════════════════════════
        # Section 5: Peak Search Parameters
        # ══════════════════════════════════════════════════════════════
        html.Div(
            id="sec-peaks",
            className="pi-vc-section",
            children=[
                _section_head("Peak Search Parameters", "bi bi-bullseye", "blue"),
                html.Div(
                    className="pi-vc-field-grid--three",
                    style={"display": "grid", "gap": ".6rem 1.25rem"},
                    children=[
                        _field("Box Size [pixels]", "boxsize-vc"),
                        _field("Max R-factor", "maxRfactor-vc"),
                        _field("Threshold", "threshold-vc", placeholder="empty → auto"),
                        _field("Threshold Ratio", "thresholdRatio-vc", placeholder="empty → auto"),
                        _field("Min Spot Size [px]", "min_size-vc"),
                        _field("Min Spot Sep. [px]", "min_separation-vc"),
                        _field("Max No. of Spots", "max_number-vc", placeholder="empty for all"),
                        _field_select(
                            "Peak Shape",
                            "peakShape-vc",
                            [
                                {"label": "Lorentzian", "value": "Lorentzian"},
                                {"label": "Gaussian", "value": "Gaussian"},
                            ],
                        ),
                        html.Div(),  # alignment spacer
                        html.Div(
                            className="pi-vc-check-row",
                            children=[
                                dbc.Checkbox(id="smooth-vc", label="Smooth peak before fitting"),
                                dbc.Checkbox(id="cosmicFilter-vc", label="Cosmic Filter"),
                            ],
                        ),
                    ],
                ),
            ],
        ),
        # ══════════════════════════════════════════════════════════════
        # Section 6: Indexing Parameters
        # ══════════════════════════════════════════════════════════════
        html.Div(
            id="sec-index",
            className="pi-vc-section",
            children=[
                _section_head("Indexing Parameters", "bi bi-diagram-3", "slate"),
                html.Div(
                    className="pi-vc-field-grid--three",
                    style={"display": "grid", "gap": ".6rem 1.25rem"},
                    children=[
                        _field("Max Calc Energy [keV]", "indexKeVmaxCalc-vc"),
                        _field("Max Test Energy [keV]", "indexKeVmaxTest-vc"),
                        _field("Angle Tolerance [°]", "indexAngleTolerance-vc"),
                        _field("Central HKL", "indexHKL-vc"),
                        _field("Cone Angle [°]", "indexCone-vc"),
                        _field("Max No. of Spots", "max_peaks-vc", placeholder="empty: 200"),
                        _field("Depth [µm]", "depth-vc", placeholder="empty → auto"),
                    ],
                ),
            ],
        ),
        # ══════════════════════════════════════════════════════════════
        # Section 7: Notes
        # ══════════════════════════════════════════════════════════════
        html.Div(
            id="sec-notes",
            className="pi-vc-section",
            children=[
                _section_head("Notes", "bi bi-journal-text", "warn"),
                html.Div(
                    className="pi-vc-field-grid",
                    children=[
                        _field_textarea(
                            "Notes",
                            "notes-vc",
                            placeholder="Optional notes about this indexing run...",
                        ),
                    ],
                ),
            ],
        ),
        # bottom spacer
        html.Div(style={"height": "3rem"}),
    ],
)


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

layout = html.Div(
    [
        navbar.navbar,
        dcc.Location(id="url-create-peakindexing-vc", refresh=False),
        # Hidden alerts
        dbc.Alert(id="alert-upload-vc", is_open=False, dismissable=True),
        dbc.Alert(id="alert-submit-vc", is_open=False, dismissable=True),
        dbc.Alert(id="alert-scan-loaded-vc", is_open=False, dismissable=True, color="success"),
        html.Div(
            className="pi-variant-c",
            children=[
                # ── Top bar ──
                html.Div(
                    className="pi-vc-topbar",
                    children=[
                        html.H2(
                            [
                                html.I(className="bi bi-diamond-half me-2", style={"color": "#18bc9c"}),
                                "New Peak Indexing",
                            ]
                        ),
                        html.Div(
                            className="pi-actions",
                            children=[
                                dbc.Button(
                                    [html.I(className="bi bi-check2-circle me-1"), "Validate"],
                                    id="peakindex-validate-btn-vc",
                                    color="light",
                                    size="sm",
                                    outline=True,
                                ),
                                dbc.Button(
                                    [html.I(className="bi bi-send me-1"), "Submit Job"],
                                    id="submit_peakindexing-vc",
                                    color="success",
                                    size="sm",
                                ),
                            ],
                        ),
                    ],
                ),
                # ── Body: sidebar + main ──
                html.Div(
                    className="pi-vc-body",
                    children=[sidebar, main_content],
                ),
            ],
        ),
        dcc.Store(id="peakindex-data-loaded-signal-vc"),
    ],
)
