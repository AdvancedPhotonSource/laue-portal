import copy
import os
import h5py
import numpy as np
import time
import shutil
import argparse
from functools import partial
from subprocess import call
import yaml
import glob

PTREPACK_PATH = '/APSshare/epd/rh6-x86_64/bin/ptrepack'
DATA_PATH = '/data/laue34/results'
OUT_PATH = '/data/laue34/repackaged'

def compress_remove_ds(attr_h5, out_path, ptrepack_path):
    f = h5py.File(attr_h5, 'r+')
    del f['entry1/data/data']
    f.close()

    tmp = os.path.join(out_path, 'temp.h5')
    command = [ptrepack_path, "-o", "--chunkshape=auto", "--propindexes", attr_h5, tmp]
    call(command)

    os.remove(attr_h5)
    shutil.move(tmp, attr_h5)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('exp_name', help='experiment folder to look for')
    parser.add_argument('file_path', help='base filepath returned to the program by DM')
    return parser.parse_args()

def process_chunk(args):
    filename, lau_set, y_dim = args
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

def write_to_hd5(args):
    data, ind, attr_file, new_dir, scannumber, depth = args
    depth = np.array([depth])
    fn = new_dir + '/out_' + scannumber + '_' + str(ind) + '.h5'
    shutil.copyfile(attr_file, fn)
    f = h5py.File(fn, "r+")
    f.create_dataset('entry1/data/data', data=data, dtype='float32')
    f.create_dataset('entry1/depth', data=depth, dtype='float32')
    f.close()


def apply_mask(data, parent_dir, threshold):
    mask = np.zeros((2048,2048), dtype='bool')
    mask[68:200,380:543] = 1
    mask[100:400,1100:1300] = 1
    mask[625:750,243:395] = 1
    mask[650:850,415:770] = 1
    mask[800:960,1300:1550] = 1
    mask[1166:1280,50:184] = 1
    mask[1275:1369,800:950] = 1
    mask[1370:1500,700:875] = 1
    mask[1383:1436,1740:1853] = 1
    mask[1460:1600,1787:1980] = 1
    mask[1501:1700,533:733] = 1
    mask[1863:1993,310:455] = 1
    mask[1925:2022,1236:1376] = 1

    base_h5 = glob.glob(os.path.join(parent_dir, '*.h5'))[0]
    with h5py.File(base_h5, 'r') as h5_f:
        base_data = np.asarray(h5_f['/entry1/data/data'])
    thresh_mask = np.any((base_data >= threshold), axis=0)

    mask = mask & thresh_mask
    
    return data * mask.astype('float')


def repackage_files(file_path, exp_name, data_path, out_path, ptrepack_path):
    start = time.time()

    point_file = os.path.basename(file_path)
    point_name = point_file.split('.')[0]

    data_dir = os.path.join(data_path, exp_name, point_name, 'proc_results')
    data_files = os.listdir(data_dir)

    # create directory where results will go
    new_dir = os.path.join(out_path, exp_name, point_name)
    if not os.path.isdir(new_dir):
        os.makedirs(new_dir)
    attr_file = os.path.join(data_path, exp_name, point_name, point_file)

    if not os.path.isfile(attr_file):
        raise ValueError("ATTR_FILE does not exist")

    copy_attr_file = os.path.join(out_path, exp_name, point_name, point_file)
    shutil.copy(attr_file, copy_attr_file)
    attr_file = copy_attr_file
    compress_remove_ds(attr_file, new_dir, ptrepack_path)

    data_files = [data_dir + '/' + fn for fn in data_files]
    # get shapes from the last file
    ff = h5py.File(data_files[0], 'r')
    print(f"{file_path}_{ff['lau'].shape}")
    stack = ff['lau'].shape[1]
    frame = ff['frame']
    y_dim = frame[3] - frame[2]
    x_dim = y_dim
    # find scannumber from the data_dir parent dir
    parent_dir = os.path.dirname(data_dir)
    scannumber = parent_dir.split('_')[-1]

    lau_set = np.ndarray((x_dim, y_dim, stack), dtype=float)

    data_files_load = [(data_fp, lau_set, y_dim) for data_fp in data_files]

    list(map(process_chunk, data_files_load))

    config_fp = glob.glob(os.path.join(parent_dir, '*.yml'))[0]
    with open(config_fp, 'r') as conf_f:
        config = yaml.safe_load(conf_f)
    
    start_depth = config['geo']['source']['grid'][0] * 1000 # mm -> um
    step = config['geo']['source']['grid'][2] * 1000

    lau_set = np.moveaxis(lau_set, 2, 0)
    lau_set = apply_mask(lau_set, parent_dir, 10.0)

    output_params = []
    for i in range(stack):
        depth = start_depth + (step * i)
        if depth >= -100.0 and depth <= 100.0:
            output_params.append((lau_set[i, :, :], len(output_params), attr_file, new_dir, scannumber, depth))

    list(map(write_to_hd5, output_params))

    os.remove(attr_file)
    stop = time.time()
    print(f'{file_path} took ', stop-start, 'secs')

def main():
    args = parse_args()
    repackage_files(args.file_path, 
                    args.exp_name,
                    DATA_PATH,
                    OUT_PATH,
                    PTREPACK_PATH)

if __name__ == '__main__':
    main()