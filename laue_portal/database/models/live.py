"""One active live session and its durable, point-level arrival ledger."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from laue_portal.database.base import Base


class LiveSession(Base):
    __tablename__ = "live_session"

    id: Mapped[int] = mapped_column(primary_key=True)
    # SQLite permits multiple NULLs; only the active session holds slot 1.
    active_slot: Mapped[int | None] = mapped_column(Integer, unique=True)
    reconstruction_id: Mapped[int | None] = mapped_column(ForeignKey("reconstruction_run.id"), unique=True)
    indexing_id: Mapped[int | None] = mapped_column(ForeignKey("indexing_run.id"), unique=True)
    reconstruction_job_id: Mapped[int | None] = mapped_column(ForeignKey("job.job_id"), unique=True)
    indexing_job_id: Mapped[int | None] = mapped_column(ForeignKey("job.job_id"), unique=True)
    state: Mapped[str] = mapped_column(String)
    action: Mapped[str | None] = mapped_column(String)
    control_directory: Mapped[str] = mapped_column(String)
    recipe: Mapped[dict] = mapped_column(JSON)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    error: Mapped[str | None] = mapped_column(String)


class LiveCheckpoint(Base):
    """Keep the growing checkpoint separate from frequently updated heartbeats."""

    __tablename__ = "live_checkpoint"

    session_id: Mapped[int] = mapped_column(ForeignKey("live_session.id"), primary_key=True)
    state: Mapped[dict] = mapped_column(JSON)


class LivePoint(Base):
    __tablename__ = "live_point"
    __table_args__ = (
        UniqueConstraint("session_id", "source"),
        UniqueConstraint("session_id", "point_id"),
        UniqueConstraint("session_id", "point_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("live_session.id"), index=True)
    point_number: Mapped[int] = mapped_column(Integer)
    point_id: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String)
    source_identity: Mapped[dict] = mapped_column(JSON)
    arrived_at: Mapped[datetime] = mapped_column(DateTime)
    task: Mapped[dict | None] = mapped_column(JSON)
    reconstruction_state: Mapped[str] = mapped_column(String, default="ready")
    indexing_state: Mapped[str] = mapped_column(String, default="pending")
    indexing_order: Mapped[int | None] = mapped_column(Integer)
    indexing_inputs: Mapped[int] = mapped_column(Integer, default=0)
    indexing_succeeded: Mapped[int] = mapped_column(Integer, default=0)
    indexing_failed: Mapped[int] = mapped_column(Integer, default=0)
    indexed_frames: Mapped[int] = mapped_column(Integer, default=0)
    reconstruction_receipt: Mapped[dict | None] = mapped_column(JSON)
    indexing_receipt: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(String)
