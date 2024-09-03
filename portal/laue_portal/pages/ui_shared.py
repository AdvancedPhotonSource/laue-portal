import dash_bootstrap_components as dbc
from dash import html

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
        dbc.NavItem(dbc.NavLink("Run Monitor", href="/runs")),
    ],
    brand="Coded Apeture Laue",
    brand_href="/",
    color="primary",
    className="navbar-expand-lg",
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
            dbc.Input(id=field_id, readonly=True, **kwargs),
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
                                        _recon_field("Wideing", 'widening', size='sm'),
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