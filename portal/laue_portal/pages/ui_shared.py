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
        dbc.NavItem(dbc.NavLink("Reconstructions", href="/")),
        dbc.NavItem(dbc.NavLink("New Reconstruction", href="/create-reconstruction")),
        dbc.NavItem(dbc.NavLink("Recon Run Monitor", href="/runs")),
        dbc.NavItem(dbc.NavLink("Indexations", href="/indexedpeaks")),
        dbc.NavItem(dbc.NavLink("New Indexation", href="/create-indexedpeaks")),
        dbc.NavItem(dbc.NavLink("Index Run Monitor", href="/index-runs")),
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

recon_form = dbc.Row(
                [
                    dbc.Accordion(
                        [
                        dbc.AccordionItem(
                            [
                                _stack(
                                    [
                                        _field("Dataset", "dataset", size='lg')
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
                                        _field("File Path", 'file_path', size='lg')
                                    ]
                                ),
                                _stack(
                                    [
                                        _field('File Output', 'file_output', size='lg')
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
                                        _ckbx("Reversed", 'reversed', size='sm')
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


def set_form_props(recon, read_only=False):
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
    # set_props("dataset", {'value':peakindex.dataset_id, 'readonly':read_only})
    
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