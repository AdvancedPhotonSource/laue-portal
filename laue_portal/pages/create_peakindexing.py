import datetime
import glob
import logging
import os
import urllib.parse
import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, set_props, State
from dash.exceptions import PreventUpdate
from sqlalchemy.orm import Session
import laue_portal.database.db_utils as db_utils
import laue_portal.database.db_schema as db_schema
import laue_portal.components.navbar as navbar
from laue_portal.database.db_utils import get_catalog_data, remove_root_path_prefix, parse_parameter
from laue_portal.components.peakindex_form import peakindex_form, set_peakindex_form_props
from laue_portal.processing.redis_utils import enqueue_peakindexing, STATUS_REVERSE_MAPPING
from laue_portal.config import DEFAULT_VARIABLES
from srange import srange
import laue_portal.database.session_utils as session_utils
import re
from difflib import SequenceMatcher
from itertools import combinations

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
    # "peakProgram": "peaksearch",
    "threshold": "", #250
    "thresholdRatio": "",
    "maxRfactor": 0.5, #0.5
    "boxsize": 18, #18
    "max_number": 300,
    "min_separation": 20, #40
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
    "indexKeVmaxCalc": 17.2, #17.2
    "indexKeVmaxTest": 35.0, #30.0
    "indexAngleTolerance": 0.1, #0.1
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
        dbc.Row(
                [
                    dbc.Col(
                        html.H3(id="peakindex-title", children="New Peak Indexing"),
                        width="auto",   # shrink to content
                    ),
                    dbc.Col(
                        dbc.Button(
                            "Set from ...",
                            id="upload-peakindexing-config",
                            color="secondary",
                            style={"minWidth": 150, "maxWidth": "150px", "width": "100%"},
                        ),
                        width="auto",
                        className="ms-3",  # small gap from title
                    ),
                    dbc.Col(
                        dbc.Button(
                            "Validate",
                            id="validate-btn",
                            color="secondary",
                            style={"minWidth": 150, "maxWidth": "150px", "width": "100%"},
                        ),
                        width="auto",
                        className="ms-3",  # small gap from title
                    ),
                    dbc.Col(
                        dbc.Button(
                            "Submit",
                            id="submit_peakindexing",
                            color="primary",
                            style={"minWidth": 150, "maxWidth": "150px", "width": "100%"},
                        ),
                        width="auto",
                        className="ms-2",
                    ),
                ],
                className="g-2",     # gutter between cols
                justify="center",     # CENTER horizontally
                align="center",       # CENTER vertically
            ),
        html.Hr(),
    
        dbc.Row([
                dbc.Col(
                    dbc.Alert([
                                html.H4("Validate status: Warning !", className="alert-heading"),
                                html.Hr(),
                                html.P("Press button Validate! or Some parameter (which one) seems to be too big! Better check it! ", className="mb-0"),
                            ],
                            color="warning",  # <- set the color here
                    ),
                ),
                ],
                className="g-0",            # g-0 removes row gutters
                align="center",
        ),
        ######## Below are other examples of the Alert 
        # this is just example  but it should be changable to something like that if Error
        dbc.Row([
                dbc.Col(
                    dbc.Alert([
                                html.H4("Validate status: Error !", className="alert-heading"),
                                html.Hr(),
                                html.P("Check your file inputs! or check Peak Search parameters! or Check Index Parameters!", className="mb-0"),
                            ],
                            color="danger",  # <- set the color here
                    ),
                ),
        
                ],
                className="g-0",            # g-0 removes row gutters
                align="center",
        ),
        # this is just example  but it should be changable to something like that if Success
        dbc.Row([
                dbc.Col(
                    dbc.Alert([
                                html.H4("Validate status: Success !", className="alert-heading"),
                                html.Hr(),
                                html.P("You can Submit!", className="mb-0"),
                            ],
                            color="success",  # <- set the color here
                    ),
                 ),
                ],
                className="g-0",            # g-0 removes row gutters
                align="center",
        ),
        
        html.Hr(),
        dbc.Row([
                dbc.Col(
                    dbc.InputGroup([
                            dbc.InputGroupText("Author"),
                            dbc.Input(
                                type="text",
                                id="author",
                                placeholder="Required! Enter author or Tag for the reconstruction",
                            ),
                        ],
                        className="w-100 mb-0",
                    ),
                    md=12, xs=12,   # full row on small, wide on medium+
                    width = "auto",
                    style={"minWidth": "300px"},
                ),
            ],
            justify="center",
            className="mb-3",
            align="center",
        ),
        peakindex_form,
        dcc.Store(id="peakindex-data-loaded-trigger"),
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
    Input('submit_peakindexing', 'n_clicks'),
    
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
    
    prevent_initial_call=True,
)
def submit_parameters(n,
    scanNumber,
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
    
):
    # TODO: Input validation and response

    """
    Submit parameters for peak indexing job(s).
    Handles both single scan and pooled scan submissions.
    """
    # Parse data_path first to get the number of inputs
    data_path_list = parse_parameter(data_path)
    num_inputs = len(data_path_list)
    
    # Parse all other parameters with num_inputs
    try:
        scanNumber_list = parse_parameter(scanNumber, num_inputs)
        author_list = parse_parameter(author, num_inputs)
        notes_list = parse_parameter(notes, num_inputs)
        recon_id_list = parse_parameter(recon_id, num_inputs)
        wirerecon_id_list = parse_parameter(wirerecon_id, num_inputs)
        threshold_list = parse_parameter(threshold, num_inputs)
        thresholdRatio_list = parse_parameter(thresholdRatio, num_inputs)
        maxRfactor_list = parse_parameter(maxRfactor, num_inputs)
        boxsize_list = parse_parameter(boxsize, num_inputs)
        max_number_list = parse_parameter(max_number, num_inputs)
        min_separation_list = parse_parameter(min_separation, num_inputs)
        peakShape_list = parse_parameter(peakShape, num_inputs)
        scanPoints_list = parse_parameter(scanPoints, num_inputs)
        depthRange_list = parse_parameter(depthRange, num_inputs)
        detectorCropX1_list = parse_parameter(detectorCropX1, num_inputs)
        detectorCropX2_list = parse_parameter(detectorCropX2, num_inputs)
        detectorCropY1_list = parse_parameter(detectorCropY1, num_inputs)
        detectorCropY2_list = parse_parameter(detectorCropY2, num_inputs)
        min_size_list = parse_parameter(min_size, num_inputs)
        max_peaks_list = parse_parameter(max_peaks, num_inputs)
        smooth_list = parse_parameter(smooth, num_inputs)
        maskFile_list = parse_parameter(maskFile, num_inputs)
        indexKeVmaxCalc_list = parse_parameter(indexKeVmaxCalc, num_inputs)
        indexKeVmaxTest_list = parse_parameter(indexKeVmaxTest, num_inputs)
        indexAngleTolerance_list = parse_parameter(indexAngleTolerance, num_inputs)
        indexHKL_list = parse_parameter(indexHKL, num_inputs)
        indexCone_list = parse_parameter(indexCone, num_inputs)
        energyUnit_list = parse_parameter(energyUnit, num_inputs)
        exposureUnit_list = parse_parameter(exposureUnit, num_inputs)
        cosmicFilter_list = parse_parameter(cosmicFilter, num_inputs)
        recipLatticeUnit_list = parse_parameter(recipLatticeUnit, num_inputs)
        latticeParametersUnit_list = parse_parameter(latticeParametersUnit, num_inputs)
        data_path_list = parse_parameter(data_path, num_inputs)
        filenamePrefix_list = parse_parameter(filenamePrefix, num_inputs)
        outputFolder_list = parse_parameter(outputFolder, num_inputs)
        geoFile_list = parse_parameter(geometry_file, num_inputs)
        crystFile_list = parse_parameter(crystal_file, num_inputs)
        depth_list = parse_parameter(depth, num_inputs)
        beamline_list = parse_parameter(beamline, num_inputs)
    except ValueError as e:
        # Error: mismatched lengths
        set_props("alert-submit", {
            'is_open': True, 
            'children': str(e),
            'color': 'danger'
        })
        return
    
    root_path = DEFAULT_VARIABLES["root_path"]
    
    peakindexes_to_enqueue = []

    # First loop: Create all database entries for each listed scanNumber
    with Session(session_utils.get_engine()) as session:
        try:
            for i in range(num_inputs):
                # Extract values for this scan
                current_scanNumber = scanNumber_list[i]
                current_recon_id = recon_id_list[i]
                current_wirerecon_id = wirerecon_id_list[i]
                current_output_folder = outputFolder_list[i]
                current_geo_file = geoFile_list[i]
                current_crystal_file = crystFile_list[i]
                current_scanPoints = scanPoints_list[i]
                current_depthRange = depthRange_list[i]

                # Convert relative paths to full paths
                full_geometry_file = os.path.join(root_path, current_geo_file.lstrip('/'))
                full_crystal_file = os.path.join(root_path, current_crystal_file.lstrip('/'))

                next_peakindex_id = db_utils.get_next_id(session, db_schema.PeakIndex)
                # Now that we have the ID, format the output folder path
                try:
                    if '%d' in current_output_folder:
                        if current_wirerecon_id:
                            formatted_output_folder = current_output_folder % (current_scanNumber, current_wirerecon_id, next_peakindex_id)
                        elif current_recon_id:
                            formatted_output_folder = current_output_folder % (current_scanNumber, current_recon_id, next_peakindex_id)
                        else:
                            formatted_output_folder = current_output_folder % (current_scanNumber, next_peakindex_id)
                    else:
                        formatted_output_folder = current_output_folder
                except TypeError:
                    formatted_output_folder = current_output_folder # Fallback if formatting fails
                
                full_output_folder = os.path.join(root_path, formatted_output_folder.lstrip('/'))
                
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

                session.add(job)
                session.flush()  # Get job_id without committing
                job_id = job.job_id
                
                # Create subjobs for parallel processing
                # Parse scanPoints using srange
                scanPoints_srange = srange(current_scanPoints)
                scanPoint_nums = scanPoints_srange.list()
                
                # Parse depthRange if provided using srange
                if current_depthRange and current_depthRange.strip():
                    depthRange_srange = srange(current_depthRange)
                    depthRange_nums = depthRange_srange.list()
                else:
                    depthRange_srange = srange('')
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
        
                # Extract HKL values from indexHKL parameter
                current_indexHKL = str(indexHKL_list[i])
                
                # Get filefolder and filenamePrefix
                current_data_path = data_path_list[i]
                current_filename_prefix_str = filenamePrefix_list[i]
                current_filename_prefix = [s.strip() for s in current_filename_prefix_str.split(',')] if current_filename_prefix_str else []
                # Build full path
                current_full_data_path=os.path.join(root_path, current_data_path.lstrip('/'))
                
                peakindex = db_schema.PeakIndex(
                    scanNumber = current_scanNumber,
                    job_id = job_id,
                    author = author_list[i],
                    notes = notes_list[i],
                    recon_id = current_recon_id,
                    wirerecon_id = current_wirerecon_id,
                    filefolder=current_full_data_path,
                    filenamePrefix=current_filename_prefix,

                    # peakProgram=peakProgram,
                    threshold=threshold_list[i],
                    thresholdRatio=thresholdRatio_list[i],
                    maxRfactor=maxRfactor_list[i],
                    boxsize=boxsize_list[i],
                    max_number=max_number_list[i],
                    min_separation=min_separation_list[i],
                    peakShape=peakShape_list[i],
                    # scanPointStart=scanPointStart,
                    # scanPointEnd=scanPointEnd,
                    # depthRangeStart=depthRangeStart,
                    # depthRangeEnd=depthRangeEnd,
                    scanPoints=current_scanPoints,
                    scanPointslen=scanPoints_srange.len(),
                    depthRange=current_depthRange,
                    depthRangelen=depthRange_srange.len(),
                    detectorCropX1=detectorCropX1_list[i],
                    detectorCropX2=detectorCropX2_list[i],
                    detectorCropY1=detectorCropY1_list[i],
                    detectorCropY2=detectorCropY2_list[i],
                    min_size=min_size_list[i],
                    max_peaks=max_peaks_list[i],
                    smooth=smooth_list[i],
                    maskFile=maskFile_list[i],
                    indexKeVmaxCalc=indexKeVmaxCalc_list[i],
                    indexKeVmaxTest=indexKeVmaxTest_list[i],
                    indexAngleTolerance=indexAngleTolerance_list[i],
                    indexH=int(current_indexHKL[0]),
                    indexK=int(current_indexHKL[1]),
                    indexL=int(current_indexHKL[2]),
                    indexCone=indexCone_list[i],
                    energyUnit=energyUnit_list[i],
                    exposureUnit=exposureUnit_list[i],
                    cosmicFilter=cosmicFilter_list[i],
                    recipLatticeUnit=recipLatticeUnit_list[i],
                    latticeParametersUnit=latticeParametersUnit_list[i],
                    # peaksearchPath=peaksearchPath,
                    # p2qPath=p2qPath,
                    # indexingPath=indexingPath,
                    outputFolder=full_output_folder,  # Store full path in database
                    geoFile=full_geometry_file,  # Store full path in database
                    crystFile=full_crystal_file,  # Store full path in database
                    depth=depth_list[i],
                    beamline=beamline_list[i],
                )
                session.add(peakindex)
                peakindexes_to_enqueue.append({
                    "job_id": job_id,
                    "scanNumber": current_scanNumber,
                    "filefolder": current_full_data_path,
                    "filenamePrefix": current_filename_prefix,
                    "outputFolder": full_output_folder,
                    "geoFile": full_geometry_file,
                    "crystFile": full_crystal_file,
                    "scanPoints": current_scanPoints,
                    "depthRange": current_depthRange,
                    "boxsize": boxsize_list[i],
                    "maxRfactor": maxRfactor_list[i],
                    "min_size": min_size_list[i],
                    "min_separation": min_separation_list[i],
                    "threshold": threshold_list[i],
                    "peakShape": peakShape_list[i],
                    "max_peaks": max_peaks_list[i],
                    "smooth": smooth_list[i],
                    "indexKeVmaxCalc": indexKeVmaxCalc_list[i],
                    "indexKeVmaxTest": indexKeVmaxTest_list[i],
                    "indexAngleTolerance": indexAngleTolerance_list[i],
                    "indexCone": indexCone_list[i],
                    "indexH": int(current_indexHKL[0]),
                    "indexK": int(current_indexHKL[1]),
                    "indexL": int(current_indexHKL[2]),
                })

            session.commit()
            set_props("alert-submit", {'is_open': True, 
                                        'children': 'Entries Added to Database',
                                        'color': 'success'})
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to create database entries: {e}")
            set_props("alert-submit", {'is_open': True,
                                       'children': f'Failed to create database entries: {str(e)}',
                                       'color': 'danger'})
            return

    # Second loop: Enqueue jobs to Redis
    for i, spec in enumerate(peakindexes_to_enqueue):
        try:
            # Extract values for this scan
            full_data_path = spec["filefolder"]
            current_filename_prefix = spec["filenamePrefix"]
            
            scanPoints_srange = srange(spec["scanPoints"])
            scanPoint_nums = scanPoints_srange.list()

            if spec["depthRange"] and str(spec["depthRange"]).strip():
                depthRange_srange = srange(spec["depthRange"])
                depthRange_nums = depthRange_srange.list()
            else:
                depthRange_nums = [None]

            # Prepare lists of input and output files for all subjobs
            input_files = []
            
            for current_filename_prefix_i in current_filename_prefix:
                for scanPoint_num in scanPoint_nums:
                    for depthRange_num in depthRange_nums:
                        # Apply %d formatting with scanPoint_num if prefix contains %d placeholder
                        file_str = current_filename_prefix_i % scanPoint_num if '%d' in current_filename_prefix_i else current_filename_prefix_i
                        
                        # Add depth index if processing reconstruction data
                        if depthRange_num is not None:
                            file_str += f"_{depthRange_num}"
                        
                        input_file_pattern = os.path.join(full_data_path, file_str)
                        
                        # Use glob to find matching files
                        matched_files = glob.glob(input_file_pattern)
                        
                        if not matched_files:
                            raise ValueError(f"No files found matching pattern: {input_file_pattern}")
                        
                        input_files.extend(matched_files)
            
            # Create output directory list matching input_files length
            output_dirs = [spec["outputFolder"] for _ in input_files]
            
            # Enqueue the batch job with all files
            rq_job_id = enqueue_peakindexing(
                job_id=spec["job_id"],
                input_files=input_files,
                output_files=output_dirs,
                geometry_file=spec["geoFile"],
                crystal_file=spec["crystFile"],
                boxsize=spec["boxsize"],
                max_rfactor=spec["maxRfactor"],
                min_size=spec["min_size"],
                min_separation=spec["min_separation"],
                threshold=spec["threshold"],
                peak_shape=spec["peakShape"],
                max_peaks=spec["max_peaks"],
                smooth=spec["smooth"],
                index_kev_max_calc=spec["indexKeVmaxCalc"],
                index_kev_max_test=spec["indexKeVmaxTest"],
                index_angle_tolerance=spec["indexAngleTolerance"],
                index_cone=spec["indexCone"],
                index_h=spec["indexH"],
                index_k=spec["indexK"],
                index_l=spec["indexL"]
            )
            
            logger.info(f"Peakindexing batch job {spec['job_id']} enqueued with RQ ID: {rq_job_id} for {len(input_files)} files")
            
            set_props("alert-submit", {'is_open': True, 
                                        'children': f'Job {spec["job_id"]} submitted to queue with {len(input_files)} file(s)',
                                        'color': 'info'})
        except Exception as e:
            # Provide more context to help diagnose format issues and input parsing
            logger.error(
                f"Failed to enqueue job {spec['job_id']}: {e}. "
                f"filenamePrefix='{current_filename_prefix_str}', "
                f"parsed prefixes={current_filename_prefix}, "
                f"scanPoints='{spec['scanPoints']}', depthRange='{spec['depthRange']}', data_path='{current_data_path}'"
            )
            set_props("alert-submit", {'is_open': True, 
                                        'children': f'Failed to queue job {spec["job_id"]}: {str(e)}. '
                                                    f'filenamePrefix={current_filename_prefix_str}, '
                                                    f'scanPoints={spec["scanPoints"]}, depthRange={spec["depthRange"]}',
                                        'color': 'danger'})


@dash.callback(
    Output('peakindex-filename-templates', 'children', allow_duplicate=True),
    Input('peakindex-check-filenames-btn', 'n_clicks'),
    Input('peakindex-update-path-fields-btn', 'n_clicks'),
    Input('peakindex-data-loaded-trigger', 'data'),
    # Files
    State('data_path', 'value'),
    prevent_initial_call=True,
)
def check_filenames(n_check, n_update, data_loaded_trigger,
    # Files
    data_path,
    num_indices=2,
):
    """
    Scan directory and suggest common filename patterns.
    Replaces numeric sequences with %d to find templates and shows index ranges.
    
    For peak indexing, this captures TWO rightmost numbers:
    - First number: scanPoint (e.g., 7 in file_7_150.h5)
    - Second number: depthRange (e.g., 150 in file_7_150.h5)
    
    Parameters:
    -----------
    n : int
        Number of clicks (callback trigger)
    data_path : str
        Path to the data directory
    num_indices : int, optional
        Number of rightmost numeric indices to capture (default=2 for peak indexing)
    """
    
    if not data_path:
        return [html.Option(value="", label="No data path provided")]
    
    # Parse data_path first to get the number of inputs
    data_path_list = parse_parameter(data_path)
    num_inputs = len(data_path_list)
    
    root_path = DEFAULT_VARIABLES["root_path"]
    
    # Dictionary to store pattern -> list of indices
    pattern_files = {}

    for i in range(num_inputs):
        # Get filefolder
        current_data_path = data_path_list[i]

        # Build full path
        current_full_data_path=os.path.join(root_path, current_data_path.lstrip('/'))
        
        # Check if directory exists
        if not os.path.exists(current_full_data_path):
            logger.warning(f"Directory does not exist: {current_full_data_path}")
            continue
        
        # List all files in directory
        try:
            files = [f for f in os.listdir(current_full_data_path) if os.path.isfile(os.path.join(current_full_data_path, f))]
        except Exception as e:
            logger.error(f"Error reading directory {current_full_data_path}: {e}")
            continue
        
        # Extract patterns and indices
        for filename in files:
            base_name, extension = os.path.splitext(filename)
            
            # Build regex pattern to capture N rightmost numbers
            # For num_indices=1: (\d+)(?!.*\d)
            # For num_indices=2: (\d+)_(\d+)(?!.*\d)
            if num_indices == 1:
                regex_pattern = r'(\d+)(?!.*\d)'
            else:
                # Capture N groups of digits separated by underscores from the right
                regex_pattern = r'_'.join([r'(\d+)'] * num_indices) + r'(?!.*\d)'
            
            match = re.search(regex_pattern, base_name)
            
            if match:
                # Extract all captured groups as integers
                indices = [int(match.group(i)) for i in range(1, num_indices + 1)]
                
                # Create pattern with appropriate number of %d placeholders
                pattern_placeholder = '_'.join(['%d'] * num_indices)
                pattern = base_name[:match.start()] + pattern_placeholder + base_name[match.end():] + extension
                
                pattern_files.setdefault(pattern, []).append(indices)
            else:
                # No numeric pattern found
                pattern_files.setdefault(filename, []).append([])
    
    if not pattern_files:
        return [html.Option(value="", label="No files found in specified path(s)")]
    
    # Sort by file count and create options for top 10 patterns
    sorted_patterns = sorted(pattern_files.items(), key=lambda x: len(x[1]), reverse=True)[:10]
    pattern_options = []
    
    for pattern, indices_list in sorted_patterns:
        if indices_list and indices_list[0]:
            if num_indices == 1:
                # Single index: show simple range
                label = f"{pattern} (files {str(srange(sorted(set(idx[0] for idx in indices_list))))})"
            else:
                # Multiple indices: show ranges for each dimension
                range_labels = []
                dim_names = ['scanPoints', 'depths'] if num_indices == 2 else [f"dim{i+1}" for i in range(num_indices)]
                
                for dim in range(num_indices):
                    dim_values = sorted(set(idx[dim] for idx in indices_list if len(idx) > dim))
                    if dim_values:
                        range_labels.append(f"{dim_names[dim]}: {str(srange(dim_values))}")
                
                if range_labels:
                    label = f"{pattern} ({', '.join(range_labels)})"
                else:
                    label = f"{pattern} ({len(indices_list)} file{'s' if len(indices_list) != 1 else ''})"
        else:
            label = f"{pattern} ({len(indices_list)} file{'s' if len(indices_list) != 1 else ''})"
        pattern_options.append(html.Option(value=pattern, label=label))
    
    # Generate combined wildcard patterns for similar patterns
    if len(sorted_patterns) > 1:
        seen_wildcards = set()
        
        for (pattern1, indices1), (pattern2, indices2) in combinations(sorted_patterns, 2):
            # Find matching and differing sections
            matcher = SequenceMatcher(None, pattern1, pattern2)
            wildcard_parts = []
            last_pos = 0
            
            for match_start1, match_start2, match_length in matcher.get_matching_blocks():
                # Handle the gap before this match (differences)
                if match_start1 > last_pos:
                    diff1 = pattern1[last_pos:match_start1]
                    diff2 = pattern2[last_pos:match_start2]
                    
                    # Skip if differences contain %d
                    if '%d' in diff1 or '%d' in diff2:
                        break
                    
                    wildcard_parts.append('*')
                
                # Add the matching section
                if match_length > 0:
                    wildcard_parts.append(pattern1[match_start1:match_start1 + match_length])
                
                last_pos = match_start1 + match_length
            else:
                # Only create wildcard if pattern contains wildcards and hasn't been seen before
                wildcard_pattern = ''.join(wildcard_parts)
                if '*' in wildcard_pattern and wildcard_pattern not in seen_wildcards:
                    seen_wildcards.add(wildcard_pattern)
                    
                    # Combine indices from both patterns
                    combined_indices = sorted(set(idx[0] for idx in indices1 + indices2 if idx))
                    label = f"{wildcard_pattern} (files {str(srange(combined_indices))})"
                    pattern_options.append(html.Option(value=wildcard_pattern, label=label))
    
    return pattern_options


# @dash.callback(
#     Input('url-create-peakindexing','pathname'),
#     prevent_initial_call=True,
# )
# def get_peakindexings(path):
#     root_path = DEFAULT_VARIABLES["root_path"]
#     if path == '/create-peakindexing':
#         # Create a PeakIndex object with form defaults (not for database insertion)
#         peakindex_form_data = db_schema.PeakIndex(
#             scanNumber=PEAKINDEX_DEFAULTS.get("scanNumber", 0),
            
#             # User text
#             author=DEFAULT_VARIABLES["author"],
#             notes=DEFAULT_VARIABLES["notes"],
            
#             # Processing parameters
#             # peakProgram=PEAKINDEX_DEFAULTS["peakProgram"],
#             threshold=PEAKINDEX_DEFAULTS["threshold"],
#             thresholdRatio=PEAKINDEX_DEFAULTS["thresholdRatio"],
#             maxRfactor=PEAKINDEX_DEFAULTS["maxRfactor"],
#             boxsize=PEAKINDEX_DEFAULTS["boxsize"],
#             max_number=PEAKINDEX_DEFAULTS["max_peaks"],
#             min_separation=PEAKINDEX_DEFAULTS["min_separation"],
#             peakShape=PEAKINDEX_DEFAULTS["peakShape"],
#             # scanPointStart=PEAKINDEX_DEFAULTS["scanPointStart"],
#             # scanPointEnd=PEAKINDEX_DEFAULTS["scanPointEnd"],
#             # depthRangeStart=PEAKINDEX_DEFAULTS.get("depthRangeStart"),
#             # depthRangeEnd=PEAKINDEX_DEFAULTS.get("depthRangeEnd"),
#             scanPoints=PEAKINDEX_DEFAULTS["scanPoints"],
#             scanPointslen=srange(PEAKINDEX_DEFAULTS["scanPoints"]).len(),
#             depthRange=PEAKINDEX_DEFAULTS["depthRange"],
#             depthRangelen=srange(PEAKINDEX_DEFAULTS["depthRange"]).len(),
#             detectorCropX1=PEAKINDEX_DEFAULTS["detectorCropX1"],
#             detectorCropX2=PEAKINDEX_DEFAULTS["detectorCropX2"],
#             detectorCropY1=PEAKINDEX_DEFAULTS["detectorCropY1"],
#             detectorCropY2=PEAKINDEX_DEFAULTS["detectorCropY2"],
#             min_size=PEAKINDEX_DEFAULTS["min_size"],
#             max_peaks=PEAKINDEX_DEFAULTS["max_peaks"],
#             smooth=PEAKINDEX_DEFAULTS["smooth"],
#             maskFile=PEAKINDEX_DEFAULTS["maskFile"],
#             indexKeVmaxCalc=PEAKINDEX_DEFAULTS["indexKeVmaxCalc"],
#             indexKeVmaxTest=PEAKINDEX_DEFAULTS["indexKeVmaxTest"],
#             indexAngleTolerance=PEAKINDEX_DEFAULTS["indexAngleTolerance"],
#             indexH=PEAKINDEX_DEFAULTS["indexH"],
#             indexK=PEAKINDEX_DEFAULTS["indexK"],
#             indexL=PEAKINDEX_DEFAULTS["indexL"],
#             indexCone=PEAKINDEX_DEFAULTS["indexCone"],
#             energyUnit=PEAKINDEX_DEFAULTS["energyUnit"],
#             exposureUnit=PEAKINDEX_DEFAULTS["exposureUnit"],
#             cosmicFilter=PEAKINDEX_DEFAULTS["cosmicFilter"],
#             recipLatticeUnit=PEAKINDEX_DEFAULTS["recipLatticeUnit"],
#             latticeParametersUnit=PEAKINDEX_DEFAULTS["latticeParametersUnit"],
#             # peaksearchPath=PEAKINDEX_DEFAULTS["peaksearchPath"],
#             # p2qPath=PEAKINDEX_DEFAULTS["p2qPath"],
#             # indexingPath=PEAKINDEX_DEFAULTS["indexingPath"],
            
#             # File paths
#             outputFolder=PEAKINDEX_DEFAULTS["outputFolder"],
#             # filefolder=CATALOG_DEFAULTS["filefolder"],
#             geoFile=PEAKINDEX_DEFAULTS["geoFile"],
#             crystFile=PEAKINDEX_DEFAULTS["crystFile"],
            
#             # Other fields
#             depth=PEAKINDEX_DEFAULTS["depth"],
#             beamline=PEAKINDEX_DEFAULTS["beamline"],
#         )
        
#         # Add root_path from DEFAULT_VARIABLES
#         peakindex_form_data.root_path = root_path
#         with Session(session_utils.get_engine()) as session:
#             # Get next peakindex_id
#             next_peakindex_id = db_utils.get_next_id(session, db_schema.PeakIndex)                                
#             # Store next_peakindex_id and update title
#             set_props('next-peakindex-id', {'value': next_peakindex_id})
#             set_props('peakindex-title', {'children': f"New peak indexing {next_peakindex_id}"})
            
#             # Retrieve data_path and filenamePrefix from catalog data
#             catalog_data = get_catalog_data(session, PEAKINDEX_DEFAULTS["scanNumber"], root_path, CATALOG_DEFAULTS)
#         peakindex_form_data.data_path = catalog_data["data_path"]
#         peakindex_form_data.filenamePrefix = catalog_data["filenamePrefix"]
            
#         # Populate the form with the defaults
#         set_peakindex_form_props(peakindex_form_data)
#     else:
#         raise PreventUpdate

@dash.callback(
    Output('peakindex-data-loaded-trigger', 'data'),
    Input('url-create-peakindexing', 'href'),
    prevent_initial_call=True,
)
def load_scan_data_from_url(href):
    """
    Load scan data and optionally existing recon and peakindex data when provided in URL query parameters
    URL format: /create-peakindexing?scan_id={scan_id}
    Pooled URL format: /create-peakindexing?scan_id={scan_ids}
    With recon_id: /create-peakindexing?scan_id={scan_id}&recon_id={recon_id}
    With wirerecon_id: /create-peakindexing?scan_id={scan_id}&wirerecon_id={wirerecon_id}
    With peakindex_id: /create-peakindexing?scan_id={scan_id}&peakindex_id={peakindex_id}
    With both recon_id and peakindex_id: /create-peakindexing?scan_id={scan_id}&recon_id={recon_id}&peakindex_id={peakindex_id}
    """
    if not href:
        raise PreventUpdate

    parsed_url = urllib.parse.urlparse(href)
    query_params = urllib.parse.parse_qs(parsed_url.query)
    
    scan_id_str = query_params.get('scan_id', [None])[0]

    recon_id_str = query_params.get('recon_id', [None])[0]
    wirerecon_id_str = query_params.get('wirerecon_id', [None])[0]
    peakindex_id_str = query_params.get('peakindex_id', [None])[0]

    root_path = DEFAULT_VARIABLES.get("root_path", "")
    
    if scan_id_str:
        with Session(session_utils.get_engine()) as session:
            # # Get next peakindex_id
            # next_peakindex_id = db_utils.get_next_id(session, db_schema.PeakIndex)
            # # Store next_peakindex_id and update title
            # set_props('next-peakindex-id', {'value': next_peakindex_id})
            # set_props('peakindex-title', {'children': f"New peak indexing {next_peakindex_id}"})

            try:
                # This section handles both single and multiple/pooled scan numbers
                scan_ids = [int(sid) if sid and sid.lower() != 'none' else None for sid in (scan_id_str.split(',') if scan_id_str else [])]
                
                # Handle pooled reconstruction IDs
                wirerecon_ids = [int(wid) if wid and wid.lower() != 'none' else None for wid in (wirerecon_id_str.split(',') if wirerecon_id_str else [])]
                recon_ids = [int(rid) if rid and rid.lower() != 'none' else None for rid in (recon_id_str.split(',') if recon_id_str else [])]
                peakindex_ids = [int(pid) if pid and pid.lower() != 'none' else None for pid in (peakindex_id_str.split(',') if peakindex_id_str else [])]

                # Validate that lists have matching lengths
                if wirerecon_ids and len(wirerecon_ids) != len(scan_ids): raise ValueError(f"Mismatch: {len(scan_ids)} scan IDs but {len(wirerecon_ids)} wirerecon IDs")
                if recon_ids and len(recon_ids) != len(scan_ids): raise ValueError(f"Mismatch: {len(scan_ids)} scan IDs but {len(recon_ids)} recon IDs")
                if peakindex_ids and len(peakindex_ids) != len(scan_ids): raise ValueError(f"Mismatch: {len(scan_ids)} scan IDs but {len(peakindex_ids)} peakindex IDs")

                # If no reconstruction IDs provided, fill with None
                if not wirerecon_ids: wirerecon_ids = [None] * len(scan_ids)
                if not recon_ids: recon_ids = [None] * len(scan_ids)
                if not peakindex_ids: peakindex_ids = [None] * len(scan_ids)

                peakindex_form_data_list = []
                found_items = []
                not_found_items = []
                for i, current_scan_id in enumerate(scan_ids):
                    current_wirerecon_id = wirerecon_ids[i]
                    current_recon_id = recon_ids[i]
                    current_peakindex_id = peakindex_ids[i]

                    # Query metadata and scan data
                    metadata_data = session.query(db_schema.Metadata).filter(db_schema.Metadata.scanNumber == current_scan_id).first()
                    # scan_data = session.query(db_schema.Scan).filter(db_schema.Scan.scanNumber == current_scan_id).all()
                    if metadata_data:
                        if current_peakindex_id:
                            found_items.append(f"peak index {current_peakindex_id}")
                        elif current_recon_id:
                            found_items.append(f"reconstruction {current_recon_id}")
                        elif current_wirerecon_id:
                            found_items.append(f"wire reconstruction {current_wirerecon_id}")
                        else:
                            found_items.append(f"scan {current_scan_id}")

                        # Determine output folder format based on if reconstruction ID
                        outputFolder = PEAKINDEX_DEFAULTS["outputFolder"]
                        if current_recon_id or current_wirerecon_id:
                            outputFolder = outputFolder.replace("index_%d", "rec_%d/index_%d") #"analysis/scan_%d/rec_%d/index_%d"
                        
                        # # Format output folder with scan number and IDs
                        # try:
                        #     if current_wirerecon_id:
                        #         outputFolder = outputFolder % (current_scan_id, current_wirerecon_id, next_peakindex_id)
                        #     elif current_recon_id:
                        #         outputFolder = outputFolder % (current_scan_id, current_recon_id, next_peakindex_id)
                        #     else:
                        #         outputFolder = outputFolder % (current_scan_id, next_peakindex_id)
                        # except:
                        #     # If formatting fails, use the original string
                        #     pass
                        # next_peakindex_id += 1

                        # If peakindex_id is provided, load existing peakindex data
                        if current_peakindex_id:
                            try:
                                peakindex_data = session.query(db_schema.PeakIndex).filter(db_schema.PeakIndex.peakindex_id == current_peakindex_id).first()
                                if peakindex_data:
                                    # Use existing peakindex data as the base
                                    peakindex_form_data = peakindex_data
                                    # Update only the necessary fields
                                    # peakindex_form_data.scanNumber = current_scan_id
                                    # peakindex_form_data.recon_id = current_recon_id
                                    # peakindex_form_data.wirerecon_id = current_wirerecon_id
                                    peakindex_form_data.outputFolder = outputFolder
                                    # Convert file paths to relative paths
                                    peakindex_form_data.geoFile = remove_root_path_prefix(peakindex_data.geoFile, root_path)
                                    peakindex_form_data.crystFile = remove_root_path_prefix(peakindex_data.crystFile, root_path)
                                    if peakindex_data.filefolder:
                                        peakindex_form_data.data_path = remove_root_path_prefix(peakindex_data.filefolder, root_path)
                                    if peakindex_data.filenamePrefix:
                                        peakindex_form_data.filenamePrefix = peakindex_data.filenamePrefix
                            
                            except (ValueError, Exception):
                                # If peakindex_id is not valid or not found, create defaults
                                current_peakindex_id = None

                        # Create defaults if no peakindex_id or if loading failed
                        if not current_peakindex_id:
                            # Create a PeakIndex object with populated defaults from metadata/scan
                            peakindex_form_data = db_schema.PeakIndex(
                                scanNumber=current_scan_id,
                                # Recon ID
                                recon_id=current_recon_id,
                                wirerecon_id=current_wirerecon_id,
                                # Energy-related fields from source
                                indexKeVmaxCalc=metadata_data.source_energy if metadata_data else PEAKINDEX_DEFAULTS["indexKeVmaxCalc"],
                                indexKeVmaxTest=metadata_data.source_energy if metadata_data else PEAKINDEX_DEFAULTS["indexKeVmaxTest"],
                                energyUnit=metadata_data.source_energy_unit if metadata_data else PEAKINDEX_DEFAULTS["energyUnit"],
                                outputFolder=outputFolder,
                                **{k: v for k, v in PEAKINDEX_DEFAULTS.items() if k not in ['scanNumber', 'outputFolder', 'indexKeVmaxCalc', 'indexKeVmaxTest', 'energyUnit']}
                            )

                        # Add root_path from DEFAULT_VARIABLES
                        peakindex_form_data.root_path = root_path

                        # If processing reconstruction data, use the reconstruction output folder as data path
                        if current_wirerecon_id:
                            wirerecon_data = session.query(db_schema.WireRecon).filter(db_schema.WireRecon.wirerecon_id == current_wirerecon_id).first()
                            if wirerecon_data:
                                if wirerecon_data.outputFolder:
                                    peakindex_form_data.data_path = remove_root_path_prefix(wirerecon_data.outputFolder, root_path)
                                if wirerecon_data.filenamePrefix:
                                    peakindex_form_data.filenamePrefix = wirerecon_data.filenamePrefix
                        elif current_recon_id:
                            recon_data = session.query(db_schema.Recon).filter(db_schema.Recon.recon_id == current_recon_id).first()
                            if recon_data:
                                if recon_data.file_output:
                                    peakindex_form_data.data_path = remove_root_path_prefix(recon_data.file_output, root_path)
                                if recon_data.filenamePrefix: #if hasattr(recon_data, 'filenamePrefix') and recon_data.filenamePrefix:
                                    peakindex_form_data.filenamePrefix = recon_data.filenamePrefix
                        
                        if not all([hasattr(peakindex_form_data, 'data_path'), getattr(peakindex_form_data, 'filenamePrefix')]):
                            # Retrieve data_path and filenamePrefix from catalog data
                            catalog_data = get_catalog_data(session, current_scan_id, root_path, CATALOG_DEFAULTS)
                        if not hasattr(peakindex_form_data, 'data_path'):
                            peakindex_form_data.data_path = catalog_data.get('data_path', '')
                        if not getattr(peakindex_form_data, 'filenamePrefix'):
                            # peakindex_form_data.filenamePrefix = catalog_data.get('filenamePrefix', '')
                            peakindex_form_data.filenamePrefix = catalog_data.get('filenamePrefix', [])
                        
                        peakindex_form_data_list.append(peakindex_form_data)
                    else:
                        if current_peakindex_id:
                            not_found_items.append(f"peak index {current_peakindex_id}")
                        elif current_recon_id:
                            not_found_items.append(f"reconstruction {current_recon_id}")
                        elif current_wirerecon_id:
                            not_found_items.append(f"wire reconstruction {current_wirerecon_id}")
                        else:
                            not_found_items.append(f"scan {current_scan_id}")
                    
                # Create pooled peakindex_form_data by combining values from all scans
                if peakindex_form_data_list:
                    pooled_peakindex_form_data = db_schema.PeakIndex()
                    
                    # Pool all attributes - both database columns and extra attributes
                    all_attrs = list(db_schema.PeakIndex.__table__.columns.keys()) + ['root_path', 'data_path', 'filenamePrefix']
                    
                    for attr in all_attrs:
                        if attr == 'peakindex_id': continue
                        
                        values = []
                        for d in peakindex_form_data_list:
                            if hasattr(d, attr):
                                values.append(getattr(d, attr))
                        
                        if values:
                            if all(v == values[0] for v in values):
                                setattr(pooled_peakindex_form_data, attr, values[0])
                            else:
                                setattr(pooled_peakindex_form_data, attr, "; ".join(map(str, values)))
                    
                    # User text
                    pooled_peakindex_form_data.author = DEFAULT_VARIABLES['author']
                    pooled_peakindex_form_data.notes = DEFAULT_VARIABLES['notes']
                    # # Add root_path from DEFAULT_VARIABLES
                    # pooled_peakindex_form_data.root_path = root_path
                    # Populate the form with the defaults
                    set_peakindex_form_props(pooled_peakindex_form_data)

                    # Set alert based on what was found
                    if not_found_items:
                        # Partial success
                        set_props("alert-scan-loaded", {
                            'is_open': True,
                            'children': f"Loaded data for {len(found_items)} items. Could not find: {', '.join(not_found_items)}.",
                            'color': 'warning'
                        })
                    else:
                        # Full success
                        set_props("alert-scan-loaded", {
                            'is_open': True,
                            'children': f"Successfully loaded and merged data from {len(found_items)} items into the form.",
                            'color': 'success'
                        })
                else:
                    # Fallback if no valid scans found
                    if not_found_items:
                        set_props("alert-scan-loaded", {
                            'is_open': True,
                            'children': f"Could not find any of the requested items: {', '.join(not_found_items)}. Displaying default values.",
                            'color': 'danger'
                        })
                    
                    peakindex_form_data = db_schema.PeakIndex(
                        scanNumber=str(scan_id_str).replace(',','; '),
                        
                        # User text
                        author=DEFAULT_VARIABLES['author'],
                        notes=DEFAULT_VARIABLES['notes'],
                        
                        # Processing parameters
                        threshold=PEAKINDEX_DEFAULTS["threshold"],
                        thresholdRatio=PEAKINDEX_DEFAULTS["thresholdRatio"],
                        maxRfactor=PEAKINDEX_DEFAULTS["maxRfactor"],
                        boxsize=PEAKINDEX_DEFAULTS["boxsize"],
                        max_number=PEAKINDEX_DEFAULTS["max_number"],
                        min_separation=PEAKINDEX_DEFAULTS["min_separation"],
                        peakShape=PEAKINDEX_DEFAULTS["peakShape"],
                        scanPoints=PEAKINDEX_DEFAULTS["scanPoints"],
                        scanPointslen=srange(PEAKINDEX_DEFAULTS["scanPoints"]).len(),
                        depthRange=PEAKINDEX_DEFAULTS["depthRange"],
                        depthRangelen=srange(PEAKINDEX_DEFAULTS["depthRange"]).len(),
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
                        outputFolder=PEAKINDEX_DEFAULTS["outputFolder"],
                        geoFile=PEAKINDEX_DEFAULTS["geoFile"],
                        crystFile=PEAKINDEX_DEFAULTS["crystFile"],
                        depth=PEAKINDEX_DEFAULTS["depth"],
                        beamline=PEAKINDEX_DEFAULTS["beamline"]
                    )
                    
                    # Set root_path
                    peakindex_form_data.root_path = root_path
                    peakindex_form_data.data_path = ""
                    peakindex_form_data.filenamePrefix = ""
                    
                    # Populate the form with the defaults
                    set_peakindex_form_props(peakindex_form_data)

            except Exception as e:
                set_props("alert-scan-loaded", {
                    'is_open': True, 
                    'children': f'Error loading scan data: {str(e)}',
                    'color': 'danger'
                })
    
    # Return timestamp to trigger downstream callbacks
    return datetime.datetime.now().isoformat()
