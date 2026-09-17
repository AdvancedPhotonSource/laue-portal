"""Detector-view tab adapter around lauelab's detector preparation, simulation, and renderer.

Measured peaks, indexed assignments, and simulated missing reflections come
from ``prepare_detector_view``; the portal supplies the externally loaded
detector image, the display controls, and its axis conventions. A simulation
failure is not replaced by another simulator: the error propagates to the
page, which keeps the measured and indexed layers usable and shows the message.
"""

from __future__ import annotations

import math

import numpy as np
import plotly.graph_objects as go
from lauelab.visualization import DetectorViewData, VisualizationDataset, plot_detector_view, prepare_detector_view
from plotly.colors import sample_colorscale

# Portal colormap names (kept from the previous UI) to Plotly colorscales.
IMAGE_COLOR_SCALES = {
    "gray": "Gray",
    "gray_r": "Greys",
    "viridis": "Viridis",
    "plasma": "Plasma",
    "inferno": "Inferno",
    "magma": "Magma",
    "turbo": "Turbo",
    "jet": "Jet",
    "terrain_r": "Portland",
}

# Energy window for simulated missing reflections, unchanged from the previous
# portal simulator. Not a visible control.
SIMULATION_ENERGY_RANGE_KEV = (6.0, 30.0)


def image_colorscale(name: str | None):
    """Return a Plotly colorscale for the portal colormap name."""

    if name == "gray_r":
        colors = sample_colorscale("Gray", [i / 255 for i in range(256)])
        return [[i / 255, colors[255 - i]] for i in range(256)]
    return IMAGE_COLOR_SCALES.get(name or "gray", IMAGE_COLOR_SCALES["gray"])


def image_limits(custom_vmin, custom_vmax, auto_vmin, auto_vmax):
    """Resolve contrast limits from the sidebar controls and the loaded image."""

    vmin = auto_vmin if custom_vmin in (None, "") else custom_vmin
    vmax = auto_vmax if custom_vmax in (None, "") else custom_vmax
    if vmin is None or vmax is None:
        return None
    try:
        low, high = float(vmin), float(vmax)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(low) and math.isfinite(high)):
        return None
    if low > high:
        low, high = high, low
    if low == high:
        return None
    return (low, high)


def frame_patterns(dataset: VisualizationDataset, frame_id) -> list[tuple[int, int]]:
    """``(rank, n_indexed)`` of every pattern in the frame, in rank order."""

    position = dataset.frame_ids.index(frame_id)
    rows = np.flatnonzero(dataset.pattern_frame_indices == position)
    order = np.argsort(dataset.pattern_indices[rows])
    return [(int(dataset.pattern_indices[row]), int(dataset.pattern_n_indexed[row])) for row in rows[order]]


def eligible_frames(dataset: VisualizationDataset, scope) -> np.ndarray:
    """Positions of frames the scope keeps (frames with a selected pattern or eligible frame-only)."""

    mask = np.zeros(dataset.n_frames, dtype=bool)
    rows = np.flatnonzero(scope.pattern_mask(dataset))
    mask[dataset.pattern_frame_indices[rows]] = True
    if scope.includes_unindexed_frames:
        mask |= scope.unindexed_frame_mask(dataset)
    return np.flatnonzero(mask)


def build_detector_view(
    dataset: VisualizationDataset,
    *,
    frame_id,
    patterns="all",
    image: np.ndarray | None = None,
    show_detected: bool = True,
    show_indexed: bool = True,
    show_simulated: bool = False,
    show_hkl_labels: bool = True,
    marker_size: int = 10,
    label_size: int = 10,
    image_colormap: str | None = "gray",
    limits=None,
    image_opacity: float = 0.8,
    energy_range_kev=SIMULATION_ENERGY_RANGE_KEV,
) -> tuple[go.Figure, DetectorViewData]:
    """Prepare and render one frame's detector overlay for the portal controls.

    ``patterns`` is ``"all"`` or a sequence of frame-local pattern ranks. The
    simulation runs only when ``show_simulated`` is true; its ``ValueError``
    (missing crystal or geometry) or ``RuntimeError`` propagates unchanged.
    """

    selected = "all" if patterns in (None, "all") else tuple(int(value) for value in patterns)
    view = prepare_detector_view(
        dataset,
        frame_id=frame_id,
        patterns=selected,
        image=image,
        simulation_energy_range_kev=tuple(energy_range_kev) if show_simulated else None,
    )
    extent_x, extent_y = view.extent
    size = max(1, int(marker_size))
    text_size = max(6, int(label_size))
    figure = plot_detector_view(
        view,
        show_detected=bool(show_detected),
        show_indexed=bool(show_indexed),
        show_simulated=bool(show_simulated),
        show_hkl_labels=bool(show_hkl_labels),
        marker_size=size,
        image_colorscale=image_colorscale(image_colormap),
        image_limits=limits,
        image_opacity=float(image_opacity),
        trace_update={
            "indexed": {"textfont": {"size": text_size}},
            "simulated": {"textfont": {"size": text_size}},
        },
        layout_update={
            # Detector convention: pixel (0, 0) at the upper left, equal scale, plot
            # area shrinks rather than clipping so the chip and every marker stay visible.
            "xaxis": {
                "title": {"text": "X pixel"},
                "scaleanchor": "y",
                "scaleratio": 1,
                "constrain": "domain",
                "zeroline": False,
                "showgrid": False,
            },
            "yaxis": {
                "title": {"text": "Y pixel"},
                "autorange": "reversed",
                "constrain": "domain",
                "zeroline": False,
                "showgrid": False,
            },
            "plot_bgcolor": "white",
            "paper_bgcolor": "white",
            "margin": {"l": 50, "r": 20, "t": 40, "b": 50},
            "autosize": True,
            "showlegend": True,
            "legend": {
                "orientation": "v",
                "yanchor": "top",
                "y": 0.99,
                "xanchor": "right",
                "x": 1.18,
                "bgcolor": "rgba(255,255,255,0.85)",
                "bordercolor": "rgb(200,200,200)",
                "borderwidth": 1,
            },
            "uirevision": f"detector-view-{int(extent_x)}x{int(extent_y)}",
        },
    )
    return figure, view


def detector_summary(dataset: VisualizationDataset, view: DetectorViewData) -> dict:
    """Values for the card beneath the detector graph."""

    position = dataset.frame_ids.index(view.frame_id)
    n_measured = int(len(view.measured_xy))
    n_indexed_peaks = int(np.count_nonzero(view.measured_indexed))
    simulated = {sim.pattern_index: int(len(sim.hkl)) for sim in view.simulations}
    pattern_rows = {
        int(dataset.pattern_indices[row]): row for row in np.flatnonzero(dataset.pattern_frame_indices == position)
    }
    patterns = []
    for pattern in view.patterns:
        row = pattern_rows.get(pattern.pattern_index)
        patterns.append(
            {
                "pattern_index": pattern.pattern_index,
                "n_indexed": int(len(pattern.measured_peak_indices)),
                "n_predicted": int(len(pattern.predicted_xy)),
                "goodness": None if row is None else float(dataset.pattern_goodness[row]),
                "rms_error_deg": None if row is None else float(dataset.pattern_rms_error_deg[row]),
                "n_simulated": simulated.get(pattern.pattern_index, 0),
            }
        )
    return {
        "step": position,
        "frame_id": view.frame_id,
        "detector_id": view.detector_id,
        "input_image": dataset.input_images[position],
        "sample_position": [float(value) for value in dataset.sample_positions[position]],
        "n_measured": n_measured,
        "n_indexed_peaks": n_indexed_peaks,
        "indexed_fraction": (n_indexed_peaks / n_measured) if n_measured else 0.0,
        "patterns": patterns,
    }
