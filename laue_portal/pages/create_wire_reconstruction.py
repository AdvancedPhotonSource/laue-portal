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
from laue_portal.components.wire_recon_form import wire_recon_form, set_wire_recon_form_props
from laue_portal.processing.redis_utils import enqueue_wire_reconstruction, STATUS_REVERSE_MAPPING
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

WIRERECON_DEFAULTS = {
    "scanNumber": 276994,
    "geoFile": "Run1/geofiles/geoN_2023-04-06_03-07-11_cor6.xml",
    "percent_brightest": 100,
    "depth_start": -50,
    "depth_end": 150,
    "depth_resolution": 50,#1,
    "outputFolder": "analysis/scan_%d/rec_%d",#"wire_recons",
    "files": 7,#"1",
    "wire_edges": "leading",
}

CATALOG_DEFAULTS = {
    "filefolder": "tests/data/gdata",
    "filenamePrefix": "HAs_long_laue1_",
}

# DEFAULT_VARIABLES = {
#     "author": "",
#     "notes": "",
#     "root_path": "/net/s34data/export/s34data1/LauePortal/portal_workspace/",
#     "num_threads": 35,
#     "memory_limit_mb": 50000,
#     "verbose": 1,
# }

dash.register_page(__name__)

layout = dbc.Container(
    [html.Div([
        navbar.navbar,
        dcc.Location(id='url-create-wirerecon', refresh=False),
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
        # html.Hr(),
        # html.Center(
        #     html.Div(
        #         [
        #             html.Div([
        #                     dcc.Upload(dbc.Button('Upload Config'), id='upload-wireconfig'),
        #             ], style={'display':'inline-block'}),
        #         ],
        #     )
        # ),
        html.Hr(),
        html.Center(
            html.H3(id="wirerecon-title", children="New wire recon"),
        ),
        html.Hr(),
        html.Center(
            dbc.Button('Submit', id='submit_wire', color='primary'),
        ),
        html.Hr(),
        wire_recon_form,
        dcc.Store(id="next-wire-recon-id"),
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
#     Input('upload-wireconfig', 'contents'),
#     prevent_initial_call=True,
# )
# def upload_config(contents):
#     try:
#         content_type, content_string = contents.split(',')
#         decoded = base64.b64decode(content_string)
#         config = yaml.safe_load(decoded)
#         recon_row = db_utils.import_wire_recon_row(config)
#         recon_row.date = datetime.datetime.now()
#         recon_row.commit_id = ''
#         recon_row.calib_id = ''
#         recon_row.runtime = ''
#         recon_row.computer_name = ''
#         recon_row.dataset_id = 0
#         recon_row.notes = ''

#         set_props("alert-upload", {'is_open': True, 
#                                     'children': 'Config uploaded successfully',
#                                     'color': 'success'})
#         set_wire_recon_form_props(recon_row)

#     except Exception as e:
#         set_props("alert-upload", {'is_open': True, 
#                                     'children': f'Upload Failed! Error: {e}',
#                                     'color': 'danger'})


@dash.callback(
    Input('submit_wire', 'n_clicks'),

    State('next-wire-recon-id', 'value'),

    State('scanNumber', 'value'),
    
    # Recon constraints
    State('geoFile', 'value'),
    State('percent_brightest', 'value'),
    
    # Depth parameters
    State('depth_start', 'value'),
    State('depth_end', 'value'),
    State('depth_resolution', 'value'),
    
    # Output
    State('outputFolder', 'value'),
    
    # Additional fields
    State('files', 'value'),
    State('wire_edges', 'value'),
    
    # User text
    State('author', 'value'),
    State('notes', 'value'),

    prevent_initial_call=True,
)
def submit_parameters(n, rec_id,
    scanNumbers, #Pooled scanNumbers

    # Recon constraints
    geometry_file,
    percent_brightest,

    # Depth parameters
    depth_start,
    depth_end,
    depth_resolution,
    
    # Output
    output_folder,
    
    # Additional fields
    files,
    wire_edges,
    
    # User text
    author,
    notes,
):
    # TODO: Input validation and response

    root_path = DEFAULT_VARIABLES["root_path"]
    num_threads = DEFAULT_VARIABLES["num_threads"]
    memory_limit_mb = DEFAULT_VARIABLES["memory_limit_mb"]
    verbose = DEFAULT_VARIABLES["verbose"]

    # Convert relative paths to full paths # Strip leading slashes to ensure paths are treated as relative
    full_geometry_file = os.path.join(root_path, geometry_file.lstrip('/'))
    full_output_folder = os.path.join(root_path, output_folder.lstrip('/'))

    for scanNumber in str(scanNumbers).split(','):

        try:
            scan_full_output_folder = full_output_folder % (int(scanNumber), rec_id)
        except:
            scan_full_output_folder = full_output_folder
        
        # Create output directory if it doesn't exist
        try:
            os.makedirs(scan_full_output_folder, exist_ok=True)
            logger.info(f"Output directory: {scan_full_output_folder}")
        except Exception as e:
            logger.error(f"Failed to create output directory {scan_full_output_folder}: {e}")
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
            # Parse files string using srange
            files_srange = srange(files)
            file_nums = files_srange.list()
            for file_num in file_nums:
                subjob = db_schema.SubJob(
                    job_id=job_id,
                    computer_name=JOB_DEFAULTS['computer_name'],
                    status=STATUS_REVERSE_MAPPING["Queued"],
                    priority=JOB_DEFAULTS['priority']
                )
                session.add(subjob)
            
            wirerecon = db_schema.WireRecon(
                # date=datetime.datetime.now(),
                # commit_id='TEST',
                # calib_id='TEST',
                # runtime='TEST',
                # computer_name='TEST',
                # dataset_id=0,
                # notes='TODO', 

                scanNumber=int(scanNumber),
                job_id = job_id,
                
                # User text
                author=author,
                notes=notes,
                
                # Recon constraints
                geoFile=full_geometry_file,  # Store full path in database
                percent_brightest=percent_brightest,
                wire_edges=wire_edges,
                
                # Depth parameters
                depth_start=depth_start,
                depth_end=depth_end,
                depth_resolution=depth_resolution,
                
                # Compute parameters
                num_threads=num_threads,
                memory_limit_mb=memory_limit_mb,
                
                # Files
                files=files,
                
                # Output
                outputFolder=scan_full_output_folder,  # Store full path in database
                verbose=verbose,
            )

        # with Session(db_utils.ENGINE) as session:
            session.add(wirerecon)
            # config_dict = db_utils.create_config_obj(wirerecon)

            session.commit()
        
        set_props("alert-submit", {'is_open': True, 
                                    'children': 'Config Added to Database',
                                    'color': 'success'})

        # Enqueue the job to Redis
        try:
            # Get catalog data from database
            catalog_data = get_catalog_data(session, int(scanNumber), root_path, CATALOG_DEFAULTS)
            
            # Prepare lists of input and output files for all subjobs
            input_files = []
            output_files = []
            
            for file_num in file_nums:
                # Prepare parameters for wire reconstruction
                file_str = catalog_data['filenamePrefix'] % file_num
                input_filename = file_str + ".h5"
                input_file = os.path.join(catalog_data['filefolder'], input_filename)
                output_base_name = file_str + "_"
                output_file_base = os.path.join(scan_full_output_folder, output_base_name)
                
                input_files.append(input_file)
                output_files.append(output_file_base)
            
            # Enqueue the batch job with all files
            depth_range = (depth_start, depth_end)
            rq_job_id = enqueue_wire_reconstruction(
                job_id=job_id,
                input_files=input_files,
                output_files=output_files,
                geometry_file=full_geometry_file,  # Use full path
                depth_range=depth_range,
                resolution=depth_resolution,
                percent_brightest=percent_brightest, #percent_to_process
                wire_edge=wire_edges,  # Note: form uses 'wire_edges', function expects 'wire_edge'
                memory_limit_mb=memory_limit_mb,
                num_threads=num_threads,
                verbose=verbose,
                detector_number=0  # Default detector number
            )
            
            logger.info(f"Wire reconstruction batch job {job_id} enqueued with RQ ID: {rq_job_id} for {len(file_nums)} files")
            
            set_props("alert-submit", {'is_open': True, 
                                      'children': f'Job {job_id} submitted to queue with {files_srange.len()} file(s)',
                                      'color': 'info'})
        except Exception as e:
            logger.error(f"Failed to enqueue job: {e}")
            set_props("alert-submit", {'is_open': True, 
                                      'children': f'Failed to queue job: {str(e)}',
                                      'color': 'danger'})


@dash.callback(
    Input('url-create-wirerecon','pathname'),
    prevent_initial_call=True,
)
def get_wirerecons(path):
    root_path = DEFAULT_VARIABLES["root_path"]
    if path == '/create-wire-reconstruction':
        # Create a WireRecon object with form defaults (not for database insertion)
        wirerecon_defaults = db_schema.WireRecon(
            scanNumber=WIRERECON_DEFAULTS["scanNumber"],
            
            # User text
            author=DEFAULT_VARIABLES["author"],
            notes=DEFAULT_VARIABLES["notes"],
            
            # Recon constraints
            geoFile=WIRERECON_DEFAULTS["geoFile"],
            percent_brightest=WIRERECON_DEFAULTS["percent_brightest"],
            wire_edges=WIRERECON_DEFAULTS["wire_edges"],
            
            # Depth parameters
            depth_start=WIRERECON_DEFAULTS["depth_start"],
            depth_end=WIRERECON_DEFAULTS["depth_end"],
            depth_resolution=WIRERECON_DEFAULTS["depth_resolution"],
            
            # Compute parameters
            num_threads=DEFAULT_VARIABLES["num_threads"],
            memory_limit_mb=DEFAULT_VARIABLES["memory_limit_mb"],
            
            # Files
            files=WIRERECON_DEFAULTS["files"],
            
            # Output
            outputFolder=WIRERECON_DEFAULTS["outputFolder"],
            verbose=DEFAULT_VARIABLES["verbose"],
        )
        # Add root_path from DEFAULT_VARIABLES
        wirerecon_defaults.root_path = root_path
        with Session(db_utils.ENGINE) as session:
            # Get next wirerecon_id and update title
            next_wirerecon_id = db_utils.get_next_id(session, db_schema.WireRecon)
            set_props('next-wire-recon-id', {'value': next_wirerecon_id})
            set_props('wirerecon-title', {'children': f"New wire recon {next_wirerecon_id}"})
            
            # Retrieve data_path and filenamePrefix from catalog data
            catalog_data = get_catalog_data(session, WIRERECON_DEFAULTS["scanNumber"], root_path, CATALOG_DEFAULTS)
        wirerecon_defaults.data_path = catalog_data["data_path"]
        wirerecon_defaults.filenamePrefix = catalog_data["filenamePrefix"]
            
        set_wire_recon_form_props(wirerecon_defaults)
    else:
        raise PreventUpdate

@dash.callback(
    Input('url-create-wirerecon', 'href'),
    prevent_initial_call=True,
)
def load_scan_data_from_url(href):
    """
    Load scan data when scan_id is provided in URL query parameter
    URL format: /create-wirerecons?scan_id={scan_id}
    Pooled URL format: /create-wirerecons?scan_id={(scan_ids)}
    """
    if not href:
        raise PreventUpdate

    parsed_url = urllib.parse.urlparse(href)
    query_params = urllib.parse.parse_qs(parsed_url.query)
    
    scan_id = query_params.get('scan_id', [None])[0]
    root_path = DEFAULT_VARIABLES["root_path"]

    if scan_id:
        with Session(db_utils.ENGINE) as session:
            try:
                scan_id = int(scan_id)
                # Query metadata and scan data
                metadata_data = session.query(db_schema.Metadata).filter(
                    db_schema.Metadata.scanNumber == scan_id
                ).first()
                
                # scans = session.query(db_schema.Scan).filter(
                #     db_schema.Scan.scanNumber == scan_id
                # ).all()

                if metadata_data:
                    # Create a WireRecon object with populated defaults from metadata/scan
                    wirerecon_defaults = db_schema.WireRecon(
                        scanNumber=scan_id,
                        
                        # User text
                        author=DEFAULT_VARIABLES["author"],
                        notes=DEFAULT_VARIABLES["notes"],
                        
                        # Recon constraints
                        geoFile=WIRERECON_DEFAULTS["geoFile"],
                        percent_brightest=WIRERECON_DEFAULTS["percent_brightest"],
                        wire_edges=WIRERECON_DEFAULTS["wire_edges"],
                        
                        # Depth parameters
                        depth_start=WIRERECON_DEFAULTS["depth_start"],
                        depth_end=WIRERECON_DEFAULTS["depth_end"],
                        depth_resolution=WIRERECON_DEFAULTS["depth_resolution"],
                        
                        # Compute parameters
                        num_threads=DEFAULT_VARIABLES["num_threads"],
                        memory_limit_mb=DEFAULT_VARIABLES["memory_limit_mb"],
                        
                        # Files
                        files=WIRERECON_DEFAULTS["files"],
                        
                        # Output
                        outputFolder=WIRERECON_DEFAULTS["outputFolder"],
                        verbose=DEFAULT_VARIABLES["verbose"],
                    )
                    # Add root_path from DEFAULT_VARIABLES
                    wirerecon_defaults.root_path = root_path
                    # Retrieve data_path and filenamePrefix from catalog data
                    catalog_data = get_catalog_data(session, scan_id, root_path, CATALOG_DEFAULTS)
                    wirerecon_defaults.data_path = catalog_data["data_path"]
                    wirerecon_defaults.filenamePrefix = catalog_data["filenamePrefix"]
                    
                    # Get next wirerecon_id and update title
                    next_wirerecon_id = db_utils.get_next_id(session, db_schema.WireRecon)
                    set_props('next-wire-recon-id', {'value': next_wirerecon_id})
                    set_props('wirerecon-title', {'children': f"New wire recon {next_wirerecon_id}"})
                    
                    # Populate the form with the defaults
                    set_wire_recon_form_props(wirerecon_defaults)#,read_only=True)
                    
                    # Show success message
                    set_props("alert-scan-loaded", {
                        'is_open': True, 
                        'children': f'Scan {scan_id} data loaded successfully. Scan Number: {metadata_data.dataset_id}, Energy: {metadata_data.source_energy} {metadata_data.source_energy_unit}',
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
                    scan_numbers = str(scan_id).replace('$','').replace(',',', ').split(',')
                    
                    # Find common path among all scans and collect filename prefixes
                    common_path = None
                    filename_prefixes = []
                    for scan_num in scan_numbers:
                        try:
                            catalog_data = get_catalog_data(session, int(scan_num.strip()), root_path, CATALOG_DEFAULTS)
                            if catalog_data:
                                if 'filefolder' in catalog_data:
                                    if common_path is None:
                                        common_path = catalog_data['filefolder']
                                    else:
                                        # Find common prefix
                                        common_path = os.path.commonpath([common_path, catalog_data['filefolder']])
                                
                                # Collect filename prefix if available
                                if catalog_data.get('filenamePrefix'):
                                    filename_prefixes.append(catalog_data['filenamePrefix'])
                        except:
                            continue
                    
                    wirerecon_defaults = db_schema.WireRecon(
                        scanNumber=str(scan_id).replace('$','').replace(',',', '),
                        
                        # User text
                        author=DEFAULT_VARIABLES["author"],
                        notes=DEFAULT_VARIABLES["notes"],
                        
                        # Recon constraints
                        geoFile=WIRERECON_DEFAULTS["geoFile"],
                        percent_brightest=WIRERECON_DEFAULTS["percent_brightest"],
                        wire_edges=WIRERECON_DEFAULTS["wire_edges"],
                        
                        # Depth parameters
                        depth_start=WIRERECON_DEFAULTS["depth_start"],
                        depth_end=WIRERECON_DEFAULTS["depth_end"],
                        depth_resolution=WIRERECON_DEFAULTS["depth_resolution"],
                        
                        # Compute parameters
                        num_threads=DEFAULT_VARIABLES["num_threads"],
                        memory_limit_mb=DEFAULT_VARIABLES["memory_limit_mb"],
                        
                        # Files
                        files=WIRERECON_DEFAULTS["files"],
                        
                        # Output
                        outputFolder=WIRERECON_DEFAULTS["outputFolder"],
                        verbose=DEFAULT_VARIABLES["verbose"],
                    )
                    
                    # Determine root_path and data_path based on common path
                    if common_path:
                        if common_path.startswith(root_path):
                            # Common path is within default root
                            wirerecon_defaults.root_path = root_path
                            wirerecon_defaults.data_path = remove_root_path_prefix(common_path, root_path)
                        else:
                            # Common path is outside default root, update root_path
                            wirerecon_defaults.root_path = common_path
                            wirerecon_defaults.data_path = ""
                    else:
                        # No common path found, use defaults
                        wirerecon_defaults.root_path = root_path
                        wirerecon_defaults.data_path = ""
                    
                    # Set filenamePrefix as comma-separated string of unique prefixes
                    # unique_prefixes = list(dict.fromkeys(filename_prefixes))  # Remove duplicates while preserving order
                    # wirerecon_defaults.filenamePrefix = ", ".join(unique_prefixes) if unique_prefixes else ""
                    wirerecon_defaults.filenamePrefix = ", ".join(filename_prefixes) if filename_prefixes else ""

                    # Get next wirerecon_id and update title
                    next_wirerecon_id = db_utils.get_next_id(session, db_schema.WireRecon)
                    set_props('next-wire-recon-id', {'value': next_wirerecon_id})
                    set_props('wirerecon-title', {'children': f"New wire recon {next_wirerecon_id}"})
                    
                    # Populate the form with the defaults
                    set_wire_recon_form_props(wirerecon_defaults)#,read_only=True)
                    
                except Exception as e:
                    set_props("alert-scan-loaded", {
                        'is_open': True, 
                        'children': f'Error loading scan data: {str(e)}',
                        'color': 'danger'
                    })
