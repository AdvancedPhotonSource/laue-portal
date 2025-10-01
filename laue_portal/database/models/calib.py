"""
Contains calibration data for mask reconstructions.
"""
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Float, JSON, ForeignKey
from laue_portal.database.base import Base


class Calib(Base):
    __tablename__ = "calib"

    calib_id: Mapped[int] = mapped_column(primary_key=True)
    scanNumber: Mapped[int] = mapped_column(ForeignKey("metadata.scanNumber"))
    job_id: Mapped[int] = mapped_column(ForeignKey("job.job_id"), unique=True)

    filefolder: Mapped[str] = mapped_column(String)  # infile
    # filenamePrefix: Mapped[str] = mapped_column(String) # infile
    filenamePrefix: Mapped[list[str]] = mapped_column(JSON)  # infile

    author: Mapped[str] = mapped_column(String, nullable=True)
    notes: Mapped[str] = mapped_column(String, nullable=True)

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
    # wirerecon_: Mapped["WireRecon"] = relationship(backref="calib")

    def __repr__(self) -> str:
        pass  # TODO: Consider implemeting for debugging
