"""Persist a submission identity before contacting DM; never automatically submit twice."""

from __future__ import annotations

import logging
from uuid import uuid4

from sqlalchemy.orm import Session

from laue_portal.database import db_schema
from laue_portal.processing.bdp.dm import DMClient
from laue_portal.processing.bdp.plan import save_plan
from laue_portal.processing.bdp.settings import portal_settings, require_backend
from laue_portal.workflows import execution

logger = logging.getLogger(__name__)


def submit_run(job_id, *, engine, settings=None, client=None):
    settings = portal_settings(settings)
    client = client or DMClient(settings["dm"])
    submission_id = str(uuid4())
    with Session(engine) as session, session.begin():
        job = session.get(db_schema.Job, job_id)
        if job is None:
            raise ValueError(f"Job {job_id} does not exist")
        execution.assert_enqueueable(job)
        require_backend(job.backend, settings)
        plan = save_plan(job, settings, submission_id)
        job.submission_id = submission_id
        job.external_state = "submitting"
        execution.mark_queued(job, f"dm:{submission_id}")
    try:
        record = client.submit(plan)
        external_id = record["id"] if isinstance(record, dict) else str(record)
        if not external_id:
            raise ValueError("DM returned no processing job ID")
    except Exception:
        # A timeout may mean DM accepted the job but its reply was lost.
        # The poller searches by submissionId; it must never blindly resubmit.
        with Session(engine) as session, session.begin():
            job = session.get(db_schema.Job, job_id)
            job.external_state = "submission_uncertain"
            execution._append_message(job, "DM submission response was lost; reconciliation required before retrying")
        logger.exception("DM submission %s needs reconciliation", submission_id)
        raise
    with Session(engine) as session, session.begin():
        job = session.get(db_schema.Job, job_id)
        job.external_id = external_id
        job.external_state = "pending"
    return external_id
