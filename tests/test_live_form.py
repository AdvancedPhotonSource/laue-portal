"""Live form validation must block bad submissions without inspecting scan files."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import lau_dash  # noqa: F401 enables page registration
from laue_portal.components.live_form import INDEX_FIELDS, WIRE_FIELDS, _walk
from laue_portal.components.live_header import header_view
from laue_portal.components.live_validation import FIELD_IDS, FORM_FIELDS, PARAMETER_IDS, form_errors
from laue_portal.components.request_defaults import create_default_peakindex, create_default_wirerecon
from laue_portal.pages import live
from laue_portal.utilities.srange import srange


@pytest.fixture
def values():
    result = dict(
        zip(
            FORM_FIELDS,
            (
                1,
                "Demo",
                "/future/raw",
                "wire_%d.h5",
                "/future/results",
                "geo.xml",
                "geo.xml",
                "Ni.xml",
                "",
                True,
                True,
                "notifications",
            ),
            strict=True,
        )
    )
    for stage, mapping, defaults in (
        ("r", WIRE_FIELDS, vars(create_default_wirerecon())),
        ("i", INDEX_FIELDS, vars(create_default_peakindex())),
    ):
        for field, name in mapping.items():
            result[f"live-{stage}-{field}"] = "0 0 1" if name == "indexHKL" else defaults[name]
    return result


def test_validation_uses_formats_without_expanding_ranges_or_reading_files(values, monkeypatch):
    monkeypatch.setattr(srange, "list", Mock(side_effect=AssertionError("Do not expand the range")))
    values["live-depths"] = "1-1000000000"
    assert form_errors(values) == {}


@pytest.mark.parametrize(
    "field,value",
    [
        ("live-input", " "),
        ("live-filename", "wire.h5"),
        ("live-filename", "wire_%d_%d.h5"),
        ("live-depths", "1,x"),
        ("live-r-depth_resolution", 0),
        ("live-r-depth_start", "nan"),
        ("live-r-depth_end", -1000),
        ("live-r-percent_brightest", 101),
        ("live-r-frame_skip", -1),
        ("live-r-wire_skip", 1.5),
        ("live-i-boxsize", 1.5),
        ("live-i-maxRfactor", 0),
        ("live-i-indexHKL", "0 1"),
        ("live-i-indexKeVmaxCalc", "inf"),
    ],
)
def test_invalid_field_is_identified(values, field, value):
    values[field] = value
    assert field in form_errors(values)


def test_disabled_indexing_skips_its_validation(values):
    for field in (*PARAMETER_IDS, "live-geometry-i", "live-crystal", "live-depths"):
        if field.startswith("live-i-") or field in {"live-geometry-i", "live-crystal", "live-depths"}:
            values[field] = "invalid"
    values["live-index-enabled"] = False
    assert form_errors(values) == {}


@pytest.mark.parametrize("reconstruction,indexing", [(True, False), (False, True), (True, True)])
def test_stage_selection_builds_only_enabled_requests(values, reconstruction, indexing):
    values["live-recon-enabled"], values["live-index-enabled"] = reconstruction, indexing
    if not reconstruction:
        for identity in PARAMETER_IDS:
            if identity.startswith("live-r-"):
                values[identity] = "unused"
        values["live-geometry-r"], values["live-depths"] = "", "unused"
    assert form_errors(values) == {}
    r, i = live.build_live_requests(*(values[key] for key in FORM_FIELDS), [values[key] for key in PARAMETER_IDS])
    assert (r is not None, i is not None) == (reconstruction, indexing)
    if not reconstruction:
        assert i.depth_range is None
    styles = live.select_stages(reconstruction, indexing)
    assert (styles[0].get("display") != "none") == reconstruction
    assert (styles[1].get("display") != "none") == indexing


def test_no_stage_is_rejected(values):
    values["live-recon-enabled"] = values["live-index-enabled"] = False
    assert "live-filename" in form_errors(values)


@pytest.mark.parametrize("mask", [None, "", "None", "none", "null"])
def test_optional_mask_default_does_not_become_a_path(values, mask):
    values["live-i-maskFile"] = mask
    _, indexing = live.build_live_requests(
        *(values[key] for key in FORM_FIELDS), [values[key] for key in PARAMETER_IDS]
    )
    assert indexing.mask_file is None


def test_feedback_targets_all_exist_once():
    ids = [node.id for node in _walk(live.layout()) if getattr(node, "id", None)]
    assert len(ids) == len(set(ids))
    assert {f"{field}-feedback" for field in FIELD_IDS} <= set(ids)
    assert "live-points" not in ids and "live-finish" not in ids


def test_live_requests_have_no_fixed_point_selection(values):
    r, i = live.build_live_requests(*(values[key] for key in FORM_FIELDS), [values[key] for key in PARAMETER_IDS])
    assert r.scan_points is None and r.scan_point_values == ()
    assert i.scan_points is None and i.scan_point_values == ()


def test_invalid_start_does_not_create_or_enqueue_a_run(values, monkeypatch):
    values["live-input"] = ""
    create, enqueue, feedback = Mock(), Mock(), Mock()
    monkeypatch.setattr(live.dash, "ctx", SimpleNamespace(triggered_id="live-start"))
    monkeypatch.setattr(live.dash, "set_props", Mock())
    monkeypatch.setattr(live, "create_live", create)
    monkeypatch.setattr(live, "enqueue_live", enqueue)
    monkeypatch.setattr(live, "show_feedback", feedback)
    result = live.control_live(1, None, None, None, None, *(values[key] for key in (*FORM_FIELDS, *PARAMETER_IDS)))
    assert result[:2] == ("Check the highlighted fields.", True)
    create.assert_not_called()
    enqueue.assert_not_called()
    assert "live-input" in feedback.call_args.args[0]


@pytest.mark.parametrize(
    "state,visible",
    [
        (None, (True, True, False, False)),
        ("finished", (True, True, False, False)),
        ("cancelled", (True, True, False, False)),
        ("failed", (True, True, False, False)),
        ("queued", (False, False, True, False)),
        ("running", (False, False, True, False)),
        ("recovery", (False, False, True, True)),
    ],
)
def test_start_and_stop_are_exclusive(state, visible):
    status = _status(state) if state else None
    view = header_view(status)
    assert tuple(style.get("display") != "none" for style in view["styles"]) == visible
    assert not (visible[1] and visible[2])


def test_repeated_stop_is_disabled():
    assert header_view({**_status("running"), "action": "stop"})["disabled"][2] is True


def test_stop_interrupted_by_shutdown_keeps_recovery_controls_available():
    view = header_view({**_status("recovery"), "action": "stop"})
    assert view["phase"] == "Recovery"
    assert view["disabled"][2:] == (False, False)


def _status(state):
    return dict(
        state=state,
        action=None,
        reconstruction_id=13,
        reconstruction_job_id=21,
        indexing_id=9,
        indexing_job_id=22,
        arrived=2,
        reconstructed=1,
        indexed_points=1,
        pending=1,
        failures=0,
        published_at="2026-10-20T18:08:02",
        error=None,
    )


@pytest.mark.parametrize("state", ["finished", "cancelled", "failed"])
def test_stopped_header_hides_previous_run_details(state):
    view = header_view(_status(state))
    assert view["details"] == []
    assert view["details_style"] == {"display": "none"}
    assert view["phase"] == "Ready to start"


@pytest.mark.parametrize("valid", [True, False])
def test_validate_never_builds_or_submits_a_run(values, monkeypatch, valid):
    if not valid:
        values["live-input"] = ""
    create, enqueue, build = Mock(), Mock(), Mock()
    monkeypatch.setattr(live.dash, "ctx", SimpleNamespace(triggered_id="live-validate"))
    monkeypatch.setattr(live.dash, "set_props", Mock())
    monkeypatch.setattr(live, "create_live", create)
    monkeypatch.setattr(live, "enqueue_live", enqueue)
    monkeypatch.setattr(live, "build_live_requests", build)
    monkeypatch.setattr(live, "show_feedback", Mock())
    result = live.control_live(None, None, None, 1, None, *(values[key] for key in (*FORM_FIELDS, *PARAMETER_IDS)))
    assert result[:2] == ("Form settings are valid." if valid else "Check the highlighted fields.", True)
    create.assert_not_called()
    enqueue.assert_not_called()
    build.assert_not_called()
