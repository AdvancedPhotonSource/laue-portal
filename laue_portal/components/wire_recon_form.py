import dash_bootstrap_components as dbc
from dash import html, set_props
from laue_portal.components.form_base import _stack, _field


wire_recon_form = dbc.Row(
                [
                    dbc.Accordion(
                        [
                        dbc.AccordionItem(
                            [
                                _stack(
                                    [
                                        _field("Scan Number", "scanNumber", size='md'),
                                        _field("Root Path", "root_path", size='md'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Data Path", "data_path", size='md'),
                                        _field("Filename Prefix", "filenamePrefix", size='md'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Range of Files", "scanPoints", size='md'),
                                        dbc.Button("Load file indices as list", id="load-file-indices-btn", color="secondary", size="sm"),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Output Path", "outputFolder", size='hg'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Geometry File", "geoFile", size='md'),
                                        dbc.Button("Load default", id="load-default-geo-btn", color="secondary", size="sm"),
                                        dbc.Button("View / Modify Parameters", id="view-modify-params-btn", color="secondary", size="sm"),
                                    ]
                                ),
                            ],
                            title="Files",#"File Parameters"
                            item_id="item-1",
                        ),
                        dbc.AccordionItem(
                            [
                                _stack(
                                    [
                                        _field("Depth Start [µm]", 'depth_start', size='md'),
                                        _field("Depth End [µm]", 'depth_end', size='md'),
                                        _field("Depth Resolution [µm]", 'depth_resolution', size='md'),
                                    ]
                                ),
                                _stack(
                                    [
                                        dbc.Select(
                                            placeholder="Wire Edges",
                                            options=[
                                                {"label": "Leading Edge", "value": "leading"},
                                                {"label": "Trailing Edge", "value": "trailing"},
                                                {"label": "Both Edges", "value": "both"},
                                            ],
                                            style={'width': 350}, #size='md'
                                            id="wire_edges",
                                        ),
                                        _field("Percentage of pixels to process", 'percent_brightest', size='md'),
                                        _field("Detector", 'detector', size='md'), # default to detector number 0, but never pass this argument. It will get this from geo file.
                                    ]
                                ),
                            ],
                            title="Wire Reconstruction Parameters",
                            item_id="item-2",
                        ),
                        dbc.AccordionItem(
                            [
                                _stack(
                                    [
                                        _field("Author", "author", size='md', kwargs={'placeholder': 'Required'}),
                                    ]
                                ),
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
    # Basic fields
    # set_props("wirerecon_id", {'value':wirerecon.wirerecon_id, 'readonly':read_only})
    set_props("scanNumber", {'value':wirerecon.scanNumber, 'readonly':read_only})
    
    # File paths
    set_props("root_path", {'value':wirerecon.root_path, 'readonly':True})
    set_props("data_path", {'value':wirerecon.data_path, 'readonly':True})
    set_props("filenamePrefix", {'value':wirerecon.filenamePrefix, 'readonly':True})
    
    # Wire recon parameters
    set_props("geoFile", {'value':wirerecon.geoFile, 'readonly':read_only})
    set_props("percent_brightest", {'value':wirerecon.percent_brightest, 'readonly':read_only})
    
    # Depth parameters
    set_props("depth_start", {'value':wirerecon.depth_start, 'readonly':read_only})
    set_props("depth_end", {'value':wirerecon.depth_end, 'readonly':read_only})
    set_props("depth_resolution", {'value':wirerecon.depth_resolution, 'readonly':read_only})
    
    # Output parameters
    set_props("outputFolder", {'value':wirerecon.outputFolder, 'readonly':read_only})
    
    # Additional form fields
    set_props("scanPoints", {'value':wirerecon.scanPoints, 'readonly':read_only})  # Range of files field
    set_props("wire_edges", {'value':wirerecon.wire_edges, 'readonly':read_only})  # Wire edge field
    set_props("detector", {'value': '0 or auto', 'readonly':True})  # Default detector number
    
    # User text
    set_props("author", {'value':wirerecon.author, 'readonly':read_only})
    set_props("notes", {'value':wirerecon.notes, 'readonly':read_only})
