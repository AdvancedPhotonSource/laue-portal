"""Cheap, submit-time checks for the live form; no filesystem inspection."""

import math

import dash_bootstrap_components as dbc
from dash import set_props

from laue_portal.components.live_form import INDEX_FIELDS, WIRE_FIELDS, _walk
from laue_portal.utilities.srange import srange

FORM_FIELDS = (
    "live-scan",
    "live-author",
    "live-input",
    "live-filename",
    "live-output",
    "live-geometry-r",
    "live-geometry-i",
    "live-crystal",
    "live-depths",
    "live-index-enabled",
    "live-recon-enabled",
    "live-daq",
)
PARAMETER_IDS = tuple(
    f"live-{stage}-{name}" for stage, fields in (("r", WIRE_FIELDS), ("i", INDEX_FIELDS)) for name in fields
)
FIELD_IDS = tuple(
    name
    for name in (*FORM_FIELDS, *PARAMETER_IDS)
    if name not in {"live-index-enabled", "live-recon-enabled", "live-i-smooth"}
)


def with_feedback(form):
    for field in _walk(form):
        if "lp-form-field" not in str(getattr(field, "className", "")).split():
            continue
        control = next((child for child in field.children if getattr(child, "id", None) in FIELD_IDS), None)
        if control is not None:
            field.children.append(dbc.FormFeedback(id=f"{control.id}-feedback", type="invalid"))
    return form


def form_errors(values):
    errors = {}
    indexing = bool(values.get("live-index-enabled"))
    reconstruction = bool(values.get("live-recon-enabled", True))
    required = ["live-author", "live-input", "live-filename", "live-output"]
    if reconstruction:
        required += ["live-geometry-r"]
    if not reconstruction and not indexing:
        errors["live-filename"] = "Enable reconstruction, indexing, or both."
    if indexing:
        required += ["live-geometry-i", "live-crystal"]
    for name in required:
        if not str(values.get(name) or "").strip():
            errors[name] = "Required."
    filename = str(values.get("live-filename") or "").strip()
    if filename and filename.count("%d") != 1:
        errors["live-filename"] = "Use one %d point index, e.g. scan_%d.h5."
    for name in ("live-depths",) if indexing and reconstruction else ():
        value = str(values.get(name) or "").strip()
        if value:
            try:
                parsed = srange(value)
                if not parsed.len() or parsed.first() < 0:
                    raise ValueError()
            except (TypeError, ValueError):
                errors[name] = "Use indices such as 1-10 or 1,3,5."
    integers = {
        "live-scan",
        "frame_skip",
        "wire_skip",
        "boxsize",
        "min_separation",
        "threshold",
        "thresholdRatio",
        "max_number",
        "max_peaks",
    }
    optional = {"live-scan", "threshold", "thresholdRatio", "max_number", "max_peaks"}
    numbers = {}
    for identity in FIELD_IDS:
        if identity.startswith("live-i-") and not indexing:
            continue
        if identity.startswith("live-r-") and not reconstruction:
            continue
        name = identity.removeprefix("live-r-").removeprefix("live-i-")
        if identity != "live-scan" and name not in WIRE_FIELDS and name not in INDEX_FIELDS:
            continue
        if name in {"wire_edges", "peakShape", "maskFile", "indexHKL", "depth"}:
            continue
        value = values.get(identity)
        if (value is None or str(value).strip() == "") and name in optional:
            continue
        try:
            number = float(value)
            if not math.isfinite(number) or (name in integers and (int(value) != number)):
                raise ValueError()
        except (TypeError, ValueError, OverflowError):
            errors[identity] = "Enter a whole number." if name in integers else "Enter a finite number."
            continue
        numbers[identity] = number
        if name in {"depth_start", "depth_end", "threshold"}:
            continue
        if name in {"live-scan", "frame_skip", "wire_skip"}:
            if number < 0:
                errors[identity] = "Must be zero or greater."
        elif number <= 0:
            errors[identity] = "Must be greater than zero."
        elif name == "percent_brightest" and number > 100:
            errors[identity] = "Must be greater than 0 and at most 100."
    start, end = (numbers.get(f"live-r-depth_{name}") for name in ("start", "end"))
    if start is not None and end is not None and end < start:
        errors["live-r-depth_end"] = "Must be at least the start depth."
    if indexing:
        try:
            hkl = str(values.get("live-i-indexHKL") or "").replace(",", " ").split()
            if len(hkl) != 3:
                raise ValueError()
            tuple(map(int, hkl))
        except ValueError:
            errors["live-i-indexHKL"] = "Enter three integers, e.g. 0 0 1."
    return errors


def show_feedback(errors):
    for identity in FIELD_IDS:
        set_props(identity, {"invalid": identity in errors})
        set_props(f"{identity}-feedback", {"children": errors.get(identity, "")})
