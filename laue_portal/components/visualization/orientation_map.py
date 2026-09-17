"""Color-map tab adapter: portal controls in, lauelab prepared data and Plotly figure out.

The scientific work (axes, orientation colors, symmetry, references, pole HSV,
frame-only records) is lauelab's ``prepare_map`` and ``plot_map``. This module
owns only portal choices: control values, non-indexed appearance, user color
ranges, the "step" notion, and cross-plot selection highlighting.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Sequence

import numpy as np
import plotly.graph_objects as go
from lauelab.analysis import SurfaceFrame
from lauelab.visualization import (
    AXIS_OPTIONS,
    COLOR_MODES,
    NO_PATTERN,
    DataScope,
    MapData,
    VisualizationDataset,
    plot_map,
    prepare_map,
)

# Portal labels for the library axis names (values must be library axis names).
AXIS_CHOICES = (
    ("X", "X motor"),
    ("Y", "Y motor"),
    ("Z", "Z motor"),
    ("H", "H"),
    ("F", "F"),
    ("depth", "Depth"),
    ("Xlab", "X lab"),
    ("Ylab", "Y lab"),
    ("Zlab", "Z lab"),
    ("Hlab", "H lab"),
    ("Flab", "F lab"),
)
assert {value for value, _ in AXIS_CHOICES} == {choice.value for choice in AXIS_OPTIONS}

SCALAR_MODES = frozenset({"n_indexed", "goodness", "rms_error", "n_patterns"})
ORIENTATION_MODES = frozenset({"cubic_ipf", "rodrigues", "misorientation", "pole_hsv"})
assert SCALAR_MODES | ORIENTATION_MODES == {choice.value for choice in COLOR_MODES}

NONINDEXED_COLORS = {
    "gray": "rgb(150,150,150)",
    "red": "rgb(220,40,40)",
    "blue": "rgb(40,90,220)",
    "green": "rgb(40,160,60)",
}
NONINDEXED_STYLES = (*NONINDEXED_COLORS, "transparent")
SURFACE_PRESETS = ("normal", "X", "H", "Y", "Z", "F")
HIGHLIGHT_ROLE = "highlight"


def is_scalar_mode(color_by: str | None) -> bool:
    return (color_by or "cubic_ipf") in SCALAR_MODES


def resolve_surface(surface: str | None, values: Sequence | None = None) -> str | SurfaceFrame:
    """A preset name, or a validated custom ``SurfaceFrame`` built from nine inputs."""

    if surface != "custom":
        name = surface or "normal"
        if name not in SURFACE_PRESETS:
            raise ValueError(f"unknown surface {name!r}")
        return name
    if values is None or len(values) != 9 or any(value is None or value == "" for value in values):
        raise ValueError("Custom surface needs all nine tilt, roll, and normal components")
    try:
        numbers = [float(value) for value in values]
    except (TypeError, ValueError) as error:
        raise ValueError("Custom surface components must be numbers") from error
    if not all(math.isfinite(value) for value in numbers):
        raise ValueError("Custom surface components must be finite")
    return SurfaceFrame.from_vectors(tilt=numbers[0:3], roll=numbers[3:6], normal=numbers[6:9], name="custom")


def parse_reference_matrix(values: Sequence | None) -> np.ndarray | None:
    """Nine G_ref inputs (rows a*, b*, c* in 1/nm with 2 pi) as a matrix, or None when incomplete."""

    if values is None or len(values) != 9 or any(value is None or value == "" for value in values):
        return None
    try:
        matrix = np.array([float(value) for value in values], dtype=float).reshape(3, 3)
    except (TypeError, ValueError) as error:
        raise ValueError("G_ref entries must be numbers") from error
    if not np.isfinite(matrix).all():
        raise ValueError("G_ref entries must be finite")
    return matrix


def frame_id_at(dataset: VisualizationDataset, step) -> object:
    """The frame identity at a step position (manifest index, or XML step order)."""

    if step is None or step == "":
        raise ValueError("Step is required")
    value = float(step)
    if not value.is_integer() or value < 0 or value >= dataset.n_frames:
        raise ValueError(f"Step must be an integer between 0 and {dataset.n_frames - 1}")
    return dataset.frame_ids[int(value)]


def frame_position(dataset: VisualizationDataset, frame_id) -> int:
    """The step position of a frame identity."""

    try:
        return dataset.frame_ids.index(frame_id)
    except ValueError:
        raise KeyError(f"frame {frame_id!r} is not in the dataset") from None


def _limits(cmin, cmax):
    values = []
    for value in (cmin, cmax):
        if value is None or value == "":
            return None
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            return None
    low, high = values
    if not (math.isfinite(low) and math.isfinite(high)) or low == high:
        return None
    return (min(low, high), max(low, high))


def build_map(
    dataset: VisualizationDataset,
    *,
    scope: DataScope,
    axes: Sequence[str],
    color: str,
    surface="normal",
    marker_size: int = 10,
    nonindexed_style: str = "gray",
    palette: str | None = None,
    reverse: bool = False,
    cmin=None,
    cmax=None,
    symmetry: str = "auto",
    reference_mode: str = "lab",
    reference_step=None,
    reference_matrix: np.ndarray | None = None,
    pole_hkl=(1, 0, 0),
    pole_center=(0.0, 0.0),
    pole_radius_deg: float = 22.5,
    misorientation_reference=None,
) -> tuple[go.Figure, MapData]:
    """Prepare and render the color map for the portal's control values.

    Raises ``ValueError`` (or ``KeyError`` for an unknown reference) with a
    message meant for the user when the inputs cannot produce a map.
    """

    color = color or "cubic_ipf"
    kwargs = {"axes": tuple(axes), "color": color, "scope": scope, "surface": surface}
    if color == "pole_hsv":
        kwargs.update(
            pole_hkl=tuple(pole_hkl), pole_center=tuple(pole_center), pole_color_radius_deg=float(pole_radius_deg)
        )
    if color in ("rodrigues", "misorientation"):
        kwargs["orientation_symmetry"] = symmetry or "auto"
    if color == "rodrigues":
        if reference_mode == "step":
            kwargs["rodrigues_reference"] = (frame_id_at(dataset, reference_step), 0)
        elif reference_mode == "custom":
            if reference_matrix is None:
                raise ValueError("Custom G_ref needs all nine entries")
            kwargs["rodrigues_reference_reciprocal"] = reference_matrix
    if color == "misorientation":
        if misorientation_reference is None:
            raise ValueError("Misorientation coloring needs a reference pattern: click one in the pole figure")
        kwargs["misorientation_reference"] = tuple(misorientation_reference)

    map_data = prepare_map(dataset, **kwargs)
    if map_data.color_kind == "scalar":
        changes = {}
        if palette:
            changes["palette"] = palette
        limits = _limits(cmin, cmax)
        if limits is not None:
            changes["color_limits"] = limits
        if changes:
            map_data = dataclasses.replace(map_data, **changes)

    trace_update: dict = {"data": {"marker": {"symbol": "square"}}}
    if map_data.color_kind == "scalar" and reverse:
        trace_update["data"]["marker"]["reversescale"] = True
    style = nonindexed_style if nonindexed_style in NONINDEXED_STYLES else "gray"
    if style == "transparent":
        trace_update["unindexed"] = {"visible": False}
    else:
        trace_update["unindexed"] = {"marker": {"color": NONINDEXED_COLORS[style], "symbol": "square"}}
    figure = plot_map(map_data, marker_size=max(1, int(marker_size)), trace_update=trace_update)
    return figure, map_data


def scalar_range_for(dataset: VisualizationDataset, scope: DataScope, color: str) -> tuple[float | None, float | None]:
    """Data range of a scalar color over the scoped patterns, without preparing a map."""

    if color not in SCALAR_MODES:
        return None, None
    rows = np.flatnonzero(scope.pattern_mask(dataset))
    if color == "n_patterns":
        frames = np.unique(dataset.pattern_frame_indices[rows])
        values = np.bincount(dataset.pattern_frame_indices, minlength=dataset.n_frames)[frames].astype(float)
    else:
        source = {
            "n_indexed": dataset.pattern_n_indexed,
            "goodness": dataset.pattern_goodness,
            "rms_error": dataset.pattern_rms_error_deg,
        }[color]
        values = np.asarray(source[rows], dtype=float)
    values = values[np.isfinite(values)]
    if not len(values):
        return None, None
    return float(values.min()), float(values.max())


def scalar_auto_range(map_data: MapData) -> tuple[float | None, float | None]:
    """Finite range of a scalar color, ignoring frame-only and unindexed records."""

    if map_data.color_kind != "scalar":
        return None, None
    values = map_data.colors[np.isfinite(map_data.colors)]
    if not len(values):
        return None, None
    return float(values.min()), float(values.max())


def _selected_mask(trace, selected: set) -> np.ndarray | None:
    customdata = trace.customdata
    if customdata is None:
        return None
    rows = np.asarray(customdata, dtype=object)
    if rows.ndim != 2 or rows.shape[1] < 2:
        return None
    mask = np.zeros(len(rows), dtype=bool)
    for index, (frame_id, pattern_index) in enumerate(rows[:, :2]):
        frame_key = _identity(frame_id)
        pattern_key = _identity(pattern_index)
        if pattern_key is None:
            continue
        mask[index] = (frame_key, int(pattern_key)) in selected
    return mask


def _identity(value):
    if value is None:
        return None
    if isinstance(value, (float, np.floating)):
        if np.isnan(value):
            return None
        return int(value) if float(value).is_integer() else float(value)
    if isinstance(value, np.integer):
        return int(value)
    return value


def normalize_pattern_ids(values) -> set[tuple]:
    """Pattern identities from a Dash store (lists of ``[frame_id, pattern_index]``)."""

    selected = set()
    for item in values or ():
        if item is None or len(item) != 2 or item[1] is None:
            continue
        selected.add((_identity(item[0]), int(item[1])))
    return selected


def highlight_selection(figure: go.Figure, map_data: MapData, selected_pattern_ids, *, marker_size: int) -> int:
    """Dim unselected map points and ring the selected patterns. Returns the ring count."""

    selected = normalize_pattern_ids(selected_pattern_ids)
    if not selected or not figure.data:
        return 0
    is_3d = any(trace.type == "scatter3d" for trace in figure.data)
    ring_x, ring_y, ring_z, ring_custom = [], [], [], []
    for trace in figure.data:
        role = (trace.meta or {}).get("role") if isinstance(trace.meta, dict) else None
        if role not in ("data", "unindexed"):
            continue
        mask = _selected_mask(trace, selected)
        if mask is None:
            continue
        if not is_3d:
            trace.marker.opacity = np.where(mask, 1.0, 0.2)
        if mask.any():
            ring_x.extend(np.asarray(trace.x)[mask])
            ring_y.extend(np.asarray(trace.y)[mask])
            if is_3d:
                ring_z.extend(np.asarray(trace.z)[mask])
            ring_custom.extend(np.asarray(trace.customdata, dtype=object)[mask].tolist())
    if not ring_x:
        return 0
    ring = {
        "mode": "markers",
        "name": "Selected",
        "marker": {
            "symbol": "circle-open",
            "size": max(1, int(marker_size)) + 6,
            "color": "black",
            "line": {"width": 2},
        },
        "customdata": ring_custom,
        "hoverinfo": "skip",
        "meta": {"role": HIGHLIGHT_ROLE},
        "uid": "map-highlight",
    }
    if is_3d:
        ring["marker"]["size"] = max(1, int(marker_size)) + 3
        figure.add_trace(go.Scatter3d(x=ring_x, y=ring_y, z=ring_z, **ring))
    else:
        figure.add_trace(go.Scattergl(x=ring_x, y=ring_y, **ring))
    return len(ring_x)


def point_details(dataset: VisualizationDataset, frame_id, pattern_index=None) -> dict:
    """Values shown when a map point is clicked."""

    position = frame_position(dataset, frame_id)
    pattern_rows = np.flatnonzero(dataset.pattern_frame_indices == position)
    details = {
        "step": position,
        "frame_id": frame_id,
        "sample_position": [float(value) for value in dataset.sample_positions[position]],
        "depth": None if np.isnan(dataset.depths[position]) else float(dataset.depths[position]),
        "n_peaks": int(dataset.frame_n_peaks[position]),
        "n_patterns": int(len(pattern_rows)),
        "pattern_index": None if pattern_index in (None, NO_PATTERN) else int(pattern_index),
        "n_indexed": None,
        "goodness": None,
        "rms_error_deg": None,
    }
    if details["pattern_index"] is not None:
        rows = pattern_rows[dataset.pattern_indices[pattern_rows] == details["pattern_index"]]
        if len(rows):
            row = int(rows[0])
            details.update(
                n_indexed=int(dataset.pattern_n_indexed[row]),
                goodness=float(dataset.pattern_goodness[row]),
                rms_error_deg=float(dataset.pattern_rms_error_deg[row]),
            )
    return details
