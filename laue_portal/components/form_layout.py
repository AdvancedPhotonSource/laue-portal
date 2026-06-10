import dash_bootstrap_components as dbc
from dash import html


def form_field(label_text, field_id, placeholder="", input_type="text", wide=False, readonly=False, **kwargs):
    cls = "lp-form-field lp-form-field-wide" if wide else "lp-form-field"
    return html.Div(
        [
            html.Label(label_text, htmlFor=field_id),
            dbc.Input(
                id=field_id,
                type=input_type,
                placeholder=placeholder,
                readonly=readonly,
                className="form-control",
                **kwargs,
            ),
        ],
        className=cls,
    )


def form_select(label_text, field_id, options, placeholder="Select:", wide=False, disabled=False, **kwargs):
    cls = "lp-form-field lp-form-field-wide" if wide else "lp-form-field"
    return html.Div(
        [
            html.Label(label_text, htmlFor=field_id),
            dbc.Select(
                id=field_id,
                options=options,
                placeholder=placeholder,
                disabled=disabled,
                className="form-select",
                **kwargs,
            ),
        ],
        className=cls,
    )


def form_checkbox(label_text, field_id, disabled=False):
    return dbc.Checkbox(id=field_id, label=label_text, disabled=disabled)


def form_textarea(label_text, field_id, placeholder="", wide=True, readonly=False, min_height="80px", **kwargs):
    cls = "lp-form-field lp-form-field-wide" if wide else "lp-form-field"
    return html.Div(
        [
            html.Label(label_text, htmlFor=field_id),
            dbc.Textarea(
                id=field_id,
                placeholder=placeholder,
                readonly=readonly,
                className="form-control",
                style={"minHeight": min_height},
                **kwargs,
            ),
        ],
        className=cls,
    )


def form_field_with_button(
    label_text,
    field_id,
    button_id,
    button_label,
    placeholder="",
    datalist_id=None,
    readonly=False,
    show_button=True,
    button_color="success",
    button_outline=False,
    button_children=None,
    **kwargs,
):
    input_kwargs = {"list": datalist_id} if datalist_id else {}
    input_kwargs.update(kwargs)
    children = [
        html.Div(
            [
                html.Label(label_text, htmlFor=field_id),
                dbc.Input(
                    id=field_id,
                    placeholder=placeholder,
                    readonly=readonly,
                    className="form-control",
                    **input_kwargs,
                ),
            ],
            className="lp-form-field",
            style={"flex": "1"},
        )
    ]
    if show_button:
        children.append(
            dbc.Button(
                button_children or button_label,
                id=button_id,
                color=button_color,
                outline=button_outline,
                size="sm",
                className="lp-form-inline-button",
            )
        )
    if datalist_id:
        children.append(html.Datalist(id=datalist_id, children=[]))
    return html.Div(children, className="lp-form-field-inline lp-form-field-wide")


def form_fields_with_button(
    *fields, button_id, button_label, show_button=True, button_color="success", button_outline=False
):
    children = list(fields)
    if show_button:
        children.append(
            dbc.Button(
                button_label,
                id=button_id,
                color=button_color,
                outline=button_outline,
                size="sm",
                className="lp-form-inline-button",
            )
        )
    return html.Div(children, className="lp-form-field-inline lp-form-field-wide")


def form_check_row(*checkboxes):
    return html.Div(list(checkboxes), className="lp-form-check-row")


def section_card(title, children, accent="teal", icon_class="bi bi-circle", anchor_id=None, header_actions=None):
    head_children = [
        html.Div(
            [html.I(className=f"lp-form-section-icon {icon_class}"), html.H3(title)],
            className="lp-form-card-title",
        )
    ]
    if header_actions:
        actions = header_actions if isinstance(header_actions, (list, tuple)) else [header_actions]
        actions = [action for action in actions if action is not None]
        if actions:
            head_children.append(html.Div(actions, className="lp-form-card-actions"))

    card = html.Div(
        [
            html.Div(head_children, className="lp-form-card-head"),
            html.Div(children, className="lp-form-card-body"),
        ],
        className=f"lp-form-card lp-form-card--{accent}",
    )
    if anchor_id:
        return html.Div([html.Div(id=anchor_id, className="lp-form-section-anchor"), card])
    return card


def nav_link(label, icon_class="bi bi-circle", href="#"):
    return html.A(
        [html.Span(className=f"lp-form-nav-icon {icon_class}"), html.Span(label, className="lp-form-nav-label")],
        className="lp-form-nav-link",
        href=href,
    )


def section_sidebar(groups, title="Sections"):
    return html.Details(
        className="lp-form-sidebar",
        open=True,
        children=[
            html.Summary(
                [html.I(className="bi bi-layout-sidebar-inset"), html.Span(title)],
                className="lp-form-sidebar-toggle",
            ),
            html.Div(
                className="lp-form-sidebar-content",
                children=[
                    html.Div(
                        className="lp-form-nav-group",
                        children=[
                            html.Div(group_title, className="lp-form-nav-heading"),
                            *[nav_link(label, icon, href) for label, icon, href in links],
                        ],
                    )
                    for group_title, links in groups
                ],
            ),
        ],
    )


def form_layout(sidebar, children):
    return html.Div(
        className="lp-form-body",
        children=[sidebar, html.Div(className="lp-form-main", children=children)],
    )
