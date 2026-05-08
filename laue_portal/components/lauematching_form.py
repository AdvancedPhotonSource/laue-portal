import dash_bootstrap_components as dbc
from dash import html, set_props
from laue_portal.components.form_base import _stack, _field, _select, _ckbx


def _toolbar():
    return html.Div(
        dbc.Row(
            [
                dbc.Col(
                    dbc.Button("Set to defaults", size="sm", color="light"),
                    width="auto",
                ),
                dbc.Col(
                    dbc.Button("Set from ...", size="sm", color="light"),
                    width="auto",
                ),
            ],
            className="g-2 align-items-center",
        ),
        style={
            "background": "var(--bs-accordion-active-bg)",
            "padding": ".5rem 1rem",
            "margin": "-1rem -1.25rem 1rem",
            "borderTop": "none",
            "borderBottom": "1px solid var(--bs-accordion-border-color)",
        },
    )


def _readonly_field(label, field_id, value="", placeholder=""):
    return dbc.InputGroup(
        [
            dbc.InputGroupText(label),
            dbc.Input(
                id=field_id,
                type="text",
                value=value,
                placeholder=placeholder,
                readonly=True,
            ),
        ],
        className="mb-3",
    )


def _editable_field(label, field_id, value="", placeholder=""):
    return dbc.InputGroup(
        [
            dbc.InputGroupText(label),
            dbc.Input(
                id=field_id,
                type="text",
                value=value,
                placeholder=placeholder,
            ),
        ],
        className="mb-3",
    )


def _simulation_existing_view():
    return dbc.Card(
        dbc.CardBody(
            [
                _editable_field(
                    "Simulation file",
                    "simulationFileExisting",
                    placeholder="/path/to/existing/simulation file",
                ),
                dbc.Alert(
                    "If an existing simulation file is provided, the parameters used to create it are shown below.",
                    color="secondary",
                    className="py-2",
                ),
                _readonly_field("Energy range", "simulationEnergyRangeExisting"),
                _readonly_field("Maximum Number of Laue Spots", "simulationMaxNrLaueSpotsExisting"),
                _readonly_field("Geometry File", "simulationGeometryFile"),
                _readonly_field("Crystal Structure File", "simulationCrystalStructureFile"),
                _readonly_field("Orientation file", "simulationOrientationFileExisting"),
                _readonly_field("Orientation spacing", "simulationOrientationSpacingExisting"),
            ]
        ),
        className="mb-3",
    )


def _simulation_new_view():
    return dbc.Card(
        dbc.CardBody(
            [
                dbc.Switch(
                    id="generate-new-simulation-file-switch",
                    label="Generate new simulation file with current geometry file",
                    value=True,
                    className="mb-3",
                ),
                _editable_field(
                    "Simulation file",
                    "SimFileSavePath",
                    placeholder="full path or relative with file name",
                ),
                _editable_field(
                    "Energy range",
                    "simulationEnergyRangeNew",
                    placeholder="e.g. 5-25 keV",
                ),
                _editable_field(
                    "Maximum Number of Laue Spots",
                    "simulationMaxNrLaueSpotsNew",
                    placeholder="e.g. 150",
                ),
                _editable_field("Geometry File", "simulationGeometryFile"),
                _editable_field("Crystal Structure File", "simulationCrystalStructureFile"),
                
                
                html.Div("Orientation setup", className="fw-semibold mb-2"),
                dbc.Tabs(
                    [
                        dbc.Tab(
                            dbc.Card(
                                dbc.CardBody(
                                    [
                                        _editable_field(
                                            "Orientation file",
                                            "simulationOrientationFileNew",
                                            placeholder="/path/to/orientation file",
                                        ),
                                        dbc.Alert(
                                            "If an existing orientation file is provided, the parameters used to create it are shown below.",
                                            color="secondary",
                                            className="py-2",
                                        ),
                                        _readonly_field("Orientation spacing", "simulationOrientationSpacingExisting"),
                                    ]
                                ),
                                className="mt-3",
                            ),
                            label="Use existing orientation file",
                            tab_id="orientation-file-tab",
                        ),
                        dbc.Tab(
                            dbc.Card(
                                dbc.CardBody(
                                    [
                                        dbc.Switch(
                                            id="generate-new-orientation-file-switch",
                                            label="Generate new orientation file",
                                            value=True,
                                            className="mb-3",
                                        ),
                                        _editable_field(
                                            "Orientation file",
                                            "OrientFileSavePath",
                                            placeholder="full path or relative with file name",
                                        ),
                                        _editable_field(
                                            "Orientation spacing",
                                            "simulationOrientationSpacingNew",
                                            value="0.4",
                                            placeholder="e.g. 0.4",
                                        ),
                                        
                                    ]
                                ),
                                className="mt-3",
                            ),
                            label="Generate new orientation file",
                            tab_id="orientation-generate-tab",
                        ),
                    ],
                    active_tab="orientation-file-tab",
                ),
            ]
        ),
        className="mb-3",
    )


lauematching_form = dbc.Row(
    [
        dbc.Col(
            dbc.Accordion(
                [
                    dbc.AccordionItem(
                        [
                            dbc.Row(
                                [
                                    dbc.Col(
                                        dbc.InputGroup(
                                            [
                                                dbc.InputGroupText("ID Number: SN# | WR# | MR# | PI#"),
                                                dbc.Input(
                                                    id="IDnumber",
                                                    type="text",
                                                    placeholder="e.g. SN123456 or WR1 or MR3 or PI4",
                                                ),
                                            ],
                                            className="w-100",
                                        ),
                                        className="flex-grow-1",
                                        style={"minWidth": 0},
                                    ),
                                    dbc.Col(
                                        dbc.Button(
                                            "Update path fields",
                                            id="update-path-fields-btn",
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
                            ),
                            _field("Root Path", "root_path"),
                            _field("Folder Path", "data_path"),
                            dbc.Card(
                                dbc.CardBody(
                                    [
                                        _stack(
                                            [
                                                dbc.Switch(
                                                    id="all-files-switch",
                                                    label="All Files",
                                                    value=False,
                                                ),
                                            ]
                                        ),
                                        dbc.Row(
                                            [
                                                dbc.Col(
                                                    html.Div(
                                                        [
                                                            dbc.InputGroup(
                                                                [
                                                                    dbc.InputGroupText("Filename"),
                                                                    dbc.Input(
                                                                        id="filenamePrefix",
                                                                        type="text",
                                                                        placeholder="e.g. Si_%d.h5 or Si_*%d.h5",
                                                                        list="filename-templates",
                                                                    ),
                                                                ],
                                                                className="w-100",
                                                            ),
                                                            html.Datalist(
                                                                id="filename-templates",
                                                                children=[
                                                                    html.Option(
                                                                        value="Si1_PE2_%d.h5",
                                                                        label="Si1_PE2_%d.h5   (files 1–245)",
                                                                    ),
                                                                    html.Option(
                                                                        value="Si1_Eiger1_%d.h5",
                                                                        label="Si1_Eiger1_%d.h5 (files 3–198)",
                                                                    ),
                                                                    html.Option(
                                                                        value="Si_*_%d.h5",
                                                                        label="Si_*_%d.h5        (files 1–245)",
                                                                    ),
                                                                ],
                                                            ),
                                                        ]
                                                    ),
                                                    className="flex-grow-1",
                                                    style={"minWidth": 0},
                                                ),
                                                dbc.Col(
                                                    dbc.Button(
                                                        "Update from folder",
                                                        id="check-filenames-btn",
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
                                        ),
                                        dbc.Row(
                                            [
                                                dbc.Col(
                                                    dbc.InputGroup(
                                                        [
                                                            dbc.InputGroupText("Scan indices"),
                                                            dbc.Input(
                                                                id="scanPoints",
                                                                type="text",
                                                                size="md",
                                                                placeholder="e.g. 1-10 or 1,5,8,9 or 1-4,10-21",
                                                            ),
                                                        ],
                                                        className="w-100",
                                                    ),
                                                    className="flex-grow-1",
                                                    style={"minWidth": 0},
                                                ),
                                                dbc.Col(
                                                    dbc.InputGroup(
                                                        [
                                                            dbc.InputGroupText("Depth indices"),
                                                            dbc.Input(
                                                                id="depthRange",
                                                                type="text",
                                                                size="md",
                                                                placeholder="e.g. 1-10 or 1,5,8,9 or 1-4,10-21",
                                                            ),
                                                        ],
                                                        className="w-100",
                                                    ),
                                                    className="flex-grow-1",
                                                    style={"minWidth": 0},
                                                ),
                                                dbc.Col(
                                                    dbc.Button(
                                                        "Load indices from file",
                                                        id="load-file-indices-btn",
                                                        color="secondary",
                                                        size="md",
                                                        style={"minWidth": "220px", "whiteSpace": "nowrap"},
                                                    ),
                                                    width="auto",
                                                    className="d-flex justify-content-end",
                                                ),
                                            ],
                                            className="mb-2",
                                            align="center",
                                        ),
                                    ],
                                    className="p-2",
                                ),
                                className="mb-3",
                            ),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        dbc.InputGroup(
                                            [
                                                dbc.InputGroupText("Geometry File"),
                                                dbc.Input(id="geoFile", type="text", size="md", placeholder=""),
                                            ],
                                            className="w-100",
                                        ),
                                        className="flex-grow-1",
                                        style={"minWidth": 150},
                                    ),
                                    dbc.Col(
                                        dbc.Row(
                                            [
                                                dbc.Col(
                                                    dbc.Button(
                                                        "Load default",
                                                        id="load-default-geo-btn",
                                                        color="secondary",
                                                        size="md",
                                                        style={"minWidth": "120px", "whiteSpace": "nowrap"},
                                                    ),
                                                    width="auto",
                                                ),
                                                dbc.Col(
                                                    dbc.Button(
                                                        "Load...",
                                                        id="load-from-geo-btn",
                                                        color="secondary",
                                                        size="md",
                                                        style={"minWidth": "120px", "whiteSpace": "nowrap"},
                                                    ),
                                                    width="auto",
                                                ),
                                                dbc.Col(
                                                    dbc.Button(
                                                        "Edit",
                                                        id="edit-geo-params-btn",
                                                        color="secondary",
                                                        size="md",
                                                        style={"minWidth": "120px", "whiteSpace": "nowrap"},
                                                    ),
                                                    width="auto",
                                                ),
                                            ],
                                            className="g-2 justify-content-end",
                                        ),
                                        xs=12,
                                        md="auto",
                                    ),
                                ],
                                className="mb-3 g-2",
                                align="center",
                            ),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        dbc.InputGroup(
                                            [
                                                dbc.InputGroupText("Crystal structure File"),
                                                dbc.Input(id="materialFile", type="text", size="md", placeholder=""),
                                            ],
                                            className="w-100",
                                        ),
                                        className="flex-grow-1",
                                        style={"minWidth": 150},
                                    ),
                                    dbc.Col(
                                        dbc.Row(
                                            [
                                                dbc.Col(
                                                    dbc.Button(
                                                        "Load default",
                                                        id="load-default-material-btn",
                                                        color="secondary",
                                                        size="md",
                                                        style={"minWidth": "120px", "whiteSpace": "nowrap"},
                                                    ),
                                                    width="auto",
                                                ),
                                                dbc.Col(
                                                    dbc.Button(
                                                        "Load...",
                                                        id="load-from-material-btn",
                                                        color="secondary",
                                                        size="md",
                                                        style={"minWidth": "120px", "whiteSpace": "nowrap"},
                                                    ),
                                                    width="auto",
                                                ),
                                                dbc.Col(
                                                    dbc.Button(
                                                        "Edit",
                                                        id="edit-material-params-btn",
                                                        color="secondary",
                                                        size="md",
                                                        style={"minWidth": "120px", "whiteSpace": "nowrap"},
                                                    ),
                                                    width="auto",
                                                ),
                                            ],
                                            className="g-2 justify-content-end",
                                        ),
                                        xs=12,
                                        md="auto",
                                    ),
                                ],
                                className="mb-3 g-2",
                                align="center",
                            ),
                            _field("Output Path", "outputFolder"),
                            _field("Output XML file", "outputXMLFile"),
                        ],
                        title="Files",
                        item_id="item-1",
                    ),
                    dbc.AccordionItem(
                        [
                            _toolbar(),
                            html.Div("Simulation mode", className="fw-semibold mb-2"),
                            dbc.Tabs(
                                [
                                    dbc.Tab(
                                        _simulation_existing_view(),
                                        label="Use existing simulation file",
                                        tab_id="simulation-existing-tab",
                                    ),
                                    dbc.Tab(
                                        _simulation_new_view(),
                                        label="Create new simulation file",
                                        tab_id="simulation-new-tab",
                                    ),
                                ],
                                active_tab="simulation-existing-tab",
                            ),
                        ],
                        title="Simulation parameters",
                        item_id="item-2",
                        className="no-border-bottom",
                    ),
                    dbc.AccordionItem(
                        [
                            _toolbar(),
                            
                            dbc.Switch(
                                id="compute-background-switch",
                                label="compute the background",
                                value=False,
                            ),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        dbc.InputGroup(
                                            [
                                                dbc.InputGroupText("Background file"),
                                                dbc.Input(id="BkgFile", type="text", placeholder=""),
                                            ],
                                            className="w-100",
                                        ),
                                        className="flex-grow-1",
                                        style={"minWidth": 0},
                                    ),
                                    dbc.Col(
                                        dbc.Button(
                                            "Load...",
                                            id="load-cryst-file-btn",
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
                            ),
                            
                        _editable_field(
                            "Threshold",
                            "thresholdImgProc",
                            placeholder="e.g. 0, 100",
                        ),
                        
                        _editable_field(
                            "Minimum number pixel in spot",
                            "MinNumPixelInSpot",
                            placeholder="e.g. 2, 5",
                        ),
                        
                        
                        ],
                        title="Image processing Parameters",
                        item_id="item-3",
                        className="no-border-bottom",
                    ),
                    
                    
                    dbc.AccordionItem(
                        [
                            _toolbar(),
                        _editable_field(
                            "Minimum Number of Spots for Orientation",
                            "MinNumSpotsOrient",
                            placeholder="e.g. 5",
                        ),
                        _editable_field(
                            "Minumum Intensity for Orientation",
                            "MinIntenSpotsOrient",
                            placeholder="e.g. 10",
                        ),
                        _editable_field(
                            "Max Angle [deg]",
                            "MaxAngleSpotOrient",
                            placeholder="e.g. 0.1",
                        ),
                        
                        # _select("Error Matrix Select", "ErrorCalc",
                        #                     [
                        #                         {"label": "Lorentzian", "value": "Lorentzian"},
                        #                         {"label": "Gaussian", "value": "Gaussian"},
                        #                     ],
                        #                     size='md',
                        #                     kwargs={'placeholder':'Select:'}, 
                        #                 ),
                        
                        # dbc.Select(
                        #         id="Error Matrix Select",
                        #         label="ErrorCalc",
                        #         data=[
                        #             {"label": "√(ΣI) · N", "value": "sqrt_sumI_times_N"},
                        #             {"label": "√(ΣIN)", "value": "sqrt_sumIN"},
                        #             {"label": "ΣI · √N", "value": "sumI_sqrtN"},
                        #             {"label": "ΣIN", "value": "sumIN"},
                        #             {"label": "ΣI", "value": "sumI"},
                        #         ],
                        #         placeholder="Select:",
                        #         size="md",
                        #     ),
                        
                        
                        _select("Error Matrix Select", "ErrorCalc",
                                            [
                                                {"label": "√ΣI · N", "value": "sqrt_sumI_times_N"},
                                                {"label": "√ΣIN", "value": "sqrt_sumIN"},
                                                {"label": "ΣI√N", "value": "sumI_sqrtN"},
                                                {"label": "ΣIN", "value": "sumIN"},
                                                {"label": "ΣI", "value": "sumI"},
                                            ],
                                            size='md',
                                            kwargs={'placeholder':'Select:'}, 
                                        ),
                        
                        # dbc.Select(
                        #     id="Error Matrix Select",
                        #     options=[
                        #         {"label": "√ΣI · N", "value": "sqrt_sumI_times_N"},
                        #         {"label": "√ΣIN", "value": "sqrt_sumIN"},
                        #         {"label": "ΣI√N", "value": "sumI_sqrtN"},
                        #         {"label": "ΣIN", "value": "sumIN"},
                        #         {"label": "ΣI", "value": "sumI"},
                        #     ],
                        #     value="sqrt_sumIN",
                        # ),
                        
                        dbc.Switch(
                                id="compute-strain-switch",
                                label="compute strain",
                                value=False,
                            ),
                        
                        ],
                        title="Indexing Parameters",
                        item_id="item-3",
                        className="no-border-bottom",
                    ),
                    
                    
                    
                    
                    dbc.AccordionItem(
                        [
                            dbc.Row(
                                [
                                    dbc.Col(
                                        [
                                            html.P(html.Strong("Notes:")),
                                        ],
                                        width="auto",
                                        align="start",
                                    ),
                                    dbc.Col(
                                        dbc.Textarea(
                                            id="notes",
                                            style={"width": "100%", "minHeight": "100px"},
                                        )
                                    ),
                                ],
                                className="mb-3",
                                align="start",
                            )
                        ],
                        title="User Text",
                        item_id="item-4",
                    ),
                ],
                always_open=True,
                start_collapsed=False,
                active_item=["item-1", "item-2", "item-3", "item-4"],
            ),
            xs=12,
            className="px-0",
        ),
    ],
    className="g-0",
    style={"width": "100%", "overflow-x": "auto"},
)


def set_peakindex_form_props(peakindex, read_only=False):
    # set_props("dataset", {'value': peakindex.dataset_id, 'readonly': read_only})
    set_props("scanNumber", {"value": peakindex.scanNumber, "readonly": read_only})
    set_props("root_path", {"value": peakindex.root_path, "readonly": read_only})
    set_props("data_path", {"value": peakindex.data_path, "readonly": read_only})
    set_props("filenamePrefix", {"value": ",".join(peakindex.filenamePrefix), "readonly": read_only})
    set_props("recon_id", {"value": peakindex.recon_id, "readonly": read_only})
    set_props("wirerecon_id", {"value": peakindex.wirerecon_id, "readonly": read_only})

    # set_props("peakProgram", {'value': peakindex.peakProgram, 'readonly': read_only})
    set_props("threshold", {"value": peakindex.threshold, "readonly": read_only})
    set_props("thresholdRatio", {"value": peakindex.thresholdRatio, "readonly": read_only})
    set_props("maxRfactor", {"value": peakindex.maxRfactor, "readonly": read_only})
    set_props("boxsize", {"value": peakindex.boxsize, "readonly": read_only})
    set_props("max_number", {"value": peakindex.max_number, "readonly": read_only})
    set_props("min_separation", {"value": peakindex.min_separation, "readonly": read_only})
    set_props("peakShape", {"value": peakindex.peakShape, "disabled": read_only})
    set_props("scanPoints", {"value": peakindex.scanPoints, "readonly": read_only})
    set_props("depthRange", {"value": peakindex.depthRange, "readonly": read_only})
    set_props("detectorCropX1", {"value": peakindex.detectorCropX1, "readonly": read_only})
    set_props("detectorCropX2", {"value": peakindex.detectorCropX2, "readonly": read_only})
    set_props("detectorCropY1", {"value": peakindex.detectorCropY1, "readonly": read_only})
    set_props("detectorCropY2", {"value": peakindex.detectorCropY2, "readonly": read_only})
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
    # set_props("indexH", {'value': peakindex.indexH, 'readonly': read_only})
    # set_props("indexK", {'value': peakindex.indexK, 'readonly': read_only})
    # set_props("indexL", {'value': peakindex.indexL, 'readonly': read_only})
    set_props("indexCone", {"value": peakindex.indexCone, "readonly": read_only})
    set_props("energyUnit", {"value": peakindex.energyUnit, "readonly": read_only})
    set_props("exposureUnit", {"value": peakindex.exposureUnit, "readonly": read_only})
    set_props("cosmicFilter", {"value": peakindex.cosmicFilter, "disabled": read_only})
    set_props("recipLatticeUnit", {"value": peakindex.recipLatticeUnit, "readonly": read_only})
    set_props("latticeParametersUnit", {"value": peakindex.latticeParametersUnit, "readonly": read_only})
    # set_props("peaksearchPath", {'value': peakindex.peaksearchPath, 'readonly': read_only})
    # set_props("p2qPath", {'value': peakindex.p2qPath, 'readonly': read_only})
    # set_props("indexingPath", {'value': peakindex.indexingPath, 'readonly': read_only})
    set_props("outputFolder", {"value": peakindex.outputFolder, "readonly": read_only})
    set_props("geoFile", {"value": peakindex.geoFile, "readonly": read_only})
    set_props("crystFile", {"value": peakindex.crystFile, "readonly": read_only})
    set_props("depth", {"value": peakindex.depth, "readonly": read_only})
    set_props("beamline", {"value": peakindex.beamline, "readonly": read_only})

    # simulation fields if they exist on the object
    if hasattr(peakindex, "simulationFile"):
        set_props("simulationFileExisting", {"value": peakindex.simulationFile, "readonly": read_only})

    if hasattr(peakindex, "EnergyRange"):
        set_props("simulationEnergyRangeExisting", {"value": peakindex.EnergyRange, "readonly": True})
        set_props("simulationEnergyRangeNew", {"value": peakindex.EnergyRange, "readonly": read_only})

    if hasattr(peakindex, "MaxNrLaueSpots"):
        set_props("simulationMaxNrLaueSpotsExisting", {"value": peakindex.MaxNrLaueSpots, "readonly": True})
        set_props("simulationMaxNrLaueSpotsNew", {"value": peakindex.MaxNrLaueSpots, "readonly": read_only})

    if hasattr(peakindex, "OrientationFile"):
        set_props("simulationOrientationFileExisting", {"value": peakindex.OrientationFile, "readonly": True})
        set_props("simulationOrientationFileNew", {"value": peakindex.OrientationFile, "readonly": read_only})

    if hasattr(peakindex, "OrientationSpacing"):
        set_props("simulationOrientationSpacingExisting", {"value": peakindex.OrientationSpacing, "readonly": True})
        set_props("simulationOrientationSpacingNew", {"value": peakindex.OrientationSpacing, "readonly": read_only})

    # User text
    set_props("author", {"value": peakindex.author, "readonly": read_only})
    set_props("notes", {"value": peakindex.notes, "readonly": read_only})
