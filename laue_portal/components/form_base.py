import dash_bootstrap_components as dbc
from dash import html


def _stack(objects,gap=3):
    return dbc.Stack(
        objects, 
        direction="horizontal",
        gap=gap#3
    )

def _field(label, field_id, size='', kwargs={}):
    if size == 'sm':
        width='200px'
    elif size == 'md':
        width='350px'
    elif size == 'lg':
        width='500px'

    if size:
        return dbc.InputGroup(
            [
                dbc.InputGroupText(label),
                dbc.Input(id=field_id, **kwargs),
            ],
            style={'width': width},
            className="mb-3",
        )
    else:
        return dbc.InputGroup(
            [
                dbc.InputGroupText(label),
                dbc.Input(id=field_id, **kwargs),
            ],
            className="mb-3 w-100",
        )

def _select(label, field_id, select_options, size='', kwargs={}):
    if size == 'sm':
        width='200px'
    elif size == 'md':
        width='350px'
    elif size == 'lg':
        width='500px'

    if size:
        return dbc.InputGroup(
            [
                dbc.InputGroupText(label),
                dbc.Select(
                    options=select_options,
                    id=field_id, **kwargs,
                ),
            ],
            style={'width': width},
            className="mb-3",
        )
    else:
        return dbc.InputGroup(
            [
                dbc.InputGroupText(label),
                dbc.Select(
                    options=select_options,
                    id=field_id, **kwargs,
                ),
            ],
            className="mb-3 w-100",
        )

def _ckbx(label, field_id, size='', kwargs={}):
    if size == 'sm':
        width='200px'
    elif size == 'md':
        width='350px'
    elif size == 'lg':
        width='500px'

    if size:
        return dbc.Checkbox(id=field_id, 
                            label=label,
                            style={'width': width},
                            className="mb-3",
                            **kwargs)
    else:
        return dbc.Checkbox(id=field_id, 
                        label=label,
                        className="mb-3 w-100",
                        **kwargs)

def _notes(field_id, kwargs={}):
    return dbc.Row(
        [
            dbc.Col(
                html.P(html.Strong("Notes:")),
                width="auto", align="start"),
            dbc.Col(
                dbc.Textarea(
                    id=field_id, #"notes",
                    style={"width": "100%", "minHeight": "100px"},
                    **kwargs))
        ], className="mb-3 w-100", align="start")
