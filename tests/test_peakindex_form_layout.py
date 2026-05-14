from collections import Counter

from dash.development.base_component import Component

from laue_portal.components.peakindex_form import peakindex_form, peakindex_readonly_form

EDIT_ONLY_ACTION_IDS = {
    "peakindex-update-path-fields-btn",
    "peakindex-check-filenames-btn",
    "peakindex-set-default-peak-search-btn",
    "peakindex-set-default-indexing-btn",
}

REQUIRED_FIELD_IDS = {
    "IDnumber",
    "author",
    "root_path",
    "data_path",
    "filenamePrefix",
    "scanPoints",
    "depthRange",
    "geoFile",
    "crystFile",
    "outputFolder",
    "outputXML",
    "maskFile",
    "boxsize",
    "maxRfactor",
    "threshold",
    "thresholdRatio",
    "min_size",
    "min_separation",
    "max_number",
    "peakShape",
    "smooth",
    "cosmicFilter",
    "indexKeVmaxCalc",
    "indexKeVmaxTest",
    "indexAngleTolerance",
    "indexHKL",
    "indexCone",
    "max_peaks",
    "depth",
    "notes",
}


def collect_ids(component):
    ids = []

    def walk(node):
        if isinstance(node, (list, tuple)):
            for item in node:
                walk(item)
            return
        if not isinstance(node, Component):
            return

        component_id = getattr(node, "id", None)
        if component_id is not None:
            ids.append(component_id)

        children = getattr(node, "children", None)
        if children is not None:
            walk(children)

    walk(component)
    return ids


def assert_no_duplicate_ids(component):
    counts = Counter(collect_ids(component))
    duplicates = {component_id: count for component_id, count in counts.items() if count > 1}
    assert duplicates == {}


def test_peakindex_forms_have_no_duplicate_ids():
    assert_no_duplicate_ids(peakindex_form)
    assert_no_duplicate_ids(peakindex_readonly_form)


def test_peakindex_edit_form_contains_fields_and_actions():
    ids = set(collect_ids(peakindex_form))

    assert REQUIRED_FIELD_IDS <= ids
    assert EDIT_ONLY_ACTION_IDS <= ids


def test_peakindex_readonly_form_contains_fields_without_actions():
    ids = set(collect_ids(peakindex_readonly_form))

    assert REQUIRED_FIELD_IDS <= ids
    assert ids.isdisjoint(EDIT_ONLY_ACTION_IDS)
