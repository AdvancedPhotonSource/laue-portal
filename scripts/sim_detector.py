import time
import shutil
import os
import json
import shutil

DELAY = 0

base_dir = '/data34a/Run2023-1/Sheyfer323_NiWireMask/Ni2_50mN_mask'
staging_dir = '/clhome/EPIX34ID/dev/src/experiment_staging'

images = os.listdir(base_dir)
images = sorted(images, key=lambda x: int(x.split('.')[0].split('_')[-1]))

completed_fp = '/clhome/EPIX34ID/dev/src/completed_ims.json'
if not os.path.exists(completed_fp):
    completed_ims = {}
else:
    with open(completed_fp, 'r') as comp_f:
        completed_ims = json.load(comp_f)

prev_ims = [] 
for i in range(25):
    im = images[i]
    if im in completed_ims:
        continue
    print(f'copying: {im}')
    
    if len(prev_ims) > 30:
        os.remove(prev_ims.pop(0))
    prev_ims.append(os.path.join(staging_dir, f'{im}'))
    shutil.copy(os.path.join(base_dir, im), os.path.join(staging_dir, f'{im}'))
    
    completed_ims[im] = True

    with open(completed_fp, 'w') as comp_f:
        json.dump(completed_ims, comp_f)
    
    print('waiting')

    time.sleep(DELAY)
    

