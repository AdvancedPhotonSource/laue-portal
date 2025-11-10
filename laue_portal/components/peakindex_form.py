import dash_bootstrap_components as dbc
from dash import html, set_props
from laue_portal.components.form_base import _stack, _field, _select, _ckbx
from laue_portal.pages.validation_helpers import get_num_inputs_from_fields
import laue_portal.database.db_schema as db_schema
import re


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
                                            _field("Geometry File", "geoFile", size='md',
                                                    kwargs={
                                                        "type": "text",
                                                        "placeholder": "",
                                                    }),
                                            className="flex-grow-1",
                                            style={"minWidth": 150},
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
                                        _field("Max no. of Spots (empty for all)", "max_peaks", size='md'),
                                    ]
                                ),
                                    _stack(
                                    [
                                        _field("Depth [µm] (empty -> auto)", "depth", size='md'),
                                        
                                    ]
                                ),
                                # dbc.Button(
                                #     "Show Path to Program",
                                #     id="collapse2-button",
                                #     className="mb-3",
                                #     color="primary",
                                #     n_clicks=0,
                                # ),
                                # dbc.Collapse(
                                #     [
                                #         _field("Indexing Path", "indexingPath"),
                                #     ],
                                # id="collapse2",
                                # is_open=False,
                                # ),
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
    set_props("filenamePrefix", {'value':','.join(peakindex.filenamePrefix), 'readonly':read_only})
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


def make_IDnumber(SN=None, WR=None, MR=None, PI=None, delimiter="; "): # "; ".join(map(str, values)))
    """
    Create ID number string from scan, wire recon, recon, and peakindex IDs.
    Handles None values, "None" strings, and pooled values.
    
    Parameters:
    - SN: Scan number(s) - can be single value or semicolon-delimited string
    - WR: Wire recon ID(s) - can be single value or semicolon-delimited string
    - MR: Recon ID(s) - can be single value or semicolon-delimited string
    - PI: Peak index ID(s) - can be single value or semicolon-delimited string
    - delimiter: Delimiter used to separate multiple values (default "; ")
    
    Returns:
    - String with ID number(s) in priority order (PI > MR > WR > SN)
    - Returns None if all inputs are None or no valid entries found
    - Deduplicates if all entries are identical
    
    Raises:
    - ValueError: If field lengths don't match expected pattern (1 or max_len)
    """
    # Helper function to check if value is None or "None"
    def is_none_value(val):
        return val is None or str(val).strip().lower() == 'none'
    
    # Build params dict for get_num_inputs_from_params
    params_dict = {
        'SN': SN,
        'WR': WR,
        'MR': MR,
        'PI': PI
    }
    
    # Get max length across all parameters
    max_len = get_num_inputs_from_fields(params_dict, delimiter)
    
    # Build ID_lists directly from params_dict, excluding None values
    ID_lists = {}
    for key, value in params_dict.items():
        if not is_none_value(value):
            # Split into entries
            entries = str(value).split(delimiter)
            
            # Validate and pad to max_len
            if len(entries) == 1 and max_len > 1:
                # Duplicate single value (collapsed from pooling)
                ID_lists[key] = entries * max_len
            elif len(entries) == max_len:
                # Already correct length
                ID_lists[key] = entries
            else:
                # Unexpected length - this shouldn't happen with proper pooling
                raise ValueError(
                    f"Field {key} has {len(entries)} entries but expected 1 or {max_len}. "
                    f"Value: {value}"
                )
    
    # If all are None, return None
    if not ID_lists:
        return None
    
    # Build ID strings with priority: PI > MR > WR > SN
    IDnumbers = []
    for i in range(max_len):
        if 'PI' in ID_lists and ID_lists['PI'][i] and not is_none_value(ID_lists['PI'][i]):
            IDnumbers.append(f"PI{ID_lists['PI'][i]}")
        elif 'MR' in ID_lists and ID_lists['MR'][i] and not is_none_value(ID_lists['MR'][i]):
            IDnumbers.append(f"MR{ID_lists['MR'][i]}")
        elif 'WR' in ID_lists and ID_lists['WR'][i] and not is_none_value(ID_lists['WR'][i]):
            IDnumbers.append(f"WR{ID_lists['WR'][i]}")
        elif 'SN' in ID_lists and ID_lists['SN'][i] and not is_none_value(ID_lists['SN'][i]):
            IDnumbers.append(f"SN{ID_lists['SN'][i]}")
    
    # If no valid entries were found, return None
    if not IDnumbers:
        return None
    
    # If all entries are identical, return just one
    if all(id_num == IDnumbers[0] for id_num in IDnumbers):
        return IDnumbers[0]
    
    return delimiter.join(IDnumbers)


def parse_IDnumber(IDnumber, session, delimiter="; "):
    """
    Parse IDnumber string and query database for parent IDs.
    Reverses the operation of make_IDnumber and fills in parent relationships.
    
    Parameters:
    - IDnumber: String like "PI5", "MR3; MR4", "WR1", "SN276994", etc.
                Can also be None or empty string.
    - session: SQLAlchemy session for database queries
    - delimiter: Delimiter used in the IDnumber string (default "; ")
    
    Returns:
    - dict: {'scanNumber': value, 'wirerecon_id': value, 'recon_id': value, 'peakindex_id': value}
      where value can be:
      - None (if that ID type wasn't present in any entry)
      - Single value string (if all entries were identical, e.g., "5")
      - Semicolon-delimited string (if multiple different values, e.g., "3; 4; 5")
      - Semicolon-delimited string with None (e.g., "3; None; 5" for pooled data where some entries lack that parent ID)
    
    Database Lookup Rules:
    - If peakindex_id is provided: Queries PeakIndex table for scanNumber, recon_id, wirerecon_id
    - If recon_id is provided: Queries Recon table for scanNumber
    - If wirerecon_id is provided: Queries WireRecon table for scanNumber
    - If scanNumber is provided: No database query needed (it's the root)
    - Does NOT query for child IDs (e.g., if scanNumber provided, doesn't look up wirerecon_id/recon_id/peakindex_id)
    
    Raises:
    - ValueError: If IDnumber format is invalid
    
    Examples:
    - parse_IDnumber("PI5", session) 
      → Queries PeakIndex.peakindex_id=5
      → Returns {'scanNumber': '276994', 'wirerecon_id': None, 'recon_id': '3', 'peakindex_id': '5'}
      
    - parse_IDnumber("MR3; MR4", session)
      → Queries Recon.recon_id IN (3,4)
      → Returns {'scanNumber': '100; 101', 'wirerecon_id': None, 'recon_id': '3; 4', 'peakindex_id': None}
      
    - parse_IDnumber("WR1", session)
      → Queries WireRecon.wirerecon_id=1
      → Returns {'scanNumber': '276994', 'wirerecon_id': '1', 'recon_id': None, 'peakindex_id': None}
      
    - parse_IDnumber("SN276994", session)
      → No database query
      → Returns {'scanNumber': '276994', 'wirerecon_id': None, 'recon_id': None, 'peakindex_id': None}
      
    - parse_IDnumber("PI5; PI6", session)
      → Queries PeakIndex.peakindex_id IN (5,6)
      → If PI5 has recon_id=3 but PI6 has recon_id=None
      → Returns {'scanNumber': '276994; 276995', 'wirerecon_id': None, 'recon_id': '3; None', 'peakindex_id': '5; 6'}
    """
    # Initialize result dict with proper field names, each containing a list
    result = {
        'scanNumber': [],
        'wirerecon_id': [],
        'recon_id': [],
        'peakindex_id': []
    }
    
    # Handle None or empty input
    if not IDnumber or str(IDnumber).strip().lower() in ['none', '']:
        return {k: None for k in result.keys()}
    
    # Split by delimiter to get individual ID entries
    entries = str(IDnumber).split(delimiter)
    
    # Define prefix to field name mapping
    prefix_map = {
        'SN': 'scanNumber',
        'WR': 'wirerecon_id',
        'MR': 'recon_id',
        'PI': 'peakindex_id'
    }
    
    # Process each entry
    for entry in entries:
        if not entry or entry.lower() == 'none':
            continue
        
        # Use regex to match prefix and number
        # Pattern: (SN|WR|MR|PI) followed by one or more digits
        match = re.match(r'^(SN|WR|MR|PI)(\d+)$', entry.upper())
        
        if match:
            prefix = match.group(1)
            number_str = match.group(2)
            field_name = prefix_map[prefix]
            
            # Add to result list for this field
            result[field_name].append(number_str)
            
            # Query database for parent IDs based on field_name
            if field_name == 'peakindex_id':
                pi_id_int = int(number_str)
                peakindex_data = session.query(db_schema.PeakIndex).filter(
                    db_schema.PeakIndex.peakindex_id == pi_id_int
                ).first()
                
                if peakindex_data:
                    result['scanNumber'].append(str(peakindex_data.scanNumber))
                    # Always append, even if None
                    result['recon_id'].append(str(peakindex_data.recon_id) if peakindex_data.recon_id else None)
                    result['wirerecon_id'].append(str(peakindex_data.wirerecon_id) if peakindex_data.wirerecon_id else None)
                else:
                    raise ValueError(f"PeakIndex ID {number_str} not found in database")
            
            elif field_name == 'recon_id':
                mr_id_int = int(number_str)
                recon_data = session.query(db_schema.Recon).filter(
                    db_schema.Recon.recon_id == mr_id_int
                ).first()
                
                if recon_data:
                    result['scanNumber'].append(str(recon_data.scanNumber))
                else:
                    raise ValueError(f"Recon ID {number_str} not found in database")
            
            elif field_name == 'wirerecon_id':
                wr_id_int = int(number_str)
                wirerecon_data = session.query(db_schema.WireRecon).filter(
                    db_schema.WireRecon.wirerecon_id == wr_id_int
                ).first()
                
                if wirerecon_data:
                    result['scanNumber'].append(str(wirerecon_data.scanNumber))
                else:
                    raise ValueError(f"WireRecon ID {number_str} not found in database")
            
            # If field_name == 'scanNumber', no database query needed
        else:
            raise ValueError(f"Invalid IDnumber entry: '{entry}' - expected format: (SN|WR|MR|PI)###")
    
    # Convert lists to final format (None, single value, or delimited string)
    final_result = {}
    for field_name, id_list in result.items():
        if not id_list:
            final_result[field_name] = None
        elif all(id_val == id_list[0] for id_val in id_list):
            # All values are identical, return single value
            final_result[field_name] = id_list[0]
        else:
            # Return semicolon-delimited string
            final_result[field_name] = delimiter.join(id_list)
    
    return final_result


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
