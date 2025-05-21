import numpy as np
from pathlib import Path
import pandas as pd
import h5py
import fire
import logging
import cold
import laue_portal.recon.calib_indices as calib_indices

def savenpyimg(path, vals, inds, shape, frame=None, swap=False):
    _vals = cold.expand(vals, inds, shape)
    data = _vals #save(path, _vals, frame, swap)

#def save(path, data, frame=None, swap=False):
    """Saves Laue diffraction data to file."""

    if frame is not None:
        data = data[frame[0]:frame[1],frame[2]:frame[3]]
    if swap is True:
        data = np.swapaxes(data, 0, 2)
        data = np.swapaxes(data, 1, 2)

    with open(path+'.npy', 'wb') as f:
        if data.ndim > 2:
            saved_data = np.sum(data,axis=2)
        else:
            saved_data = data.copy()
        np.save(f, saved_data)

    logging.info(f"Saved: {path}.npy") #logging.info("Saved: " + str(path) + ".tiff")

def savenpyimg2(path, vals, frame=None, swap=False):
    data = vals

#def save(path, data, frame=None, swap=False):
    """Saves Laue diffraction data to file."""

    if frame is not None:
        data = data[frame[0]:frame[1],frame[2]:frame[3]]
    if swap is True:
        data = np.swapaxes(data, 0, 2)
        data = np.swapaxes(data, 1, 2)

    with open(path+'.npy', 'wb') as f:
        if data.ndim > 2:
            saved_data = np.sum(data,axis=2)
        else:
            saved_data = data.copy()
        np.save(f, saved_data)

    logging.info(f"Saved: {path}.npy") #logging.info("Saved: " + str(path) + ".tiff")

def saveh5basic(path, name, vals):

    with h5py.File(path+'.h5', 'a') as f:
        if name not in f.keys():
            f.create_dataset(name, data=vals)

    logging.info(f"Saved: {name} in + {path}.h5")

def loahdh5(path, key, results_filename = "results.h5"):
    h5_flag = '.h5'
    if h5_flag not in results_filename: results_filename += h5_flag
    results_file = Path(path)/results_filename
    f = h5py.File(results_file, 'r')
    value = f[key][:]
    #logging.info("Loaded: " + str(file))
    return value

def run_convert_h5_to_npyimg(output_dir=Path('data'),results_filename='1_recon'):
    
    #ind = loahdh5(output_dir, 'ind', results_filename)
    # ind = ind.T
    lau = loahdh5(output_dir, 'lau', results_filename)
    lau = lau.T

    # frame: [0, 2048, 0, 2048] # [pixels]
    # shape_, frame_ = (file['frame'][1], file['frame'][3]), file['frame']
    
    lau_shape_0 = lau.shape[0]; lau_shape_1 = lau.shape[1]; lau_shape_2 = lau.shape[2]
    frame = [0, lau_shape_0, 0, lau_shape_1]
    shape_, frame_ = (frame[1], frame[3]), frame

    ind = np.indices(shape_).T
    ind_new = ind.reshape(ind.shape[0]*ind.shape[1],ind.shape[2])

    #ind_new = ind.reshape(ind.shape[0]*lau_shape_1,ind.shape[2])
    lau_new = lau.reshape(lau_shape_0*lau_shape_1,lau_shape_2)

    # # CoLD save
    # cold.saveplt(output_dir / ('dep' + name_append), dep, geo['source']['grid'])
    # cold.saveimg(str(output_dir / ('ene' + name_append)), ene, ind, shape_, frame_)
    # cold.saveimg(str(output_dir / ('pos' + name_append)), pos, ind, shape_, frame_)
    # cold.saveimg(str(output_dir / ('lau' + name_append)), lau, ind, shape_, frame_)
    # # cold.saveimg(file['output'] + '/lau' + str(len(ind)), lau, ind, (file['frame'][1], file['frame'][3]), file['frame'], swap=True)

    results_filename += '_new'
    # # HDF5 save
    h5path_ = str(output_dir / ('img' + results_filename))# + name_append))
    # saveh5img(h5path_, 'ene', ene, ind, shape_, frame_)
    # saveh5img(h5path_, 'pos', pos, ind, shape_, frame_)
    # saveh5img(h5path_, 'lau', lau, ind, shape_, frame_)
    
    #savenpyimg(h5path_, lau_new, ind_new, shape_, frame_)
    savenpyimg2(h5path_, lau, frame_)

    h5path = str(output_dir / results_filename) #('basic' + 'results' + name_append))
    saveh5basic(h5path, 'ind', ind_new)
    # saveh5basic(h5path, 'ene', ene)
    # saveh5basic(h5path, 'pos', pos)
    # saveh5basic(h5path, 'sig', sig)
    saveh5basic(h5path, 'lau', lau_new)
output_dir=Path('data');results_filename='1_recon'
if __name__ == '__main__':
    fire.Fire(run_convert_h5_to_npyimg)
