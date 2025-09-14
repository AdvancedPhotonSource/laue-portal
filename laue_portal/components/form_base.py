import dash_bootstrap_components as dbc


def _stack(objects,gap=3):
    return dbc.Stack(
        objects, 
        direction="horizontal",
        gap=gap#3
    )

def _field(label, field_id, size='sm', kwargs={}):
    if size == 'sm':
        width='200px'
    elif size == 'md':
        width='350px'
    elif size == 'lg':
        width='500px'
    elif size == 'hg':
        width='9999px'

    return dbc.InputGroup(
        [
            dbc.InputGroupText(label),
            dbc.Input(id=field_id, **kwargs),
        ],
        style={'width': width},
        className="mb-3",
    )

def _select(label, field_id, select_options, size='sm', kwargs={}):
    if size == 'sm':
        width='200px'
    elif size == 'md':
        width='350px'
    elif size == 'lg':
        width='500px'
    elif size == 'hg':
        width='9999px'

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

def _ckbx(label, field_id, size='sm'):
    if size == 'sm':
        width='200px'
    elif size == 'md':
        width='350px'
    elif size == 'lg':
        width='500px'

    return dbc.Checkbox(id=field_id, 
                        label=label,
                        className="mb-3",
                        style={'width': width})