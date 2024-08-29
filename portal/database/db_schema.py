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
from sqlalchemy import Table, Column, Integer, String, DateTime, Float

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

    recon_id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[DateTime] = mapped_column(DateTime)
    commit_id: Mapped[str] = mapped_column(String)
    calib_id: Mapped[int] = mapped_column(Integer) # Likely foreign key in the future
    runtime: Mapped[str] = mapped_column(String)
    computer_name: Mapped[str] = mapped_column(String)
    recon_config: Mapped[str] = mapped_column(String)
    dataset_id: Mapped[int] = mapped_column(Integer) # Likely foreign key in the future
    dataset_path: Mapped[str] = mapped_column(String)
    dataset_filename: Mapped[str] = mapped_column(String)
    notes: Mapped[str] = mapped_column(String)
    depth_start: Mapped[float] = mapped_column(Float)
    depth_end: Mapped[float] = mapped_column(Float)
    depth_step: Mapped[float] = mapped_column(Float)
    cenx: Mapped[float] = mapped_column(Float)
    dist: Mapped[float] = mapped_column(Float)
    anglez: Mapped[float] = mapped_column(Float)
    angley: Mapped[float] = mapped_column(Float)
    anglex: Mapped[float] = mapped_column(Float)
    cenz: Mapped[float] = mapped_column(Float)
    shift_parameter: Mapped[float] = mapped_column(Float)
    folder_recon_results: Mapped[str] = mapped_column(String)
    pixel_mask: Mapped[str] = mapped_column(String)
    indexing_hpcs_cluster: Mapped[str] = mapped_column(String)

    def __repr__(self) -> str:
        pass # TODO: Consider implemeting for debugging

# NOTE: Not Implemented
MASK_FOCUT_TABLE = [
                    'cenx (Z)',
                    'dist (Y)',
                    'anglez (angleX)',
                    'angley (angleY)',
                    'anglex (angleZ)',
                    'cenz (X)',
                    'shift parameter',
                    ]

