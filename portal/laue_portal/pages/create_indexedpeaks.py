import dash_bootstrap_components as dbc
from dash import html, Input, set_props, State
import dash
import laue_portal.pages.ui_shared as ui_shared
from dash import dcc
import base64
import yaml
import laue_portal.database.db_utils as db_utils
import datetime
import laue_portal.database.db_schema as db_schema
from sqlalchemy.orm import Session
#import laue_portal.recon.analysis_recon as analysis_recon

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
                            dcc.Upload(dbc.Button('Upload Config'), id='upload-peakindex-config'),
                    ], style={'display':'inline-block'}),
                ],
            )
        ),
        html.Hr(),
        html.Center(
            dbc.Button('Submit', id='submit_peakindex', color='primary'),
        ),
        html.Hr(),
        ui_shared.peakindex_form,
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
    Input('upload-peakindex-config', 'contents'),
    prevent_initial_call=True,
)
def upload_config(contents):
    try:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        config = yaml.safe_load(decoded)
        peakindex_row = db_utils.import_peakindex_row(config)
        peakindex_row.date = datetime.datetime.now()
        peakindex_row.commit_id = ''
        peakindex_row.calib_id = ''
        peakindex_row.runtime = ''
        peakindex_row.computer_name = ''
        peakindex_row.dataset_id = 0
        peakindex_row.notes = ''

        set_props("alert-upload", {'is_open': True, 
                                    'children': 'Config uploaded successfully',
                                    'color': 'success'})
        ui_shared.set_peakindex_form_props(peakindex_row)

    except Exception as e:
        set_props("alert-upload", {'is_open': True, 
                                    'children': f'Upload Failed! Error: {e}',
                                    'color': 'danger'})


@dash.callback(
    Input('submit_peakindex', 'n_clicks'),

    # State('dataset', 'value'),
    
    State('peakProgram', 'value'),
    State('threshold', 'value'),
    State('thresholdRatio', 'value'),
    State('maxRfactor', 'value'),
    State('boxsize', 'value'),
    State('max_number', 'value'),
    State('min_separation', 'value'),
    State('peakShape', 'value'),
    State('scanPointStart', 'value'),
    State('scanPointEnd', 'value'),
    # State('depthRangeStart', 'value'),
    # State('depthRangeEnd', 'value'),
    State('detectorCropX1', 'value'),
    State('detectorCropX2', 'value'),
    State('detectorCropY1', 'value'),
    State('detectorCropY2', 'value'),
    State('min_size', 'value'),
    State('max_peaks', 'value'),
    State('smooth', 'value'),
    State('maskFile', 'value'),
    State('indexKeVmaxCalc', 'value'),
    State('indexKeVmaxTest', 'value'),
    State('indexAngleTolerance', 'value'),
    State('indexH', 'value'),
    State('indexK', 'value'),
    State('indexL', 'value'),
    State('indexCone', 'value'),
    State('energyUnit', 'value'),
    State('exposureUnit', 'value'),
    State('cosmicFilter', 'value'),
    State('recipLatticeUnit', 'value'),
    State('latticeParametersUnit', 'value'),
    State('peaksearchPath', 'value'),
    State('p2qPath', 'value'),
    State('indexingPath', 'value'),
    State('outputFolder', 'value'),
    State('filefolder', 'value'),
    State('filenamePrefix', 'value'),
    State('geoFile', 'value'),
    State('crystFile', 'value'),
    State('depth', 'value'),
    State('beamline', 'value'),
    # State('cosmicFilter', 'value'),

    prevent_initial_call=True,
)
def submit_config(n,
    # dataset,
    peakProgram,
    threshold,
    thresholdRatio,
    maxRfactor,
    boxsize,
    max_number,
    min_separation,
    peakShape,
    scanPointStart,
    scanPointEnd,
    # depthRangeStart,
    # depthRangeEnd,
    detectorCropX1,
    detectorCropX2,
    detectorCropY1,
    detectorCropY2,
    min_size,
    max_peaks,
    smooth,
    maskFile,
    indexKeVmaxCalc,
    indexKeVmaxTest,
    indexAngleTolerance,
    indexH,
    indexK,
    indexL,
    indexCone,
    energyUnit,
    exposureUnit,
    cosmicFilter,
    recipLatticeUnit,
    latticeParametersUnit,
    peaksearchPath,
    p2qPath,
    indexingPath,
    outputFolder,
    filefolder,
    filenamePrefix,
    geoFile,
    crystFile,
    depth,
    beamline,
    # cosmicFilter,
    
):
    # TODO: Input validation and reponse
    
    peakindex = db_schema.PeakIndex(
        date=datetime.datetime.now(),
        commit_id='TEST',
        calib_id='TEST',
        runtime='TEST',
        computer_name='TEST',
        dataset_id=0,
        notes='TODO', 

        peakProgram=peakProgram,
        threshold=threshold,
        thresholdRatio=thresholdRatio,
        maxRfactor=maxRfactor,
        boxsize=boxsize,
        max_number=max_number,
        min_separation=min_separation,
        peakShape=peakShape,
        scanPointStart=scanPointStart,
        scanPointEnd=scanPointEnd,
        # depthRangeStart=depthRangeStart,
        # depthRangeEnd=depthRangeEnd,
        detectorCropX1=detectorCropX1,
        detectorCropX2=detectorCropX2,
        detectorCropY1=detectorCropY1,
        detectorCropY2=detectorCropY2,
        min_size=min_size,
        max_peaks=max_peaks,
        smooth=smooth,
        maskFile=maskFile,
        indexKeVmaxCalc=indexKeVmaxCalc,
        indexKeVmaxTest=indexKeVmaxTest,
        indexAngleTolerance=indexAngleTolerance,
        indexH=indexH,
        indexK=indexK,
        indexL=indexL,
        indexCone=indexCone,
        energyUnit=energyUnit,
        exposureUnit=exposureUnit,
        cosmicFilter=cosmicFilter,
        recipLatticeUnit=recipLatticeUnit,
        latticeParametersUnit=latticeParametersUnit,
        peaksearchPath=peaksearchPath,
        p2qPath=p2qPath,
        indexingPath=indexingPath,
        outputFolder=outputFolder,
        filefolder=filefolder,
        filenamePrefix=filenamePrefix,
        geoFile=geoFile,
        crystFile=crystFile,
        depth=depth,
        beamline=beamline,
        # cosmicFilter=cosmicFilter,
    )

    with Session(db_utils.ENGINE) as session:
        session.add(peakindex)
        config_dict = db_utils.create_peakindex_config_obj(peakindex)

        session.commit()
    
    set_props("alert-submit", {'is_open': True, 
                                'children': 'Config Added to Database',
                                'color': 'success'})

    #analysis_recon.run_analysis(config_dict)