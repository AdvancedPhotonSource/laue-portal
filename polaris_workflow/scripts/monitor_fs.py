import time
import os
import json
import sys

WAIT_TIME = 20
base_dir = sys.argv[1]

out_dir = 'file_timings'
if not os.path.exists(out_dir):
    os.makedirs(out_dir)

time_passed = 0
while True:
    files = {}
    for file in os.listdir(base_dir):
        size = os.path.getsize(os.path.join(base_dir, file))
        files[file] = size

    with open(os.path.join(out_dir, f'{time_passed:05d}.json'), 'w') as out_f:
        json.dump(files, out_f)
    print(f"Wrote {os.path.join(out_dir, f'{time_passed:05d}.json')}")
    time.sleep(WAIT_TIME)
    time_passed += WAIT_TIME