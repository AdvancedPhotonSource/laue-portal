import dash
from dash import html, Input, Output, State, set_props
import dash_bootstrap_components as dbc

# TODO: Make navbar links dynamic
"""
Something like this...
@app.callback(
    [Output(f"link-{i}", "active") for i in range(1, 5)],
    [Input('url', 'pathname')]
)
def update_active_links(pathname):
    return [pathname == link.href for link in navbar.children]

"""
navbar = dbc.NavbarSimple(
    children=[
        #dbc.NavItem(dbc.NavLink("Scans", href="/")),
        dbc.NavItem(dbc.NavLink("New Scan", href="/create-scan")),
        dbc.NavItem(dbc.NavLink("Reconstructions", href="/reconstructions")),
        dbc.NavItem(dbc.NavLink("New Reconstruction", href="/create-reconstruction")),
        dbc.NavItem(dbc.NavLink("Recon Run Monitor", href="/runs")),
        dbc.NavItem(dbc.NavLink("Indexations", href="/indexedpeaks")),
        dbc.NavItem(dbc.NavLink("New Indexation", href="/create-indexedpeaks")),
        dbc.NavItem(dbc.NavLink("Index Run Monitor", href="/index-runs")),
        dbc.NavItem(dbc.NavLink("Review", href="/review")),
    ],
    brand="Coded Aperture Laue",
    brand_href="/",
    color="primary",
    className="navbar-lg",
    dark=True,
    style={"max-height": "50px"},
)

def _stack(objects):
    return dbc.Stack(
        objects, 
        direction="horizontal",
        gap=3
    )

def _field(label, field_id, size='sm', kwargs={}):
    if size == 'sm':
        width='200px'
    elif size == 'md':
        width='350px'
    elif size == 'lg':
        width='500px'
    elif size == 'hg':
        width='9999px'

    return dbc.InputGroup(
        [
            dbc.InputGroupText(label),
            dbc.Input(id=field_id, **kwargs),
        ],
        style={'width': width},
        className="mb-3",
    )

def _ckbx(label, field_id, size='sm'):
    if size == 'sm':
        width='200px'
    elif size == 'md':
        width='350px'
    elif size == 'lg':
        width='500px'

    return dbc.Checkbox(id=field_id, 
                        label=label,
                        class_name="mb-3",
                        style={'width': width})


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
                                        _field("Time", "scanEnd_time", size='lg'),


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
                                html.Div(id="scan_cards", children=[])#, className="mt-4"),
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

def make_scan_card(i):
    i += 1
    return dbc.Card(
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


recon_form = dbc.Row(
                [
                    dbc.Accordion(
                        [
                        dbc.AccordionItem(
                            [
                                _stack(
                                    [
                                        _field("Dataset", "dataset", size='lg'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Frame Start", 'frame_start', size='sm'),
                                        _field("Frame End", 'frame_end', size='sm'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("X Start", 'x_start', size='sm'),
                                        _field("X End", 'x_end', size='sm'),
                                        _field("Y Start", 'y_start', size='sm'),
                                        _field("Y End", 'y_end', size='sm'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Depth Start", 'depth_start', size='sm'),
                                        _field("Depth End", 'depth_end', size='sm'),
                                        _field("Depth Step", 'depth_step', size='sm'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Recon Name", 'recon_name', size='lg'),
                                    ]
                                ),
                            ],
                            title="Recon Parameters",
                        ),
                        dbc.AccordionItem(
                            [
                                _stack(
                                    [
                                        _field("File Path", 'file_path', size='lg'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field('File Output', 'file_output', size='lg'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _ckbx("Data Stacked", 'data_stacked', size='sm'),
                                        _field("H5_key", 'h5_key', size='sm'),
                                        _field("File Offset", 'file_offset', size='sm'),
                                    ]
                                )
                            ],
                            title="File Parameters",
                        ),
                        dbc.AccordionItem(
                            [
                                _stack(
                                    [
                                        _field("CenX", 'cenx', size='sm'),
                                        _field("CenY", 'ceny', size='sm'),
                                        _field("CenZ", 'cenz', size='sm'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("AngleX", 'anglex', size='sm'),
                                        _field("AngleY", 'angley', size='sm'),
                                        _field("AngleZ", 'anglez', size='sm'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Shift", 'shift', size='sm'), 
                                    ]
                                ),
                            ],
                            title="Calibration",
                        ),
                        dbc.AccordionItem(
                            [
                                _stack(
                                    [
                                        _field("Mask Path", 'mask_path', size='lg'),
                                        _ckbx("Reversed", 'reversed', size='sm'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Bitsize 0", 'bitsize_0', size='sm'),
                                        _field("Bitsize 1", 'bitsize_1', size='sm'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Thickness", 'thickness', size='sm'),
                                        _field("Resolution", 'resolution', size='sm'),
                                        _field("Smoothness", 'smoothness', size='sm'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Widening", 'widening', size='sm'),
                                        _field("Pad", 'pad', size='sm'),
                                        _field("Stretch", 'stretch', size='sm'),
                                    ]
                                ),

                            ],
                            title="Mask",
                        ),
                        dbc.AccordionItem(
                            [
                                _stack(
                                    [
                                        _field("Step Size", 'step', size='sm'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Rot A", 'mot_rot_a', size='sm'),
                                        _field("Rot B", 'mot_rot_b', size='sm'),
                                        _field("Rot C", 'mot_rot_c', size='sm'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Axis X", 'mot_axis_x', size='sm'),
                                        _field("Axis Y", 'mot_axis_y', size='sm'),
                                        _field("Axis Z", 'mot_axis_z', size='sm'),
                                    ]
                                ),
                            ],
                            title="Motor Path",
                        ),
                        dbc.AccordionItem(
                            [
                                _stack(
                                    [
                                        _field("Pixels X", 'pixels_x', size='sm'),
                                        _field("Pixels Y", 'pixels_y', size='sm'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Size X", 'size_x', size='sm'),
                                        _field("Size Y", 'size_y', size='sm'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Rot A", 'det_rot_a', size='sm'),
                                        _field("Rot B", 'det_rot_b', size='sm'),
                                        _field("Rot C", 'det_rot_c', size='sm'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Pos X", 'det_pos_x', size='sm'),
                                        _field("Pos Y", 'det_pos_y', size='sm'),
                                        _field("Pos Z", 'det_pos_z', size='sm'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Offest", 'source_offset', size='sm'),
                                    ]
                                )
                            ],
                            title="Detector",
                        ),
                        dbc.AccordionItem(
                            [
                               _stack(
                                    [
                                        _field("Iters", 'iters', size='sm'),
                                    ]
                               ),
                               _stack(
                                   [
                                        _field("Pos Method", 'pos_method', size='sm'),
                                        _field("Pos Regpar", 'pos_regpar', size='sm'),
                                        _field("Pos Init", 'pos_init', size='sm'),
                                   ]
                               ),
                               html.Hr(),
                               _stack(
                                    [
                                        _ckbx("Enable Sigrecon", 'recon_sig', size='sm'),
                                    ]
                               ),
                               _stack(
                                    [
                                        _field("Sig Method", 'sig_method', size='sm'),
                                        _field("Sig Order", 'sig_order', size='sm'),
                                        _field("SigScale", 'sig_scale', size='sm'),
                                    ]
                               ), 
                               _stack(
                                    [
                                        _field("Sig Maxsize", 'sig_maxsize', size='sm'),
                                        _field("Sig Avgsize", 'sig_avgsize', size='sm'),
                                        _field("Sig Atol", 'sig_atol', size='sm'),
                                    ]
                               ),
                               html.Hr(),
                               _stack(
                                    [
                                        _ckbx("Enable Ene Recon", 'recon_ene', size='sm'),
                                        _ckbx("Enable Ene Exact", 'exact_ene', size='sm'),
                                    ]
                               ),
                               _stack(
                                   [
                                       _field("Ene Method", 'ene_method', size='sm'),
                                   ]
                               ),
                               _stack(
                                    [
                                        _field("Ene Min", 'ene_min', size='sm'),
                                        _field("Ene Max", 'ene_max', size='sm'),
                                        _field("Ene Step", 'ene_step', size='sm'),
                                    ]
                               ),
                            ],
                            title="Algorithm Parameters",
                        ),
                        ],
                        always_open=True
                    ),
                ],
                style={'width': '100%', 'overflow-x': 'auto'}
        )

def set_recon_form_props(recon, read_only=False):
    set_props("dataset", {'value':recon.dataset_id, 'readonly':read_only})

    set_props("frame_start", {'value':recon.file_range[0], 'readonly':read_only})
    set_props("frame_end", {'value':recon.file_range[1], 'readonly':read_only})
    set_props("x_start", {'value':recon.file_frame[0], 'readonly':read_only})
    set_props("x_end", {'value':recon.file_frame[1], 'readonly':read_only})
    set_props("y_start", {'value':recon.file_frame[2], 'readonly':read_only})
    set_props("y_end", {'value':recon.file_frame[3], 'readonly':read_only})
    set_props("depth_start", {'value':recon.geo_source_grid[0], 'readonly':read_only})
    set_props("depth_end", {'value':recon.geo_source_grid[1], 'readonly':read_only})
    set_props("depth_step", {'value':recon.geo_source_grid[2], 'readonly':read_only})
    set_props("recon_name", {'value':recon.notes, 'readonly':read_only})

    set_props("file_path", {'value':recon.file_path, 'readonly':read_only})
    set_props("file_output", {'value':recon.file_output, 'readonly':read_only})
    set_props("data_stacked", {'value':recon.file_stacked, 'readonly':read_only})
    set_props("h5_key", {'value':recon.file_h5_key, 'readonly':read_only})
    set_props("file_offset", {'value':recon.file_offset, 'readonly':read_only})

    #TODO: Coloring based on connnection to config table
    set_props("cenx", {'value':recon.geo_mask_focus_cenx, 'readonly':read_only})
    set_props("ceny", {'value':recon.geo_mask_focus_cenz, 'readonly':read_only})
    set_props("cenz", {'value':recon.geo_mask_focus_cenz, 'readonly':read_only})
    set_props("anglex", {'value':recon.geo_mask_focus_anglex, 'readonly':read_only})
    set_props("angley", {'value':recon.geo_mask_focus_angley, 'readonly':read_only})
    set_props("anglez", {'value':recon.geo_mask_focus_anglez, 'readonly':read_only})
    set_props("shift", {'value':recon.geo_mask_shift, 'readonly':read_only})
    set_props("mask_path", {'value':recon.geo_mask_path, 'readonly':read_only})
    set_props("reversed", {'value':recon.geo_mask_reversed, 'readonly':read_only})
    set_props("bitsize_0", {'value':recon.geo_mask_bitsizes[0], 'readonly':read_only})
    set_props("bitsize_1", {'value':recon.geo_mask_bitsizes[1], 'readonly':read_only})
    set_props("thickness", {'value':recon.geo_mask_thickness, 'readonly':read_only})
    set_props("resolution", {'value':recon.geo_mask_resolution, 'readonly':read_only})
    set_props("smoothness", {'value':recon.geo_mask_smoothness, 'readonly':read_only})
    set_props("widening", {'value':recon.geo_mask_widening, 'readonly':read_only})
    set_props("pad", {'value':recon.geo_mask_pad, 'readonly':read_only})
    set_props("stretch", {'value':recon.geo_mask_stretch, 'readonly':read_only})
    set_props("step", {'value':recon.geo_scanner_step, 'readonly':read_only})
    set_props("mot_rot_a", {'value':recon.geo_scanner_rot[0], 'readonly':read_only})
    set_props("mot_rot_b", {'value':recon.geo_scanner_rot[1], 'readonly':read_only})
    set_props("mot_rot_c", {'value':recon.geo_scanner_rot[2], 'readonly':read_only})
    set_props("mot_axis_x", {'value':recon.geo_scanner_axis[0], 'readonly':read_only})
    set_props("mot_axis_y", {'value':recon.geo_scanner_axis[1], 'readonly':read_only})
    set_props("mot_axis_z", {'value':recon.geo_scanner_axis[2], 'readonly':read_only})
    set_props("pixels_x", {'value':recon.geo_detector_shape[0], 'readonly':read_only})
    set_props("pixels_y", {'value':recon.geo_detector_shape[1], 'readonly':read_only})
    set_props("size_x", {'value':recon.geo_detector_size[0], 'readonly':read_only})
    set_props("size_y", {'value':recon.geo_detector_size[1], 'readonly':read_only})
    set_props("det_rot_a", {'value':recon.geo_detector_rot[0], 'readonly':read_only})
    set_props("det_rot_b", {'value':recon.geo_detector_rot[1], 'readonly':read_only})
    set_props("det_rot_c", {'value':recon.geo_detector_rot[2], 'readonly':read_only})
    set_props("det_pos_x", {'value':recon.geo_detector_pos[0], 'readonly':read_only})
    set_props("det_pos_y", {'value':recon.geo_detector_pos[1], 'readonly':read_only})
    set_props("det_pos_z", {'value':recon.geo_detector_pos[2], 'readonly':read_only})
    set_props("source_offset", {'value':recon.geo_source_offset, 'readonly':read_only})

    set_props('iters', {'value':recon.algo_iter, 'readonly':read_only})
    set_props("pos_method", {'value':recon.algo_pos_method, 'readonly':read_only})
    set_props("pos_regpar", {'value':recon.algo_pos_regpar, 'readonly':read_only})
    set_props("pos_init", {'value':recon.algo_pos_init, 'readonly':read_only})
    set_props("recon_sig", {'value':recon.algo_sig_recon, 'readonly':read_only})
    set_props("sig_method", {'value':recon.algo_sig_method, 'readonly':read_only})
    set_props("sig_order", {'value':recon.algo_sig_order, 'readonly':read_only})
    set_props("sig_scale", {'value':recon.algo_sig_scale, 'readonly':read_only})
    set_props("sig_maxsize", {'value':recon.algo_sig_init_maxsize, 'readonly':read_only})
    set_props("sig_avgsize", {'value':recon.algo_sig_init_maxsize, 'readonly':read_only})
    set_props("sig_atol", {'value':recon.algo_sig_init_atol, 'readonly':read_only})
    set_props("recon_ene", {'value':recon.algo_ene_recon, 'readonly':read_only})
    set_props("exact_ene", {'value':recon.algo_ene_exact, 'readonly':read_only})
    set_props("ene_method", {'value':recon.algo_ene_method, 'readonly':read_only})
    set_props("ene_min", {'value':recon.algo_ene_range[0], 'readonly':read_only})
    set_props("ene_max", {'value':recon.algo_ene_range[1], 'readonly':read_only})
    set_props("ene_step", {'value':recon.algo_ene_range[2], 'readonly':read_only})


peakindex_form = dbc.Row(
                [
                    dbc.Accordion(
                        [
                        dbc.AccordionItem(
                            [
                                _stack(
                                    [
                                        # _field("Dataset", "dataset", size='lg'),
                                        _field("Files Path", "filefolder", size='hg'),
                                    ]
                                ),
                                _stack(
                                    [
                                        # _field("Dataset", "dataset", size='lg'),
                                        _field("Filename Prefix", "filenamePrefix", size='lg'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Scan Point (Inner Index) Range Start", "scanPointStart", size='md'),
                                        _field("Scan Point (Inner Index) Range End", "scanPointEnd", size='md'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Geo File", "geoFile", size='hg'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Output Path", "outputFolder", size='hg'),
                                    ]
                                ),
                                # _stack(
                                #     [
                                #         _field("Depth (Outer Index) Range Start", "depthRangeStart", size='lg'),
                                #         _field("Depth (Outer Index) Range End", "depthRangeEnd", size='lg'),
                                #     ]
                                # ),
                            ],
                            title="Files",
                        ),
                        dbc.AccordionItem(
                            [
                                # _stack(
                                #     [
                                #         _field("Peak Program", "peakProgram", size='md'),
                                #     ]
                                # ),
                                _stack(
                                    [
                                        _field("Box Size", "boxsize", size='md'),
                                        _field("Max Rfactor", "maxRfactor", size='md'),
                                        _field("Threshold", "threshold", size='md'),
                                        _field("Threshold Ratio", "thresholdRatio", size='md'),
                                        
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Min Spot Size", "min_size", size='md'),
                                        _field("Min Spot Separation", "min_separation", size='md'),
                                        _field("Max No. of Spots", "max_number", size='md')
                                    ]
                                ),
                                _stack(
                                    [
                                        #_field("Peak Shape", "peakShape", size='lg'),
                                        dbc.Select(
                                            placeholder="Peak Shape",
                                            options=[
                                                {"label": "Lorentzian", "value": "Lorentzian"},
                                                {"label": "Gaussian", "value": "Gaussian"},
                                            ],
                                            style={'width':200},
                                            id="peakShape",
                                        ),
                                        _ckbx("Smooth peak before fitting", "smooth", size='md'),
                                        _ckbx("Cosmic Filter", "cosmicFilter", size='md'),
                                        # _ckbx("Cosmic Filter", "cosmicFilter", size='lg'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Detector CropX1", "detectorCropX1", size='md'),
                                        _field("Detector CropY1", "detectorCropY1", size='md'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Detector CropX2", "detectorCropX2", size='md'),
                                        _field("Detector CropY2", "detectorCropY2", size='md'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Mask File", "maskFile", size='hg'),
                                    ]
                                ),
                                dbc.Button(
                                    "Show Paths to Programs",
                                    id="collapse1-button",
                                    className="mb-3",
                                    color="primary",
                                    n_clicks=0,
                                ),
                                dbc.Collapse(
                                    [
                                        _field("peaksearch Path", "peaksearchPath", size='hg'),
                                        _field("p2q Path", "p2qPath", size='hg'),
                                    ],
                                id="collapse1",
                                is_open=False,
                                ),
                            ],
                            title="Peak Search",
                        ),
                        dbc.AccordionItem(
                            [
                                _stack(
                                    [
                                        _field("Cryst File", "crystFile", size='hg'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Max Calc Energy [keV]", "indexKeVmaxCalc", size='md'),
                                        _field("Max Test Energy [keV]", "indexKeVmaxTest", size='md'),
                                        _field("Index Angle Tolerance", "indexAngleTolerance", size='md'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Index HKL", "indexHKL", size='md'),
                                        # _field("Index H", "indexH", size='md'),
                                        # _field("Index K", "indexK", size='md'),
                                        # _field("Index L", "indexL", size='md'),
                                        _field("Index Cone", "indexCone", size='md'),
                                        _field("Max Peaks", "max_peaks", size='md'),
                                    ]
                                ),
                                dbc.Button(
                                    "Show Path to Program",
                                    id="collapse2-button",
                                    className="mb-3",
                                    color="primary",
                                    n_clicks=0,
                                ),
                                dbc.Collapse(
                                    [
                                        _field("Indexing Path", "indexingPath", size='hg'),
                                    ],
                                id="collapse2",
                                is_open=False,
                                ),
                            ],
                            title="Indexing",
                        ),
                        dbc.AccordionItem(
                            [
                                _stack(
                                    [
                                        _field("Energy Unit", "energyUnit", size='md'),
                                        _field("Exposure Unit", "exposureUnit", size='md'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Recip Lattice Unit", "recipLatticeUnit", size='md'),
                                        _field("Lattice Parameters Unit", "latticeParametersUnit", size='md'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Beamline", "beamline", size='md'),
                                        _field("Depth", "depth", size='md'),
                                    ]
                                ),
                            ],
                            title="Labels",
                        ),
                        ],
                        always_open=True
                    ),
                ],
                style={'width': '100%', 'overflow-x': 'auto'}
        )

@dash.callback(
    Output("collapse1", "is_open"),
    [Input("collapse1-button", "n_clicks")],
    [State("collapse1", "is_open")],
)
def toggle_collapse12(n, is_open):
    if n:
        return not is_open
    return is_open

@dash.callback(
    Output("collapse2", "is_open"),
    [Input("collapse2-button", "n_clicks")],
    [State("collapse2", "is_open")],
)
def toggle_collapse2(n, is_open):
    if n:
        return not is_open
    return is_open

def set_peakindex_form_props(peakindex, read_only=False):
    set_props("dataset", {'value':peakindex.dataset_id, 'readonly':read_only})
    
    # set_props("peakProgram", {'value':peakindex.peakProgram, 'readonly':read_only})
    set_props("threshold", {'value':peakindex.threshold, 'readonly':read_only})
    set_props("thresholdRatio", {'value':peakindex.thresholdRatio, 'readonly':read_only})
    set_props("maxRfactor", {'value':peakindex.maxRfactor, 'readonly':read_only})
    set_props("boxsize", {'value':peakindex.boxsize, 'readonly':read_only})
    set_props("max_number", {'value':peakindex.max_number, 'readonly':read_only})
    set_props("min_separation", {'value':peakindex.min_separation, 'readonly':read_only})
    set_props("peakShape", {'value':peakindex.peakShape, 'readonly':read_only})
    set_props("scanPointStart", {'value':peakindex.scanPointStart, 'readonly':read_only})
    set_props("scanPointEnd", {'value':peakindex.scanPointEnd, 'readonly':read_only})
    # set_props("depthRangeStart", {'value':peakindex.depthRangeStart, 'readonly':read_only})
    # set_props("depthRangeEnd", {'value':peakindex.depthRangeEnd, 'readonly':read_only})
    set_props("detectorCropX1", {'value':peakindex.detectorCropX1, 'readonly':read_only})
    set_props("detectorCropX2", {'value':peakindex.detectorCropX2, 'readonly':read_only})
    set_props("detectorCropY1", {'value':peakindex.detectorCropY1, 'readonly':read_only})
    set_props("detectorCropY2", {'value':peakindex.detectorCropY2, 'readonly':read_only})
    set_props("min_size", {'value':peakindex.min_size, 'readonly':read_only})
    set_props("max_peaks", {'value':peakindex.max_peaks, 'readonly':read_only})
    set_props("smooth", {'value':peakindex.smooth, 'readonly':read_only})
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
    set_props("cosmicFilter", {'value':peakindex.cosmicFilter, 'readonly':read_only})
    set_props("recipLatticeUnit", {'value':peakindex.recipLatticeUnit, 'readonly':read_only})
    set_props("latticeParametersUnit", {'value':peakindex.latticeParametersUnit, 'readonly':read_only})
    set_props("peaksearchPath", {'value':peakindex.peaksearchPath, 'readonly':read_only})
    set_props("p2qPath", {'value':peakindex.p2qPath, 'readonly':read_only})
    set_props("indexingPath", {'value':peakindex.indexingPath, 'readonly':read_only})
    set_props("outputFolder", {'value':peakindex.outputFolder, 'readonly':read_only})
    set_props("filefolder", {'value':peakindex.filefolder, 'readonly':read_only})
    set_props("filenamePrefix", {'value':peakindex.filenamePrefix, 'readonly':read_only})
    set_props("geoFile", {'value':peakindex.geoFile, 'readonly':read_only})
    set_props("crystFile", {'value':peakindex.crystFile, 'readonly':read_only})
    set_props("depth", {'value':peakindex.depth, 'readonly':read_only})
    set_props("beamline", {'value':peakindex.beamline, 'readonly':read_only})
    # set_props("cosmicFilter", {'value':peakindex.cosmicFilter, 'readonly':read_only})