"""
Interactive indexed peak table component using dash-ag-grid.

Displays all indexed peaks across all steps and patterns in a
sortable, filterable grid.
"""

import dash_ag_grid as dag
import dash_bootstrap_components as dbc
from dash import html


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


def make_peak_table(indexed_peaks: list[dict]) -> html.Div:
    """
    Create an AG Grid table of indexed peaks.

    Parameters
    ----------
    indexed_peaks : list[dict]
        Output from xml_parser.get_all_indexed_peaks().

    Returns
    -------
    dash html.Div containing the AG Grid.
    """
    default_fields = [
        "step_index",
        "pattern_num",
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
        "rms_error",
        "goodness",
    ]
    column_defs = [
        _num_col("Step", "step_index", 70),
        _num_col("Pattern", "pattern_num", 85),
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
        _num_col("RMS Error", "rms_error", 100, "d3.format('.5f')(params.value)"),
        _num_col("Goodness", "goodness", 100, "d3.format('.1f')(params.value)"),
        _num_col("N Peaks", "n_peaks", 95, hide=True),
        _num_col("Energy", "energy", 95, "d3.format('.4f')(params.value)", hide=True),
        _num_col("Q Magnitude", "q_magnitude", 120, "d3.format('.5f')(params.value)", hide=True),
        _text_col("Input Image", "input_image", 220, hide=True),
        _num_col("hwhmX", "hwhm_x", 95, "d3.format('.3f')(params.value)", hide=True),
        _num_col("hwhmY", "hwhm_y", 95, "d3.format('.3f')(params.value)", hide=True),
        _num_col("Aspect Ratio", "aspect_ratio", 120, "d3.format('.3f')(params.value)", hide=True),
        _num_col("Tilt", "tilt", 95, "d3.format('.2f')(params.value)", hide=True),
        _num_col("ChiSq", "chisq", 95, "d3.format('.5f')(params.value)", hide=True),
        _text_col("Peak Shape", "peak_shape", 115, hide=True),
        _num_col("Box Size", "boxsize", 95, "d3.format('.0f')(params.value)", hide=True),
        _num_col("Min Width", "min_width", 100, "d3.format('.3f')(params.value)", hide=True),
        _num_col("Max Width", "max_width", 100, "d3.format('.3f')(params.value)", hide=True),
        _num_col("Min Separation", "min_separation", 125, "d3.format('.1f')(params.value)", hide=True),
        _num_col("Pattern N Indexed", "pattern_n_indexed", 145, hide=True),
        _num_col("Pattern Indexed %", "pattern_indexed_fraction", 150, "d3.format('.1%')(params.value)", hide=True),
    ]

    grid = dag.AgGrid(
        id="indexed-peaks-grid",
        rowData=indexed_peaks,
        columnDefs=column_defs,
        defaultColDef={
            "resizable": True,
            "sortable": True,
            "filter": True,
        },
        dashGridOptions={
            "pagination": True,
            "paginationPageSize": 50,
            "animateRows": True,
            "rowSelection": "single",
        },
        style={"height": "calc(100vh - 260px)", "minHeight": "400px", "width": "100%"},
        className="ag-theme-alpine",
    )

    selector = html.Div(
        [
            html.H6("Columns", className="mb-2"),
            html.Div(
                "Choose which peak attributes to show.",
                className="text-muted small mb-3",
            ),
            html.Div(
                [
                    html.Div("Default", className="fw-semibold small mb-1"),
                    dbc.Checklist(
                        id="peak-columns-default",
                        options=[
                            {"label": col["headerName"], "value": col["field"]}
                            for col in column_defs
                            if col["field"] in default_fields
                        ],
                        value=default_fields,
                        className="small",
                    ),
                ],
                className="mb-3",
            ),
            html.Div(
                [
                    html.Div("Geometry", className="fw-semibold small mb-1"),
                    dbc.Checklist(
                        id="peak-columns-geometry",
                        options=[
                            {"label": "N Peaks", "value": "n_peaks"},
                            {"label": "Energy", "value": "energy"},
                            {"label": "Q Magnitude", "value": "q_magnitude"},
                            {"label": "Input Image", "value": "input_image"},
                        ],
                        value=[],
                        className="small",
                    ),
                ],
                className="mb-3",
            ),
            html.Div(
                [
                    html.Div("Fit Quality", className="fw-semibold small mb-1"),
                    dbc.Checklist(
                        id="peak-columns-fit",
                        options=[
                            {"label": "hwhmX", "value": "hwhm_x"},
                            {"label": "hwhmY", "value": "hwhm_y"},
                            {"label": "Aspect Ratio", "value": "aspect_ratio"},
                            {"label": "Tilt", "value": "tilt"},
                            {"label": "ChiSq", "value": "chisq"},
                        ],
                        value=[],
                        className="small",
                    ),
                ],
                className="mb-3",
            ),
            html.Div(
                [
                    html.Div("Peak Search", className="fw-semibold small mb-1"),
                    dbc.Checklist(
                        id="peak-columns-search",
                        options=[
                            {"label": "Peak Shape", "value": "peak_shape"},
                            {"label": "Box Size", "value": "boxsize"},
                            {"label": "Min Width", "value": "min_width"},
                            {"label": "Max Width", "value": "max_width"},
                            {"label": "Min Separation", "value": "min_separation"},
                        ],
                        value=[],
                        className="small",
                    ),
                ],
                className="mb-3",
            ),
            html.Div(
                [
                    html.Div("Indexing", className="fw-semibold small mb-1"),
                    dbc.Checklist(
                        id="peak-columns-indexing",
                        options=[
                            {"label": "Pattern N Indexed", "value": "pattern_n_indexed"},
                            {"label": "Pattern Indexed %", "value": "pattern_indexed_fraction"},
                        ],
                        value=[],
                        className="small",
                    ),
                ],
            ),
        ],
        className="border rounded bg-light p-3",
        style={"width": "230px", "flex": "0 0 230px", "maxHeight": "calc(100vh - 230px)", "overflowY": "auto"},
    )

    return html.Div(
        [
            html.H5(
                f"Indexed Peaks ({len(indexed_peaks)} total)",
                className="mt-3 mb-2",
            ),
            html.Div(
                [
                    selector,
                    html.Div(grid, style={"minWidth": 0, "flex": "1 1 auto"}),
                ],
                className="d-flex gap-3 align-items-start",
            ),
        ]
    )
