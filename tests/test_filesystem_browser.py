from pathlib import Path

import pytest

from laue_portal.services.filesystem_browser import (
    list_directory,
    normalize_path,
    read_selected_file,
    validate_selection,
)


def test_list_directory_filters_files_and_sorts_directories_first(tmp_path):
    folder = tmp_path / "archive"
    folder.mkdir()
    (tmp_path / "scan_b.xml").write_text("b")
    (tmp_path / "scan_a.XML").write_text("a")
    (tmp_path / "notes.txt").write_text("ignored")

    current_path, entries, truncated = list_directory(tmp_path, extensions=[".xml"])

    assert current_path == str(tmp_path.resolve())
    assert [entry["name"] for entry in entries] == ["archive", "scan_a.XML", "scan_b.xml"]
    assert [entry["type"] for entry in entries] == ["Directory", "File", "File"]
    assert truncated is False


def test_list_directory_reports_listing_limit(tmp_path):
    for index in range(3):
        (tmp_path / f"scan_{index}.xml").write_text("scan")

    _, entries, truncated = list_directory(tmp_path, extensions=[".xml"], limit=2)

    assert len(entries) == 2
    assert truncated is True


def test_validate_selection_supports_file_and_directory_modes(tmp_path):
    scan_log = tmp_path / "scan.xml"
    scan_log.write_bytes(b"<scanLog />")

    assert validate_selection(tmp_path, mode="directory") == str(tmp_path.resolve())
    assert validate_selection(scan_log, extensions=[".xml"]) == str(scan_log.resolve())


def test_validate_selection_rejects_wrong_extension_and_large_file(tmp_path):
    text_file = tmp_path / "scan.txt"
    text_file.write_text("not xml")
    large_file = tmp_path / "large.xml"
    large_file.write_bytes(b"x" * 1050)

    with pytest.raises(ValueError, match="extensions"):
        validate_selection(text_file, extensions=[".xml"])
    with pytest.raises(ValueError, match="exceeds"):
        validate_selection(large_file, extensions=[".xml"], max_file_size_mb=0.001)


def test_read_selected_file_revalidates_and_reads_bytes(tmp_path):
    scan_log = tmp_path / "scan.xml"
    scan_log.write_bytes(b"<scanLog />")

    assert read_selected_file(scan_log, extensions=[".xml"], max_file_size_mb=1) == b"<scanLog />"

    scan_log.unlink()
    with pytest.raises(ValueError, match="regular file"):
        read_selected_file(scan_log, extensions=[".xml"], max_file_size_mb=1)


def test_normalize_path_expands_user_path(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))

    assert normalize_path("~/logs") == Path(tmp_path / "logs").resolve()


def test_empty_and_non_directory_paths_are_rejected(tmp_path):
    regular_file = tmp_path / "scan.xml"
    regular_file.write_text("scan")

    with pytest.raises(ValueError, match="Enter a path"):
        normalize_path(" ")
    with pytest.raises(ValueError, match="not an accessible directory"):
        list_directory(regular_file)
