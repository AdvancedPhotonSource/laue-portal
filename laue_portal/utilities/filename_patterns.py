"""
Filename pattern extraction and wildcard generation utilities.

This module provides pure functions (no Dash dependencies) for scanning
directories, extracting filename patterns by replacing numeric indices with
%d placeholders, and generating wildcard patterns for groups of similar
filenames.

Used by the "Find file names" feature on the create_peakindexing and
create_wire_reconstruction pages.
"""

import logging
import os
import re
from itertools import combinations

from laue_portal.utilities.srange import srange

logger = logging.getLogger(__name__)


def filter_files_by_extension(directory_path, valid_extensions):
    """
    List files in a directory, keeping only those with a valid extension.

    Parameters:
        directory_path: Full path to the directory to scan.
        valid_extensions: List of extensions to keep (e.g. ['.h5', '.hdf5']).
            If empty or falsy, all files are returned unfiltered.

    Returns:
        List of matching filenames (basename only, not full paths).
    """
    all_files = [f for f in os.listdir(directory_path) if os.path.isfile(os.path.join(directory_path, f))]

    if valid_extensions:
        return [f for f in all_files if any(f.lower().endswith(ext.lower()) for ext in valid_extensions)]
    return all_files


def extract_index_patterns(files, num_indices):
    """
    Group filenames by pattern, replacing rightmost numeric indices with %d.

    For each filename the function tries to match *num_indices* underscore-
    separated trailing numbers first, then falls back to fewer indices down
    to 1.  Files with no trailing numbers are kept as-is.

    Parameters:
        files: List of filenames to process.
        num_indices: Maximum number of rightmost numeric indices to capture.

    Returns:
        Dict mapping pattern strings to lists of index lists, e.g.::

            {
                "Si_wire_%d.h5": [[7], [8], [9]],
                "Si_wire_%d_%d.h5": [[7, 5], [8, 5]],
            }
    """
    pattern_files = {}

    for filename in files:
        base_name, extension = os.path.splitext(filename)

        matched = False
        for n in range(num_indices, 0, -1):
            if n == 1:
                regex_pattern = r"(\d+)(?!.*\d)"
            else:
                regex_pattern = r"_".join([r"(\d+)"] * n) + r"(?!.*\d)"

            match = re.search(regex_pattern, base_name)
            if match:
                indices = [int(match.group(i)) for i in range(1, n + 1)]

                placeholder = "_".join(["%d"] * n)
                pattern = base_name[: match.start()] + placeholder + base_name[match.end() :] + extension

                pattern_files.setdefault(pattern, []).append(indices)
                matched = True
                break

        if not matched:
            pattern_files.setdefault(filename, []).append([])

    return pattern_files


# ---------------------------------------------------------------------------
# Segment-level wildcard generation
# ---------------------------------------------------------------------------

_PLACEHOLDER_TOKEN = "\x00"  # sentinel used during segment splitting


def _split_pattern_segments(pattern):
    """
    Split a filename pattern into semantic segments on underscores, keeping
    ``%d`` tokens atomic (they are never split across segments).

    The file extension is separated first and re-attached to the last segment
    so that it is always preserved verbatim.

    Returns:
        List of segment strings.

    Examples::

        >>> _split_pattern_segments('Si_PE2_%d.h5')
        ['Si', 'PE2', '%d.h5']
        >>> _split_pattern_segments('Si_%d_%d.h5')
        ['Si', '%d', '%d.h5']
        >>> _split_pattern_segments('file.h5')
        ['file.h5']
    """
    base, ext = os.path.splitext(pattern)

    # Temporarily replace %d so underscores inside it aren't split
    protected = base.replace("%d", _PLACEHOLDER_TOKEN)
    parts = protected.split("_")
    parts = [p.replace(_PLACEHOLDER_TOKEN, "%d") for p in parts]

    if parts:
        parts[-1] = parts[-1] + ext

    return parts


def generate_wildcard_patterns(pattern_dict):
    """
    Merge similar patterns into wildcard patterns using segment-level diffing.

    Two patterns are considered mergeable when:
    - They have the same number of segments (split on ``_``).
    - Fewer than half the segments differ.
    - All ``%d`` placeholders are in the same positions.

    Differing segments are replaced with ``*``.

    Parameters:
        pattern_dict: Dict mapping pattern strings to lists of index lists
            (as returned by :func:`extract_index_patterns`).

    Returns:
        List of ``(wildcard_pattern, combined_indices_list, num_asterisks)``
        tuples, sorted by ascending asterisk count then descending file count.
        Indices are deduplicated.
    """
    patterns = list(pattern_dict.keys())
    if len(patterns) < 2:
        return []

    # Pre-compute segments for every pattern
    segments_map = {p: _split_pattern_segments(p) for p in patterns}

    wildcard_accum = {}  # wildcard_str -> set of index tuples

    for p1, p2 in combinations(patterns, 2):
        segs1 = segments_map[p1]
        segs2 = segments_map[p2]

        if len(segs1) != len(segs2):
            continue

        # Build merged segments, tracking diffs
        merged = []
        diff_count = 0
        valid = True
        for s1, s2 in zip(segs1, segs2, strict=False):
            if s1 == s2:
                merged.append(s1)
            else:
                # Don't merge if a %d placeholder is in one but not the other
                if ("%d" in s1) != ("%d" in s2):
                    valid = False
                    break
                merged.append("*")
                diff_count += 1

        if not valid or diff_count == 0:
            continue

        # Skip if too many segments differ (more than half)
        if diff_count > len(segs1) / 2:
            continue

        wildcard = "_".join(merged)

        if wildcard not in wildcard_accum:
            wildcard_accum[wildcard] = set()
        for idx in pattern_dict[p1]:
            wildcard_accum[wildcard].add(tuple(idx))
        for idx in pattern_dict[p2]:
            wildcard_accum[wildcard].add(tuple(idx))

    results = []
    for wc, idx_set in wildcard_accum.items():
        num_asterisks = wc.count("*")
        indices_list = [list(t) for t in sorted(idx_set)]
        results.append((wc, indices_list, num_asterisks))

    # Sort: fewer asterisks first, then more files first
    results.sort(key=lambda x: (x[2], -len(x[1])))
    return results


# ---------------------------------------------------------------------------
# Label generation
# ---------------------------------------------------------------------------


def build_pattern_label(pattern, indices_list):
    """
    Generate a human-readable label for a pattern showing file count / ranges.

    Parameters:
        pattern: Filename pattern string (e.g. ``'file_%d.h5'``).
        indices_list: List of index lists for this pattern.

    Returns:
        Label string, e.g. ``'file_%d.h5 (files 1-10)'``.
    """
    if not indices_list or not indices_list[0]:
        return pattern

    num_dims = len(indices_list[0])

    if num_dims == 1:
        vals = set(idx[0] for idx in indices_list)
        return f"{pattern} (files {srange(vals)})"

    dim_names = ["scanPoints", "depths"] if num_dims == 2 else [f"dim{i + 1}" for i in range(num_dims)]
    range_labels = []
    for dim in range(num_dims):
        dim_values = sorted(set(idx[dim] for idx in indices_list if len(idx) > dim))
        if dim_values:
            range_labels.append(f"{dim_names[dim]}: {srange(dim_values)}")

    if range_labels:
        return f"{pattern} ({', '.join(range_labels)})"

    count = len(indices_list)
    return f"{pattern} ({count} file{'s' if count != 1 else ''})"


# ---------------------------------------------------------------------------
# High-level orchestrator
# ---------------------------------------------------------------------------


def scan_directory_patterns(directory, valid_extensions, num_indices, max_results=10):
    """
    Scan a directory and return the top filename patterns with wildcards.

    This is the main entry point used by Dash callbacks.  It combines
    :func:`filter_files_by_extension`, :func:`extract_index_patterns`, and
    :func:`generate_wildcard_patterns` into a single call.

    Parameters:
        directory: Full path to the directory to scan.
        valid_extensions: Extension whitelist (e.g. ``['.h5']``).
        num_indices: Max number of trailing numeric indices to capture.
        max_results: Maximum number of patterns to return.

    Returns:
        List of ``(pattern, indices_list)`` tuples, wildcards first, then
        exact patterns, truncated to *max_results*.  Returns an empty list
        if the directory doesn't exist or can't be read.
    """
    if not os.path.isdir(directory):
        logger.warning(f"Directory does not exist: {directory}")
        return []

    try:
        files = filter_files_by_extension(directory, valid_extensions)
    except Exception as e:
        logger.error(f"Error reading directory {directory}: {e}")
        return []

    if not files:
        return []

    pattern_dict = extract_index_patterns(files, num_indices)

    sorted_patterns = sorted(pattern_dict.items(), key=lambda x: len(x[1]), reverse=True)[:max_results]

    top_pattern_dict = dict(sorted_patterns)
    wildcards = generate_wildcard_patterns(top_pattern_dict)

    result = []
    for wc, indices_list, _num_asterisks in wildcards:
        result.append((wc, indices_list))
    for pattern, indices_list in sorted_patterns:
        result.append((pattern, indices_list))

    return result[:max_results]
