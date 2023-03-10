import matplotlib.pyplot as plt
import os
import numpy as np
import argparse
import json

"""
Reads qstat outputs from a queue and graphs the jobs started and completed over time.
"""


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('time_dir')
    return parser.parse_args()

FAILURE_THRESHOLD = [420, 900]
ENABLE_TIMED_FAILURES = False

started_jobs = []
started_jobs_timestamps = {}
finished_jobs = []

num_jobs_running = []
num_jobs_started = []
num_jobs_finished = []
timestamps = []
failures = []
failure_count = 0
cur_jobs_finished = 0
cur_jobs_started = 0


args = parse_args()
files = list(os.listdir(args.time_dir))
files = sorted(files, key=lambda filename: int(filename.split('.')[0]))
for file in files:
    with open(os.path.join(args.time_dir, file), 'r') as log_f:
        data = json.load(log_f)

    has_failure = 0

    if data['timestamp'] != "": 
        if 'Jobs' not in data:
            continue
        #print(file)
        jobs_finished = 0
        for started_job in started_jobs:
            if started_job not in data['Jobs']:
                started_jobs.remove(started_job)
                finished_jobs.append(started_job)
                cur_jobs_finished += 1
                jobs_finished += 1

                time_elapsed = int(data['timestamp']) - started_jobs_timestamps[started_job]
                if (time_elapsed < FAILURE_THRESHOLD[0] or time_elapsed > FAILURE_THRESHOLD[1]) and ENABLE_TIMED_FAILURES:
                    has_failure = 1
                    failure_count += 1
        
        failures.append(has_failure)

        running_jobs = 0
        for job in data['Jobs'].keys():
            if job not in started_jobs:
                started_jobs.append(job)
                started_jobs_timestamps[job] = int(data['timestamp'])
                cur_jobs_started += 1
            
            if data['Jobs'][job]['job_state'] != 'Q':
                running_jobs += 1
        
        
        num_jobs_started.append(cur_jobs_started) 
        num_jobs_finished.append(cur_jobs_finished)
        num_jobs_running.append(cur_jobs_finished + running_jobs)
        #print(len(data['Jobs'].keys()))
        timestamps.append(int(data['timestamp']))


    
failures = np.asarray(failures)
failures *= np.max(num_jobs_started)

plt.figure(figsize=(5,5))
plt.plot(timestamps, num_jobs_started, label='jobs queued')
plt.plot(timestamps, num_jobs_running, label='jobs running')
plt.plot(timestamps, num_jobs_finished, label='jobs finished')
#plt.bar(timestamps, failures, label='failures', width=50, color='red')
plt.fill_between(timestamps, num_jobs_started, 0)
plt.fill_between(timestamps, num_jobs_running, num_jobs_finished)
plt.fill_between(timestamps, num_jobs_finished, 0)
plt.legend(loc='upper left')
plt.title('Laue Processing Test (50 Nodes)')
plt.xlabel('Unix Timestamp')
plt.ylabel('Jobs')
plt.tight_layout()
plt.savefig('test.png', dpi=300)

print(cur_jobs_finished)
print(failure_count)

