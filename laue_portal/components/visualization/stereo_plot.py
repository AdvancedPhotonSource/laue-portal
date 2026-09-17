"""Pole-figure tab adapter around lauelab's pole preparation and renderer."""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
from lauelab.analysis import pairwise_misorientation, symmetry_operations
from lauelab.visualization import DataScope, PoleFigureData, VisualizationDataset, plot_pole_figure, prepare_pole_figure

from laue_portal.components.visualization.orientation_map import HIGHLIGHT_ROLE, _selected_mask, normalize_pattern_ids

HOVER_POINT_LIMIT = 50_000
MAX_PATTERNS_FOR_MISORIENTATION = 700  # pairwise work is O(k^2); keep the ROI summary interactive


def build_pole_figure(
    dataset: VisualizationDataset,
    *,
    scope: DataScope,
    hkl=(1, 0, 0),
    surface="normal",
    color: str = "hsv_position",
    radius_deg: float = 22.5,
    center=(0.0, 0.0),
    marker_size: int = 7,
) -> tuple[go.Figure, PoleFigureData]:
    pole_data = prepare_pole_figure(
        dataset,
        hkl=tuple(int(value) for value in hkl),
        scope=scope,
        surface=surface,
        color=color or "hsv_position",
        pole_center=tuple(float(value) for value in center),
        pole_color_radius_deg=float(radius_deg),
    )
    figure = plot_pole_figure(pole_data, marker_size=max(1, int(marker_size)), hover_point_limit=HOVER_POINT_LIMIT)
    return figure, pole_data


def highlight_pole_selection(figure: go.Figure, selected_pattern_ids, *, marker_size: int) -> int:
    """Ring the poles of the selected patterns; returns the number of ringed poles."""

    selected = normalize_pattern_ids(selected_pattern_ids)
    if not selected:
        return 0
    count = 0
    for trace in figure.data:
        role = (trace.meta or {}).get("role") if isinstance(trace.meta, dict) else None
        if role != "data":
            continue
        mask = _selected_mask(trace, selected)
        if mask is None or not mask.any():
            continue
        figure.add_trace(
            go.Scattergl(
                x=np.asarray(trace.x)[mask],
                y=np.asarray(trace.y)[mask],
                mode="markers",
                name="Selected",
                marker={
                    "symbol": "circle-open",
                    "size": max(1, int(marker_size)) + 6,
                    "color": "black",
                    "line": {"width": 2},
                },
                hoverinfo="skip",
                showlegend=False,
                meta={"role": HIGHLIGHT_ROLE},
                uid="pole-highlight",
            )
        )
        count += int(mask.sum())
    return count


def pattern_rows(dataset: VisualizationDataset, pattern_ids) -> np.ndarray:
    """Dataset pattern rows for stable ``(frame_id, pattern_index)`` identities, in identity order."""

    positions = {frame_id: index for index, frame_id in enumerate(dataset.frame_ids)}
    rows = []
    for frame_id, pattern_index in normalize_pattern_ids(pattern_ids):
        position = positions.get(frame_id)
        if position is None:
            continue
        candidates = np.flatnonzero(
            (dataset.pattern_frame_indices == position) & (dataset.pattern_indices == pattern_index)
        )
        rows.extend(int(value) for value in candidates)
    return np.asarray(sorted(rows), dtype=int)


def crystal_operations(dataset: VisualizationDataset):
    """Proper rotations of the crystal system when lauelab supports it, else None (no reduction)."""

    system = dataset.crystal.crystal_system if dataset.crystal is not None else None
    if system in ("cubic", "hexagonal"):
        return symmetry_operations(system)
    return None


def misorientation_summary(
    dataset: VisualizationDataset, pattern_ids, *, max_patterns: int = MAX_PATTERNS_FOR_MISORIENTATION
) -> dict | None:
    """Pairwise misorientation statistics for selected patterns, or a skip notice above the bound."""

    rows = pattern_rows(dataset, pattern_ids)
    rotations = dataset.pattern_rotations[rows]
    finite = np.isfinite(rotations).all(axis=(1, 2))
    rotations = rotations[finite]
    if len(rotations) < 2:
        return None
    if len(rotations) > max_patterns:
        return {"skipped": True, "n_patterns": int(len(rotations)), "limit": max_patterns}
    operations = crystal_operations(dataset)
    _, angles = pairwise_misorientation(rotations, operations=operations)
    return {
        "skipped": False,
        "n_patterns": int(len(rotations)),
        "n_pairs": int(len(angles)),
        "mean": float(np.mean(angles)),
        "min": float(np.min(angles)),
        "max": float(np.max(angles)),
        "symmetry": dataset.crystal.crystal_system if operations is not None else "none",
    }
