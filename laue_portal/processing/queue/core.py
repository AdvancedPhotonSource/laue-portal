"""Core Redis/RQ queue state and status constants."""

import logging
import os
from typing import Any, List

import redis
from redis import Redis
from rq import Queue

from laue_portal.config import REDIS_CONFIG

logger = logging.getLogger(__name__)

# Redis connection
redis_conn = Redis(host="localhost", port=REDIS_CONFIG["port"], decode_responses=False)

# Single queue for all job types
job_queue = Queue("laue_jobs", connection=redis_conn)

# Global variable to store startup status
REDIS_CONNECTED_AT_STARTUP = None

# Job status mapping
STATUS_MAPPING = {0: "Queued", 1: "Running", 2: "Finished", 3: "Failed", 4: "Cancelled"}

# Reverse mapping for converting status names to integers
STATUS_REVERSE_MAPPING = {v: k for k, v in STATUS_MAPPING.items()}

PEAKINDEXING_QUEUE_BATCH_SIZE = max(1, int(os.environ.get("LAUE_PEAKINDEXING_QUEUE_BATCH_SIZE", "50")))
WRITE_SUCCESS_SUBJOB_DETAILS = os.environ.get("LAUE_WRITE_SUCCESS_SUBJOB_DETAILS", "0").lower() in {
    "1",
    "true",
    "yes",
}


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


def _chunked(items: List[Any], chunk_size: int):
    for start in range(0, len(items), chunk_size):
        yield items[start : start + chunk_size]
