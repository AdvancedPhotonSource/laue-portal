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
                                        _select("Aperture", 'aperture',
                                            [
                                                {"label": "None", "value": None},
                                                {"label": "Wire", "value": "wire"},
                                                {"label": "Coded Aperture", "value": "mask"},
                                            ],
                                            size='sm',
                                            kwargs={'placeholder': 'Select:'},
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
                                        _field("Files Path", "filefolder"),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Filename Prefix", "filenamePrefix", size='lg'),
                                    ]
                                ),
                            ],
                            title="File Parameters",
                            item_id="item-2",
                        ),
                        dbc.AccordionItem(
                            [
                                _stack(
                                    [
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
                        active_item=["item-1", "item-2", "item-3"]
                    ),
                ],
                style={'width': '100%', 'overflow-x': 'auto'}
        )


def set_catalog_form_props(catalog, read_only=False):
    set_props("filefolder", {'value': catalog.filefolder, 'readonly': read_only})
    set_props("filenamePrefix", {'value': ','.join(catalog.filenamePrefix), 'readonly': read_only})
    set_props("aperture", {'value': catalog.aperture, 'disabled': read_only})
    set_props("sample_name", {'value': catalog.sample_name, 'readonly': read_only})
    set_props("notes", {'value': catalog.notes, 'readonly': read_only})