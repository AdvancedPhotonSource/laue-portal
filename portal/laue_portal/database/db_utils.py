import database.db_schema as db_schema
import config
import yaml
import sqlalchemy
import datetime

ENGINE = sqlalchemy.create_engine(f'sqlite:///{config.db_file}') 

def _clean(line):
    c = '#'
    if c in line: line = line[:line.index('#')-1]
    else: line = line.rstrip('\n').rstrip()
    return line

def import_recon_row(recon_object):
    """
    Reads a yaml file and creates a new Recon ORM object with 
    the base data of the file
    """

    # Optinal Params
    use_gpu = recon_object['comp']['use_gpu'] if 'use_gpu' in recon_object['comp'] else False
    batch_size = recon_object['comp']['batch_size'] if 'batch_size' in recon_object['comp'] else 1

    recon_row = db_schema.Recon(
        file_path=recon_object['file']['path'],
        file_output=recon_object['file']['output'],
        file_range=recon_object['file']['range'],
        file_threshold=recon_object['file']['threshold'],
        file_frame=recon_object['file']['frame'],
        file_offset=recon_object['file']['offset'],
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