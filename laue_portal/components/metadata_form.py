import dash_bootstrap_components as dbc
from dash import html, set_props
from laue_portal.components.form_base import _stack, _field, _ckbx


metadata_form = dbc.Row(
                [
                    dbc.Accordion(
                        [
                        dbc.AccordionItem(
                            [
                                _stack(
                                    [
                                        _field("Scan Number", "scanNumber", size='lg'),
                                        # _field("Time Epoch", "time_epoch", size='lg'),
                                        html.Div(
                                            [
                                                _field("Time Epoch", "time_epoch", size='lg'),
                                            ],
                                            style= {'display': 'none'}
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
                                html.Div(id="scan_accordion", children=[])#, className="mt-4"),
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

def make_scan_accordion(i):
    i += 1
    return dbc.Accordion(
        [
            dbc.AccordionItem(
                [
                    _stack(
                        [
                            _field("Dimensions", f"scan_dim_{i}", size='lg'),
                            _field("No. Points", f"scan_npts_{i}", size='lg'),
                            _field("After", f"scan_after_{i}", size='lg'),
                        ]
                    ),
                    _stack(
                        [
                            _field("Positioner 1 PV", f"scan_positioner1_PV_{i}", size='lg'),
                            _field("Positioner 1 ar", f"scan_positioner1_ar_{i}", size='lg'),
                            _field("Positioner 1 mode", f"scan_positioner1_mode_{i}", size='lg'),
                            _field("Positioner 1", f"scan_positioner1_{i}", size='lg'),
                        ]
                    ),
                    _stack(
                        [
                            _field("Positioner 2 PV", f"scan_positioner2_PV_{i}", size='lg'),
                            _field("Positioner 2 ar", f"scan_positioner2_ar_{i}", size='lg'),
                            _field("Positioner 2 mode", f"scan_positioner2_mode_{i}", size='lg'),
                            _field("Positioner 2", f"scan_positioner2_{i}", size='lg'),
                        ]
                    ),
                    _stack(
                        [
                            _field("Positioner 3 PV", f"scan_positioner3_PV_{i}", size='lg'),
                            _field("Positioner 3 ar", f"scan_positioner3_ar_{i}", size='lg'),
                            _field("Positioner 3 mode", f"scan_positioner3_mode_{i}", size='lg'),
                            _field("Positioner 3", f"scan_positioner3_{i}", size='lg'),
                        ]
                    ),
                    _stack(
                        [
                            _field("Positioner 4 PV", f"scan_positioner4_PV_{i}", size='lg'),
                            _field("Positioner 4 ar", f"scan_positioner4_ar_{i}", size='lg'),
                            _field("Positioner 4 mode", f"scan_positioner4_mode_{i}", size='lg'),
                            _field("Positioner 4", f"scan_positioner4_{i}", size='lg'),
                        ]
                    ),
                    _stack(
                        [
                            _field("Detector Trig 1 PV", f"scan_detectorTrig1_PV_{i}", size='lg'),
                            _field("Detector Trig 1 VAL", f"scan_detectorTrig1_VAL_{i}", size='lg'),
                        ]
                    ),
                    _stack(
                        [
                            _field("Detector Trig 2 PV", f"scan_detectorTrig2_PV_{i}", size='lg'),
                            _field("Detector Trig 2 VAL", f"scan_detectorTrig2_VAL_{i}", size='lg'),
                        ]
                    ),
                    _stack(
                        [
                            _field("Detector Trig 3 PV", f"scan_detectorTrig3_PV_{i}", size='lg'),
                            _field("Detector Trig 3 VAL", f"scan_detectorTrig3_VAL_{i}", size='lg'),
                        ]
                    ),
                    _stack(
                        [
                            _field("Detector Trig 4 PV", f"scan_detectorTrig4_PV_{i}", size='lg'),
                            _field("Detector Trig 4 VAL", f"scan_detectorTrig4_VAL_{i}", size='lg'),
                        ]
                    ),
                    _stack(
                        [
                            _field("Completed", f"scan_cpt_{i}", size='lg'),
                        ]
                    ),
                ],
                title=f"Scan {i}",
            ),
        ],
        # style={
        #     "width": 400,
        #     "display": "inline-block",
        # },
        # className="m-1",
        id=f"scan_card_{i}",
    )

def set_metadata_form_props(metadata, scans, read_only=True):
    set_props("scanNumber", {'value':metadata.scanNumber, 'readonly':read_only})

    set_props("time_epoch", {'value':metadata.time_epoch, 'readonly':read_only})
    set_props("time", {'value':metadata.time, 'readonly':read_only})
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

    for i,scan in enumerate(scans):
        i += 1
        set_props(f"scan_dim_{i}", {'value':scan.scan_dim, 'readonly':read_only})
        set_props(f"scan_npts_{i}", {'value':scan.scan_npts, 'readonly':read_only})
        set_props(f"scan_after_{i}", {'value':scan.scan_after, 'readonly':read_only})
        set_props(f"scan_positioner1_PV_{i}", {'value':scan.scan_positioner1_PV, 'readonly':read_only})
        set_props(f"scan_positioner1_ar_{i}", {'value':scan.scan_positioner1_ar, 'readonly':read_only})
        set_props(f"scan_positioner1_mode_{i}", {'value':scan.scan_positioner1_mode, 'readonly':read_only})
        set_props(f"scan_positioner1_{i}", {'value':scan.scan_positioner1, 'readonly':read_only})
        set_props(f"scan_positioner2_PV_{i}", {'value':scan.scan_positioner2_PV, 'readonly':read_only})
        set_props(f"scan_positioner2_ar_{i}", {'value':scan.scan_positioner2_ar, 'readonly':read_only})
        set_props(f"scan_positioner2_mode_{i}", {'value':scan.scan_positioner2_mode, 'readonly':read_only})
        set_props(f"scan_positioner2_{i}", {'value':scan.scan_positioner2, 'readonly':read_only})
        set_props(f"scan_positioner3_PV_{i}", {'value':scan.scan_positioner3_PV, 'readonly':read_only})
        set_props(f"scan_positioner3_ar_{i}", {'value':scan.scan_positioner3_ar, 'readonly':read_only})
        set_props(f"scan_positioner3_mode_{i}", {'value':scan.scan_positioner3_mode, 'readonly':read_only})
        set_props(f"scan_positioner3_{i}", {'value':scan.scan_positioner3, 'readonly':read_only})
        set_props(f"scan_positioner4_PV_{i}", {'value':scan.scan_positioner4_PV, 'readonly':read_only})
        set_props(f"scan_positioner4_ar_{i}", {'value':scan.scan_positioner4_ar, 'readonly':read_only})
        set_props(f"scan_positioner4_mode_{i}", {'value':scan.scan_positioner4_mode, 'readonly':read_only})
        set_props(f"scan_positioner4_{i}", {'value':scan.scan_positioner4, 'readonly':read_only})
        set_props(f"scan_detectorTrig1_PV_{i}", {'value':scan.scan_detectorTrig1_PV, 'readonly':read_only})
        set_props(f"scan_detectorTrig1_VAL_{i}", {'value':scan.scan_detectorTrig1_VAL, 'readonly':read_only})
        set_props(f"scan_detectorTrig2_PV_{i}", {'value':scan.scan_detectorTrig2_PV, 'readonly':read_only})
        set_props(f"scan_detectorTrig2_VAL_{i}", {'value':scan.scan_detectorTrig2_VAL, 'readonly':read_only})
        set_props(f"scan_detectorTrig3_PV_{i}", {'value':scan.scan_detectorTrig3_PV, 'readonly':read_only})
        set_props(f"scan_detectorTrig3_VAL_{i}", {'value':scan.scan_detectorTrig3_VAL, 'readonly':read_only})
        set_props(f"scan_detectorTrig4_PV_{i}", {'value':scan.scan_detectorTrig4_PV, 'readonly':read_only})
        set_props(f"scan_detectorTrig4_VAL_{i}", {'value':scan.scan_detectorTrig4_VAL, 'readonly':read_only})
        set_props(f"scan_cpt_{i}", {'value':scan.scan_cpt, 'readonly':read_only})

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