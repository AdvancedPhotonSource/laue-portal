import dash_bootstrap_components as dbc
from dash import html, set_props
from laue_portal.components.form_base import _stack, _field, _select

catalog_form = dbc.Row(
                [
                    dbc.Accordion(
                        [
                        dbc.AccordionItem(
                            [
                                _stack(
                                    [
                                        # _field("Dataset", "dataset", size='lg'),
                                        # _field("Scan Number", "scanNumber", size='md'),
                                    ]
                                ),
                                _stack(
                                    [
                                        #_field("Aperture", 'aperture', size='lg'),
                                        _select("Aperture", 'aperture',
                                            [
                                                {"label": "None", "value": None},
                                                {"label": "Wire", "value": "wire"},
                                                {"label": "Coded Aperture", "value": "mask"},
                                            ],
                                            size='sm',
                                            kwargs={'placeholder':'Select:'}, 
                                        ),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Sample Name", 'sample_name', size='lg'),
                                    ]
                                ),
                            ],
                            title="Scan Info",
                            item_id="item-1",
                        ),
                        dbc.AccordionItem(
                            [
                                _stack(
                                    [
                                        _field("Files Path", "filefolder", size='hg'), #'file_path'
                                    ]
                                ),
                                _stack(
                                    [
                                        # _field("Filename Prefix", "filenamePrefix", size='lg'),
                                        _field("Filename Prefix 1", "filenamePrefix1", size='lg'),
                                        _field("Filename Prefix 2", "filenamePrefix2", size='lg'),
                                        _field("Filename Prefix 3", "filenamePrefix3", size='lg'),
                                        _field("Filename Prefix 4", "filenamePrefix4", size='lg'),
                                    ]
                                ),
                                # _stack(
                                #     [
                                #         _field("Scan Point (Inner Index) Range Start", "scanPointStart", size='md'),
                                #         _field("Scan Point (Inner Index) Range End", "scanPointEnd", size='md'),
                                #     ]
                                # ),
                            ],
                            title="File Parameters",
                            item_id="item-2",
                        ),
                        dbc.AccordionItem(
                            [
                                _stack(
                                    [
                                        # _field("Notes", "notes", size='hg')
                                        dbc.Textarea(
                                            id="notes",
                                            style={"width": "100%", "minHeight": "100px"},
                                        )
                                    ]
                                ),
                            ],
                            title="Notes",
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

def set_catalog_form_props(catalog, read_only=False):
    # set_props("scanNumber", {'value':catalog.scanNumber, 'readonly':read_only})

    set_props("filefolder", {'value':catalog.filefolder, 'readonly':read_only})
    # set_props("filenamePrefix", {'value':catalog.filenamePrefix, 'readonly':read_only})
    for i, filenamePrefix in enumerate(catalog.filenamePrefix):
        set_props(f"filenamePrefix{i+1}", {'value':filenamePrefix, 'readonly':read_only})

    set_props("aperture", {'value':catalog.aperture, 'disabled':read_only})
    set_props("sample_name", {'value':catalog.sample_name, 'readonly':read_only})
    set_props("notes", {'value':catalog.notes, 'readonly':read_only})
