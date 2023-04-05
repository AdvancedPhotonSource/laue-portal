from gladier import GladierBaseTool, generate_flow_definition

def qsub_launch(**data) -> int:
    import subprocess
    import shutil
    import os
    if not os.path.exists(data['out_dir']):
        os.makedirs(data['out_dir'])
    shutil.copy(data['im_dir'], data['out_dir'])
    proc_data = subprocess.call(['/usr/bin/bash', '/home/aps34ide/laue_src/laue-gladier/funcx_launch/launch_scripts/gladier_demand.sh', data['im_dir'], data['out_dir']]) 
    return proc_data

@generate_flow_definition(modifiers={
    qsub_launch: {'WaitTime': 1000000,
                      'ExceptionOnActionFailure': True}
})
class QSubLaunch(GladierBaseTool):
    funcx_functions = [qsub_launch]
    required_input = [
        'im_dir', 
        'out_dir',
        'funcx_endpoint_compute'
        ]