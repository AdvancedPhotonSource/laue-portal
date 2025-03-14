import dash
from dash import html, dcc, callback, Input, Output, State, set_props, ctx
import dash_bootstrap_components as dbc
import laue_portal.pages.ui_shared as ui_shared
from dash import dcc, ctx, dash_table
from dash.exceptions import PreventUpdate
import laue_portal.database.db_utils as db_utils
import laue_portal.database.db_schema as db_schema
from sqlalchemy import select
from sqlalchemy.orm import Session
import pandas as pd
import base64
import yaml
import datetime
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import h5py

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
                #dbc.ModalBody(html.H1("TODO: Results Display")),
                html.Div(children=[
                    dbc.Select(
                        placeholder="Select Detector Pixel",
                        id="pixels",
                    ),
                    dcc.Graph(
                        #style={'height': 300},
                        style={'display': 'inline-block'},
                        id="lineout-graph"
                    ),
                    dcc.Graph(
                        #style={'height': 300},
                        style={'display': 'inline-block', 'height': 300},
                        id="detector-graph"
                    ),
                    dcc.Store(id='zoom_info'),
                    dcc.Store(id='index_pointer'),
                    dbc.Alert(
                        "No data found here",
                        is_open=False,
                        duration=2400,
                        color="warning",
                        id="alert-auto-no-data",
                    ),
                    dbc.Alert(
                        "Updating depth-profile plot",
                        is_open=False,
                        duration=2400,
                        color="success",
                        id="alert-auto-update-plot",
                    ),
                    dcc.Store(
                        id="results-path",
                    ),
                    dcc.Store(
                        id="integrated-lau",
                    ),
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
def _get_recons():
    with Session(db_utils.ENGINE) as session:
        recons = pd.read_sql(session.query(*VISIBLE_COLS ).statement, session.bind)

    cols = [{'name': str(col), 'id': str(col)} for col in recons.columns]
    cols.append({'name': 'Parameters', 'id': 'Parameters', 'presentation': 'markdown'})
    cols.append({'name': 'Results', 'id': 'Results', 'presentation': 'markdown'})

    recons['id'] = recons['recon_id']

    recons['Parameters'] = '**Parameters**'
    recons['Results'] = '**Results**'
    
    return cols, recons.to_dict('records')



@dash.callback(
    Output('recon-table', 'columns', allow_duplicate=True),
    Output('recon-table', 'data', allow_duplicate=True),
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
        recon_row.commit_id = 'TEST'
        recon_row.calib_id = 'TEST'
        recon_row.runtime = 'TEST'
        recon_row.computer_name = 'TEST'
        recon_row.dataset_id = 0
        recon_row.notes = 'TEST'

        with Session(db_utils.ENGINE) as session:
            session.add(recon_row)
            session.commit()

    except Exception as e:
        print('Unable to parse config')
        print(e)
    
    cols, recons = _get_recons()
    return cols, recons


@dash.callback(
        Input('integrated-lau', 'value'),
        Input('results-path', 'value'),
        Input('pixels', 'options'),
        Input('pixels', 'value'),
        Input('detector-graph', 'clickData'),
        Input('index_pointer', 'value'),
        State('zoom_info', 'data'),
)
def set_lineout_and_detector_graphs(integrated_lau, file_output, pixels_options, pixels_value, clickData, index_pointer=None,zoom_info=None):

    fig2 = px.imshow(integrated_lau)#, binary_string=True)
                                                         
    if isinstance(pixels_value, str): 
        pixel_index = [int(i) for i in pixels_value.split(',')]
    else:
        pixel_index = pixels_value
    
    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
    print(f'trigger_id {trigger_id}')

    if trigger_id == 'pixels':
        if np.any(pixel_index):
            if pixel_index == index_pointer:
                raise dash.exceptions.PreventUpdate
            else:
                set_props('zoom_info',{'data':None})

    if trigger_id in ('pixels','detector-graph','index_pointer'):
        ind = [e['value'] for e in pixels_options]

    if trigger_id == 'detector-graph':
        clicked_pixel_index = [clickData["points"][0][k] for k in ["x", "y"]]

        if clicked_pixel_index not in ind:
            set_props('alert-auto-no-data',{'is_open':True})
            print('alert-auto-no-data')

        else:
            pixel_index = clicked_pixel_index
            set_props('alert-auto-update-plot',{'is_open':True})
            print('alert-auto-update-plot')

        if zoom_info:
            x0, x1, y0, y1 = None, None, None, None
            if 'xaxis.range[0]' in zoom_info: x0 = zoom_info['xaxis.range[0]']
            if 'xaxis.range[1]' in zoom_info: x1 = zoom_info['xaxis.range[1]']
            if 'yaxis.range[0]' in zoom_info: y0 = zoom_info['yaxis.range[0]']
            if 'yaxis.range[1]' in zoom_info: y1 = zoom_info['yaxis.range[1]']
            
            if all([x0, x1, y0, y1]):
                newLayout = go.Layout(
                    xaxis_range=[x0, x1],
                    yaxis_range=[y0, y1],
                )
            else:
                newLayout = go.Layout(
                    xaxis_autorange=True,
                    yaxis_autorange="reversed",
                )
            fig2['layout'] = newLayout
        
        if np.any(pixel_index):
            str_pixels_value = ','.join(str(i) for i in pixel_index)
            if str_pixels_value != pixels_value:
                set_props('pixels',{'value':str_pixels_value})
    
    if np.any(pixel_index):

        if pixel_index != index_pointer:
            set_props('index_pointer',{'value':pixel_index})

        p_x, p_y = pixel_index
        print(f'Selected: {p_x}, {p_y}')

        # Lineout plot
        #lau_slice = np.where(np.array(ind)==np.array(pixel_index))[0][0] # lau[*pixel_index,:]
        all_ind = loahdh5(file_output,'ind')
        lau_slice = np.where((all_ind[:,0]==pixel_index[0]) & (all_ind[:,1]==pixel_index[1]))[0][0]
        lau_lineout = loahdh5(file_output,'lau',lau_slice)
        
        fig1 = px.line(lau_lineout)

        fig1.update_layout(
            title={'text':f'Intensity vs. Depth: {p_x}, {p_y}',
                'x':0.5,
                'xanchor':'center'}
        )
        
        set_props('lineout-graph',{'figure':fig1})

        # Detector plot: Add circle
        size = 100
        fig2.add_shape(type="circle",
            xref="x", yref="y",
            x0=p_x-size, y0=p_y-size, x1=p_x+size, y1=p_y+size,
            line_color="Red")

    fig2.update_layout(width=800, height=800,
                        coloraxis=dict(
                            colorscale='gray',
                            cmax=np.max(integrated_lau)/2**7, cauto=False)
    )
    fig2.update_yaxes(scaleanchor='x')

    set_props('detector-graph',{'figure':fig2})


@dash.callback(
    Output('zoom_info', 'data'),
    Input('detector-graph', 'relayoutData')
)
def update_zoom_info(relayout_data):
    return relayout_data



VISIBLE_COLS = [
    db_schema.Recon.recon_id,
    db_schema.Recon.date,
    db_schema.Recon.calib_id,
    db_schema.Recon.dataset_id,
    db_schema.Recon.notes,
]


@dash.callback(
    Output('recon-table', 'columns', allow_duplicate=True),
    Output('recon-table', 'data', allow_duplicate=True),
    Input('url','pathname'),
    prevent_initial_call=True,
)
def get_recons(path):
       if path == '/':
            cols, recons = _get_recons()
            return cols, recons
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
        set_props("modal-details-header", {'children':dbc.ModalTitle(f"Details for Recon {row_id} (Read Only)")})
        
        ui_shared.set_form_props(recon, read_only=True)


    
    elif col == 6:
        with Session(db_utils.ENGINE) as session:
            recon = session.query(db_schema.Recon).filter(db_schema.Recon.recon_id == row_id).first()

        set_props("modal-results", {'is_open':True})
        set_props("modal-results-header", {'children':dbc.ModalTitle(f"Results for Recon {row_id}")})
        
        file_output = recon.file_output
        set_props("results-path", {"value":file_output})

        integrated_lau = loadnpy(file_output)
        integrated_lau[np.isnan(integrated_lau)] = 0
        set_props("integrated-lau",{"value":integrated_lau})

        if np.count_nonzero(integrated_lau) > int(1E2):
            ind_slice = np.sort(np.argpartition(integrated_lau, -30, axis=None)[-30:]) #np.sort(np.random.randint(0,2048**2,30))#np.argsort(-integrated_lau)[:30]
            ind = loahdh5(file_output,'ind',ind_slice)
        else:
            ind = loahdh5(file_output,'ind')
        pixel_selections = [{"label": f'{i}', "value": i} for i in ind]
        set_props("pixels",{"options":pixel_selections})

    print(f"Row {row} and Column {col} was clicked")
    

"""
=======================
Helper Functions
=======================
"""

def loahdh5(path, key, slice=None, results_filename = "results.h5"):
    results_file = Path(path)/results_filename
    f = h5py.File(results_file, 'r')
    if not np.any(slice):
        value = f[key][:]
    else:
        value = f[key][slice]
    #logging.info("Loaded: " + str(file))
    return value

def loadnpy(path, results_filename = 'img' + 'results' + '.npy'):
    results_file = Path(path)/results_filename
    value = np.zeros((2**11,2**11))
    if results_file.exists():
        value = np.load(results_file)
    return value