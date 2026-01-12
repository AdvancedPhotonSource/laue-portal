"""
Table for sub-jobs within a computation jobs.
"""
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String, DateTime, Text, ForeignKey
from laue_portal.database.base import Base


class SubJob(Base):
    __tablename__ = "subjob"

    subjob_id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("job.job_id"))

    computer_name: Mapped[str] = mapped_column(String)
    status: Mapped[int] = mapped_column(Integer)  # Queued, Running, Finished, Failed, Cancelled
    priority: Mapped[int] = mapped_column(Integer)

    start_time: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    finish_time: Mapped[DateTime] = mapped_column(DateTime, nullable=True)

    messages: Mapped[str] = mapped_column(String, nullable=True)
    command: Mapped[str] = mapped_column(Text, nullable=True)  # CLI command(s) used to execute the job
