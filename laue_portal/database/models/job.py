"""
Job table with info on compute jobs.

One job is one queued run. Per-input bookkeeping lives in the run's manifest
and failure report on disk (see ``laue_portal.workflows.manifest``); the
database keeps run-level counters and execution state so progress and report
queries never join per-frame rows.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from laue_portal.database.base import Base


class Job(Base):
    __tablename__ = "job"
    __table_args__ = (
        CheckConstraint(
            "n_inputs >= 0 AND n_succeeded >= 0 AND n_failed >= 0 AND n_not_run >= 0",
            name="ck_job_counters_non_negative",
        ),
        CheckConstraint("n_succeeded + n_failed + n_not_run <= n_inputs", name="ck_job_counters_bounded"),
    )

    job_id: Mapped[int] = mapped_column(primary_key=True)

    computer_name: Mapped[str] = mapped_column(String)
    status: Mapped[int] = mapped_column(Integer)  # Queued, Running, Finished, Failed, Cancelled
    priority: Mapped[int] = mapped_column(Integer)

    submit_time: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    start_time: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    finish_time: Mapped[DateTime] = mapped_column(DateTime, nullable=True)

    # Human-readable log; the last line is the terminal message of a finished run.
    messages: Mapped[str] = mapped_column(String, nullable=True)

    # Execution state (values in laue_portal.workflows.execution.RunPhase).
    phase: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    queue_job_id: Mapped[str | None] = mapped_column(String, nullable=True)

    # Run counters. Processed work is n_succeeded + n_failed; n_not_run is work
    # that was never attempted (cancelled, interrupted, or skipped) and is fixed
    # at finalization so the three always sum to n_inputs for a finished run.
    n_inputs: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    n_succeeded: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    n_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    n_not_run: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    # Run-level artifact references (absolute paths).
    run_directory: Mapped[str | None] = mapped_column(String, nullable=True)
    manifest_path: Mapped[str | None] = mapped_column(String, nullable=True)
    manifest_digest: Mapped[str | None] = mapped_column(String, nullable=True)
    request_path: Mapped[str | None] = mapped_column(String, nullable=True)
    failure_report_path: Mapped[str | None] = mapped_column(String, nullable=True)

    # Parent of:
    calib_: Mapped["Calib"] = relationship(backref="job")  # noqa: F821
    reconstruction_run: Mapped["ReconstructionRun | None"] = relationship(  # noqa: F821
        back_populates="job", uselist=False
    )
    indexing_run: Mapped["IndexingRun | None"] = relationship(  # noqa: F821
        back_populates="job", uselist=False
    )
