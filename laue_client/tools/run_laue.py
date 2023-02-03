from gladier import GladierBaseTool, generate_flow_definition

def qsub_launch(**data) -> int:
    import subprocess
    proc_data = subprocess.call(['/usr/bin/bash', 'funcx_launch/launch_scripts/gladier_preempt.sh', data['im_dir'], data['out_dir']]) 
    return proc_data

@generate_flow_definition(modifiers={
    qsub_launch: {'WaitTime': 7200,
                      'ExceptionOnActionFailure': True}
})
class QSubLaunch(GladierBaseTool):
    funcx_functions = [qsub_launch]
    required_input = [
        'im_dir', 
        'out_dir',
        'funcx_endpoint_compute'
        ]