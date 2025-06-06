import dash_bootstrap_components as dbc
from dash import html, dcc, Input, set_props, State
import dash
import base64
import yaml
import laue_portal.database.db_utils as db_utils
import datetime
import laue_portal.database.db_schema as db_schema
from sqlalchemy.orm import Session
import logging
logger = logging.getLogger(__name__)
import laue_portal.components.navbar as navbar
from laue_portal.components.recon_form import recon_form, set_recon_form_props

try:
    import laue_portal.recon.analysis_recon as analysis_recon
    _ANALYSIS_LIB_AVAILABLE = True
except ImportError:
    analysis_recon = None
    _ANALYSIS_LIB_AVAILABLE = False
    logger.warning("CA Reconstruction libraries not installed. Analysis will be skipped.")

dash.register_page(__name__)

layout = dbc.Container(
    [html.Div([
        navbar.navbar,
        dbc.Alert(
            "CA Reconstruction libraries not installed. Dry runs only.",
            id="alert-lib-warning",
            dismissable=True,
            is_open=not _ANALYSIS_LIB_AVAILABLE,
            color="warning",
        ),
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
        recon_form,
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
        set_recon_form_props(recon_row)

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
    
    State('file_path', 'value'),
    State('file_output', 'value'),
    State('data_stacked', 'value'),
    State('h5_key', 'value'),
    #State('file_offset', 'value'),

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
    State('det_rot_a', 'value'),
    State('det_rot_b', 'value'),
    State('det_rot_c', 'value'),
    State('det_pos_x', 'value'),
    State('det_pos_y', 'value'),
    State('det_pos_z', 'value'),
    State('source_offset', 'value'),

    State('iters', 'value'),
    State('pos_method', 'value'),
    State('pos_regpar', 'value'),
    State('pos_init', 'value'),
    State('recon_sig', 'value'),
    State('sig_method', 'value'),
    State('sig_order', 'value'),
    State('sig_scale', 'value'),
    State('sig_maxsize', 'value'),
    State('sig_avgsize', 'value'),
    State('sig_atol', 'value'),
    State('recon_ene', 'value'),
    State('exact_ene', 'value'),
    State('ene_method', 'value'),
    State('ene_min', 'value'),
    State('ene_max', 'value'),
    State('ene_step', 'value'),
    
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

    file_path,
    file_output,
    data_stacked,
    h5_key,
    #file_offset,

    cenx,
    ceny,
    cenz,
    anglex,
    angley,
    anglez,
    shift,

    mask_path,
    mask_reversed,
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
    det_rot_a,
    det_rot_b,
    det_rot_c,
    det_pos_x,
    det_pos_y,
    det_pos_z,
    source_offset,

    iters,
    pos_method,
    pos_regpar,
    pos_init,
    recon_sig,
    sig_method,
    sig_order,
    sig_scale,
    sig_maxsize,
    sig_avgsize,
    sig_atol,
    recon_ene,
    exact_ene,
    ene_method,
    ene_min,
    ene_max,
    ene_step,
    
):
    # TODO: Input validation and reponse
    
    recon = db_schema.Recon(
        date=datetime.datetime.now(),
        commit_id='TEST',
        calib_id='TEST',
        runtime='TEST',
        computer_name='TEST',
        dataset_id=0,
        notes='TODO', 

        scanNumber = dataset,

        file_path=file_path,
        file_output=file_output,
        file_stacked=data_stacked,
        file_range=[frame_start, frame_end],
        file_threshold=0,
        file_frame=[x_start, x_end, y_start, y_end],
        #file_offset=file_offset,
        file_ext='h5', #'TODO',
        file_h5_key=h5_key,
        
        comp_server='TODO',
        comp_workers=0,
        comp_usegpu=True,
        comp_batch_size=0,
        
        geo_mask_path=mask_path,
        geo_mask_reversed=mask_reversed,
        geo_mask_bitsizes=[bitsize_0, bitsize_1],
        geo_mask_thickness=thickness,
        geo_mask_resolution=resolution,
        geo_mask_smoothness=0,
        geo_mask_alpha=0,
        geo_mask_widening=widening,
        geo_mask_pad=pad,
        geo_mask_stretch=stretch,
        geo_mask_shift=shift,

        geo_mask_focus_cenx=cenx,
        geo_mask_focus_dist=ceny, 
        geo_mask_focus_anglez=anglez,
        geo_mask_focus_angley=angley,
        geo_mask_focus_anglex=anglex,
        geo_mask_focus_cenz=cenz,

        geo_mask_cal_id=0,
        geo_mask_cal_path='TODO',

        geo_scanner_step=step,
        geo_scanner_rot=[mot_rot_a, mot_rot_b, mot_rot_c],
        geo_scanner_axis=[mot_axis_x, mot_axis_y, mot_axis_z],

        geo_detector_shape=[pixels_x, pixels_y],
        geo_detector_size=[size_x, size_y],
        geo_detector_rot=[det_rot_a, det_rot_b, det_rot_c],
        geo_detector_pos=[det_pos_x, det_pos_y, det_pos_z],
        geo_source_offset=source_offset,
        geo_source_grid=[depth_start, depth_end, depth_step],

        algo_iter=iters,
        algo_pos_method=pos_method,
        algo_pos_regpar=pos_regpar,
        algo_pos_init=pos_init,
        algo_sig_recon=recon_sig,
        algo_sig_method=sig_method,
        algo_sig_order=sig_order,
        algo_sig_scale=sig_scale,
        algo_sig_init_maxsize=sig_maxsize,
        algo_sig_init_avgsize=sig_avgsize,
        algo_sig_init_atol=sig_atol,
        algo_ene_recon=recon_ene,
        algo_ene_exact=exact_ene,
        algo_ene_method=ene_method,
        algo_ene_range=[ene_min, ene_max, ene_step],
    )

    with Session(db_utils.ENGINE) as session:
        session.add(recon)
        config_dict = db_utils.create_config_obj(recon)

        session.commit()
    
    set_props("alert-submit", {'is_open': True, 
                                'children': 'Config Added to Database',
                                'color': 'success'})

    if _ANALYSIS_LIB_AVAILABLE:
        analysis_recon.run_analysis(config_dict)
    else:
        logger.warning("Skipping reconstruction analysis; libraries not available")
