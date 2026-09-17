"""Indexed-pattern table: lauelab ``pattern_table`` rows in the portal's AG Grid.

Row identity is ``frame_id`` plus ``pattern_index``; ``step`` is the frame
position for readers used to step numbers. Run-level parameters that were
repeated on every row of the old XML table (indexing program, energy limits,
angle tolerance, cone, preferred HKL, execution time) live on the Parameters tab.
"""

from __future__ import annotations

import dash_ag_grid as dag
import dash_bootstrap_components as dbc
import numpy as np
from dash import html
from lauelab.visualization import DataScope, VisualizationDataset, pattern_table


def _num_col(header, field, width=100, formatter=None, hide=False):
    col = {
        "headerName": header,
        "field": field,
        "width": width,
        "filter": "agNumberColumnFilter",
        "sortable": True,
        "hide": hide,
    }
    if formatter:
        col["valueFormatter"] = {"function": formatter}
    return col


def _text_col(header, field, width=130, hide=False):
    return {
        "headerName": header,
        "field": field,
        "width": width,
        "filter": "agTextColumnFilter",
        "sortable": True,
        "hide": hide,
    }


def _vector_text(values: np.ndarray) -> str:
    return " ".join(f"{value:.6g}" for value in values)


def pattern_rows(dataset: VisualizationDataset, scope: DataScope) -> list[dict]:
    """Rows for the grid: one per selected pattern, with stable identities and step positions."""

    table = pattern_table(dataset, scope=scope)
    positions = {frame_id: index for index, frame_id in enumerate(dataset.frame_ids)}
    frame_ids = table["frame_id"]
    n_frames_patterns = np.bincount(dataset.pattern_frame_indices, minlength=dataset.n_frames)
    steps = np.fromiter((positions[frame_id] for frame_id in frame_ids), dtype=int, count=len(frame_ids))
    reciprocal = np.stack(
        [np.stack([table[f"reciprocal_{row}{col}"] for col in range(3)], axis=1) for row in range(3)], axis=1
    )
    structure = dataset.crystal.name if dataset.crystal is not None else None
    space_group = dataset.crystal.space_group if dataset.crystal is not None else None
    rows = []
    for index in range(len(table)):
        rows.append(
            {
                "step": int(steps[index]),
                "frame_id": _json_identity(frame_ids[index]),
                "scan_number": _number(table["scan_number"][index]),
                "pattern_index": int(table["pattern_index"][index]),
                "n_indexed": int(table["n_indexed"][index]),
                "n_peaks": int(dataset.frame_n_peaks[steps[index]]),
                "indexed_fraction": _number(table["indexed_fraction"][index]),
                "rms_error_deg": _number(table["rms_error_deg"][index]),
                "goodness": _number(table["goodness"][index]),
                "n_patterns": int(n_frames_patterns[steps[index]]),
                "astar": _vector_text(reciprocal[index, 0]),
                "bstar": _vector_text(reciprocal[index, 1]),
                "cstar": _vector_text(reciprocal[index, 2]),
                "structure": structure,
                "space_group": space_group,
                "x_um": _number(table["x_um"][index]),
                "y_um": _number(table["y_um"][index]),
                "z_um": _number(table["z_um"][index]),
                "depth_um": _number(table["depth_um"][index]),
                "frame_energy_kev": _number(table["frame_energy_kev"][index]),
                "input_image": dataset.input_images[steps[index]],
            }
        )
    return rows


def _number(value):
    value = float(value)
    return None if not np.isfinite(value) else value


def _json_identity(value):
    return int(value) if isinstance(value, (np.integer, int)) else str(value)


DEFAULT_FIELDS = [
    "step",
    "frame_id",
    "scan_number",
    "pattern_index",
    "n_indexed",
    "n_peaks",
    "indexed_fraction",
    "rms_error_deg",
    "goodness",
    "n_patterns",
    "astar",
    "bstar",
    "cstar",
    "structure",
    "space_group",
]

COLUMN_DEFS = [
    _num_col("Step", "step", 75),
    _text_col("Frame", "frame_id", 130),
    _num_col("Scan", "scan_number", 95),
    _num_col("Pattern", "pattern_index", 90),
    _num_col("N Indexed", "n_indexed", 105),
    _num_col("N Peaks", "n_peaks", 95),
    _num_col("Indexed %", "indexed_fraction", 110, "d3.format('.1%')(params.value)"),
    _num_col("RMS Error", "rms_error_deg", 105, "d3.format('.5f')(params.value)"),
    _num_col("Goodness", "goodness", 105, "d3.format('.1f')(params.value)"),
    _num_col("N Patterns", "n_patterns", 110),
    _text_col("a*", "astar", 145),
    _text_col("b*", "bstar", 145),
    _text_col("c*", "cstar", 145),
    _text_col("Structure", "structure", 120),
    _num_col("Space Group", "space_group", 110),
    _num_col("X motor", "x_um", 95, "d3.format('.3f')(params.value)", hide=True),
    _num_col("Y motor", "y_um", 95, "d3.format('.3f')(params.value)", hide=True),
    _num_col("Z motor", "z_um", 95, "d3.format('.3f')(params.value)", hide=True),
    _num_col("Depth", "depth_um", 95, "d3.format('.3f')(params.value)", hide=True),
    _num_col("Energy", "frame_energy_kev", 95, "d3.format('.4f')(params.value)", hide=True),
    _text_col("Input Image", "input_image", 220, hide=True),
]

POSITION_FIELDS = [("X motor", "x_um"), ("Y motor", "y_um"), ("Z motor", "z_um"), ("Depth", "depth_um")]
RUN_FIELDS = [("Energy", "frame_energy_kev"), ("Input Image", "input_image")]


def make_pattern_table(rows: list[dict]) -> html.Div:
    """Create the AG Grid of indexed patterns from :func:`pattern_rows`."""

    column_defs = [dict(col) for col in COLUMN_DEFS]
    grid = dag.AgGrid(
        id="indexed-patterns-grid",
        rowData=rows,
        columnDefs=column_defs,
        getRowId="params.data.frame_id + ':' + params.data.pattern_index",
        defaultColDef={"resizable": True, "sortable": True, "filter": True},
        dashGridOptions={"pagination": True, "paginationPageSize": 50, "animateRows": True, "rowSelection": "single"},
        style={"height": "calc(100vh - 260px)", "minHeight": "400px", "width": "100%"},
        className="ag-theme-alpine",
    )
    selector = html.Div(
        [
            html.H6("Columns", className="mb-2"),
            html.Div("Choose which pattern attributes to show.", className="text-muted small mb-3"),
            html.Div(
                [
                    html.Div("Default", className="fw-semibold small mb-1"),
                    dbc.Checklist(
                        id="pattern-columns-default",
                        options=[
                            {"label": col["headerName"], "value": col["field"]}
                            for col in column_defs
                            if col["field"] in DEFAULT_FIELDS
                        ],
                        value=list(DEFAULT_FIELDS),
                        className="small",
                    ),
                ],
                className="mb-3",
            ),
            html.Div(
                [
                    html.Div("Position", className="fw-semibold small mb-1"),
                    dbc.Checklist(
                        id="pattern-columns-position",
                        options=[{"label": label, "value": field} for label, field in POSITION_FIELDS],
                        value=[],
                        className="small",
                    ),
                ],
                className="mb-3",
            ),
            html.Div(
                [
                    html.Div("Run", className="fw-semibold small mb-1"),
                    dbc.Checklist(
                        id="pattern-columns-run",
                        options=[{"label": label, "value": field} for label, field in RUN_FIELDS],
                        value=[],
                        className="small",
                    ),
                ],
                className="mb-3",
            ),
        ],
        className="border rounded bg-light p-3",
        style={"width": "230px", "flex": "0 0 230px", "maxHeight": "calc(100vh - 230px)", "overflowY": "auto"},
    )
    return html.Div(
        [
            html.H5(f"Indexed Patterns ({len(rows)} total)", className="mt-3 mb-2"),
            html.Div(
                [selector, html.Div(grid, style={"minWidth": 0, "flex": "1 1 auto"})],
                className="d-flex gap-3 align-items-start",
            ),
        ]
    )
