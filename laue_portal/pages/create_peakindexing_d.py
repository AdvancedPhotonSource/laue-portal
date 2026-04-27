"""
Peak Indexing Form — Variant D: "Console + Navigator"

Hybrid of Variant A's dense inline-label rows with Variant C's sidebar
navigation. Section headers use a light-tinted strip with a subtle
colored left accent and dark text for high readability (avoids the
green-on-dark contrast issue from A).

All fields from the production form are present with matching IDs suffixed
with '-vd' to avoid collisions with the live page.
"""

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html

import laue_portal.components.navbar as navbar
from laue_portal.components.validation_alerts import validation_alerts

dash.register_page(__name__, path="/create-peakindexing-d")

# ---------------------------------------------------------------------------
# Helpers — dense inline-label cells (from A), plus section heads & sidebar
# ---------------------------------------------------------------------------


def _cell(label_text, field_id, placeholder="", input_type="text", wide=False):
    """Compact inline cell: fixed-width label | flexible input."""
    cls = "pi-vd-cell pi-vd-cell--wide" if wide else "pi-vd-cell"
    return html.Div(
        [
            html.Label(label_text),
            dbc.Input(id=field_id, type=input_type, placeholder=placeholder, className="form-control"),
        ],
        className=cls,
    )


def _cell_select(label_text, field_id, options, placeholder="Select:", wide=False):
    cls = "pi-vd-cell pi-vd-cell--wide" if wide else "pi-vd-cell"
    return html.Div(
        [
            html.Label(label_text),
            dbc.Select(id=field_id, options=options, placeholder=placeholder, className="form-select"),
        ],
        className=cls,
    )


def _cell_check(label_text, field_id, wide=False):
    cls = "pi-vd-cell pi-vd-cell--wide" if wide else "pi-vd-cell"
    return html.Div(
        [
            html.Label(""),
            dbc.Checkbox(id=field_id, label=label_text, className="form-check"),
        ],
        className=cls,
    )


def _file_row(label_text, field_id, btn_id=None, btn_label=None, placeholder="", datalist_id=None):
    """Full-width row: label | text input | optional action button."""
    input_kwargs = {}
    if datalist_id:
        input_kwargs["list"] = datalist_id
    children = [
        html.Label(label_text),
        dbc.Input(id=field_id, placeholder=placeholder, className="form-control", **input_kwargs),
    ]
    if datalist_id:
        children.append(html.Datalist(id=datalist_id, children=[]))
    if btn_id and btn_label:
        children.append(
            dbc.Button(btn_label, id=btn_id, color="success", size="sm", style={"whiteSpace": "nowrap"}),
        )
    return html.Div(children, className="pi-vd-file-row")


def _section(title, icon_class="bi bi-circle", accent=""):
    """Light-tinted section header strip with colored left accent."""
    cls = "pi-vd-section-head"
    if accent:
        cls += f" pi-vd-section-head--{accent}"
    return html.Div(
        [
            html.I(className=f"pi-vd-section-icon {icon_class}"),
            html.H3(title),
        ],
        className=cls,
    )


def _action_row(*buttons):
    """Right-aligned row for action buttons between sections."""
    return html.Div(list(buttons), className="pi-vd-action-row")


def _nav_link(label, icon_class="bi bi-circle", href="#"):
    return html.A(
        [html.Span(className=f"pi-vd-nav-icon {icon_class}"), label],
        className="pi-vd-nav-link",
        href=href,
    )


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

sidebar = html.Div(
    className="pi-vd-sidebar",
    children=[
        html.Div(
            className="pi-vd-nav-group",
            children=[
                html.Div("Configuration", className="pi-vd-nav-heading"),
                _nav_link("Identity", "bi bi-person-badge", "#sec-d-identity"),
                _nav_link("File Paths", "bi bi-folder2-open", "#sec-d-files"),
                _nav_link("Scan Data", "bi bi-grid-3x3-gap", "#sec-d-scan"),
            ],
        ),
        html.Div(
            className="pi-vd-nav-group",
            children=[
                html.Div("Parameters", className="pi-vd-nav-heading"),
                _nav_link("Geometry & Output", "bi bi-bounding-box", "#sec-d-geo"),
                _nav_link("Peak Search", "bi bi-bullseye", "#sec-d-peaks"),
                _nav_link("Indexing", "bi bi-diagram-3", "#sec-d-index"),
            ],
        ),
        html.Div(
            className="pi-vd-nav-group",
            children=[
                html.Div("Other", className="pi-vd-nav-heading"),
                _nav_link("Notes", "bi bi-journal-text", "#sec-d-notes"),
            ],
        ),
    ],
)

# ---------------------------------------------------------------------------
# Main content — dense A-style rows with redesigned section headers
# ---------------------------------------------------------------------------

main_content = html.Div(
    className="pi-vd-main",
    children=[
        # ── Validation ──
        html.Div(validation_alerts, className="pi-vd-validation"),
        # ══════════════════════════════════════════════════════════════
        # Section 1: Identity
        # ══════════════════════════════════════════════════════════════
        html.Div(id="sec-d-identity"),
        _section("Identity", "bi bi-person-badge", "slate"),
        html.Div(
            className="pi-vd-grid",
            children=[
                _cell("ID Number", "IDnumber-vd", placeholder="SN123456 | WR1 | MR3 | PI4"),
                _cell("Author", "author-vd", placeholder="Enter author or tag"),
            ],
        ),
        _action_row(
            dbc.Button(
                [html.I(className="bi bi-arrow-repeat me-1"), "Update path fields"],
                id="peakindex-update-path-fields-btn-vd",
                color="secondary",
                size="sm",
                outline=True,
            ),
        ),
        # ══════════════════════════════════════════════════════════════
        # Section 2: File Paths
        # ══════════════════════════════════════════════════════════════
        html.Div(id="sec-d-files"),
        _section("File Paths", "bi bi-folder2-open"),
        html.Div(
            className="pi-vd-grid pi-vd-grid--single",
            children=[
                _file_row("Root Path", "root_path-vd"),
                _file_row("Folder Path", "data_path-vd"),
            ],
        ),
        # ══════════════════════════════════════════════════════════════
        # Section 3: Scan Data
        # ══════════════════════════════════════════════════════════════
        html.Div(id="sec-d-scan"),
        _section("Scan Data", "bi bi-grid-3x3-gap", "blue"),
        html.Div(
            className="pi-vd-grid pi-vd-grid--single",
            children=[
                _file_row(
                    "Filename",
                    "filenamePrefix-vd",
                    btn_id="peakindex-check-filenames-btn-vd",
                    btn_label="Find files",
                    placeholder="e.g. Si_%d.h5 or Si_*%d.h5",
                    datalist_id="peakindex-filename-templates-vd",
                ),
            ],
        ),
        html.Div(
            className="pi-vd-grid",
            children=[
                _cell("Scan Indices", "scanPoints-vd", placeholder="e.g. 1-10 or 1,5,8,9"),
                _cell("Depth Indices", "depthRange-vd", placeholder="e.g. 1-10 or 1,5,8,9"),
            ],
        ),
        _action_row(
            dbc.Button(
                [html.I(className="bi bi-file-earmark-arrow-up me-1"), "Load indices from file"],
                id="peakindex-load-file-indices-btn-vd",
                color="secondary",
                size="sm",
                outline=True,
            ),
        ),
        # ══════════════════════════════════════════════════════════════
        # Section 4: Geometry & Output
        # ══════════════════════════════════════════════════════════════
        html.Div(id="sec-d-geo"),
        _section("Geometry & Output", "bi bi-bounding-box"),
        html.Div(
            className="pi-vd-grid pi-vd-grid--single",
            children=[
                _file_row("Geometry File", "geoFile-vd"),
                _file_row("Crystal Structure", "crystFile-vd"),
                _file_row("Output Path", "outputFolder-vd"),
                _file_row("Output XML", "outputXML-vd", placeholder="e.g. output.xml"),
                _file_row("Mask File", "maskFile-vd"),
            ],
        ),
        # ══════════════════════════════════════════════════════════════
        # Section 5: Peak Search Parameters
        # ══════════════════════════════════════════════════════════════
        html.Div(id="sec-d-peaks"),
        _section("Peak Search Parameters", "bi bi-bullseye", "blue"),
        html.Div(
            className="pi-vd-grid",
            children=[
                _cell("Box Size [px]", "boxsize-vd"),
                _cell("Max R-factor", "maxRfactor-vd"),
                _cell("Threshold", "threshold-vd", placeholder="empty → auto"),
                _cell("Threshold Ratio", "thresholdRatio-vd", placeholder="empty → auto"),
                _cell("Min Spot Size [px]", "min_size-vd"),
                _cell("Min Spot Sep. [px]", "min_separation-vd"),
                _cell("Max No. Spots", "max_number-vd", placeholder="empty for all"),
                _cell_select(
                    "Peak Shape",
                    "peakShape-vd",
                    [
                        {"label": "Lorentzian", "value": "Lorentzian"},
                        {"label": "Gaussian", "value": "Gaussian"},
                    ],
                ),
            ],
        ),
        html.Div(
            className="pi-vd-check-row",
            children=[
                dbc.Checkbox(id="smooth-vd", label="Smooth peak before fitting"),
                dbc.Checkbox(id="cosmicFilter-vd", label="Cosmic Filter"),
            ],
        ),
        # ══════════════════════════════════════════════════════════════
        # Section 6: Indexing Parameters
        # ══════════════════════════════════════════════════════════════
        html.Div(id="sec-d-index"),
        _section("Indexing Parameters", "bi bi-diagram-3", "slate"),
        html.Div(
            className="pi-vd-grid",
            children=[
                _cell("Max Calc Energy [keV]", "indexKeVmaxCalc-vd"),
                _cell("Max Test Energy [keV]", "indexKeVmaxTest-vd"),
                _cell("Angle Tolerance [°]", "indexAngleTolerance-vd"),
                _cell("Central HKL", "indexHKL-vd"),
                _cell("Cone Angle [°]", "indexCone-vd"),
                _cell("Max Spots", "max_peaks-vd", placeholder="empty: 200"),
                _cell("Depth [µm]", "depth-vd", placeholder="empty → auto", wide=True),
            ],
        ),
        # ══════════════════════════════════════════════════════════════
        # Section 7: Notes
        # ══════════════════════════════════════════════════════════════
        html.Div(id="sec-d-notes"),
        _section("Notes", "bi bi-journal-text", "warn"),
        html.Div(
            className="pi-vd-grid pi-vd-grid--single",
            children=[
                html.Div(
                    className="pi-vd-notes",
                    children=[
                        dbc.Textarea(
                            id="notes-vd",
                            placeholder="Optional notes about this indexing run...",
                            style={"width": "100%", "minHeight": "68px"},
                        ),
                    ],
                ),
            ],
        ),
        # bottom spacer
        html.Div(style={"height": "2rem"}),
    ],
)


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

layout = html.Div(
    [
        navbar.navbar,
        dcc.Location(id="url-create-peakindexing-vd", refresh=False),
        # Hidden alerts
        dbc.Alert(id="alert-upload-vd", is_open=False, dismissable=True),
        dbc.Alert(id="alert-submit-vd", is_open=False, dismissable=True),
        dbc.Alert(id="alert-scan-loaded-vd", is_open=False, dismissable=True, color="success"),
        html.Div(
            className="pi-variant-d",
            children=[
                # ── Top bar ──
                html.Div(
                    className="pi-vd-topbar",
                    children=[
                        html.H2("New Peak Indexing"),
                        html.Div(
                            className="pi-vd-actions",
                            children=[
                                dbc.Button(
                                    [html.I(className="bi bi-check2-circle me-1"), "Validate"],
                                    id="peakindex-validate-btn-vd",
                                    color="light",
                                    size="sm",
                                    outline=True,
                                ),
                                dbc.Button(
                                    [html.I(className="bi bi-send me-1"), "Submit"],
                                    id="submit_peakindexing-vd",
                                    color="success",
                                    size="sm",
                                ),
                            ],
                        ),
                    ],
                ),
                # ── Body: sidebar + main ──
                html.Div(
                    className="pi-vd-body",
                    children=[sidebar, main_content],
                ),
            ],
        ),
        dcc.Store(id="peakindex-data-loaded-signal-vd"),
    ],
)
