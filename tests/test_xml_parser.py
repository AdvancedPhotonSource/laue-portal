"""
Tests for laue_portal.analysis.xml_parser module.

Uses the sample output.xml in the project root.
"""

import os
import sys
import numpy as np
import pytest

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from laue_portal.analysis.xml_parser import (
    parse_indexing_xml,
    get_step_peaks,
    get_all_indexed_peaks,
)

# Path to the sample XML file in the project root
SAMPLE_XML = os.path.join(project_root, "output.xml")


@pytest.fixture
def parsed():
    """Parse the sample XML once for reuse across tests."""
    assert os.path.exists(SAMPLE_XML), f"Sample XML not found: {SAMPLE_XML}"
    return parse_indexing_xml(SAMPLE_XML)


# ---------------------------------------------------------------------------
# parse_indexing_xml tests
# ---------------------------------------------------------------------------

class TestParseIndexingXml:

    def test_returns_dict(self, parsed):
        assert isinstance(parsed, dict)

    def test_required_keys_present(self, parsed):
        expected_keys = [
            "positions", "depths", "energies", "scan_nums",
            "n_patterns", "recip_lattices", "rms_errors",
            "goodnesses", "n_indexed", "space_group",
            "lattice_params", "structure_desc", "_steps",
        ]
        for key in expected_keys:
            assert key in parsed, f"Missing key: {key}"

    def test_step_count(self, parsed):
        """output.xml has multiple steps -- verify we parse them all."""
        n = len(parsed["positions"])
        assert n >= 4, f"Expected at least 4 steps, got {n}"

    def test_positions_shape(self, parsed):
        pos = parsed["positions"]
        assert pos.ndim == 2
        assert pos.shape[1] == 3  # Xsample, Ysample, Zsample

    def test_positions_values(self, parsed):
        """First step has Xsample=2490.0, Ysample=-4030.71, Zsample=-9263.71."""
        pos = parsed["positions"]
        assert abs(pos[0, 0] - 2490.0) < 0.1
        assert abs(pos[0, 1] - (-4030.71)) < 0.1
        assert abs(pos[0, 2] - (-9263.71)) < 0.1

    def test_depths_nan_when_absent(self, parsed):
        """output.xml steps have depth='nan'."""
        assert np.all(np.isnan(parsed["depths"]))

    def test_energies(self, parsed):
        energies = parsed["energies"]
        assert np.all(np.abs(energies - 19.9999) < 0.01)

    def test_scan_nums(self, parsed):
        scan_nums = parsed["scan_nums"]
        assert scan_nums[0] == 274038

    def test_n_patterns(self, parsed):
        """First step has Npatterns=4."""
        assert parsed["n_patterns"][0] == 4

    def test_recip_lattices_shape(self, parsed):
        rl = parsed["recip_lattices"]
        n = len(parsed["positions"])
        assert rl.shape == (n, 3, 3)

    def test_recip_lattice_values(self, parsed):
        """First step, first pattern astar = [-13.5059076, 5.1823194, -5.6106001]."""
        rl = parsed["recip_lattices"]
        astar_0 = rl[0, 0, :]  # First row = astar
        assert abs(astar_0[0] - (-13.5059076)) < 0.001
        assert abs(astar_0[1] - 5.1823194) < 0.001
        assert abs(astar_0[2] - (-5.6106001)) < 0.001

    def test_rms_errors(self, parsed):
        """First step best pattern has rms_error=0.00592."""
        assert abs(parsed["rms_errors"][0] - 0.00592) < 0.0001

    def test_goodnesses(self, parsed):
        """First step best pattern has goodness=141.459."""
        assert abs(parsed["goodnesses"][0] - 141.459) < 0.01

    def test_n_indexed(self, parsed):
        """First step best pattern has Nindexed=9."""
        assert parsed["n_indexed"][0] == 9

    def test_crystal_structure(self, parsed):
        assert parsed["space_group"] == 225
        assert parsed["structure_desc"] == "Aluminum"
        lp = parsed["lattice_params"]
        assert len(lp) == 6
        assert abs(lp[0] - 0.40495) < 0.0001  # a
        assert abs(lp[3] - 90.0) < 0.1  # alpha


# ---------------------------------------------------------------------------
# get_step_peaks tests
# ---------------------------------------------------------------------------

class TestGetStepPeaks:

    def test_returns_dict(self, parsed):
        result = get_step_peaks(parsed, 0)
        assert isinstance(result, dict)

    def test_pixel_positions(self, parsed):
        result = get_step_peaks(parsed, 0)
        pp = result["pixel_positions"]
        assert pp is not None
        assert pp.ndim == 2
        assert pp.shape[1] == 2

    def test_q_vectors(self, parsed):
        result = get_step_peaks(parsed, 0)
        qv = result["q_vectors"]
        assert qv is not None
        assert qv.ndim == 2
        assert qv.shape[1] == 3

    def test_n_peaks(self, parsed):
        """First step has Npeaks=97."""
        result = get_step_peaks(parsed, 0)
        assert result["n_peaks"] == 97

    def test_patterns(self, parsed):
        """First step has 4 patterns."""
        result = get_step_peaks(parsed, 0)
        assert len(result["patterns"]) == 4

    def test_pattern_hkl(self, parsed):
        """First step, pattern 0 has 9 indexed peaks."""
        result = get_step_peaks(parsed, 0)
        pat0 = result["patterns"][0]
        assert pat0["hkl"].shape == (9, 3)
        assert pat0["peak_indices"] is not None
        assert len(pat0["peak_indices"]) == 9

    def test_out_of_range_returns_none(self, parsed):
        result = get_step_peaks(parsed, 9999)
        assert result is None

    def test_negative_index_returns_none(self, parsed):
        result = get_step_peaks(parsed, -1)
        assert result is None


# ---------------------------------------------------------------------------
# get_all_indexed_peaks tests
# ---------------------------------------------------------------------------

class TestGetAllIndexedPeaks:

    def test_returns_list(self, parsed):
        rows = get_all_indexed_peaks(parsed)
        assert isinstance(rows, list)

    def test_has_expected_keys(self, parsed):
        rows = get_all_indexed_peaks(parsed)
        assert len(rows) > 0
        row = rows[0]
        expected = [
            "step_index", "step_scan_num", "pattern_num",
            "h", "k", "l", "peak_index",
            "x_pixel", "y_pixel", "intensity", "integral",
            "qx", "qy", "qz",
            "rms_error", "goodness",
        ]
        for key in expected:
            assert key in row, f"Missing key: {key}"

    def test_total_rows(self, parsed):
        """Should have rows from all steps and all patterns."""
        rows = get_all_indexed_peaks(parsed)
        # First step: 4 patterns with 9+9+9+3 = 30 indexed peaks
        # Should have at least 30 rows (more from other steps)
        assert len(rows) >= 30

    def test_hkl_values(self, parsed):
        """First row should have valid hkl integers."""
        rows = get_all_indexed_peaks(parsed)
        row = rows[0]
        assert isinstance(row["h"], int)
        assert isinstance(row["k"], int)
        assert isinstance(row["l"], int)

    def test_pixel_coordinates(self, parsed):
        """Pixel coordinates should be present and reasonable."""
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
        with pytest.raises(Exception):
            parse_indexing_xml("/nonexistent/path.xml")

    def test_all_steps_parseable(self, parsed):
        """Every step should be parseable via get_step_peaks."""
        n = len(parsed["positions"])
        for i in range(n):
            result = get_step_peaks(parsed, i)
            assert result is not None, f"Step {i} returned None"
