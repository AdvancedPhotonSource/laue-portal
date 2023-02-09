import time
import shutil

NUM_IMGS = 40
DELAY = 120


for i in range(NUM_IMGS):
    test_im = i % 9
    shutil.copy(f'testing_data/im_000{test_im}.h5', f'experiment_staging/test_11n_{i:04d}.h5')
    print(f'Copied im {test_im} to {i}')
    time.sleep(DELAY)