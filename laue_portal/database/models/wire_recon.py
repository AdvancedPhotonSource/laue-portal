"""
Table of wire reconstruction parameters and results.
"""
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, Float, ForeignKey
from laue_portal.database.base import Base


class WireRecon(Base):
    __tablename__ = "wirerecon"

    # Wire Recon Metadata
    wirerecon_id: Mapped[int] = mapped_column(primary_key=True)
    scanNumber: Mapped[int] = mapped_column(ForeignKey("metadata.scanNumber"))
    # calib_id: Mapped[int] = mapped_column(ForeignKey("calib.calib_id"))
    job_id: Mapped[int] = mapped_column(ForeignKey("job.job_id"), unique=True)

    author: Mapped[str] = mapped_column(String, nullable=True)
    notes: Mapped[str] = mapped_column(String, nullable=True)

    # Recon constraints
    geoFile: Mapped[str] = mapped_column(String)
    percent_brightest: Mapped[float] = mapped_column(Float)
    wire_edges: Mapped[str] = mapped_column(String)

    # Depth Parameters
    depth_start: Mapped[float] = mapped_column(Float)  # depth-start
    depth_end: Mapped[float] = mapped_column(Float)  # depth-end
    depth_resolution: Mapped[float] = mapped_column(Float)  # resolution

    # Compute parameters
    num_threads: Mapped[int] = mapped_column(Integer)
    memory_limit_mb: Mapped[int] = mapped_column(Integer)

    # Files
    scanPoints: Mapped[str] = mapped_column(String)  # String field for srange parsing
    scanPointslen: Mapped[int] = mapped_column(Integer)  # Cached value

    # Output
    outputFolder: Mapped[str] = mapped_column(String)
    verbose: Mapped[int] = mapped_column(Integer)

    # Parent of:
    peakindex_: Mapped["PeakIndex"] = relationship(backref="wirerecon")

    def __repr__(self) -> str:
        return f"WireRecon {self.wirerecon_id}"  # TODO: Consider implementing for debugging
