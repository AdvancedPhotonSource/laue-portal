import dash_bootstrap_components as dbc
from dash import html, set_props
from laue_portal.components.form_base import _stack, _field, _select, _notes


wire_recon_form = dbc.Row(
                [
                    dbc.Accordion(
                        [
                        dbc.AccordionItem(
                            [
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            _field("Scan Number", "scanNumber",
                                                    kwargs={
                                                        "placeholder": "e.g. 123 or 123, 126, 234 or 234-240",
                                                    }),
                                            className="flex-grow-1",          # THIS makes it expand
                                            style={"minWidth": 0},            # avoid overflow when very narrow
                                        ),
                                        dbc.Col(
                                            dbc.Button(
                                                "Update path fields",
                                                id="wirerecon-update-path-fields-btn",
                                                color="secondary",
                                                size="md",
                                                style={"minWidth": "220px", "whiteSpace": "nowrap"},  # fixed/min size
                                            ),
                                            width="auto",                      # column sizes to content
                                            className="d-flex justify-content-end mb-3",  # optional: keep at right edge
                                        ),
                                    ],
                                    align="center",
                                ),
                                _stack(
                                    [
                                        _field("Root Path", "root_path"),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Folder Path", "data_path"),
                                    ]
                                ),
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            html.Div(
                                                [
                                                    _field("Filename", "filenamePrefix",
                                                            kwargs={
                                                                "placeholder": "e.g. Si_%d.h5 or Si_*%d.h5",
                                                                "list": "wirerecon-filename-templates",  # link to datalist below
                                                            }),
                                                    # just as example
                                                    html.Datalist(
                                                        id="wirerecon-filename-templates",
                                                        children=[
                                                                html.Option(value="Si1_PE2_%d.h5",    label="Si1_PE2_%d.h5   (files 1–245)"),
                                                                html.Option(value="Si1_Eiger1_%d.h5", label="Si1_Eiger1_%d.h5 (files 3–198)"),
                                                                html.Option(value="Si1_*_%d.h5",        label="Si1_*_%d.h5        (files 1–245)"),
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
                                                id="wirerecon-check-filenames-btn",
                                                color="secondary",
                                                size="md",
                                                style={"minWidth": "220px", "whiteSpace": "nowrap"},
                                            ),
                                            width="auto",
                                            className="d-flex justify-content-end mb-3",
                                        ),
                                    ],
                                    align="center",
                                ),
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            _field("Range of Files", "scanPoints",
                                                    kwargs={
                                                        "placeholder": "e.g. 1-10 or 1,5,8,9 or 1-4,10-21"
                                                    }),
                                            className="flex-grow-1",          # THIS makes it expand
                                            style={"minWidth": 0},            # avoid overflow when very narrow
                                        ),
                                        dbc.Col(
                                            dbc.Button(
                                                "Load indices from file",#"Load file indices as list",
                                                id="wirerecon-load-file-indices-btn",
                                                color="secondary",
                                                size="md",
                                                style={"minWidth": "220px", "whiteSpace": "nowrap"},  # fixed/min size
                                            ),
                                            width="auto",                      # column sizes to content
                                            className="d-flex justify-content-end mb-3",  # optional: keep at right edge
                                        ),
                                    ],
                                    align="center",
                                    ),
                                _stack(
                                    [
                                        _field("Output Path", "outputFolder"),
                                    ]
                                ),
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            _field("Geometry File", "geoFile"),
                                            className="flex-grow-1",
                                            style={"minWidth": 150},
                                        ),
                                        dbc.Col(
                                            dbc.Row(
                                                [
                                                    dbc.Col(
                                                        dbc.Button(
                                                            "Use default",
                                                            id="wirerecon-load-default-geo-btn",
                                                            color="secondary",
                                                            size="md",
                                                            style={"minWidth": "120px", "whiteSpace": "nowrap"},
                                                        ),
                                                        width="auto",
                                                    ),
                                                    dbc.Col(
                                                        dbc.Button(
                                                            "Edit current",
                                                            id="wirerecon-view-modify-params-btn",
                                                            color="secondary",
                                                            size="md",
                                                            style={"minWidth": "220px", "whiteSpace": "nowrap"},
                                                        ),
                                                        width="auto",
                                                    ),
                                                ],
                                                className="g-2 justify-content-end",  # g-2 adds a nice gap
                                            ),
                                            xs=12, md="auto",  # whole block drops under input on small screens
                                            className="mb-3",
                                        ),
                                    ],
                                    className="g-2",
                                    align="center",
                                ),
                            ],
                            title="Files",#"File Parameters"
                            item_id="item-1",
                        ),
                        dbc.AccordionItem(
                            [
                                _stack(
                                    [
                                        dbc.Row(
                                            [
                                                dbc.Col(
                                                    _field("Depth Start [µm]", 'depth_start', size='md'),
                                                    className="flex-grow-1",          # THIS makes it expand
                                                    style={"minWidth": 100},            # avoid overflow when very narrow
                                                    # width = "auto",
                                                    xs=12, 
                                                    md=4,
                                                ),
                                                dbc.Col(
                                                _field("Depth End [µm]", 'depth_end', size='md'),
                                                    className="flex-grow-1",          # THIS makes it expand
                                                    style={"minWidth": 100},            # avoid overflow when very narrow
                                                    # width = "auto",
                                                    xs=12, 
                                                    md=4,
                                                ),
                                                dbc.Col(
                                                    _field("Depth Resolution [µm]", 'depth_resolution', size='md'),
                                                    className="flex-grow-1",          # THIS makes it expand
                                                    style={"minWidth": 100},            # avoid overflow when very narrow
                                                    # width = "auto",
                                                    xs=12, 
                                                    md=4,
                                                ),
                                            ],
                                            # align="center",
                                        ),
                                    ]
                                ),
                                _stack(
                                    [
                                        _select("Wire Edges", "wire_edges",
                                            [
                                                {"label": "Leading Edge", "value": "leading"},
                                                {"label": "Trailing Edge", "value": "trailing"},
                                                {"label": "Both Edges", "value": "both"},
                                            ],
                                            size='md',
                                            kwargs={'placeholder':"Select:"}
                                        ),
                                        _field("Intensity percentile", 'percent_brightest', size='md'), # "Percentage of pixels to process"
                                        # _field("Detector", 'detector', size='md'), # default to detector number 0, but never pass this argument. It will get this from geo file.
                                    ]
                                ),
                            ],
                            title="Wire Reconstruction Parameters",
                            item_id="item-2",
                        ),
                        dbc.AccordionItem(
                            [
                                _notes("notes")
                            ],
                            title="User Text",
                            item_id="item-3",
                        ),
                        ],
                        always_open=True,
                        start_collapsed=False,
                        active_item=["item-1","item-2","item-3"]
                    ),
                ],
                style={'width': '100%', 'overflow-x': 'auto'}
        )

def set_wire_recon_form_props(wirerecon, read_only=False):
    set_props("scanNumber", {'value':wirerecon.scanNumber, 'readonly':read_only})
    
    # File paths
    set_props("root_path", {'value':wirerecon.root_path, 'readonly':read_only})
    set_props("data_path", {'value':wirerecon.data_path, 'readonly':read_only})
    set_props("filenamePrefix", {'value':','.join(wirerecon.filenamePrefix), 'readonly':read_only})
    
    # User text
    # set_props("author", {'value':wirerecon.author, 'readonly':read_only})
    set_props("notes", {'value':wirerecon.notes, 'readonly':read_only})
    
    # Wire recon parameters
    set_props("geoFile", {'value':wirerecon.geoFile, 'readonly':read_only})
    set_props("percent_brightest", {'value':wirerecon.percent_brightest, 'readonly':read_only})
    set_props("wire_edges", {'value':wirerecon.wire_edges, 'disabled':read_only})  # Wire edge field

    # Depth parameters
    set_props("depth_start", {'value':wirerecon.depth_start, 'readonly':read_only})
    set_props("depth_end", {'value':wirerecon.depth_end, 'readonly':read_only})
    set_props("depth_resolution", {'value':wirerecon.depth_resolution, 'readonly':read_only})
    
    # Files
    set_props("scanPoints", {'value':wirerecon.scanPoints, 'readonly':read_only})  # Range of files field

    # Output
    set_props("outputFolder", {'value':wirerecon.outputFolder, 'readonly':read_only})
    
    # Additional form fields
    set_props("detector", {'value': None, 'readonly':True})  # Default detector number '0 or auto'
