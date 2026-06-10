import dash_bootstrap_components as dbc
from dash import html, set_props

from laue_portal.components.form_layout import (
    form_check_row,
    form_checkbox,
    form_field,
    form_field_with_button,
    form_fields_with_button,
    form_layout,
    form_select,
    form_textarea,
    section_card,
    section_sidebar,
)
from laue_portal.database.db_utils import make_IDnumber

PEAKINDEX_SECTIONS = [
    (
        "Configuration",
        [
            ("Identity", "bi bi-person-badge", "#peakindex-sec-identity"),
            ("File Paths", "bi bi-folder2-open", "#peakindex-sec-files"),
        ],
    ),
    (
        "Parameters",
        [
            ("Peak Search", "bi bi-bullseye", "#peakindex-sec-peaks"),
            ("Indexing", "bi bi-diagram-3", "#peakindex-sec-index"),
        ],
    ),
    ("Other", [("Notes", "bi bi-journal-text", "#peakindex-sec-notes")]),
]


def build_peakindex_form(readonly=False, show_actions=True):
    return form_layout(
        section_sidebar(PEAKINDEX_SECTIONS),
        [
            section_card(
                "Identity",
                html.Div(
                    className="lp-form-field-grid",
                    children=[
                        form_field_with_button(
                            "ID Number",
                            "IDnumber",
                            "peakindex-update-path-fields-btn",
                            "Update Paths",
                            placeholder="SN123456 | WR1 | MR3 | PI4",
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
                anchor_id="peakindex-sec-identity",
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
                            "peakindex-check-filenames-btn",
                            "Find Matching Files",
                            placeholder="e.g. Si_%d.h5 or Si_*%d.h5",
                            datalist_id="peakindex-filename-templates",
                            readonly=readonly,
                            show_button=show_actions,
                        ),
                        form_fields_with_button(
                            form_field(
                                "Scan Indices",
                                "scanPoints",
                                placeholder="e.g. 1-10 or 1,5,8,9 or 1-4,10-21",
                                readonly=readonly,
                            ),
                            form_field(
                                "Depth Indices",
                                "depthRange",
                                placeholder="e.g. 1-10 or 1,5,8,9 or 1-4,10-21",
                                readonly=readonly,
                            ),
                            button_id="peakindex-find-indices-btn",
                            button_label="Find Indices",
                            show_button=show_actions,
                        ),
                        form_field("Geometry File", "geoFile", wide=True, readonly=readonly),
                        form_field("Crystal Structure File", "crystFile", wide=True, readonly=readonly),
                        form_field("Output Path", "outputFolder", wide=True, readonly=readonly),
                        form_field(
                            "Output XML",
                            "outputXML",
                            placeholder="e.g. output.xml or /absolute/path/output.xml",
                            readonly=readonly,
                        ),
                    ],
                ),
                accent="teal",
                icon_class="bi bi-folder2-open",
                anchor_id="peakindex-sec-files",
            ),
            section_card(
                "Peak Search Parameters",
                html.Div(
                    className="lp-form-field-grid--three",
                    children=[
                        form_field("Box Size [px]", "boxsize", readonly=readonly),
                        form_field("Max R-factor", "maxRfactor", readonly=readonly),
                        form_field("Threshold", "threshold", placeholder="empty -> auto", readonly=readonly),
                        form_field(
                            "Threshold Ratio",
                            "thresholdRatio",
                            placeholder="empty -> auto",
                            readonly=readonly,
                        ),
                        form_field("Min Spot Size [px]", "min_size", readonly=readonly),
                        form_field("Min Spot Sep. [px]", "min_separation", readonly=readonly),
                        form_field(
                            "Max No. of Spots",
                            "max_number",
                            placeholder="empty for all",
                            readonly=readonly,
                        ),
                        form_select(
                            "Peak Shape",
                            "peakShape",
                            [
                                {"label": "Lorentzian", "value": "Lorentzian"},
                                {"label": "Gaussian", "value": "Gaussian"},
                            ],
                            disabled=readonly,
                        ),
                        form_field("Mask File", "maskFile", wide=True, readonly=readonly),
                        form_check_row(
                            form_checkbox("Smooth peak before fitting", "smooth", disabled=readonly),
                            form_checkbox("Cosmic Filter", "cosmicFilter", disabled=readonly),
                        ),
                    ],
                ),
                accent="purple",
                icon_class="bi bi-bullseye",
                anchor_id="peakindex-sec-peaks",
                header_actions=(
                    dbc.Button(
                        "Restore Default",
                        id="peakindex-set-default-peak-search-btn",
                        color="primary",
                        outline=True,
                        size="sm",
                    )
                    if show_actions
                    else None
                ),
            ),
            section_card(
                "Indexing Parameters",
                html.Div(
                    className="lp-form-field-grid--three",
                    children=[
                        form_field("Max Calc Energy [keV]", "indexKeVmaxCalc", readonly=readonly),
                        form_field("Max Test Energy [keV]", "indexKeVmaxTest", readonly=readonly),
                        form_field("Angle Tolerance [deg]", "indexAngleTolerance", readonly=readonly),
                        form_field("Central HKL", "indexHKL", readonly=readonly),
                        form_field("Cone Angle [deg]", "indexCone", readonly=readonly),
                        form_field("Max No. of Spots", "max_peaks", placeholder="empty: 200", readonly=readonly),
                        form_field("Depth [um]", "depth", placeholder="empty -> auto", readonly=readonly),
                    ],
                ),
                accent="rose",
                icon_class="bi bi-diagram-3",
                anchor_id="peakindex-sec-index",
                header_actions=(
                    dbc.Button(
                        "Restore Default",
                        id="peakindex-set-default-indexing-btn",
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
                            placeholder="Optional notes about this indexing run...",
                            readonly=readonly,
                        )
                    ],
                ),
                accent="gold",
                icon_class="bi bi-journal-text",
                anchor_id="peakindex-sec-notes",
            ),
            html.Div(style={"height": "3rem"}),
        ],
    )


peakindex_form = build_peakindex_form()
peakindex_readonly_form = build_peakindex_form(readonly=True, show_actions=False)


def set_peakindex_form_props(peakindex, read_only=False):
    IDnumber = make_IDnumber(peakindex.scanNumber, peakindex.wirerecon_id, peakindex.recon_id, peakindex.peakindex_id)
    set_props("IDnumber", {"value": IDnumber, "readonly": read_only})
    set_props("root_path", {"value": peakindex.root_path, "readonly": read_only})
    set_props("data_path", {"value": peakindex.data_path, "readonly": read_only})

    filename_value = peakindex.filenamePrefix
    if isinstance(filename_value, list):
        filename_value = ", ".join(filename_value)
    set_props("filenamePrefix", {"value": filename_value, "readonly": read_only})

    set_props("threshold", {"value": peakindex.threshold, "readonly": read_only})
    set_props("thresholdRatio", {"value": peakindex.thresholdRatio, "readonly": read_only})
    set_props("maxRfactor", {"value": peakindex.maxRfactor, "readonly": read_only})
    set_props("boxsize", {"value": peakindex.boxsize, "readonly": read_only})
    set_props("max_number", {"value": peakindex.max_number, "readonly": read_only})
    set_props("min_separation", {"value": peakindex.min_separation, "readonly": read_only})
    set_props("peakShape", {"value": peakindex.peakShape, "disabled": read_only})
    set_props("scanPoints", {"value": peakindex.scanPoints, "readonly": read_only})
    set_props("depthRange", {"value": peakindex.depthRange, "readonly": read_only})
    set_props("min_size", {"value": peakindex.min_size, "readonly": read_only})
    set_props("max_peaks", {"value": peakindex.max_peaks, "readonly": read_only})
    set_props("smooth", {"value": peakindex.smooth, "disabled": read_only})
    set_props("maskFile", {"value": peakindex.maskFile, "readonly": read_only})
    set_props("indexKeVmaxCalc", {"value": peakindex.indexKeVmaxCalc, "readonly": read_only})
    set_props("indexKeVmaxTest", {"value": peakindex.indexKeVmaxTest, "readonly": read_only})
    set_props("indexAngleTolerance", {"value": peakindex.indexAngleTolerance, "readonly": read_only})
    set_props(
        "indexHKL",
        {
            "value": "".join([str(idx) for idx in [peakindex.indexH, peakindex.indexK, peakindex.indexL]]),
            "readonly": read_only,
        },
    )
    set_props("indexCone", {"value": peakindex.indexCone, "readonly": read_only})
    set_props("energyUnit", {"value": peakindex.energyUnit, "readonly": read_only})
    set_props("exposureUnit", {"value": peakindex.exposureUnit, "readonly": read_only})
    set_props("cosmicFilter", {"value": peakindex.cosmicFilter, "disabled": read_only})
    set_props("recipLatticeUnit", {"value": peakindex.recipLatticeUnit, "readonly": read_only})
    set_props("latticeParametersUnit", {"value": peakindex.latticeParametersUnit, "readonly": read_only})
    set_props("outputFolder", {"value": peakindex.outputFolder, "readonly": read_only})
    set_props("outputXML", {"value": peakindex.outputXML or "", "readonly": read_only})
    set_props("geoFile", {"value": peakindex.geoFile, "readonly": read_only})
    set_props("crystFile", {"value": peakindex.crystFile, "readonly": read_only})
    set_props("depth", {"value": peakindex.depth, "readonly": read_only})
    set_props("beamline", {"value": peakindex.beamline, "readonly": read_only})

    set_props("author", {"value": peakindex.author, "readonly": read_only})
    set_props("notes", {"value": peakindex.notes, "readonly": read_only})
