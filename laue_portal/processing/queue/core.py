"""Core Redis/RQ queue state, status constants, and the whole-run execution policy."""

import logging
from dataclasses import dataclass

import redis
from redis import Redis
from rq import Queue

from laue_portal.config import REDIS_CONFIG, RUN_EXECUTION
from laue_portal.workflows.execution import STATUS_NAMES

logger = logging.getLogger(__name__)

# Redis connection
redis_conn = Redis(host=REDIS_CONFIG.get("host", "localhost"), port=REDIS_CONFIG["port"], decode_responses=False)

# Single queue for all run types; one queue item is one run.
job_queue = Queue("laue_jobs", connection=redis_conn)

# Global variable to store startup status
REDIS_CONNECTED_AT_STARTUP = None

# Job status mapping, shared with laue_portal.workflows.execution.JobStatus
STATUS_MAPPING = {int(status): name for status, name in STATUS_NAMES.items()}

# Reverse mapping for converting status names to integers
STATUS_REVERSE_MAPPING = {v: k for k, v in STATUS_MAPPING.items()}

RUN_JOB_TYPE = "run"


def run_queue_id(job_id: int) -> str:
    """The deterministic RQ job identity of one run; enqueueing it twice is impossible."""

    return f"{RUN_JOB_TYPE}_{int(job_id)}"


@dataclass(frozen=True)
class RunPolicy:
    """Whole-run execution limits, read from the ``RUN_EXECUTION`` section of config.yaml.

    ``job_timeout_seconds`` is the wall-clock limit for one run; RQ raises inside
    the run when it is exceeded and the run is finalized as Failed. It replaces
    the old two-hour per-chunk assumption. ``stale_heartbeat_seconds`` decides
    when a Running job whose heartbeat stopped is reconciled as interrupted.
    """

    job_timeout_seconds: int = 24 * 3600
    heartbeat_seconds: float = 15.0
    progress_seconds: float = 5.0
    cancel_poll_seconds: float = 2.0
    stale_heartbeat_seconds: int = 300
    shutdown_grace_seconds: int = 600
    workers: int = 4
    max_in_flight: int | None = None

    def __post_init__(self) -> None:
        if self.job_timeout_seconds <= 0:
            raise ValueError("job_timeout_seconds must be positive")
        for name in ("heartbeat_seconds", "progress_seconds", "cancel_poll_seconds"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if self.stale_heartbeat_seconds <= self.heartbeat_seconds:
            raise ValueError("stale_heartbeat_seconds must exceed heartbeat_seconds")
        if self.shutdown_grace_seconds < 0:
            raise ValueError("shutdown_grace_seconds must not be negative")
        if self.workers <= 0:
            raise ValueError("workers must be positive")
        if self.max_in_flight is not None and self.max_in_flight < self.workers:
            raise ValueError("max_in_flight must be at least workers")

    @classmethod
    def from_config(cls, values: dict | None) -> "RunPolicy":
        values = dict(values or {})
        unknown = set(values) - {field for field in cls.__dataclass_fields__}
        if unknown:
            raise ValueError(f"Unknown RUN_EXECUTION settings: {', '.join(sorted(unknown))}")
        return cls(**values)


RUN_POLICY = RunPolicy.from_config(RUN_EXECUTION)


def check_redis_connection():
    """Check if Redis server is accessible and responding."""
    try:
        return redis_conn.ping()
    except (redis.ConnectionError, redis.TimeoutError, Exception):
        return False


def init_redis_status():
    """Initialize Redis status check on startup."""
    global REDIS_CONNECTED_AT_STARTUP
    REDIS_CONNECTED_AT_STARTUP = check_redis_connection()
    logger.info(f"Redis connection status at startup: {'Connected' if REDIS_CONNECTED_AT_STARTUP else 'Disconnected'}")
    return REDIS_CONNECTED_AT_STARTUP
