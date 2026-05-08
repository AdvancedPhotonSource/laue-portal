import dash_bootstrap_components as dbc
from dash import html, set_props
from laue_portal.components.form_base import _stack, _field, _select, _ckbx


lauematching_form2 = dbc.Row(
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
                                                        dbc.Input(id="IDnumber", type="text", placeholder="e.g. SN123456 or WR1 or MR3 or PI4"),
                                                    ],
                                                    className="w-100",            # input group spans the col
                                                ),
                                                className="flex-grow-1",          # THIS makes it expand
                                                style={"minWidth": 0},            # avoid overflow when very narrow
                                            ),
                                            dbc.Col(
                                                dbc.Button(
                                                    "Update path fields",
                                                    id="update-path-fields-btn",
                                                    color="secondary",
                                                    size="md",
                                                    style={"minWidth": "220px", "whiteSpace": "nowrap"},  # fixed/min size
                                                ),
                                                width="auto",                      # column sizes to content
                                                className="d-flex justify-content-end",  # optional: keep at right edge
                                            ),
                                        ],
                                        className="mb-3",
                                        align="center",
                                    ),
                                _field("Root Path", "root_path"),
                                _field("Folder Path", "data_path"),
                                dbc.Card(
                                dbc.CardBody([
                                
                                _stack(   
                                       [
                                dbc.Switch(
                                    id="files switch-switch",
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
                                                                list="filename-templates",  # link to datalist below
                                                                
                                                            ),
                                                        ],
                                                        className="w-100",
                                                    ),
                                                    # just as example
                                                    html.Datalist(
                                                        id="filename-templates",
                                                        children=[
                                                                html.Option(value="Si1_PE2_%d.h5",    label="Si1_PE2_%d.h5   (files 1–245)"),
                                                                html.Option(value="Si1_Eiger1_%d.h5", label="Si1_Eiger1_%d.h5 (files 3–198)"),
                                                                html.Option(value="Si_*_%d.h5",        label="Si_*_%d.h5        (files 1–245)"),
                                                            ]
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
                                                        dbc.Input(id="scanPoints", type="text", size = "md", placeholder="e.g. 1-10 or 1,5,8,9 or 1-4,10-21"),
                                                    ],
                                                    className="w-100",            # input group spans the col
                                                ),
                                                className="flex-grow-1",          # THIS makes it expand
                                                style={"minWidth": 0},            # avoid overflow when very narrow
                                            ),
                                            
                                            dbc.Col(
                                                dbc.InputGroup(
                                                    [
                                                        dbc.InputGroupText("Depth indices"),
                                                        dbc.Input(id="depthRange", type="text", size = "md", placeholder="e.g. 1-10 or 1,5,8,9 or 1-4,10-21"),
                                                    ],
                                                    className="w-100",            # input group spans the col
                                                ),
                                                className="flex-grow-1",          # THIS makes it expand
                                                style={"minWidth": 0},            # avoid overflow when very narrow
                                            ),

                                            dbc.Col(
                                                dbc.Button(
                                                    "Load indices from file",
                                                    id="load-file-indices-btn",
                                                    color="secondary",
                                                    size="md",
                                                    style={"minWidth": "220px", "whiteSpace": "nowrap"},  # fixed/min size
                                                ),
                                                width="auto",                      # column sizes to content
                                                className="d-flex justify-content-end",  # optional: keep at right edge
                                            ),
                                        ],
                                        className="mb-2",
                                        align="center",
                                    ),
                                
                            ],
                                             className="p-2",
                                ),
                                className="mb-3",
                                #style={"margin": "10px"},             # control outer spacing of the card itself
                                ),
                                
                                
                                #_stack([
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
                                                            id="edit-modify-params-btn",
                                                            color="secondary",
                                                            size="md",
                                                            style={"minWidth": "120px", "whiteSpace": "nowrap"},
                                                        ),
                                                        width="auto",
                                                    ),
                                                ],
                                                className="g-2 justify-content-end",  # g-2 adds a nice gap
                                            ),
                                            xs=12, md="auto",  # whole block drops under input on small screens
                                        ),
                                    ],
                                    className="mb-3 g-2",
                                    align="center",
                                ),
                                #]),
                                #_stack([
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
                                                            id="edit-modify-params-btn",
                                                            color="secondary",
                                                            size="md",
                                                            style={"minWidth": "120px", "whiteSpace": "nowrap"},
                                                        ),
                                                        width="auto",
                                                    ),
                                                ],
                                                className="g-2 justify-content-end",  # g-2 adds a nice gap
                                            ),
                                            xs=12, md="auto",  # whole block drops under input on small screens
                                        ),
                                    ],
                                    className="mb-3 g-2",
                                    align="center",
                                ),
                                #]),
                               
                                
                                _field("Output Path", "outputFolder"),
                                _field("Output XML file", "output XML file"),
                                
                                
                                
                                
                            ],
                            title="Files",
                            item_id = "item-1",
                        ),
                        dbc.AccordionItem(
                            
                            [
                                html.Div(
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
                                            "background": "var(--bs-accordion-active-bg)",   # match header when open
                                            "padding": ".5rem 1rem",
                                            "margin": "-1rem -1.25rem 1rem",                 # stretch to card edges
                                            "borderTop": "none",
                                            "borderBottom": "1px solid var(--bs-accordion-border-color)",
                                        },
                                    ),
                               
                                _field("Simulation file", "default"),
                                # dbc.Switch(
                                #     id="files switch-switch",
                                #     label="generate new simulation file with current geometry file",
                                #     value=False,
                                # ),
                                _field("Energy range", "default"),
                                
                                _field("MaxNrLaueSpots", "default"),
                                _field("Orientation file", "default"),
                                
                                dbc.Switch(
                                    id="files switch-switch",
                                    label="generate new orientation file",
                                    value=False,
                                ),
                                _field("OrientationSpacing", "0.4"),
                                
                                
                                
                                
                                





                            ],
                            title="Simulation parameters",
                            item_id = "item-2",
                            className="no-border-bottom",   # 👈 add custom class
                            
                        ),
                        dbc.AccordionItem(
                            [
                                
                                html.Div(
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
                                            "background": "var(--bs-accordion-active-bg)",   # match header when open
                                            "padding": ".5rem 1rem",
                                            "margin": "-1rem -1.25rem 1rem",                 # stretch to card edges
                                            "borderTop": "none",
                                            "borderBottom": "1px solid var(--bs-accordion-border-color)",
                                        },
                                    ),
                                
                                dbc.Switch(
                                    id="files switch-switch",
                                    label="compute the background",
                                    value=False,
                                ),
                                _field("Background file", "0.4"),
                                
                                dbc.Switch(
                                    id="bkg_params-switch",
                                    label="set default parameters for image processing",
                                    value=False,
                                ),
                                
                                dbc.Row(
                                        [
                                            
                                            dbc.Col(
                                                dbc.InputGroup(
                                                    [
                                                        dbc.InputGroupText("Threshold"),
                                                        dbc.Input(id="scanPoints", type="text", size = "md", placeholder="0 If you want to apply a threshold. It will also compute the threshold automatically, and will use the higher of the two values. This is before gaussian blurring"),
                                                    ],
                                                    className="w-100",            # input group spans the col
                                                ),
                                                className="flex-grow-1",          # THIS makes it expand
                                                style={"minWidth": 0},            # avoid overflow when very narrow
                                            ),
                                            
                                            dbc.Col(
                                                dbc.InputGroup(
                                                    [
                                                        dbc.InputGroupText("Min Area [pixels]"),
                                                        dbc.Input(id="depthRange", type="text", size = "md", placeholder="5 Minimum number of pixels that qualify a spot. Connected pixels smaller than this number will be set to 0."),
                                                    ],
                                                    className="w-100",            # input group spans the col
                                                ),
                                                className="flex-grow-1",          # THIS makes it expand
                                                style={"minWidth": 0},            # avoid overflow when very narrow
                                            ),

                                            
                                        ],
                                        className="mb-2",
                                        align="center",
                                    ),
                                
                                
                            ],
                            title="Image processing Parameters",
                            item_id = "item-3",
                            className="no-border-bottom",   # 👈 add custom class
                        ),
                        
    
                      
                        
                        
                        
                        
                        
                        dbc.AccordionItem(
                            [
                                
                                dbc.Row([
                                    dbc.Col([
                                        html.P(html.Strong("Notes:")),
                                    ], width="auto", align="start"),
                                    dbc.Col(
                                        dbc.Textarea(
                                            id="notes",
                                            style={"width": "100%", "minHeight": "100px"},
                                        )
                                    )
                                ], className="mb-3", align="start")
                            ],
                            title="User Text",
                            item_id="item-4"
                        ),
                        ],
                        always_open=True,
                        start_collapsed=False,
                        active_item=["item-1","item-2","item-3","item-4"]
                    ),
                    xs=12,
                    className="px-0",
                    ),
                ],
                className="g-0",             # no gutters
                style={'width': '100%', 'overflow-x': 'auto'}
        )


def set_peakindex_form_props(peakindex, read_only=False):
    #set_props("dataset", {'value':peakindex.dataset_id, 'readonly':read_only})
    set_props("scanNumber", {'value':peakindex.scanNumber, 'readonly':read_only})
    set_props("root_path", {'value':peakindex.root_path, 'readonly':read_only})
    set_props("data_path", {'value':peakindex.data_path, 'readonly':read_only})
    set_props("filenamePrefix", {'value':','.join(peakindex.filenamePrefix), 'readonly':read_only})
    set_props("recon_id", {'value':peakindex.recon_id, 'readonly':read_only})
    set_props("wirerecon_id", {'value':peakindex.wirerecon_id, 'readonly':read_only})
    
    # set_props("peakProgram", {'value':peakindex.peakProgram, 'readonly':read_only})
    set_props("threshold", {'value':peakindex.threshold, 'readonly':read_only})
    set_props("thresholdRatio", {'value':peakindex.thresholdRatio, 'readonly':read_only})
    set_props("maxRfactor", {'value':peakindex.maxRfactor, 'readonly':read_only})
    set_props("boxsize", {'value':peakindex.boxsize, 'readonly':read_only})
    set_props("max_number", {'value':peakindex.max_number, 'readonly':read_only})
    set_props("min_separation", {'value':peakindex.min_separation, 'readonly':read_only})
    set_props("peakShape", {'value':peakindex.peakShape, 'disabled':read_only})
    set_props("scanPoints", {'value':peakindex.scanPoints, 'readonly':read_only})
    set_props("depthRange", {'value':peakindex.depthRange, 'readonly':read_only})
    set_props("detectorCropX1", {'value':peakindex.detectorCropX1, 'readonly':read_only})
    set_props("detectorCropX2", {'value':peakindex.detectorCropX2, 'readonly':read_only})
    set_props("detectorCropY1", {'value':peakindex.detectorCropY1, 'readonly':read_only})
    set_props("detectorCropY2", {'value':peakindex.detectorCropY2, 'readonly':read_only})
    set_props("min_size", {'value':peakindex.min_size, 'readonly':read_only})
    set_props("max_peaks", {'value':peakindex.max_peaks, 'readonly':read_only})
    set_props("smooth", {'value':peakindex.smooth, 'disabled':read_only})
    set_props("maskFile", {'value':peakindex.maskFile, 'readonly':read_only})
    set_props("indexKeVmaxCalc", {'value':peakindex.indexKeVmaxCalc, 'readonly':read_only})
    set_props("indexKeVmaxTest", {'value':peakindex.indexKeVmaxTest, 'readonly':read_only})
    set_props("indexAngleTolerance", {'value':peakindex.indexAngleTolerance, 'readonly':read_only})
    set_props("indexHKL", {'value':''.join(
        [str(idx) for idx in [peakindex.indexH, peakindex.indexK, peakindex.indexL]]
                                          ),
                           'readonly':read_only})
    # set_props("indexH", {'value':peakindex.indexH, 'readonly':read_only})
    # set_props("indexK", {'value':peakindex.indexK, 'readonly':read_only})
    # set_props("indexL", {'value':peakindex.indexL, 'readonly':read_only})
    set_props("indexCone", {'value':peakindex.indexCone, 'readonly':read_only})
    set_props("energyUnit", {'value':peakindex.energyUnit, 'readonly':read_only})
    set_props("exposureUnit", {'value':peakindex.exposureUnit, 'readonly':read_only})
    set_props("cosmicFilter", {'value':peakindex.cosmicFilter, 'disabled':read_only})
    set_props("recipLatticeUnit", {'value':peakindex.recipLatticeUnit, 'readonly':read_only})
    set_props("latticeParametersUnit", {'value':peakindex.latticeParametersUnit, 'readonly':read_only})
    # set_props("peaksearchPath", {'value':peakindex.peaksearchPath, 'readonly':read_only})
    # set_props("p2qPath", {'value':peakindex.p2qPath, 'readonly':read_only})
    # set_props("indexingPath", {'value':peakindex.indexingPath, 'readonly':read_only})
    set_props("outputFolder", {'value':peakindex.outputFolder, 'readonly':read_only})
    set_props("geoFile", {'value':peakindex.geoFile, 'readonly':read_only})
    set_props("crystFile", {'value':peakindex.crystFile, 'readonly':read_only})
    set_props("depth", {'value':peakindex.depth, 'readonly':read_only})
    set_props("beamline", {'value':peakindex.beamline, 'readonly':read_only})
    # set_props("cosmicFilter", {'value':peakindex.cosmicFilter, 'readonly':read_only})

    # User text
    set_props("author", {'value':peakindex.author, 'readonly':read_only})
    set_props("notes", {'value':peakindex.notes, 'readonly':read_only})





