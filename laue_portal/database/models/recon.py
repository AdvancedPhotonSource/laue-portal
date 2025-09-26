"""
Table of mask reconstruction parameters and results.
"""
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, Float, Boolean, JSON, ForeignKey
from laue_portal.database.base import Base


class Recon(Base):
    __tablename__ = "recon"

    # Recon Metadata
    recon_id: Mapped[int] = mapped_column(primary_key=True)
    scanNumber: Mapped[int] = mapped_column(ForeignKey("metadata.scanNumber"))
    calib_id: Mapped[int] = mapped_column(ForeignKey("calib.calib_id"))
    job_id: Mapped[int] = mapped_column(ForeignKey("job.job_id"), unique=True)

    author: Mapped[str] = mapped_column(String, nullable=True)
    notes: Mapped[str] = mapped_column(String, nullable=True)

    # outputFolder: Mapped[str] = mapped_column(String) # outfile
    geoFile: Mapped[str] = mapped_column(String, default="")  # geofile
    percent_brightest: Mapped[float] = mapped_column(Float, default=0.0)  # pxl_recon

    # Recon Parameters
    file_path: Mapped[str] = mapped_column(String)
    scanPointslen: Mapped[str] = mapped_column(Integer, default=0)  # Cached value
    file_output: Mapped[str] = mapped_column(String)
    file_range: Mapped[list[int]] = mapped_column(JSON)
    file_threshold: Mapped[int] = mapped_column(Integer)
    file_frame: Mapped[list[int]] = mapped_column(JSON)
    # file_offset: Mapped[list[int]] = mapped_column(JSON)
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
    geo_source_grid: Mapped[list[float]] = mapped_column(JSON)  # Consider splitting into components

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
        return f"Recon {self.recon_id}"  # TODO: Consider implementing for debugging
