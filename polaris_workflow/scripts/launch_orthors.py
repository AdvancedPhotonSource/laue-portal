import time
import shutil
import os
import json
import shutil
import subprocess

DELAY = 72

base_dir = '/data34b/Run2023-1/Sheyfer223_CodedAperture/Ni2_mask'

images = os.listdir(base_dir)
images = sorted(images, key=lambda x: int(x.split('.')[0].split('_')[-1]))

completed_fp = '/clhome/EPIX34ID/dev/src/completed_repacks.json'
with open(completed_fp, 'r') as comp_f:
   completed_ims = json.load(comp_f)

prev_im = None
for im in images:
    if im in completed_ims:
        continue
    im = f'consgeo_{im}'
    print(f'Launching {im}')
    call = [
        '/usr/bin/bash',
        '/clhome/EPIX34ID/dev/src/laue-gladier/repackage/orthros_queue.sh',
        'Feb23_COLD_ALCF_Demo',
        os.path.join(f'/clhome/EPIX34ID/dev/src/experiment_staging', im),
        '-N',
        im
    ]

    subprocess.call(call) 
    
    completed_ims[im] = True

    with open(completed_fp, 'w') as comp_f:
        json.dump(completed_ims, comp_f)
    
    print('waiting')

    time.sleep(DELAY)
    

