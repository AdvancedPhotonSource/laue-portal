"""
Interactive indexed pattern table component using dash-ag-grid.

Displays one row per indexed pattern/grain solution across all steps.
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


def make_pattern_table(patterns: list[dict]) -> html.Div:
    """
    Create an AG Grid table of indexed patterns.

    Parameters
    ----------
    patterns : list[dict]
        Output from xml_parser.get_all_patterns().

    Returns
    -------
    dash html.Div containing the AG Grid.
    """
    default_fields = [
        "step_index",
        "step_scan_num",
        "pattern_num",
        "rank",
        "n_indexed",
        "n_peaks",
        "indexed_fraction",
        "rms_error",
        "goodness",
        "n_patterns",
        "astar",
        "bstar",
        "cstar",
        "structure",
        "space_group",
    ]
    column_defs = [
        _num_col("Step", "step_index", 75),
        _num_col("Scan", "step_scan_num", 95),
        _num_col("Pattern", "pattern_num", 90),
        _num_col("Rank", "rank", 75),
        _num_col("N Indexed", "n_indexed", 105),
        _num_col("N Peaks", "n_peaks", 95),
        _num_col("Indexed %", "indexed_fraction", 110, "d3.format('.1%')(params.value)"),
        _num_col("RMS Error", "rms_error", 105, "d3.format('.5f')(params.value)"),
        _num_col("Goodness", "goodness", 105, "d3.format('.1f')(params.value)"),
        _num_col("N Patterns", "n_patterns", 110),
        _text_col("a*", "astar", 145),
        _text_col("b*", "bstar", 145),
        _text_col("c*", "cstar", 145),
        _text_col("Structure", "structure", 120),
        _num_col("Space Group", "space_group", 110),
        _num_col("X", "x_sample", 95, "d3.format('.3f')(params.value)", hide=True),
        _num_col("Y", "y_sample", 95, "d3.format('.3f')(params.value)", hide=True),
        _num_col("Z", "z_sample", 95, "d3.format('.3f')(params.value)", hide=True),
        _num_col("H", "h_sample", 95, "d3.format('.3f')(params.value)", hide=True),
        _num_col("F", "f_sample", 95, "d3.format('.3f')(params.value)", hide=True),
        _num_col("Depth", "depth", 95, "d3.format('.3f')(params.value)", hide=True),
        _num_col("Energy", "energy", 95, "d3.format('.4f')(params.value)", hide=True),
        _text_col("Input Image", "input_image", 220, hide=True),
        _text_col("Index Program", "index_program", 125, hide=True),
        _num_col("keV Max Calc", "kev_max_calc", 125, "d3.format('.3f')(params.value)", hide=True),
        _num_col("keV Max Test", "kev_max_test", 125, "d3.format('.3f')(params.value)", hide=True),
        _num_col("Angle Tol.", "angle_tolerance", 115, "d3.format('.4f')(params.value)", hide=True),
        _num_col("Cone", "cone", 95, "d3.format('.3f')(params.value)", hide=True),
        _text_col("HKL Prefer", "hkl_prefer", 120, hide=True),
        _num_col("Exec Time", "execution_time", 110, "d3.format('.2f')(params.value)", hide=True),
        _num_col("HKL Count", "hkl_count", 105, hide=True),
        _text_col("Indexed Peak IDs", "indexed_peak_ids", 220, hide=True),
    ]

    grid = dag.AgGrid(
        id="indexed-patterns-grid",
        rowData=patterns,
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
                "Choose which pattern attributes to show.",
                className="text-muted small mb-3",
            ),
            html.Div(
                [
                    html.Div("Default", className="fw-semibold small mb-1"),
                    dbc.Checklist(
                        id="pattern-columns-default",
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
                    html.Div("Position", className="fw-semibold small mb-1"),
                    dbc.Checklist(
                        id="pattern-columns-position",
                        options=[
                            {"label": "X", "value": "x_sample"},
                            {"label": "Y", "value": "y_sample"},
                            {"label": "Z", "value": "z_sample"},
                            {"label": "H", "value": "h_sample"},
                            {"label": "F", "value": "f_sample"},
                            {"label": "Depth", "value": "depth"},
                        ],
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
                        options=[
                            {"label": "Energy", "value": "energy"},
                            {"label": "Input Image", "value": "input_image"},
                            {"label": "Index Program", "value": "index_program"},
                            {"label": "keV Max Calc", "value": "kev_max_calc"},
                            {"label": "keV Max Test", "value": "kev_max_test"},
                            {"label": "Angle Tol.", "value": "angle_tolerance"},
                            {"label": "Cone", "value": "cone"},
                            {"label": "HKL Prefer", "value": "hkl_prefer"},
                            {"label": "Exec Time", "value": "execution_time"},
                        ],
                        value=[],
                        className="small",
                    ),
                ],
                className="mb-3",
            ),
            html.Div(
                [
                    html.Div("Details", className="fw-semibold small mb-1"),
                    dbc.Checklist(
                        id="pattern-columns-detail",
                        options=[
                            {"label": "HKL Count", "value": "hkl_count"},
                            {"label": "Indexed Peak IDs", "value": "indexed_peak_ids"},
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
                f"Indexed Patterns ({len(patterns)} total)",
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
