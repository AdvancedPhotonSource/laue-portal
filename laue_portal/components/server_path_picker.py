"""Reusable server-side file and directory picker for Dash pages."""

import dash
import dash_ag_grid as dag
import dash_bootstrap_components as dbc
from dash import Input, Output, State, dcc, html
from dash.exceptions import PreventUpdate

from laue_portal.services.filesystem_browser import list_directory, normalize_path, validate_selection


def server_path_picker(
    picker_id,
    default_path,
    *,
    mode="file",
    extensions=None,
    max_file_size_mb=None,
    title="Browse Server",
):
    """Create a server path picker and a store containing its confirmed selection."""
    return html.Div(
        [
            dcc.Store(id=f"{picker_id}-selection"),
            dbc.Button(
                [html.I(className="bi bi-folder2-open me-2"), title],
                id=f"{picker_id}-open",
                color="secondary",
                size="lg",
            ),
            dbc.Modal(
                [
                    dbc.ModalHeader(dbc.ModalTitle(title), close_button=True),
                    dbc.ModalBody(
                        [
                            dbc.InputGroup(
                                [
                                    dbc.Input(id=f"{picker_id}-path", value=default_path, debounce=True),
                                    dbc.Button("Up", id=f"{picker_id}-up", color="secondary", outline=True),
                                    dbc.Button("Go", id=f"{picker_id}-go", color="primary", outline=True),
                                ],
                                className="mb-3",
                            ),
                            dbc.Alert(id=f"{picker_id}-alert", is_open=False, color="danger", className="py-2"),
                            dag.AgGrid(
                                id=f"{picker_id}-grid",
                                columnDefs=[
                                    {
                                        "headerName": "",
                                        "field": "type",
                                        "width": 46,
                                        "sortable": False,
                                        "resizable": False,
                                        "valueFormatter": {"function": "''"},
                                        "cellClassRules": {
                                            "bi bi-folder-fill text-warning": "params.data.type === 'Directory'",
                                            "bi bi-file-earmark-code text-primary": "params.data.type === 'File'",
                                        },
                                    },
                                    {
                                        "field": "name",
                                        "headerName": "Name",
                                        "flex": 1,
                                    },
                                    {"field": "type", "headerName": "Type", "width": 115},
                                    {
                                        "field": "size",
                                        "headerName": "Size (bytes)",
                                        "width": 130,
                                        "valueFormatter": {
                                            "function": "params.value == null ? '' : params.value.toLocaleString()"
                                        },
                                    },
                                    {"field": "modified", "headerName": "Modified", "width": 175},
                                ],
                                rowData=[],
                                defaultColDef={"sortable": True, "resizable": True},
                                dashGridOptions={
                                    "rowSelection": "single",
                                    "animateRows": False,
                                    "pagination": True,
                                    "paginationPageSize": 20,
                                },
                                style={"height": "55vh", "width": "100%"},
                                className="ag-theme-alpine",
                                getRowId="params.data.path",
                            ),
                            html.Div(
                                "Double-click a folder to open it, or select a file and click Open File.",
                                id=f"{picker_id}-help",
                                className="small text-muted mt-2",
                            ),
                        ]
                    ),
                    dbc.ModalFooter(
                        [
                            dbc.Button("Cancel", id=f"{picker_id}-cancel", color="secondary", outline=True),
                            dbc.Button("Open File", id=f"{picker_id}-select", color="primary", disabled=True),
                        ]
                    ),
                ],
                id=f"{picker_id}-modal",
                is_open=False,
                size="xl",
                centered=True,
                scrollable=True,
            ),
        ]
    )


def register_server_path_picker_callbacks(
    picker_id,
    default_path,
    *,
    mode="file",
    extensions=None,
    max_file_size_mb=None,
):
    """Register callbacks for one server path picker instance."""
    extensions = list(extensions or [])

    def browse(path):
        try:
            current_path, entries, truncated = list_directory(path, extensions)
            message = "Only the first 1,000 entries are shown." if truncated else ""
            return current_path, entries, bool(message), message
        except (OSError, ValueError) as exc:
            return str(path or ""), [], True, str(exc)

    @dash.callback(
        Output(f"{picker_id}-modal", "is_open"),
        Output(f"{picker_id}-path", "value"),
        Output(f"{picker_id}-grid", "rowData"),
        Output(f"{picker_id}-grid", "selectedRows"),
        Output(f"{picker_id}-alert", "is_open"),
        Output(f"{picker_id}-alert", "children"),
        Input(f"{picker_id}-open", "n_clicks"),
        State(f"{picker_id}-path", "value"),
        prevent_initial_call=True,
    )
    def open_picker(n_clicks, path):
        if not n_clicks:
            raise PreventUpdate
        current_path, entries, has_message, message = browse(path or default_path)
        return True, current_path, entries, [], has_message, message

    @dash.callback(
        Output(f"{picker_id}-path", "value", allow_duplicate=True),
        Output(f"{picker_id}-grid", "rowData", allow_duplicate=True),
        Output(f"{picker_id}-grid", "selectedRows", allow_duplicate=True),
        Output(f"{picker_id}-alert", "is_open", allow_duplicate=True),
        Output(f"{picker_id}-alert", "children", allow_duplicate=True),
        Input(f"{picker_id}-go", "n_clicks"),
        Input(f"{picker_id}-up", "n_clicks"),
        Input(f"{picker_id}-grid", "cellDoubleClicked"),
        State(f"{picker_id}-path", "value"),
        State(f"{picker_id}-grid", "rowData"),
        prevent_initial_call=True,
    )
    def navigate(go_clicks, up_clicks, double_clicked, current_path, row_data):
        from dash import ctx

        if ctx.triggered_id == f"{picker_id}-up":
            try:
                target = str(normalize_path(current_path).parent)
            except ValueError:
                target = default_path
        elif ctx.triggered_id == f"{picker_id}-grid":
            row_id = str((double_clicked or {}).get("rowId", ""))
            row = next((item for item in row_data or [] if str(item.get("path")) == row_id), None)
            if not row or row.get("type") != "Directory":
                raise PreventUpdate
            target = row["path"]
        else:
            target = current_path

        path, entries, has_message, message = browse(target)
        return path, entries, [], has_message, message

    @dash.callback(
        Output(f"{picker_id}-select", "disabled"),
        Output(f"{picker_id}-select", "children"),
        Input(f"{picker_id}-grid", "selectedRows"),
        Input(f"{picker_id}-path", "value"),
    )
    def update_select_button(selected_rows, current_path):
        if mode == "directory":
            return False, "Select Folder"
        is_file = bool(selected_rows and selected_rows[0].get("type") == "File")
        return not is_file, "Open File"

    @dash.callback(
        Output(f"{picker_id}-selection", "data"),
        Output(f"{picker_id}-modal", "is_open", allow_duplicate=True),
        Output(f"{picker_id}-alert", "is_open", allow_duplicate=True),
        Output(f"{picker_id}-alert", "children", allow_duplicate=True),
        Input(f"{picker_id}-select", "n_clicks"),
        State(f"{picker_id}-grid", "selectedRows"),
        State(f"{picker_id}-path", "value"),
        prevent_initial_call=True,
    )
    def select_path(n_clicks, selected_rows, current_path):
        if not n_clicks:
            raise PreventUpdate
        candidate = current_path if mode == "directory" else (selected_rows or [{}])[0].get("path")
        try:
            selected = validate_selection(
                candidate,
                mode=mode,
                extensions=extensions,
                max_file_size_mb=max_file_size_mb,
            )
        except (OSError, ValueError) as exc:
            return None, True, True, str(exc)
        return {"path": selected, "selection_id": n_clicks}, False, False, ""

    @dash.callback(
        Output(f"{picker_id}-modal", "is_open", allow_duplicate=True),
        Input(f"{picker_id}-cancel", "n_clicks"),
        prevent_initial_call=True,
    )
    def cancel_picker(n_clicks):
        if not n_clicks:
            raise PreventUpdate
        return False
