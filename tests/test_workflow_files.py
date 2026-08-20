"""Tests for linear-time workflow input resolution."""

import os

import pytest

from laue_portal.utilities.filename_patterns import FilenameTemplateMatch
from laue_portal.workflows import files


def test_wire_resolution_lists_once_and_orders_by_requested_scan_points(tmp_path, monkeypatch):
    for filename in ("wire_1.h5", "wire_2.h5", "ignore.txt"):
        (tmp_path / filename).write_text("")

    real_listdir = os.listdir
    calls = []

    def tracked_listdir(directory):
        calls.append(directory)
        return real_listdir(directory)

    monkeypatch.setattr(files.os, "listdir", tracked_listdir)
    resolved = files.resolve_input_files(
        tmp_path,
        ["wire_%d"],
        [2, 1],
        append_suffix_wildcard=True,
    )

    assert calls == [os.fspath(tmp_path)]
    assert resolved == (
        os.path.join(tmp_path, "wire_2.h5"),
        os.path.join(tmp_path, "wire_1.h5"),
    )


def test_indexing_resolution_supports_wildcards_and_two_indices(tmp_path):
    for filename in (
        "sample_A_1_0.h5",
        "sample_B_1_0.h5",
        "sample_A_1_1.h5",
        "sample_A_2_0.h5",
        "sample_A_2_1.h5",
    ):
        (tmp_path / filename).write_text("")

    resolved = files.resolve_input_files(
        tmp_path,
        ["sample_*_%d_%d.h5"],
        [2, 1],
        depth_points=[1, 0],
    )

    assert tuple(os.path.basename(path) for path in resolved) == (
        "sample_A_2_1.h5",
        "sample_A_2_0.h5",
        "sample_A_1_1.h5",
        "sample_A_1_0.h5",
        "sample_B_1_0.h5",
    )


def test_resolution_fails_when_a_requested_index_has_no_file(tmp_path):
    (tmp_path / "wire_1.h5").write_text("")

    with pytest.raises(files.FileResolutionError, match="for 2"):
        files.resolve_input_files(tmp_path, ["wire_%d.h5"], [1, 2])


def test_resolution_combines_multiple_filename_templates(tmp_path):
    for filename in ("left_1.h5", "right_1.h5"):
        (tmp_path / filename).write_text("")

    resolved = files.resolve_input_files(
        tmp_path,
        ["left_%d.h5", "right_%d.h5"],
        [1],
    )

    assert tuple(os.path.basename(path) for path in resolved) == ("left_1.h5", "right_1.h5")


def test_resolution_performs_one_match_per_directory_entry(monkeypatch):
    entry_count = 100_000
    filenames = [f"image_{index}.h5" for index in range(entry_count)]
    match_calls = 0
    list_calls = 0

    class CountingMatcher:
        def match(self, filename):
            nonlocal match_calls
            match_calls += 1
            index = int(filename.removeprefix("image_").removesuffix(".h5"))
            return FilenameTemplateMatch(0, (index,))

    def listdir(directory):
        nonlocal list_calls
        list_calls += 1
        return filenames

    monkeypatch.setattr(files, "compile_filename_templates", lambda *args, **kwargs: CountingMatcher())
    monkeypatch.setattr(files.os, "listdir", listdir)

    resolved = files.resolve_input_files("/network/scan", ["image_%d.h5"], range(entry_count))

    assert list_calls == 1
    assert match_calls == entry_count
    assert len(resolved) == entry_count


def test_resolution_reports_matching_progress(monkeypatch):
    monkeypatch.setattr(files.os, "listdir", lambda directory: ["image_1.h5", "image_2.h5"])
    updates = []

    files.resolve_input_files(
        "/network/scan",
        ["image_%d.h5"],
        [1, 2],
        progress_callback=lambda scanned, total: updates.append((scanned, total)),
        progress_interval=1,
    )

    assert updates == [(0, 2), (1, 2), (2, 2)]
