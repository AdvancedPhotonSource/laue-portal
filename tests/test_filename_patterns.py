"""
Tests for laue_portal.utilities.filename_patterns module.

Tests the pure filename-pattern logic independently of Dash.
"""

import os
import tempfile

import pytest

from laue_portal.utilities.filename_patterns import (
    filter_files_by_extension,
    extract_index_patterns,
    generate_wildcard_patterns,
    build_pattern_label,
    scan_directory_patterns,
    _split_pattern_segments,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_temp_dir(filenames):
    """Create a temp directory populated with empty files and return the path."""
    tmpdir = tempfile.mkdtemp()
    for name in filenames:
        open(os.path.join(tmpdir, name), "w").close()
    return tmpdir


# ---------------------------------------------------------------------------
# filter_files_by_extension
# ---------------------------------------------------------------------------

class TestFilterFilesByExtension:

    def test_filters_by_extension(self):
        tmpdir = _make_temp_dir(["a.h5", "b.hdf5", "c.txt", "d.log"])
        result = filter_files_by_extension(tmpdir, [".h5", ".hdf5"])
        assert sorted(result) == ["a.h5", "b.hdf5"]

    def test_case_insensitive(self):
        tmpdir = _make_temp_dir(["A.H5", "b.HDF5"])
        result = filter_files_by_extension(tmpdir, [".h5", ".hdf5"])
        assert sorted(result) == ["A.H5", "b.HDF5"]

    def test_empty_extensions_returns_all(self):
        tmpdir = _make_temp_dir(["a.h5", "b.txt"])
        result = filter_files_by_extension(tmpdir, [])
        assert sorted(result) == ["a.h5", "b.txt"]

    def test_none_extensions_returns_all(self):
        tmpdir = _make_temp_dir(["a.h5", "b.txt"])
        result = filter_files_by_extension(tmpdir, None)
        assert sorted(result) == ["a.h5", "b.txt"]

    def test_no_matching_files(self):
        tmpdir = _make_temp_dir(["a.txt", "b.csv"])
        result = filter_files_by_extension(tmpdir, [".h5"])
        assert result == []

    def test_empty_directory(self):
        tmpdir = _make_temp_dir([])
        result = filter_files_by_extension(tmpdir, [".h5"])
        assert result == []

    def test_skips_subdirectories(self):
        tmpdir = _make_temp_dir(["a.h5"])
        os.mkdir(os.path.join(tmpdir, "subdir.h5"))
        result = filter_files_by_extension(tmpdir, [".h5"])
        assert result == ["a.h5"]


# ---------------------------------------------------------------------------
# extract_index_patterns
# ---------------------------------------------------------------------------

class TestExtractIndexPatterns:

    def test_single_index(self):
        files = ["Si_001.h5", "Si_002.h5", "Si_003.h5"]
        result = extract_index_patterns(files, num_indices=1)
        assert "Si_%d.h5" in result
        assert sorted(result["Si_%d.h5"]) == [[1], [2], [3]]

    def test_two_indices(self):
        files = ["Si_7_5.h5", "Si_8_5.h5"]
        result = extract_index_patterns(files, num_indices=2)
        assert "Si_%d_%d.h5" in result
        assert sorted(result["Si_%d_%d.h5"]) == [[7, 5], [8, 5]]

    def test_adaptive_fallback(self):
        """With num_indices=2, files with only one numeric part should still match."""
        files = ["Si_001.h5", "Si_002.h5"]
        result = extract_index_patterns(files, num_indices=2)
        # Should fall back to 1-index pattern since there's only one number
        assert "Si_%d.h5" in result

    def test_mixed_index_counts(self):
        """Files with different numbers of indices produce separate patterns."""
        files = ["Si_7.h5", "Si_7_5.h5", "Si_8_5.h5"]
        result = extract_index_patterns(files, num_indices=2)
        assert "Si_%d.h5" in result
        assert "Si_%d_%d.h5" in result

    def test_no_numeric_part(self):
        files = ["readme.h5"]
        result = extract_index_patterns(files, num_indices=1)
        assert "readme.h5" in result
        assert result["readme.h5"] == [[]]

    def test_preserves_prefix_text(self):
        files = ["long_prefix_name_42.h5"]
        result = extract_index_patterns(files, num_indices=1)
        assert "long_prefix_name_%d.h5" in result

    def test_multiple_numbers_captures_rightmost(self):
        """With num_indices=1, only the rightmost number is captured."""
        files = ["run3_scan_42.h5"]
        result = extract_index_patterns(files, num_indices=1)
        assert "run3_scan_%d.h5" in result
        assert result["run3_scan_%d.h5"] == [[42]]


# ---------------------------------------------------------------------------
# _split_pattern_segments
# ---------------------------------------------------------------------------

class TestSplitPatternSegments:

    def test_basic_split(self):
        assert _split_pattern_segments("Si_PE2_%d.h5") == ["Si", "PE2", "%d.h5"]

    def test_two_placeholders(self):
        assert _split_pattern_segments("Si_%d_%d.h5") == ["Si", "%d", "%d.h5"]

    def test_no_underscores(self):
        assert _split_pattern_segments("file.h5") == ["file.h5"]

    def test_placeholder_preserved(self):
        """Ensure %d is not split even though it contains no underscore."""
        segments = _split_pattern_segments("a_%d_b.h5")
        assert "%d" in segments

    def test_extension_on_last_segment(self):
        segments = _split_pattern_segments("Si_PE2_%d.hdf5")
        assert segments[-1].endswith(".hdf5")


# ---------------------------------------------------------------------------
# generate_wildcard_patterns
# ---------------------------------------------------------------------------

class TestGenerateWildcardPatterns:

    def test_same_structure_different_name(self):
        """Two patterns differing by one segment should produce a wildcard."""
        pattern_dict = {
            "Si_PE2_%d.h5": [[1], [2], [3]],
            "Si_Eiger1_%d.h5": [[1], [2]],
        }
        result = generate_wildcard_patterns(pattern_dict)
        wildcards = [wc for wc, _, _ in result]
        assert "Si_*_%d.h5" in wildcards

    def test_indices_are_deduplicated(self):
        """Combined indices from merged patterns should not have duplicates."""
        pattern_dict = {
            "Si_PE2_%d.h5": [[1], [2], [3]],
            "Si_Eiger1_%d.h5": [[1], [2]],
        }
        result = generate_wildcard_patterns(pattern_dict)
        for _wc, indices, _n in result:
            # Convert to set of tuples to check uniqueness
            assert len(indices) == len(set(tuple(i) for i in indices))

    def test_different_segment_counts_no_merge(self):
        """Patterns with different segment counts should not be merged."""
        pattern_dict = {
            "Si_PE2_%d.h5": [[1]],
            "Si_PE2_extra_%d.h5": [[1]],
        }
        result = generate_wildcard_patterns(pattern_dict)
        assert result == []

    def test_placeholder_position_mismatch_no_merge(self):
        """Patterns where %d is in different positions should not be merged."""
        pattern_dict = {
            "Si_%d_data.h5": [[1]],
            "Si_data_%d.h5": [[1]],
        }
        result = generate_wildcard_patterns(pattern_dict)
        # The segments differ in positions where one has %d and the other doesn't
        assert result == []

    def test_too_many_differences_no_merge(self):
        """Patterns where more than half segments differ should not be merged."""
        pattern_dict = {
            "A_B_%d.h5": [[1]],
            "X_Y_%d.h5": [[1]],
        }
        result = generate_wildcard_patterns(pattern_dict)
        # 2 out of 3 segments differ -- exceeds half, should not merge
        assert result == []

    def test_single_pattern_returns_empty(self):
        pattern_dict = {"Si_%d.h5": [[1], [2]]}
        result = generate_wildcard_patterns(pattern_dict)
        assert result == []

    def test_sorted_by_asterisks_then_file_count(self):
        pattern_dict = {
            "A_PE2_%d.h5": [[1], [2], [3]],
            "A_Eig_%d.h5": [[4], [5]],
            "A_Foo_%d.h5": [[6]],
        }
        result = generate_wildcard_patterns(pattern_dict)
        if len(result) > 1:
            # Fewer asterisks should come first
            assert result[0][2] <= result[1][2]

    def test_three_patterns_same_wildcard(self):
        """Three patterns that all differ in the same segment."""
        pattern_dict = {
            "Si_PE2_%d.h5": [[1], [2]],
            "Si_Eig_%d.h5": [[3], [4]],
            "Si_Foo_%d.h5": [[5]],
        }
        result = generate_wildcard_patterns(pattern_dict)
        wildcards = [wc for wc, _, _ in result]
        assert "Si_*_%d.h5" in wildcards
        # Find the wildcard entry and check all indices are present
        for wc, indices, _ in result:
            if wc == "Si_*_%d.h5":
                idx_values = set(tuple(i) for i in indices)
                assert idx_values == {(1,), (2,), (3,), (4,), (5,)}


# ---------------------------------------------------------------------------
# build_pattern_label
# ---------------------------------------------------------------------------

class TestBuildPatternLabel:

    def test_single_index_label(self):
        label = build_pattern_label("Si_%d.h5", [[1], [2], [3]])
        assert "Si_%d.h5" in label
        assert "files" in label

    def test_two_index_label(self):
        label = build_pattern_label("Si_%d_%d.h5", [[1, 5], [2, 5], [3, 10]])
        assert "scanPoints" in label
        assert "depths" in label

    def test_no_indices_returns_pattern(self):
        label = build_pattern_label("readme.h5", [[]])
        assert label == "readme.h5"

    def test_empty_list_returns_pattern(self):
        label = build_pattern_label("readme.h5", [])
        assert label == "readme.h5"


# ---------------------------------------------------------------------------
# scan_directory_patterns (integration)
# ---------------------------------------------------------------------------

class TestScanDirectoryPatterns:

    def test_basic_scan(self):
        files = [f"Si_PE2_{i}.h5" for i in range(1, 11)]
        tmpdir = _make_temp_dir(files)
        result = scan_directory_patterns(tmpdir, [".h5"], num_indices=1)
        assert len(result) >= 1
        patterns = [p for p, _ in result]
        assert "Si_PE2_%d.h5" in patterns

    def test_with_wildcards(self):
        files = (
            [f"Si_PE2_{i}.h5" for i in range(1, 6)]
            + [f"Si_Eiger1_{i}.h5" for i in range(1, 4)]
        )
        tmpdir = _make_temp_dir(files)
        result = scan_directory_patterns(tmpdir, [".h5"], num_indices=1)
        patterns = [p for p, _ in result]
        # Should include a wildcard pattern
        assert any("*" in p for p in patterns)
        # Should also include the exact patterns
        assert "Si_PE2_%d.h5" in patterns
        assert "Si_Eiger1_%d.h5" in patterns

    def test_nonexistent_directory(self):
        result = scan_directory_patterns("/nonexistent/path", [".h5"], num_indices=1)
        assert result == []

    def test_max_results(self):
        # Create many distinct patterns
        files = [f"pattern{i}_{j}.h5" for i in range(20) for j in range(3)]
        tmpdir = _make_temp_dir(files)
        result = scan_directory_patterns(tmpdir, [".h5"], num_indices=1, max_results=5)
        assert len(result) <= 5

    def test_extension_filtering(self):
        files = ["data_1.h5", "data_2.h5", "notes.txt", "log.csv"]
        tmpdir = _make_temp_dir(files)
        result = scan_directory_patterns(tmpdir, [".h5"], num_indices=1)
        patterns = [p for p, _ in result]
        # Should only contain h5 patterns
        assert all(".h5" in p or "*" in p for p in patterns)

    def test_two_index_scan(self):
        files = [f"Si_{i}_{j}.h5" for i in range(1, 4) for j in range(1, 3)]
        tmpdir = _make_temp_dir(files)
        result = scan_directory_patterns(tmpdir, [".h5"], num_indices=2)
        patterns = [p for p, _ in result]
        assert "Si_%d_%d.h5" in patterns

    def test_empty_directory(self):
        tmpdir = _make_temp_dir([])
        result = scan_directory_patterns(tmpdir, [".h5"], num_indices=1)
        assert result == []

    def test_no_matching_extensions(self):
        tmpdir = _make_temp_dir(["a.txt", "b.csv"])
        result = scan_directory_patterns(tmpdir, [".h5"], num_indices=1)
        assert result == []
