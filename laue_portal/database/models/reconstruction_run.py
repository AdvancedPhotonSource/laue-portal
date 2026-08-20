"""Unified reconstruction runs and method-specific parameters."""

from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from laue_portal.database.base import Base


class ReconstructionRun(Base):
    """One reconstruction operation, independent of reconstruction method."""

    __tablename__ = "reconstruction_run"
    __table_args__ = (
        CheckConstraint("method IN ('wire', 'ca')", name="ck_reconstruction_run_method"),
        Index("ix_reconstruction_run_scan_number", "scan_number"),
        Index("ix_reconstruction_run_method", "method"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    scan_number: Mapped[int | None] = mapped_column(ForeignKey("metadata.scanNumber"), nullable=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("job.job_id"), unique=True)
    method: Mapped[str] = mapped_column(String, nullable=False)
    input_path: Mapped[str] = mapped_column(String, nullable=False)
    output_path: Mapped[str | None] = mapped_column(String, nullable=True)
    author: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    algorithm_version: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    scan: Mapped["Metadata | None"] = relationship(  # noqa: F821
        back_populates="reconstruction_runs"
    )
    job: Mapped["Job"] = relationship(back_populates="reconstruction_run")  # noqa: F821
    wire_parameters: Mapped["WireReconstructionParameters | None"] = relationship(
        back_populates="reconstruction",
        cascade="all, delete-orphan",
        single_parent=True,
        uselist=False,
    )
    indexing_runs: Mapped[list["IndexingRun"]] = relationship(  # noqa: F821
        back_populates="reconstruction"
    )

    def __repr__(self) -> str:
        return f"Reconstruction R{self.id} ({self.method})"


class WireReconstructionParameters(Base):
    """Configuration used by a wire reconstruction run."""

    __tablename__ = "wire_reconstruction_parameters"

    reconstruction_id: Mapped[int] = mapped_column(
        ForeignKey("reconstruction_run.id", ondelete="CASCADE"), primary_key=True
    )
    filename_prefixes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    geometry_file: Mapped[str] = mapped_column(String, nullable=False)
    percent_brightest: Mapped[float] = mapped_column(Float, nullable=False)
    wire_edges: Mapped[str] = mapped_column(String, nullable=False)
    depth_start: Mapped[float] = mapped_column(Float, nullable=False)
    depth_end: Mapped[float] = mapped_column(Float, nullable=False)
    depth_resolution: Mapped[float] = mapped_column(Float, nullable=False)
    num_threads: Mapped[int] = mapped_column(Integer, nullable=False)
    memory_limit_mb: Mapped[int] = mapped_column(Integer, nullable=False)
    scan_points: Mapped[str] = mapped_column(String, nullable=False)
    scan_points_len: Mapped[int] = mapped_column(Integer, nullable=False)
    verbose: Mapped[int] = mapped_column(Integer, nullable=False)

    reconstruction: Mapped[ReconstructionRun] = relationship(back_populates="wire_parameters")
