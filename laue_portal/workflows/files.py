"""Shared filename resolution for reconstruction and indexing workflows."""

import os
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import product

from laue_portal.utilities.filename_patterns import compile_filename_templates
from laue_portal.utilities.srange import srange

ProgressCallback = Callable[[int, int], None]


@dataclass(frozen=True)
class ResolvedInput:
    """An input path and the template indices used to select it.

    For reconstructed frames, ``path`` refers to the point file. ``point_id``
    and ``depth_index`` select a frame within it; depth indices are zero-based.
    """

    path: str
    template_index: int
    indices: tuple[int, ...]
    point_id: str | None = None
    depth_index: int | None = None

    @property
    def scan_point(self) -> int | None:
        return self.indices[0] if self.indices else None

    @property
    def depth_point(self) -> int | None:
        return self.indices[1] if len(self.indices) > 1 else None


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


def resolve_inputs(
    directory: str | os.PathLike[str],
    templates: Sequence[str],
    scan_points: Sequence[int],
    *,
    depth_points: Sequence[int] | None = None,
    append_suffix_wildcard: bool = False,
    progress_callback: ProgressCallback | None = None,
    progress_interval: int = 10_000,
) -> tuple[ResolvedInput, ...]:
    """Resolve requested files with one directory listing and one regex pass.

    Matches are bucketed by captured ``%d`` indices, then emitted in template
    and requested-index order. Files within a bucket retain directory-listing
    order. The input manifest records this order for execution.
    """

    if progress_interval <= 0:
        raise WorkflowValidationError("Progress interval must be greater than zero")
    input_directory = normalize_input_directory(directory)
    normalized_templates = normalize_filename_templates(templates)
    for template in normalized_templates:  # reject placeholder mismatches before listing the directory
        _expected_index_keys(template, scan_points, depth_points)
    try:
        filenames = os.listdir(input_directory)
    except OSError as error:
        raise FileResolutionError(f"Could not list input directory {input_directory!r}: {error}") from error

    resolved = []
    seen_paths = set()
    for template_index, index_key, filename in _match_names(
        filenames,
        normalized_templates,
        scan_points,
        depth_points,
        where=repr(input_directory),
        append_suffix_wildcard=append_suffix_wildcard,
        progress_callback=progress_callback,
        progress_interval=progress_interval,
    ):
        full_path = os.path.join(input_directory, filename)
        if full_path not in seen_paths:
            seen_paths.add(full_path)
            resolved.append(ResolvedInput(full_path, template_index, index_key))

    if not resolved:
        raise FileResolutionError(f"No input files matched in {input_directory!r}")
    return tuple(resolved)


def _match_names(
    names: Sequence[str],
    templates: Sequence[str],
    scan_points: Sequence[int],
    depth_points: Sequence[int] | None,
    *,
    where: str,
    append_suffix_wildcard: bool,
    progress_callback: ProgressCallback | None = None,
    progress_interval: int = 10_000,
):
    """Yield ``(template_index, index_key, name)`` in template and requested-index order.

    Names that match the same indices retain their input order.
    """

    expected_keys = tuple(_expected_index_keys(template, scan_points, depth_points) for template in templates)
    matcher = compile_filename_templates(templates, append_suffix_wildcard=append_suffix_wildcard)

    total = len(names)
    if progress_callback is not None:
        progress_callback(0, total)

    buckets: tuple[defaultdict[tuple[int, ...], list[str]], ...] = tuple(defaultdict(list) for _ in templates)
    for scanned, name in enumerate(names, start=1):
        match = matcher.match(name)
        if match is not None:
            buckets[match.template_index][match.indices].append(name)
        if progress_callback is not None and scanned % progress_interval == 0:
            progress_callback(scanned, total)
    if progress_callback is not None and (total == 0 or total % progress_interval):
        progress_callback(total, total)

    for template_index, template in enumerate(templates):
        for index_key in expected_keys[template_index]:
            matches = buckets[template_index].get(index_key, ())
            if not matches:
                index_description = ", ".join(str(value) for value in index_key) or "no indices"
                raise FileResolutionError(f"No files matched template {template!r} for {index_description} in {where}")
            for name in matches:
                yield template_index, tuple(index_key), name


def is_reconstruction_scan(path: str | os.PathLike[str]) -> bool:
    """Whether ``path`` is a readable lauelab reconstruction scan catalog (``scan.h5``)."""

    from lauelab.reconstruct import ScanReader

    if not os.path.isfile(path):
        return False
    try:
        with ScanReader(path):
            return True
    except (OSError, ValueError):
        return False


def resolve_scan_inputs(
    scan_path: str | os.PathLike[str],
    templates: Sequence[str],
    scan_points: Sequence[int],
    *,
    depth_indices: Sequence[int] | None = None,
) -> tuple[ResolvedInput, ...]:
    """Select reconstructed frames by source filename and depth index.

    Templates match the original input filenames recorded in the catalog.
    Each template accepts at most one ``%d`` for the scan point. Depth indices
    are zero-based; ``None`` selects every depth.

    Selection reads only catalog metadata and returns point-file references
    for indexing. All selected points must be complete in that snapshot.
    During reconstruction, catalog updates can lag point completion by a few
    seconds.

    Raises
    ------
    FileResolutionError
        If the file is not a scan catalog, a template matches no point, a
        selected point is not complete, or a depth index is outside a
        selected point's stack.
    """

    from lauelab.reconstruct import ScanReader

    path = normalize_input_directory(scan_path)
    normalized_templates = normalize_filename_templates(templates)
    for template in normalized_templates:
        if template.count("%d") > 1:
            raise FileResolutionError(
                f"Filename template {template!r} has more than one %d placeholder; "
                "a scan catalog selects depths with the depth range"
            )
    try:
        scan = ScanReader(path)  # loads the catalog snapshot and closes the file
    except (OSError, ValueError) as error:
        raise FileResolutionError(f"{path!r} is not a readable reconstruction scan catalog: {error}") from error
    points = scan.points

    by_name: dict[str, list] = defaultdict(list)
    for point in points:
        by_name[os.path.basename(point.source_path)].append(point)

    resolved = []
    problems = []
    seen = set()
    for template_index, index_key, name in _match_names(
        list(by_name), normalized_templates, scan_points, None, where=repr(path), append_suffix_wildcard=True
    ):
        for point in by_name[name]:
            if point.point_id in seen:
                continue
            seen.add(point.point_id)
            if not point.complete:
                detail = f": {point.error}" if point.error else ""
                problems.append(f"point {point.point_id!r} is {point.status}{detail}")
                continue
            n_depths = point.shape[0]
            selected = range(n_depths) if depth_indices is None else depth_indices
            outside = [value for value in selected if not 0 <= value < n_depths]
            if outside:
                problems.append(f"point {point.point_id!r} has depth indices 0-{n_depths - 1}; requested {outside[0]}")
                continue
            point_path = os.fspath(scan.point_path(point.point_id))
            for depth_index in selected:
                resolved.append(
                    ResolvedInput(
                        point_path,
                        template_index,
                        (*index_key, int(depth_index)),
                        point_id=point.point_id,
                        depth_index=int(depth_index),
                    )
                )
    if problems:
        shown = "; ".join(problems[:5]) + (f"; and {len(problems) - 5} more" if len(problems) > 5 else "")
        raise FileResolutionError(f"Cannot index {path!r}: {shown}")
    if not resolved:
        raise FileResolutionError(f"No frames were selected in {path!r}")
    return tuple(resolved)


def resolve_request_inputs(
    input_path: str | os.PathLike[str],
    templates: Sequence[str],
    scan_points: Sequence[int],
    *,
    depth_values: Sequence[int] | None = None,
    progress_callback: ProgressCallback | None = None,
) -> tuple[ResolvedInput, ...]:
    """Resolve an indexing request's inputs from a directory or a reconstruction scan catalog.

    For directory inputs, ``depth_values`` fill the second ``%d`` in the
    filename template. For scan catalogs, they select zero-based depth indices
    within each point; see :func:`resolve_scan_inputs`. Catalogs are detected
    by their format marker.
    """

    if is_reconstruction_scan(input_path):
        return resolve_scan_inputs(input_path, templates, scan_points, depth_indices=depth_values)
    return resolve_inputs(
        input_path, templates, scan_points, depth_points=depth_values, progress_callback=progress_callback
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
    """Return only the paths from :func:`resolve_inputs`, in the same order."""

    return tuple(
        entry.path
        for entry in resolve_inputs(
            directory,
            templates,
            scan_points,
            depth_points=depth_points,
            append_suffix_wildcard=append_suffix_wildcard,
            progress_callback=progress_callback,
            progress_interval=progress_interval,
        )
    )
