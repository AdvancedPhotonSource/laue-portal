import numpy as np
from pathlib import Path
import pandas as pd
import h5py
import fire
import warnings
warnings.filterwarnings('ignore')
import time
import logging
import cold
import laue_portal.recon.calib_indices as calib_indices

resolve_data = False #True #False

def make_pixels_df(idx_file,grain_file=None,grain_idx=0):
    #idx_file = 'laue_portal/recon/peaklist.txt'
    with open(idx_file,'rb') as f:
        lines = f.readlines()
    for i,l in enumerate(lines):
        #print(i)
        if 'peakList' in l.decode('ascii'):
            names_i = i
    names = (lines[names_i]).decode('ascii').replace('\n','').split('//')[-1].split()
    df = pd.read_csv(idx_file, encoding='latin1', sep='\s+', header=None, skiprows=names_i+1, names=names)
    return df

def read_indices(idx_file,grain_file=None,grain_idx=0):
    df = make_pixels_df(idx_file)
    indices = np.round(np.array(list(zip(df.iloc[:,1],df.iloc[:,0])))).astype(int)

    if grain_file:
        import laue_portal.recon.fn_LaueGopipline2 as LGp
        Peaks_calc = LGp.fn_readIndex(grain_file, 0) # 1 is to show the output
        grain_peaks = np.array(Peaks_calc[grain_idx])
        indices = indices[grain_peaks[:,10].astype(int)]

    return indices

def make_indexed_df(Midx_file,grain_file=None,grain_idx=0):
    with open(Midx_file,'rb') as f:
        lines = f.readlines()
    sel = ']'
    ls = []
    names_i = len(lines)
    for i,l in enumerate(lines):
        #print(i)
        l = l.decode('ascii').replace('\n','')
        if 'array0' in l:
            names_i = i
        #adds space for delimeter
        if sel in l:
            sel_i = l.index(sel)
            l = l[:sel_i+1] + ' ' + l[sel_i+1:]
        if i > names_i:
            l_list = [x for x in l.split('    ') if x]
            ls.append(l_list)
    names = (lines[names_i]).decode('ascii').replace('\n','').split()
    names = names[:1]+names[3:]
    df = pd.DataFrame(np.array(ls),columns=names)
    return df

def choose_indices(indices_selection):
    if isinstance(indices_selection, str):
        if '.' not in indices_selection:
            #exec(f'indices = calib_indices.{indices_selection}') problem here
            indices = calib_indices.CALIB_3_X1800 #CALIB_3_X1800_NO_TOPRIGHT
        else:
            #exec(f'indices = read_indices(indices_selection)') problem here
            indices = read_indices(indices_selection)
    elif isinstance(indices_selection, (list, tuple)):
        indices = np.array(indices_selection)
    elif isinstance(indices_selection, np.ndarray):
        indices = indices_selection
    return indices

def saveh5img(path, name, vals, inds, shape, frame=None, swap=False):
    _vals = cold.expand(vals, inds, shape)
    data = _vals #save(path, _vals, frame, swap)

#def save(path, data, frame=None, swap=False):
    """Saves Laue diffraction data to file."""

    if frame is not None:
        data = data[frame[0]:frame[1],frame[2]:frame[3]]
    if swap is True:
        data = np.swapaxes(data, 0, 2)
        data = np.swapaxes(data, 1, 2)

    with h5py.File(path+'.h5', 'a') as f:
        if name not in f.keys():
            f.create_dataset(name, data=data)

    logging.info(f"Saved: {name} in + {path}.h5") #logging.info("Saved: " + str(path) + ".tiff")

def define_vars(config_dict, indices_selection='CALIB_3_X1800'):
    # Load metadata
    file, comp, geo, algo = config_dict['file'], config_dict['comp'], config_dict['geo'], config_dict['algo'] #cold.config(path)

    #geo['mask']['shift'] += file['range'][0]*geo['scanner']['step']*0.001

    ind = choose_indices(indices_selection)
    n_ind = len(ind) #lau.shape[0]

    output_dir_str = file['output']
    output_dir = Path(output_dir_str); output_dir.mkdir(parents=True,exist_ok=True)
    
    name_elems = [f'_Nind{n_ind}',]
    name_append = '_'.join(name_elems)

    ind_file = str(output_dir / ('ind' + name_append))+'.npy'
    dat_file = str(output_dir / ('dat' + name_append))+'.npy'
    #
    pos_file = str(output_dir / ('pos' + name_append))+'.npy'
    sig_file = str(output_dir / ('sig' + name_append))+'.npy'
    scl_file = str(output_dir / ('scl' + name_append))+'.npy'
    ene_file = str(output_dir / ('ene' + name_append))+'.npy'
    #
    dep_file = output_dir / ('dep' + name_append)
    dep_file = str(dep_file)+'.npy'
    lau_file = str(output_dir / ('lau' + name_append))+'.npy'

    ### Return variables
    geo_vars = file, comp, geo, algo
    ind_vars = ind, n_ind
    dir_var = output_dir, name_append
    file_vars = ind_file, dat_file, \
                pos_file, sig_file, scl_file, ene_file, \
                dep_file, lau_file
    return geo_vars, ind_vars, dir_var, file_vars

def run_recon(config_dict, indices_selection='CALIB_3_X1800', debug=False):

    ### Recall variables
    geo_vars, ind_vars, dir_var, file_vars = define_vars(config_dict, indices_selection)
    file, comp, geo, algo = geo_vars
    ind, n_ind = ind_vars
    output_dir, name_append = dir_var
    ind_file, dat_file, \
    pos_file, sig_file, scl_file, ene_file, \
    dep_file, lau_file = file_vars

    # Load data
    if all([Path(f).exists() for f in file_vars[:2]]):
        ind = np.load(ind_file)
        dat = np.load(dat_file)
    else:
        #dat, ind = cold.load(file, collapsed=True, index=indices)
        dat, ind = cold.load(file, collapsed=True, index=ind)

        # Save data
        np.save(ind_file, ind)
        np.save(dat_file, dat)

    # Load results
    if (resolve_data == False) and all([Path(f).exists() for f in file_vars[2:]]):
        pos = np.load(pos_file)
        sig = np.load(sig_file)
        scl = np.load(scl_file)
        ene = np.load(ene_file)
        #
        dep = np.load(dep_file)
        lau = np.load(lau_file)

        t0 = t1 = t2 = time.time()
    else:
        # Resolve laue patterns
        t0 = time.time()
        pos, sig, scl, ene = cold.decode(dat, ind, comp, geo, algo, debug=debug)
        t1 = time.time()
        dep, lau = cold.resolve(dat, ind, pos, sig, geo, comp)
        t2 = time.time()

        # Save data
        np.save(pos_file, pos)
        np.save(sig_file, sig)
        np.save(scl_file, scl)
        np.save(ene_file, ene)
        #
        np.save(dep_file, dep)
        np.save(lau_file, lau)
    
    shape_, frame_ = (file['frame'][1], file['frame'][3]), file['frame']

    # # CoLD save
    # cold.saveplt(output_dir / ('dep' + name_append), dep, geo['source']['grid'])
    # cold.saveimg(str(output_dir / ('ene' + name_append)), ene, ind, shape_, frame_)
    # cold.saveimg(str(output_dir / ('pos' + name_append)), pos, ind, shape_, frame_)
    # cold.saveimg(str(output_dir / ('lau' + name_append)), lau, ind, shape_, frame_)
    # # cold.saveimg(file['output'] + '/lau' + str(len(ind)), lau, ind, (file['frame'][1], file['frame'][3]), file['frame'], swap=True)

    # HDF5 save
    h5path = str(output_dir / ('results' + name_append))
    saveh5img(h5path, 'ene', ene, ind, shape_, frame_)
    saveh5img(h5path, 'pos', pos, ind, shape_, frame_)
    saveh5img(h5path, 'lau', lau, ind, shape_, frame_)

    # # Save a copy of the config file in the output directory
    # config_path = Path(path)
    # local_config_path = output_dir/(config_path.name)
    # local_config_path.write_text(config_path.read_text())

    # Save a list if all indices used
    with open(output_dir/('indices' + name_append +'.txt'), 'w') as f:
        f.writelines('\n'.join([str(i) for i in ind]))

    t10 = t1-t0; t21 = t2-t1

    return t10, t21

def run_analysis(config_dict):
    ###temp
    config_dict['comp']['workers'] = 8
    config_dict['algo']['sig']['init']['avgsize'] = 10
    ###
    process = processes[0] #for process in processes:
    if process == 1:
        time_vals = run_recon(config_dict,indices_selection='CALIB_3_X1800')
    
    elif process == 2:
        idx_file = 'laue_portal/recon/Si1_XY.txt'
        #Midx_file = 'laue_portal/recon/Si1_Index.txt'

        # grain_file = 'laue_portal/recon//index_summed_img.txt'
        # grain_idx = 1 # 0 1
        time_vals = run_recon(config_dict,indices_selection=idx_file)

processes = [
             1,
             #2,
            ]

if __name__ == '__main__':
    fire.Fire(run_analysis)
