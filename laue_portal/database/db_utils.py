import laue_portal.database.db_schema as db_schema
from laue_portal import config
import xml.etree.ElementTree as ET
import sqlalchemy
from datetime import datetime
from laue_portal.config import MOTOR_GROUPS


def parse_metadata(xml,xmlns="http://sector34.xray.aps.anl.gov/34ide/scanLog",scan_no=2,empty='\n\t\t'):
    # tree = ET.parse(xml)
    # root = tree.getroot()
    root = ET.fromstring(xml)
    scan = root[scan_no]

    def name(s,xmlns=xmlns): return s.replace(f'{{{xmlns}}}','')

    def traverse_tree(fields,tree_dict={},parent_name=''):
        if not len(fields):
            pass
        else:
            for field in list(fields):
                field_name = name(field.tag)
                if not any([field_name == f for f in ['scan','cpt']]):
                    path_name = f'{parent_name}{field_name}'
                    field_dict = dict([(f'{path_name}_{k}',v) for k,v in field.attrib.items()])
                    if empty not in field.text: field_dict[path_name] = field.text
                    tree_dict.update(field_dict)
                    traverse_tree(field,tree_dict,path_name+'_')
        return tree_dict
    
    # Define numeric fields that should be None instead of empty string
    numeric_fields = {
        'time_epoch', 'source_energy', 'source_IDgap', 'source_IDtaper', 
        'source_ringCurrent', 'knife-edge_knifeScan', 'scanEnd_time_epoch', 
        'scanEnd_scanDuration', 'scanEnd_source_ringCurrent'
    }
    
    scanNumber = scan.get('scanNumber')
    log_dict = {'scanNumber': scanNumber,
                'time_epoch': None,
                'time': '',
                'user_name': '',
                'source_beamBad': '',
                'source_CCDshutter': '',
                'source_monoTransStatus': '',
                'source_energy_unit': '',
                'source_energy': None,
                'source_IDgap_unit': '',
                'source_IDgap': None,
                'source_IDtaper_unit': '',
                'source_IDtaper': None,
                'source_ringCurrent_unit': '',
                'source_ringCurrent': None,
                'sample_XYZ_unit': '',
                'sample_XYZ_desc': '',
                'sample_XYZ': '',
                'knife-edge_XYZ_unit': '',
                'knife-edge_XYZ_desc': '',
                'knife-edge_XYZ': '',
                'knife-edge_knifeScan_unit': '',
                'knife-edge_knifeScan': None,
                'mda_file': '',
                'scanEnd_abort': '',
                'scanEnd_time_epoch': None,
                'scanEnd_time': '',
                'scanEnd_scanDuration_unit': '',
                'scanEnd_scanDuration': None,
                'scanEnd_source_beamBad': '',
                'scanEnd_source_ringCurrent_unit': '',
                'scanEnd_source_ringCurrent': None,
    }

    log_dict = traverse_tree(scan,log_dict)
    
    # Convert empty strings to None for numeric fields
    for field in numeric_fields:
        if field in log_dict and log_dict[field] == '':
            log_dict[field] = None

    scan_label = 'scan'
    scan_dims = list(scan.iter(f'{{{xmlns}}}{scan_label}'))
    #scan_dims_num = str(len(scan_dims))

    #*****#
    PV_label1 = 'positioner'; PV_label2 = 'detectorTrig'
    scanEnd_cpt_list = scan.find(f'{{{xmlns}}}scanEnd').find(f'{{{xmlns}}}cpt').text.split()[::-1]
    # Define numeric fields for scan dimensions
    scan_numeric_fields = {'dim', 'npts', 'cpt'}
    
    dims_dict_list = []
    for ii,dim in enumerate(scan_dims):
        dim_dict = {'scanNumber': scanNumber,
                    'dim': None,
                    'npts': None,
                    'after': '',
                    'positioner1_PV': '',
                    'positioner1_ar': '',
                    'positioner1_mode': '',
                    'positioner1': '',
                    'positioner2_PV': '',
                    'positioner2_ar': '',
                    'positioner2_mode': '',
                    'positioner2': '',
                    'positioner3_PV': '',
                    'positioner3_ar': '',
                    'positioner3_mode': '',
                    'positioner3': '',
                    'positioner4_PV': '',
                    'positioner4_ar': '',
                    'positioner4_mode': '',
                    'positioner4': '',
                    'detectorTrig1_PV': '',
                    'detectorTrig1_VAL': '',
                    'detectorTrig2_PV': '',
                    'detectorTrig2_VAL': '',
                    'detectorTrig3_PV': '',
                    'detectorTrig3_VAL': '',
                    'detectorTrig4_PV': '',
                    'detectorTrig4_VAL': '',
                    'cpt': None,
        }
        dim_dict.update(dim.attrib)
        PV_count_dict = {PV_label1:0, PV_label2:0}
        for record in dim:
            #record_name = name(record.tag)
            if 'PV' in record.attrib.keys():
                record_name = name(record.tag)
                for PV_label in PV_count_dict.keys():
                    if PV_label in record_name:
                        PV_count_dict[PV_label] += 1
                        record_label = f'{PV_label}{PV_count_dict[PV_label]}'
                        record_dict = dict([('_'.join([record_label,k]),v) for k,v in record.attrib.items()])
                        if record.text: record_dict[f'{record_label}'] = record.text
                        dim_dict.update(record_dict)
        dim_dict['cpt'] = scanEnd_cpt_list[ii]
        
        # Convert empty strings to None for numeric fields
        for field in scan_numeric_fields:
            if field in dim_dict and dim_dict[field] == '':
                dim_dict[field] = None
        
        dim_dict = {f'{scan_label}_{k}' if k != 'scanNumber' else k:v for k,v in dim_dict.items()}
        dims_dict_list.append(dim_dict)
    #*****#

    return log_dict, dims_dict_list

def find_motor_group(pv_value):
    """
    Find which motor group contains the given motor string.
    
    Args:
        pv_value: The motor PV string to search for
        
    Returns:
        The motor group key if found, "none" if pv_value is None, 
        or "other" if pv_value is not None but not found
    """
    if pv_value is None:
        return "none"
    
    motor_string = pv_value.split('.VAL')[0]
    for group_key, motor_list in MOTOR_GROUPS.items():
        if motor_string in motor_list:
            return group_key
    
    return "other"

def update_motor_group_totals(motor_group_totals, scan):
    """
    Updates the motor group total programmed points and completed points
    with the data for each motor group from a single scan.
    """
    for PV_i in range(1, 5):
        pv_attr = f'scan_positioner{PV_i}_PV'
        if getattr(scan, pv_attr, None):
            motor_group = find_motor_group(getattr(scan, pv_attr))
            if motor_group not in motor_group_totals:
                motor_group_totals[motor_group] = {'points': 1, 'completed': 1}
            
            motor_group_totals[motor_group]['points'] *= int(scan.scan_npts)
            motor_group_totals[motor_group]['completed'] *= int(scan.scan_cpt)
    return motor_group_totals

def convert_time_string_to_datetime(time_string):
    """
    Convert time string to datetime object.
    Handles various time formats commonly found in the XML data.
    """
    if not time_string or time_string == '':
        return None
    
    # Common time formats in the XML data
    time_formats = [
        '%Y-%m-%dT%H:%M:%S',  # ISO format: 2023-02-01T18:46:06
        '%Y-%m-%d %H:%M:%S',  # Alternative format
        '%Y-%m-%d, %H:%M:%S',  # Format with comma: 2023-02-25, 04:00:38
        '%Y-%m-%dT%H:%M:%S.%f',  # With microseconds
    ]
    
    for fmt in time_formats:
        try:
            return datetime.strptime(time_string, fmt)
        except ValueError:
            continue
    
    # If none of the formats work, raise an error
    raise ValueError(f"Unable to parse time string: {time_string}")

def convert_epoch_string_to_int(epoch_string):
    """
    Convert epoch time string to integer.
    """
    if not epoch_string or epoch_string == '' or epoch_string is None:
        return None
    
    try:
        return int(epoch_string)
    except ValueError:
        return None

def remove_root_path_prefix(file_path, root_path):
    """
    Remove root_path prefix from a file path and any leading slash.
    
    Args:
        file_path: The full file path
        root_path: The root path prefix to remove
        
    Returns:
        str: The file path with root_path prefix removed
    """
    if not file_path:
        return ""
    
    result_path = file_path
    
    # Remove root_path from file_path if it starts with it
    if root_path and file_path.startswith(root_path):
        result_path = file_path[len(root_path):]
        
    # Remove leading slash if present
    if result_path.startswith('/'):
        result_path = result_path[1:]
        
    return result_path

def import_metadata_row(metadata_object):
    """
    Reads a yaml file and creates a new Metadata ORM object with 
    the base data of the file
    """

    metadata_row = db_schema.Metadata(
        scanNumber=metadata_object['scanNumber'],
        time_epoch=convert_epoch_string_to_int(metadata_object['time_epoch']),
        time=convert_time_string_to_datetime(metadata_object['time']),
        user_name=metadata_object['user_name'],
        source_beamBad=metadata_object['source_beamBad'],
        source_CCDshutter=metadata_object['source_CCDshutter'],
        source_monoTransStatus=metadata_object['source_monoTransStatus'],
        source_energy_unit=metadata_object['source_energy_unit'],
        source_energy=metadata_object['source_energy'],
        source_IDgap_unit=metadata_object['source_IDgap_unit'],
        source_IDgap=metadata_object['source_IDgap'],
        source_IDtaper_unit=metadata_object['source_IDtaper_unit'],
        source_IDtaper=metadata_object['source_IDtaper'],
        source_ringCurrent_unit=metadata_object['source_ringCurrent_unit'],
        source_ringCurrent=metadata_object['source_ringCurrent'],
        sample_XYZ_unit=metadata_object['sample_XYZ_unit'],
        sample_XYZ_desc=metadata_object['sample_XYZ_desc'],
        sample_XYZ=metadata_object['sample_XYZ'],
        # sample_X=metadata_object['sample_X'],
        # sample_Y=metadata_object['sample_Y'],
        # sample_Z=metadata_object['sample_Z'],
        knifeEdge_XYZ_unit=metadata_object['knife-edge_XYZ_unit'],
        knifeEdge_XYZ_desc=metadata_object['knife-edge_XYZ_desc'],
        knifeEdge_XYZ=metadata_object['knife-edge_XYZ'],
        # knifeEdge_X=metadata_object['knife-edge_X'],
        # knifeEdge_Y=metadata_object['knife-edge_Y'],
        # knifeEdge_Z=metadata_object['knife-edge_Z'],
        knifeEdge_knifeScan_unit=metadata_object['knife-edge_knifeScan_unit'],
        knifeEdge_knifeScan=metadata_object['knife-edge_knifeScan'],
        # scan_dim=metadata_object['scan_dim'],
        # scan_npts=metadata_object['scan_npts'],
        # scan_after=metadata_object['scan_after'],
        # scan_positionerSettle_unit=metadata_object['scan_positionerSettle_unit'],
        # scan_positionerSettle=metadata_object['scan_positionerSettle'],
        # scan_detectorSettle_unit=metadata_object['scan_detectorSettle_unit'],
        # scan_detectorSettle=metadata_object['scan_detectorSettle'],
        # scan_beforePV_VAL=metadata_object['scan_beforePV_VAL'],
        # scan_beforePV_wait=metadata_object['scan_beforePV_wait'],
        # scan_beforePV=metadata_object['scan_beforePV'],
        # scan_afterPV_VAL=metadata_object['scan_afterPV_VAL'],
        # scan_afterPV_wait=metadata_object['scan_afterPV_wait'],
        # scan_afterPV=metadata_object['scan_afterPV'],
        # scan_positioner_PV=metadata_object['scan_positioner_PV'],
        # scan_positioner_ar=metadata_object['scan_positioner_ar'],
        # scan_positioner_mode=metadata_object['scan_positioner_mode'],
        # scan_positioner_1=metadata_object['scan_positioner_1'],
        # scan_positioner_2=metadata_object['scan_positioner_2'],
        # scan_positioner_3=metadata_object['scan_positioner_3'],
        # scan_detectorTrig_PV=metadata_object['scan_detectorTrig_PV'],
        # scan_detectorTrig_VAL=metadata_object['scan_detectorTrig_VAL'],
        # scan_detectors=metadata_object['scan_detectors'],
        mda_file=metadata_object['mda_file'],
        scanEnd_abort=metadata_object['scanEnd_abort'],
        scanEnd_time_epoch=convert_epoch_string_to_int(metadata_object['scanEnd_time_epoch']),
        scanEnd_time=metadata_object['scanEnd_time'],
        scanEnd_scanDuration_unit=metadata_object['scanEnd_scanDuration_unit'],
        scanEnd_scanDuration=metadata_object['scanEnd_scanDuration'],
        # scanEnd_cpt=metadata_object['scanEnd_cpt'],
        scanEnd_source_beamBad=metadata_object['scanEnd_source_beamBad'],
        scanEnd_source_ringCurrent_unit=metadata_object['scanEnd_source_ringCurrent_unit'],
        scanEnd_source_ringCurrent=metadata_object['scanEnd_source_ringCurrent'],
    )
    return metadata_row


def import_scan_row(scan_object):
    """
    Reads a yaml file and creates a new Scan ORM object with 
    the base data of the file
    """

    scan_row = db_schema.Scan(

        scanNumber=scan_object['scanNumber'],
        scan_dim=scan_object['scan_dim'],
        scan_npts=scan_object['scan_npts'],
        scan_after=scan_object['scan_after'],
        # scan_positionerSettle_unit=scan_object['scan_positionerSettle_unit'],
        # scan_positionerSettle=scan_object['scan_positionerSettle'],
        # scan_detectorSettle_unit=scan_object['scan_detectorSettle_unit'],
        # scan_detectorSettle=scan_object['scan_detectorSettle'],
        # scan_beforePV_VAL=scan_object['scan_beforePV_VAL'],
        # scan_beforePV_wait=scan_object['scan_beforePV_wait'],
        # scan_beforePV=scan_object['scan_beforePV'],
        # scan_afterPV_VAL=scan_object['scan_afterPV_VAL'],
        # scan_afterPV_wait=scan_object['scan_afterPV_wait'],
        # scan_afterPV=scan_object['scan_afterPV'],
        scan_positioner1_PV=scan_object['scan_positioner1_PV'],
        scan_positioner1_ar=scan_object['scan_positioner1_ar'],
        scan_positioner1_mode=scan_object['scan_positioner1_mode'],
        scan_positioner1=scan_object['scan_positioner1'],
        scan_positioner2_PV=scan_object['scan_positioner2_PV'],
        scan_positioner2_ar=scan_object['scan_positioner2_ar'],
        scan_positioner2_mode=scan_object['scan_positioner2_mode'],
        scan_positioner2=scan_object['scan_positioner2'],
        scan_positioner3_PV=scan_object['scan_positioner3_PV'],
        scan_positioner3_ar=scan_object['scan_positioner3_ar'],
        scan_positioner3_mode=scan_object['scan_positioner3_mode'],
        scan_positioner3=scan_object['scan_positioner3'],
        scan_positioner4_PV=scan_object['scan_positioner4_PV'],
        scan_positioner4_ar=scan_object['scan_positioner4_ar'],
        scan_positioner4_mode=scan_object['scan_positioner4_mode'],
        scan_positioner4=scan_object['scan_positioner4'],
        scan_detectorTrig1_PV=scan_object['scan_detectorTrig1_PV'],
        scan_detectorTrig1_VAL=scan_object['scan_detectorTrig1_VAL'],
        scan_detectorTrig2_PV=scan_object['scan_detectorTrig2_PV'],
        scan_detectorTrig2_VAL=scan_object['scan_detectorTrig2_VAL'],
        scan_detectorTrig3_PV=scan_object['scan_detectorTrig3_PV'],
        scan_detectorTrig3_VAL=scan_object['scan_detectorTrig3_VAL'],
        scan_detectorTrig4_PV=scan_object['scan_detectorTrig4_PV'],
        scan_detectorTrig4_VAL=scan_object['scan_detectorTrig4_VAL'],
        # scan_detectors=metadata_object['scan_detectors'],
        scan_cpt=scan_object['scan_cpt'],
    )
    return scan_row


def import_catalog_row(catalog_object):

    catalog_row = db_schema.Catalog(
        scanNumber=catalog_object['scanNumber'],

        filefolder=catalog_object['filefolder'],
        filenamePrefix=catalog_object['filenamePrefix'],

        aperture=catalog_object['aperture']['options'],
        sample_name=catalog_object['sample_name'],
        notes=catalog_object['notes'],
    )
    return catalog_row


def import_recon_row(recon_object):
    """
    Reads a yaml file and creates a new Recon ORM object with 
    the base data of the file
    """

    # Optional Params
    use_gpu = recon_object['comp']['use_gpu'] if 'use_gpu' in recon_object['comp'] else False
    batch_size = recon_object['comp']['batch_size'] if 'batch_size' in recon_object['comp'] else 1

    recon_row = db_schema.Recon(
        file_path=recon_object['file']['path'],
        file_output=recon_object['file']['output'],
        file_range=recon_object['file']['range'],
        file_threshold=recon_object['file']['threshold'],
        file_frame=recon_object['file']['frame'],
        #file_offset=recon_object['file']['offset'],
        file_ext=recon_object['file']['ext'],
        file_stacked=recon_object['file']['stacked'],
        file_h5_key=recon_object['file']['h5']['key'],

        comp_server=recon_object['comp']['server'],
        comp_workers=recon_object['comp']['workers'],
        comp_usegpu=use_gpu,
        comp_batch_size=batch_size,

        geo_mask_path=recon_object['geo']['mask']['path'],
        geo_mask_reversed=recon_object['geo']['mask']['reversed'],
        geo_mask_bitsizes=recon_object['geo']['mask']['bitsizes'],
        geo_mask_thickness=recon_object['geo']['mask']['thickness'],
        geo_mask_resolution=recon_object['geo']['mask']['resolution'],
        geo_mask_smoothness=recon_object['geo']['mask']['smoothness'],
        geo_mask_alpha=recon_object['geo']['mask']['alpha'],
        geo_mask_widening=recon_object['geo']['mask']['widening'],
        geo_mask_pad=recon_object['geo']['mask']['pad'],
        geo_mask_stretch=recon_object['geo']['mask']['stretch'],
        geo_mask_shift=recon_object['geo']['mask']['shift'],

        geo_mask_focus_cenx=recon_object['geo']['mask']['focus']['cenx'],
        geo_mask_focus_dist=recon_object['geo']['mask']['focus']['dist'],
        geo_mask_focus_anglez=recon_object['geo']['mask']['focus']['anglez'],
        geo_mask_focus_angley=recon_object['geo']['mask']['focus']['angley'],
        geo_mask_focus_anglex=recon_object['geo']['mask']['focus']['anglex'],
        geo_mask_focus_cenz=recon_object['geo']['mask']['focus']['cenz'],

        geo_mask_cal_id=recon_object['geo']['mask']['cal']['id'],
        geo_mask_cal_path=recon_object['geo']['mask']['cal']['path'],

        geo_scanner_step=recon_object['geo']['scanner']['step'],
        geo_scanner_rot=recon_object['geo']['scanner']['rot'],
        geo_scanner_axis=recon_object['geo']['scanner']['axis'],

        geo_detector_shape=recon_object['geo']['detector']['shape'],
        geo_detector_size=recon_object['geo']['detector']['size'],
        geo_detector_rot=recon_object['geo']['detector']['rot'],
        geo_detector_pos=recon_object['geo']['detector']['pos'],

        geo_source_offset=recon_object['geo']['source']['offset'],
        geo_source_grid=recon_object['geo']['source']['grid'],

        algo_iter=recon_object['algo']['iter'],

        algo_pos_method=recon_object['algo']['pos']['method'],
        algo_pos_regpar=recon_object['algo']['pos']['regpar'],
        algo_pos_init=recon_object['algo']['pos']['init'],

        algo_sig_recon=recon_object['algo']['sig']['recon'],
        algo_sig_method=recon_object['algo']['sig']['method'],
        algo_sig_order=recon_object['algo']['sig']['order'],
        algo_sig_scale=recon_object['algo']['sig']['scale'],
        
        algo_sig_init_maxsize=recon_object['algo']['sig']['init']['maxsize'],
        algo_sig_init_avgsize=recon_object['algo']['sig']['init']['avgsize'],
        algo_sig_init_atol=recon_object['algo']['sig']['init']['atol'],

        algo_ene_recon=recon_object['algo']['ene']['recon'],
        algo_ene_exact=recon_object['algo']['ene']['exact'],
        algo_ene_method=recon_object['algo']['ene']['method'],
        algo_ene_range=recon_object['algo']['ene']['range'],
    )
    return recon_row

def create_config_obj(recon):
    config_dict = {
            'file':
                {
                'path':recon.file_path,
                'output':recon.file_output,
                'range':recon.file_range+[1], #temp
                'threshold':recon.file_threshold,
                'frame':recon.file_frame,
                #':recon.file_offset, #temp
                'ext':recon.file_ext,
                'stacked':recon.file_stacked,
                'h5':
                    {
                    'key':recon.file_h5_key,
                    },
                },
            'comp':
                {
                'server':recon.comp_server,
                'workers':recon.comp_workers,
                'functionid':'d8461388-9442-4008-a5f1-2cfa112f6923', #temp
                'usegpu':recon.comp_usegpu,
                'batch_size':recon.comp_batch_size,
                },
            'geo':
                {
                'mask':
                    {
                    'path':recon.geo_mask_path,
                    'reversed':recon.geo_mask_reversed,
                    'bitsizes':recon.geo_mask_bitsizes,
                    'thickness':recon.geo_mask_thickness,
                    'resolution':recon.geo_mask_resolution,
                    'smoothness':recon.geo_mask_smoothness,
                    'alpha':recon.geo_mask_alpha,
                    'widening':recon.geo_mask_widening,
                    'pad':recon.geo_mask_pad,
                    'stretch':recon.geo_mask_stretch,
                    'shift':recon.geo_mask_shift,
                    'focus':
                        {
                        'cenx':recon.geo_mask_focus_cenx,
                        'dist':recon.geo_mask_focus_dist,
                        'anglez':recon.geo_mask_focus_anglez,
                        'angley':recon.geo_mask_focus_angley,
                        'anglex':recon.geo_mask_focus_anglex,
                        'cenz':recon.geo_mask_focus_cenz,
                        },
                    'cal':
                        {
                        'id':recon.geo_mask_cal_id,
                        'path':recon.geo_mask_cal_path,
                        },
                    },
                'scanner':
                    {
                    'step':recon.geo_scanner_step,
                    'rot':recon.geo_scanner_rot,
                    'axis':recon.geo_scanner_axis,
                    },
                'detector':
                    {
                    'shape':recon.geo_detector_shape,
                    'size':recon.geo_detector_size,
                    'rot':recon.geo_detector_rot,
                    'pos':recon.geo_detector_pos,
                    },
                'source':
                    {
                    'offset':recon.geo_source_offset,
                    'grid':recon.geo_source_grid,
                    },
                },
            'algo':
                {
                'iter':recon.algo_iter,
                'pos':
                    {
                    'method':recon.algo_pos_method,
                    'regpar':recon.algo_pos_regpar,
                    'init':recon.algo_pos_init,
                    },
                'sig':
                    {
                    'recon':recon.algo_sig_recon,
                    'method':recon.algo_sig_method,
                    'order':recon.algo_sig_order,
                    'scale':recon.algo_sig_scale,
                    'init':
                        {
                        'maxsize':recon.algo_sig_init_maxsize,
                        'avgsize':recon.algo_sig_init_avgsize,
                        'atol':recon.algo_sig_init_atol,
                        },
                    },
                'ene':
                    {
                    'recon':recon.algo_ene_recon,
                    'exact':recon.algo_ene_exact,
                    'method':recon.algo_ene_method,
                    'range':recon.algo_ene_range,
                    },
                }
            }
    return config_dict


def import_peakindex_row(peakindex_object):
    """
    Reads a yaml file and creates a new PeakIndex ORM object with 
    the base data of the file
    """

    # Optional Params
    #use_gpu = peakindex_object['comp']['use_gpu'] if 'use_gpu' in peakindex_object['comp'] else False
    #batch_size = peakindex_object['comp']['batch_size'] if 'batch_size' in peakindex_object['comp'] else 1

    peakindex_row = db_schema.PeakIndex(        
        # peakProgram=peakindex_object['peakProgram'],
        threshold=peakindex_object['threshold'],
        thresholdRatio=peakindex_object['thresholdRatio'],
        maxRfactor=peakindex_object['maxRfactor'],
        boxsize=peakindex_object['boxsize'],
        max_number=peakindex_object['max_peaks'], # NOTE: Duplicate of max_peaks
        min_separation=peakindex_object['min_separation'],
        peakShape=peakindex_object['peakShape'],
        scanPointStart=peakindex_object['scanPointStart'],
        scanPointEnd=peakindex_object['scanPointEnd'],
        # depthRangeStart=peakindex_object['depthRangeStart'],
        # depthRangeEnd=peakindex_object['depthRangeEnd'],
        detectorCropX1=peakindex_object['detectorCropX1'],
        detectorCropX2=peakindex_object['detectorCropX2'],
        detectorCropY1=peakindex_object['detectorCropY1'],
        detectorCropY2=peakindex_object['detectorCropY2'],
        min_size=peakindex_object['min_size'],
        max_peaks=peakindex_object['max_peaks'],
        smooth=peakindex_object['smooth'],
        maskFile=peakindex_object['maskFile'],
        indexKeVmaxCalc=peakindex_object['indexKeVmaxCalc'],
        indexKeVmaxTest=peakindex_object['indexKeVmaxTest'],
        indexAngleTolerance=peakindex_object['indexAngleTolerance'],
        indexH=peakindex_object['indexH'],
        indexK=peakindex_object['indexK'],
        indexL=peakindex_object['indexL'],
        indexCone=peakindex_object['indexCone'],
        energyUnit=peakindex_object['energyUnit'],
        exposureUnit=peakindex_object['exposureUnit'],
        cosmicFilter=peakindex_object['cosmicFilter'],
        recipLatticeUnit=peakindex_object['recipLatticeUnit'],
        latticeParametersUnit=peakindex_object['latticeParametersUnit'],
        peaksearchPath=None,
        p2qPath=None,
        indexingPath=None,
        outputFolder=peakindex_object['outputFolder'],
        filefolder=peakindex_object['filefolder'],
        filenamePrefix=peakindex_object['filenamePrefix'],
        geoFile=peakindex_object['geoFile'],
        crystFile=peakindex_object['crystFile'],
        depth=peakindex_object['depth'],
        beamline=peakindex_object['beamline'],
        # cosmicFilter=peakindex_object['cosmicFilter'],
    )
    return peakindex_row

def create_peakindex_config_obj(peakindex):
    config_dict = {
            # 'peakProgram':peakindex.peakProgram,
            'threshold':peakindex.threshold,
            'thresholdRatio':peakindex.thresholdRatio,
            'maxRfactor':peakindex.maxRfactor,
            'boxsize':peakindex.boxsize,
            'max_number':peakindex.max_number,
            'min_separation':peakindex.min_separation,
            'peakShape':peakindex.peakShape,
            'scanPointStart':peakindex.scanPointStart,
            'scanPointEnd':peakindex.scanPointEnd,
            # 'depthRangeStart':peakindex.depthRangeStart,
            # 'depthRangeEnd':peakindex.depthRangeEnd,
            'detectorCropX1':peakindex.detectorCropX1,
            'detectorCropX2':peakindex.detectorCropX2,
            'detectorCropY1':peakindex.detectorCropY1,
            'detectorCropY2':peakindex.detectorCropY2,
            'min_size':peakindex.min_size,
            'max_peaks':peakindex.max_peaks,
            'smooth':peakindex.smooth,
            'maskFile':peakindex.maskFile,
            'indexKeVmaxCalc':peakindex.indexKeVmaxCalc,
            'indexKeVmaxTest':peakindex.indexKeVmaxTest,
            'indexAngleTolerance':peakindex.indexAngleTolerance,
            'indexH':peakindex.indexH,
            'indexK':peakindex.indexK,
            'indexL':peakindex.indexL,
            'indexCone':peakindex.indexCone,
            'energyUnit':peakindex.energyUnit,
            'exposureUnit':peakindex.exposureUnit,
            'cosmicFilter':peakindex.cosmicFilter,
            'recipLatticeUnit':peakindex.recipLatticeUnit,
            'latticeParametersUnit':peakindex.latticeParametersUnit,
            'peaksearchPath':peakindex.peaksearchPath,
            'p2qPath':peakindex.p2qPath,
            'indexingPath':peakindex.indexingPath,
            'outputFolder':peakindex.outputFolder,
            'filefolder':peakindex.filefolder,
            'filenamePrefix':peakindex.filenamePrefix,
            'geoFile':peakindex.geoFile,
            'crystFile':peakindex.crystFile,
            'depth':peakindex.depth,
            'beamline':peakindex.beamline,
            # 'cosmicFilter':peakindex.cosmicFilter,
            }
    return config_dict


def get_catalog_data(session, scan_number, root_path="", CATALOG_DEFAULTS=None):
    """
    Helper function to get catalog data for a scan and compute data_path
    
    Args:
        session: SQLAlchemy session object
        scan_number: The scan number to look up
        root_path: The root path to use for computing relative data_path (default: "")
        CATALOG_DEFAULTS: Dictionary with default values (default: None)
        
    Returns:
        dict with catalog data including computed data_path
    """
    catalog_data = session.query(db_schema.Catalog).filter(
        db_schema.Catalog.scanNumber == scan_number
    ).first()
    
    if catalog_data:
        # Compute data_path as the portion of filefolder after root_path
        filefolder = catalog_data.filefolder
        
        # Use the utility function to remove root_path prefix
        data_path = remove_root_path_prefix(filefolder, root_path)
        
        return {
            "filefolder": filefolder,
            "filenamePrefix": catalog_data.filenamePrefix,
            "data_path": data_path
        }
    else:
        # Return defaults if no catalog entry found
        # Use CATALOG_DEFAULTS if provided, otherwise empty strings
        if CATALOG_DEFAULTS:
            filefolder = CATALOG_DEFAULTS.get("filefolder", "")
            return {
                "filefolder": filefolder,
                "filenamePrefix": CATALOG_DEFAULTS.get("filenamePrefix", ""),
                "data_path": filefolder  # Use full path as data_path for defaults
            }
        else:
            return {
                "filefolder": "",
                "filenamePrefix": "",
                "data_path": ""
            }


def get_next_id(session, table_class):
    """
    Get the next available ID for a given table by finding the maximum ID and incrementing it.
    
    Args:
        session: SQLAlchemy session object
        table_class: The SQLAlchemy table class (e.g., db_schema.WireRecon)
        
    Returns:
        int: The next available ID (max_id + 1, or 1 if table is empty)
    """
    # Get the primary key column dynamically
    primary_key_columns = list(table_class.__table__.primary_key.columns)
    
    if not primary_key_columns:
        raise ValueError(f"Table {table_class.__name__} has no primary key")
    
    # Assume single column primary key
    primary_key_column = primary_key_columns[0]
    
    # Query for the maximum value of the primary key
    max_id = session.query(sqlalchemy.func.max(primary_key_column)).scalar()
    
    # Return next ID (1 if table is empty, otherwise max_id + 1)
    return 1 if max_id is None else max_id + 1


def parse_parameter(parameter_value, num_inputs=None):
    """
    Parse a single parameter, splitting semicolon-separated values into a list.
    Optionally expand single values to match the number of inputs.
    
    This function is used to handle pooled scan submissions where multiple
    inputs are submitted together with their parameters separated by semicolons.
    
    Args:
        parameter_value: The parameter value (can be None, single value, or semicolon-separated string)
        num_inputs: Optional number of inputs to expand single values to match
        
    Returns:
        list: A list of values for this parameter
        
    Raises:
        ValueError: If the parameter has multiple values that don't match num_inputs
    """
    if parameter_value is None:
        values = [None]
    else:
        # Convert to string and check for semicolons
        str_value = str(parameter_value)
        if '; ' in str_value:
            # Split and handle 'None' strings
            values = []
            for v in str_value.split('; '):
                if v.lower() in ['none', '']:
                    values.append(None)
                else:
                    # v is a string from the split operation
                    # SQLAlchemy will handle type conversion when inserting
                    values.append(v)
        else:
            # Single value - check if it's a 'None' string
            if str_value.lower() in ['none', '']:
                values = [None]
            else:
                # Keep the original value (before string conversion)
                # This preserves the original type for single values
                values = [parameter_value]
    
    # If num_inputs is provided, handle expansion or validation
    if num_inputs is not None:
        if len(values) == 1 and num_inputs > 1:
            # Expand single value to match number of inputs
            values = values * num_inputs
        elif len(values) != num_inputs and len(values) != 1:
            # Error: mismatched lengths
            raise ValueError(f"Parameter has {len(values)} values but there are {num_inputs} inputs")
    
    return values
