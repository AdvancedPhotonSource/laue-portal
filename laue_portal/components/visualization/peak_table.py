"""
Interactive indexed peak table component using dash-ag-grid.

Displays all indexed peaks across all steps and patterns in a
sortable, filterable grid.
"""

import dash_ag_grid as dag
from dash import html


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
    column_defs = [
        {
            "headerName": "Step",
            "field": "step_index",
            "width": 70,
            "filter": "agNumberColumnFilter",
            "sortable": True,
        },
        {
            "headerName": "Pattern",
            "field": "pattern_num",
            "width": 85,
            "filter": "agNumberColumnFilter",
            "sortable": True,
        },
        {
            "headerName": "h",
            "field": "h",
            "width": 60,
            "filter": "agNumberColumnFilter",
            "sortable": True,
        },
        {
            "headerName": "k",
            "field": "k",
            "width": 60,
            "filter": "agNumberColumnFilter",
            "sortable": True,
        },
        {
            "headerName": "l",
            "field": "l",
            "width": 60,
            "filter": "agNumberColumnFilter",
            "sortable": True,
        },
        {
            "headerName": "Peak #",
            "field": "peak_index",
            "width": 75,
            "filter": "agNumberColumnFilter",
            "sortable": True,
        },
        {
            "headerName": "X pixel",
            "field": "x_pixel",
            "width": 90,
            "filter": "agNumberColumnFilter",
            "sortable": True,
            "valueFormatter": {"function": "d3.format('.1f')(params.value)"},
        },
        {
            "headerName": "Y pixel",
            "field": "y_pixel",
            "width": 90,
            "filter": "agNumberColumnFilter",
            "sortable": True,
            "valueFormatter": {"function": "d3.format('.1f')(params.value)"},
        },
        {
            "headerName": "Intensity",
            "field": "intensity",
            "width": 100,
            "filter": "agNumberColumnFilter",
            "sortable": True,
            "valueFormatter": {"function": "d3.format('.0f')(params.value)"},
        },
        {
            "headerName": "Integral",
            "field": "integral",
            "width": 95,
            "filter": "agNumberColumnFilter",
            "sortable": True,
            "valueFormatter": {"function": "d3.format('.1f')(params.value)"},
        },
        {
            "headerName": "Qx",
            "field": "qx",
            "width": 90,
            "filter": "agNumberColumnFilter",
            "sortable": True,
            "valueFormatter": {"function": "d3.format('.4f')(params.value)"},
        },
        {
            "headerName": "Qy",
            "field": "qy",
            "width": 90,
            "filter": "agNumberColumnFilter",
            "sortable": True,
            "valueFormatter": {"function": "d3.format('.4f')(params.value)"},
        },
        {
            "headerName": "Qz",
            "field": "qz",
            "width": 90,
            "filter": "agNumberColumnFilter",
            "sortable": True,
            "valueFormatter": {"function": "d3.format('.4f')(params.value)"},
        },
        {
            "headerName": "RMS Error",
            "field": "rms_error",
            "width": 100,
            "filter": "agNumberColumnFilter",
            "sortable": True,
            "valueFormatter": {"function": "d3.format('.5f')(params.value)"},
        },
        {
            "headerName": "Goodness",
            "field": "goodness",
            "width": 100,
            "filter": "agNumberColumnFilter",
            "sortable": True,
            "valueFormatter": {"function": "d3.format('.1f')(params.value)"},
        },
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
        style={"height": "400px", "width": "100%"},
        className="ag-theme-alpine",
    )

    return html.Div([
        html.H5(
            f"Indexed Peaks ({len(indexed_peaks)} total)",
            className="mt-3 mb-2",
        ),
        grid,
    ])
