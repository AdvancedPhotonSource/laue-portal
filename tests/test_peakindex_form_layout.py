from collections import Counter

from dash.development.base_component import Component

from laue_portal.components.peakindex_form import peakindex_form, peakindex_readonly_form
from laue_portal.pages import callback_registrars

EDIT_ONLY_ACTION_IDS = {
    "peakindex-update-path-fields-btn",
    "peakindex-check-filenames-btn",
    "peakindex-find-indices-btn",
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


def test_peakindex_file_fields_keep_scan_inputs_before_geometry():
    expected_order = ["data_path", "filenamePrefix", "scanPoints", "depthRange", "geoFile"]

    for component in (peakindex_form, peakindex_readonly_form):
        ids = collect_ids(component)
        positions = [ids.index(component_id) for component_id in expected_order]
        assert positions == sorted(positions)


def test_peakindex_mask_file_is_before_peak_search_checkboxes():
    expected_order = ["peakShape", "maskFile", "smooth", "cosmicFilter"]

    for component in (peakindex_form, peakindex_readonly_form):
        ids = collect_ids(component)
        positions = [ids.index(component_id) for component_id in expected_order]
        assert positions == sorted(positions)


def make_find_indices_callback(monkeypatch):
    updates = {}
    monkeypatch.setattr(
        callback_registrars, "set_props", lambda component_id, props: updates.update({component_id: props})
    )
    callback = callback_registrars.register_find_indices_callback(
        button_id="test-find-indices-btn",
        data_path_id="data_path",
        filename_prefix_id="filenamePrefix",
        scan_points_id="scanPoints",
        depth_range_id="depthRange",
        num_indices=2,
    )
    return callback, updates


def test_find_indices_callback_populates_scan_and_depth_ranges(tmp_path, monkeypatch):
    callback, updates = make_find_indices_callback(monkeypatch)
    (tmp_path / "sample_1_1.h5").write_text("", encoding="utf-8")
    (tmp_path / "sample_2_1.h5").write_text("", encoding="utf-8")
    (tmp_path / "sample_2_2.h5").write_text("", encoding="utf-8")

    callback(1, str(tmp_path), "sample_%d_%d.h5", "")

    assert updates["scanPoints"] == {"value": "1,2"}
    assert updates["depthRange"] == {"value": "1,2"}


def test_find_indices_callback_clears_indices_when_no_files_match(tmp_path, monkeypatch):
    callback, updates = make_find_indices_callback(monkeypatch)
    (tmp_path / "sample_1_1.h5").write_text("", encoding="utf-8")

    callback(1, str(tmp_path), "missing_%d_%d.h5", "")

    assert updates["scanPoints"] == {"value": ""}
    assert updates["depthRange"] == {"value": ""}


def test_find_indices_callback_clears_depth_for_one_dimensional_pattern(tmp_path, monkeypatch):
    callback, updates = make_find_indices_callback(monkeypatch)
    (tmp_path / "sample_1.h5").write_text("", encoding="utf-8")
    (tmp_path / "sample_2.h5").write_text("", encoding="utf-8")

    callback(1, str(tmp_path), "sample_%d.h5", "")

    assert updates["scanPoints"] == {"value": "1,2"}
    assert updates["depthRange"] == {"value": ""}
