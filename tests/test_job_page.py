"""Tests for the job page: counters, configuration, paged failure diagnostics, live refresh, stop wording."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from dash._callback_context import context_value
from dash._utils import AttributeDict
from dash.exceptions import PreventUpdate
from sqlalchemy.orm import Session

import lau_dash  # noqa: F401  instantiates the Dash app so page modules can register
from laue_portal.database import db_schema
from laue_portal.pages import job as job_page
from laue_portal.processing.compute import contract
from laue_portal.processing.queue import executors
from laue_portal.services import run_summary
from laue_portal.workflows import execution
from laue_portal.workflows.execution import JobStatus, RunPhase
from laue_portal.workflows.manifest import FailureRecord, FailureReportWriter, ManifestEntry
from tests.run_support import FAST_POLICY, make_engine, publish_wire_run
from tests.test_run_executor import WIRE_KIND, _per_entry, _queued_run


@pytest.fixture
def engine(tmp_path, monkeypatch):
    yield make_engine(tmp_path, monkeypatch)


@pytest.fixture
def compute(monkeypatch):
    def install(function):
        monkeypatch.setitem(contract._REGISTRY, WIRE_KIND, function)
        return function

    return install


def _href(job_id):
    return f"http://localhost/job?job_id={job_id}"


def _texts(component):
    """Every string inside a Dash component tree, in order."""

    found = []

    def walk(node):
        if node is None or isinstance(node, bool):
            return
        if isinstance(node, (str, int, float)):
            found.append(str(node))
            return
        if isinstance(node, (list, tuple)):
            for child in node:
                walk(child)
            return
        for attribute in ("children", "label", "title"):
            value = getattr(node, attribute, None)
            if value is not None and attribute != "title":
                walk(value)
            elif value is not None:
                found.append(str(value))

    walk(component)
    return found


def _text(component) -> str:
    """The component tree's text with whitespace normalized."""

    return " ".join(" ".join(_texts(component)).split())


def _trigger(prop_id):
    context_value.set(
        AttributeDict(triggered_inputs=[{"prop_id": prop_id, "value": 1}], inputs_list=[], states_list=[])
    )


def test_finished_run_with_failures_shows_counters_configuration_and_a_failure_page(
    engine, tmp_path, monkeypatch, compute
):
    run = _queued_run(engine, tmp_path, monkeypatch, count=4)
    compute(_per_entry(fail={2}, artifacts={"results": os.path.join(run.output_path, "output.h5")}))
    executors.execute_run(run.job_id, engine=engine, policy=FAST_POLICY)

    outputs = job_page.load_job_data(_href(run.job_id))

    header, status, priority, computer, submit, start, finish, duration, messages, stop_disabled = outputs[:10]
    progress, configuration, interval_disabled, offset = outputs[10:]
    assert f"Job ID: {run.job_id}" in _texts(header) and f"Reconstruction R{run.id}" in " ".join(_texts(header))
    assert "Failed" in _texts(status)  # incomplete: one input failed
    assert stop_disabled is True and interval_disabled is True and offset == 0
    assert duration.endswith("s") and "(running)" not in duration
    assert "Incomplete" in messages

    progress_text = " ".join(_texts(progress))
    assert "3 succeeded" in progress_text and "1 failed" in progress_text
    assert "Processed 4 of 4" in progress_text

    configuration_text = " ".join(_texts(configuration))
    assert "Submitted request" in configuration_text and "wire edges" in configuration_text
    assert "Execution and versions" in configuration_text and "engine" in configuration_text
    assert "results" in configuration_text and "output.h5" in configuration_text
    assert "did not finish, but its published results" in configuration_text
    assert "failure report" in configuration_text

    _trigger("job-failures-offset.data")
    body, range_text, prev_disabled, next_disabled, new_offset = job_page.page_failed_inputs(
        0, None, None, True, _href(run.job_id)
    )
    text = " ".join(_texts(body))
    assert "bad frame" in text and "wire_3" in text and "input" in text  # manifest index 2 is the third file
    assert range_text == "Showing 1–1 of 1"
    assert (prev_disabled, next_disabled, new_offset) == (True, True, 0)


def test_failure_report_is_paged_in_bounded_pages(engine, tmp_path, monkeypatch):
    run = publish_wire_run(engine, tmp_path, count=3)
    report = tmp_path / "failures.jsonl"
    with FailureReportWriter(report) as writer:
        for index in range(120):
            entry = ManifestEntry(
                index=index,
                input_id=f"frame_{index}",
                source=f"/data/frame_{index}.h5",
                template_index=0,
                scan_point=index + 1,
                depth_point=None,
            )
            writer.append(FailureRecord.from_error(entry, ValueError(f"bad {index}")))
    with Session(engine) as session, session.begin():
        job = session.get(db_schema.Job, run.job_id)
        job.n_inputs = 120
        execution.mark_queued(job, "rq-1")
        execution.mark_running(job)
        execution.record_progress(job, succeeded=0, failed=120)
        execution.finalize(job, status=JobStatus.FAILED, message="All inputs failed", failure_report_path=str(report))

    _trigger("job-failures-offset.data")
    body, range_text, prev_disabled, next_disabled, offset = job_page.page_failed_inputs(
        0, None, None, True, _href(run.job_id)
    )
    assert (range_text, prev_disabled, next_disabled, offset) == ("Showing 1–50 of 120", True, False, 0)
    assert "bad 0" in " ".join(_texts(body)) and "bad 50" not in " ".join(_texts(body))

    _trigger("failed-inputs-next-btn.n_clicks")
    body, range_text, prev_disabled, next_disabled, offset = job_page.page_failed_inputs(
        0, None, 1, True, _href(run.job_id)
    )
    assert (range_text, prev_disabled, next_disabled, offset) == ("Showing 51–100 of 120", False, False, 50)

    _trigger("failed-inputs-next-btn.n_clicks")
    body, range_text, prev_disabled, next_disabled, offset = job_page.page_failed_inputs(
        50, None, 2, True, _href(run.job_id)
    )
    assert (range_text, prev_disabled, next_disabled, offset) == ("Showing 101–120 of 120", False, True, 100)
    assert "bad 119" in " ".join(_texts(body))

    _trigger("failed-inputs-prev-btn.n_clicks")
    _, range_text, _, _, offset = job_page.page_failed_inputs(100, 1, 2, True, _href(run.job_id))
    assert (range_text, offset) == ("Showing 51–100 of 120", 50)

    # A poll while the run is still active does not reload the report.
    _trigger("job-refresh-interval.disabled")
    with pytest.raises(PreventUpdate):
        job_page.page_failed_inputs(50, 1, 2, False, _href(run.job_id))


def test_running_job_keeps_the_live_interval_and_reports_heartbeat_and_stop_request(engine, tmp_path, monkeypatch):
    run = publish_wire_run(engine, tmp_path, count=10)
    now = datetime(2026, 9, 16, 12, 0, 0)
    with Session(engine) as session, session.begin():
        job = session.get(db_schema.Job, run.job_id)
        execution.mark_queued(job, "rq-1")
        execution.mark_running(job, now=now)
        execution.record_progress(job, succeeded=4, failed=1, now=now)
        execution.request_cancellation(job, reason="user", now=now)

    outputs = job_page.load_job_data(_href(run.job_id))
    assert "Running" in _texts(outputs[1])
    assert outputs[9] is False  # stop button enabled
    assert outputs[12] is False  # interval enabled
    assert "(running)" in outputs[7]
    progress_text = " ".join(_texts(outputs[10]))
    assert "Stop requested" in progress_text and "keeps completed results" in progress_text
    assert "5 pending" not in progress_text or "pending" in progress_text

    live = job_page.refresh_live_fields(1, _href(run.job_id))
    assert len(live) == 7 and live[6] is False

    with Session(engine) as session, session.begin():
        job = session.get(db_schema.Job, run.job_id)
        job.heartbeat_at = datetime.now() - timedelta(seconds=FAST_POLICY.stale_heartbeat_seconds + 100)
    with patch.object(job_page, "RUN_POLICY", FAST_POLICY):
        live = job_page.refresh_live_fields(2, _href(run.job_id))
    assert "No heartbeat for" in " ".join(_texts(live[5])) and "interrupted" in " ".join(_texts(live[5]))

    with Session(engine) as session, session.begin():
        execution.finalize(session.get(db_schema.Job, run.job_id), status=JobStatus.CANCELLED, message="Cancelled")
    live = job_page.refresh_live_fields(3, _href(run.job_id))
    assert "Cancelled" in _texts(live[0]) and live[4] is True and live[6] is True


def test_historical_run_shows_exported_diagnostics_instead_of_missing_run_files(engine, tmp_path):
    export = tmp_path / "jobs" / "job_5"
    export.mkdir(parents=True)
    (export / "history.json").write_text(
        json.dumps(
            {
                "job_id": 5,
                "original_status_name": "Failed",
                "message_classes": {"Marked as failed: stale job after Redis restart": 3},
                "subjob_time_range": ["2026-01-01 00:00:00", "2026-01-01 00:10:00"],
            }
        )
    )
    with FailureReportWriter(export / "failures.jsonl") as writer:
        for index in range(3):
            writer.append(
                FailureRecord(
                    index=None,
                    input_id=None,
                    source=None,
                    category="interrupted",
                    message="Marked as failed: stale job after Redis restart",
                    context={"subjob_id": 100 + index},
                )
            )
    with Session(engine) as session, session.begin():
        session.add(
            db_schema.Job(
                job_id=5,
                computer_name="old",
                status=int(JobStatus.FAILED),
                phase=RunPhase.INTERRUPTED,
                priority=0,
                n_inputs=3,
                n_failed=3,
                run_directory="/historical/index_5",
                failure_report_path=str(export / "failures.jsonl"),
                messages="Interrupted: recorded as Running when the database was migrated",
            )
        )

    with Session(engine) as session:
        details = run_summary.load_run_details(session, 5)
    assert details.is_historical and details.request is None and details.summary is None
    assert run_summary.history_rows(details)[0] == ("recorded status", "Failed")
    assert run_summary.failure_total(details) == 3

    outputs = job_page.load_job_data(_href(5))
    assert "interrupted" in " ".join(_texts(outputs[1]))
    configuration_text = " ".join(_texts(outputs[11]))
    assert "Historical per-input records" in configuration_text and "3 input(s)" in configuration_text
    assert "Submitted request" not in configuration_text

    _trigger("job-failures-offset.data")
    body, range_text, *_ = job_page.page_failed_inputs(0, None, None, True, _href(5))
    assert "interrupted" in " ".join(_texts(body)) and range_text == "Showing 1–3 of 3"


def test_missing_job_and_missing_id_render_without_errors(engine):
    outputs = job_page.load_job_data(_href(999))
    assert outputs[1] == "Not found" and outputs[9] is True and outputs[12] is True
    outputs = job_page.load_job_data("http://localhost/job")
    assert outputs[1] == "—"
    with pytest.raises(PreventUpdate):
        job_page.refresh_live_fields(1, "http://localhost/job")
    with pytest.raises(PreventUpdate):
        job_page.load_job_data(None)


def test_stop_run_uses_the_run_control_and_reloads(engine, tmp_path, monkeypatch):
    run = publish_wire_run(engine, tmp_path)
    with patch.object(
        job_page, "cancel_run", return_value={"success": True, "state": "cancelled", "message": "removed"}
    ) as stop:
        is_open, message, icon, toast_open, href = job_page.execute_cancel(1, _href(run.job_id))
    stop.assert_called_once_with(run.job_id)
    assert (is_open, message, icon, toast_open, href) == (False, "removed", "success", True, _href(run.job_id))
    assert "keeps every completed result" in job_page.STOP_EXPLANATION
    with pytest.raises(PreventUpdate):
        job_page.execute_cancel(None, _href(run.job_id))


def test_no_page_text_mentions_subjobs():
    source = open(job_page.__file__, encoding="utf-8").read().lower()
    assert "subjob" not in source


def test_an_incomplete_reconstruction_points_to_its_published_file():
    from laue_portal.pages.job import configuration_content
    from laue_portal.services.run_summary import RunDetails
    from laue_portal.workflows.execution import JobStatus
    from laue_portal.workflows.progress import RunProgress

    progress = RunProgress(
        job_id=4, status=int(JobStatus.FAILED), phase="finished", n_inputs=3, n_succeeded=2, n_failed=1, n_not_run=0
    )
    details = RunDetails(
        progress=progress,
        kind="wire_reconstruction",
        display_id="Reconstruction R4",
        run_directory="/runs/rec_4",
        request=None,
        summary={"artifacts": {"reconstruction": "/runs/rec_4/reconstruction/scan.h5"}},
        history=None,
        results_path=None,
    )

    text = str(configuration_content(details))

    assert "Completed point files are available from this incomplete run" in text
    assert "/runs/rec_4/reconstruction/scan.h5" in text
