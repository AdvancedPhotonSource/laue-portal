"""
Contains scan data taken from the MDA scan log XML file.
"""
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, DateTime, Float
from laue_portal.database.base import Base


class Metadata(Base):
    __tablename__ = "metadata"

    scanNumber: Mapped[int] = mapped_column(primary_key=True)

    time_epoch: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    time: Mapped[DateTime] = mapped_column(DateTime)
    user_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    source_beamBad: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # Mapped[bool] = mapped_column(Boolean)
    source_CCDshutter: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # bool?
    source_monoTransStatus: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # bool?
    source_energy_unit: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source_energy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source_IDgap_unit: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source_IDgap: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source_IDtaper_unit: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source_IDtaper: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source_ringCurrent_unit: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source_ringCurrent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    sample_XYZ_unit: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    sample_XYZ_desc: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    sample_XYZ: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # sample_X: Mapped[float] = mapped_column(Float)
    # sample_Y: Mapped[float] = mapped_column(Float)
    # sample_Z: Mapped[float] = mapped_column(Float)

    knifeEdge_XYZ_unit: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    knifeEdge_XYZ_desc: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    knifeEdge_XYZ: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # knifeEdge_X: Mapped[float] = mapped_column(Float)
    # knifeEdge_Y: Mapped[float] = mapped_column(Float)
    # knifeEdge_Z: Mapped[float] = mapped_column(Float)
    knifeEdge_knifeScan_unit: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    knifeEdge_knifeScan: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # scan:

    mda_file: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    scanEnd_abort: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # Mapped[bool] = mapped_column(Boolean)
    scanEnd_time_epoch: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    scanEnd_time: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # DateTime?
    scanEnd_scanDuration_unit: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    scanEnd_scanDuration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # scanEnd_cpt: Mapped[int] = mapped_column(Integer)
    scanEnd_source_beamBad: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # Mapped[bool] = mapped_column(Boolean)
    scanEnd_source_ringCurrent_unit: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    scanEnd_source_ringCurrent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    motorGroup_sample_npts_total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    motorGroup_sample_cpt_total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    motorGroup_energy_npts_total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    motorGroup_energy_cpt_total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    motorGroup_depth_npts_total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    motorGroup_depth_cpt_total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    motorGroup_other_npts_total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    motorGroup_other_cpt_total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Parent of:
    scan_: Mapped["Scan"] = relationship(backref="metadata")
    catalog_: Mapped["Catalog"] = relationship(backref="metadata")
    calib_: Mapped["Calib"] = relationship(backref="metadata")
    recon_: Mapped["Recon"] = relationship(backref="metadata")
    wirerecon_: Mapped["WireRecon"] = relationship(backref="metadata")
    peakindex_: Mapped["PeakIndex"] = relationship(backref="metadata")

    def __repr__(self) -> str:
        pass  # TODO: Consider implemeting for debugging
