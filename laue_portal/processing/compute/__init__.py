"""Compute-and-write functions, independent of RQ, Redis, and the ORM.

A compute function receives a plain :class:`RunRequest`, the run's manifest
entries, and :class:`RunHooks`; it writes the run's scientific output and
returns a :class:`RunOutcome`. The queue executor supplies hooks and persists
state; nothing here opens a database or Redis connection.
"""

from .contract import (
    ComputeFunction,
    RunHooks,
    RunOutcome,
    RunRequest,
    UnknownRunKind,
    get_compute_function,
    register_compute_function,
)

__all__ = [
    "ComputeFunction",
    "RunHooks",
    "RunOutcome",
    "RunRequest",
    "UnknownRunKind",
    "get_compute_function",
    "register_compute_function",
]
