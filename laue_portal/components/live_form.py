"""Reuse batch parameter fields with isolated IDs and shared defaults."""

from copy import deepcopy

from dash import html

from laue_portal.components.peakindex_form import build_peakindex_form
from laue_portal.components.wire_recon_form import build_wire_recon_form

WIRE_FIELDS = {
    name: name
    for name in (
        "depth_start",
        "depth_end",
        "depth_resolution",
        "wire_edges",
        "percent_brightest",
        "frame_skip",
        "wire_skip",
    )
}
INDEX_FIELDS = {
    "boxsize": "box_size",
    "maxRfactor": "max_rfactor",
    "threshold": "threshold",
    "thresholdRatio": "threshold_ratio",
    "min_size": "min_size",
    "min_separation": "min_separation",
    "max_number": "max_number",
    "peakShape": "peak_shape",
    "maskFile": "mask_file",
    "smooth": "smooth",
    "indexKeVmaxCalc": "index_kev_max_calc",
    "indexKeVmaxTest": "index_kev_max_test",
    "indexAngleTolerance": "index_angle_tolerance",
    "indexHKL": "indexHKL",
    "indexCone": "index_cone",
    "max_peaks": "max_peaks",
    "depth": "depth",
}


def _walk(component):
    if not hasattr(component, "to_plotly_json"):
        return
    yield component
    children = getattr(component, "children", [])
    for child in children if isinstance(children, (list, tuple)) else [children]:
        yield from _walk(child)


def parameter_cards(stage, defaults):
    """Clone only scientific parameter cards; never register batch page callbacks."""
    form = (build_wire_recon_form if stage == "r" else build_peakindex_form)(show_actions=False)
    anchors = {"wire-recon-sec-parameters"} if stage == "r" else {"peakindex-sec-peaks", "peakindex-sec-index"}
    fields = WIRE_FIELDS if stage == "r" else INDEX_FIELDS
    cards = []
    for component in _walk(form):
        children = getattr(component, "children", [])
        if not isinstance(children, list) or not children or getattr(children[0], "id", None) not in anchors:
            continue
        card = deepcopy(component)
        for child in _walk(card):
            identity = getattr(child, "id", None)
            if identity:
                child.id = f"live-{stage}-{identity}"
                if identity in fields:
                    name = fields[identity]
                    value = defaults.get(name)
                    if name == "indexHKL":
                        value = " ".join(str(defaults.get(f"index_{axis}", 0)) for axis in "hkl")
                    child.value = value
            if getattr(child, "htmlFor", None):
                child.htmlFor = f"live-{stage}-{child.htmlFor}"
        cards.append(card)
    return cards


def parameter_sections(stage, defaults):
    """Present shared fields as plain sections within each live stage card."""
    sections = []
    for card in parameter_cards(stage, defaults):
        title = next(child.children for child in _walk(card) if isinstance(child, html.H3))
        content = next(
            child.children for child in _walk(card) if getattr(child, "className", None) == "lp-form-card-body"
        )
        sections.append(
            html.Section(
                [html.H4("Depth and wire" if stage == "r" else title.removesuffix(" Parameters")), content],
                className="lp-live-parameter-section",
            )
        )
    return sections
