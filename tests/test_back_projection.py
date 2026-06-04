"""
Tests for the back-projection / detector-geometry stack:

  * ``laue_portal.analysis.geometry`` -- DetectorGeometry, parse_geometry_xml,
    rho_from_R, resolve_geometry_for_indexing.
  * ``laue_portal.analysis.back_projection`` -- pixel_to_xyz / xyz_to_pixel /
    q_to_pixel round-trips and the full ``build_step_overlay`` pipeline.

These tests do not require a Dash server.
"""

from __future__ import annotations

import os
import sys
import textwrap

import numpy as np
import pytest

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from laue_portal.analysis.back_projection import (  # noqa: E402
    ROI,
    StepOverlay,
    build_step_overlay,
    full_to_roi,
    pixel_to_xyz,
    q_to_pixel,
    q_to_pixel_batch,
    xyz_to_pixel,
)
from laue_portal.analysis.geometry import (  # noqa: E402
    extract_geo_paths_from_indexing_xml,
    parse_geometry_xml,
    resolve_geometry_for_indexing,
    rho_from_R,
)
from laue_portal.analysis.xml_parser import parse_indexing_xml  # noqa: E402

# ---------------------------------------------------------------------------
# Synthetic geometry fixture: writes a tiny geoN-style XML next to a
# minimal indexed XML in a temp dir so the tests don't depend on the
# project-wide test data.
# ---------------------------------------------------------------------------


_GEO_XML = textwrap.dedent(
    """\
    <?xml version="1.0" encoding="UTF-8" ?>
    <geoN xmlns="http://sector34.xray.aps.anl.gov/34ide/geoN">
      <Sample>
        <Origin unit="micron">0 0 0</Origin>
        <R unit="radian">0 0 0</R>
      </Sample>
      <Detectors Ndetectors="1">
        <Detector N="0">
          <Npixels>2048 2048</Npixels>
          <size unit="mm">409.6 409.6</size>
          <R unit="radian">0 0 0</R>
          <P unit="mm">0 0 500</P>
          <ID>SYN-DET</ID>
        </Detector>
      </Detectors>
    </geoN>
    """
)


@pytest.fixture
def syn_geo_path(tmp_path):
    p = tmp_path / "geoN_syn.xml"
    p.write_text(_GEO_XML)
    return str(p)


@pytest.fixture
def syn_geom(syn_geo_path):
    return parse_geometry_xml(syn_geo_path)


@pytest.fixture
def syn_det(syn_geom):
    return syn_geom.detectors[0]


# ===========================================================================
# rho_from_R
# ===========================================================================


class TestRhoFromR:
    def test_zero_vector_is_identity(self):
        np.testing.assert_array_equal(rho_from_R(np.zeros(3)), np.eye(3))

    def test_90deg_about_z(self):
        rho = rho_from_R([0, 0, np.pi / 2])
        # Rotating (1,0,0) about +Z by 90° should give (0, 1, 0)
        np.testing.assert_allclose(rho @ [1, 0, 0], [0, 1, 0], atol=1e-12)

    @pytest.mark.parametrize(
        "R",
        [
            [0.1, -0.2, 0.3],
            [-1.2, -1.21, -1.22],  # representative 34ID-E detector
            [np.pi, 0, 0],
            [0.0001, 0.0, 0.0],
        ],
    )
    def test_orthonormal_and_unit_det(self, R):
        rho = rho_from_R(R)
        np.testing.assert_allclose(rho @ rho.T, np.eye(3), atol=1e-12)
        assert np.isclose(np.linalg.det(rho), 1.0, atol=1e-12)


# ===========================================================================
# DetectorGeometry / parse_geometry_xml
# ===========================================================================


class TestParseGeometryXml:
    def test_parses_synthetic(self, syn_geom):
        assert len(syn_geom.detectors) == 1
        d = syn_geom.detectors[0]
        assert d.detector_id == "SYN-DET"
        assert d.Nx == 2048 and d.Ny == 2048
        np.testing.assert_allclose(d.P, [0, 0, 500])
        np.testing.assert_allclose(d.R, [0, 0, 0])
        np.testing.assert_allclose(d.rho, np.eye(3))

    def test_detector_by_id_normalises(self, syn_geom):
        # Case + surrounding whitespace insensitive.
        assert syn_geom.detector_by_id("syn-det  ") is syn_geom.detectors[0]
        assert syn_geom.detector_by_id("missing") is None

    def test_lru_cache_keyed_on_mtime(self, tmp_path):
        path = tmp_path / "geo.xml"
        path.write_text(_GEO_XML)
        g1 = parse_geometry_xml(str(path))
        # Rewrite the file and manually advance mtime so the cache key
        # changes regardless of filesystem timestamp resolution.
        path.write_text(_GEO_XML.replace("SYN-DET", "RENAMED-DET"))
        st = os.stat(path)
        os.utime(path, ns=(st.st_atime_ns + 10_000_000_000, st.st_mtime_ns + 10_000_000_000))
        g2 = parse_geometry_xml(str(path))
        assert g2.detectors[0].detector_id == "RENAMED-DET"
        assert g1.detectors[0].detector_id == "SYN-DET"


# ===========================================================================
# pixel ↔ xyz round-trip
# ===========================================================================


class TestPixelXyzRoundTrip:
    @pytest.mark.parametrize(
        "px,py",
        [
            (1024.0, 1024.0),  # centre
            (0.0, 0.0),  # corner
            (2047.0, 2047.0),  # opposite corner
            (500.5, 300.25),  # arbitrary
        ],
    )
    def test_roundtrip(self, syn_det, px, py):
        xyz = pixel_to_xyz(syn_det, px, py)
        px2, py2 = xyz_to_pixel(syn_det, xyz)
        assert np.isclose(px, px2, atol=1e-9)
        assert np.isclose(py, py2, atol=1e-9)

    def test_center_pixel_is_on_axis(self, syn_det):
        """For a perpendicular detector at (0, 0, 500), centre pixel must
        sit on the optical axis."""
        xyz = pixel_to_xyz(syn_det, (syn_det.Nx - 1) / 2, (syn_det.Ny - 1) / 2)
        np.testing.assert_allclose(xyz, [0, 0, 500], atol=1e-9)


# ===========================================================================
# q_to_pixel
# ===========================================================================


class TestQtoPixel:
    def test_center_pixel_q_roundtrips(self, syn_det):
        """A reflection that produces the centre pixel should have a
        well-defined Q-vector; back-projecting that Q must return the
        same pixel."""
        cx = (syn_det.Nx - 1) / 2
        cy = (syn_det.Ny - 1) / 2
        # kf for this pixel:
        kf = pixel_to_xyz(syn_det, cx, cy)
        kf = kf / np.linalg.norm(kf)
        ki = np.array([0.0, 0.0, 1.0])
        q = kf - ki
        # If kf == ki (forward-scattered) the q vector is zero -- skip.
        if np.linalg.norm(q) < 1e-9:
            # For a perpendicular flat detector centred on the beam, the
            # "centre pixel" is exactly the forward-beam pixel and so it
            # has no associated reflection.  Use a slightly off-centre
            # pixel instead.
            cx, cy = cx + 50, cy + 100
            kf = pixel_to_xyz(syn_det, cx, cy)
            kf = kf / np.linalg.norm(kf)
            q = kf - ki
        px2, py2 = q_to_pixel(syn_det, q)
        assert np.isclose(px2, cx, atol=1e-6)
        assert np.isclose(py2, cy, atol=1e-6)

    def test_q_pointing_into_beam_returns_nan(self, syn_det):
        # qhat · -ki must be positive for a real reflection; the opposite
        # direction returns NaN.
        px, py = q_to_pixel(syn_det, [0.0, 0.0, -1.0])
        assert np.isnan(px) and np.isnan(py)

    def test_zero_q_returns_nan(self, syn_det):
        assert np.isnan(q_to_pixel(syn_det, [0.0, 0.0, 0.0])[0])

    def test_batch_matches_scalar(self, syn_det):
        qs = np.array(
            [
                [0.1, 0.0, -0.05],
                [0.0, 0.1, -0.05],
                [0.0, 0.0, 0.0],
                [0.2, 0.05, -0.1],
            ]
        )
        out_batch = q_to_pixel_batch(syn_det, qs)
        out_loop = np.array([q_to_pixel(syn_det, q) for q in qs])
        np.testing.assert_allclose(out_batch, out_loop, equal_nan=True)


# ===========================================================================
# ROI conversion
# ===========================================================================


class TestRoi:
    def test_identity_when_default(self):
        px = np.array([100.0, 200.0])
        py = np.array([300.0, 400.0])
        roi = ROI(startx=0, groupx=1, starty=0, groupy=1)
        rx, ry = full_to_roi(px, py, roi)
        np.testing.assert_allclose(rx, px)
        np.testing.assert_allclose(ry, py)

    def test_binned(self):
        roi = ROI(startx=100, groupx=2, starty=200, groupy=4)
        px = np.array([100.0, 300.0])  # full-chip
        py = np.array([200.0, 600.0])
        rx, ry = full_to_roi(px, py, roi)
        # Manual: (100 - 100 - 0.5)/2 = -0.25 ; (300-100-0.5)/2 = 99.75
        # Y: (200-200-1.5)/4 = -0.375 ; (600-200-1.5)/4 = 99.625
        np.testing.assert_allclose(rx, [-0.25, 99.75])
        np.testing.assert_allclose(ry, [-0.375, 99.625])


# ===========================================================================
# extract_geo_paths_from_indexing_xml + resolve_geometry_for_indexing
# ===========================================================================


_INDEXED_XML_HEAD = textwrap.dedent(
    """\
    <?xml version="1.0"?>
    <AllSteps>
      <step>
        <Xsample>0</Xsample><Ysample>0</Ysample><Zsample>0</Zsample>
        <depth>nan</depth><energy>15.0</energy>
        <detector>
          <inputImage>foo.h5</inputImage>
          <detectorID>SYN-DET</detectorID>
          <Nx>2048</Nx><Ny>2048</Ny>
          <geoFile>{geo_path}</geoFile>
          <ROI startx="0" endx="2047" groupx="1" starty="0" endy="2047" groupy="1"> </ROI>
          <peaksXY Npeaks="0">
            <Xpixel></Xpixel><Ypixel></Ypixel><Intens></Intens><Integral></Integral>
            <hwhmX/><hwhmY/><tilt/><chisq/>
            <Qx/><Qy/><Qz/>
          </peaksXY>
        </detector>
      </step>
    </AllSteps>
    """
)


def test_extract_geo_paths_and_resolve(tmp_path, syn_geo_path):
    indexed = tmp_path / "indexed.xml"
    indexed.write_text(_INDEXED_XML_HEAD.format(geo_path=syn_geo_path))
    paths = extract_geo_paths_from_indexing_xml(str(indexed))
    assert paths == [syn_geo_path]

    geom = resolve_geometry_for_indexing(str(indexed))
    assert geom is not None
    assert geom.detectors[0].detector_id == "SYN-DET"


def test_resolve_returns_none_when_geo_missing(tmp_path):
    indexed = tmp_path / "indexed.xml"
    indexed.write_text(_INDEXED_XML_HEAD.format(geo_path="/does/not/exist.xml"))
    geom = resolve_geometry_for_indexing(str(indexed))
    assert geom is None


# ===========================================================================
# build_step_overlay: end-to-end against synthetic data
# ===========================================================================


def _make_synthetic_indexed_xml(tmp_path, geo_path):
    """Construct a single-step indexed XML with one indexed reflection
    whose hkl back-projects to a known pixel.  We choose the pixel first,
    derive the corresponding Q-vector, then set hkl = (1, 0, 0) and
    astar = q exactly so q = a* · 1 + b* · 0 + c* · 0 = a*.
    """
    # Pick a target pixel and derive q from it for our synthetic detector.
    target_px = 700.0
    target_py = 850.0

    det = parse_geometry_xml(geo_path).detectors[0]
    kf = pixel_to_xyz(det, target_px, target_py)
    kf /= np.linalg.norm(kf)
    q = kf - np.array([0.0, 0.0, 1.0])
    # The recip_lattice in xml_parser is stored row-major: astar/bstar/cstar
    # as rows. So q = h*a* + k*b* + l*c*; with hkl=(1,0,0) -> q = a*.
    astar = q
    bstar = np.zeros(3)
    cstar = np.zeros(3)

    # Add one extra measured peak that is NOT indexed.
    extra_px, extra_py = 1500.0, 200.0

    template = f"""<?xml version="1.0"?>
<AllSteps>
  <step>
    <Xsample>0</Xsample><Ysample>0</Ysample><Zsample>0</Zsample>
    <depth>nan</depth><energy>15.0</energy>
    <detector>
      <inputImage>foo.h5</inputImage>
      <detectorID>SYN-DET</detectorID>
      <Nx>2048</Nx><Ny>2048</Ny>
      <geoFile>{geo_path}</geoFile>
      <ROI startx="0" endx="2047" groupx="1" starty="0" endy="2047" groupy="1"> </ROI>
      <peaksXY Npeaks="2" peakProgram="peaksearch">
        <Xpixel>{target_px} {extra_px}</Xpixel>
        <Ypixel>{target_py} {extra_py}</Ypixel>
        <Intens>1000 500</Intens>
        <Integral>0 0</Integral>
        <hwhmX>1 1</hwhmX><hwhmY>1 1</hwhmY>
        <tilt>0 0</tilt><chisq>0 0</chisq>
        <Qx>0 0</Qx><Qy>0 0</Qy><Qz>0 0</Qz>
      </peaksXY>
    </detector>
    <indexing indexProgram="euler" Nindexed="1" Npeaks="2" Npatterns="1"
              keVmaxCalc="30" keVmaxTest="30" angleTolerance="0.1"
              cone="72" hklPrefer="0 0 0" executionTime="0">
      <xtl>
        <structureDesc>Si</structureDesc>
        <xtlFile/>
        <SpaceGroup>227</SpaceGroup>
        <latticeParameters unit="nm">0.5431 0.5431 0.5431 90 90 90</latticeParameters>
      </xtl>
      <pattern num="0" Nindexed="1" rms_error="0.001" goodness="100">
        <recip_lattice unit="1/nm">
          <astar>{astar[0]} {astar[1]} {astar[2]}</astar>
          <bstar>{bstar[0]} {bstar[1]} {bstar[2]}</bstar>
          <cstar>{cstar[0]} {cstar[1]} {cstar[2]}</cstar>
        </recip_lattice>
        <hkl_s>
          <h>1</h><k>0</k><l>0</l>
          <PkIndex>0</PkIndex>
        </hkl_s>
      </pattern>
    </indexing>
  </step>
</AllSteps>
"""
    path = tmp_path / "indexed_syn.xml"
    path.write_text(template)
    return str(path), target_px, target_py, extra_px, extra_py


def test_build_step_overlay_end_to_end(tmp_path, syn_geo_path):
    indexed_path, tpx, tpy, expx, expy = _make_synthetic_indexed_xml(tmp_path, syn_geo_path)

    parsed = parse_indexing_xml(indexed_path)
    geom = resolve_geometry_for_indexing(indexed_path)
    overlay = build_step_overlay(parsed, 0, geom)
    assert isinstance(overlay, StepOverlay)
    assert overlay.detector_id == "SYN-DET"
    assert overlay.Nx == 2048

    # 2 measured peaks
    assert len(overlay.measured_xy) == 2
    np.testing.assert_allclose(overlay.measured_xy[0], [tpx, tpy], atol=1e-6)

    # 1 pattern, 1 reflection, predicted ≈ target
    assert len(overlay.patterns) == 1
    pat = overlay.patterns[0]
    assert len(pat.predicted_xy) == 1
    np.testing.assert_allclose(pat.predicted_xy[0], [tpx, tpy], atol=1e-4)

    # The first measured peak should be matched to that reflection
    assert pat.measured_index[0] == 0
    assert pat.match_distance[0] < 0.01

    # The extra peak should be flagged un-indexed
    assert overlay.measured_indexed_mask[0]
    assert not overlay.measured_indexed_mask[1]


def test_build_step_overlay_empty_step(tmp_path, syn_geo_path):
    """A step with no peaksXY produces a degenerate but non-crashing
    overlay (or None for completely empty steps)."""
    indexed = tmp_path / "empty.xml"
    indexed.write_text(_INDEXED_XML_HEAD.format(geo_path=syn_geo_path))
    parsed = parse_indexing_xml(str(indexed))
    geom = resolve_geometry_for_indexing(str(indexed))
    overlay = build_step_overlay(parsed, 0, geom)
    assert overlay is not None
    assert len(overlay.measured_xy) == 0
    assert len(overlay.patterns) == 0
