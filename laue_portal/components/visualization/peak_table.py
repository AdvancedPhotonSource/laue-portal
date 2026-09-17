"""Indexed-peak table: lauelab ``indexed_peak_table`` rows in the portal's AG Grid.

Row identity is ``frame_id``, ``pattern_index``, ``peak_index``. Peak-search
settings that the old XML repeated on every row (peak shape, box size, widths,
separation) are run parameters and live on the Parameters tab.
"""

from __future__ import annotations

import dash_ag_grid as dag
import dash_bootstrap_components as dbc
import numpy as np
from dash import html
from lauelab.visualization import DataScope, VisualizationDataset, indexed_peak_table

from laue_portal.components.visualization.pattern_table import _json_identity, _num_col, _number, _text_col


def peak_rows(dataset: VisualizationDataset, scope: DataScope) -> list[dict]:
    """Rows for the grid: one per selected pattern-to-peak assignment."""

    table = indexed_peak_table(dataset, scope=scope)
    positions = {frame_id: index for index, frame_id in enumerate(dataset.frame_ids)}
    frame_ids = table["frame_id"]
    steps = np.fromiter((positions[frame_id] for frame_id in frame_ids), dtype=int, count=len(frame_ids))
    qhat = np.column_stack([table["qhat_x"], table["qhat_y"], table["qhat_z"]]) if "qhat_x" in table.columns else None
    rows = []
    for index in range(len(table)):
        n_peaks = int(dataset.frame_n_peaks[steps[index]])
        pattern_n_indexed = int(table["pattern_n_indexed"][index])
        row = {
            "step": int(steps[index]),
            "frame_id": _json_identity(frame_ids[index]),
            "pattern_index": int(table["pattern_index"][index]),
            "h": int(table["h"][index]),
            "k": int(table["k"][index]),
            "l": int(table["l"][index]),
            "peak_index": int(table["peak_index"][index]),
            "x_pixel": _number(table["fit_x"][index]),
            "y_pixel": _number(table["fit_y"][index]),
            "intensity": _number(table["intens"][index]),
            "integral": _number(table["integral"][index]),
            "qx": None if qhat is None else _number(qhat[index, 0]),
            "qy": None if qhat is None else _number(qhat[index, 1]),
            "qz": None if qhat is None else _number(qhat[index, 2]),
            "rms_error_deg": _number(table["rms_error_deg"][index]),
            "goodness": _number(table["goodness"][index]),
            "n_peaks": n_peaks,
            "energy_kev": _number(table["energy_kev"][index]),
            "error_deg": _number(table["error_deg"][index]),
            "predicted_intensity": _number(table["predicted_intensity"][index]),
            "input_image": dataset.input_images[steps[index]],
            "hwhm_x": _number(table["hwhm_x"][index]),
            "hwhm_y": _number(table["hwhm_y"][index]),
            "tilt": _number(table["tilt"][index]),
            "chisq": _number(table["chisq"][index]),
            "background": _number(table["background"][index]),
            "pattern_n_indexed": pattern_n_indexed,
            "pattern_indexed_fraction": (pattern_n_indexed / n_peaks) if n_peaks else None,
        }
        rows.append(row)
    return rows


DEFAULT_FIELDS = [
    "step",
    "pattern_index",
    "h",
    "k",
    "l",
    "peak_index",
    "x_pixel",
    "y_pixel",
    "intensity",
    "integral",
    "qx",
    "qy",
    "qz",
    "rms_error_deg",
    "goodness",
]

COLUMN_DEFS = [
    _num_col("Step", "step", 70),
    _text_col("Frame", "frame_id", 130, hide=True),
    _num_col("Pattern", "pattern_index", 85),
    _num_col("h", "h", 60),
    _num_col("k", "k", 60),
    _num_col("l", "l", 60),
    _num_col("Peak #", "peak_index", 75),
    _num_col("X pixel", "x_pixel", 90, "d3.format('.1f')(params.value)"),
    _num_col("Y pixel", "y_pixel", 90, "d3.format('.1f')(params.value)"),
    _num_col("Intensity", "intensity", 100, "d3.format('.0f')(params.value)"),
    _num_col("Integral", "integral", 95, "d3.format('.1f')(params.value)"),
    _num_col("Qx", "qx", 90, "d3.format('.4f')(params.value)"),
    _num_col("Qy", "qy", 90, "d3.format('.4f')(params.value)"),
    _num_col("Qz", "qz", 90, "d3.format('.4f')(params.value)"),
    _num_col("RMS Error", "rms_error_deg", 100, "d3.format('.5f')(params.value)"),
    _num_col("Goodness", "goodness", 100, "d3.format('.1f')(params.value)"),
    _num_col("N Peaks", "n_peaks", 95, hide=True),
    _num_col("Energy", "energy_kev", 95, "d3.format('.4f')(params.value)", hide=True),
    _num_col("Error", "error_deg", 95, "d3.format('.4f')(params.value)", hide=True),
    _num_col("Pred. Intensity", "predicted_intensity", 125, "d3.format('.3f')(params.value)", hide=True),
    _text_col("Input Image", "input_image", 220, hide=True),
    _num_col("hwhmX", "hwhm_x", 95, "d3.format('.3f')(params.value)", hide=True),
    _num_col("hwhmY", "hwhm_y", 95, "d3.format('.3f')(params.value)", hide=True),
    _num_col("Tilt", "tilt", 95, "d3.format('.2f')(params.value)", hide=True),
    _num_col("ChiSq", "chisq", 95, "d3.format('.5f')(params.value)", hide=True),
    _num_col("Background", "background", 105, "d3.format('.1f')(params.value)", hide=True),
    _num_col("Pattern N Indexed", "pattern_n_indexed", 145, hide=True),
    _num_col("Pattern Indexed %", "pattern_indexed_fraction", 150, "d3.format('.1%')(params.value)", hide=True),
]

GEOMETRY_FIELDS = [
    ("Frame", "frame_id"),
    ("N Peaks", "n_peaks"),
    ("Energy", "energy_kev"),
    ("Error", "error_deg"),
    ("Pred. Intensity", "predicted_intensity"),
    ("Input Image", "input_image"),
]
FIT_FIELDS = [
    ("hwhmX", "hwhm_x"),
    ("hwhmY", "hwhm_y"),
    ("Tilt", "tilt"),
    ("ChiSq", "chisq"),
    ("Background", "background"),
]
INDEXING_FIELDS = [("Pattern N Indexed", "pattern_n_indexed"), ("Pattern Indexed %", "pattern_indexed_fraction")]


def make_peak_table(rows: list[dict]) -> html.Div:
    """Create the AG Grid of indexed peaks from :func:`peak_rows`."""

    column_defs = [dict(col) for col in COLUMN_DEFS]
    grid = dag.AgGrid(
        id="indexed-peaks-grid",
        rowData=rows,
        columnDefs=column_defs,
        getRowId="params.data.frame_id + ':' + params.data.pattern_index + ':' + params.data.peak_index",
        defaultColDef={"resizable": True, "sortable": True, "filter": True},
        dashGridOptions={"pagination": True, "paginationPageSize": 50, "animateRows": True, "rowSelection": "single"},
        style={"height": "calc(100vh - 260px)", "minHeight": "400px", "width": "100%"},
        className="ag-theme-alpine",
    )

    def group(title, checklist_id, fields, default):
        return html.Div(
            [
                html.Div(title, className="fw-semibold small mb-1"),
                dbc.Checklist(
                    id=checklist_id,
                    options=[{"label": label, "value": field} for label, field in fields],
                    value=default,
                    className="small",
                ),
            ],
            className="mb-3",
        )

    selector = html.Div(
        [
            html.H6("Columns", className="mb-2"),
            html.Div("Choose which peak attributes to show.", className="text-muted small mb-3"),
            group(
                "Default",
                "peak-columns-default",
                [(col["headerName"], col["field"]) for col in column_defs if col["field"] in DEFAULT_FIELDS],
                list(DEFAULT_FIELDS),
            ),
            group("Geometry", "peak-columns-geometry", GEOMETRY_FIELDS, []),
            group("Fit Quality", "peak-columns-fit", FIT_FIELDS, []),
            group("Indexing", "peak-columns-indexing", INDEXING_FIELDS, []),
        ],
        className="border rounded bg-light p-3",
        style={"width": "230px", "flex": "0 0 230px", "maxHeight": "calc(100vh - 230px)", "overflowY": "auto"},
    )
    return html.Div(
        [
            html.H5(f"Indexed Peaks ({len(rows)} total)", className="mt-3 mb-2"),
            html.Div(
                [selector, html.Div(grid, style={"minWidth": 0, "flex": "1 1 auto"})],
                className="d-flex gap-3 align-items-start",
            ),
        ]
    )
