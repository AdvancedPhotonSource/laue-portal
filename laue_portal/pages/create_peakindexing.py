import datetime
import logging
import os
import urllib.parse
import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, set_props, State
from dash.exceptions import PreventUpdate
from sqlalchemy.orm import Session
import laue_portal.database.db_utils as db_utils
import laue_portal.database.db_schema as db_schema
import laue_portal.components.navbar as navbar
from laue_portal.database.db_utils import get_catalog_data, remove_root_path_prefix
from laue_portal.components.peakindex_form import peakindex_form, set_peakindex_form_props
from laue_portal.processing.redis_utils import enqueue_peakindexing, STATUS_REVERSE_MAPPING
from config import DEFAULT_VARIABLES
from srange import srange

logger = logging.getLogger(__name__)

JOB_DEFAULTS = {
    "computer_name": 'example_computer',
    "status": 0, #pending, running, finished, stopped
    "priority": 0,
    "submit_time": datetime.datetime.now(),
    "start_time": datetime.datetime.now(),
    "finish_time": datetime.datetime.now(),
}

PEAKINDEX_DEFAULTS = {
    "scanNumber": 276994,
    "peakProgram": "peaksearch",
    "threshold": 100, #250
    "thresholdRatio": -1,
    "maxRfactor": 2.0, #0.5
    "boxsize": 5, #18
    "min_separation": 10, #40
    "peakShape": "L", #"Lorentzian"
    # "scanPointStart": 1,
    # "scanPointEnd": 2,
    "scanPoints": "",#"1-2",  # String field for srange parsing
    "depthRange": "",  # Empty string for no depth range
    "detectorCropX1": 0,
    "detectorCropX2": 2047,
    "detectorCropY1": 0,
    "detectorCropY2": 2047,
    "min_size": 3, #1.13
    "max_peaks": 50,
    "smooth": False, #0
    "maskFile": "None", 
    "indexKeVmaxCalc": 30.0, #17.2
    "indexKeVmaxTest": 35.0, #30.0
    "indexAngleTolerance": 0.12, #0.1
    "indexH": 0, #1
    "indexK": 0, #1
    "indexL": 1,
    "indexCone": 72.0,
    "energyUnit": "keV",
    "exposureUnit": "sec",
    "cosmicFilter": True,  # Assuming the last occurrence in YAML is the one to use
    "recipLatticeUnit": "1/nm",
    "latticeParametersUnit": "nm",
    # "peaksearchPath": None,
    # "p2qPath": None,
    # "indexingPath": None,
    "outputFolder": "analysis/scan_%d/index_%d",# "analysis/scan_%d/rec_%d/index_%d",
    # "filefolder": "tests/data/gdata",
    # "filenamePrefix": "HAs_long_laue1_",
    "geoFile": "tests/data/geo/geoN_2022-03-29_14-15-05.xml",
    "crystFile": "tests/data/crystal/Al.xtal",
    "depth": float('nan'), # Representing YAML nan
    "beamline": "34ID-E"
}

CATALOG_DEFAULTS = {
    "filefolder": "tests/data/gdata",
    "filenamePrefix": "HAs_long_laue1_",
}

# DEFAULT_VARIABLES = {
#     "author": "",
#     "notes": "",
# }

dash.register_page(__name__)

layout = dbc.Container(
    [html.Div([
        navbar.navbar,
        dcc.Location(id='url-create-peakindexing', refresh=False),
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
                            dcc.Upload(dbc.Button('Upload Config'), id='upload-peakindexing-config'),
                    ], style={'display':'inline-block'}),
                ],
            )
        ),
        html.Hr(),
        html.Center(
            html.H3(id="peakindex-title", children="New peak indexing"),
        ),
        html.Hr(),
        html.Center(
            dbc.Button('Submit', id='submit_peakindexing', color='primary'),
        ),
        html.Hr(),
        peakindex_form,
        dcc.Store(id="next-peakindex-id"),
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
# @dash.callback(
#     Input('upload-peakindexing-config', 'contents'),
#     prevent_initial_call=True,
# )
# def upload_config(contents):
#     try:
#         content_type, content_string = contents.split(',')
#         decoded = base64.b64decode(content_string)
#         config = yaml.safe_load(decoded)
#         peakindex_row = db_utils.import_peakindex_row(config)
#         peakindex_row.date = datetime.datetime.now()
#         peakindex_row.commit_id = ''
#         peakindex_row.calib_id = ''
#         peakindex_row.runtime = ''
#         peakindex_row.computer_name = ''
#         peakindex_row.dataset_id = 0
#         peakindex_row.notes = ''

#         set_props("alert-upload", {'is_open': True, 
#                                     'children': 'Config uploaded successfully',
#                                     'color': 'success'})
#         set_peakindex_form_props(peakindex_row)

#     except Exception as e:
#         set_props("alert-upload", {'is_open': True, 
#                                     'children': f'Upload Failed! Error: {e}',
#                                     'color': 'danger'})
#         raise e


@dash.callback(
    Input('submit_peakindexing', 'n_clicks'),
    
    State('next-peakindex-id', 'value'),
    
    State('scanNumber', 'value'),
    State('author', 'value'),
    State('notes', 'value'),
    State('recon_id', 'value'),
    State('wirerecon_id', 'value'),
    # State('peakProgram', 'value'),
    State('threshold', 'value'),
    State('thresholdRatio', 'value'),
    State('maxRfactor', 'value'),
    State('boxsize', 'value'),
    State('max_number', 'value'),
    State('min_separation', 'value'),
    State('peakShape', 'value'),
    # State('scanPointStart', 'value'),
    # State('scanPointEnd', 'value'),
    # State('depthRangeStart', 'value'),
    # State('depthRangeEnd', 'value'),
    State('scanPoints', 'value'),
    State('depthRange', 'value'),
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
    # State('peaksearchPath', 'value'),
    # State('p2qPath', 'value'),
    # State('indexingPath', 'value'),
    State('data_path', 'value'),
    # State('filefolder', 'value'),
    State('filenamePrefix', 'value'),
    State('outputFolder', 'value'),
    State('geoFile', 'value'),
    State('crystFile', 'value'),
    State('depth', 'value'),
    State('beamline', 'value'),
    # State('cosmicFilter', 'value'),
    
    prevent_initial_call=True,
)
def submit_parameters(n, peakindex_id,
    scanNumbers, #Pooled scanNumbers
    author,
    notes,
    recon_id,
    wirerecon_id,
    # peakProgram,
    threshold,
    thresholdRatio,
    maxRfactor,
    boxsize,
    max_number,
    min_separation,
    peakShape,
    # scanPointStart,
    # scanPointEnd,
    # depthRangeStart,
    # depthRangeEnd,
    scanPoints,
    depthRange,
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
    # peaksearchPath,
    # p2qPath,
    # indexingPath,
    data_path,
    # filefolder,
    filenamePrefix,
    outputFolder,
    geometry_file,
    crystal_file,
    depth,
    beamline,
    # cosmicFilter,
    
):
    # TODO: Input validation and response
    
    root_path = DEFAULT_VARIABLES["root_path"]
    # Convert relative paths to full paths # Strip leading slashes to ensure paths are treated as relative
    full_geometry_file = os.path.join(root_path, geometry_file.lstrip('/'))
    full_crystal_file = os.path.join(root_path, crystal_file.lstrip('/'))
    
    # Parse scan_numbers, data paths, filename prefixes, and output folders if they are semicolon-separated (for pooled scans)
    scan_numbers = str(scanNumbers).split('; ')
    data_paths = data_path.split('; ')
    filename_prefixes = filenamePrefix.split('; ')
    output_folders = outputFolder.split('; ')
    
    for i, scanNumber in enumerate(scan_numbers):
        # Use the corresponding output folder
        full_output_folder = os.path.join(root_path, output_folders[i].lstrip('/'))
        
        # Create output directory if it doesn't exist
        try:
            os.makedirs(full_output_folder, exist_ok=True)
            logger.info(f"Output directory: {full_output_folder}")
        except Exception as e:
            logger.error(f"Failed to create output directory {full_output_folder}: {e}")
            set_props("alert-submit", {'is_open': True, 
                                      'children': f'Failed to create output directory: {str(e)}',
                                      'color': 'danger'})
            continue

        JOB_DEFAULTS.update({'submit_time':datetime.datetime.now()})
        JOB_DEFAULTS.update({'start_time':datetime.datetime.now()})
        JOB_DEFAULTS.update({'finish_time':datetime.datetime.now()})
        
        job = db_schema.Job(
            computer_name=JOB_DEFAULTS['computer_name'],
            status=JOB_DEFAULTS['status'],
            priority=JOB_DEFAULTS['priority'],

            submit_time=JOB_DEFAULTS['submit_time'],
            start_time=JOB_DEFAULTS['start_time'],
            finish_time=JOB_DEFAULTS['finish_time'],
        )

        with Session(db_utils.ENGINE) as session:
            
            session.add(job)
            session.flush()  # Get job_id without committing
            job_id = job.job_id
            
            # Create subjobs for parallel processing
            # Parse scanPoints using srange
            scanPoints_srange = srange(scanPoints)
            scanPoint_nums = scanPoints_srange.list()
            
            # Parse depthRange if provided using srange
            if depthRange and depthRange.strip():
                depthRange_srange = srange(depthRange)
                depthRange_nums = depthRange_srange.list()
            else:
                depthRange_nums = [None]  # No reconstruction indices
            
            # Create subjobs for each combination of scan point and depth
            subjob_count = 0
            for scanPoint_num in scanPoint_nums:
                for depthRange_num in depthRange_nums:
                    subjob = db_schema.SubJob(
                        job_id=job_id,
                        computer_name=JOB_DEFAULTS['computer_name'],
                        status=STATUS_REVERSE_MAPPING["Queued"],
                        priority=JOB_DEFAULTS['priority']
                    )
                    session.add(subjob)
                    subjob_count += 1
    
            peakindex = db_schema.PeakIndex(
                # date=datetime.datetime.now(),
                # commit_id='TEST',
                # calib_id='TEST',
                # runtime='TEST',
                # computer_name='TEST',
                # dataset_id=0,
                # notes='TODO', 

                scanNumber = scanNumber,
                job_id = job_id,
                author = author,
                notes = notes,
                recon_id = recon_id,
                wirerecon_id = wirerecon_id,

                # peakProgram=peakProgram,
                threshold=threshold,
                thresholdRatio=thresholdRatio,
                maxRfactor=maxRfactor,
                boxsize=boxsize,
                max_number=max_number,
                min_separation=min_separation,
                peakShape=peakShape,
                # scanPointStart=scanPointStart,
                # scanPointEnd=scanPointEnd,
                # depthRangeStart=depthRangeStart,
                # depthRangeEnd=depthRangeEnd,
                scanPoints=scanPoints,
                depthRange=depthRange,
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
                # peaksearchPath=peaksearchPath,
                # p2qPath=p2qPath,
                # indexingPath=indexingPath,
                outputFolder=full_output_folder,  # Store full path in database
                geoFile=full_geometry_file,  # Store full path in database
                crystFile=full_crystal_file,  # Store full path in database
                depth=depth,
                beamline=beamline,
                # cosmicFilter=cosmicFilter,
            )

        # with Session(db_utils.ENGINE) as session:
            session.add(peakindex)
            # config_dict = db_utils.create_config_obj(peakindex)

            session.commit()
        
        set_props("alert-submit", {'is_open': True, 
                                    'children': 'Entry Added to Database',
                                    'color': 'success'})

        # Enqueue the job to Redis
        try:
            # Prepare lists of input and output files for all subjobs
            input_files = []
            output_dirs = []
            
            # Construct full data path from form values
            full_data_path = os.path.join(root_path, data_paths[i].lstrip('/'))
            
            for scanPoint_num in scanPoint_nums:
                for depthRange_num in depthRange_nums:
                    # Prepare parameters for peak indexing
                    file_str = filename_prefixes[i] % scanPoint_num
                    
                    if depthRange_num is not None:
                        # Reconstruction file with depth index
                        input_filename = file_str + f"_{depthRange_num}.h5"
                    else:
                        # Raw data file
                        input_filename = file_str + ".h5"
                    input_file = os.path.join(full_data_path, input_filename)
                    
                    input_files.append(input_file)
                    output_dirs.append(full_output_folder)
            
            # Enqueue the batch job with all files
            rq_job_id = enqueue_peakindexing(
                job_id=job_id,
                input_files=input_files,
                output_files=output_dirs,
                geometry_file=full_geometry_file,
                crystal_file=full_crystal_file,
                boxsize=boxsize,
                max_rfactor=maxRfactor,
                min_size=min_size,
                min_separation=min_separation,
                threshold=threshold,
                peak_shape=peakShape,
                max_peaks=max_peaks,
                smooth=smooth,
                index_kev_max_calc=indexKeVmaxCalc,
                index_kev_max_test=indexKeVmaxTest,
                index_angle_tolerance=indexAngleTolerance,
                index_cone=indexCone,
                index_h=int(str(indexHKL)[0]),
                index_k=int(str(indexHKL)[1]),
                index_l=int(str(indexHKL)[2])
            )
            
            logger.info(f"Peakindexing batch job {job_id} enqueued with RQ ID: {rq_job_id} for {len(input_files)} files")
            
            set_props("alert-submit", {'is_open': True, 
                                        'children': f'Job {job_id} submitted to queue with {len(input_files)} file(s)',
                                        'color': 'info'})
        except Exception as e:
            logger.error(f"Failed to enqueue job: {e}")
            set_props("alert-submit", {'is_open': True, 
                                        'children': f'Failed to queue job: {str(e)}',
                                        'color': 'danger'})


@dash.callback(
    Input('url-create-peakindexing','pathname'),
    prevent_initial_call=True,
)
def get_peakindexings(path):
    root_path = DEFAULT_VARIABLES["root_path"]
    if path == '/create-peakindexing':
        # Create a PeakIndex object with form defaults (not for database insertion)
        peakindex_defaults = db_schema.PeakIndex(
            scanNumber=PEAKINDEX_DEFAULTS.get("scanNumber", 0),
            
            # User text
            author=DEFAULT_VARIABLES["author"],
            notes=DEFAULT_VARIABLES["notes"],
            
            # Processing parameters
            threshold=PEAKINDEX_DEFAULTS["threshold"],
            thresholdRatio=PEAKINDEX_DEFAULTS["thresholdRatio"],
            maxRfactor=PEAKINDEX_DEFAULTS["maxRfactor"],
            boxsize=PEAKINDEX_DEFAULTS["boxsize"],
            max_number=PEAKINDEX_DEFAULTS["max_peaks"],
            min_separation=PEAKINDEX_DEFAULTS["min_separation"],
            peakShape=PEAKINDEX_DEFAULTS["peakShape"],
            scanPoints=PEAKINDEX_DEFAULTS["scanPoints"],
            depthRange=PEAKINDEX_DEFAULTS["depthRange"],
            detectorCropX1=PEAKINDEX_DEFAULTS["detectorCropX1"],
            detectorCropX2=PEAKINDEX_DEFAULTS["detectorCropX2"],
            detectorCropY1=PEAKINDEX_DEFAULTS["detectorCropY1"],
            detectorCropY2=PEAKINDEX_DEFAULTS["detectorCropY2"],
            min_size=PEAKINDEX_DEFAULTS["min_size"],
            max_peaks=PEAKINDEX_DEFAULTS["max_peaks"],
            smooth=PEAKINDEX_DEFAULTS["smooth"],
            maskFile=PEAKINDEX_DEFAULTS["maskFile"],
            indexKeVmaxCalc=PEAKINDEX_DEFAULTS["indexKeVmaxCalc"],
            indexKeVmaxTest=PEAKINDEX_DEFAULTS["indexKeVmaxTest"],
            indexAngleTolerance=PEAKINDEX_DEFAULTS["indexAngleTolerance"],
            indexH=PEAKINDEX_DEFAULTS["indexH"],
            indexK=PEAKINDEX_DEFAULTS["indexK"],
            indexL=PEAKINDEX_DEFAULTS["indexL"],
            indexCone=PEAKINDEX_DEFAULTS["indexCone"],
            energyUnit=PEAKINDEX_DEFAULTS["energyUnit"],
            exposureUnit=PEAKINDEX_DEFAULTS["exposureUnit"],
            cosmicFilter=PEAKINDEX_DEFAULTS["cosmicFilter"],
            recipLatticeUnit=PEAKINDEX_DEFAULTS["recipLatticeUnit"],
            latticeParametersUnit=PEAKINDEX_DEFAULTS["latticeParametersUnit"],
            
            # File paths
            outputFolder=PEAKINDEX_DEFAULTS["outputFolder"],
            geoFile=PEAKINDEX_DEFAULTS["geoFile"],
            crystFile=PEAKINDEX_DEFAULTS["crystFile"],
            
            # Other fields
            depth=PEAKINDEX_DEFAULTS["depth"],
            beamline=PEAKINDEX_DEFAULTS["beamline"],
        )
        
        # Add root_path from DEFAULT_VARIABLES
        peakindex_defaults.root_path = root_path
        with Session(db_utils.ENGINE) as session:
            # Get next peakindex_id
            next_peakindex_id = db_utils.get_next_id(session, db_schema.PeakIndex)                                
            # Store next_peakindex_id and update title
            set_props('next-peakindex-id', {'value': next_peakindex_id})
            set_props('peakindex-title', {'children': f"New peak indexing {next_peakindex_id}"})
            
            # Retrieve data_path and filenamePrefix from catalog data
            catalog_data = get_catalog_data(session, PEAKINDEX_DEFAULTS["scanNumber"], root_path, CATALOG_DEFAULTS)
        peakindex_defaults.data_path = catalog_data["data_path"]
        peakindex_defaults.filenamePrefix = catalog_data["filenamePrefix"]
            
        # Populate the form with the defaults
        set_peakindex_form_props(peakindex_defaults)
    else:
        raise PreventUpdate

@dash.callback(
    Input('url-create-peakindexing', 'href'),
    prevent_initial_call=True,
)
def load_scan_data_from_url(href):
    """
    Load scan data and optionally existing recon and peakindex data when provided in URL query parameters
    URL format: /create-peakindexing?scan_id={scan_id}
    Pooled URL format: /create-peakindexing?scan_id=${scan_ids}
    With recon_id: /create-peakindexing?scan_id={scan_id}&recon_id={recon_id}
    With wirerecon_id: /create-peakindexing?scan_id={scan_id}&wirerecon_id={wirerecon_id}
    With peakindex_id: /create-peakindexing?scan_id={scan_id}&peakindex_id={peakindex_id}
    With both recon_id and peakindex_id: /create-peakindexing?scan_id={scan_id}&recon_id={recon_id}&peakindex_id={peakindex_id}
    """
    if not href:
        raise PreventUpdate

    parsed_url = urllib.parse.urlparse(href)
    query_params = urllib.parse.parse_qs(parsed_url.query)
    
    scan_id = query_params.get('scan_id', [None])[0]
    root_path = DEFAULT_VARIABLES["root_path"]

    recon_id = query_params.get('recon_id', [None])[0]
    wirerecon_id = query_params.get('wirerecon_id', [None])[0]
    peakindex_id = query_params.get('peakindex_id', [None])[0]
    
    if scan_id:
        with Session(db_utils.ENGINE) as session:
            # Get next peakindex_id
            next_peakindex_id = db_utils.get_next_id(session, db_schema.PeakIndex)                                
            # Store next_peakindex_id and update title
            set_props('next-peakindex-id', {'value': next_peakindex_id})
            set_props('peakindex-title', {'children': f"New peak indexing {next_peakindex_id}"})
            
            try:
                scan_id = int(scan_id)
                # Convert to int if not None
                if recon_id:
                    try:
                        recon_id = int(recon_id)
                    except ValueError:
                        recon_id = None
                if wirerecon_id:
                    try:
                        wirerecon_id = int(wirerecon_id)
                    except ValueError:
                        wirerecon_id = None

                # Query metadata and scan data
                metadata_data = session.query(db_schema.Metadata).filter(
                    db_schema.Metadata.scanNumber == scan_id
                ).first()
                
                # scan_data = session.query(db_schema.Scan).filter(
                #     db_schema.Scan.scanNumber == scan_id
                # ).all()

                if metadata_data:
                    
                    # Determine output folder format based on if reconstruction ID
                    outputFolder = PEAKINDEX_DEFAULTS["outputFolder"]
                    if recon_id or wirerecon_id:
                        outputFolder = outputFolder.replace("index_%d","rec_%d/index_%d") #"analysis/scan_%d/rec_%d/index_%d"
                    
                    # Format output folder with scan number and IDs
                    try:
                        if wirerecon_id:
                            outputFolder = outputFolder % (scan_id, wirerecon_id, next_peakindex_id)
                        elif recon_id:
                            outputFolder = outputFolder % (scan_id, recon_id, next_peakindex_id)
                        else:
                            outputFolder = outputFolder % (scan_id, next_peakindex_id)
                    except:
                        # If formatting fails, use the original string
                        pass
                    
                    # If peakindex_id is provided, load existing peakindex data
                    if peakindex_id:
                        try:
                            peakindex_id = int(peakindex_id)
                            peakindex_data = session.query(db_schema.PeakIndex).filter(
                                db_schema.PeakIndex.peakindex_id == peakindex_id
                            ).first()
                            
                            if peakindex_data:
                                # Use existing peakindex data as the base
                                peakindex_defaults = peakindex_data
                                
                                # Update only the necessary fields
                                # peakindex_defaults.scanNumber = scan_id
                                peakindex_defaults.author = DEFAULT_VARIABLES['author']
                                peakindex_defaults.notes = DEFAULT_VARIABLES['notes']
                                # peakindex_defaults.recon_id = recon_id
                                # peakindex_defaults.wirerecon_id = wirerecon_id
                                peakindex_defaults.outputFolder = outputFolder
                                
                                # Convert file paths to relative paths
                                peakindex_defaults.geoFile = remove_root_path_prefix(peakindex_data.geoFile, root_path)
                                peakindex_defaults.crystFile = remove_root_path_prefix(peakindex_data.crystFile, root_path)
                            else:
                                # Show warning if peakindex not found
                                set_props("alert-scan-loaded", {
                                    'is_open': True, 
                                    'children': f'Peak indexing {peakindex_id} not found in database',
                                    'color': 'warning'
                                })
                                raise ValueError("PeakIndex not found")
                                
                        except (ValueError, Exception):
                            # If peakindex_id is not valid or not found, create defaults
                            peakindex_id = None
                    
                    # Create defaults if no peakindex_id or if loading failed
                    if not peakindex_id:
                        # Create a PeakIndex object with populated defaults from metadata/scan
                        peakindex_defaults = db_schema.PeakIndex(
                            scanNumber = scan_id,
                            
                            # User text
                            author = DEFAULT_VARIABLES['author'],
                            notes = DEFAULT_VARIABLES['notes'],
                            
                            # Recon ID
                            recon_id = recon_id,
                            wirerecon_id = wirerecon_id,
                            
                            # Energy-related fields from source
                            indexKeVmaxCalc=metadata_data.source_energy or PEAKINDEX_DEFAULTS["indexKeVmaxCalc"],
                            indexKeVmaxTest=metadata_data.source_energy or PEAKINDEX_DEFAULTS["indexKeVmaxTest"],
                            energyUnit=metadata_data.source_energy_unit or PEAKINDEX_DEFAULTS["energyUnit"],
                            
                            # # Scan point range from scan data
                            # scanPointStart=PEAKINDEX_DEFAULTS["scanPointStart"],
                            # scanPointEnd=PEAKINDEX_DEFAULTS["scanPointEnd"], # Probably needs logic to determine which dim is the scan dim
                            # Scan points and depth range
                            scanPoints=PEAKINDEX_DEFAULTS["scanPoints"],
                            depthRange=PEAKINDEX_DEFAULTS["depthRange"],
                            
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
                            # peaksearchPath=PEAKINDEX_DEFAULTS["peaksearchPath"],
                            # p2qPath=PEAKINDEX_DEFAULTS["p2qPath"],
                            # indexingPath=PEAKINDEX_DEFAULTS["indexingPath"],
                            outputFolder=outputFolder,#PEAKINDEX_DEFAULTS["outputFolder"],
                            geoFile=PEAKINDEX_DEFAULTS["geoFile"],
                            crystFile=PEAKINDEX_DEFAULTS["crystFile"],
                            depth=PEAKINDEX_DEFAULTS["depth"],
                            beamline=PEAKINDEX_DEFAULTS["beamline"]
                        )
                    
                    # Add root_path from DEFAULT_VARIABLES
                    peakindex_defaults.root_path = root_path
                    # Retrieve data_path and filenamePrefix from catalog data
                    catalog_data = get_catalog_data(session, scan_id, root_path, CATALOG_DEFAULTS)
                    
                    # If processing reconstruction data, use the reconstruction output folder as data path
                    if wirerecon_id:
                        wirerecon_data = session.query(db_schema.WireRecon).filter(
                            db_schema.WireRecon.wirerecon_id == wirerecon_id
                        ).first()
                        if wirerecon_data.outputFolder:
                            # Use the wire reconstruction output folder as the data path
                            peakindex_defaults.data_path = remove_root_path_prefix(wirerecon_data.outputFolder, root_path)
                        else:
                            peakindex_defaults.data_path = catalog_data["data_path"]
                    elif recon_id:
                        recon_data = session.query(db_schema.Recon).filter(
                            db_schema.Recon.recon_id == recon_id
                        ).first()
                        if recon_data.file_output:
                            # Use the reconstruction output folder as the data path
                            peakindex_defaults.data_path = remove_root_path_prefix(recon_data.file_output, root_path)
                        else:
                            peakindex_defaults.data_path = catalog_data["data_path"]
                    else:
                        peakindex_defaults.data_path = catalog_data["data_path"]
                    
                    peakindex_defaults.filenamePrefix = catalog_data["filenamePrefix"]
                    
                    # Populate the form with the defaults
                    set_peakindex_form_props(peakindex_defaults)
                    
                    # Show success message
                    set_props("alert-scan-loaded", {
                        'is_open': True, 
                        'children': f'Scan {scan_id} data loaded successfully. Scan Number: {metadata_data.scanNumber}, Energy: {metadata_data.source_energy} {metadata_data.source_energy_unit}',
                        'color': 'success'
                    })
                else:
                    # Show error if scan not found
                    set_props("alert-scan-loaded", {
                        'is_open': True, 
                        'children': f'Scan {scan_id} not found in database',
                        'color': 'warning'
                    })
                        
            except Exception:
                try:
                    # This section handles multiple/pooled scan numbers
                    scan_numbers = str(scan_id).replace('$','').split(',')
                    
                    # Handle pooled reconstruction IDs
                    wirerecon_ids = []
                    recon_ids = []
                    
                    # Parse wirerecon_id parameter if present
                    if wirerecon_id:
                        wirerecon_id_str = str(wirerecon_id).replace('$','')
                        wirerecon_ids = wirerecon_id_str.split(',')
                        # Convert to int or None
                        wirerecon_ids = [int(wid) if wid and wid.lower() != 'none' else None for wid in wirerecon_ids]
                    
                    # Parse recon_id parameter if present
                    if recon_id:
                        recon_id_str = str(recon_id).replace('$','')
                        recon_ids = recon_id_str.split(',')
                        # Convert to int or None
                        recon_ids = [int(rid) if rid and rid.lower() != 'none' else None for rid in recon_ids]
                    
                    # Validate that lists have matching lengths
                    if wirerecon_ids and len(wirerecon_ids) != len(scan_numbers):
                        raise ValueError(f"Mismatch: {len(scan_numbers)} scan IDs but {len(wirerecon_ids)} wirerecon IDs")
                    if recon_ids and len(recon_ids) != len(scan_numbers):
                        raise ValueError(f"Mismatch: {len(scan_numbers)} scan IDs but {len(recon_ids)} recon IDs")
                    
                    # If no reconstruction IDs provided, fill with None
                    if not wirerecon_ids:
                        wirerecon_ids = [None] * len(scan_numbers)
                    if not recon_ids:
                        recon_ids = [None] * len(scan_numbers)

                    # Collect data paths and filename prefixes for each scan
                    data_paths = []
                    filename_prefixes = []
                    for i, scan_num in enumerate(scan_numbers):
                        try:
                            catalog_data = get_catalog_data(session, int(scan_num), root_path, CATALOG_DEFAULTS)
                            if catalog_data:
                                # Get the corresponding reconstruction ID for this scan
                                current_wirerecon_id = wirerecon_ids[i]
                                current_recon_id = recon_ids[i]
                                
                                # For reconstruction data, get the reconstruction output folder
                                if current_wirerecon_id:
                                    wirerecon_data = session.query(db_schema.WireRecon).filter(
                                        db_schema.WireRecon.wirerecon_id == current_wirerecon_id
                                    ).first()
                                    if wirerecon_data.outputFolder:
                                        data_paths.append(remove_root_path_prefix(wirerecon_data.outputFolder, root_path))
                                    else:
                                        data_paths.append(catalog_data.get('data_path', ''))
                                elif current_recon_id:
                                    recon_data = session.query(db_schema.Recon).filter(
                                        db_schema.Recon.recon_id == current_recon_id
                                    ).first()
                                    if recon_data.file_output:
                                        data_paths.append(remove_root_path_prefix(recon_data.file_output, root_path))
                                    else:
                                        data_paths.append(catalog_data.get('data_path', ''))
                                else:
                                    # No reconstruction, use catalog data path
                                    data_paths.append(catalog_data.get('data_path', ''))
                                
                                # Collect filename prefix
                                filename_prefixes.append(catalog_data.get('filenamePrefix', ''))
                        except:
                            # If error, add empty strings to maintain alignment
                            data_paths.append("")
                            filename_prefixes.append("")

                    # Determine output folder format based on if reconstruction ID
                    outputFolder = PEAKINDEX_DEFAULTS["outputFolder"]
                    if recon_id or wirerecon_id:
                        outputFolder = outputFolder.replace("index_%d","rec_%d/index_%d") #"analysis/scan_%d/rec_%d/index_%d"
                    
                    # For pooled scans, create a joined set of output folders
                    output_folders = []
                    for i, scan_num in enumerate(scan_numbers):
                        try:
                            current_wirerecon_id = wirerecon_ids[i]
                            current_recon_id = recon_ids[i]
                            
                            if current_wirerecon_id:
                                formatted_folder = outputFolder % (int(scan_num), current_wirerecon_id, next_peakindex_id)
                            elif current_recon_id:
                                formatted_folder = outputFolder % (int(scan_num), current_recon_id, next_peakindex_id)
                            else:
                                formatted_folder = outputFolder % (int(scan_num), next_peakindex_id)
                            output_folders.append(formatted_folder)
                        except:
                            # If formatting fails, use the original string
                            output_folders.append(outputFolder)
                        next_peakindex_id += 1
                    
                    # Join all output folders with semicolon separator
                    pooled_output_folders = "; ".join(output_folders)

                    # Format reconstruction IDs for display (semicolon-separated, with 'none' for None values)
                    display_wirerecon_ids = "; ".join([str(wid) if wid else 'none' for wid in wirerecon_ids])
                    display_recon_ids = "; ".join([str(rid) if rid else 'none' for rid in recon_ids])
                    
                    peakindex_defaults = db_schema.PeakIndex(
                        scanNumber = str(scan_id).replace('$','').replace(',','; '),
                        
                        # User text
                        author = DEFAULT_VARIABLES['author'],
                        notes = DEFAULT_VARIABLES['notes'],
                        
                        # Recon ID - display as semicolon-separated list
                        recon_id = display_recon_ids if any(recon_ids) else None,
                        wirerecon_id = display_wirerecon_ids if any(wirerecon_ids) else None,
                        
                        # Energy-related fields - use defaults for pooled scans
                        indexKeVmaxCalc=PEAKINDEX_DEFAULTS["indexKeVmaxCalc"],
                        indexKeVmaxTest=PEAKINDEX_DEFAULTS["indexKeVmaxTest"],
                        energyUnit=PEAKINDEX_DEFAULTS["energyUnit"],
                        
                        # Scan points and depth range
                        scanPoints=PEAKINDEX_DEFAULTS["scanPoints"],
                        depthRange=PEAKINDEX_DEFAULTS["depthRange"],
                        
                        # Default processing parameters
                        threshold=PEAKINDEX_DEFAULTS["threshold"],
                        thresholdRatio=PEAKINDEX_DEFAULTS["thresholdRatio"],
                        maxRfactor=PEAKINDEX_DEFAULTS["maxRfactor"],
                        boxsize=PEAKINDEX_DEFAULTS["boxsize"],
                        max_number=PEAKINDEX_DEFAULTS["max_peaks"],
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
                        outputFolder=pooled_output_folders,
                        geoFile=PEAKINDEX_DEFAULTS["geoFile"],
                        crystFile=PEAKINDEX_DEFAULTS["crystFile"],
                        depth=PEAKINDEX_DEFAULTS["depth"],
                        beamline=PEAKINDEX_DEFAULTS["beamline"]
                    )
                    
                    # Set root_path and join data_paths and filename_prefixes with semicolons
                    peakindex_defaults.root_path = root_path
                    peakindex_defaults.data_path = "; ".join(data_paths)
                    peakindex_defaults.filenamePrefix = "; ".join(filename_prefixes) if filename_prefixes else ""
                    
                    # Populate the form with the defaults
                    set_peakindex_form_props(peakindex_defaults)
                    
                except Exception as e:
                    set_props("alert-scan-loaded", {
                        'is_open': True, 
                        'children': f'Error loading scan data: {str(e)}',
                        'color': 'danger'
                    })
