"""Unified indexing runs and method-specific parameters."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from laue_portal.database.base import Base


class IndexingRun(Base):
    """One indexing operation, optionally based on a reconstruction."""

    __tablename__ = "indexing_run"
    __table_args__ = (
        CheckConstraint("method IN ('lauego', 'laue_matching')", name="ck_indexing_run_method"),
        Index("ix_indexing_run_scan_number", "scan_number"),
        Index("ix_indexing_run_reconstruction_id", "reconstruction_id"),
        Index("ix_indexing_run_method", "method"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    scan_number: Mapped[int | None] = mapped_column(ForeignKey("metadata.scanNumber"), nullable=True)
    reconstruction_id: Mapped[int | None] = mapped_column(ForeignKey("reconstruction_run.id"), nullable=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("job.job_id"), unique=True)
    method: Mapped[str] = mapped_column(String, nullable=False)
    input_path: Mapped[str] = mapped_column(String, nullable=False)
    output_path: Mapped[str | None] = mapped_column(String, nullable=True)
    author: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    algorithm_version: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    scan: Mapped["Metadata | None"] = relationship(  # noqa: F821
        back_populates="indexing_runs"
    )
    reconstruction: Mapped["ReconstructionRun | None"] = relationship(  # noqa: F821
        back_populates="indexing_runs"
    )
    job: Mapped["Job"] = relationship(back_populates="indexing_run")  # noqa: F821
    lauego_parameters: Mapped["LaueGoIndexingParameters | None"] = relationship(
        back_populates="indexing",
        cascade="all, delete-orphan",
        single_parent=True,
        uselist=False,
    )

    def __repr__(self) -> str:
        return f"Indexing I{self.id} ({self.method})"


class LaueGoIndexingParameters(Base):
    """Configuration used by a LaueGo indexing run."""

    __tablename__ = "lauego_indexing_parameters"

    indexing_id: Mapped[int] = mapped_column(ForeignKey("indexing_run.id", ondelete="CASCADE"), primary_key=True)
    filename_prefixes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    threshold: Mapped[int | None] = mapped_column(Integer, nullable=True)
    threshold_ratio: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_rfactor: Mapped[float] = mapped_column(Float, nullable=False)
    box_size: Mapped[int] = mapped_column(Integer, nullable=False)
    max_number: Mapped[int] = mapped_column(Integer, nullable=False)
    min_separation: Mapped[int] = mapped_column(Integer, nullable=False)
    peak_shape: Mapped[str] = mapped_column(String, nullable=False)
    scan_points: Mapped[str] = mapped_column(String, nullable=False)
    scan_points_len: Mapped[int] = mapped_column(Integer, nullable=False)
    depth_range: Mapped[str | None] = mapped_column(String, nullable=True)
    depth_range_len: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detector_crop_x1: Mapped[int] = mapped_column(Integer, nullable=False)
    detector_crop_x2: Mapped[int] = mapped_column(Integer, nullable=False)
    detector_crop_y1: Mapped[int] = mapped_column(Integer, nullable=False)
    detector_crop_y2: Mapped[int] = mapped_column(Integer, nullable=False)
    min_size: Mapped[float] = mapped_column(Float, nullable=False)
    max_peaks: Mapped[int] = mapped_column(Integer, nullable=False)
    smooth: Mapped[bool] = mapped_column(Boolean, nullable=False)
    mask_file: Mapped[str | None] = mapped_column(String, nullable=True)
    index_kev_max_calc: Mapped[float] = mapped_column(Float, nullable=False)
    index_kev_max_test: Mapped[float] = mapped_column(Float, nullable=False)
    index_angle_tolerance: Mapped[float] = mapped_column(Float, nullable=False)
    index_h: Mapped[int] = mapped_column(Integer, nullable=False)
    index_k: Mapped[int] = mapped_column(Integer, nullable=False)
    index_l: Mapped[int] = mapped_column(Integer, nullable=False)
    index_cone: Mapped[float] = mapped_column(Float, nullable=False)
    energy_unit: Mapped[str] = mapped_column(String, nullable=False)
    exposure_unit: Mapped[str] = mapped_column(String, nullable=False)
    cosmic_filter: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reciprocal_lattice_unit: Mapped[str] = mapped_column(String, nullable=False)
    lattice_parameters_unit: Mapped[str] = mapped_column(String, nullable=False)
    output_xml: Mapped[str | None] = mapped_column(String, nullable=True)
    geometry_file: Mapped[str] = mapped_column(String, nullable=False)
    crystal_file: Mapped[str] = mapped_column(String, nullable=False)
    depth: Mapped[str | None] = mapped_column(String, nullable=True)
    beamline: Mapped[str] = mapped_column(String, nullable=False)

    indexing: Mapped[IndexingRun] = relationship(back_populates="lauego_parameters")
