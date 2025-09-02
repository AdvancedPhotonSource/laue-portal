import dash_bootstrap_components as dbc
from dash import html, set_props
from laue_portal.components.form_base import _stack, _field, _ckbx
from datetime import datetime


metadata_form = dbc.Row(
                [
                    dbc.Accordion(
                        [
                        dbc.AccordionItem(
                            [
                                _stack(
                                    [
                                        _field("Scan Number", "scanNumber", size='md'),
                                        # _field("Time Epoch", "time_epoch", size='lg'),
                                        html.Div(
                                            [
                                                _field("Time Epoch", "time_epoch", size='lg'),
                                            ],
                                            style={'display': 'none'}
                                        ),
                                        _field("Time", "time", size='lg'),
                                        _field("User Name", "user_name", size='lg'),
                                    ]
                                ),
                            ],
                            title="Identifiers",
                        ),
                        dbc.AccordionItem(
                            [
                                _stack(
                                    [
                                        _field("Beam Bad", "source_beamBad", size='lg'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("CCD Shutter", "source_CCDshutter", size='lg'),
                                        _field("monoTransStatus", "source_monoTransStatus", size='lg'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Source Energy", "source_energy", size='lg'),
                                        _field("Units", "source_energy_unit", size='sm'),
                                        _field("Source Ring Current", "source_ringCurrent", size='lg'),
                                        _field("Units", "source_ringCurrent_unit", size='sm'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Source ID Gap", "source_IDgap", size='lg'),
                                        _field("Units", "source_IDgap_unit", size='sm'),
                                        _field("Source ID Taper", "source_IDtaper", size='lg'),
                                        _field("Units", "source_IDtaper_unit", size='sm'),
                                    ]
                                ),
                            ],
                            title="Source",
                        ),
                        dbc.AccordionItem(
                            [
                                _stack(
                                    [
                                        # _field("Sample X", "sample_X", size='lg'),
                                        # _field("Sample Y", "sample_Y", size='lg'),
                                        # _field("Sample Z", "sample_Z", size='lg'),
                                        _field("Sample XYZ", "sample_XYZ", size='lg'),
                                        _field("Units", "sample_XYZ_unit", size='sm'),
                                        _field("Description", "sample_XYZ_desc", size='sm'),
                                    ]
                                ),
                            ],
                            title="Sample Positioner",
                        ),
                        dbc.AccordionItem(
                            [
                                _stack(
                                    [
                                        # _field("Aperture X", "knife-edge_X", size='lg'),
                                        # _field("Aperture Y", "knife-edge_Y", size='lg'),
                                        # _field("Aperture Z", "knife-edge_Z", size='lg'),
                                        _field("Aperture XYZ", "knife-edge_XYZ", size='lg'),
                                        _field("Units", "knife-edge_XYZ_unit", size='sm'),
                                        _field("Description", "knife-edge_XYZ_desc", size='sm'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Scan", "knife-edge_knifeScan", size='lg'),
                                        _field("Units", "knife-edge_knifeScan_unit", size='sm'),
                                    ]
                                ),
                            ],
                            title="Aperture Positioner",
                        ),
                        dbc.AccordionItem(
                            [
                                dbc.Row(id="scan_accordions")#, children=[], className="mt-4"),
                            ],
                            title="Scan",
                        ),
                        dbc.AccordionItem(
                            [
                                _stack(
                                    [
                                        _field("MDA File", "mda_file", size='lg'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Abort", "scanEnd_abort", size='lg'),
                                        # _field("Time Epoch", "scanEnd_time_epoch", size='lg'),
                                        html.Div(
                                            [
                                                _field("Time Epoch", "scanEnd_time_epoch", size='lg'),
                                            ],
                                            style= {'display': 'none'}
                                        ),
                                        _field("Time", "scanEnd_time", size='lg'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Scan Duration", "scanEnd_scanDuration", size='lg'),
                                        _field("Units", "scanEnd_scanDuration_unit", size='sm'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Beam Bad", "scanEnd_source_beamBad", size='lg'),
                                        _field("Ring Current", "scanEnd_source_ringCurrent", size='lg'),
                                        _field("Units", "scanEnd_source_ringCurrent_unit", size='sm'),
                                    ]
                                ),
                            ],
                            title="Scan End",
                        ),
                        ],
                        always_open=True
                    ),
                ],
                style={'width': '100%', 'overflow-x': 'auto'}
        )

def make_scan_accordion(i, scan_data, read_only=True):
    """
    Create a scan accordion with pre-populated values if scan_data is provided.
    Only includes fields that have non-None values.
    
    Args:
        i: Index of the scan
        scan_data: Scan object with field values
        read_only: Whether fields should be read-only (default: True)
    """
    # return dbc.Accordion(
    #     [
    #         dbc.AccordionItem(
    #             [
    #                 _stack(
    #                     [
    #                         _field("Dimensions", {"type": "scan_dim", "index": i}, size='lg', 
    #                                kwargs={'value': scan_data.scan_dim, 'readonly': read_only}),
    #                         _field("No. Points", {"type": "scan_npts", "index": i}, size='lg', 
    #                                kwargs={'value': scan_data.scan_npts, 'readonly': read_only}),
    #                         _field("After", {"type": "scan_after", "index": i}, size='lg', 
    #                                kwargs={'value': scan_data.scan_after, 'readonly': read_only}),
    #                     ]
    #                 ),
    #                 _stack(
    #                     [
    #                         _field("Positioner 1 PV", {"type": "scan_positioner1_PV", "index": i}, size='lg', 
    #                                kwargs={'value': scan_data.scan_positioner1_PV, 'readonly': read_only}),
    #                         _field("Positioner 1 ar", {"type": "scan_positioner1_ar", "index": i}, size='lg', 
    #                                kwargs={'value': scan_data.scan_positioner1_ar, 'readonly': read_only}),
    #                         _field("Positioner 1 mode", {"type": "scan_positioner1_mode", "index": i}, size='lg', 
    #                                kwargs={'value': scan_data.scan_positioner1_mode, 'readonly': read_only}),
    #                         _field("Positioner 1", {"type": "scan_positioner1", "index": i}, size='lg', 
    #                                kwargs={'value': scan_data.scan_positioner1, 'readonly': read_only}),
    #                     ]
    #                 ),
    #                 _stack(
    #                     [
    #                         _field("Positioner 2 PV", {"type": "scan_positioner2_PV", "index": i}, size='lg', 
    #                                kwargs={'value': scan_data.scan_positioner2_PV, 'readonly': read_only}),
    #                         _field("Positioner 2 ar", {"type": "scan_positioner2_ar", "index": i}, size='lg', 
    #                                kwargs={'value': scan_data.scan_positioner2_ar, 'readonly': read_only}),
    #                         _field("Positioner 2 mode", {"type": "scan_positioner2_mode", "index": i}, size='lg', 
    #                                kwargs={'value': scan_data.scan_positioner2_mode, 'readonly': read_only}),
    #                         _field("Positioner 2", {"type": "scan_positioner2", "index": i}, size='lg', 
    #                                kwargs={'value': scan_data.scan_positioner2, 'readonly': read_only}),
    #                     ]
    #                 ),
    #                 _stack(
    #                     [
    #                         _field("Positioner 3 PV", {"type": "scan_positioner3_PV", "index": i}, size='lg', 
    #                                kwargs={'value': scan_data.scan_positioner3_PV, 'readonly': read_only}),
    #                         _field("Positioner 3 ar", {"type": "scan_positioner3_ar", "index": i}, size='lg', 
    #                                kwargs={'value': scan_data.scan_positioner3_ar, 'readonly': read_only}),
    #                         _field("Positioner 3 mode", {"type": "scan_positioner3_mode", "index": i}, size='lg', 
    #                                kwargs={'value': scan_data.scan_positioner3_mode, 'readonly': read_only}),
    #                         _field("Positioner 3", {"type": "scan_positioner3", "index": i}, size='lg', 
    #                                kwargs={'value': scan_data.scan_positioner3, 'readonly': read_only}),
    #                     ]
    #                 ),
    #                 _stack(
    #                     [
    #                         _field("Positioner 4 PV", {"type": "scan_positioner4_PV", "index": i}, size='lg', 
    #                                kwargs={'value': scan_data.scan_positioner4_PV, 'readonly': read_only}),
    #                         _field("Positioner 4 ar", {"type": "scan_positioner4_ar", "index": i}, size='lg', 
    #                                kwargs={'value': scan_data.scan_positioner4_ar, 'readonly': read_only}),
    #                         _field("Positioner 4 mode", {"type": "scan_positioner4_mode", "index": i}, size='lg', 
    #                                kwargs={'value': scan_data.scan_positioner4_mode, 'readonly': read_only}),
    #                         _field("Positioner 4", {"type": "scan_positioner4", "index": i}, size='lg', 
    #                                kwargs={'value': scan_data.scan_positioner4, 'readonly': read_only}),
    #                     ]
    #                 ),
    #                 _stack(
    #                     [
    #                         _field("Detector Trig 1 PV", {"type": "scan_detectorTrig1_PV", "index": i}, size='lg', 
    #                                kwargs={'value': scan_data.scan_detectorTrig1_PV, 'readonly': read_only}),
    #                         _field("Detector Trig 1 VAL", {"type": "scan_detectorTrig1_VAL", "index": i}, size='lg', 
    #                                kwargs={'value': scan_data.scan_detectorTrig1_VAL, 'readonly': read_only}),
    #                     ]
    #                 ),
    #                 _stack(
    #                     [
    #                         _field("Detector Trig 2 PV", {"type": "scan_detectorTrig2_PV", "index": i}, size='lg', 
    #                                kwargs={'value': scan_data.scan_detectorTrig2_PV, 'readonly': read_only}),
    #                         _field("Detector Trig 2 VAL", {"type": "scan_detectorTrig2_VAL", "index": i}, size='lg', 
    #                                kwargs={'value': scan_data.scan_detectorTrig2_VAL, 'readonly': read_only}),
    #                     ]
    #                 ),
    #                 _stack(
    #                     [
    #                         _field("Detector Trig 3 PV", {"type": "scan_detectorTrig3_PV", "index": i}, size='lg', 
    #                                kwargs={'value': scan_data.scan_detectorTrig3_PV, 'readonly': read_only}),
    #                         _field("Detector Trig 3 VAL", {"type": "scan_detectorTrig3_VAL", "index": i}, size='lg', 
    #                                kwargs={'value': scan_data.scan_detectorTrig3_VAL, 'readonly': read_only}),
    #                     ]
    #                 ),
    #                 _stack(
    #                     [
    #                         _field("Detector Trig 4 PV", {"type": "scan_detectorTrig4_PV", "index": i}, size='lg', 
    #                                kwargs={'value': scan_data.scan_detectorTrig4_PV, 'readonly': read_only}),
    #                         _field("Detector Trig 4 VAL", {"type": "scan_detectorTrig4_VAL", "index": i}, size='lg', 
    #                                kwargs={'value': scan_data.scan_detectorTrig4_VAL, 'readonly': read_only}),
    #                     ]
    #                 ),
    #                 _stack(
    #                     [
    #                         _field("Completed", {"type": "scan_cpt", "index": i}, size='lg', 
    #                                kwargs={'value': scan_data.scan_cpt, 'readonly': read_only}),
    #                     ]
    #                 ),
    #             ],
    #             title=f"Scan {i + 1}",
    #         ),
    #     ],
    #     # style={
    #     #     "width": 400,
    #     #     "display": "inline-block",
    #     # },
    #     # className="m-1",
    #     id={"type": "scan_accordion", "index": i},
    # )
    # Helper function to check if a value should be displayed
    def should_display(value):
        return value is not None and str(value).strip() != ''
    
    # Build stacks dynamically based on which fields have values
    stacks = []
    
    # General scan info
    general_fields = []
    if should_display(scan_data.scan_dim):
        general_fields.append(_field("Dimensions", {"type": "scan_dim", "index": i}, size='lg', 
                                   kwargs={'value': scan_data.scan_dim, 'readonly': read_only}))
    if should_display(scan_data.scan_npts):
        general_fields.append(_field("No. Points", {"type": "scan_npts", "index": i}, size='lg', 
                                   kwargs={'value': scan_data.scan_npts, 'readonly': read_only}))
    if should_display(scan_data.scan_after):
        general_fields.append(_field("After", {"type": "scan_after", "index": i}, size='lg', 
                                   kwargs={'value': scan_data.scan_after, 'readonly': read_only}))
    if general_fields:
        stacks.append(_stack(general_fields))
    
    # Positioner 1
    pos1_fields = []
    if should_display(scan_data.scan_positioner1_PV):
        pos1_fields.append(_field("Positioner 1 PV", {"type": "scan_positioner1_PV", "index": i}, size='lg', 
                                kwargs={'value': scan_data.scan_positioner1_PV, 'readonly': read_only}))
    if should_display(scan_data.scan_positioner1_ar):
        pos1_fields.append(_field("Positioner 1 ar", {"type": "scan_positioner1_ar", "index": i}, size='lg', 
                                kwargs={'value': scan_data.scan_positioner1_ar, 'readonly': read_only}))
    if should_display(scan_data.scan_positioner1_mode):
        pos1_fields.append(_field("Positioner 1 mode", {"type": "scan_positioner1_mode", "index": i}, size='lg', 
                                kwargs={'value': scan_data.scan_positioner1_mode, 'readonly': read_only}))
    if should_display(scan_data.scan_positioner1):
        pos1_fields.append(_field("Positioner 1", {"type": "scan_positioner1", "index": i}, size='lg', 
                                kwargs={'value': scan_data.scan_positioner1, 'readonly': read_only}))
    if pos1_fields:
        stacks.append(_stack(pos1_fields))
    
    # Positioner 2
    pos2_fields = []
    if should_display(scan_data.scan_positioner2_PV):
        pos2_fields.append(_field("Positioner 2 PV", {"type": "scan_positioner2_PV", "index": i}, size='lg', 
                                kwargs={'value': scan_data.scan_positioner2_PV, 'readonly': read_only}))
    if should_display(scan_data.scan_positioner2_ar):
        pos2_fields.append(_field("Positioner 2 ar", {"type": "scan_positioner2_ar", "index": i}, size='lg', 
                                kwargs={'value': scan_data.scan_positioner2_ar, 'readonly': read_only}))
    if should_display(scan_data.scan_positioner2_mode):
        pos2_fields.append(_field("Positioner 2 mode", {"type": "scan_positioner2_mode", "index": i}, size='lg', 
                                kwargs={'value': scan_data.scan_positioner2_mode, 'readonly': read_only}))
    if should_display(scan_data.scan_positioner2):
        pos2_fields.append(_field("Positioner 2", {"type": "scan_positioner2", "index": i}, size='lg', 
                                kwargs={'value': scan_data.scan_positioner2, 'readonly': read_only}))
    if pos2_fields:
        stacks.append(_stack(pos2_fields))
    
    # Positioner 3
    pos3_fields = []
    if should_display(scan_data.scan_positioner3_PV):
        pos3_fields.append(_field("Positioner 3 PV", {"type": "scan_positioner3_PV", "index": i}, size='lg', 
                                kwargs={'value': scan_data.scan_positioner3_PV, 'readonly': read_only}))
    if should_display(scan_data.scan_positioner3_ar):
        pos3_fields.append(_field("Positioner 3 ar", {"type": "scan_positioner3_ar", "index": i}, size='lg', 
                                kwargs={'value': scan_data.scan_positioner3_ar, 'readonly': read_only}))
    if should_display(scan_data.scan_positioner3_mode):
        pos3_fields.append(_field("Positioner 3 mode", {"type": "scan_positioner3_mode", "index": i}, size='lg', 
                                kwargs={'value': scan_data.scan_positioner3_mode, 'readonly': read_only}))
    if should_display(scan_data.scan_positioner3):
        pos3_fields.append(_field("Positioner 3", {"type": "scan_positioner3", "index": i}, size='lg', 
                                kwargs={'value': scan_data.scan_positioner3, 'readonly': read_only}))
    if pos3_fields:
        stacks.append(_stack(pos3_fields))
    
    # Positioner 4
    pos4_fields = []
    if should_display(scan_data.scan_positioner4_PV):
        pos4_fields.append(_field("Positioner 4 PV", {"type": "scan_positioner4_PV", "index": i}, size='lg', 
                                kwargs={'value': scan_data.scan_positioner4_PV, 'readonly': read_only}))
    if should_display(scan_data.scan_positioner4_ar):
        pos4_fields.append(_field("Positioner 4 ar", {"type": "scan_positioner4_ar", "index": i}, size='lg', 
                                kwargs={'value': scan_data.scan_positioner4_ar, 'readonly': read_only}))
    if should_display(scan_data.scan_positioner4_mode):
        pos4_fields.append(_field("Positioner 4 mode", {"type": "scan_positioner4_mode", "index": i}, size='lg', 
                                kwargs={'value': scan_data.scan_positioner4_mode, 'readonly': read_only}))
    if should_display(scan_data.scan_positioner4):
        pos4_fields.append(_field("Positioner 4", {"type": "scan_positioner4", "index": i}, size='lg', 
                                kwargs={'value': scan_data.scan_positioner4, 'readonly': read_only}))
    if pos4_fields:
        stacks.append(_stack(pos4_fields))
    
    # Detector Trigger 1
    det1_fields = []
    if should_display(scan_data.scan_detectorTrig1_PV):
        det1_fields.append(_field("Detector Trig 1 PV", {"type": "scan_detectorTrig1_PV", "index": i}, size='lg', 
                                kwargs={'value': scan_data.scan_detectorTrig1_PV, 'readonly': read_only}))
    if should_display(scan_data.scan_detectorTrig1_VAL):
        det1_fields.append(_field("Detector Trig 1 VAL", {"type": "scan_detectorTrig1_VAL", "index": i}, size='lg', 
                                kwargs={'value': scan_data.scan_detectorTrig1_VAL, 'readonly': read_only}))
    if det1_fields:
        stacks.append(_stack(det1_fields))
    
    # Detector Trigger 2
    det2_fields = []
    if should_display(scan_data.scan_detectorTrig2_PV):
        det2_fields.append(_field("Detector Trig 2 PV", {"type": "scan_detectorTrig2_PV", "index": i}, size='lg', 
                                kwargs={'value': scan_data.scan_detectorTrig2_PV, 'readonly': read_only}))
    if should_display(scan_data.scan_detectorTrig2_VAL):
        det2_fields.append(_field("Detector Trig 2 VAL", {"type": "scan_detectorTrig2_VAL", "index": i}, size='lg', 
                                kwargs={'value': scan_data.scan_detectorTrig2_VAL, 'readonly': read_only}))
    if det2_fields:
        stacks.append(_stack(det2_fields))
    
    # Detector Trigger 3
    det3_fields = []
    if should_display(scan_data.scan_detectorTrig3_PV):
        det3_fields.append(_field("Detector Trig 3 PV", {"type": "scan_detectorTrig3_PV", "index": i}, size='lg', 
                                kwargs={'value': scan_data.scan_detectorTrig3_PV, 'readonly': read_only}))
    if should_display(scan_data.scan_detectorTrig3_VAL):
        det3_fields.append(_field("Detector Trig 3 VAL", {"type": "scan_detectorTrig3_VAL", "index": i}, size='lg', 
                                kwargs={'value': scan_data.scan_detectorTrig3_VAL, 'readonly': read_only}))
    if det3_fields:
        stacks.append(_stack(det3_fields))
    
    # Detector Trigger 4
    det4_fields = []
    if should_display(scan_data.scan_detectorTrig4_PV):
        det4_fields.append(_field("Detector Trig 4 PV", {"type": "scan_detectorTrig4_PV", "index": i}, size='lg', 
                                kwargs={'value': scan_data.scan_detectorTrig4_PV, 'readonly': read_only}))
    if should_display(scan_data.scan_detectorTrig4_VAL):
        det4_fields.append(_field("Detector Trig 4 VAL", {"type": "scan_detectorTrig4_VAL", "index": i}, size='lg', 
                                kwargs={'value': scan_data.scan_detectorTrig4_VAL, 'readonly': read_only}))
    if det4_fields:
        stacks.append(_stack(det4_fields))
    
    # Completed
    if should_display(scan_data.scan_cpt):
        stacks.append(_stack([
            _field("Completed", {"type": "scan_cpt", "index": i}, size='lg', 
                   kwargs={'value': scan_data.scan_cpt, 'readonly': read_only})
        ]))
    
    # Only create accordion if there are fields to display
    if stacks:
        return dbc.Accordion(
            [
                dbc.AccordionItem(
                    stacks,
                    title=f"Scan {i + 1}",
                ),
            ],
            id={"type": "scan_accordion", "index": i},
        )
    else:
        # Return empty div if no fields to display
        return html.Div()

def set_metadata_form_props(metadata, scans=None, read_only=True):
    set_props("scanNumber", {'value':metadata.scanNumber, 'readonly':read_only})

    set_props("time_epoch", {'value':metadata.time_epoch, 'readonly':read_only})
    # Format datetime for display
    time_value = metadata.time
    if isinstance(time_value, datetime):
        time_value = time_value.strftime('%Y-%m-%d, %H:%M:%S')
    set_props("time", {'value':time_value, 'readonly':read_only})
    set_props("user_name", {'value':metadata.user_name, 'readonly':read_only})
    set_props("source_beamBad", {'value':metadata.source_beamBad, 'readonly':read_only})
    set_props("source_CCDshutter", {'value':metadata.source_CCDshutter, 'readonly':read_only})
    set_props("source_monoTransStatus", {'value':metadata.source_monoTransStatus, 'readonly':read_only})
    set_props("source_energy_unit", {'value':metadata.source_energy_unit, 'readonly':read_only})
    set_props("source_energy", {'value':metadata.source_energy, 'readonly':read_only})
    set_props("source_IDgap_unit", {'value':metadata.source_IDgap_unit, 'readonly':read_only})
    set_props("source_IDgap", {'value':metadata.source_IDgap, 'readonly':read_only})
    set_props("source_IDtaper_unit", {'value':metadata.source_IDgap_unit, 'readonly':read_only})
    set_props("source_IDtaper", {'value':metadata.source_IDgap, 'readonly':read_only})
    set_props("source_ringCurrent_unit", {'value':metadata.source_ringCurrent_unit, 'readonly':read_only})
    set_props("source_ringCurrent", {'value':metadata.source_ringCurrent, 'readonly':read_only})
    set_props("sample_XYZ_unit", {'value':metadata.sample_XYZ_unit, 'readonly':read_only})
    set_props("sample_XYZ_desc", {'value':metadata.sample_XYZ_desc, 'readonly':read_only})
    set_props("sample_XYZ", {'value':metadata.sample_XYZ, 'readonly':read_only})
    # set_props("sample_X", {'value':metadata.sample_X, 'readonly':read_only})
    # set_props("sample_Y", {'value':metadata.sample_Y, 'readonly':read_only})
    # set_props("sample_Z", {'value':metadata.sample_Z, 'readonly':read_only})
    set_props("knife-edge_XYZ_unit", {'value':metadata.knifeEdge_XYZ_unit, 'readonly':read_only})
    set_props("knife-edge_XYZ_desc", {'value':metadata.knifeEdge_XYZ_desc, 'readonly':read_only})
    set_props("knife-edge_XYZ", {'value':metadata.knifeEdge_XYZ, 'readonly':read_only})
    # set_props("knife-edge_X", {'value':metadata.knifeEdge_X, 'readonly':read_only})
    # set_props("knife-edge_Y", {'value':metadata.knifeEdge_Y, 'readonly':read_only})
    # set_props("knife-edge_Z", {'value':metadata.knifeEdge_Z, 'readonly':read_only})
    set_props("knife-edge_knifeScan_unit", {'value':metadata.knifeEdge_knifeScan_unit, 'readonly':read_only})
    set_props("knife-edge_knifeScan", {'value':metadata.knifeEdge_knifeScan, 'readonly':read_only})
    # set_props("scan_dim", {'value':metadata.scan_dim, 'readonly':read_only})
    # set_props("scan_npts", {'value':metadata.scan_npts, 'readonly':read_only})
    # set_props("scan_after", {'value':metadata.scan_after, 'readonly':read_only})
    # set_props("scan_positionerSettle_unit", {'value':metadata.scan_positionerSettle_unit, 'readonly':read_only})
    # set_props("scan_positionerSettle", {'value':metadata.scan_positionerSettle, 'readonly':read_only})
    # set_props("scan_detectorSettle_unit", {'value':metadata.scan_detectorSettle_unit, 'readonly':read_only})
    # set_props("scan_detectorSettle", {'value':metadata.scan_detectorSettle, 'readonly':read_only})
    # set_props("scan_beforePV_VAL", {'value':metadata.scan_beforePV_VAL, 'readonly':read_only})
    # set_props("scan_beforePV_wait", {'value':metadata.scan_beforePV_wait, 'readonly':read_only})
    # set_props("scan_beforePV", {'value':metadata.scan_beforePV, 'readonly':read_only})
    # set_props("scan_afterPV_VAL", {'value':metadata.scan_beforePV_VAL, 'readonly':read_only})
    # set_props("scan_afterPV_wait", {'value':metadata.scan_beforePV_wait, 'readonly':read_only})
    # set_props("scan_afterPV", {'value':metadata.scan_beforePV, 'readonly':read_only})
    # set_props("scan_positioner_PV", {'value':metadata.scan_positioner_PV, 'readonly':read_only})
    # set_props("scan_positioner_ar", {'value':metadata.scan_positioner_ar, 'readonly':read_only})
    # set_props("scan_positioner_mode", {'value':metadata.scan_positioner_mode, 'readonly':read_only})
    # set_props("scan_positioner_1", {'value':metadata.scan_positioner_1, 'readonly':read_only})
    # set_props("scan_positioner_2", {'value':metadata.scan_positioner_2, 'readonly':read_only})
    # set_props("scan_positioner_3", {'value':metadata.scan_positioner_3, 'readonly':read_only})
    # set_props("scan_detectorTrig_PV", {'value':metadata.scan_detectorTrig_PV, 'readonly':read_only})
    # set_props("scan_detectorTrig_VAL", {'value':metadata.scan_detectorTrig_VAL, 'readonly':read_only})
    # set_props("scan_detectors", {'value':metadata.scan_detectors, 'readonly':read_only})
    set_props("mda_file", {'value':metadata.mda_file, 'readonly':read_only})
    set_props("scanEnd_abort", {'value':metadata.scanEnd_abort, 'readonly':read_only})
    set_props("scanEnd_time_epoch", {'value':metadata.scanEnd_time_epoch, 'readonly':read_only})
    set_props("scanEnd_time", {'value':metadata.scanEnd_time, 'readonly':read_only})
    set_props("scanEnd_scanDuration_unit", {'value':metadata.scanEnd_scanDuration_unit, 'readonly':read_only})
    set_props("scanEnd_scanDuration", {'value':metadata.scanEnd_scanDuration, 'readonly':read_only})
    # set_props("scanEnd_cpt", {'value':metadata.scanEnd_cpt, 'readonly':read_only})
    set_props("scanEnd_source_ringCurrent_unit", {'value':metadata.scanEnd_source_ringCurrent_unit, 'readonly':read_only})
    set_props("scanEnd_source_ringCurrent", {'value':metadata.scanEnd_source_ringCurrent, 'readonly':read_only})

    # for i,scan in enumerate(scans):
    #     set_props({"type": "scan_dim", "index": i}, {'value':scan.scan_dim, 'readonly':read_only})
    #     set_props({"type": "scan_npts", "index": i}, {'value':scan.scan_npts, 'readonly':read_only})
    #     set_props({"type": "scan_after", "index": i}, {'value':scan.scan_after, 'readonly':read_only})
    #     set_props({"type": "scan_positioner1_PV", "index": i}, {'value':scan.scan_positioner1_PV, 'readonly':read_only})
    #     set_props({"type": "scan_positioner1_ar", "index": i}, {'value':scan.scan_positioner1_ar, 'readonly':read_only})
    #     set_props({"type": "scan_positioner1_mode", "index": i}, {'value':scan.scan_positioner1_mode, 'readonly':read_only})
    #     set_props({"type": "scan_positioner1", "index": i}, {'value':scan.scan_positioner1, 'readonly':read_only})
    #     set_props({"type": "scan_positioner2_PV", "index": i}, {'value':scan.scan_positioner2_PV, 'readonly':read_only})
    #     set_props({"type": "scan_positioner2_ar", "index": i}, {'value':scan.scan_positioner2_ar, 'readonly':read_only})
    #     set_props({"type": "scan_positioner2_mode", "index": i}, {'value':scan.scan_positioner2_mode, 'readonly':read_only})
    #     set_props({"type": "scan_positioner2", "index": i}, {'value':scan.scan_positioner2, 'readonly':read_only})
    #     set_props({"type": "scan_positioner3_PV", "index": i}, {'value':scan.scan_positioner3_PV, 'readonly':read_only})
    #     set_props({"type": "scan_positioner3_ar", "index": i}, {'value':scan.scan_positioner3_ar, 'readonly':read_only})
    #     set_props({"type": "scan_positioner3_mode", "index": i}, {'value':scan.scan_positioner3_mode, 'readonly':read_only})
    #     set_props({"type": "scan_positioner3", "index": i}, {'value':scan.scan_positioner3, 'readonly':read_only})
    #     set_props({"type": "scan_positioner4_PV", "index": i}, {'value':scan.scan_positioner4_PV, 'readonly':read_only})
    #     set_props({"type": "scan_positioner4_ar", "index": i}, {'value':scan.scan_positioner4_ar, 'readonly':read_only})
    #     set_props({"type": "scan_positioner4_mode", "index": i}, {'value':scan.scan_positioner4_mode, 'readonly':read_only})
    #     set_props({"type": "scan_positioner4", "index": i}, {'value':scan.scan_positioner4, 'readonly':read_only})
    #     set_props({"type": "scan_detectorTrig1_PV", "index": i}, {'value':scan.scan_detectorTrig1_PV, 'readonly':read_only})
    #     set_props({"type": "scan_detectorTrig1_VAL", "index": i}, {'value':scan.scan_detectorTrig1_VAL, 'readonly':read_only})
    #     set_props({"type": "scan_detectorTrig2_PV", "index": i}, {'value':scan.scan_detectorTrig2_PV, 'readonly':read_only})
    #     set_props({"type": "scan_detectorTrig2_VAL", "index": i}, {'value':scan.scan_detectorTrig2_VAL, 'readonly':read_only})
    #     set_props({"type": "scan_detectorTrig3_PV", "index": i}, {'value':scan.scan_detectorTrig3_PV, 'readonly':read_only})
    #     set_props({"type": "scan_detectorTrig3_VAL", "index": i}, {'value':scan.scan_detectorTrig3_VAL, 'readonly':read_only})
    #     set_props({"type": "scan_detectorTrig4_PV", "index": i}, {'value':scan.scan_detectorTrig4_PV, 'readonly':read_only})
    #     set_props({"type": "scan_detectorTrig4_VAL", "index": i}, {'value':scan.scan_detectorTrig4_VAL, 'readonly':read_only})
    #     set_props({"type": "scan_cpt", "index": i}, {'value':scan.scan_cpt, 'readonly':read_only})

    # set_props("dataset", {'value':metadata.dataset_id, 'readonly':read_only})
    
    # set_props("dataset_path", {'value':metadata.dataset_path, 'readonly':read_only})
    # set_props("dataset_filename", {'value':metadata.dataset_filename, 'readonly':read_only})
    # set_props("dataset_type", {'value':metadata.dataset_type, 'readonly':read_only})
    # set_props("dataset_group", {'value':metadata.dataset_group, 'readonly':read_only})
    # set_props("start_time", {'value':metadata.start_time, 'readonly':read_only})
    # set_props("end_time", {'value':metadata.end_time, 'readonly':read_only})
    # set_props("start_image_num", {'value':metadata.start_image_num, 'readonly':read_only})
    # set_props("end_image_num", {'value':metadata.end_image_num, 'readonly':read_only})
    # set_props("total_points", {'value':metadata.total_points, 'readonly':read_only})
    # set_props("maskX_wireBaseX", {'value':metadata.maskX_wireBaseX, 'readonly':read_only})
    # set_props("maskY_wireBaseY", {'value':metadata.maskY_wireBaseY, 'readonly':read_only})
    # set_props("sr1_motor", {'value':metadata.sr1_motor, 'readonly':read_only})
    # set_props("motion", {'value':metadata.motion, 'readonly':read_only})
    # set_props("sr1_init", {'value':metadata.sr1_init, 'readonly':read_only})
    # set_props("sr1_final", {'value':metadata.sr1_final, 'readonly':read_only})
    # set_props("sr1_step", {'value':metadata.sr1_step, 'readonly':read_only})
    # set_props("sr2_motor", {'value':metadata.sr2_motor, 'readonly':read_only})
    # set_props("sr2_init", {'value':metadata.sr2_init, 'readonly':read_only})
    # set_props("sr2_final", {'value':metadata.sr2_final, 'readonly':read_only})
    # set_props("sr2_step", {'value':metadata.sr2_step, 'readonly':read_only})
    # set_props("sr3_motor", {'value':metadata.sr3_motor, 'readonly':read_only})
    # set_props("sr3_init", {'value':metadata.sr3_init, 'readonly':read_only})
    # set_props("sr3_final", {'value':metadata.sr3_final, 'readonly':read_only})
    # set_props("sr3_step", {'value':metadata.sr3_step, 'readonly':read_only})
    # set_props("shift_parameter", {'value':metadata.shift_parameter, 'readonly':read_only})
    # set_props("exp_time", {'value':metadata.exp_time, 'readonly':read_only})
    # set_props("mda", {'value':metadata.mda, 'readonly':read_only})
    # set_props("sampleXini", {'value':metadata.sampleXini, 'readonly':read_only})
    # set_props("sampleYini", {'value':metadata.sampleYini, 'readonly':read_only})
    # set_props("sampleZini", {'value':metadata.sampleZini, 'readonly':read_only})
    # set_props("comment", {'value':metadata.comment, 'readonly':read_only})

def set_scaninfo_form_props(metadata, scans, catalog, read_only=True):
    set_props('ScanID_print', {'children':[metadata.scanNumber]})
    set_props('User_print', {'children':[metadata.user_name]})
    # Format datetime for display
    time_value = metadata.time
    if isinstance(time_value, datetime):
        time_value = time_value.strftime('%Y-%m-%d, %H:%M:%S')
    set_props('Date_print', {'children':[time_value]})
    set_props('ScanType_print', {'children':[f"{len([i for i,scan in enumerate(scans)])}D"]})
    set_props('Technique_print', {'children':[catalog.aperture.title()]}) #"depth"
    set_props('Sample_print', {'children':[catalog.sample_name]}) #"Si"
    set_props('Comment_print', {'children':["submit indexing"]})
# def set_scaninfo_form_props(metadata, scans, read_only=True):
#     set_props('ScanID_print', {'children':["Scan ID: ", metadata.scanNumber]})
#     set_props('User_print', {'children':[html.Strong("User: "), metadata.user_name]})
#     set_props('Date_print', {'children':[html.Strong("Date: "), metadata.time]})
#     set_props('ScanType_print', {'children':[html.Strong("Scan Type: "), f"{len([i for i,scan in enumerate(scans)])}D"]})
#     set_props('Technique_print', {'children':[html.Strong("Technique: "), "depth"]})
#     set_props('Sample_print', {'children':[html.Strong("Sample: "), "Si"]})
#     set_props('Comment_print', {'children':["submit indexing"]})
