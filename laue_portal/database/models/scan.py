"""
Table of scan PV parameters extracted from MDA scan log XML.
"""
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String, Float, Boolean, ForeignKey
from laue_portal.database.base import Base


class Scan(Base):
    __tablename__ = "scan"

    id: Mapped[int] = mapped_column(primary_key=True)
    scanNumber: Mapped[int] = mapped_column(ForeignKey("metadata.scanNumber"))

    scan_dim: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    scan_npts: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    scan_after: Mapped[str] = mapped_column(String)  # bool?
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
    scan_positioner1_ar: Mapped[str] = mapped_column(String)  # bool?
    scan_positioner1_mode: Mapped[str] = mapped_column(String)
    scan_positioner1: Mapped[str] = mapped_column(String)
    scan_positioner2_PV: Mapped[str] = mapped_column(String)
    scan_positioner2_ar: Mapped[str] = mapped_column(String)  # bool?
    scan_positioner2_mode: Mapped[str] = mapped_column(String)
    scan_positioner2: Mapped[str] = mapped_column(String)
    scan_positioner3_PV: Mapped[str] = mapped_column(String)
    scan_positioner3_ar: Mapped[str] = mapped_column(String)  # bool?
    scan_positioner3_mode: Mapped[str] = mapped_column(String)
    scan_positioner3: Mapped[str] = mapped_column(String)
    scan_positioner4_PV: Mapped[str] = mapped_column(String)
    scan_positioner4_ar: Mapped[str] = mapped_column(String)  # bool?
    scan_positioner4_mode: Mapped[str] = mapped_column(String)
    scan_positioner4: Mapped[str] = mapped_column(String)
    # scan_positioner_1: Mapped[float] = mapped_column(Float)
    # scan_positioner_2: Mapped[float] = mapped_column(Float)
    # scan_positioner_3: Mapped[float] = mapped_column(Float)
    scan_detectorTrig1_PV: Mapped[str] = mapped_column(String)
    scan_detectorTrig1_VAL: Mapped[str] = mapped_column(String)  # int?
    scan_detectorTrig2_PV: Mapped[str] = mapped_column(String)
    scan_detectorTrig2_VAL: Mapped[str] = mapped_column(String)  # int?
    scan_detectorTrig3_PV: Mapped[str] = mapped_column(String)
    scan_detectorTrig3_VAL: Mapped[str] = mapped_column(String)  # int?
    scan_detectorTrig4_PV: Mapped[str] = mapped_column(String)
    scan_detectorTrig4_VAL: Mapped[str] = mapped_column(String)  # int?
    # scan_detectors: Mapped[str] = mapped_column(String) #list?
    scan_cpt: Mapped[int] = mapped_column(Integer)

    def __repr__(self) -> str:
        pass  # TODO: Consider implementing for debugging
