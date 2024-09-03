import dash_bootstrap_components as dbc
from dash import html
import dash
import laue_portal.pages.ui_shared as ui_shared

dash.register_page(__name__)

layout = dbc.Container(
    [html.Div([
        ui_shared.navbar,
        dbc.Row(
                [
                    dbc.Accordion(
                        [
                        dbc.AccordionItem(
                            [
                                html.P("This is the content of the first section"),
                                dbc.Button("Click here"),
                            ],
                            title="Recon Parameters",
                        ),
                        dbc.AccordionItem(
                            [
                                html.P("This is the content of the second section"),
                                dbc.Button("Don't click me!", color="danger"),
                            ],
                            title="Calibration",
                        ),
                        dbc.AccordionItem(
                            "This is the content of the third section",
                            title="Mask",
                        ),
                        dbc.AccordionItem(
                            "This is the content of the third section",
                            title="Motor Path",
                        ),
                        dbc.AccordionItem(
                            "This is the content of the third section",
                            title="Detector",
                        ),
                        dbc.AccordionItem(
                            "This is the content of the third section",
                            title="Algorithm Parameters",
                        ),
                        ],
                        always_open=True
                    ),
                ],
                style={'width': '100%', 'overflow-x': 'auto'}
        )
    ],
    )
    ],
    className='dbc', 
    fluid=True
)