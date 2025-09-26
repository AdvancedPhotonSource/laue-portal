"""
Job table with info on compute jobs.
"""
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, DateTime
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
    subjob_: Mapped["SubJob"] = relationship(backref="job")
    calib_: Mapped["Calib"] = relationship(backref="job")
    recon_: Mapped["Recon"] = relationship(backref="job")
    wirerecon_: Mapped["WireRecon"] = relationship(backref="job")
    peakindex_: Mapped["PeakIndex"] = relationship(backref="job")
