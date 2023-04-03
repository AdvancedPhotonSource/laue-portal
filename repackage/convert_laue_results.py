
import copy
import os
import h5py
import numpy as np
import time
import shutil
import argparse
from multiprocessing import cpu_count, Pool, shared_memory
from functools import partial
from subprocess import call

PTREPACK_PATH = '/APSshare/epd/rh6-x86_64/bin/ptrepack'
DATA_PATH = '/data/laue34/results'
OUT_PATH = '/data/laue34/repackaged'

def compress_remove_ds(attr_h5, out_path):
    f = h5py.File(attr_h5, 'r+')
    del f['entry1/data/data']
    f.close()

    tmp = os.path.join(out_path, 'temp.h5')
    command = [PTREPACK_PATH, "-o", "--chunkshape=auto", "--propindexes", attr_h5, tmp]
    call(command)

    os.remove(attr_h5)
    shutil.move(tmp, attr_h5)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('exp_name', help='experiment folder to look for')
    parser.add_argument('file_path', help='base filepath returned to the program by DM')
    return parser.parse_args()

start = time.time()
args = parse_args()

point_file = os.path.basename(args.file_path)
point_name = point_file.split('.')[0]

data_dir = os.path.join(DATA_PATH, args.exp_name, point_name, 'proc_results')
data_files = os.listdir(data_dir)

# create directory where results will go
new_dir = os.path.join(OUT_PATH, args.exp_name, point_name)
if not os.path.isdir(new_dir):
    os.makedirs(new_dir)
attr_file = os.path.join(DATA_PATH, args.exp_name, point_name, point_file)

if not os.path.isfile(attr_file):
    raise ValueError("ATTR_FILE does not exist")

copy_attr_file = os.path.join(OUT_PATH, args.exp_name, point_name, point_file)
shutil.copy(attr_file, copy_attr_file)
attr_file = copy_attr_file
compress_remove_ds(attr_file, OUT_PATH)

data_files = [data_dir + '/' + fn for fn in data_files]
# get shapes from the last file
ff = h5py.File(data_files[0], 'r')
stack = ff['lau'].shape[1]
frame = ff['frame']
y_dim = frame[3] - frame[2]
x_dim = y_dim
# find scannumber from the data_dir parent dir
parent_dir = os.path.dirname(data_dir)
scannumber = parent_dir.split('_')[-1]
print(scannumber)

lau_set_sm = shared_memory.SharedMemory(create=True, size=x_dim * y_dim * stack * 8)
lau_set = np.ndarray((x_dim, y_dim, stack), dtype=float, buffer=lau_set_sm.buf)

def process_chunk(filename, def_param=lau_set):
    f = h5py.File(filename, 'r')
    frame = f['frame']
    lau = f['lau']
    ind = f['ind']
    # adjust the index to the current frame and flatten it
    new_ind = (ind[:, 0] - frame[0]) * y_dim + ind[:, 1]
    # create a new ndarray that the laue will be expanded to according to index
    lau_arr = np.zeros(((frame[1] - frame[0]) * (frame[3] - frame[2]), lau.shape[1]))
    # fill out the laue values by index
    lau_arr[new_ind] = lau
    # reshape the array
    lau_arr = np.reshape(lau_arr, ((frame[1] - frame[0]), (frame[3] - frame[2]), lau.shape[1]))
    # write to the corresponding chunk of shared memory
    lau_set[frame[0] : frame[1], :, :] = lau_arr
    f.close()


pool_size = min(len(data_files), cpu_count() * 2)
pool = Pool(processes=pool_size)
pool.map(process_chunk, data_files)
pool.close()
pool.join()
pool.terminate()

mid = time.time()
print('mid time', mid - start)

def write_to_hd5(data_ind):
    (data, ind) = data_ind
    depth = np.array([scannumber])
    fn = new_dir + '/out_' + scannumber + '_' + str(ind) + '.h5'
    shutil.copyfile(attr_file, fn)
    f = h5py.File(fn, "r+")
    f.create_dataset('entry1/data/data', data=data)
    f.create_dataset('entry1/depth', data=depth)
    f.close()

iterable = [(lau_set[:, :, i], i) for i in range(stack)]
with Pool(processes=pool_size) as pool:
    pool.map_async(write_to_hd5, iterable)
    pool.close()
    pool.join()
    pool.terminate()

lau_set_sm.close()
lau_set_sm.unlink()

os.remove(attr_file)
stop = time.time()
print('took ', stop-start, 'secs')

