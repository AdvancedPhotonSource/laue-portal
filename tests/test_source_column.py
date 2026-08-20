"""Focused tests for canonical indexing source identities."""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from sqlalchemy.orm import Session

import lau_dash  # noqa: F401
from laue_portal.database import db_schema
from laue_portal.pages.peakindexings import _get_peakindexings
from tests.conftest import (
    create_test_indexing_run,
    create_test_lauego_parameters,
    create_test_metadata,
    create_test_reconstruction_run,
    create_test_wire_reconstruction_parameters,
)


def _add_linked_indexing(engine):
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
        reconstruction = create_test_reconstruction_run(scan_number=12, job_id=1)
        reconstruction.wire_parameters = create_test_wire_reconstruction_parameters()
        session.add_all(
            [
                create_test_metadata(12),
                reconstruction_job,
                indexing_job,
                reconstruction,
            ]
        )
        session.flush()
        indexing = create_test_indexing_run(
            scan_number=12,
            job_id=2,
            reconstruction_id=reconstruction.id,
        )
        indexing.lauego_parameters = create_test_lauego_parameters()
        session.add(indexing)
        session.commit()
        return reconstruction.id, indexing.id


def test_source_column_replaces_method_specific_parent_columns(empty_test_database):
    engine, _ = empty_test_database
    with patch("laue_portal.database.session_utils.get_engine", return_value=engine):
        columns, _ = _get_peakindexings()

    headers = [column["headerName"] for column in columns]
    assert headers.count("Source") == 1
    assert "Recon ID" not in headers
    assert "Wire Recon ID" not in headers
    source = next(column for column in columns if column["headerName"] == "Source")
    assert source["cellRenderer"] == "SourceLinksRenderer"
    getter = source["valueGetter"]["function"]
    assert "scan_number" in getter
    assert "reconstruction_id" in getter
    assert "wirerecon_id" not in getter
    assert "recon_id" not in getter


def test_linked_indexing_row_carries_one_reconstruction_parent(empty_test_database):
    engine, _ = empty_test_database
    reconstruction_id, indexing_id = _add_linked_indexing(engine)

    with patch("laue_portal.database.session_utils.get_engine", return_value=engine):
        _, rows = _get_peakindexings()

    assert len(rows) == 1
    assert rows[0]["indexing_id"] == indexing_id
    assert rows[0]["scan_number"] == 12
    assert rows[0]["reconstruction_id"] == reconstruction_id
    assert rows[0]["reconstruction_method"] == "wire"


def test_source_renderer_uses_canonical_urls():
    javascript = Path("assets/customAgGridFunctions.js").read_text()

    source_start = javascript.index("dagcomponentfuncs.SourceLinksRenderer")
    source_end = javascript.index("};", source_start)
    renderer = javascript[source_start:source_end]

    assert "/scan?scan_id=" in renderer
    assert "'/wire_reconstruction'" in renderer
    assert "'?reconstruction_id='" in renderer
    assert "'/reconstruction'" in renderer
    assert "wirerecon_id" not in renderer
    assert "recon_id" not in renderer


def test_indexing_renderer_uses_i_identity():
    javascript = Path("assets/customAgGridFunctions.js").read_text()

    renderer_start = javascript.index("dagcomponentfuncs.IndexingLinkRenderer")
    renderer_end = javascript.index("};", renderer_start)
    renderer = javascript[renderer_start:renderer_end]

    assert "/peakindexing?indexing_id=" in renderer
    assert "'I' + props.value" in renderer
    assert "peakindex_id" not in renderer
