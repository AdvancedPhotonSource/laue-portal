import dash_bootstrap_components as dbc
from dash import html, Input, set_props, State
import dash
import laue_portal.pages.ui_shared as ui_shared
from dash import dcc
import base64
import yaml
import laue_portal.database.db_utils as db_utils
import datetime

dash.register_page(__name__)

layout = dbc.Container(
    [html.Div([
        ui_shared.navbar,
        dbc.Alert(
            "Hello! I am an alert",
            id="alert-upload",
            dismissable=True,
            is_open=False,
        ),
        dbc.Alert(
            "Hello! I am an alert",
            id="alert-submit",
            dismissable=True,
            is_open=False,
        ),
        html.Hr(),
        html.Center(
            html.Div(
                [
                    html.Div([
                        dbc.Button('Copy From Existing (TODO)', id='copy-existing', className='mr-2'),
                    ], style={'display':'inline-block'}),
                    html.Div([
                            dcc.Upload(dbc.Button('Upload Config'), id='upload-config'),
                    ], style={'display':'inline-block'}),
                ],
            )
        ),
        html.Hr(),
        html.Center(
            dbc.Button('Submit', id='submit', color='primary'),
        ),
        html.Hr(),
        ui_shared.recon_form,
    ],
    )
    ],
    className='dbc', 
    fluid=True
)

"""
=======================
Callbacks
=======================
"""
@dash.callback(
    Input('upload-config', 'contents'),
    prevent_initial_call=True,
)
def upload_config(contents):
    try:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        config = yaml.safe_load(decoded)
        recon_row = db_utils.import_recon_row(config)
        recon_row.date = datetime.datetime.now()
        recon_row.commit_id = ''
        recon_row.calib_id = ''
        recon_row.runtime = ''
        recon_row.computer_name = ''
        recon_row.dataset_id = 0
        recon_row.notes = ''

        set_props("alert-upload", {'is_open': True, 
                                    'children': 'Config uploaded successfully',
                                    'color': 'success'})
        ui_shared.set_form_props(recon_row)

    except Exception as e:
        set_props("alert-upload", {'is_open': True, 
                                    'children': f'Upload Failed! Error: {e}',
                                    'color': 'danger'})


@dash.callback(
    Input('submit', 'n_clicks'),

    State('dataset', 'value'),
    State('frame_start', 'value'),
    State('frame_end', 'value'),
    State('x_start', 'value'),
    State('x_end', 'value'),
    State('y_start', 'value'),
    State('y_end', 'value'),
    State('depth_start', 'value'),
    State('depth_end', 'value'),
    State('depth_step', 'value'),
    State('recon_name', 'value'),

    State('cenx', 'value'),
    State('ceny', 'value'),
    State('cenz', 'value'),
    State('anglex', 'value'),
    State('angley', 'value'),
    State('anglez', 'value'),
    State('shift', 'value'),

    State('mask_path', 'value'),
    State('reversed', 'value'),
    State('bitsize_0', 'value'),
    State('bitsize_1', 'value'),
    State('thickness', 'value'),
    State('resolution', 'value'),
    State('widening', 'value'),
    State('pad', 'value'),
    State('stretch', 'value'),

    State('step', 'value'),
    State('mot_rot_a', 'value'),
    State('mot_rot_b', 'value'),
    State('mot_rot_c', 'value'),
    State('mot_axis_x', 'value'),
    State('mot_axis_y', 'value'),
    State('mot_axis_z', 'value'),
    State('pixels_x', 'value'),
    State('pixels_y', 'value'),
    State('size_x', 'value'),
    State('size_y', 'value'),

    prevent_initial_call=True,
)
def submit_config(n,
    dataset,
    frame_start,
    frame_end,
    x_start,
    x_end,
    y_start,
    y_end,
    depth_start,
    depth_end,
    depth_step,
    recon_name,

    cenx,
    ceny,
    cenz,
    anglex,
    angley,
    anglez,
    shift,

    mask_path,
    reversed,
    bitsize_0,
    bitsize_1,
    thickness,
    resolution,
    widening,
    pad,
    stretch,

    step,
    mot_rot_a,
    mot_rot_b,
    mot_rot_c,
    mot_axis_x,
    mot_axis_y,
    mot_axis_z,
    pixels_x,
    pixels_y,
    size_x,
    size_y,
    
):
    print('Parsed')