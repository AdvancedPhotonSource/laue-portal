"""Lightweight timed refresh for AG Grid tables of runs.

A poll never re-sends the whole table. It queries only the jobs that are active
or were finalized since the previous poll (``progress.active_or_changed_since``)
and applies them as an AG Grid row transaction: rows the grid already holds are
updated in place, runs created since the page loaded are added at the top. With
``getRowId`` set on the grid, a transaction preserves selection, filters, sort
order, pagination, column state, and scroll position. Nothing is sent when
nothing changed.

The poll callback disables its interval while it runs (Dash ``running``), so
polls never overlap. Each page keeps a small store with the previous poll time
and the highest identity it has seen.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from laue_portal.workflows.execution import JobStatus

REFRESH_SECONDS = 10
PROGRESS_FIELDS = ["n_inputs", "n_succeeded", "n_failed", "n_not_run", "n_processed", "n_pending"]
# Overlap between polls so a row finalized while the previous query ran is not missed.
POLL_OVERLAP = timedelta(seconds=2)


def initial_state(rows: list[dict[str, Any]], id_field: str, *, now: datetime | None = None) -> dict[str, Any]:
    """State to store right after a full load of ``rows``."""

    moment = now or datetime.now()
    ids = [row[id_field] for row in rows if row.get(id_field) is not None]
    return {"since": moment.isoformat(timespec="microseconds"), "max_id": max(ids) if ids else 0}


def since_from_state(state: dict[str, Any] | None) -> datetime | None:
    """The lower bound for ``updated_at`` in the next poll, with the overlap applied."""

    if not state or not state.get("since"):
        return None
    return datetime.fromisoformat(state["since"]) - POLL_OVERLAP


def transaction(
    rows: list[dict[str, Any]],
    id_field: str,
    state: dict[str, Any] | None,
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Split polled ``rows`` into an AG Grid transaction and the state for the next poll.

    Returns ``(transaction, next_state)``; ``transaction`` is None when there is
    nothing to apply. Rows whose identity is above the highest one seen so far
    are new runs and are added at the top of the grid.
    """

    moment = now or datetime.now()
    max_seen = int((state or {}).get("max_id") or 0)
    update, add = [], []
    for row in rows:
        identity = row.get(id_field)
        if identity is None:
            continue
        (add if int(identity) > max_seen else update).append(row)
    ids = [int(row[id_field]) for row in rows if row.get(id_field) is not None]
    next_state = {"since": moment.isoformat(timespec="microseconds"), "max_id": max([max_seen, *ids])}
    if not update and not add:
        return None, next_state
    payload: dict[str, Any] = {}
    if update:
        payload["update"] = update
    if add:
        payload["add"] = add
        payload["addIndex"] = 0
    return payload, next_state


def payload_bytes(value: Any) -> int:
    """Size of ``value`` as the JSON Dash would send; used to measure refresh cost."""

    return len(json.dumps(value, default=str, separators=(",", ":")).encode("utf-8"))


def add_status_progress(frame):
    """``processed/total`` next to the Running badge, from the counters stored on the job (pandas frame)."""

    frame[PROGRESS_FIELDS] = frame[PROGRESS_FIELDS].fillna(0).astype(int)
    frame["status_progress"] = None
    running_rows = (frame["status"] == int(JobStatus.RUNNING)) & (frame["n_inputs"] > 0)
    frame.loc[running_rows, "status_progress"] = (
        frame.loc[running_rows, "n_processed"].astype(str) + "/" + frame.loc[running_rows, "n_inputs"].astype(str)
    )
    return frame
