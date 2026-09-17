"""Tests for the lightweight timed refresh of run tables."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from laue_portal.components import live_rows

T0 = datetime(2026, 9, 16, 12, 0, 0)


def test_initial_state_records_the_poll_time_and_highest_identity():
    state = live_rows.initial_state([{"job_id": 3}, {"job_id": 11}, {"job_id": None}], "job_id", now=T0)
    assert state == {"since": T0.isoformat(timespec="microseconds"), "max_id": 11}
    assert live_rows.initial_state([], "job_id", now=T0)["max_id"] == 0


def test_since_applies_an_overlap_so_boundary_rows_are_not_missed():
    state = live_rows.initial_state([], "job_id", now=T0)
    assert live_rows.since_from_state(state) == T0 - live_rows.POLL_OVERLAP
    assert live_rows.since_from_state(None) is None
    assert live_rows.since_from_state({}) is None


def test_transaction_updates_known_rows_and_adds_new_runs_at_the_top():
    state = live_rows.initial_state([{"job_id": 5}], "job_id", now=T0)
    later = T0 + timedelta(seconds=10)
    rows = [{"job_id": 7, "status": 0}, {"job_id": 5, "status": 1}, {"job_id": None}]

    transaction, next_state = live_rows.transaction(rows, "job_id", state, now=later)

    assert transaction == {"update": [{"job_id": 5, "status": 1}], "add": [{"job_id": 7, "status": 0}], "addIndex": 0}
    assert next_state == {"since": later.isoformat(timespec="microseconds"), "max_id": 7}


def test_transaction_is_none_when_nothing_changed_and_state_still_advances():
    state = live_rows.initial_state([{"job_id": 5}], "job_id", now=T0)
    later = T0 + timedelta(seconds=10)

    transaction, next_state = live_rows.transaction([], "job_id", state, now=later)

    assert transaction is None
    assert next_state == {"since": later.isoformat(timespec="microseconds"), "max_id": 5}


def test_status_progress_is_processed_over_total_only_for_running_rows():
    frame = pd.DataFrame(
        {
            "status": [1, 2, 1],
            "n_inputs": [10, 10, 0],
            "n_succeeded": [3, 10, 0],
            "n_failed": [1, 0, 0],
            "n_not_run": [0, 0, 0],
            "n_processed": [4, 10, 0],
            "n_pending": [6, 0, 0],
        }
    )
    assert list(live_rows.add_status_progress(frame)["status_progress"]) == ["4/10", None, None]


def test_payload_bytes_measures_the_json_dash_would_send():
    assert live_rows.payload_bytes({"a": 1}) == len(b'{"a":1}')
    assert live_rows.payload_bytes({"t": T0}) > 0
