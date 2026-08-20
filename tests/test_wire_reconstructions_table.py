"""Focused tests for unified reconstruction UI paths."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import dash
import pytest
from dash.exceptions import PreventUpdate
from sqlalchemy.orm import Session

import lau_dash  # noqa: F401
import laue_portal.pages.create_peakindexing as create_peakindexing
import laue_portal.pages.create_wire_reconstruction as create_wire_reconstruction
from laue_portal.database import db_schema
from laue_portal.pages.reconstructions import (
    _get_recons,
    get_recons,
    handle_peakindex_button,
    handle_recon_button,
    update_button_states,
)
from tests.conftest import (
    create_test_catalog,
    create_test_metadata,
    create_test_reconstruction_run,
    create_test_wire_reconstruction_parameters,
)


def _add_wire_reconstruction(engine, scan_number=12):
    with Session(engine) as session:
        job = db_schema.Job(
            job_id=1,
            computer_name="localhost",
            status=2,
            priority=0,
            submit_time=datetime(2026, 8, 1),
        )
        reconstruction = create_test_reconstruction_run(scan_number=scan_number, job_id=1)
        reconstruction.input_path = "/workspace/raw"
        reconstruction.output_path = "/workspace/analysis/scan_12/rec_1/data"
        reconstruction.wire_parameters = create_test_wire_reconstruction_parameters()
        reconstruction.wire_parameters.filename_prefixes = ["image_%d"]
        reconstruction.wire_parameters.geometry_file = "/workspace/geometries/wire.xml"
        reconstruction.wire_parameters.scan_points = "4-7"
        reconstruction.wire_parameters.scan_points_len = 4
        values = [job, reconstruction]
        if scan_number is not None:
            values.insert(0, create_test_metadata(scan_number))
        session.add_all(values)
        session.commit()
        return reconstruction.id


def _add_scan_catalog(engine, scan_number=12):
    with Session(engine) as session:
        catalog = create_test_catalog(scan_number)
        # Make the regression condition explicit: Session.get(Catalog, 12)
        # must not accidentally find this row by its primary key.
        catalog.catalog_id = 99
        catalog.filefolder = "/workspace/raw"
        catalog.filenamePrefix = ["scan_%d.h5"]
        session.add_all([create_test_metadata(scan_number), catalog])
        session.commit()


@pytest.mark.parametrize(
    ("selected_rows", "expected_disabled"),
    [
        ([], (True, True)),
        ([{"reconstruction_id": 3, "scan_number": 12, "method": "wire"}], (False, False)),
        ([{"reconstruction_id": 4, "scan_number": 12, "method": "ca"}], (True, False)),
        (
            [
                {"reconstruction_id": 3, "scan_number": 12, "method": "wire"},
                {"reconstruction_id": 4, "scan_number": 12, "method": "ca"},
            ],
            (True, True),
        ),
    ],
)
def test_wire_reconstruction_action_buttons_follow_selection(selected_rows, expected_disabled):
    states = update_button_states(selected_rows)
    assert states[::2] == expected_disabled


def test_wire_reconstruction_actions_use_canonical_urls():
    rows = [{"reconstruction_id": 3, "scan_number": 12, "method": "wire"}]
    assert handle_recon_button(1, rows) == "/create-wire-reconstruction?scan_id=12&reconstruction_id=3"
    assert handle_peakindex_button(1, rows) == "/create-peakindexing?scan_id=12&reconstruction_id=3"
    assert handle_recon_button(0, rows) is dash.no_update
    assert handle_peakindex_button(0, rows) is dash.no_update
    assert handle_recon_button(1, [{"reconstruction_id": 4, "method": "ca"}]) is dash.no_update


def test_wire_reconstruction_table_reads_unified_rows(empty_test_database):
    engine, _ = empty_test_database
    reconstruction_id = _add_wire_reconstruction(engine)

    with patch("laue_portal.database.session_utils.get_engine", return_value=engine):
        columns, rows = _get_recons()

    assert len(rows) == 1
    assert rows[0]["reconstruction_id"] == reconstruction_id
    assert rows[0]["scan_number"] == 12
    assert rows[0]["scan_points_len"] == 4
    assert rows[0]["method"] == "wire"
    assert "wirerecon_id" not in rows[0]

    id_column = next(column for column in columns if column["field"] == "reconstruction_id")
    assert id_column["cellRenderer"] == "ReconstructionLinkRenderer"


def test_wire_reconstruction_table_callback(empty_test_database):
    engine, _ = empty_test_database
    with patch("laue_portal.database.session_utils.get_engine", return_value=engine):
        columns, rows = get_recons("/reconstructions")
    assert columns
    assert rows == []
    with pytest.raises(PreventUpdate):
        get_recons("/wrong-path")


def test_wire_create_loader_copies_selected_r_run(empty_test_database):
    engine, _ = empty_test_database
    reconstruction_id = _add_wire_reconstruction(engine)
    loaded = []

    with (
        patch("laue_portal.database.session_utils.get_engine", return_value=engine),
        patch.dict(
            create_wire_reconstruction.DEFAULT_VARIABLES,
            {"root_path": "/workspace", "author": "new author", "notes": "new notes"},
        ),
        patch.object(create_wire_reconstruction, "set_wire_recon_form_props", side_effect=loaded.append),
        patch.object(create_wire_reconstruction, "set_props"),
    ):
        result = create_wire_reconstruction.load_scan_data_from_url(
            f"http://localhost/create-wire-reconstruction?scan_id=12&reconstruction_id={reconstruction_id}"
        )

    assert result is dash.no_update
    form_data = loaded[0]
    assert form_data.identity_value == f"SN12 | R{reconstruction_id}"
    assert form_data.data_path == "raw"
    assert form_data.filename_prefixes == ["image_%d"]
    assert form_data.geometry_file == "geometries/wire.xml"
    assert form_data.scan_points == "4-7"
    assert form_data.output_path_template == "analysis/scan_12/rec_%d/data"


def test_wire_create_loader_reads_catalog_by_scan_number(empty_test_database):
    engine, _ = empty_test_database
    _add_scan_catalog(engine)
    loaded = []

    with (
        patch("laue_portal.database.session_utils.get_engine", return_value=engine),
        patch.dict(create_wire_reconstruction.DEFAULT_VARIABLES, {"root_path": "/workspace"}),
        patch.object(create_wire_reconstruction, "set_wire_recon_form_props", side_effect=loaded.append),
        patch.object(create_wire_reconstruction, "set_props"),
    ):
        create_wire_reconstruction.load_scan_data_from_url("http://localhost/create-wire-reconstruction?scan_id=12")

    form_data = loaded[0]
    assert form_data.data_path == "raw"
    assert form_data.input_path == "/workspace/raw"
    assert form_data.filename_prefixes == ["scan_%d.h5"]


def test_index_create_loader_reads_catalog_by_scan_number(empty_test_database):
    engine, _ = empty_test_database
    _add_scan_catalog(engine)
    loaded = []

    with (
        patch("laue_portal.database.session_utils.get_engine", return_value=engine),
        patch.dict(create_peakindexing.DEFAULT_VARIABLES, {"root_path": "/workspace"}),
        patch.object(create_peakindexing, "set_peakindex_form_props", side_effect=loaded.append),
        patch.object(create_peakindexing, "set_props"),
    ):
        create_peakindexing.load_scan_data_from_url("http://localhost/create-peakindexing?scan_id=12")

    form_data = loaded[0]
    assert form_data.data_path == "raw"
    assert form_data.input_path == "/workspace/raw"
    assert form_data.filename_prefixes == ["scan_%d.h5"]


def test_index_create_loader_uses_one_optional_reconstruction_parent(empty_test_database):
    engine, _ = empty_test_database
    reconstruction_id = _add_wire_reconstruction(engine)
    loaded = []

    with (
        patch("laue_portal.database.session_utils.get_engine", return_value=engine),
        patch.dict(
            create_peakindexing.DEFAULT_VARIABLES,
            {"root_path": "/workspace", "author": "new author", "notes": "new notes"},
        ),
        patch.object(create_peakindexing, "set_peakindex_form_props", side_effect=loaded.append),
        patch.object(create_peakindexing, "set_props"),
    ):
        create_peakindexing.load_scan_data_from_url(
            f"http://localhost/create-peakindexing?scan_id=12&reconstruction_id={reconstruction_id}"
        )

    form_data = loaded[0]
    assert form_data.identity_value == f"SN12 | R{reconstruction_id}"
    assert form_data.reconstruction_id == reconstruction_id
    assert form_data.data_path == "analysis/scan_12/rec_1/data"
    assert form_data.filename_prefixes == ["image_%d"]
    assert form_data.scan_points == "4-7"
    assert form_data.output_path_template == (f"analysis/scan_12/rec_{reconstruction_id}/index_%d")


def _no_validation_errors():
    return {"errors": {}, "warnings": {}, "successes": {}}


def test_wire_submission_passes_a_request_to_the_workflow_service(empty_test_database, tmp_path):
    engine, _ = empty_test_database
    created_run = SimpleNamespace(id=41)
    callback_context = SimpleNamespace(states={"data_path.value": str(tmp_path)})

    with (
        patch.object(create_wire_reconstruction.dash, "callback_context", callback_context),
        patch.object(
            create_wire_reconstruction,
            "validate_wire_reconstruction_inputs",
            return_value=_no_validation_errors(),
        ),
        patch.object(create_wire_reconstruction, "apply_validation_highlights"),
        patch.object(create_wire_reconstruction, "update_validation_alerts"),
        patch.object(create_wire_reconstruction.session_utils, "get_engine", return_value=engine),
        patch.object(create_wire_reconstruction, "create_reconstruction", return_value=created_run) as create,
        patch.object(create_wire_reconstruction, "enqueue_reconstruction") as enqueue,
        patch.object(create_wire_reconstruction, "set_props"),
    ):
        create_wire_reconstruction.submit_parameters(
            1,
            str(tmp_path),
            "SN12",
            "author",
            "notes",
            "geometry.xml",
            10,
            "leading",
            -10,
            10,
            1,
            "1-2",
            "raw",
            "image_%d.h5",
            "analysis/scan_12/rec_%d/data",
        )

    request = create.call_args.args[0]
    assert request.scan_number == 12
    assert request.filename_prefixes == ("image_%d.h5",)
    assert request.output_path_template.endswith("analysis/scan_12/rec_%d/data")
    enqueue.assert_called_once_with(41)


def test_index_submission_uses_one_reconstruction_id(empty_test_database, tmp_path):
    engine, _ = empty_test_database
    reconstruction_id = _add_wire_reconstruction(engine)
    created_run = SimpleNamespace(id=52)
    callback_context = SimpleNamespace(states={"data_path.value": str(tmp_path)})

    with (
        patch.object(create_peakindexing.dash, "callback_context", callback_context),
        patch.object(
            create_peakindexing,
            "validate_peakindexing_inputs",
            return_value=_no_validation_errors(),
        ),
        patch.object(create_peakindexing, "apply_validation_highlights"),
        patch.object(create_peakindexing, "update_validation_alerts"),
        patch.object(create_peakindexing.session_utils, "get_engine", return_value=engine),
        patch.object(create_peakindexing, "create_indexing", return_value=created_run) as create,
        patch.object(create_peakindexing, "enqueue_indexing") as enqueue,
        patch.object(create_peakindexing, "set_props"),
    ):
        create_peakindexing.submit_parameters(
            1,
            str(tmp_path),
            f"SN12 | R{reconstruction_id}",
            "author",
            "notes",
            None,
            None,
            0.5,
            18,
            300,
            20,
            "Lorentzian",
            "1-2",
            None,
            3,
            200,
            False,
            None,
            17.2,
            35,
            0.1,
            "001",
            72,
            True,
            "raw",
            "image_%d.h5",
            f"analysis/scan_12/rec_{reconstruction_id}/index_%d",
            "geometry.xml",
            "crystal.xtal",
            None,
            "output.xml",
        )

    request = create.call_args.args[0]
    assert request.scan_number == 12
    assert request.reconstruction_id == reconstruction_id
    assert request.filename_prefixes == ("image_%d.h5",)
    enqueue.assert_called_once_with(52)
