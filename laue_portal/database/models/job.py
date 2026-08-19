"""
Job table with info on compute jobs.
"""

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from laue_portal.database.base import Base


class Job(Base):
    __tablename__ = "job"

    job_id: Mapped[int] = mapped_column(primary_key=True)

    computer_name: Mapped[str] = mapped_column(String)
    status: Mapped[int] = mapped_column(Integer)  # Queued, Running, Finished, Failed, Cancelled
    priority: Mapped[int] = mapped_column(Integer)

    submit_time: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    start_time: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    finish_time: Mapped[DateTime] = mapped_column(DateTime, nullable=True)

    messages: Mapped[str] = mapped_column(String, nullable=True)

    # Parent of:
    subjobs: Mapped[list["SubJob"]] = relationship(back_populates="job")  # noqa: F821
    calib_: Mapped["Calib"] = relationship(backref="job")  # noqa: F821
    recon_: Mapped["Recon"] = relationship(backref="job")  # noqa: F821
    wirerecon_: Mapped["WireRecon"] = relationship(backref="job")  # noqa: F821
    peakindex_: Mapped["PeakIndex"] = relationship(backref="job")  # noqa: F821
    reconstruction_run: Mapped["ReconstructionRun | None"] = relationship(  # noqa: F821
        back_populates="job", uselist=False
    )
    indexing_run: Mapped["IndexingRun | None"] = relationship(  # noqa: F821
        back_populates="job", uselist=False
    )
