import dash_bootstrap_components as dbc
from dash import html, set_props

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
        dbc.NavItem(dbc.NavLink("Scans", href="/")),
        dbc.NavItem(dbc.NavLink("Reconstructions", href="/reconstructions")),
        dbc.NavItem(dbc.NavLink("Indexing", href="/indexing")),
        #dbc.NavItem(dbc.NavLink("New Reconstruction", href="/create-reconstruction")),
        #dbc.NavItem(dbc.NavLink("New Indexing", href="/create-indexing")),
        dbc.NavItem(dbc.NavLink("Run Monitor", href="/runs")),
    ],
    brand="Coded Aperture Laue",
    brand_href="/",
    color="primary",
    className="navbar-lg",
    dark=True,
    style={"max-height": "50px"},
)


navbar = dbc.NavbarSimple(
    children=[
        dbc.NavItem(dbc.NavLink("Scans", href="/", id="nav-scans")),
        dbc.NavItem(dbc.NavLink("Reconstructions", href="/reconstructions", id="nav-recon")),
        dbc.NavItem(dbc.NavLink("Indexing", href="/indexing", id="nav-index")),
        #dbc.NavItem(dbc.NavLink("New Reconstruction", href="/create_reconstruction", id="nav-createRecon")),
        #dbc.NavItem(dbc.NavLink("New Indexing", href="/create_indexing", id="nav-createIndex")),
        dbc.NavItem(dbc.NavLink("Run Monitor", href="/runs")),
    ],
    brand="3DMN Portal",
    brand_href="/",
    color="primary",
    className="navbar-lg",
    dark=True,
    style={"max-height": "50px"},
)


def _recon_stack(objects):
    return dbc.Stack(
        objects, 
        direction="horizontal",
        gap=3
    )

def _recon_field(label, field_id, size='sm', kwargs={}):
    if size == 'sm':
        width='200px'
    elif size == 'md':
        width='350px'
    elif size == 'lg':
        width='500px'

    return dbc.InputGroup(
        [
            dbc.InputGroupText(label),
            dbc.Input(id=field_id, **kwargs),
        ],
        style={'width': width},
        className="mb-3",
    )

def _recon_ckbx(label, field_id, size='sm'):
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
                                _recon_stack(
                                    [
                                        _recon_field("Dataset", "dataset", size='lg')
                                    ]
                                ),
                                _recon_stack(
                                    [
                                        _recon_field("Frame Start", 'frame_start', size='sm'),
                                        _recon_field("Frame End", 'frame_end', size='sm'),
                                    ]
                                ),
                                _recon_stack(
                                    [
                                        _recon_field("X Start", 'x_start', size='sm'),
                                        _recon_field("X End", 'x_end', size='sm'),
                                        _recon_field("Y Start", 'y_start', size='sm'),
                                        _recon_field("Y End", 'y_end', size='sm'),
                                    ]
                                ),
                                _recon_stack(
                                    [
                                        _recon_field("Depth Start", 'depth_start', size='sm'),
                                        _recon_field("Depth End", 'depth_end', size='sm'),
                                        _recon_field("Depth Step", 'depth_step', size='sm'),
                                    ]
                                ),
                                _recon_stack(
                                    [
                                        _recon_field("Recon Name", 'recon_name', size='lg'),
                                    ]
                                ),
                            ],
                            title="Recon Parameters",
                        ),
                        dbc.AccordionItem(
                            [
                                _recon_stack(
                                    [
                                        _recon_field("File Path", 'file_path', size='lg')
                                    ]
                                ),
                                _recon_stack(
                                    [
                                        _recon_field('File Output', 'file_output', size='lg')
                                    ]
                                ),
                                _recon_stack(
                                    [
                                        _recon_ckbx("Data Stacked", 'data_stacked', size='sm'),
                                        _recon_field("H5_key", 'h5_key', size='sm'),
                                        _recon_field("File Offset", 'file_offset', size='sm'),
                                    ]
                                )
                            ],
                            title="File Parameters",
                        ),
                        dbc.AccordionItem(
                            [
                                _recon_stack(
                                    [
                                        _recon_field("CenX", 'cenx', size='sm'),
                                        _recon_field("CenY", 'ceny', size='sm'),
                                        _recon_field("CenZ", 'cenz', size='sm'),
                                    ]
                                ),
                                _recon_stack(
                                    [
                                        _recon_field("AngleX", 'anglex', size='sm'),
                                        _recon_field("AngleY", 'angley', size='sm'),
                                        _recon_field("AngleZ", 'anglez', size='sm'),
                                    ]
                                ),
                                _recon_stack(
                                    [
                                        _recon_field("Shift", 'shift', size='sm'), 
                                    ]
                                ),
                            ],
                            title="Calibration",
                        ),
                        dbc.AccordionItem(
                            [
                                _recon_stack(
                                    [
                                        _recon_field("Mask Path", 'mask_path', size='lg'),
                                        _recon_ckbx("Reversed", 'reversed', size='sm')
                                    ]
                                ),
                                _recon_stack(
                                    [
                                        _recon_field("Bitsize 0", 'bitsize_0', size='sm'),
                                        _recon_field("Bitsize 1", 'bitsize_1', size='sm'),
                                    ]
                                ),
                                _recon_stack(
                                    [
                                        _recon_field("Thickness", 'thickness', size='sm'),
                                        _recon_field("Resolution", 'resolution', size='sm'),
                                        _recon_field("Smoothness", 'smoothness', size='sm'),
                                    ]
                                ),
                                _recon_stack(
                                    [
                                        _recon_field("Widening", 'widening', size='sm'),
                                        _recon_field("Pad", 'pad', size='sm'),
                                        _recon_field("Stretch", 'stretch', size='sm'),
                                    ]
                                ),

                            ],
                            title="Mask",
                        ),
                        dbc.AccordionItem(
                            [
                                _recon_stack(
                                    [
                                        _recon_field("Step Size", 'step', size='sm'),
                                    ]
                                ),
                                _recon_stack(
                                    [
                                        _recon_field("Rot A", 'mot_rot_a', size='sm'),
                                        _recon_field("Rot B", 'mot_rot_b', size='sm'),
                                        _recon_field("Rot C", 'mot_rot_c', size='sm'),
                                    ]
                                ),
                                _recon_stack(
                                    [
                                        _recon_field("Axis X", 'mot_axis_x', size='sm'),
                                        _recon_field("Axis Y", 'mot_axis_y', size='sm'),
                                        _recon_field("Axis Z", 'mot_axis_z', size='sm'),
                                    ]
                                ),
                            ],
                            title="Motor Path",
                        ),
                        dbc.AccordionItem(
                            [
                                _recon_stack(
                                    [
                                        _recon_field("Pixels X", 'pixels_x', size='sm'),
                                        _recon_field("Pixels Y", 'pixels_y', size='sm'),
                                    ]
                                ),
                                _recon_stack(
                                    [
                                        _recon_field("Size X", 'size_x', size='sm'),
                                        _recon_field("Size Y", 'size_y', size='sm'),
                                    ]
                                ),
                                _recon_stack(
                                    [
                                        _recon_field("Rot A", 'det_rot_a', size='sm'),
                                        _recon_field("Rot B", 'det_rot_b', size='sm'),
                                        _recon_field("Rot C", 'det_rot_c', size='sm'),
                                    ]
                                ),
                                _recon_stack(
                                    [
                                        _recon_field("Pos X", 'det_pos_x', size='sm'),
                                        _recon_field("Pos Y", 'det_pos_y', size='sm'),
                                        _recon_field("Pos Z", 'det_pos_z', size='sm'),
                                    ]
                                ),
                                _recon_stack(
                                    [
                                        _recon_field("Offest", 'source_offset', size='sm'),
                                    ]
                                )
                            ],
                            title="Detector",
                        ),
                        dbc.AccordionItem(
                            [
                               _recon_stack(
                                    [
                                        _recon_field("Iters", 'iters', size='sm'),
                                    ]
                               ),
                               _recon_stack(
                                   [
                                        _recon_field("Pos Method", 'pos_method', size='sm'),
                                        _recon_field("Pos Regpar", 'pos_regpar', size='sm'),
                                        _recon_field("Pos Init", 'pos_init', size='sm'),
                                   ]
                               ),
                               html.Hr(),
                               _recon_stack(
                                    [
                                        _recon_ckbx("Enable Sigrecon", 'recon_sig', size='sm'),
                                    ]
                               ),
                               _recon_stack(
                                    [
                                        _recon_field("Sig Method", 'sig_method', size='sm'),
                                        _recon_field("Sig Order", 'sig_order', size='sm'),
                                        _recon_field(" SigScale", 'sig_scale', size='sm'),
                                    ]
                               ), 
                               _recon_stack(
                                    [
                                        _recon_field("Sig Maxsize", 'sig_maxsize', size='sm'),
                                        _recon_field("Sig Avgsize", 'sig_avgsize', size='sm'),
                                        _recon_field("Sig Atol", 'sig_atol', size='sm'),
                                    ]
                               ),
                               html.Hr(),
                               _recon_stack(
                                    [
                                        _recon_ckbx("Enable Ene Recon", 'recon_ene', size='sm'),
                                        _recon_ckbx("Enable Ene Exact", 'exact_ene', size='sm'),
                                    ]
                               ),
                               _recon_stack(
                                   [
                                       _recon_field("Ene Method", 'ene_method', size='sm'),
                                   ]
                               ),
                               _recon_stack(
                                    [
                                        _recon_field("Ene Min", 'ene_min', size='sm'),
                                        _recon_field("Ene Max", 'ene_max', size='sm'),
                                        _recon_field("Ene Step", 'ene_step', size='sm'),
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