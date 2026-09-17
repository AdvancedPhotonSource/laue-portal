"""Tests for run input manifests, frozen requests, failure reports, and publication."""

import json
import os
import stat

import pytest

from laue_portal.workflows import publication
from laue_portal.workflows.files import ResolvedInput
from laue_portal.workflows.manifest import (
    CATEGORY_CANCELLED,
    CATEGORY_ERROR,
    CATEGORY_INPUT,
    CATEGORY_MEMORY,
    CATEGORY_NUMERICAL,
    FAILURE_REPORT_FILENAME,
    MANIFEST_FILENAME,
    REQUEST_FORMAT,
    RESERVED_RUN_FILENAMES,
    FailureRecord,
    FailureReportWriter,
    ManifestEntry,
    ManifestError,
    build_manifest_entries,
    classify_error,
    count_failure_records,
    manifest_digest,
    read_failure_report,
    read_manifest,
    read_request,
    verify_manifest,
    write_manifest,
    write_request,
)


def _inputs(*names, template_index=0):
    return tuple(ResolvedInput(f"/data/{name}", template_index, (index,)) for index, name in enumerate(names, start=1))


def test_entries_use_file_stems_in_run_order_with_selection_identity():
    inputs = (
        ResolvedInput("/data/scan_7_0.h5", 0, (7, 0)),
        ResolvedInput("/data/scan_7_1.h5", 0, (7, 1)),
        ResolvedInput("/data/other_3.h5", 1, (3,)),
        ResolvedInput("/data/fixed.h5", 2, ()),
    )

    entries = build_manifest_entries(inputs, depths={1: -49.0})

    assert [(e.index, e.input_id, e.template_index, e.scan_point, e.depth_point, e.depth) for e in entries] == [
        (0, "scan_7_0", 0, 7, 0, None),
        (1, "scan_7_1", 0, 7, 1, -49.0),
        (2, "other_3", 1, 3, None, None),
        (3, "fixed", 2, None, None, None),
    ]
    assert entries[0].source == "/data/scan_7_0.h5"


def test_shared_stems_fall_back_to_full_filenames_for_the_whole_run():
    entries = build_manifest_entries(_inputs("a.h5", "a.tif", "b.h5"))
    assert [entry.input_id for entry in entries] == ["a.h5", "a.tif", "b.h5"]


def test_duplicate_filenames_and_empty_runs_are_rejected():
    with pytest.raises(ManifestError, match="not unique"):
        build_manifest_entries((ResolvedInput("/x/a.h5", 0, (1,)), ResolvedInput("/y/a.h5", 0, (2,))))
    with pytest.raises(ManifestError, match="at least one input"):
        build_manifest_entries(())


def test_manifest_roundtrip_digest_and_verification(tmp_path):
    path = tmp_path / MANIFEST_FILENAME
    entries = build_manifest_entries(_inputs("f_1.h5", "f_2.h5", "f_3.h5"))

    summary = write_manifest(path, entries)

    assert summary.path == os.fspath(path)
    assert summary.n_inputs == 3
    assert summary.sha256 == manifest_digest(path)
    assert list(read_manifest(path)) == list(entries)
    assert sorted(os.listdir(tmp_path)) == [MANIFEST_FILENAME]
    verify_manifest(path, expected_digest=summary.sha256, expected_count=3)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[1]) == {
        "index": 1,
        "input_id": "f_2",
        "source": "/data/f_2.h5",
        "template_index": 0,
        "scan_point": 2,
        "depth_point": None,
        "depth": None,
    }

    with pytest.raises(ManifestError, match="digest"):
        verify_manifest(path, expected_digest="0" * 64, expected_count=3)
    with pytest.raises(ManifestError, match="holds 3 inputs"):
        verify_manifest(path, expected_digest=summary.sha256, expected_count=4)
    with pytest.raises(ManifestError, match="missing"):
        verify_manifest(tmp_path / "absent.jsonl", expected_digest=summary.sha256, expected_count=3)


def test_manifest_never_overwrites_and_leaves_no_partial_on_failure(tmp_path):
    path = tmp_path / MANIFEST_FILENAME
    entries = build_manifest_entries(_inputs("f_1.h5"))
    write_manifest(path, entries)
    original = path.read_bytes()

    with pytest.raises(FileExistsError):
        write_manifest(path, build_manifest_entries(_inputs("g_1.h5")))
    assert path.read_bytes() == original
    assert sorted(os.listdir(tmp_path)) == [MANIFEST_FILENAME]

    bad_order = (ManifestEntry(1, "x", "/data/x.h5", 0, 1, None),)
    with pytest.raises(ManifestError, match="expected 0"):
        write_manifest(tmp_path / "other.jsonl", bad_order)
    assert sorted(os.listdir(tmp_path)) == [MANIFEST_FILENAME]

    with pytest.raises(ManifestError, match="at least one input"):
        write_manifest(tmp_path / "empty.jsonl", ())
    assert sorted(os.listdir(tmp_path)) == [MANIFEST_FILENAME]

    write_manifest(path, build_manifest_entries(_inputs("g_1.h5")), overwrite=True)
    assert [entry.input_id for entry in read_manifest(path)] == ["g_1"]


def test_reading_a_corrupt_manifest_names_the_entry(tmp_path):
    path = tmp_path / MANIFEST_FILENAME
    good = ManifestEntry(0, "a", "/data/a.h5", 0, 1, None).to_json()
    path.write_text(good + "\n" + '{"index": 5, "input_id": "b", "source": "/b", "template_index": 0}\n')
    with pytest.raises(ManifestError, match="entry 1 carries index 5"):
        list(read_manifest(path))
    path.write_text(good + "\nnot json\n")
    with pytest.raises(ManifestError, match="entry 1 is not JSON"):
        list(read_manifest(path))
    path.write_text(good + "\n\n")
    with pytest.raises(ManifestError, match="blank line"):
        list(read_manifest(path))


def test_request_document_carries_format_and_version(tmp_path):
    path = tmp_path / "request.json"
    digest = write_request(path, {"kind": "test", "request": {"when": "now"}})

    document = read_request(path)
    assert document["format"] == REQUEST_FORMAT
    assert document["version"] == 1
    assert document["kind"] == "test"
    assert len(digest) == 64
    with pytest.raises(FileExistsError):
        write_request(path, {"kind": "again"})

    path.write_text(json.dumps({"format": "other"}))
    with pytest.raises(ManifestError, match="is not a"):
        read_request(path)


def test_reserved_names_cover_every_support_file():
    assert RESERVED_RUN_FILENAMES >= {"inputs.jsonl", "request.json", "failures.jsonl", "run.json", "output.h5"}


class _InputError(ValueError):
    pass


class _NumericalIndexingError(RuntimeError):
    pass


InputError = type("InputError", (_InputError,), {})
NumericalIndexingError = type("NumericalIndexingError", (_NumericalIndexingError,), {})


@pytest.mark.parametrize(
    ("error", "category"),
    [
        (InputError("bad frame"), CATEGORY_INPUT),
        (NumericalIndexingError("pixel-to-q failed"), CATEGORY_NUMERICAL),
        (MemoryError(), CATEGORY_MEMORY),
        (FileNotFoundError("gone"), CATEGORY_INPUT),
        (KeyError("entry1/data"), CATEGORY_INPUT),
        (RuntimeError("worker died"), CATEGORY_ERROR),
    ],
)
def test_error_classification_uses_class_names(error, category):
    assert classify_error(error) == category


def test_failure_report_is_created_only_when_something_is_recorded(tmp_path):
    path = tmp_path / FAILURE_REPORT_FILENAME
    with FailureReportWriter(path) as writer:
        pass
    assert writer.close() is None
    assert os.listdir(tmp_path) == []

    entry = ManifestEntry(3, "f_4", "/data/f_4.h5", 0, 4, None)
    writer = FailureReportWriter(path)
    writer.append(FailureRecord.from_error(entry, FileNotFoundError("no such file"), context={"attempt": 1}))
    writer.append(FailureRecord.not_run(entry, category=CATEGORY_CANCELLED, message="cancelled by user"))
    assert writer.count == 2
    assert path.exists() is False  # published on close only
    assert writer.close() == os.fspath(path)
    assert sorted(os.listdir(tmp_path)) == [FAILURE_REPORT_FILENAME]

    records, has_more = read_failure_report(path)
    assert has_more is False
    assert [(r.index, r.input_id, r.category, r.error_type, r.message) for r in records] == [
        (3, "f_4", CATEGORY_INPUT, "FileNotFoundError", "no such file"),
        (3, "f_4", CATEGORY_CANCELLED, None, "cancelled by user"),
    ]
    assert records[0].context == {"attempt": 1}
    assert records[0].recorded_at is not None
    assert count_failure_records(path) == 2

    with pytest.raises(FileExistsError):
        FailureReportWriter(path)
    with pytest.raises(RuntimeError, match="closed"):
        writer.append(records[0])


def test_failure_report_pages_are_bounded(tmp_path):
    path = tmp_path / FAILURE_REPORT_FILENAME
    with FailureReportWriter(path) as writer:
        for index in range(250):
            entry = ManifestEntry(index, f"f_{index}", f"/data/f_{index}.h5", 0, index, None)
            writer.append(FailureRecord.not_run(entry))

    first, more = read_failure_report(path, offset=0, limit=100)
    last, no_more = read_failure_report(path, offset=200, limit=100)
    assert (len(first), more) == (100, True)
    assert [record.index for record in first[:3]] == [0, 1, 2]
    assert (len(last), no_more) == (50, False)
    assert last[-1].index == 249
    with pytest.raises(ValueError):
        read_failure_report(path, offset=-1)


def test_failure_report_keeps_its_partial_when_the_run_raises(tmp_path):
    path = tmp_path / FAILURE_REPORT_FILENAME
    entry = ManifestEntry(0, "f_0", "/data/f_0.h5", 0, 0, None)
    with pytest.raises(RuntimeError, match="boom"):
        with FailureReportWriter(path) as writer:
            writer.append(FailureRecord.not_run(entry))
            raise RuntimeError("boom")
    assert sorted(os.listdir(tmp_path)) == [FAILURE_REPORT_FILENAME + publication.PARTIAL_SUFFIX]
    assert not path.exists()


def test_publish_file_links_atomically_and_refuses_to_clobber(tmp_path):
    final = tmp_path / "file.txt"
    partial = publication.partial_path(final)
    assert partial.name == "file.txt.partial"
    partial.write_text("one")

    assert publication.publish_file(partial, final) == final
    assert final.read_text() == "one"
    assert not partial.exists()

    partial.write_text("two")
    with pytest.raises(FileExistsError):
        publication.publish_file(partial, final)
    assert final.read_text() == "one"
    assert partial.read_text() == "two"

    publication.publish_file(partial, final, overwrite=True)
    assert final.read_text() == "two"

    with pytest.raises(FileNotFoundError):
        publication.publish_file(partial, final)
    with pytest.raises(ValueError, match="same directory"):
        publication.publish_file(tmp_path / "a" / "x.partial", tmp_path / "x")
    publication.discard_partial(final)  # absent partial is fine


def test_publish_file_falls_back_to_rename_when_links_are_unsupported(tmp_path, monkeypatch):
    import errno

    final = tmp_path / "file.txt"
    partial = publication.partial_path(final)
    partial.write_text("payload")

    def unsupported_link(source, target):
        raise OSError(errno.EPERM, "Operation not permitted")

    monkeypatch.setattr(publication.os, "link", unsupported_link)
    publication.publish_file(partial, final)
    assert final.read_text() == "payload"
    assert not partial.exists()

    partial.write_text("again")
    with pytest.raises(FileExistsError):
        publication.publish_file(partial, final)
    assert final.read_text() == "payload"


def test_published_files_are_regular_files(tmp_path):
    path = tmp_path / MANIFEST_FILENAME
    write_manifest(path, build_manifest_entries(_inputs("f_1.h5")))
    assert stat.S_ISREG(path.stat().st_mode)
    assert path.stat().st_nlink == 1
