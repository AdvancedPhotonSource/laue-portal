"""
Detector-pixel view of indexed and measured Laue peaks.

This component projects every indexed reflection (h, k, l) from the
reciprocal lattice in the indexing XML back onto the detector via
:mod:`laue_portal.analysis.back_projection`, then overlays the predicted
positions on top of the *measured* peaks from ``<peaksXY>``.

Visual conventions mirror Igor Pro's ``DisplayResultOfIndexing`` and
``xmlPixelinfoForMovies``:

    - Measured peaks, NOT matched to any indexed reflection
        light-blue open squares
    - Measured peaks, matched to pattern 0 (the best grain)
        green circles
    - Measured peaks, matched to pattern ≥ 1 (extra grains)
        blue diamonds
    - Back-projected predicted positions
        orange "X" markers
        with optional hkl text labels (overlines for negatives)

The figure is plotted in detector-pixel coordinates (Y axis inverted so
pixel (0, 0) is at the top-left, matching detector image convention).
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np
import plotly.graph_objects as go
from plotly.colors import sample_colorscale

from laue_portal.analysis.back_projection import StepOverlay

# Colours chosen to match Igor Pro's ``DisplayResultOfIndexing`` defaults
# (RGB / 65535 in Igor; we use CSS rgb() so they read well in Plotly).
_COLOR_MEASURED_UNINDEXED = "rgb(140, 200, 240)"  # light blue
_COLOR_MATCHED_PATTERN0 = "rgb(0, 170, 0)"  # green
_COLOR_MATCHED_PATTERN1PLUS = "rgb(40, 80, 220)"  # deep blue
_COLOR_PREDICTED = "rgb(214, 19, 0)"  # orange-red (Igor X)
_COLOR_PREDICTED_OFFDETECTOR = "rgba(214, 19, 0, 0.25)"  # faded for off-chip
_COLOR_MISSING = "rgb(130, 45, 210)"

# Pattern colours after the first are cycled for the "matched" markers.
_PATTERN_COLOURS = [
    _COLOR_MATCHED_PATTERN0,
    _COLOR_MATCHED_PATTERN1PLUS,
    "rgb(200, 120, 0)",
    "rgb(160, 0, 180)",
    "rgb(0, 160, 160)",
]

# Unicode combining overline for negative Miller indices.
_OVERLINE = "\u0305"

_IMAGE_COLOR_SCALES = {
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


def _format_hkl(h: int, k: int, l: int) -> str:
    """Format Miller indices with overlines for negatives, like Igor."""
    parts = []
    for v in (h, k, l):
        s = str(abs(int(v)))
        if v < 0:
            s = s + _OVERLINE
        parts.append(s)
    return "(" + " ".join(parts) + ")"


def make_detector_view(
    overlay: Optional[StepOverlay],
    show_predicted: bool = True,
    show_missing: bool = False,
    show_unindexed: bool = True,
    show_hkl_labels: bool = True,
    marker_size: int = 10,
    label_size: int = 10,
    selected_patterns: Optional[List[int]] = None,
    detector_image: Optional[np.ndarray] = None,
    image_visible: bool = True,
    image_colorscale: str = "gray",
    image_vmin: Optional[float] = None,
    image_vmax: Optional[float] = None,
    image_opacity: float = 0.8,
) -> go.Figure:
    """
    Render the detector-pixel overlay for one step.

    Parameters
    ----------
    overlay : StepOverlay | None
        Output of
        :func:`laue_portal.analysis.back_projection.build_step_overlay`.
        ``None`` produces an empty figure with a helpful annotation.
    show_predicted : bool
        Draw the orange "X" markers at each predicted pixel position.
    show_missing : bool
        Draw simulated on-detector reflections not already indexed/matched.
    show_unindexed : bool
        Draw measured peaks that did not match any indexed reflection.
    show_hkl_labels : bool
        Annotate each predicted marker with its ``(h k l)`` string.
    marker_size : int
        Marker diameter in px.
    label_size : int
        hkl label font size in px.
    selected_patterns : list[int] | None
        If supplied, only patterns whose ``pattern_num`` is in this list
        are drawn.  ``None`` shows everything (Igor's default).
    detector_image : ndarray | None
        Optional 2-D detector intensity image shown under the peak overlays.
    image_visible, image_colorscale, image_vmin, image_vmax, image_opacity
        Display controls for the optional detector image.

    Returns
    -------
    plotly.graph_objects.Figure
    """
    fig = go.Figure()

    if overlay is None:
        # Draw an empty 2048x2048 chip outline so the axes have data to
        # autoscale to -- otherwise Plotly picks a default [-1, 6] range
        # and the annotation/legend area looks broken.
        fig.add_trace(
            go.Scatter(
                x=[0, 2048, 2048, 0, 0],
                y=[0, 0, 2048, 2048, 0],
                mode="lines",
                line=dict(color="rgb(190,190,190)", width=1),
                hoverinfo="skip",
                showlegend=False,
                name="Detector chip",
            )
        )
        fig.add_annotation(
            text="No detector data available for this step.",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=14, color="rgb(120,120,120)"),
        )
        _style_detector_axes(fig, nx=2048, ny=2048)
        return fig

    # ── Detector chip background (clip rectangle) ─────────────────────
    x_max = overlay.Nx if overlay.Nx else 2048
    y_max = overlay.Ny if overlay.Ny else 2048
    # If ROI is non-trivial, the measured pixel coords live in the
    # binned/ROI system; show that extent instead.
    if not overlay.roi.is_identity:
        if overlay.roi.endx and overlay.roi.groupx:
            x_max = (overlay.roi.endx - overlay.roi.startx) / overlay.roi.groupx
        if overlay.roi.endy and overlay.roi.groupy:
            y_max = (overlay.roi.endy - overlay.roi.starty) / overlay.roi.groupy

    if detector_image is not None and image_visible:
        img = np.asarray(detector_image, dtype=float)
        image_zmin = float(image_vmin) if image_vmin is not None else float(np.nanmin(img))
        image_zmax = float(image_vmax) if image_vmax is not None else float(np.nanmax(img))
        fig.add_trace(
            go.Heatmap(
                z=img,
                x=np.arange(img.shape[1]),
                y=np.arange(img.shape[0]),
                zmin=image_zmin,
                zmax=image_zmax,
                colorscale=_detector_colorscale(image_colorscale),
                opacity=max(0.0, min(1.0, float(image_opacity))),
                name="Detector image",
                colorbar=dict(title="I", thickness=14, len=0.75),
                hovertemplate="x: %{x}<br>y: %{y}<br>I: %{z:.3g}<extra>image</extra>",
            )
        )

    # Outline the chip with a thin polyline.  Using ``add_shape`` with a
    # filled rect would normally work, but combining shapes with
    # ``scaleanchor`` + ``autorange="reversed"`` has historically caused
    # the Plotly autoscale to ignore the data extent.  A real Scatter
    # trace participates in autoscaling and keeps the visible area sane.
    fig.add_trace(
        go.Scatter(
            x=[0, x_max, x_max, 0, 0],
            y=[0, 0, y_max, y_max, 0],
            mode="lines",
            line=dict(color="rgb(120,120,120)", width=1),
            fill="toself",
            fillcolor="rgba(20,20,20,0.035)",
            hoverinfo="skip",
            showlegend=False,
            name="Detector chip",
        )
    )

    # ── Measured peaks ────────────────────────────────────────────────
    n_meas = len(overlay.measured_xy)
    if n_meas:
        matched_mask = overlay.measured_indexed_mask
        meas_intens = overlay.measured_intensity

        if show_unindexed and np.any(~matched_mask):
            xs = overlay.measured_xy[~matched_mask, 0]
            ys = overlay.measured_xy[~matched_mask, 1]
            ints = meas_intens[~matched_mask] if len(meas_intens) == n_meas else None
            # Use Scatter (SVG) -- a few hundred points at most -- and a
            # transparent fill + coloured stroke so the "open square"
            # look renders consistently across browsers / Plotly versions.
            fig.add_trace(
                go.Scatter(
                    x=xs,
                    y=ys,
                    mode="markers",
                    name=f"Measured, un-indexed ({len(xs)})",
                    marker=dict(
                        size=marker_size,
                        symbol="square",
                        color="rgba(0,0,0,0)",
                        line=dict(width=1.5, color=_COLOR_MEASURED_UNINDEXED),
                    ),
                    customdata=ints.reshape(-1, 1) if ints is not None else None,
                    hovertemplate=(
                        "x: %{x:.2f} px<br>y: %{y:.2f} px"
                        + ("<br>I: %{customdata[0]:.0f}" if ints is not None else "")
                        + "<extra>un-indexed</extra>"
                    ),
                )
            )

    # ── Per-pattern overlays ──────────────────────────────────────────
    # Track which measured peak belongs to which pattern so we can colour
    # the "matched" markers separately.  When a measured peak is matched
    # by more than one pattern (rare) the *first* pattern wins -- same as
    # Igor's loop order.
    measured_pattern = -np.ones(n_meas, dtype=int)
    for pat in overlay.patterns:
        if selected_patterns is not None and pat.pattern_num not in selected_patterns:
            continue
        for k in range(len(pat.predicted_xy)):
            j = int(pat.measured_index[k])
            if j >= 0 and measured_pattern[j] == -1:
                measured_pattern[j] = pat.pattern_num

    for pat in overlay.patterns:
        if selected_patterns is not None and pat.pattern_num not in selected_patterns:
            continue
        colour = _PATTERN_COLOURS[pat.pattern_num % len(_PATTERN_COLOURS)]

        # Matched measured peaks (this pattern)
        mask_pat = measured_pattern == pat.pattern_num
        if np.any(mask_pat):
            xs = overlay.measured_xy[mask_pat, 0]
            ys = overlay.measured_xy[mask_pat, 1]
            fig.add_trace(
                go.Scatter(
                    x=xs,
                    y=ys,
                    mode="markers",
                    name=(f"Measured, indexed (pattern {pat.pattern_num}, {int(mask_pat.sum())})"),
                    marker=dict(
                        size=marker_size + 2,
                        # Filled symbol + transparent fill + coloured stroke
                        # renders the "open" look reliably (avoids the
                        # ``*-open`` symbol variants whose stroke can vanish
                        # at small line widths).
                        symbol="circle" if pat.pattern_num == 0 else "diamond",
                        color="rgba(0,0,0,0)",
                        line=dict(width=2.0, color=colour),
                    ),
                    hovertemplate=(
                        f"pattern {pat.pattern_num}<br>x: %{{x:.2f}} px<br>y: %{{y:.2f}} px<extra>matched</extra>"
                    ),
                )
            )

        # Predicted (back-projected) positions with hkl labels
        if show_predicted and len(pat.predicted_xy):
            px = pat.predicted_xy[:, 0]
            py = pat.predicted_xy[:, 1]
            finite = np.isfinite(px) & np.isfinite(py)

            hkl_labels = [_format_hkl(*hkl) for hkl in pat.hkl] if show_hkl_labels else None
            customdata = np.column_stack([pat.hkl.astype(int), pat.measured_index])

            # On-detector vs off-detector (we still draw both, but off-detector
            # uses a faded colour and is hidden by default).
            on_chip = finite & (px >= 0) & (py >= 0) & (px <= x_max) & (py <= y_max)
            off_chip = finite & ~on_chip

            for sub_mask, sub_color, sub_visible, sub_suffix in (
                (on_chip, _COLOR_PREDICTED, True, "on-detector"),
                (off_chip, _COLOR_PREDICTED_OFFDETECTOR, "legendonly", "off-detector"),
            ):
                if not np.any(sub_mask):
                    continue
                xs = px[sub_mask]
                ys = py[sub_mask]
                cd = customdata[sub_mask]
                texts = [hkl_labels[i] for i in np.where(sub_mask)[0]] if hkl_labels else None
                fig.add_trace(
                    go.Scatter(
                        x=xs,
                        y=ys,
                        mode="markers+text" if (show_hkl_labels and texts) else "markers",
                        name=f"Predicted (pat {pat.pattern_num}, {sub_suffix}, {len(xs)})",
                        visible=sub_visible,
                        text=texts,
                        textposition="top right",
                        textfont=dict(size=label_size, color=sub_color),
                        marker=dict(
                            # ``x-thin-open`` is the slim "+" with diagonal
                            # arms -- a vector stroke instead of the filled
                            # ``x`` glyph, which is solid enough to cover
                            # the matched-peak circles.  We explicitly set
                            # ``line.width`` so the stroke is always visible
                            # (Plotly's default of 0 was the cause of the
                            # earlier "only visible on hover" symptom).
                            size=marker_size + 5,
                            symbol="x-thin-open",
                            color=sub_color,
                            line=dict(width=1.6, color=sub_color),
                        ),
                        customdata=cd,
                        hovertemplate=(
                            f"pattern {pat.pattern_num}<br>"
                            "hkl: (%{customdata[0]} %{customdata[1]} %{customdata[2]})<br>"
                            "x: %{x:.2f} px<br>y: %{y:.2f} px<br>"
                            "PkIndex: %{customdata[3]}"
                            f"<extra>predicted ({sub_suffix})</extra>"
                        ),
                    )
                )

    if show_missing:
        for missing in overlay.missing_spots:
            if selected_patterns is not None and missing.pattern_num not in selected_patterns:
                continue
            if not len(missing.predicted_xy):
                continue
            customdata = np.column_stack([missing.hkl.astype(int), missing.energy_kev])
            texts = [_format_hkl(*hkl) for hkl in missing.hkl] if show_hkl_labels else None
            fig.add_trace(
                go.Scatter(
                    x=missing.predicted_xy[:, 0],
                    y=missing.predicted_xy[:, 1],
                    mode="markers+text" if (show_hkl_labels and texts) else "markers",
                    name=f"Simulated missing (pat {missing.pattern_num}, {len(missing.predicted_xy)})",
                    text=texts,
                    textposition="bottom right",
                    textfont=dict(size=label_size, color=_COLOR_MISSING),
                    marker=dict(
                        size=marker_size + 4,
                        symbol="triangle-up-open",
                        color=_COLOR_MISSING,
                        line=dict(width=1.8, color=_COLOR_MISSING),
                    ),
                    customdata=customdata,
                    hovertemplate=(
                        f"pattern {missing.pattern_num}<br>"
                        "hkl: (%{customdata[0]} %{customdata[1]} %{customdata[2]})<br>"
                        "E: %{customdata[3]:.2f} keV<br>"
                        "x: %{x:.2f} px<br>y: %{y:.2f} px"
                        "<extra>missing</extra>"
                    ),
                )
            )

    _style_detector_axes(fig, nx=x_max, ny=y_max)

    if n_meas == 0 and not overlay.patterns:
        fig.add_annotation(
            text="This step has no measured peaks or indexed patterns.",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=13, color="rgb(120,120,120)"),
        )

    # Optional warning annotations
    if overlay.warnings:
        fig.add_annotation(
            text="<br>".join("\u26a0 " + w for w in overlay.warnings),
            xref="paper",
            yref="paper",
            x=0.01,
            y=0.99,
            xanchor="left",
            yanchor="top",
            showarrow=False,
            align="left",
            font=dict(size=11, color="rgb(190,80,0)"),
            bgcolor="rgba(255,255,200,0.85)",
            bordercolor="rgb(190,80,0)",
            borderwidth=1,
            borderpad=4,
        )

    return fig


def _detector_colorscale(name: str):
    """Return a Plotly colorscale for detector image intensity."""
    scale = _IMAGE_COLOR_SCALES.get(name or "terrain_r", _IMAGE_COLOR_SCALES["terrain_r"])
    if name == "gray_r":
        colors = sample_colorscale("Gray", [i / 255 for i in range(256)])
        return [[i / 255, colors[255 - i]] for i in range(256)]
    return scale


def _style_detector_axes(fig: go.Figure, nx: float, ny: float) -> None:
    """Apply detector-image axis convention: y inverted, equal scale.

    Notes on the configuration choices below
    ----------------------------------------
    - ``autorange="reversed"`` is used instead of ``range=[max, min]``
      because the combination of explicit reversed ``range`` +
      ``scaleanchor`` + ``constrain="domain"`` interacts badly in some
      Plotly versions (the data-area gets clipped down to a fraction
      of the canvas and markers appear "out of bounds" or invisible).
    - ``scaleanchor`` is applied on the X axis (anchored to Y) so that
      Plotly's autorange logic owns the Y extent, which it computes from
      the chip-rectangle trace.  Anchoring the Y axis to X instead gave
      the same clipping behaviour reported by users.
    - Both axes use ``constrain="domain"`` so the equal-aspect ratio is
      maintained by shrinking the *plot area* rather than clipping
      data, which keeps the chip rectangle and all markers fully visible
      regardless of viewport size.
    """
    fig.update_layout(
        xaxis=dict(
            title="X pixel",
            scaleanchor="y",
            scaleratio=1,
            constrain="domain",
            zeroline=False,
            showgrid=False,
        ),
        # autorange="reversed" puts y=0 at the top, matching detector
        # image convention (pixel (0, 0) is the upper-left of the chip).
        yaxis=dict(
            title="Y pixel",
            autorange="reversed",
            constrain="domain",
            zeroline=False,
            showgrid=False,
        ),
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=50, r=20, t=40, b=50),
        autosize=True,
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="top",
            y=0.99,
            xanchor="right",
            x=1.18,
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor="rgb(200,200,200)",
            borderwidth=1,
        ),
        # uirevision is keyed on the detector size so toggling between
        # steps with different chip sizes properly resets the view, but
        # users still keep their zoom/pan within a single chip size.
        uirevision=f"detector-view-{int(nx)}x{int(ny)}",
    )
