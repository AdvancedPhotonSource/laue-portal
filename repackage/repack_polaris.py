import convert_laue_results_single as clr
import os
import json
import argparse
from mpi4py import MPI
import numpy as np

RESULTS_PATH = '/eagle/APSDataAnalysis/LAUE/results'
REPACKS_PATH = '/eagle/APSDataAnalysis/LAUE/repacks'
PTREPACK_PATH = '/eagle/APSDataAnalysis/mprince/lau_env_polaris/bin/ptrepack'
COMPLETED_FILES_FP = 'completed.json'
WIN_SIZE = 4

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('exp_name', help='experiment folder to look for')
    return parser.parse_args()


def allocate_window(rank, comm):
    if rank == 0:
        scanWinSize = WIN_SIZE
    else:
        scanWinSize = 0
    
    queue_win = MPI.Win.Allocate(scanWinSize, comm=comm)

    repack_idx = rank
    if rank == 0:
        queue_win.Lock(rank=0)
        queue_win.Put([comm.size.to_bytes(WIN_SIZE, 'little'), MPI.BYTE], target_rank=0)
        queue_win.Unlock(rank=0)
    
    comm.Barrier()

    return queue_win, repack_idx


def get_next_idx(queue_win):
    scanBuff = bytearray(WIN_SIZE)
    queue_win.Lock(rank=0)
    queue_win.Get([scanBuff, MPI.BYTE], target_rank=0)
    cur_idx = int.from_bytes(scanBuff, 'little')

    next_idx = cur_idx + 1
    queue_win.Put([next_idx.to_bytes(WIN_SIZE, 'little'), MPI.BYTE], target_rank=0)
    queue_win.Unlock(rank=0)

    return next_idx


def process_experiment(experiment_name):
    results_path = os.path.join(RESULTS_PATH, experiment_name)
    repacks_path = os.path.join(REPACKS_PATH, experiment_name)

    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()

    if rank == 0:
        if not os.path.exists(repacks_path):
            os.makedirs(repacks_path)
    comm.Barrier()
        
    files = list(os.listdir(results_path))

    filtered_files = []
    for file in files:
        # Check for bad files
        if (not file.endswith('_debug')
            and os.path.isdir(os.path.join(results_path, file))):
            filtered_files.append(file)
            
    filtered_files = sorted(filtered_files)

    queue_win, repack_idx = allocate_window(rank, comm)

    while repack_idx < len(filtered_files):
        clr.repackage_files(f'{filtered_files[repack_idx]}.h5', 
                            experiment_name, 
                            RESULTS_PATH,
                            REPACKS_PATH,
                            PTREPACK_PATH)
        repack_idx = get_next_idx(queue_win)
        print(f'{rank}, {repack_idx}')
        return
    
if __name__ == '__main__':
    args = parse_args()
    process_experiment(args.exp_name)