import dash
from dash import html, dcc, callback, Input, Output, set_props
import dash_bootstrap_components as dbc
import laue_portal.pages.ui_shared as ui_shared
from dash import dcc, ctx, dash_table
from dash.exceptions import PreventUpdate
import laue_portal.database.db_utils as db_utils
import laue_portal.database.db_schema as db_schema
from sqlalchemy import select
from sqlalchemy.orm import Session
import pandas as pd
import numpy as np
import plotly.express as px
from pathlib import Path
import h5py

files = [(Path('../results')/f).with_suffix('.h5') for f in
        ['results6_by13_start0','results30_by1_start0','results30_by3_start0']]

dash.register_page(__name__, path='/')

layout = html.Div([
        ui_shared.navbar,
        dcc.Location(id='url', refresh=False),
        dbc.Row(
            [
                dash_table.DataTable(
                    id='recon-table',
                    filter_action="native",
                    sort_action="native",
                    sort_mode="multi",
                    page_action="native",
                    page_current= 0,
                    page_size= 20,
                )
            ],
            style={'width': '100%', 'overflow-x': 'auto'}
        ),
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("Header"), id="modal-details-header"),
                dbc.ModalBody(ui_shared.recon_form),
            ],
            id="modal-details",
            size="xl",
            is_open=False,
        ),
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("Header"), id="modal-results-header"),
                dbc.ModalBody(html.H1("TODO: Results Display")),
                html.Div(children=[
                    dbc.Select(
                        id="pixels",
                        placeholder="Select Detector Pixel"
                    ),
                    dcc.Graph(
                        #style={'height': 300},
                        style={'display': 'inline-block'},
                        id='my-graph-example'
                    ),
                    # dcc.Graph(
                    #     #style={'height': 300},
                    #     style={'display': 'inline-block', 'height': 300},
                    #     id='my-graph-example2'
                    # )
                ])
            ],
            id="modal-results",
            size="xl",
            is_open=False,
        ),
    ],
)

"""
=======================
Callbacks
=======================
"""

@dash.callback(Output('my-graph-example', 'figure'),
               Input('pixels','value'))
def set_lineout_graph(pixel_index):
    if pixel_index is None: return dash.no_update
    
    pixel_index = [int(i) for i in pixel_index.split(',')]
    lau = loahdh5(files[0],'lau')
    print(pixel_index[:],pixel_index[0],pixel_index[1],)
    lau_lineout = lau[*pixel_index,:]
    fig = px.line(lau_lineout)

    return fig
     


VISIBLE_COLS = [
    db_schema.Recon.recon_id,
    db_schema.Recon.date,
    db_schema.Recon.calib_id,
    db_schema.Recon.dataset_id,
    db_schema.Recon.notes,
]


@dash.callback(Output('recon-table', 'columns'),
               Output('recon-table', 'data'),
               Input('url','pathname'))
def get_recons(path):
       if path == '/':
            with Session(db_utils.ENGINE) as session:
                recons = pd.read_sql(session.query(*VISIBLE_COLS ).statement, session.bind)

            cols = [{'name': str(col), 'id': str(col)} for col in recons.columns]
            cols.append({'name': 'Parameters', 'id': 'Parameters', 'presentation': 'markdown'})
            cols.append({'name': 'Results', 'id': 'Results', 'presentation': 'markdown'})

            recons['id'] = recons['recon_id']

            recons['Parameters'] = '**Parameters**'
            recons['Results'] = '**Results**'

            return cols, recons.to_dict('records')
       else:
            raise PreventUpdate


@dash.callback(
    Input("recon-table", "active_cell"),
)
def cell_clicked(active_cell):
    if active_cell is None:
        return dash.no_update

    print(active_cell)
    row = active_cell["row"]
    row_id = active_cell["row_id"]
    col = active_cell["column"]

    if col == 5:
        with Session(db_utils.ENGINE) as session:
            recon = session.query(db_schema.Recon).filter(db_schema.Recon.recon_id == row_id).first()
        
        set_props("modal-details", {'is_open':True})
        set_props("modal-details-header", {'children':dbc.ModalTitle(f"Details for Recon {row_id}")})
        set_props("dataset", {'value':recon.dataset_id})
        set_props("frame_start", {'value':recon.file_range[0]})
        set_props("frame_end", {'value':recon.file_range[1]})
        set_props("x_start", {'value':recon.file_frame[0]})
        set_props("x_end", {'value':recon.file_frame[1]})
        set_props("y_start", {'value':recon.file_frame[2]})
        set_props("y_end", {'value':recon.file_frame[3]})
        set_props("depth_start", {'value':recon.geo_source_grid[0]})
        set_props("depth_end", {'value':recon.geo_source_grid[1]})
        set_props("depth_step", {'value':recon.geo_source_grid[2]})
        set_props("recon_name", {'value':recon.notes})
        #TODO: Coloring based on connnection to config table
        set_props("cenx", {'value':recon.geo_mask_focus_cenx})
        set_props("ceny", {'value':recon.geo_mask_focus_cenz})
        set_props("cenz", {'value':recon.geo_mask_focus_cenz})
        set_props("anglex", {'value':recon.geo_mask_focus_anglex})
        set_props("angley", {'value':recon.geo_mask_focus_angley})
        set_props("anglez", {'value':recon.geo_mask_focus_anglez})
        set_props("shift", {'value':recon.geo_mask_shift})
        set_props("mask_path", {'value':recon.geo_mask_path})
        set_props("reversed", {'value':recon.geo_mask_reversed})
        set_props("bitsize_0", {'value':recon.geo_mask_bitsizes[0]})
        set_props("bitsize_1", {'value':recon.geo_mask_bitsizes[1]})
        set_props("thickness", {'value':recon.geo_mask_thickness})
        set_props("resolution", {'value':recon.geo_mask_resolution})
        set_props("smoothness", {'value':recon.geo_mask_smoothness})
        set_props("widening", {'value':recon.geo_mask_widening})
        set_props("pad", {'value':recon.geo_mask_pad})
        set_props("stretch", {'value':recon.geo_mask_stretch})
        set_props("step", {'value':recon.geo_scanner_step})
        set_props("mot_rot_a", {'value':recon.geo_scanner_rot[0]})
        set_props("mot_rot_b", {'value':recon.geo_scanner_rot[1]})
        set_props("mot_rot_c", {'value':recon.geo_scanner_rot[2]})
        set_props("mot_axis_x", {'value':recon.geo_scanner_axis[0]})
        set_props("mot_axis_y", {'value':recon.geo_scanner_axis[1]})
        set_props("mot_axis_z", {'value':recon.geo_scanner_axis[2]})
        set_props("pixels_x", {'value':recon.geo_detector_shape[0]})
        set_props("pixels_y", {'value':recon.geo_detector_shape[1]})
        set_props("size_x", {'value':recon.geo_detector_size[0]})
        set_props("size_y", {'value':recon.geo_detector_size[1]})
        set_props("det_rot_a", {'value':recon.geo_detector_rot[0]})
        set_props("det_rot_b", {'value':recon.geo_detector_rot[1]})
        set_props("det_rot_c", {'value':recon.geo_detector_rot[2]})
        set_props("det_pos_x", {'value':recon.geo_detector_pos[0]})
        set_props("det_pos_y", {'value':recon.geo_detector_pos[1]})
        set_props("det_pos_z", {'value':recon.geo_detector_pos[2]})
        set_props('iters', {'value':recon.algo_iter})
        set_props("pos_method", {'value':recon.algo_pos_method})
        set_props("pos_regpar", {'value':recon.algo_pos_regpar})
        set_props("pos_init", {'value':recon.algo_pos_init})
        set_props("recon_sig", {'value':recon.algo_sig_recon})
        set_props("sig_method", {'value':recon.algo_sig_method})
        set_props("sig_order", {'value':recon.algo_sig_order})
        set_props("sig_scale", {'value':recon.algo_sig_scale})
        set_props("sig_maxsize", {'value':recon.algo_sig_init_maxsize})
        set_props("sig_avgsize", {'value':recon.algo_sig_init_maxsize})
        set_props("sig_atol", {'value':recon.algo_sig_init_atol})
        set_props("recon_ene", {'value':recon.algo_ene_recon})
        set_props("exact_ene", {'value':recon.algo_ene_exact})
        set_props("ene_method", {'value':recon.algo_ene_method})
        set_props("ene_min", {'value':recon.algo_ene_range[0]})
        set_props("ene_max", {'value':recon.algo_ene_range[1]})
        set_props("ene_step", {'value':recon.algo_ene_range[2]})

        





    
    elif col == 6:
        set_props("modal-results", {'is_open':True})
        set_props("modal-results-header", {'children':dbc.ModalTitle(f"Results for Recon {row_id}")})

        lau = loahdh5(files[0],'lau')
        lau_mean = np.sum(lau,axis=2)
        ind = [(ix,iy) for ix,iy in zip(*np.where(lau_mean!=0))]

        pixel_selections = [{"label": f"{i}", "value": i} for i in ind]
        set_props("pixels",{'options':pixel_selections})

        #fig2 = px.imshow(lau_mean, color_continuous_scale='gray')#, binary_string=True)

        #set_props("my-graph-example",{'figure':fig1})
        #set_props("my-graph-example2",{'figure':fig2})

    print(f"Row {row} and Column {col} was clicked")
    

"""
=======================
Helper Functions
=======================
"""

def loahdh5(file, key):
    f = h5py.File(file, 'r')
    value = f[key][:]
    #logging.info("Loaded: " + str(file))
    return value