from collections import Counter

from dash.development.base_component import Component

from laue_portal.components.wire_recon_form import wire_recon_form, wire_recon_readonly_form

EDIT_ONLY_ACTION_IDS = {
    "wirerecon-update-path-fields-btn",
    "wirerecon-check-filenames-btn",
    "wirerecon-load-file-indices-btn",
    "wirerecon-set-default-parameters-btn",
}

REMOVED_STUB_IDS = {
    "wirerecon-load-default-geo-btn",
    "wirerecon-view-modify-params-btn",
}

REQUIRED_FIELD_IDS = {
    "IDnumber",
    "author",
    "root_path",
    "data_path",
    "filenamePrefix",
    "wirerecon-filename-templates",
    "scanPoints",
    "outputFolder",
    "geoFile",
    "depth_start",
    "depth_end",
    "depth_resolution",
    "wire_edges",
    "percent_brightest",
    "notes",
}


def collect_components(component):
    components = []

    def walk(node):
        if isinstance(node, (list, tuple)):
            for item in node:
                walk(item)
            return
        if not isinstance(node, Component):
            return

        components.append(node)
        children = getattr(node, "children", None)
        if children is not None:
            walk(children)

    walk(component)
    return components


def collect_ids(component):
    return [item.id for item in collect_components(component) if getattr(item, "id", None) is not None]


def component_by_id(component, component_id):
    return next(item for item in collect_components(component) if getattr(item, "id", None) == component_id)


def test_wire_recon_forms_have_no_duplicate_ids():
    for form in (wire_recon_form, wire_recon_readonly_form):
        counts = Counter(collect_ids(form))
        assert {component_id: count for component_id, count in counts.items() if count > 1} == {}


def test_wire_recon_edit_form_contains_fields_and_actions():
    ids = set(collect_ids(wire_recon_form))

    assert REQUIRED_FIELD_IDS <= ids
    assert EDIT_ONLY_ACTION_IDS <= ids
    assert ids.isdisjoint(REMOVED_STUB_IDS)


def test_wire_recon_readonly_form_contains_fields_without_actions():
    ids = set(collect_ids(wire_recon_readonly_form))

    assert REQUIRED_FIELD_IDS <= ids
    assert ids.isdisjoint(EDIT_ONLY_ACTION_IDS)


def test_wire_recon_readonly_form_disables_all_fields():
    readonly_inputs = REQUIRED_FIELD_IDS - {"wirerecon-filename-templates", "wire_edges"}
    for component_id in readonly_inputs:
        assert component_by_id(wire_recon_readonly_form, component_id).readonly is True

    assert component_by_id(wire_recon_readonly_form, "wire_edges").disabled is True


def test_wire_recon_file_fields_keep_expected_order():
    expected_order = ["root_path", "data_path", "filenamePrefix", "scanPoints", "outputFolder", "geoFile"]

    for form in (wire_recon_form, wire_recon_readonly_form):
        ids = collect_ids(form)
        positions = [ids.index(component_id) for component_id in expected_order]
        assert positions == sorted(positions)
