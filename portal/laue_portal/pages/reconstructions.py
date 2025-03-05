import dash
from dash import html, dcc, callback, Input, Output, State, set_props
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
                    dbc.Alert(
                        "No data found here",
                        is_open=False,
                        duration=1200,
                        color="warning",
                        id="alert-auto-no-data",
                    ),
                    dbc.Alert(
                        "Updating depth-profile plot",
                        is_open=False,
                        duration=1200,
                        color="success",
                        id="alert-auto-update-plot",
                    ),
                    dcc.Store(
                        id="results-path",
                    ),
                    dcc.Store(
                        id="listed-pixels",
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


@dash.callback(Output('lineout-graph', 'figure', allow_duplicate=True),
               Output('detector-graph', 'clickData'),
               Input('results-path', 'value'),
               Input('listed-pixels', 'value'),
               Input('pixels', 'value'),
               prevent_initial_call=True,
)
def set_lineout_graph_from_dropdown(file_output, ind, pixel_index):
    if file_output is None: return dash.no_update
    if ind is None: return dash.no_update
    if pixel_index is None: return dash.no_update
    print("set_lineout_graph_from_dropdown")
    if isinstance(pixel_index, str): 
        pixel_index = [int(i) for i in pixel_index.split(',')]
    
    p_y, p_x = pixel_index

    lau = loahdh5(file_output,'lau')
    lau_lineout = lau[np.where(ind==np.array(pixel_index))[0][0]] # lau[*pixel_index,:]
    
    fig = px.line(lau_lineout)

    fig.update_layout(
        title={'text':f'Intensity vs. Depth: {p_x}, {p_y}',
               'x':0.5,
               'xanchor':'center'}
    )

    clickData = None #Reset clickData
 
    return fig, clickData


@dash.callback(Output('lineout-graph', 'figure'),
               Input('results-path', 'value'),
               Input('listed-pixels', 'value'),
               Input('detector-graph', 'clickData'),
)
def set_lineout_graph_from_click(file_output, ind, clickData):
    if not clickData:
        raise dash.exceptions.PreventUpdate
    if file_output is None: return dash.no_update
    if ind is None: return dash.no_update
    print("set_lineout_graph_from_click")

    #Graph click
    #print(f'previous {pixel_index}')
    clicked_pixel_index = [clickData["points"][0][k] for k in ["y", "x"]]
    if clicked_pixel_index not in ind:
        raise dash.exceptions.PreventUpdate
        print(f'no ind {clicked_pixel_index}')
        #alert_0 = True
    else:
        print(f'ind {clicked_pixel_index}')
        pixel_index = clicked_pixel_index
        #alert_1 = True
    #
    
    p_y, p_x = pixel_index

    lau = loahdh5(file_output,'lau')
    lau_lineout = lau[np.where(ind==np.array(pixel_index))[0][0]] # lau[*pixel_index,:]
    
    fig = px.line(lau_lineout)

    fig.update_layout(
        title={'text':f'Intensity vs. Depth: {p_x}, {p_y}',
               'x':0.5,
               'xanchor':'center'}
    )

    return fig


@dash.callback(Output('detector-graph', 'figure', allow_duplicate=True),
               Input('integrated-lau', 'value'),
               Input('pixels', 'value'),
               prevent_initial_call=True,
)
def set_detector_graph_from_dropdown(integrated_lau, pixel_index=None):
    if integrated_lau is None: return dash.no_update
    if not pixel_index:
        raise dash.exceptions.PreventUpdate
    print("set_detector_graph_from_dropdown")

    fig = px.imshow(integrated_lau)#, binary_string=True)

    if pixel_index:
        print(f'changed: {pixel_index}')
        if isinstance(pixel_index, str): 
            pixel_index = np.array([int(i) for i in pixel_index.split(',')])
            print(f'changed check: {pixel_index}')
            print(f'changed check0: {pixel_index[0]}')

        p_y, p_x = pixel_index
        print(f'both {p_y}, {p_x}')
        
        # Add circle
        size = 100
        fig.add_shape(type="circle",
            xref="x", yref="y",
            x0=p_x-size, y0=p_y-size, x1=p_x+size, y1=p_y+size,
            line_color="Red")

    fig.update_layout(width=800, height=800,
                        coloraxis=dict(
                            colorscale='gray',
                            cmax=100, cauto=False)
    )
    fig.update_yaxes(scaleanchor='x')      

    return fig


@dash.callback(Output('alert-auto-no-data', 'is_open'),
               Output('alert-auto-update-plot', 'is_open'),
               Output('detector-graph', 'figure'),
               Output('pixels', 'value'),
               Input('integrated-lau', 'value'),
               Input('listed-pixels', 'value'),
               Input('detector-graph', 'clickData'),
               State("alert-auto-no-data", "is_open"),
               State("alert-auto-update-plot", "is_open"),
               State('pixels', 'value'),
               State('zoom_info', 'data'),
               Input('detector-graph', 'figure'),
)
def set_detector_graph_from_click(integrated_lau, ind, clickData, alert_0, alert_1, pixel_index=None, zoom_info=None, prior_fig=None):
    # if not clickData:
    #     raise dash.exceptions.PreventUpdate
    print("set_detector_graph_from_click")
    if integrated_lau is None: return dash.no_update

    fig = px.imshow(integrated_lau)#, binary_string=True)

    if clickData:
        #Graph click
        print(f'previous {pixel_index}')
        clicked_pixel_index = [clickData["points"][0][k] for k in ["y", "x"]]
        if clicked_pixel_index not in ind:
            print(f'no ind {clicked_pixel_index}')
            alert_0 = True
            if prior_fig:
                fig = prior_fig
                print(fig['layout'])
            else:
                return alert_0, alert_1, dash.no_update, pixel_index
        else:
            print(f'ind {clicked_pixel_index}')
            pixel_index = clicked_pixel_index
            alert_1 = True
        #

        if zoom_info:
            x0, x1, y0, y1 = None, None, None, None
            print(zoom_info)
            if 'xaxis.range[0]' in zoom_info: x0 = zoom_info['xaxis.range[0]']
            if 'xaxis.range[1]' in zoom_info: x1 = zoom_info['xaxis.range[1]']
            if 'yaxis.range[0]' in zoom_info: y0 = zoom_info['yaxis.range[0]']
            if 'yaxis.range[1]' in zoom_info: y1 = zoom_info['yaxis.range[1]']
            
            if all([x0, x1, y0, y1]):
                newLayout = go.Layout(
                    xaxis_range=[x0, x1],
                    yaxis_range=[y0, y1],
                )
                fig['layout'] = newLayout
                print(newLayout)

    if pixel_index:
        print(f'changed: {pixel_index}')
        if isinstance(pixel_index, str): 
            pixel_index = np.array([int(i) for i in pixel_index.split(',')])
            print(f'changed check: {pixel_index}')
            print(f'changed check0: {pixel_index[0]}')

        p_y, p_x = pixel_index
        print(f'both {p_y}, {p_x}')
        
        # Add circle
        size = 100
        fig.add_shape(type="circle",
            xref="x", yref="y",
            x0=p_x-size, y0=p_y-size, x1=p_x+size, y1=p_y+size,
            line_color="Red")

    fig['layout'].update({'width':800,'height':800,
                        'coloraxis':dict(
                            colorscale='gray',
                            cmax=100, cauto=False)}
    )
    fig['layout']['yaxis'].update(dict(scaleanchor='x'))
    
    if clickData:
        pixel_index = None #Reset pixel_index
 
    return alert_0, alert_1, fig, pixel_index


@dash.callback(
    Output('zoom_info', 'data'),
    [Input('detector-graph', 'relayoutData'),
     Input('zoom_info', 'data')]
)
def update_zoom_info(relayout_data, zoom_info):
    if zoom_info is None:
        return relayout_data
    else:
        zoom_info.update(relayout_data)
        return zoom_info



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
        
        ind = loahdh5(file_output,'ind')
        set_props("listed-pixels",{"value":ind})

        pixel_selections = [{"label": f'{i}', "value": i} for i in ind]
        set_props("pixels",{"options":pixel_selections})

        integrated_lau = loadnpy(file_output)
        set_props("integrated-lau",{"value":integrated_lau})

        #set_props("lineout-graph",{'figure':fig1})
        #set_props("detector-graph",{'figure':fig2})

    print(f"Row {row} and Column {col} was clicked")
    

"""
=======================
Helper Functions
=======================
"""

def loahdh5(path, key, results_filename = "results.h5"):
    results_file = Path(path)/results_filename
    f = h5py.File(results_file, 'r')
    value = f[key][:]
    #logging.info("Loaded: " + str(file))
    return value

def loadnpy(path, results_filename = 'img' + 'results' + '.npy'):
    results_file = Path(path)/results_filename
    value = np.zeros((2**11,2**11))
    if results_file.exists():
        value = np.load(results_file)
    return value