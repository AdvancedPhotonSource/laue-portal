"""
This file contains the definitions of the tables in the database.
We are currently using sqlalchemy ORMs to deifne the tables
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

    dataset_id: Mapped[int] = mapped_column(primary_key=True)
    dataset_path: Mapped[str] = mapped_column(String)
    dataset_filename: Mapped[str] = mapped_column(String)
    dataset_type: Mapped[str] = mapped_column(String)
    dataset_group: Mapped[str] = mapped_column(String)
    start_time: Mapped[DateTime] = mapped_column(DateTime)
    end_time: Mapped[DateTime] = mapped_column(DateTime)
    start_image_num: Mapped[int] = mapped_column(Integer)
    end_image_num: Mapped[int] = mapped_column(Integer)
    total_points: Mapped[int] = mapped_column(Integer)
    maskX_wireBaseX: Mapped[float] = mapped_column(Float)
    maskY_wireBaseY: Mapped[float] = mapped_column(Float)
    sr1_motor: Mapped[float] = mapped_column(Float)
    motion: Mapped[float] = mapped_column(Float)
    sr1_init: Mapped[float] = mapped_column(Float)
    sr1_final: Mapped[float] = mapped_column(Float)
    sr1_step: Mapped[float] = mapped_column(Float)
    sr2_motor: Mapped[float] = mapped_column(Float)
    sr2_init: Mapped[float] = mapped_column(Float)
    sr2_final: Mapped[float] = mapped_column(Float)
    sr2_step: Mapped[float] = mapped_column(Float)
    sr3_motor: Mapped[float] = mapped_column(Float)
    sr3_init: Mapped[float] = mapped_column(Float)
    sr3_final: Mapped[float] = mapped_column(Float)
    sr3_step: Mapped[float] = mapped_column(Float)
    shift_parameter: Mapped[float] = mapped_column(Float)
    exp_time: Mapped[float] = mapped_column(Float)
    mda: Mapped[int] = mapped_column(Integer)
    sampleXini: Mapped[float] = mapped_column(Float)
    sampleYini: Mapped[float] = mapped_column(Float)
    sampleZini: Mapped[float] = mapped_column(Float)
    comment: Mapped[str] = mapped_column(String)

    def __repr__(self) -> str:
        pass # TODO: Consider implemeting for debugging


class Calib(Base):
    __tablename__ = "calib"

    calib_id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[DateTime] = mapped_column(DateTime)
    commit_id: Mapped[str] = mapped_column(String)
    runtime: Mapped[str] = mapped_column(String)
    computer_name: Mapped[str] = mapped_column(String)
    calib_config: Mapped[str] = mapped_column(String)
    dataset_id: Mapped[int] = mapped_column(Integer) # Likely foreign key in the future
    dataset_path: Mapped[str] = mapped_column(String)
    dataset_filename: Mapped[str] = mapped_column(String)
    notes: Mapped[str] = mapped_column(String)
    cenx: Mapped[float] = mapped_column(Float)
    dist: Mapped[float] = mapped_column(Float)
    anglez: Mapped[float] = mapped_column(Float)
    angley: Mapped[float] = mapped_column(Float)
    anglex: Mapped[float] = mapped_column(Float)
    cenz: Mapped[float] = mapped_column(Float)
    shift_parameter: Mapped[float] = mapped_column(Float)
    comment: Mapped[str] = mapped_column(String)

    def __repr__(self) -> str:
        pass # TODO: Consider implemeting for debugging


class Recon(Base):
    __tablename__ = "recon"

    # Recon Metadata
    recon_id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[DateTime] = mapped_column(DateTime)
    commit_id: Mapped[str] = mapped_column(String)
    calib_id: Mapped[int] = mapped_column(Integer) # Likely foreign key in the future
    runtime: Mapped[str] = mapped_column(String)
    computer_name: Mapped[str] = mapped_column(String)
    dataset_id: Mapped[int] = mapped_column(Integer) # Likely foreign key in the future
    notes: Mapped[str] = mapped_column(String)

    # Recon Parameters
    file_path: Mapped[str] = mapped_column(String)
    file_output: Mapped[str] = mapped_column(String)
    file_range: Mapped[list[int]] = mapped_column(JSON)
    file_threshold: Mapped[int] = mapped_column(Integer)
    file_frame: Mapped[list[int]] = mapped_column(JSON)
    file_offset: Mapped[list[int]] = mapped_column(JSON)
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
    geo_source_grid: Mapped[list[float]] = mapped_column(JSON) # Consdier splitting into components

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

    def __repr__(self) -> str:
        return f'Recon {self.recon_id}' # TODO: Consider implemeting for debugging

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

