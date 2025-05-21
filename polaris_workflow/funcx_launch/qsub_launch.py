from funcx import FuncXExecutor
import subprocess
import json
import os


def main():
    with open('uids.json') as uuids_f:
        uuids = json.load(uuids_f)

    down_src_path = os.path.join('/eagle/APSDataAnalysis/mprince/lau/dev/laue-parallel/outputs/gladier_staging/all_recons/', 'al_400_test') # TEMP

    with FuncXExecutor(endpoint_id=uuids['endpoint']) as fxe:
        fut = fxe.submit(qsub_launch, down_src_path, 0)

    print(f'Call result {fut.result()}')


def qsub_launch(im_dir: str, im_num: int) -> int:
    import subprocess
    proc_data = subprocess.call(['/usr/bin/bash', 'funcx_launch/launch_scripts/gladier_debug.sh', im_dir, str(im_num)]) 
    return proc_data


if __name__ == '__main__':
    main()