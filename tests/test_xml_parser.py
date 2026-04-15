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
    get_all_indexed_peaks,
    get_step_peaks,
    parse_indexing_xml,
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
