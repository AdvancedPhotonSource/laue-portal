import dash
from dash import html, dcc, ctx, callback, Input, Output, State, set_props
import dash_bootstrap_components as dbc
import laue_portal.database.db_utils as db_utils
import laue_portal.database.db_schema as db_schema
from sqlalchemy import select
from sqlalchemy.orm import Session
import laue_portal.components.navbar as navbar
from dash.exceptions import PreventUpdate
from sqlalchemy import asc # Import asc for ordering
from laue_portal.components.recon_form import recon_form, set_recon_form_props
import urllib.parse
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import h5py

dash.register_page(__name__, path="/reconstruction")

layout = html.Div([
        navbar.navbar,
        dcc.Location(id='url-recon-page', refresh=False),
        dbc.Container(id='recon-content-container', fluid=True, className="mt-4",
                  children=[
                        html.H2(id='recon-id-header', className="mb-3"),
                        recon_form
                  ]),
        html.Div(children=[
                    dbc.Select(
                        placeholder="Select Detector Pixel",
                        id="pixels",
                    ),
                    dcc.Graph(
                        #style={'height': 300},
                        style={'display': 'inline-block'},
                        id="lineout-graph",
                    ),
                    dcc.Graph(
                        #style={'height': 300},
                        style={'display': 'inline-block', 'height': 300},
                        id="detector-graph",
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
                ]),
    ],
)

"""
=======================
Callbacks
=======================
"""
# @dash.callback(
#     Output('recon-table', 'columns', allow_duplicate=True),
#     Output('recon-table', 'data', allow_duplicate=True),
#     Input('upload-config', 'contents'),
#     prevent_initial_call=True,
# )
# def upload_config(contents):
#     try:
#         content_type, content_string = contents.split(',')
#         decoded = base64.b64decode(content_string)
#         config = yaml.safe_load(decoded)
#         recon_row = db_utils.import_recon_row(config)
#         recon_row.date = datetime.datetime.now()
#         recon_row.commit_id = 'TEST'
#         recon_row.calib_id = 'TEST'
#         recon_row.runtime = 'TEST'
#         recon_row.computer_name = 'TEST'
#         recon_row.dataset_id = 0
#         recon_row.notes = 'TEST'

#         with Session(db_utils.ENGINE) as session:
#             session.add(recon_row)
#             session.commit()

#     except Exception as e:
#         print('Unable to parse config')
#         print(e)
    
#     cols, recons = _get_recons()
#     return cols, recons


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

    pixel_index = index_pointer

    fig2 = px.imshow(integrated_lau)#, binary_string=True)
                                                         
    if isinstance(pixels_value, str): 
        pixel_index = [int(i) for i in pixels_value.split(',')]
    else:
        pixel_index = pixels_value
    
    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
    print(f'trigger_id {trigger_id}')

    if trigger_id == 'pixels':
        if pixel_index is not None:
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
            
            set_props('zoom_info',{'data':None})
            
            if all([x0, x1, y0, y1]):
                newLayout = go.Layout(
                    xaxis_range=[x0, x1],
                    yaxis_range=[y0, y1],
                )
                
                fig2['layout'] = newLayout
        
        if pixel_index is not None:
            str_pixels_value = ','.join(str(i) for i in pixel_index)
            if str_pixels_value != pixels_value:
                set_props('pixels',{'value':str_pixels_value})
    
    if pixel_index is not None:

        if pixel_index != index_pointer:
            set_props('index_pointer',{'value':pixel_index})

        p_x, p_y = pixel_index
        print(f'Selected: {p_x}, {p_y}')

        # Lineout plot
        #lau_slice = np.where(np.array(ind)==np.array(pixel_index))[0][0] # lau[*pixel_index,:]
        all_ind = loahdh5(file_output,'ind')
        lau_slice = np.where((all_ind[:,0]==pixel_index[0]) & (all_ind[:,1]==pixel_index[1]))[0][0]
        print('slice',lau_slice)
        lau_lineout = loahdh5(file_output,'lau',lau_slice)
        print('lineout shape',lau_lineout.shape)
        
        fig1 = px.line(lau_lineout)

        fig1.update_layout(
            title={'text':f'Intensity vs. Depth: {p_x}, {p_y}',
                'x':0.5,
                'xanchor':'center'},
            xaxis_title="Depth (microns)",
            yaxis_title="Intensity",
        )
        fig1.update(layout_showlegend=False)        
        
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


@callback(
    Output('recon-id-header', 'children'),
    Input('url-recon-page', 'href'),
    prevent_initial_call=True
)
def load_recon_data(href):
    if not href:
        raise PreventUpdate

    parsed_url = urllib.parse.urlparse(href)
    query_params = urllib.parse.parse_qs(parsed_url.query)
    
    recon_id = query_params.get('reconid', [None])[0]

    if recon_id:
        try:
            recon_id = int(recon_id)
            with Session(db_utils.ENGINE) as session:
                recon_data = session.query(db_schema.Recon).filter(db_schema.Recon.recon_id == recon_id).first()
                if recon_data:
                    set_recon_form_props(recon_data, read_only=True)

                    file_output = recon_data.file_output
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
                    return f"Recon | ID: {recon_id}"

        except Exception as e:
            print(f"Error loading reconstruction data: {e}")
            return f"Error loading data for Recon ID: {recon_id}"
    
    return "No Recon ID provided"


"""
=======================
Helper Functions
=======================
"""

def loahdh5(path, key, slice=None, results_filename = "results.h5"):
    results_file = Path(path)/results_filename
    f = h5py.File(results_file, 'r')
    if slice is None:
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