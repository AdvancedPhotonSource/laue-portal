import dash_bootstrap_components as dbc
from dash import html, set_props

from laue_portal.components.form_layout import (
    form_field,
    form_field_with_button,
    form_layout,
    form_select,
    form_textarea,
    section_card,
    section_sidebar,
)
from laue_portal.database.db_utils import make_IDnumber

WIRE_RECON_SECTIONS = [
    (
        "Configuration",
        [
            ("Identity", "bi bi-person-badge", "#wire-recon-sec-identity"),
            ("File Paths", "bi bi-folder2-open", "#wire-recon-sec-files"),
        ],
    ),
    (
        "Parameters",
        [("Reconstruction", "bi bi-layers", "#wire-recon-sec-parameters")],
    ),
    ("Other", [("Notes", "bi bi-journal-text", "#wire-recon-sec-notes")]),
]


def build_wire_recon_form(readonly=False, show_actions=True):
    return form_layout(
        section_sidebar(WIRE_RECON_SECTIONS),
        [
            section_card(
                "Identity",
                html.Div(
                    className="lp-form-field-grid",
                    children=[
                        form_field_with_button(
                            "ID Number",
                            "IDnumber",
                            "wirerecon-update-path-fields-btn",
                            "Update Paths",
                            placeholder="SN123456 | WR1",
                            readonly=readonly,
                            show_button=show_actions,
                        ),
                        form_field(
                            "Author",
                            "author",
                            placeholder="Required! Enter author or tag",
                            wide=True,
                            readonly=readonly,
                        ),
                    ],
                ),
                accent="slate",
                icon_class="bi bi-person-badge",
                anchor_id="wire-recon-sec-identity",
            ),
            section_card(
                "File Paths",
                html.Div(
                    className="lp-form-field-grid",
                    children=[
                        form_field("Root Path", "root_path", wide=True, readonly=readonly),
                        form_field("Folder Path", "data_path", wide=True, readonly=readonly),
                        form_field_with_button(
                            "Filename",
                            "filenamePrefix",
                            "wirerecon-check-filenames-btn",
                            "Find Matching Files",
                            placeholder="e.g. Si_%d.h5 or Si_*%d.h5",
                            datalist_id="wirerecon-filename-templates",
                            readonly=readonly,
                            show_button=show_actions,
                        ),
                        form_field_with_button(
                            "Scan Indices",
                            "scanPoints",
                            "wirerecon-load-file-indices-btn",
                            "Find Indices",
                            placeholder="e.g. 1-10 or 1,5,8,9 or 1-4,10-21",
                            readonly=readonly,
                            show_button=show_actions,
                        ),
                        form_field("Output Path", "outputFolder", wide=True, readonly=readonly),
                        form_field("Geometry File", "geoFile", wide=True, readonly=readonly),
                    ],
                ),
                accent="teal",
                icon_class="bi bi-folder2-open",
                anchor_id="wire-recon-sec-files",
            ),
            section_card(
                "Wire Reconstruction Parameters",
                html.Div(
                    className="lp-form-field-grid--three",
                    children=[
                        form_field("Depth Start [µm]", "depth_start", readonly=readonly),
                        form_field("Depth End [µm]", "depth_end", readonly=readonly),
                        form_field("Depth Resolution [µm]", "depth_resolution", readonly=readonly),
                        form_select(
                            "Wire Edges",
                            "wire_edges",
                            [
                                {"label": "Leading Edge", "value": "leading"},
                                {"label": "Trailing Edge", "value": "trailing"},
                                {"label": "Both Edges", "value": "both"},
                            ],
                            disabled=readonly,
                        ),
                        form_field("Intensity Percentile", "percent_brightest", readonly=readonly),
                    ],
                ),
                accent="purple",
                icon_class="bi bi-layers",
                anchor_id="wire-recon-sec-parameters",
                header_actions=(
                    dbc.Button(
                        "Restore Default",
                        id="wirerecon-set-default-parameters-btn",
                        color="primary",
                        outline=True,
                        size="sm",
                    )
                    if show_actions
                    else None
                ),
            ),
            section_card(
                "Notes",
                html.Div(
                    className="lp-form-field-grid",
                    children=[
                        form_textarea(
                            "Notes",
                            "notes",
                            placeholder="Optional notes about this reconstruction run...",
                            readonly=readonly,
                        )
                    ],
                ),
                accent="gold",
                icon_class="bi bi-journal-text",
                anchor_id="wire-recon-sec-notes",
            ),
            html.Div(style={"height": "3rem"}),
        ],
    )


wire_recon_form = build_wire_recon_form()
wire_recon_readonly_form = build_wire_recon_form(readonly=True, show_actions=False)


def set_wire_recon_form_props(wirerecon, read_only=False):
    IDnumber = make_IDnumber(wirerecon.scanNumber, wirerecon.wirerecon_id)
    set_props("IDnumber", {"value": IDnumber, "readonly": read_only})
    set_props("root_path", {"value": wirerecon.root_path, "readonly": read_only})
    set_props("data_path", {"value": wirerecon.data_path, "readonly": read_only})

    # Convert list to comma-separated string for form display
    filename_value = wirerecon.filenamePrefix
    if isinstance(filename_value, list):
        filename_value = ", ".join(filename_value)
    set_props("filenamePrefix", {"value": filename_value, "readonly": read_only})

    set_props("author", {"value": wirerecon.author, "readonly": read_only})
    set_props("notes", {"value": wirerecon.notes, "readonly": read_only})

    set_props("geoFile", {"value": wirerecon.geoFile, "readonly": read_only})
    set_props("percent_brightest", {"value": wirerecon.percent_brightest, "readonly": read_only})
    set_props("wire_edges", {"value": wirerecon.wire_edges, "disabled": read_only})

    set_props("depth_start", {"value": wirerecon.depth_start, "readonly": read_only})
    set_props("depth_end", {"value": wirerecon.depth_end, "readonly": read_only})
    set_props("depth_resolution", {"value": wirerecon.depth_resolution, "readonly": read_only})

    set_props("scanPoints", {"value": wirerecon.scanPoints, "readonly": read_only})
    set_props("outputFolder", {"value": wirerecon.outputFolder, "readonly": read_only})
    set_props("detector", {"value": None, "readonly": True})
