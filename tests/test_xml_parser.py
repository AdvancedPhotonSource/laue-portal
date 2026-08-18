"""
Tests for laue_portal.analysis.xml_parser module.

Uses a synthetic fixture XML at tests/fixtures/test_indexing.xml.
"""

import os
import sys

import numpy as np
import pytest

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from laue_portal.analysis.xml_parser import (
    apply_data_scope,
    get_all_indexed_peaks,
    get_all_patterns,
    get_step_peaks,
    parse_indexing_xml,
    positions_hf,
    positions_lab,
    yz_to_hf,
)

FIXTURE_XML = os.path.join(os.path.dirname(__file__), "fixtures", "test_indexing.xml")


@pytest.fixture
def parsed():
    return parse_indexing_xml(FIXTURE_XML)


# ---------------------------------------------------------------------------
# parse_indexing_xml tests
# ---------------------------------------------------------------------------


class TestParseIndexingXml:
    def test_returns_dict(self, parsed):
        assert isinstance(parsed, dict)

    def test_required_keys_present(self, parsed):
        expected_keys = [
            "positions",
            "depths",
            "energies",
            "scan_nums",
            "n_patterns",
            "n_peaks",
            "recip_lattices",
            "rms_errors",
            "goodnesses",
            "n_indexed",
            "space_group",
            "lattice_params",
            "structure_desc",
            "_steps",
        ]
        for key in expected_keys:
            assert key in parsed, f"Missing key: {key}"

    def test_step_count(self, parsed):
        assert len(parsed["positions"]) == 4

    def test_positions_shape(self, parsed):
        pos = parsed["positions"]
        assert pos.ndim == 2
        assert pos.shape == (4, 3)

    def test_positions_values(self, parsed):
        pos = parsed["positions"]
        assert abs(pos[0, 0] - 100.0) < 0.1
        assert abs(pos[0, 1] - 200.0) < 0.1
        assert abs(pos[0, 2] - 300.0) < 0.1

    def test_depths_nan_when_absent(self, parsed):
        assert np.all(np.isnan(parsed["depths"]))

    def test_energies(self, parsed):
        assert np.all(np.abs(parsed["energies"] - 20.0) < 0.01)

    def test_scan_nums(self, parsed):
        assert parsed["scan_nums"][0] == 1001
        assert parsed["scan_nums"][3] == 1004

    def test_n_patterns(self, parsed):
        assert parsed["n_patterns"][0] == 2
        assert parsed["n_patterns"][1] == 1

    def test_n_peaks(self, parsed):
        assert parsed["n_peaks"].tolist() == [12, 8, 5, 6]

    def test_recip_lattices_shape(self, parsed):
        assert parsed["recip_lattices"].shape == (4, 3, 3)

    def test_recip_lattice_values(self, parsed):
        astar_0 = parsed["recip_lattices"][0, 0, :]
        assert abs(astar_0[0] - (-10.0)) < 0.01
        assert abs(astar_0[1] - 5.0) < 0.01
        assert abs(astar_0[2] - (-6.0)) < 0.01

    def test_rms_errors(self, parsed):
        assert abs(parsed["rms_errors"][0] - 0.005) < 0.0001

    def test_goodnesses(self, parsed):
        assert abs(parsed["goodnesses"][0] - 150.0) < 0.01

    def test_n_indexed(self, parsed):
        assert parsed["n_indexed"][0] == 9

    def test_crystal_structure(self, parsed):
        assert parsed["space_group"] == 225
        assert parsed["structure_desc"] == "TestMaterial"
        lp = parsed["lattice_params"]
        assert len(lp) == 6
        assert abs(lp[0] - 0.40000) < 0.0001
        assert abs(lp[3] - 90.0) < 0.1


# ---------------------------------------------------------------------------
# data scope tests
# ---------------------------------------------------------------------------


class TestDataScope:
    def test_neutral_scope_preserves_all_steps(self, parsed):
        scoped = apply_data_scope(parsed)
        assert scoped["_step_indices"].tolist() == [0, 1, 2, 3]
        assert len(scoped["positions"]) == len(parsed["positions"])

    def test_min_peaks_filters_without_mutating_cached_parse(self, parsed):
        scoped = apply_data_scope(parsed, {"min_peaks": 7})
        assert scoped["_step_indices"].tolist() == [0, 1]
        assert scoped["n_peaks"].tolist() == [12, 8]
        assert len(parsed["positions"]) == 4

    def test_pattern_zero_scope_filters_pattern_consumers(self, parsed):
        scoped = apply_data_scope(parsed, {"pattern0_only": True})
        assert [p["pattern_num"] for p in get_step_peaks(scoped, 0)["patterns"]] == [0]
        assert scoped["n_patterns"][0] == 1
        assert scoped["n_indexed"][0] == 9
        assert {row["pattern_num"] for row in get_all_patterns(scoped)} == {0}
        assert {row["pattern_num"] for row in get_all_indexed_peaks(scoped)} == {0}

    def test_combined_scope_preserves_original_step_ids(self, parsed):
        scoped = apply_data_scope(parsed, {"min_peaks": 6, "pattern0_only": True})
        assert scoped["_step_indices"].tolist() == [0, 1, 3]
        assert {row["step_index"] for row in get_all_patterns(scoped)} == {0, 1, 3}
        assert {row["step_index"] for row in get_all_indexed_peaks(scoped)} == {0, 1, 3}

    def test_empty_scope(self, parsed):
        scoped = apply_data_scope(parsed, {"min_peaks": 100})
        assert len(scoped["positions"]) == 0
        assert get_all_patterns(scoped) == []
        assert get_all_indexed_peaks(scoped) == []


# ---------------------------------------------------------------------------
# get_step_peaks tests
# ---------------------------------------------------------------------------


class TestGetStepPeaks:
    def test_returns_dict(self, parsed):
        assert isinstance(get_step_peaks(parsed, 0), dict)

    def test_pixel_positions(self, parsed):
        result = get_step_peaks(parsed, 0)
        pp = result["pixel_positions"]
        assert pp is not None
        assert pp.ndim == 2
        assert pp.shape == (12, 2)

    def test_q_vectors(self, parsed):
        result = get_step_peaks(parsed, 0)
        qv = result["q_vectors"]
        assert qv is not None
        assert qv.shape == (12, 3)

    def test_n_peaks(self, parsed):
        assert get_step_peaks(parsed, 0)["n_peaks"] == 12

    def test_patterns(self, parsed):
        result = get_step_peaks(parsed, 0)
        assert len(result["patterns"]) == 2

    def test_pattern_hkl(self, parsed):
        pat0 = get_step_peaks(parsed, 0)["patterns"][0]
        assert pat0["hkl"].shape == (9, 3)
        assert len(pat0["peak_indices"]) == 9

    def test_out_of_range_returns_none(self, parsed):
        assert get_step_peaks(parsed, 9999) is None

    def test_negative_index_returns_none(self, parsed):
        assert get_step_peaks(parsed, -1) is None


# ---------------------------------------------------------------------------
# get_all_patterns tests
# ---------------------------------------------------------------------------


class TestGetAllPatterns:
    def test_returns_list(self, parsed):
        assert isinstance(get_all_patterns(parsed), list)

    def test_total_rows(self, parsed):
        rows = get_all_patterns(parsed)
        assert len(rows) == 5

    def test_has_expected_keys(self, parsed):
        rows = get_all_patterns(parsed)
        expected = [
            "step_index",
            "step_scan_num",
            "pattern_num",
            "rank",
            "n_indexed",
            "n_peaks",
            "indexed_fraction",
            "rms_error",
            "goodness",
            "n_patterns",
            "x_sample",
            "y_sample",
            "z_sample",
            "h_sample",
            "f_sample",
            "depth",
            "astar",
            "bstar",
            "cstar",
            "structure",
            "space_group",
        ]
        for key in expected:
            assert key in rows[0], f"Missing key: {key}"

    def test_pattern_quality_values(self, parsed):
        row = get_all_patterns(parsed)[0]
        assert row["step_index"] == 0
        assert row["step_scan_num"] == 1001
        assert row["pattern_num"] == 0
        assert row["n_indexed"] == 9
        assert row["n_peaks"] == 12
        assert abs(row["indexed_fraction"] - 0.75) < 0.001
        assert abs(row["rms_error"] - 0.005) < 0.0001
        assert abs(row["goodness"] - 150.0) < 0.01

    def test_recip_lattice_vectors_are_formatted(self, parsed):
        row = get_all_patterns(parsed)[0]
        assert row["astar"] == "(-10, 5, -6)"
        assert row["bstar"] == "(-15, -2, -1)"
        assert row["cstar"] == "(-2, 13, 8)"


# ---------------------------------------------------------------------------
# get_all_indexed_peaks tests
# ---------------------------------------------------------------------------


class TestGetAllIndexedPeaks:
    def test_returns_list(self, parsed):
        assert isinstance(get_all_indexed_peaks(parsed), list)

    def test_has_expected_keys(self, parsed):
        rows = get_all_indexed_peaks(parsed)
        assert len(rows) > 0
        expected = [
            "step_index",
            "step_scan_num",
            "pattern_num",
            "h",
            "k",
            "l",
            "peak_index",
            "x_pixel",
            "y_pixel",
            "intensity",
            "integral",
            "qx",
            "qy",
            "qz",
            "rms_error",
            "goodness",
            "n_peaks",
            "energy",
            "q_magnitude",
            "hwhm_x",
            "hwhm_y",
            "aspect_ratio",
            "tilt",
            "chisq",
            "input_image",
            "pattern_n_indexed",
            "pattern_indexed_fraction",
        ]
        for key in expected:
            assert key in rows[0], f"Missing key: {key}"

    def test_total_rows(self, parsed):
        rows = get_all_indexed_peaks(parsed)
        # Step 0: 9+3=12, Step 1: 6, Step 2: 4, Step 3: 5 = 27
        assert len(rows) == 27

    def test_hkl_values(self, parsed):
        row = get_all_indexed_peaks(parsed)[0]
        assert isinstance(row["h"], int)
        assert isinstance(row["k"], int)
        assert isinstance(row["l"], int)

    def test_pixel_coordinates(self, parsed):
        rows = get_all_indexed_peaks(parsed)
        for row in rows[:5]:
            if row["x_pixel"] is not None:
                assert 0 <= row["x_pixel"] <= 2048
                assert 0 <= row["y_pixel"] <= 2048

    def test_optional_peak_fields(self, parsed):
        row = get_all_indexed_peaks(parsed)[0]
        assert row["n_peaks"] == 12
        assert abs(row["energy"] - 20.0) < 0.01
        assert abs(row["q_magnitude"] - 1.003245) < 0.0001
        assert row["hwhm_x"] is None
        assert row["hwhm_y"] is None
        assert row["aspect_ratio"] is None
        assert row["tilt"] is None
        assert row["chisq"] is None
        assert row["input_image"] == "test/image_001.h5"
        assert row["pattern_n_indexed"] == 9
        assert abs(row["pattern_indexed_fraction"] - 0.75) < 0.001


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_nonexistent_file_raises(self):
        with pytest.raises(Exception):  # noqa: B017
            parse_indexing_xml("/nonexistent/path.xml")

    def test_all_steps_parseable(self, parsed):
        for i in range(len(parsed["positions"])):
            assert get_step_peaks(parsed, i) is not None, f"Step {i} returned None"


# ---------------------------------------------------------------------------
# H / F wire-frame coordinates
# ---------------------------------------------------------------------------


class TestHFCoordinates:
    """
    Pin Igor Pro's wire-frame rotation formulas.

    From ``LaueGo/micro/microGeometry.ipf:319-342`` with the 34ID-E
    default ``thetaWire = π/4``::

        H = Y * sin(theta) + Z * cos(theta)
        F = -Y * cos(theta) + Z * sin(theta)

    A silent sign error here would render plots in a flipped/rotated
    orientation that's hard to catch by eye, so the formula is asserted
    explicitly against canonical (Y, Z) inputs.
    """

    _IR2 = 1.0 / np.sqrt(2.0)

    def test_yz_to_hf_unit_z(self):
        # (Y=0, Z=1) -> H=+1/sqrt(2), F=+1/sqrt(2)
        h, f = yz_to_hf(0.0, 1.0)
        assert abs(h - self._IR2) < 1e-9
        assert abs(f - self._IR2) < 1e-9

    def test_yz_to_hf_unit_y(self):
        # (Y=1, Z=0) -> H=+1/sqrt(2), F=-1/sqrt(2)
        h, f = yz_to_hf(1.0, 0.0)
        assert abs(h - self._IR2) < 1e-9
        assert abs(f - (-self._IR2)) < 1e-9

    def test_yz_to_hf_vectorized(self):
        # Vectorized inputs preserve shape and per-element formula.
        y = np.array([0.0, 1.0, 2.0])
        z = np.array([1.0, 0.0, 0.0])
        h, f = yz_to_hf(y, z)
        assert h.shape == (3,) and f.shape == (3,)
        assert np.allclose(h, [self._IR2, self._IR2, 2 * self._IR2])
        assert np.allclose(f, [self._IR2, -self._IR2, -2 * self._IR2])

    def test_yz_to_hf_inverse(self):
        # Sanity: applying Igor's inverse rotation recovers (Y, Z).
        y0, z0 = 3.7, -1.2
        h, f = yz_to_hf(y0, z0)
        cos_t = np.cos(np.pi / 4)
        sin_t = np.sin(np.pi / 4)
        y_back = h * sin_t - f * cos_t
        z_back = h * cos_t + f * sin_t
        assert abs(y_back - y0) < 1e-9
        assert abs(z_back - z0) < 1e-9

    def test_positions_hf_in_parsed_dict(self, parsed):
        # Regression guard: parser must populate positions_hf.
        assert "positions_hf" in parsed
        hf = parsed["positions_hf"]
        assert hf.shape == (len(parsed["positions"]), 2)
        # Cross-check first row against direct compute.
        exp_h, exp_f = yz_to_hf(parsed["positions"][0, 1], parsed["positions"][0, 2])
        assert abs(hf[0, 0] - exp_h) < 1e-9
        assert abs(hf[0, 1] - exp_f) < 1e-9

    def test_positions_hf_helper_matches_parsed(self, parsed):
        # ``positions_hf`` helper and the parser-cached array must agree.
        recomputed = positions_hf(parsed["positions"])
        assert np.allclose(recomputed, parsed["positions_hf"])


class TestPositionsLab:
    """
    Lab (beam-line) voxel-in-sample coordinates.

    Ported from Igor ``xmlMultiIndex.ipf:4084-4092``::

        XX = -(Xsample)
        YY = -(Ysample)
        ZZ = -(Zsample) + depth     // depth only for wire scans
        HH = YZ2H(YY, ZZ)
        FF = YZ2F(YY, ZZ)

    The sign flip turns stage position into position *inside* the sample.
    Getting it wrong flips the map, and folding depth into the wrong axis
    would silently distort wire-scan reconstructions, so both are pinned
    explicitly here.
    """

    def test_negates_stage_position(self):
        pos = np.array([[10.0, 20.0, 30.0], [-5.0, 2.0, 7.0]])
        lab = positions_lab(pos)
        assert np.allclose(lab[:, 0], [-10.0, 5.0])
        assert np.allclose(lab[:, 1], [-20.0, -2.0])
        assert np.allclose(lab[:, 2], [-30.0, -7.0])

    def test_depth_folded_into_z_only(self):
        # Igor adds depth to ZZ; X and Y must be untouched.
        pos = np.array([[10.0, 20.0, 30.0]])
        lab = positions_lab(pos, np.array([25.0]))
        assert np.allclose(lab[:, 2], [-30.0 + 25.0])
        assert np.allclose(lab[:, 0], [-10.0])
        assert np.allclose(lab[:, 1], [-20.0])

    def test_nan_depth_treated_as_zero(self):
        # Igor guard: numtype(depthRaw) ? 0 : depthRaw
        pos = np.array([[10.0, 20.0, 30.0]])
        lab_nan = positions_lab(pos, np.array([np.nan]))
        lab_none = positions_lab(pos)
        assert np.allclose(lab_nan, lab_none)

    def test_hf_derived_from_negated_and_depth_corrected_yz(self):
        # HH/FF must come from YY/ZZ (post-negation, post-depth), which is
        # NOT the same as negating the stage-frame H/F.
        pos = np.array([[10.0, 20.0, 30.0]])
        depths = np.array([25.0])
        lab = positions_lab(pos, depths)
        exp_h, exp_f = yz_to_hf(lab[0, 1], lab[0, 2])
        assert abs(lab[0, 3] - exp_h) < 1e-9
        assert abs(lab[0, 4] - exp_f) < 1e-9
        # Guard against the tempting-but-wrong "lab H == -stage H" shortcut.
        stage_h = positions_hf(pos)[0, 0]
        assert abs(lab[0, 3] - (-stage_h)) > 1e-6

    def test_lab_hf_equals_negated_stage_hf_without_depth(self):
        # With no depth term the rotation is linear, so lab H/F collapse
        # to the negated stage H/F.  Pins the linearity assumption.
        pos = np.array([[10.0, 20.0, 30.0], [-5.0, 2.0, 7.0]])
        lab = positions_lab(pos)
        stage = positions_hf(pos)
        assert np.allclose(lab[:, 3], -stage[:, 0])
        assert np.allclose(lab[:, 4], -stage[:, 1])

    def test_shape_and_parsed_dict(self, parsed):
        # Regression guard: parser must populate positions_lab.
        assert "positions_lab" in parsed
        lab = parsed["positions_lab"]
        assert lab.shape == (len(parsed["positions"]), 5)
        recomputed = positions_lab(parsed["positions"], parsed["depths"])
        assert np.allclose(recomputed, lab, equal_nan=True)
