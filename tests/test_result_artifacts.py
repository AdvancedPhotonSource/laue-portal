"""Tests for indexing-result discovery and historical XML conversion (service and CLI)."""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

import h5py
import numpy as np
import pytest
from lauelab.visualization import convert_xml
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from laue_portal.database import db_schema, session_utils
from laue_portal.services import indexing_results as service
from scripts import convert_indexing_results as cli
from tests.conftest import create_test_lauego_parameters

FIXTURE_XML = Path(__file__).parent / "fixtures" / "test_indexing.xml"


@pytest.fixture
def engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'results.db'}")
    event.listen(engine, "connect", session_utils.enable_sqlite_pragmas)
    db_schema.Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def _add_run(engine, run_id, output_path, *, output_xml="output.xml", results_path=None):
    with Session(engine) as session:
        session.add(
            db_schema.Job(job_id=run_id, computer_name="h", status=2, priority=0, submit_time=datetime(2026, 1, 1))
        )
        run = db_schema.IndexingRun(
            id=run_id,
            job_id=run_id,
            method="lauego",
            input_path="/data",
            output_path=os.fspath(output_path) if output_path is not None else None,
            created_at=datetime(2026, 1, 1),
            results_path=results_path,
        )
        parameters = create_test_lauego_parameters()
        parameters.output_xml = output_xml
        run.lauego_parameters = parameters
        session.add(run)
        session.commit()
    return run_id


def _load(engine, run_id):
    with Session(engine) as session:
        return service.load_indexing_run(session, run_id)


def _results_path(engine, run_id):
    with Session(engine) as session:
        return session.get(db_schema.IndexingRun, run_id).results_path


def _xml_run(engine, tmp_path, run_id, name="output.xml", xml_name=None, *, identical_to=None):
    """A run with its own copy of the fixture XML; copies differ unless ``identical_to`` names a run."""

    directory = tmp_path / f"index_{run_id}"
    directory.mkdir()
    target = directory / (xml_name or name)
    shutil.copy(FIXTURE_XML, target)
    marker = identical_to if identical_to is not None else run_id
    with open(target, "a", encoding="utf-8") as handle:
        handle.write(f"<!-- historical output {marker} -->\n")
    _add_run(engine, run_id, directory, output_xml=name)
    return directory


def _write_frame_h5(path):
    with h5py.File(path, "w") as handle:
        handle.create_dataset("entry1/data/data", data=np.zeros((4, 4), dtype=np.uint16))


# --- resolution -------------------------------------------------------------------


def test_resolution_prefers_a_valid_recorded_reference(engine, tmp_path):
    directory = _xml_run(engine, tmp_path, 1)
    converted = convert_xml(directory / "output.xml", tmp_path / "elsewhere" / "results.h5")
    with Session(engine) as session, session.begin():
        session.get(db_schema.IndexingRun, 1).results_path = str(converted)

    resolution = service.resolve_indexing_artifacts(_load(engine, 1))

    assert resolution.status == service.STATUS_RESULTS
    assert (resolution.results_path, resolution.results_source) == (str(converted), "recorded")
    assert resolution.results_summary.n_frames == 4
    assert resolution.problems == ()
    assert resolution.as_dict()["results_summary"]["source"].endswith("output.xml")


def test_unusable_recorded_reference_falls_through_with_a_problem(engine, tmp_path):
    directory = _xml_run(engine, tmp_path, 1)
    with Session(engine) as session, session.begin():
        session.get(db_schema.IndexingRun, 1).results_path = str(tmp_path / "gone.h5")
    convert_xml(directory / "output.xml", directory / "output.h5")

    resolution = service.resolve_indexing_artifacts(_load(engine, 1))

    assert (resolution.status, resolution.results_source) == (service.STATUS_RESULTS, "canonical")
    assert resolution.results_path == str(directory / "output.h5")
    assert resolution.problems[0].startswith("recorded results reference unusable")


def test_a_detector_frame_named_output_h5_is_never_taken_for_results(engine, tmp_path):
    directory = _xml_run(engine, tmp_path, 1)
    _write_frame_h5(directory / "output.h5")

    resolution = service.resolve_indexing_artifacts(_load(engine, 1))

    assert resolution.status == service.STATUS_XML_ONLY
    assert resolution.xml_path == str(directory / "output.xml")
    assert "not a lauelab indexing-results file" in resolution.problems[0]


def test_interrupted_results_file_is_reported_not_used(engine, tmp_path):
    directory = _xml_run(engine, tmp_path, 1)
    good = convert_xml(directory / "output.xml", directory / "output.h5")
    with h5py.File(good, "a") as handle:
        del handle["frames/frame_ids"]  # a writer that never closed cleanly

    resolution = service.resolve_indexing_artifacts(_load(engine, 1))

    assert resolution.status == service.STATUS_XML_ONLY
    assert "canonical results file unusable" in resolution.problems[0]


def test_xml_is_found_by_recorded_name_absolute_or_single_file_and_never_guessed(engine, tmp_path):
    recorded = _xml_run(engine, tmp_path, 1, name="named.xml")
    absolute_dir = tmp_path / "abs"
    absolute_dir.mkdir()
    shutil.copy(FIXTURE_XML, absolute_dir / "far.xml")
    _add_run(engine, 2, tmp_path / "index_2", output_xml=str(absolute_dir / "far.xml"))
    single = _xml_run(engine, tmp_path, 3, name="missing.xml", xml_name="only.xml")
    ambiguous = _xml_run(engine, tmp_path, 4, name="missing.xml", xml_name="a.xml")
    shutil.copy(FIXTURE_XML, ambiguous / "b.xml")
    _add_run(engine, 5, tmp_path / "index_5")
    _add_run(engine, 6, None)

    assert service.resolve_indexing_artifacts(_load(engine, 1)).xml_path == str(recorded / "named.xml")
    assert service.resolve_indexing_artifacts(_load(engine, 2)).xml_path == str(absolute_dir / "far.xml")
    assert service.resolve_indexing_artifacts(_load(engine, 3)).xml_path == str(single / "only.xml")
    four = service.resolve_indexing_artifacts(_load(engine, 4))
    assert four.status == service.STATUS_AMBIGUOUS
    assert four.xml_candidates == (str(ambiguous / "a.xml"), str(ambiguous / "b.xml"))
    assert four.xml_path is None and four.convertible is False
    assert service.resolve_indexing_artifacts(_load(engine, 5)).status == service.STATUS_MISSING
    assert service.resolve_indexing_artifacts(_load(engine, 6)).status == service.STATUS_MISSING
    assert service.deterministic_xml_path(_load(engine, 4)) is None
    assert service.resolve_for_indexing_id(99, engine=engine) is None
    assert service.resolve_for_indexing_id(1, engine=engine).status == service.STATUS_XML_ONLY


# --- conversion -------------------------------------------------------------------


def test_conversion_publishes_validated_files_links_duplicates_and_continues_past_bad_documents(engine, tmp_path):
    good = _xml_run(engine, tmp_path, 1)
    duplicate = _xml_run(engine, tmp_path, 2, identical_to=1)  # byte-identical copy of the same historical output
    malformed = _xml_run(engine, tmp_path, 3)
    (malformed / "output.xml").write_text("<AllSteps>\n")
    empty = _xml_run(engine, tmp_path, 4)
    (empty / "output.xml").write_text("<AllSteps></AllSteps>\n")
    _add_run(engine, 5, tmp_path / "index_5")  # nothing on disk
    ambiguous = _xml_run(engine, tmp_path, 6, name="missing.xml", xml_name="a.xml")
    shutil.copy(FIXTURE_XML, ambiguous / "b.xml")
    invalid_existing = _xml_run(engine, tmp_path, 7)
    _write_frame_h5(invalid_existing / "output.h5")
    seen = []

    report = service.convert_indexing_results(engine=engine, progress=lambda outcome: seen.append(outcome.indexing_id))

    outcomes = {outcome.indexing_id: outcome for outcome in report.outcomes}
    assert seen == [1, 2, 3, 4, 5, 6, 7]
    assert outcomes[1].outcome == service.OUTCOME_CONVERTED
    assert outcomes[1].destination == str(good / "output.h5")
    assert outcomes[1].n_frames == 4
    assert outcomes[2].outcome == service.OUTCOME_LINKED
    assert (outcomes[2].destination, outcomes[2].linked_to) == (str(good / "output.h5"), 1)
    assert not (duplicate / "output.h5").exists()
    assert outcomes[3].outcome == service.OUTCOME_MALFORMED and "ParseError" in outcomes[3].message
    assert outcomes[4].outcome == service.OUTCOME_MALFORMED and "no <step> elements" in outcomes[4].message
    assert outcomes[5].outcome == service.OUTCOME_MISSING
    assert outcomes[6].outcome == service.OUTCOME_AMBIGUOUS and "a.xml" in outcomes[6].message
    assert outcomes[7].outcome == service.OUTCOME_INVALID_EXISTING
    assert report.counts()[service.OUTCOME_CONVERTED] == 1
    assert report.counts()[service.OUTCOME_FAILED] == 0
    # Pointers are set only for published, validated files; originals are retained.
    assert _results_path(engine, 1) == str(good / "output.h5")
    assert _results_path(engine, 2) == str(good / "output.h5")
    assert all(_results_path(engine, run_id) is None for run_id in (3, 4, 5, 6, 7))
    assert (good / "output.xml").exists() and (malformed / "output.xml").exists()
    assert not any(name.startswith("output.h5.partial") for name in os.listdir(good))
    text = report.format_text()
    assert "converted: 1" in text and "linked: 1" in text and "malformed: 2" in text
    with h5py.File(good / "output.h5") as handle:
        assert handle.attrs["source"].endswith("index_1/output.xml")


def test_rerun_is_idempotent_and_dry_run_writes_nothing(engine, tmp_path):
    good = _xml_run(engine, tmp_path, 1)
    dry = service.convert_indexing_results(engine=engine, dry_run=True)
    assert [outcome.outcome for outcome in dry.outcomes] == [service.OUTCOME_WOULD_CONVERT]
    assert dry.outcomes[0].destination == str(good / "output.h5")
    assert sorted(os.listdir(good)) == ["output.xml"]
    assert _results_path(engine, 1) is None

    first = service.convert_indexing_results([1], engine=engine)
    stamp = os.stat(good / "output.h5").st_mtime_ns
    second = service.convert_indexing_results([1], engine=engine)
    assert first.outcomes[0].outcome == service.OUTCOME_CONVERTED
    assert second.outcomes[0].outcome == service.OUTCOME_ALREADY_CONVERTED
    assert os.stat(good / "output.h5").st_mtime_ns == stamp
    assert second.outcomes[0].n_frames == 4

    with Session(engine) as session, session.begin():
        session.get(db_schema.IndexingRun, 1).results_path = None  # pointer lost; file still valid
    third = service.convert_indexing_results([1], engine=engine)
    assert third.outcomes[0].outcome == service.OUTCOME_ALREADY_CONVERTED
    assert _results_path(engine, 1) == str(good / "output.h5")
    assert service.convert_indexing_results([42], engine=engine).outcomes[0].outcome == service.OUTCOME_MISSING


def test_invalid_existing_destination_is_replaced_only_on_request(engine, tmp_path):
    directory = _xml_run(engine, tmp_path, 1)
    _write_frame_h5(directory / "output.h5")

    kept = service.convert_indexing_results([1], engine=engine)
    assert kept.outcomes[0].outcome == service.OUTCOME_INVALID_EXISTING
    replaced = service.convert_indexing_results([1], engine=engine, replace_invalid=True)
    assert replaced.outcomes[0].outcome == service.OUTCOME_CONVERTED
    assert service.validate_results(directory / "output.h5")[0].n_frames == 4


def test_concurrent_publication_by_another_converter_is_recognized(engine, tmp_path, monkeypatch):
    directory = _xml_run(engine, tmp_path, 1)
    real_convert = service.convert_xml

    def racing_convert(xml_path, output_path, **kwargs):
        real_convert(xml_path, output_path)  # the "button" finished first
        raise FileExistsError(output_path)

    monkeypatch.setattr(service, "convert_xml", racing_convert)
    report = service.convert_indexing_results([1], engine=engine)
    assert report.outcomes[0].outcome == service.OUTCOME_ALREADY_CONVERTED
    assert report.outcomes[0].message == "published concurrently"
    assert _results_path(engine, 1) == str(directory / "output.h5")


def test_explicit_destination_root_and_geometry_override(engine, tmp_path):
    _xml_run(engine, tmp_path, 1)
    geometry = Path(__file__).parent / "fixtures" / "lauelab" / "geoN_2022-03-29_14-15-05.xml"
    root = tmp_path / "writable"

    report = service.convert_indexing_results([1], engine=engine, destination_root=str(root), geometry=str(geometry))

    destination = root / "index_1" / "output.h5"
    assert report.outcomes[0].outcome == service.OUTCOME_CONVERTED
    assert report.outcomes[0].destination == str(destination)
    assert _results_path(engine, 1) == str(destination)
    with h5py.File(destination) as handle:
        assert handle["geometry"].attrs["path"] == str(geometry)
        assert "geometry/xml" in handle


def test_unexpected_converter_errors_are_recorded_not_raised(engine, tmp_path, monkeypatch):
    _xml_run(engine, tmp_path, 1)
    _xml_run(engine, tmp_path, 2)

    def exploding(xml_path, output_path, **kwargs):
        if "index_1" in str(xml_path):
            raise RuntimeError("boom")
        return service.convert_xml.__wrapped__(xml_path, output_path, **kwargs)

    exploding.__wrapped__ = service.convert_xml
    monkeypatch.setattr(service, "convert_xml", exploding)
    report = service.convert_indexing_results(engine=engine)
    assert [outcome.outcome for outcome in report.outcomes] == [service.OUTCOME_FAILED, service.OUTCOME_CONVERTED]
    assert "RuntimeError: boom" in report.outcomes[0].message


def test_pattern_assignments_without_peak_indices_are_a_reported_failure(engine, tmp_path):
    """Five historical documents carry hkl assignments but no PkIndex; the converter's output fails validation."""

    import re

    directory = _xml_run(engine, tmp_path, 1)
    text = (directory / "output.xml").read_text()
    stripped = re.sub(r"\s*<PkIndex>.*?</PkIndex>", "", text, flags=re.DOTALL)
    assert stripped != text
    (directory / "output.xml").write_text(stripped)

    report = service.convert_indexing_results([1], engine=engine)

    outcome = report.outcomes[0]
    assert outcome.outcome == service.OUTCOME_FAILED
    assert "converter output failed validation" in outcome.message
    assert "without PkIndex" in outcome.message
    assert not (directory / "output.h5").exists()
    assert not any(name.startswith("output.h5.partial") for name in os.listdir(directory))
    assert _results_path(engine, 1) is None
    assert service.diagnose_xml(str(FIXTURE_XML)) == ""

    # The variant found in five March 2026 documents: Nindexed smaller than the assignments listed.
    other = _xml_run(engine, tmp_path, 2)
    text = (other / "output.xml").read_text()
    lowered = text.replace('Nindexed="9"', 'Nindexed="3"', 1)
    assert lowered != text
    (other / "output.xml").write_text(lowered)
    outcome = service.convert_indexing_results([2], engine=engine).outcomes[0]
    assert outcome.outcome == service.OUTCOME_FAILED
    assert "1 of 5 patterns have an Nindexed attribute that disagrees" in outcome.message


# --- CLI ------------------------------------------------------------------------------


def test_cli_dry_run_then_convert_with_report(engine, tmp_path, capsys):
    _xml_run(engine, tmp_path, 1)
    _xml_run(engine, tmp_path, 2, name="b.xml")
    db_file = tmp_path / "results.db"
    report_file = tmp_path / "report.json"

    assert cli.main(["--all", "--dry-run", "--db", str(db_file)]) == 0
    out = capsys.readouterr().out
    assert "DRY RUN: 2 indexing run(s) examined" in out and "would_convert: 2" in out
    assert not (tmp_path / "index_1" / "output.h5").exists()

    assert cli.main(["I1", "2", "--db", str(db_file), "--report", str(report_file)]) == 0
    out = capsys.readouterr().out
    assert "converted: 2" in out
    document = json.loads(report_file.read_text())
    assert document["format"] == "laue-portal-conversion-report"
    assert document["counts"]["converted"] == 2
    assert [item["indexing_id"] for item in document["outcomes"]] == [1, 2]
    assert (tmp_path / "index_2" / "output.h5").exists()

    with pytest.raises(SystemExit, match="Give indexing identities or --all"):
        cli.main(["--db", str(db_file)])
    with pytest.raises(SystemExit, match="does not exist"):
        cli.main(["--all", "--db", str(tmp_path / "nope.db")])
    assert cli.build_parser().parse_args(["3-5", "I9"]).ids == ["3-5", "I9"]
    assert service.iter_ids(["3-5", "I9", "12"]) == [3, 4, 5, 9, 12]


def test_cli_exit_code_reports_failures(engine, tmp_path, monkeypatch):
    _xml_run(engine, tmp_path, 1)
    monkeypatch.setattr(service, "convert_xml", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk full")))
    assert cli.main(["--all", "--db", str(tmp_path / "results.db")]) == 1
