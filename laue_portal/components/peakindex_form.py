import dash_bootstrap_components as dbc
from dash import html, dcc, set_props
from laue_portal.components.form_base import _stack, _field, _select, _ckbx
from laue_portal.database.db_utils import make_IDnumber, parse_IDnumber
import laue_portal.database.db_schema as db_schema


peakindex_form = dbc.Row(
                [
                    dbc.Col(
                    dbc.Accordion(
                        [
                        dbc.AccordionItem(
                            [
                                dbc.Row(
                                        [
                                            dbc.Col(
                                                _field("ID Number: SN# | WR# | MR# | PI#", "IDnumber",
                                                        kwargs={
                                                            "type": "text",
                                                            "placeholder": "e.g. SN123456 or WR1 or MR3 or PI4",
                                                        }),
                                                className="flex-grow-1",          # THIS makes it expand
                                                style={"minWidth": 0},            # avoid overflow when very narrow
                                            ),
                                            dbc.Col(
                                                dbc.Button(
                                                    "Update path fields",
                                                    id="peakindex-update-path-fields-btn",
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
                                                    _field("Filename", "filenamePrefix",
                                                            kwargs={
                                                                "type": "text",
                                                                "placeholder": "e.g. Si_%d.h5 or Si_*%d.h5",
                                                                "list": "peakindex-filename-templates",  # link to datalist below
                                                            }),
                                                    # just as example
                                                    html.Datalist(
                                                        id="peakindex-filename-templates",
                                                        children=[
                                                                html.Option(value="Si1_PE2_%d.h5",    label="Si1_PE2_%d.h5   (files 1–245)"),
                                                                html.Option(value="Si1_Eiger1_%d.h5", label="Si1_Eiger1_%d.h5 (files 3–198)"),
                                                                html.Option(value="Si_*_%d.h5",        label="Si_*_%d.h5        (files 1–245)"),
                                                            ]
                                                    ),
                                                    # Hidden store for cached patterns per path
                                                    dcc.Store(id='peakindex-cached-patterns', data={}),
                                                ]
                                            ),
                                            className="flex-grow-1",
                                            style={"minWidth": 0},
                                        ),
                                        dbc.Col(
                                            dbc.Button(
                                                "Find file names",
                                                id="peakindex-check-filenames-btn",
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
                                                _field("Scan indices", "scanPoints", size='md',
                                                        kwargs={
                                                            "type": "text",
                                                            "placeholder": "e.g. 1-10 or 1,5,8,9 or 1-4,10-21",
                                                        }),
                                                className="flex-grow-1",          # THIS makes it expand
                                                style={"minWidth": 0},            # avoid overflow when very narrow
                                            ),
                                            dbc.Col(
                                                _field("Depth indices", "depthRange", size='md',
                                                        kwargs={
                                                            "type": "text",
                                                            "placeholder": "e.g. 1-10 or 1,5,8,9 or 1-4,10-21",
                                                        }),
                                                className="flex-grow-1",          # THIS makes it expand
                                                style={"minWidth": 0},            # avoid overflow when very narrow
                                            ),
                                            dbc.Col(
                                                dbc.Button(
                                                    "Load indices from file",
                                                    id="peakindex-load-file-indices-btn",
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
                                            _field("Geometry File", "geoFile", 
                                                    kwargs={
                                                        "type": "text",
                                                        "placeholder": "",
                                                    }),
                                            className="flex-grow-1",
                                            style={"minWidth": 0},
                                        ),
                                        dbc.Col(
                                            dbc.Row(
                                                [
                                                    dbc.Col(
                                                        dbc.Button(
                                                            "Load default",
                                                            id="peakindex-load-default-geo-btn",
                                                            color="secondary",
                                                            size="md",
                                                            style={"minWidth": "120px", "whiteSpace": "nowrap"},
                                                        ),
                                                        width="auto",
                                                    ),
                                                    dbc.Col(
                                                        dbc.Button(
                                                            "Load...",
                                                            id="peakindex-load-from-geo-btn",
                                                            color="secondary",
                                                            size="md",
                                                            style={"minWidth": "120px", "whiteSpace": "nowrap"},
                                                        ),
                                                        width="auto",
                                                    ),
                                                    dbc.Col(
                                                        dbc.Button(
                                                            "Edit",
                                                            id="peakindex-edit-modify-params-btn",
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
                                            className="mb-3", # fixes y alignment 
                                        ),
                                    ],
                                    className="mb-3 g-2",
                                    align="center",
                                ),
                                #]),
                               
                                
                                _field("Output Path", "outputFolder"),
                                
                                
                                
                                
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
                                # _stack(
                                #     [
                                #         _field("Peak Program", "peakProgram", size='md'),
                                #     ]
                                # ),
                                _stack(
                                    [
                                        _field("Box Size [pixels]", "boxsize", size='md'),
                                        _field("Max R-factor", "maxRfactor", size='md'),
                                        _field("Threshold (empty -> auto)", "threshold", size='md'),
                                        _field("Threshold Ratio (empty -> auto)", "thresholdRatio", size='md'),
                                        
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Min Spot Size [pixels]", "min_size", size='md'),
                                        _field("Min Spot Separation [pixels]", "min_separation", size='md'),
                                        _field("Max No. of Spots (empty for all)", "max_number", size='md')
                                    ]
                                ),
                                _stack(
                                    [
                                        #_field("Peak Shape", "peakShape", size='lg'),
                                        _select("Peak Shape", "peakShape",
                                            [
                                                {"label": "Lorentzian", "value": "Lorentzian"},
                                                {"label": "Gaussian", "value": "Gaussian"},
                                            ],
                                            size='md',
                                            kwargs={'placeholder':'Select:'}, 
                                        ),
                                        _ckbx("Smooth peak before fitting", "smooth", size='md'),
                                        _ckbx("Cosmic Filter", "cosmicFilter", size='md'),
                                        # _ckbx("Cosmic Filter", "cosmicFilter", size='lg'),
                                    ]
                                ),
                                # _stack(
                                #     [
                                #         _field("Detector CropX1", "detectorCropX1", size='md'),
                                #         _field("Detector CropY1", "detectorCropY1", size='md'),
                                #     ]
                                # ),
                                # _stack(
                                #     [
                                #         _field("Detector CropX2", "detectorCropX2", size='md'),
                                #         _field("Detector CropY2", "detectorCropY2", size='md'),
                                #     ]
                                # ),
                                
                                dbc.Row(
                                        [
                                            dbc.Col(
                                                _field("Mask File", "maskFile",
                                                        kwargs={
                                                            "type": "text",
                                                            "placeholder": "",
                                                        }),
                                                className="flex-grow-1",          # THIS makes it expand
                                                style={"minWidth": 0},            # avoid overflow when very narrow
                                            ),
                                            dbc.Col(
                                                dbc.Button(
                                                    "Load...",
                                                    id="peakindex-load-mask-file-btn",
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
                                
                                
                                
                                # _stack(
                                #     [
                                #         _field("Mask File", "maskFile", size='lg'),
                                #     ]
                                # ),
                                # dbc.Button(
                                #     "Show Paths to Programs",
                                #     id="collapse1-button",
                                #     className="mb-3",
                                #     color="primary",
                                #     n_clicks=0,
                                # ),
                                # dbc.Collapse(
                                #     [
                                #         _field("peaksearch Path", "peaksearchPath"),
                                #         _field("p2q Path", "p2qPath"),
                                #     ],
                                # id="collapse1",
                                # is_open=False,
                                # ),
                            ],
                            title="Peak Search Parameters",
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
                                
                                dbc.Row(
                                        [
                                            dbc.Col(
                                                _field("Crystal Structure File", "crystFile",
                                                        kwargs={
                                                            "type": "text",
                                                            "placeholder": "",
                                                        }),
                                                className="flex-grow-1",          # THIS makes it expand
                                                style={"minWidth": 0},            # avoid overflow when very narrow
                                            ),
                                            dbc.Col(
                                                dbc.Button(
                                                    "Load...",
                                                    id="peakindex-load-cryst-file-btn",
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
                                
                                # _stack(
                                #     [
                                #         _field("Crystal Structure File", "crystFile", size='lg'),
                                #     ]
                                # ),
                                _stack(
                                    [
                                        _field("Max Calc Energy [keV]", "indexKeVmaxCalc", size='md'),
                                        _field("Max Test Energy [keV]", "indexKeVmaxTest", size='md'),
                                        _field("Angle Tolerance [deg]", "indexAngleTolerance", size='md'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Central HKL", "indexHKL", size='md'),
                                        # _field("Index H", "indexH", size='md'),
                                        # _field("Index K", "indexK", size='md'),
                                        # _field("Index L", "indexL", size='md'),
                                        _field("Cone Angle [deg]", "indexCone", size='md'),
                                        _field("Max no. of Spots (empty: 200)", "max_peaks", size='md'),
                                    ]
                                ),
                                    _stack(
                                    [
                                        _field("Depth [µm] (empty -> auto)", "depth", size='md'),
                                        
                                    ]
                                ),
                            ],
                            title="Indexing Parameters",
                            item_id = "item-3",
                            className="no-border-bottom",   # 👈 add custom class
                        ),
                        
    
                        # dbc.AccordionItem(
                        #     [
                        #         _stack(
                        #             [
                        #                 _field("Energy Unit", "energyUnit", size='md'),
                        #                 _field("Exposure Unit", "exposureUnit", size='md'),
                        #             ]
                        #         ),
                        #         _stack(
                        #             [
                        #                 _field("Recip Lattice Unit", "recipLatticeUnit", size='md'),
                        #                 _field("Lattice Parameters Unit", "latticeParametersUnit", size='md'),
                        #             ]
                        #         ),
                        #         _stack(
                        #             [
                        #                 _field("Beamline", "beamline", size='md'),
                        #                 _field("Depth", "depth", size='md'),
                        #             ]
                        #         ),
                        #     ],
                        #     title="Labels",
                        # ),
                        
                        
                        
                        
                        
                        dbc.AccordionItem(
                            [
                                # _stack(
                                #     [
                                #         _field("Author", "author", size='md', kwargs={'placeholder': 'Required'}),
                                #     ]
                                # ),
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
    IDnumber = make_IDnumber(peakindex.scanNumber,peakindex.wirerecon_id,peakindex.recon_id,peakindex.peakindex_id)
    set_props("IDnumber", {'value':IDnumber, 'readonly':read_only})
    # set_props("scanNumber", {'value':peakindex.scanNumber, 'readonly':read_only})
    set_props("root_path", {'value':peakindex.root_path, 'readonly':read_only})
    set_props("data_path", {'value':peakindex.data_path, 'readonly':read_only})
    
    # Convert list to comma-separated string for form display
    filename_value = peakindex.filenamePrefix
    if isinstance(filename_value, list):
        filename_value = ', '.join(filename_value)
    set_props("filenamePrefix", {'value':filename_value, 'readonly':read_only})
    # set_props("filenamePrefix", {'value':peakindex.filenamePrefix, 'readonly':read_only})
    # set_props("recon_id", {'value':peakindex.recon_id, 'readonly':read_only})
    # set_props("wirerecon_id", {'value':peakindex.wirerecon_id, 'readonly':read_only})
    
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
    # set_props("detectorCropX1", {'value':peakindex.detectorCropX1, 'readonly':read_only})
    # set_props("detectorCropX2", {'value':peakindex.detectorCropX2, 'readonly':read_only})
    # set_props("detectorCropY1", {'value':peakindex.detectorCropY1, 'readonly':read_only})
    # set_props("detectorCropY2", {'value':peakindex.detectorCropY2, 'readonly':read_only})
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


# @callback(
#     Output("collapse1", "is_open"),
#     [Input("collapse1-button", "n_clicks")],
#     [State("collapse1", "is_open")],
# )
# def toggle_collapse12(n, is_open):
#     if n:
#         return not is_open
#     return is_open

# @callback(
#     Output("collapse2", "is_open"),
#     [Input("collapse2-button", "n_clicks")],
#     [State("collapse2", "is_open")],
# )
# def toggle_collapse2(n, is_open):
#     if n:
#         return not is_open
#     return is_open
