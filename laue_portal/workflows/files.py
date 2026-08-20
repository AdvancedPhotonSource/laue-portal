"""Shared filename resolution for reconstruction and indexing workflows."""

import os
from collections import defaultdict
from collections.abc import Callable, Sequence
from itertools import product

from laue_portal.utilities.filename_patterns import compile_filename_templates
from laue_portal.utilities.srange import srange

ProgressCallback = Callable[[int, int], None]


class WorkflowValidationError(ValueError):
    """Raised when a normalized workflow request is internally inconsistent."""


class FileResolutionError(WorkflowValidationError):
    """Raised when a submission's input files cannot be resolved."""


def normalize_filename_templates(templates: Sequence[str]) -> tuple[str, ...]:
    normalized = tuple(str(template).strip() for template in templates if str(template).strip())
    if not normalized:
        raise WorkflowValidationError("At least one filename template is required")
    return normalized


def normalize_integer_range(value: str, field_name: str) -> tuple[str, tuple[int, ...]]:
    try:
        parsed = srange(str(value or ""))
        values = tuple(parsed.list())
    except (TypeError, ValueError) as error:
        raise WorkflowValidationError(f"Invalid {field_name}: {value!r}") from error
    if not values:
        raise WorkflowValidationError(f"{field_name} must contain at least one value")
    return str(parsed), values


def normalize_optional_integer_range(value: str | None, field_name: str) -> tuple[str | None, tuple[int, ...] | None]:
    if value is None or not str(value).strip():
        return None, None
    normalized, values = normalize_integer_range(str(value), field_name)
    return normalized, values


def normalize_input_directory(path: str | os.PathLike[str]) -> str:
    normalized = os.path.normpath(os.fspath(path))
    if not normalized or normalized == ".":
        raise WorkflowValidationError("Input path is required")
    return normalized


def normalize_output_path_template(path_template: str | os.PathLike[str]) -> str:
    normalized = os.path.normpath(os.fspath(path_template))
    if normalized.count("%d") != 1:
        raise WorkflowValidationError("Output path template must contain exactly one %d run-ID placeholder")
    return normalized


def format_output_path(path_template: str, run_id: int) -> str:
    """Format a validated run output path after SQLite assigns the run ID."""

    try:
        return path_template % run_id
    except (TypeError, ValueError) as error:
        raise WorkflowValidationError(f"Could not format output path template {path_template!r}") from error


def _expected_index_keys(
    template: str,
    scan_points: Sequence[int],
    depth_points: Sequence[int] | None,
) -> tuple[tuple[int, ...], ...]:
    placeholder_count = template.count("%d")
    if placeholder_count == 0:
        return ((),)
    if placeholder_count == 1:
        if depth_points is not None:
            raise FileResolutionError(
                f"Filename template {template!r} has one %d placeholder but both scan and depth ranges were provided"
            )
        return tuple((scan_point,) for scan_point in scan_points)
    if placeholder_count == 2:
        if depth_points is None:
            raise FileResolutionError(f"Filename template {template!r} has two %d placeholders but no depth range")
        return tuple(product(scan_points, depth_points))
    raise FileResolutionError(
        f"Filename template {template!r} has {placeholder_count} %d placeholders; at most two are supported"
    )


def resolve_input_files(
    directory: str | os.PathLike[str],
    templates: Sequence[str],
    scan_points: Sequence[int],
    *,
    depth_points: Sequence[int] | None = None,
    append_suffix_wildcard: bool = False,
    progress_callback: ProgressCallback | None = None,
    progress_interval: int = 10_000,
) -> tuple[str, ...]:
    """Resolve requested files with one directory listing and one regex pass.

    Matches are bucketed by captured ``%d`` indices, then emitted in template
    and requested-index order. Files within a bucket retain directory-listing
    order, avoiding a sort that would make the operation super-linear.
    """

    if progress_interval <= 0:
        raise WorkflowValidationError("Progress interval must be greater than zero")
    input_directory = normalize_input_directory(directory)
    normalized_templates = normalize_filename_templates(templates)
    expected_keys = tuple(
        _expected_index_keys(template, scan_points, depth_points) for template in normalized_templates
    )
    matcher = compile_filename_templates(normalized_templates, append_suffix_wildcard=append_suffix_wildcard)

    try:
        filenames = os.listdir(input_directory)
    except OSError as error:
        raise FileResolutionError(f"Could not list input directory {input_directory!r}: {error}") from error

    total = len(filenames)
    if progress_callback is not None:
        progress_callback(0, total)

    buckets: tuple[defaultdict[tuple[int, ...], list[str]], ...] = tuple(
        defaultdict(list) for _ in normalized_templates
    )
    for scanned, filename in enumerate(filenames, start=1):
        match = matcher.match(filename)
        if match is not None:
            buckets[match.template_index][match.indices].append(filename)
        if progress_callback is not None and scanned % progress_interval == 0:
            progress_callback(scanned, total)
    if progress_callback is not None and (total == 0 or total % progress_interval):
        progress_callback(total, total)

    resolved = []
    seen_paths = set()
    for template_index, template in enumerate(normalized_templates):
        for index_key in expected_keys[template_index]:
            matches = buckets[template_index].get(index_key, ())
            if not matches:
                index_description = ", ".join(str(value) for value in index_key) or "no indices"
                raise FileResolutionError(
                    f"No files matched template {template!r} for {index_description} in {input_directory!r}"
                )
            for filename in matches:
                full_path = os.path.join(input_directory, filename)
                if full_path not in seen_paths:
                    seen_paths.add(full_path)
                    resolved.append(full_path)

    if not resolved:
        raise FileResolutionError(f"No input files matched in {input_directory!r}")
    return tuple(resolved)
