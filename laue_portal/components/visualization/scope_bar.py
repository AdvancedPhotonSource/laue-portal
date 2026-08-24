"""
Global data-scope bar for the peak-indexing visualization page.

The controls here are *data scope*, not per-tab view tuning: they change
which steps and which patterns every tab sees.  That is why they live in a
page-level bar between the detail header and the tabs rather than in a
``.pi-viz-sidebar`` -- the sidebars are per-tab, Dash forbids duplicate
component IDs, and three of the six tabs have no sidebar at all.

All widgets use the stable ``SCOPE_*_ID`` constants below so page callbacks
can address them, following the same convention as ``ipf_legend.py``.

Consumers should read the single ``SCOPE_STORE_ID`` store rather than take
one ``Input`` per filter: ``update_orientation_map`` already carries ~50
positional inputs, and growing that list per filter does not scale.
"""

from typing import Optional

import dash_bootstrap_components as dbc
from dash import dcc, html

# ---------------------------------------------------------------------------
# Stable component IDs
# ---------------------------------------------------------------------------

SCOPE_STORE_ID = "global-data-scope"
SCOPE_BAR_ID = "scope-bar"
SCOPE_RESET_ID = "scope-reset-btn"

SCOPE_PATTERN0_ID = "scope-pattern0-only"
SCOPE_MIN_PEAKS_ID = "scope-min-peaks"

#: Default scope -- skip steps with 3 or fewer peaks, pattern 0 only.
DEFAULT_SCOPE = {"pattern0_only": True, "min_peaks": 4}


# ---------------------------------------------------------------------------
# Scope value helpers
# ---------------------------------------------------------------------------


def normalize_scope(data: Optional[dict]) -> dict:
    """Coerce raw control values into a complete, well-typed scope dict.

    A cleared ``dbc.Input(type="number")`` yields ``None`` rather than 0, and
    a partially-typed one can yield a string, so the threshold is defaulted
    and clamped rather than trusted.
    """
    data = data or {}

    raw_min = data.get("min_peaks", DEFAULT_SCOPE["min_peaks"])
    try:
        min_peaks = int(raw_min) if raw_min not in (None, "") else DEFAULT_SCOPE["min_peaks"]
    except (TypeError, ValueError):
        min_peaks = DEFAULT_SCOPE["min_peaks"]

    return {
        "pattern0_only": bool(data.get("pattern0_only", DEFAULT_SCOPE["pattern0_only"])),
        # Negative thresholds are meaningless; 0 is the "off" value.
        "min_peaks": max(0, min_peaks),
    }


def max_skipped_peaks(scope: Optional[dict] = None) -> int:
    """Convert the internal minimum-kept threshold to the displayed maximum."""
    return max(0, normalize_scope(scope)["min_peaks"] - 1)


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


def scope_bar(scope: Optional[dict] = None, is_open: bool = False) -> html.Div:
    """Build the collapsible global data-scope bar.

    Uses ``dbc.Accordion``, which handles open/close, the caret and the ARIA
    state itself -- there is no toggle callback and the title is static.
    """
    scope = normalize_scope(scope)

    return html.Div(
        id=SCOPE_BAR_ID,
        className="pi-scope-bar",
        children=[
            dcc.Store(id=SCOPE_STORE_ID, data=scope),
            dbc.Accordion(
                flush=True,
                start_collapsed=not is_open,
                children=dbc.AccordionItem(
                    title="Data scope",
                    children=html.Div(
                        className="pi-scope-body",
                        children=[
                            html.Div(
                                className="pi-scope-field",
                                children=[
                                    dbc.Checkbox(
                                        id=SCOPE_PATTERN0_ID,
                                        label="Load only pattern 0",
                                        value=scope["pattern0_only"],
                                    ),
                                ],
                            ),
                            html.Div(
                                className="pi-scope-field",
                                children=[
                                    html.Div(
                                        className="pi-scope-inline",
                                        children=[
                                            html.Label(
                                                "Skip steps with peaks ≤",
                                                htmlFor=SCOPE_MIN_PEAKS_ID,
                                                className="pi-scope-label",
                                            ),
                                            dbc.Input(
                                                id=SCOPE_MIN_PEAKS_ID,
                                                type="number",
                                                min=0,
                                                step=1,
                                                value=max_skipped_peaks(scope),
                                                debounce=True,
                                                className="pi-scope-input",
                                            ),
                                        ],
                                    ),
                                    html.Small(
                                        "0 keeps every step.",
                                        className="pi-scope-help",
                                    ),
                                ],
                            ),
                            dbc.Button(
                                "Reset",
                                id=SCOPE_RESET_ID,
                                color="link",
                                size="sm",
                                n_clicks=0,
                                className="pi-scope-reset",
                            ),
                        ],
                    ),
                ),
            ),
        ],
    )
