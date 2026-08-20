"""Tests for canonical SN/R/I form identities."""

from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from laue_portal.database import db_schema
from laue_portal.workflows.identity import parse_workflow_identities
from tests.conftest import create_test_metadata


def _add_chain(engine):
    with Session(engine) as session:
        reconstruction_job = db_schema.Job(
            job_id=1,
            computer_name="localhost",
            status=2,
            priority=0,
            submit_time=datetime(2026, 8, 1),
        )
        indexing_job = db_schema.Job(
            job_id=2,
            computer_name="localhost",
            status=2,
            priority=0,
            submit_time=datetime(2026, 8, 2),
        )
        reconstruction = db_schema.ReconstructionRun(
            scan_number=12,
            job_id=1,
            method="wire",
            input_path="/input",
            output_path="/reconstruction",
            created_at=datetime(2026, 8, 1),
        )
        session.add_all([create_test_metadata(12), reconstruction_job, indexing_job, reconstruction])
        session.flush()
        indexing = db_schema.IndexingRun(
            scan_number=12,
            reconstruction_id=reconstruction.id,
            job_id=2,
            method="lauego",
            input_path="/reconstruction",
            output_path="/indexing",
            created_at=datetime(2026, 8, 2),
        )
        session.add(indexing)
        session.commit()
        return reconstruction.id, indexing.id


def test_r_and_i_identities_load_their_parent_chain(empty_test_database):
    engine, _ = empty_test_database
    reconstruction_id, indexing_id = _add_chain(engine)

    with Session(engine) as session:
        reconstruction = parse_workflow_identities(f"R{reconstruction_id}", session)[0]
        indexing = parse_workflow_identities(f"I{indexing_id}", session)[0]

    assert (reconstruction.scan_number, reconstruction.reconstruction_id) == (12, reconstruction_id)
    assert (indexing.scan_number, indexing.reconstruction_id, indexing.indexing_id) == (
        12,
        reconstruction_id,
        indexing_id,
    )


def test_full_and_pooled_identities_are_supported(empty_test_database):
    engine, _ = empty_test_database
    reconstruction_id, indexing_id = _add_chain(engine)

    with Session(engine) as session:
        identities = parse_workflow_identities(
            f"SN12 | R{reconstruction_id} | I{indexing_id}; SN13",
            session,
        )

    assert identities[0].indexing_id == indexing_id
    assert identities[1].scan_number == 13


@pytest.mark.parametrize("value", ["WR1", "MR1", "PI1", "Rnope"])
def test_legacy_and_malformed_identities_are_rejected(empty_test_database, value):
    engine, _ = empty_test_database
    with Session(engine) as session, pytest.raises(ValueError):
        parse_workflow_identities(value, session)
