import dash_bootstrap_components as dbc
from dash import html, Input, set_props, State
import dash
from dash import dcc
import base64
import yaml
import laue_portal.database.db_utils as db_utils
import datetime
import laue_portal.database.db_schema as db_schema
import laue_portal.components.navbar as navbar
from sqlalchemy.orm import Session
import laueindexing.pyLaueGo as pyLaueGo
from laue_portal.components.peakindex_form import peakindex_form, set_peakindex_form_props
import urllib.parse
from dash.exceptions import PreventUpdate
import os

PEAKINDEX_DEFAULTS = {
    "peakProgram": "peaksearch",
    "threshold": 250,
    "thresholdRatio": -1,
    "maxRfactor": 0.5,
    "boxsize": 18,
    "min_separation": 40,
    "peakShape": "Lorentzian",
    "scanPointStart": 1,
    "scanPointEnd": 2,
    "detectorCropX1": 0,
    "detectorCropX2": 2047,
    "detectorCropY1": 0,
    "detectorCropY2": 2047,
    "min_size": 1.13,
    "max_peaks": 50,
    "smooth": 0,
    "maskFile": "None", 
    "indexKeVmaxCalc": 17.2,
    "indexKeVmaxTest": 30.0,
    "indexAngleTolerance": 0.1,
    "indexH": 1,
    "indexK": 1,
    "indexL": 1,
    "indexCone": 72.0,
    "energyUnit": "keV",
    "exposureUnit": "sec",
    "cosmicFilter": True,  # Assuming the last occurrence in YAML is the one to use
    "recipLatticeUnit": "1/nm",
    "latticeParametersUnit": "nm",
    "peaksearchPath": None,
    "p2qPath": None,
    "indexingPath": None,
    "outputFolder": "tests/data/output",
    "filefolder": "tests/data/gdata",
    "filenamePrefix": "HAs_long_laue1_",
    "geoFile": "tests/data/geo/geoN_2022-03-29_14-15-05.xml",
    "crystFile": "tests/data/crystal/Al.xtal",
    "depth": float('nan'), # Representing YAML nan
    "beamline": "34ID-E"
}

dash.register_page(__name__)

layout = dbc.Container(
    [html.Div([
        navbar.navbar,
        dcc.Location(id='url-create-indexedpeaks', refresh=False),
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
        dbc.Alert(
            "Scan data loaded successfully",
            id="alert-scan-loaded",
            dismissable=True,
            is_open=False,
            color="success",
        ),
        html.Hr(),
        html.Center(
            html.Div(
                [
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
        peakindex_form,
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
        set_peakindex_form_props(peakindex_row)

    except Exception as e:
        set_props("alert-upload", {'is_open': True, 
                                    'children': f'Upload Failed! Error: {e}',
                                    'color': 'danger'})


@dash.callback(
    Input('submit_peakindex', 'n_clicks'),
    
    State('dataset', 'value'),
    
    # State('peakProgram', 'value'),
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
    State('indexHKL', 'value'),
    # State('indexH', 'value'),
    # State('indexK', 'value'),
    # State('indexL', 'value'),
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
    dataset,
    # peakProgram,
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
    indexHKL,
    # indexH,
    # indexK,
    # indexL,
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
        dataset_id=dataset or 0,
        notes='TODO', 

        # peakProgram=peakProgram,
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
        indexH=int(str(indexHKL)[0]),
        indexK=int(str(indexHKL)[1]),
        indexL=int(str(indexHKL)[2]),
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

    """ TODO: Running not implemented yet. 
    pyLaueGo = pyLaueGo(config_dict)
    pyLaueGo.run(0, 1)
    """

@dash.callback(
    Input('url-create-indexedpeaks', 'href'),
    prevent_initial_call=True,
)
def load_scan_data_from_url(href):
    """
    Load scan data when scan_id is provided in URL query parameter
    URL format: /create-indexpeaks?scan_id={scan_id}
    """
    if not href:
        raise PreventUpdate

    parsed_url = urllib.parse.urlparse(href)
    query_params = urllib.parse.parse_qs(parsed_url.query)
    
    scan_id = query_params.get('scan_id', [None])[0]

    if scan_id:
        try:
            scan_id = int(scan_id)
            with Session(db_utils.ENGINE) as session:
                # Query metadata and scan data
                metadata = session.query(db_schema.Metadata).filter(
                    db_schema.Metadata.scanNumber == scan_id
                ).first()
                
                scans = session.query(db_schema.Scan).filter(
                    db_schema.Scan.scanNumber == scan_id
                ).all()

                if metadata:
                    # Create a PeakIndex object with populated defaults from metadata/scan
                    peakindex_defaults = db_schema.PeakIndex(
                        # Metadata fields
                        date=datetime.datetime.now(),
                        commit_id='',
                        calib_id=metadata.calib_id or 0,
                        runtime='',
                        computer_name='',
                        dataset_id=metadata.scanNumber,
                        notes=f"Auto-populated from scan {scan_id}. Original notes: {metadata.notes or ''}",
                        
                        # File-related fields derived from metadata
                        filefolder=os.path.dirname(metadata.mda_file) if metadata.mda_file else PEAKINDEX_DEFAULTS["filefolder"],
                        filenamePrefix=os.path.splitext(os.path.basename(metadata.mda_file))[0] if metadata.mda_file else PEAKINDEX_DEFAULTS["filenamePrefix"],
                        
                        # Energy-related fields from source
                        indexKeVmaxCalc=metadata.source_energy or PEAKINDEX_DEFAULTS["indexKeVmaxCalc"],
                        indexKeVmaxTest=metadata.source_energy or PEAKINDEX_DEFAULTS["indexKeVmaxTest"],
                        energyUnit=metadata.source_energy_unit or PEAKINDEX_DEFAULTS["energyUnit"],
                        
                        # Scan point range from scan data
                        scanPointStart=PEAKINDEX_DEFAULTS["scanPointStart"],
                        scanPointEnd=PEAKINDEX_DEFAULTS["scanPointEnd"], # Probably needs logic to determine which dim is the scan dim
                        
                        # Default processing parameters - set to None to leave empty for user input
                        threshold=PEAKINDEX_DEFAULTS["threshold"],
                        thresholdRatio=PEAKINDEX_DEFAULTS["thresholdRatio"],
                        maxRfactor=PEAKINDEX_DEFAULTS["maxRfactor"],
                        boxsize=PEAKINDEX_DEFAULTS["boxsize"],
                        max_number=PEAKINDEX_DEFAULTS["max_peaks"], # Assuming max_peaks from YAML maps to max_number
                        min_separation=PEAKINDEX_DEFAULTS["min_separation"],
                        peakShape=PEAKINDEX_DEFAULTS["peakShape"],
                        detectorCropX1=PEAKINDEX_DEFAULTS["detectorCropX1"],
                        detectorCropX2=PEAKINDEX_DEFAULTS["detectorCropX2"],
                        detectorCropY1=PEAKINDEX_DEFAULTS["detectorCropY1"],
                        detectorCropY2=PEAKINDEX_DEFAULTS["detectorCropY2"],
                        min_size=PEAKINDEX_DEFAULTS["min_size"],
                        max_peaks=PEAKINDEX_DEFAULTS["max_peaks"],
                        smooth=PEAKINDEX_DEFAULTS["smooth"],
                        maskFile=PEAKINDEX_DEFAULTS["maskFile"],
                        indexAngleTolerance=PEAKINDEX_DEFAULTS["indexAngleTolerance"],
                        indexH=PEAKINDEX_DEFAULTS["indexH"],
                        indexK=PEAKINDEX_DEFAULTS["indexK"],
                        indexL=PEAKINDEX_DEFAULTS["indexL"],
                        indexCone=PEAKINDEX_DEFAULTS["indexCone"],
                        exposureUnit=PEAKINDEX_DEFAULTS["exposureUnit"],
                        cosmicFilter=PEAKINDEX_DEFAULTS["cosmicFilter"],
                        recipLatticeUnit=PEAKINDEX_DEFAULTS["recipLatticeUnit"],
                        latticeParametersUnit=PEAKINDEX_DEFAULTS["latticeParametersUnit"],
                        peaksearchPath=PEAKINDEX_DEFAULTS["peaksearchPath"],
                        p2qPath=PEAKINDEX_DEFAULTS["p2qPath"],
                        indexingPath=PEAKINDEX_DEFAULTS["indexingPath"],
                        outputFolder=PEAKINDEX_DEFAULTS["outputFolder"],
                        geoFile=PEAKINDEX_DEFAULTS["geoFile"],
                        crystFile=PEAKINDEX_DEFAULTS["crystFile"],
                        depth=f"{len(scans)}D" if scans else PEAKINDEX_DEFAULTS["depth"],
                        beamline=PEAKINDEX_DEFAULTS["beamline"]
                    )
                    
                    # Populate the form with the defaults
                    set_peakindex_form_props(peakindex_defaults)
                    
                    # Show success message
                    set_props("alert-scan-loaded", {
                        'is_open': True, 
                        'children': f'Scan {scan_id} data loaded successfully. Dataset ID: {metadata.dataset_id}, Energy: {metadata.source_energy} {metadata.source_energy_unit}',
                        'color': 'success'
                    })
                else:
                    # Show error if scan not found
                    set_props("alert-scan-loaded", {
                        'is_open': True, 
                        'children': f'Scan {scan_id} not found in database',
                        'color': 'warning'
                    })
                    
        except Exception as e:
            set_props("alert-scan-loaded", {
                'is_open': True, 
                'children': f'Error loading scan data: {str(e)}',
                'color': 'danger'
            })