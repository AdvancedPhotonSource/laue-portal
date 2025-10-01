"""
Table of peak indexing parameters and results.
"""
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String, Float, Boolean, JSON, ForeignKey
from laue_portal.database.base import Base


class PeakIndex(Base):
    __tablename__ = "peakindex"

    # Peak Index Metadata
    peakindex_id: Mapped[int] = mapped_column(primary_key=True)
    scanNumber: Mapped[int] = mapped_column(ForeignKey("metadata.scanNumber"))
    job_id: Mapped[int] = mapped_column(ForeignKey("job.job_id"), unique=True)

    filefolder: Mapped[str] = mapped_column(String)  # infile
    # filenamePrefix: Mapped[str] = mapped_column(String) # infile
    filenamePrefix: Mapped[list[str]] = mapped_column(JSON)  # infile

    author: Mapped[str] = mapped_column(String, nullable=True)
    notes: Mapped[str] = mapped_column(String, nullable=True)

    recon_id: Mapped[int] = mapped_column(ForeignKey("recon.recon_id"), nullable=True)
    wirerecon_id: Mapped[int] = mapped_column(ForeignKey("wirerecon.wirerecon_id"), nullable=True)

    # Peak Index Parameters
    # peakProgram: Mapped[str] = mapped_column(String)
    threshold: Mapped[int] = mapped_column(Integer)
    thresholdRatio: Mapped[int] = mapped_column(Integer)
    maxRfactor: Mapped[float] = mapped_column(Float)
    boxsize: Mapped[int] = mapped_column(Integer)
    max_number: Mapped[int] = mapped_column(Integer)
    min_separation: Mapped[int] = mapped_column(Integer)
    peakShape: Mapped[str] = mapped_column(String)
    # scanPointStart: Mapped[int] = mapped_column(Integer)
    # scanPointEnd: Mapped[int] = mapped_column(Integer)
    # depthRangeStart: Mapped[int] = mapped_column(Integer)
    # depthRangeEnd: Mapped[int] = mapped_column(Integer)
    scanPoints: Mapped[str] = mapped_column(String)  # String field for srange parsing
    scanPointslen: Mapped[int] = mapped_column(Integer)  # Cached value
    depthRange: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # String field for srange parsing
    depthRangelen: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Cached value
    detectorCropX1: Mapped[int] = mapped_column(Integer)
    detectorCropX2: Mapped[int] = mapped_column(Integer)
    detectorCropY1: Mapped[int] = mapped_column(Integer)
    detectorCropY2: Mapped[int] = mapped_column(Integer)
    min_size: Mapped[float] = mapped_column(Float)
    max_peaks: Mapped[int] = mapped_column(Integer)
    smooth: Mapped[bool] = mapped_column(Boolean)  # Mapped[int] = mapped_column(Integer)
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
    # peaksearchPath: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # p2qPath: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # indexingPath: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    outputFolder: Mapped[str] = mapped_column(String)
    # filefolder: Mapped[str] = mapped_column(String)
    # filenamePrefix: Mapped[str] = mapped_column(String)
    geoFile: Mapped[str] = mapped_column(String)
    crystFile: Mapped[str] = mapped_column(String)
    depth: Mapped[str] = mapped_column(String, nullable=True)
    beamline: Mapped[str] = mapped_column(String)

    def __repr__(self) -> str:
        return f"Peak Index {self.peakindex_id}"  # TODO: Consider implementing for debugging
