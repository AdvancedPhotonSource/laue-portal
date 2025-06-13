import dash_bootstrap_components as dbc
from dash import html, set_props
from laue_portal.components.form_base import _stack, _field, _ckbx
import laue_portal.database.db_utils as db_utils
import laue_portal.database.db_schema as db_schema
from sqlalchemy.orm import Session

wire_recon_form = dbc.Row(
                [
                    dbc.Accordion(
                        [
                        dbc.AccordionItem(
                            [
                                # _stack(
                                #     [
                                #         _field("Frame Start", 'frame_start', size='sm'),
                                #         _field("Frame End", 'frame_end', size='sm'),
                                #     ]
                                # ),
                                # _stack(
                                #     [
                                #         _field("X Start", 'x_start', size='sm'),
                                #         _field("X End", 'x_end', size='sm'),
                                #         _field("Y Start", 'y_start', size='sm'),
                                #         _field("Y End", 'y_end', size='sm'),
                                #     ]
                                # ),
                                _stack(
                                    [
                                        _field("Depth Start [µm]", 'depth_start', size='md'),
                                        _field("Depth End [µm]", 'depth_end', size='md'),
                                        _field("Depth Step [µm]", 'depth_resolution', size='md'), #'depth_step'
                                    ]
                                ),
                                # _stack(
                                #     [
                                #         _field("Recon Name", 'recon_name', size='lg'),
                                #     ]
                                # ),
                            ],
                            title="Wire Recon Parameters",
                            item_id="item-1",
                        ),
                        dbc.AccordionItem(
                            [
                                _stack(
                                    [
                                        # _field("Dataset", "dataset", size='lg'),
                                        _field("Scan Number", "scanNumber", size='md'),
                                    ]
                                ),
                                # _stack(
                                #     [
                                #         _field("Files Path", "filefolder", size='hg'), #'file_path'
                                #     ]
                                # ),
                                # _stack(
                                #     [
                                #         _field("Filename Prefix", "filenamePrefix", size='lg'),
                                #     ]
                                # ),
                                # # _stack(
                                # #     [
                                # #         _field("Scan Point (Inner Index) Range Start", "scanPointStart", size='md'),
                                # #         _field("Scan Point (Inner Index) Range End", "scanPointEnd", size='md'),
                                # #     ]
                                # # ),
                                # _stack(
                                #     [
                                #         _field("Geo File", "geoFile", size='hg'),
                                #     ]
                                # ),
                                # _stack(
                                #     [
                                #         _field("Output Path", "outputFolder", size='hg'),#'file_output'
                                #     ]
                                # ),
                            ],
                            title="File Parameters",
                            item_id="item-2",
                        ),
                        ],
                        always_open=True,
                        start_collapsed=False,
                        active_item=["item-1","item-2"]
                    ),
                ],
                style={'width': '100%', 'overflow-x': 'auto'}
        )

def set_wire_recon_form_props(wirerecon, read_only=False):
    set_props("scanNumber", {'value':wirerecon.scanNumber, 'readonly':read_only})
    
    set_props("depth_start", {'value':wirerecon.depth_start, 'readonly':read_only})
    set_props("depth_end", {'value':wirerecon.depth_end, 'readonly':read_only})
    set_props("depth_resolution", {'value':wirerecon.depth_resolution, 'readonly':read_only})

    # with Session(db_utils.ENGINE) as session:
    #     catalog = session.query(db_schema.Catalog).filter(db_schema.Catalog.scanNumber == wirerecon.scanNumber).first()   
    #     if catalog:
    #         set_props("filefolder", {'value':catalog.filefolder, 'readonly':True})
    #         set_props("filenamePrefix", {'value':catalog.filenamePrefix, 'readonly':True})
    #         set_props("outputFolder", {'value':catalog.outputFolder, 'readonly':True})
    #         set_props("geoFile", {'value':catalog.geoFile, 'readonly':True})