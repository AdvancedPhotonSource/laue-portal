"""
This file contains the definitions of the tables in the database.
We are currently using sqlalchemy ORMs to define the tables
"""
from typing import List
from typing import Optional
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Table, Column, Integer, String, DateTime, Float, Boolean, JSON

# Base class for all tables. Connects all ORM classes. 
class Base(DeclarativeBase):
    pass

class Metadata(Base):
    __tablename__ = "metadata"

    scanNumber: Mapped[int] = mapped_column(primary_key=True)

    time_epoch: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    time: Mapped[DateTime] = mapped_column(DateTime)
    user_name: Mapped[str] = mapped_column(String)

    source_beamBad: Mapped[str] = mapped_column(String) # Mapped[bool] = mapped_column(Boolean)
    source_CCDshutter: Mapped[str] = mapped_column(String) #bool?
    source_monoTransStatus: Mapped[str] = mapped_column(String) #bool?
    source_energy_unit: Mapped[str] = mapped_column(String)
    source_energy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source_IDgap_unit: Mapped[str] = mapped_column(String)
    source_IDgap: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source_IDtaper_unit: Mapped[str] = mapped_column(String) 
    source_IDtaper: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source_ringCurrent_unit: Mapped[str] = mapped_column(String)
    source_ringCurrent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    sample_XYZ_unit: Mapped[str] = mapped_column(String)
    sample_XYZ_desc: Mapped[str] = mapped_column(String)
    sample_XYZ: Mapped[str] = mapped_column(String)
    # sample_X: Mapped[float] = mapped_column(Float)
    # sample_Y: Mapped[float] = mapped_column(Float)
    # sample_Z: Mapped[float] = mapped_column(Float)

    knifeEdge_XYZ_unit: Mapped[str] = mapped_column(String)
    knifeEdge_XYZ_desc: Mapped[str] = mapped_column(String)
    knifeEdge_XYZ: Mapped[str] = mapped_column(String)
    # knifeEdge_X: Mapped[float] = mapped_column(Float)
    # knifeEdge_Y: Mapped[float] = mapped_column(Float)
    # knifeEdge_Z: Mapped[float] = mapped_column(Float)
    knifeEdge_knifeScan_unit: Mapped[str] = mapped_column(String)
    knifeEdge_knifeScan: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    #scan:

    mda_file: Mapped[str] = mapped_column(String)
    
    scanEnd_abort: Mapped[str] = mapped_column(String) # Mapped[bool] = mapped_column(Boolean)
    scanEnd_time_epoch: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    scanEnd_time: Mapped[str] = mapped_column(String) # DateTime?
    scanEnd_scanDuration_unit: Mapped[str] = mapped_column(String)
    scanEnd_scanDuration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # scanEnd_cpt: Mapped[int] = mapped_column(Integer)
    scanEnd_source_beamBad: Mapped[str] = mapped_column(String) # Mapped[bool] = mapped_column(Boolean)
    scanEnd_source_ringCurrent_unit: Mapped[str] = mapped_column(String)
    scanEnd_source_ringCurrent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # dataset_path: Mapped[str] = mapped_column(String)
    # dataset_filename: Mapped[str] = mapped_column(String)
    # dataset_type: Mapped[str] = mapped_column(String)
    # dataset_group: Mapped[str] = mapped_column(String)
    # start_time: Mapped[DateTime] = mapped_column(DateTime)
    # end_time: Mapped[DateTime] = mapped_column(DateTime)
    # start_image_num: Mapped[int] = mapped_column(Integer)
    # end_image_num: Mapped[int] = mapped_column(Integer)
    # total_points: Mapped[int] = mapped_column(Integer)
    # maskX_wireBaseX: Mapped[float] = mapped_column(Float)
    # maskY_wireBaseY: Mapped[float] = mapped_column(Float)
    # sr1_motor: Mapped[float] = mapped_column(Float)
    # motion: Mapped[float] = mapped_column(Float)
    # sr1_init: Mapped[float] = mapped_column(Float)
    # sr1_final: Mapped[float] = mapped_column(Float)
    # sr1_step: Mapped[float] = mapped_column(Float)
    # sr2_motor: Mapped[float] = mapped_column(Float)
    # sr2_init: Mapped[float] = mapped_column(Float)
    # sr2_final: Mapped[float] = mapped_column(Float)
    # sr2_step: Mapped[float] = mapped_column(Float)
    # sr3_motor: Mapped[float] = mapped_column(Float)
    # sr3_init: Mapped[float] = mapped_column(Float)
    # sr3_final: Mapped[float] = mapped_column(Float)
    # sr3_step: Mapped[float] = mapped_column(Float)
    # shift_parameter: Mapped[float] = mapped_column(Float)
    # exp_time: Mapped[float] = mapped_column(Float)
    # mda: Mapped[int] = mapped_column(Integer)
    # sampleXini: Mapped[float] = mapped_column(Float)
    # sampleYini: Mapped[float] = mapped_column(Float)
    # sampleZini: Mapped[float] = mapped_column(Float)
    # comment: Mapped[str] = mapped_column(String)

    # Parent of:
    scan_: Mapped["Scan"] = relationship(backref="metadata")
    catalog_: Mapped["Catalog"] = relationship(backref="metadata")
    calib_: Mapped["Calib"] = relationship(backref="metadata")
    recon_: Mapped["Recon"] = relationship(backref="metadata")
    wirerecon_: Mapped["WireRecon"] = relationship(backref="metadata")
    peakindex_: Mapped["PeakIndex"] = relationship(backref="metadata")

    def __repr__(self) -> str:
        pass # TODO: Consider implemeting for debugging


class Scan(Base):
    __tablename__ = "scan"

    id: Mapped[int] = mapped_column(primary_key=True)
    scanNumber: Mapped[int] = mapped_column(ForeignKey("metadata.scanNumber"))

    scan_dim: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    scan_npts: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    scan_after: Mapped[str] = mapped_column(String)  #bool?
    # scan_positionerSettle_unit: Mapped[str] = mapped_column(String)
    # scan_positionerSettle: Mapped[float] = mapped_column(Float)
    # scan_detectorSettle_unit: Mapped[str] = mapped_column(String)
    # scan_detectorSettle: Mapped[float] = mapped_column(Float)
    # scan_beforePV_VAL: Mapped[bool] = mapped_column(Boolean) #* #str?
    # scan_beforePV_wait: Mapped[bool] = mapped_column(Boolean) #* #str?
    # scan_beforePV: Mapped[str] = mapped_column(String) #*
    # scan_afterPV_VAL: Mapped[bool] = mapped_column(Boolean) #* #str?
    # scan_afterPV_wait: Mapped[bool] = mapped_column(Boolean) #* #str?
    # scan_afterPV: Mapped[str] = mapped_column(String)
    scan_positioner1_PV: Mapped[str] = mapped_column(String)
    scan_positioner1_ar: Mapped[str] = mapped_column(String) #bool?
    scan_positioner1_mode: Mapped[str] = mapped_column(String)
    scan_positioner1: Mapped[str] = mapped_column(String)
    scan_positioner2_PV: Mapped[str] = mapped_column(String)
    scan_positioner2_ar: Mapped[str] = mapped_column(String) #bool?
    scan_positioner2_mode: Mapped[str] = mapped_column(String)
    scan_positioner2: Mapped[str] = mapped_column(String)
    scan_positioner3_PV: Mapped[str] = mapped_column(String)
    scan_positioner3_ar: Mapped[str] = mapped_column(String) #bool?
    scan_positioner3_mode: Mapped[str] = mapped_column(String)
    scan_positioner3: Mapped[str] = mapped_column(String)
    scan_positioner4_PV: Mapped[str] = mapped_column(String)
    scan_positioner4_ar: Mapped[str] = mapped_column(String) #bool?
    scan_positioner4_mode: Mapped[str] = mapped_column(String)
    scan_positioner4: Mapped[str] = mapped_column(String)
    # scan_positioner_1: Mapped[float] = mapped_column(Float)
    # scan_positioner_2: Mapped[float] = mapped_column(Float)
    # scan_positioner_3: Mapped[float] = mapped_column(Float)
    scan_detectorTrig1_PV: Mapped[str] = mapped_column(String)
    scan_detectorTrig1_VAL: Mapped[str] = mapped_column(String) #int?
    scan_detectorTrig2_PV: Mapped[str] = mapped_column(String)
    scan_detectorTrig2_VAL: Mapped[str] = mapped_column(String) #int?
    scan_detectorTrig3_PV: Mapped[str] = mapped_column(String)
    scan_detectorTrig3_VAL: Mapped[str] = mapped_column(String) #int?
    scan_detectorTrig4_PV: Mapped[str] = mapped_column(String)
    scan_detectorTrig4_VAL: Mapped[str] = mapped_column(String) #int?
    # scan_detectors: Mapped[str] = mapped_column(String) #list?
    scan_cpt: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        pass # TODO: Consider implemeting for debugging


class Catalog(Base):
    __tablename__ = "catalog"

    catalog_id: Mapped[int] = mapped_column(primary_key=True)
    scanNumber: Mapped[int] = mapped_column(ForeignKey("metadata.scanNumber"), unique=True)

    filefolder: Mapped[str] = mapped_column(String) #infile
    filenamePrefix: Mapped[str] = mapped_column(String) #infile
    outputFolder: Mapped[str] = mapped_column(String) #outfile
    geoFile: Mapped[str] = mapped_column(String, nullable=True) #geofile
    
    aperture: Mapped[str] = mapped_column(String)
    sample_name: Mapped[str] = mapped_column(String, nullable=True)
    notes: Mapped[str] = mapped_column(String, nullable=True)


class Job(Base):
    __tablename__ = "job"

    job_id: Mapped[int] = mapped_column(primary_key=True)

    computer_name: Mapped[str] = mapped_column(String)
    status: Mapped[int] = mapped_column(Integer) #Queued, Running, Finished, Failed, Cancelled
    priority: Mapped[int] = mapped_column(Integer)
    submit_time: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    start_time: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    finish_time: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    author: Mapped[str] = mapped_column(String, nullable=True)
    notes: Mapped[str] = mapped_column(String, nullable=True)
    messages: Mapped[str] = mapped_column(String, nullable=True)

    # Parent of:
    subjob_: Mapped["SubJob"] = relationship(backref="job")
    calib_: Mapped["Calib"] = relationship(backref="job")
    recon_: Mapped["Recon"] = relationship(backref="job")
    wirerecon_: Mapped["WireRecon"] = relationship(backref="job")
    peakindex_: Mapped["PeakIndex"] = relationship(backref="job")


class SubJob(Base):
    __tablename__ = "subjob"

    subjob_id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("job.job_id"))

    status: Mapped[int] = mapped_column(Integer) #Queued, Running, Finished, Failed, Cancelled
    start_time: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    finish_time: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    messages: Mapped[str] = mapped_column(String, nullable=True)



class Calib(Base):
    __tablename__ = "calib"

    calib_id: Mapped[int] = mapped_column(primary_key=True)
    scanNumber: Mapped[int] = mapped_column(ForeignKey("metadata.scanNumber"))
    job_id: Mapped[int] = mapped_column(ForeignKey("job.job_id"), unique=True)

    calib_config: Mapped[str] = mapped_column(String)

    cenx: Mapped[float] = mapped_column(Float)
    dist: Mapped[float] = mapped_column(Float)
    anglez: Mapped[float] = mapped_column(Float)
    angley: Mapped[float] = mapped_column(Float)
    anglex: Mapped[float] = mapped_column(Float)
    cenz: Mapped[float] = mapped_column(Float)
    shift_parameter: Mapped[float] = mapped_column(Float)

    # Parent of:
    recon_: Mapped["Recon"] = relationship(backref="calib")
    #wirerecon_: Mapped["WireRecon"] = relationship(backref="calib")

    def __repr__(self) -> str:
        pass # TODO: Consider implemeting for debugging


class Recon(Base):
    __tablename__ = "recon"

    # Recon Metadata
    recon_id: Mapped[int] = mapped_column(primary_key=True)
    scanNumber: Mapped[int] = mapped_column(ForeignKey("metadata.scanNumber"))
    calib_id: Mapped[int] = mapped_column(ForeignKey("calib.calib_id"))
    job_id: Mapped[int] = mapped_column(ForeignKey("job.job_id"), unique=True)

    # Recon Parameters
    file_path: Mapped[str] = mapped_column(String)
    file_output: Mapped[str] = mapped_column(String)
    file_range: Mapped[list[int]] = mapped_column(JSON)
    file_threshold: Mapped[int] = mapped_column(Integer)
    file_frame: Mapped[list[int]] = mapped_column(JSON)
    #file_offset: Mapped[list[int]] = mapped_column(JSON)
    file_ext: Mapped[str] = mapped_column(String)
    file_stacked: Mapped[bool] = mapped_column(Boolean)
    file_h5_key: Mapped[str] = mapped_column(String)
    
    comp_server: Mapped[str] = mapped_column(String)
    comp_workers: Mapped[int] = mapped_column(Integer)
    comp_usegpu: Mapped[bool] = mapped_column(Boolean)
    comp_batch_size: Mapped[int] = mapped_column(Integer)
    
    geo_mask_path: Mapped[str] = mapped_column(String)
    geo_mask_reversed: Mapped[bool] = mapped_column(Boolean)
    geo_mask_bitsizes: Mapped[list[float]] = mapped_column(JSON)
    geo_mask_thickness: Mapped[float] = mapped_column(Float)
    geo_mask_resolution: Mapped[float] = mapped_column(Float)
    geo_mask_smoothness: Mapped[float] = mapped_column(Float)
    geo_mask_alpha: Mapped[float] = mapped_column(Float)
    geo_mask_widening: Mapped[float] = mapped_column(Float)
    geo_mask_pad: Mapped[float] = mapped_column(Float)
    geo_mask_stretch: Mapped[float] = mapped_column(Float)
    geo_mask_shift: Mapped[float] = mapped_column(Float)

    geo_mask_focus_cenx: Mapped[float] = mapped_column(Float)
    geo_mask_focus_dist: Mapped[float] = mapped_column(Float)
    geo_mask_focus_anglez: Mapped[float] = mapped_column(Float)
    geo_mask_focus_angley: Mapped[float] = mapped_column(Float)
    geo_mask_focus_anglex: Mapped[float] = mapped_column(Float)
    geo_mask_focus_cenz: Mapped[float] = mapped_column(Float)

    geo_mask_cal_id: Mapped[int] = mapped_column(Integer)
    geo_mask_cal_path: Mapped[str] = mapped_column(String)

    geo_scanner_step: Mapped[float] = mapped_column(Float)
    geo_scanner_rot: Mapped[list[float]] = mapped_column(JSON)
    geo_scanner_axis: Mapped[list[float]] = mapped_column(JSON)

    geo_detector_shape: Mapped[list[int]] = mapped_column(JSON)
    geo_detector_size: Mapped[list[float]] = mapped_column(JSON)
    geo_detector_rot: Mapped[list[float]] = mapped_column(JSON)
    geo_detector_pos: Mapped[list[float]] = mapped_column(JSON)

    geo_source_offset: Mapped[float] = mapped_column(Float)
    geo_source_grid: Mapped[list[float]] = mapped_column(JSON) # Consider splitting into components

    algo_iter: Mapped[int] = mapped_column(Integer)

    algo_pos_method: Mapped[str] = mapped_column(String)
    algo_pos_regpar: Mapped[int] = mapped_column(Integer)
    algo_pos_init: Mapped[str] = mapped_column(String)

    algo_sig_recon: Mapped[bool] = mapped_column(Boolean)
    algo_sig_method: Mapped[str] = mapped_column(String)
    algo_sig_order: Mapped[int] = mapped_column(Integer)
    algo_sig_scale: Mapped[int] = mapped_column(Integer)

    algo_sig_init_maxsize: Mapped[int] = mapped_column(Integer)
    algo_sig_init_avgsize: Mapped[int] = mapped_column(Integer)
    algo_sig_init_atol: Mapped[int] = mapped_column(Integer)
    
    algo_ene_recon: Mapped[bool] = mapped_column(Boolean)
    algo_ene_exact: Mapped[bool] = mapped_column(Boolean)
    algo_ene_method: Mapped[str] = mapped_column(String)
    algo_ene_range: Mapped[list[int]] = mapped_column(JSON)

    # Parent of:
    peakindex_: Mapped["PeakIndex"] = relationship(backref="recon")

    def __repr__(self) -> str:
        return f'Recon {self.recon_id}' # TODO: Consider implementing for debugging


class WireRecon(Base):
    __tablename__ = "wirerecon"

    # Wire Recon Metadata
    wirerecon_id: Mapped[int] = mapped_column(primary_key=True)
    scanNumber: Mapped[int] = mapped_column(ForeignKey("metadata.scanNumber"))
    # calib_id: Mapped[int] = mapped_column(ForeignKey("calib.calib_id"))
    job_id: Mapped[int] = mapped_column(ForeignKey("job.job_id"), unique=True)
    
    # Wire Recon Parameters
    depth_start: Mapped[float] = mapped_column(Float) #depth-start
    depth_end: Mapped[float] = mapped_column(Float) #depth-end
    depth_resolution: Mapped[float] = mapped_column(Float) #resolution

    # filefolder: Mapped[str] = mapped_column(String) #infile
    # filenamePrefix: Mapped[str] = mapped_column(String) #infile
    # outputFolder: Mapped[str] = mapped_column(String) #outfile
    # geoFile: Mapped[str] = mapped_column(String) #geofile

    # outputFolder: Mapped[str] = mapped_column(String) #outfile
    # filefolder: Mapped[str] = mapped_column(String) #infile
    # filenamePrefix: Mapped[str] = mapped_column(String) #infile
    # geoFile: Mapped[str] = mapped_column(String) #geofile
    # # geo_source_offset: Mapped[float] = mapped_column(Float)
    # geo_source_grid: Mapped[list[float]] = mapped_column(JSON) # depth-start; depth-end; resolution

    # Parent of:
    peakindex_: Mapped["PeakIndex"] = relationship(backref="wirerecon")

    def __repr__(self) -> str:
        return f'WireRecon {self.wirerecon_id}' # TODO: Consider implementing for debugging

class PeakIndex(Base):
    __tablename__ = "peakindex"

    # Peak Index Metadata
    peakindex_id: Mapped[int] = mapped_column(primary_key=True)
    scanNumber: Mapped[int] = mapped_column(ForeignKey("metadata.scanNumber"))
    job_id: Mapped[int] = mapped_column(ForeignKey("job.job_id"), unique=True)

    recon_id: Mapped[int] = mapped_column(ForeignKey("recon.recon_id"),nullable=True)
    wirerecon_id: Mapped[int] = mapped_column(ForeignKey("wirerecon.wirerecon_id"),nullable=True)

    # Peak Index Parameters
    # peakProgram: Mapped[str] = mapped_column(String)
    threshold: Mapped[int] = mapped_column(Integer)
    thresholdRatio: Mapped[int] = mapped_column(Integer)
    maxRfactor: Mapped[float] = mapped_column(Float)
    boxsize: Mapped[int] = mapped_column(Integer)
    max_number: Mapped[int] = mapped_column(Integer)
    min_separation: Mapped[int] = mapped_column(Integer)
    peakShape: Mapped[str] = mapped_column(String)
    scanPointStart: Mapped[int] = mapped_column(Integer)
    scanPointEnd: Mapped[int] = mapped_column(Integer)
    # depthRangeStart: Mapped[int] = mapped_column(Integer)
    # depthRangeEnd: Mapped[int] = mapped_column(Integer)
    detectorCropX1: Mapped[int] = mapped_column(Integer)
    detectorCropX2: Mapped[int] = mapped_column(Integer)
    detectorCropY1: Mapped[int] = mapped_column(Integer)
    detectorCropY2: Mapped[int] = mapped_column(Integer)
    min_size: Mapped[float] = mapped_column(Float)
    max_peaks: Mapped[int] = mapped_column(Integer)
    smooth: Mapped[bool] = mapped_column(Boolean) #Mapped[int] = mapped_column(Integer)
    maskFile: Mapped[str] = mapped_column(String, nullable=True)
    indexKeVmaxCalc: Mapped[float] = mapped_column(Float)
    indexKeVmaxTest: Mapped[float] = mapped_column(Float)
    indexAngleTolerance: Mapped[float] = mapped_column(Float)
    indexH: Mapped[int] = mapped_column(Integer)
    indexK: Mapped[int] = mapped_column(Integer)
    indexL: Mapped[int] = mapped_column(Integer)
    indexCone: Mapped[float] = mapped_column(Float)
    energyUnit: Mapped[str] = mapped_column(String)
    exposureUnit: Mapped[str] = mapped_column(String)
    cosmicFilter: Mapped[bool] = mapped_column(Boolean)
    recipLatticeUnit: Mapped[str] = mapped_column(String)
    latticeParametersUnit: Mapped[str] = mapped_column(String)
    peaksearchPath: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    p2qPath: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    indexingPath: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    outputFolder: Mapped[str] = mapped_column(String)
    filefolder: Mapped[str] = mapped_column(String)
    filenamePrefix: Mapped[str] = mapped_column(String)
    geoFile: Mapped[str] = mapped_column(String)
    crystFile: Mapped[str] = mapped_column(String)
    depth: Mapped[str] = mapped_column(String)
    beamline: Mapped[str] = mapped_column(String)
    # cosmicFilter: Mapped[bool] = mapped_column(Boolean)
    def __repr__(self) -> str:
        return f'Peak Index {self.peakindex_id}' # TODO: Consider implementing for debugging

# NOTE: Not Implemented
MASK_FOCUS_TABLE = [
                    'cenx (Z)',
                    'dist (Y)',
                    'anglez (angleX)',
                    'angley (angleY)',
                    'anglex (angleZ)',
                    'cenz (X)',
                    'shift parameter',
                    ]
