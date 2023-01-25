from funcx import FuncXExecutor
import subprocess
import json


def main():
    with open('uids.json') as uuids_f:
        uuids = json.load(uuids_f)

    with FuncXExecutor(endpoint_id=uuids['endpoint']) as fxe:
        fut = fxe.submit(qsub_launch, "/eagle/APSDataAnalysis/mprince/lau/dev/laue-gladier/funcx_launch/launch_scripts/polaris_debug.sh")

    print(f'Call result {fut.result()}')


def qsub_launch(filepath: str) -> int:
    import subprocess
    proc_data = subprocess.call(['/usr/bin/bash', filepath]) 
    return proc_data


if __name__ == '__main__':
    main()