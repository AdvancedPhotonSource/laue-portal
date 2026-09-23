"""Reconstruction page adapter: ROI state, list rows, and the stored-frame image.

The reference image, the depth traces, and ROI placement come from lauelab
(``plot_reference_image``, ``plot_depth_trace``, ``plot_roi_traces``,
``square_bounds``). The portal owns ROI names, colours, and selection, kept in
a browser store as plain values:

~~~text
{point_id: {"next": 3, "rois": [{"id": "ROI 1", "bounds": [y0, y1, x0, x1], "color": "rgb(...)"}]}}
~~~

ROIs belong to one point and are never applied to another. An ROI's colour
follows from its number, so deleting or deselecting one never recolours the
rest. The depth frame figure is a plain heatmap of one stored frame with the
same pixel conventions as the library's reference image.
"""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
from lauelab.indexing import InputError
from lauelab.reconstruct.inspection import bounds_center, square_bounds
from lauelab.visualization import DEFAULT_ROI_COLORS, RoiOverlay

from laue_portal.components.visualization.detector_view import image_colorscale


class RoiPlacementError(ValueError):
    """An ROI cannot be placed; the message is shown next to the image."""


def point_rois(state: dict | None, point_id: str | None) -> list[dict]:
    if not state or not point_id:
        return []
    return list((state.get(point_id) or {}).get("rois") or [])


def add_roi(state: dict | None, point_id: str, size, x: float, y: float, shape: tuple[int, int]) -> tuple[dict, dict]:
    """Place an ``size`` x ``size`` ROI centred as close as possible to the click.

    Returns ``(new_state, roi)``. Raises :class:`RoiPlacementError` when the
    size is not a positive integer or the square would leave the image; the
    square is never clipped or shifted.
    """

    try:
        size = int(size)
    except (TypeError, ValueError):
        size = 0
    if size < 1:
        raise RoiPlacementError("ROI size must be a positive whole number of pixels")
    try:
        bounds = square_bounds(size, float(x), float(y), tuple(shape))
    except InputError as error:
        rows, columns = shape
        raise RoiPlacementError(
            f"A {size} x {size} ROI at ({x:g}, {y:g}) would extend outside the {columns} x {rows} image; not added"
        ) from error
    state = dict(state or {})
    current = dict(state.get(point_id) or {"next": 1, "rois": []})
    number = int(current["next"])
    roi = {
        "id": f"ROI {number}",
        "bounds": [int(value) for value in bounds],
        "color": DEFAULT_ROI_COLORS[(number - 1) % len(DEFAULT_ROI_COLORS)],
    }
    current = {"next": number + 1, "rois": [*current["rois"], roi]}
    state[point_id] = current
    return state, roi


def delete_rois(state: dict | None, point_id: str, ids) -> dict:
    """Remove the named ROIs of one point; numbering continues, so colours never repeat early."""

    state = dict(state or {})
    current = state.get(point_id)
    if not current:
        return state
    remove = set(ids or ())
    state[point_id] = {"next": current["next"], "rois": [roi for roi in current["rois"] if roi["id"] not in remove]}
    return state


def roi_rows(rois: list[dict]) -> list[dict]:
    """ROI list rows: identity, centre (y, x) in stored-image pixels, size, and colour."""

    rows = []
    for roi in rois:
        y0, y1, x0, x1 = roi["bounds"]
        center_x, center_y = bounds_center(tuple(roi["bounds"]))
        rows.append({"id": roi["id"], "y": center_y, "x": center_x, "size": x1 - x0, "color": roi["color"]})
    return rows


def roi_overlays(rois: list[dict]) -> list[RoiOverlay]:
    return [RoiOverlay(roi["id"], tuple(roi["bounds"]), roi["color"]) for roi in rois]


def auto_limits(image: np.ndarray) -> tuple[float, float] | None:
    """Display contrast: the 1st to 99.9th percentile of finite pixels, else the full range."""

    finite = image[np.isfinite(image)] if image.dtype.kind == "f" else image.ravel()
    if finite.size == 0:
        return None
    low, high = (float(value) for value in np.percentile(finite, (1.0, 99.9)))
    if low >= high:
        low, high = float(finite.min()), float(finite.max())
    return (low, high) if low < high else None


def frame_figure(
    image: np.ndarray,
    *,
    point_id: str,
    depth_index: int,
    depth_um: float,
    colormap: str | None = "gray",
    limits: tuple[float, float] | None = None,
) -> go.Figure:
    """One stored frame: origin upper left, x right, y down, equal pixel scales."""

    rows, columns = image.shape
    heatmap = {
        "z": image,
        "colorscale": image_colorscale(colormap),
        "colorbar": {"title": {"text": "Stored intensity"}},
        "hovertemplate": "x: %{x}<br>y: %{y}<br>I: %{z:.6g}<extra></extra>",
        "uid": "depth-frame",
    }
    if limits is not None:
        heatmap["zmin"], heatmap["zmax"] = limits
    figure = go.Figure(go.Heatmap(**heatmap))
    figure.update_layout(
        title={"text": f"Depth {depth_um:.4g} µm (index {depth_index}) · {point_id}"},
        xaxis={
            "title": {"text": "X pixel"},
            "range": [-0.5, columns - 0.5],
            "scaleanchor": "y",
            "scaleratio": 1,
            "constrain": "domain",
            "showgrid": False,
            "zeroline": False,
        },
        yaxis={
            "title": {"text": "Y pixel"},
            "range": [rows - 0.5, -0.5],
            "constrain": "domain",
            "showgrid": False,
            "zeroline": False,
        },
        plot_bgcolor="white",
        margin={"l": 55, "r": 30, "t": 40, "b": 50},
        # Zoom survives browsing depths and resets only when the pixel grid changes.
        uirevision=f"depth-frame-{columns}x{rows}",
    )
    return figure
