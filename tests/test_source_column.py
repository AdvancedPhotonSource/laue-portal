"""
Temporary unit tests for the condensed "Source" column on the Peak Indexings table
and the navbar Mask Reconstructions removal.

Tests cover:
1. Column structure: Source column replaces scanNumber, recon_id, wirerecon_id
2. Data integrity: row data still contains the raw fields for the renderer
3. valueGetter expression: produces correct prefixed strings (SN/MR/WR)
4. SourceLinksRenderer: JS renderer exists and references correct URLs
5. Navbar: Mask Reconstructions link is commented out
6. End-to-end: _get_peakindexings with various data scenarios
"""

import sys
import os
import re
import tempfile
from unittest.mock import patch
import pytest
import datetime

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_wirerecon(scan_number=2, job_id=2):
    """Factory for a minimal WireRecon record."""
    import laue_portal.database.db_schema as db_schema
    return db_schema.WireRecon(
        scanNumber=scan_number,
        job_id=job_id,
        filefolder='/test/wire',
        filenamePrefix=['wire_prefix'],
        geoFile='/test/geo.xml',
        percent_brightest=0.5,
        wire_edges='0,100',
        depth_start=0.0,
        depth_end=10.0,
        depth_resolution=0.1,
        num_threads=4,
        memory_limit_mb=1024,
        scanPoints='1-2',
        scanPointslen=2,
        outputFolder='/test/wire_output',
        verbose=0,
    )


def _create_peakindex_with_wirerecon(scan_number=2, wirerecon_id=1, job_id=3):
    """Factory for a PeakIndex linked to a WireRecon (no mask recon)."""
    import laue_portal.database.db_schema as db_schema
    return db_schema.PeakIndex(
        scanNumber=scan_number,
        job_id=job_id,
        filefolder='tests/data/input',
        filenamePrefix=['test_file'],
        recon_id=None,
        wirerecon_id=wirerecon_id,
        threshold=250,
        thresholdRatio=-1,
        maxRfactor=0.5,
        boxsize=18,
        max_number=50,
        min_separation=40,
        peakShape='Lorentzian',
        scanPoints='1-2',
        scanPointslen=2,
        detectorCropX1=0,
        detectorCropX2=2047,
        detectorCropY1=0,
        detectorCropY2=2047,
        min_size=1.13,
        max_peaks=50,
        smooth=False,
        maskFile=None,
        indexKeVmaxCalc=17.2,
        indexKeVmaxTest=30.0,
        indexAngleTolerance=0.1,
        indexH=1,
        indexK=1,
        indexL=1,
        indexCone=72.0,
        energyUnit='keV',
        exposureUnit='sec',
        cosmicFilter=True,
        recipLatticeUnit='1/nm',
        latticeParametersUnit='nm',
        outputFolder='tests/data/output',
        geoFile='tests/data/geo/geoN.xml',
        crystFile='tests/data/crystal/Al.xtal',
        depth='2D',
        beamline='34ID-E',
    )


def _setup_db_with_peakindex(entities_fn):
    """
    Create a temp database, populate it via *entities_fn(session, engine)*,
    and return (engine, db_path).
    """
    import laue_portal.database.db_schema as db_schema
    import sqlalchemy
    from sqlalchemy.orm import Session

    tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    db_path = tmp.name
    tmp.close()

    engine = sqlalchemy.create_engine(f'sqlite:///{db_path}')
    db_schema.Base.metadata.create_all(engine)

    with Session(engine) as session:
        entities_fn(session, engine)
        session.commit()

    return engine, db_path


# ---------------------------------------------------------------------------
# 1. Column structure tests
# ---------------------------------------------------------------------------

class TestSourceColumnStructure:
    """Verify the column definitions produced by _get_peakindexings."""

    def _get_cols(self, engine, db_path):
        with patch('laue_portal.config.db_file', db_path):
            import lau_dash  # noqa: F401 – registers pages
            from laue_portal.pages.peakindexings import _get_peakindexings
            with patch('laue_portal.database.session_utils.get_engine', lambda: engine):
                cols, _ = _get_peakindexings()
        return cols

    def test_source_column_exists(self, empty_test_database):
        engine, db_path = empty_test_database
        cols = self._get_cols(engine, db_path)
        header_names = [c['headerName'] for c in cols]
        assert 'Source' in header_names, "A 'Source' column should be present"

    def test_old_columns_absent(self, empty_test_database):
        engine, db_path = empty_test_database
        cols = self._get_cols(engine, db_path)
        header_names = [c['headerName'] for c in cols]
        assert 'Scan ID' not in header_names, "'Scan ID' column should no longer exist"
        assert 'Recon ID' not in header_names, "'Recon ID' column should no longer exist"
        assert 'Wire Recon ID' not in header_names, "'Wire Recon ID' column should no longer exist"

    def test_source_column_uses_renderer(self, empty_test_database):
        engine, db_path = empty_test_database
        cols = self._get_cols(engine, db_path)
        source_col = next(c for c in cols if c['headerName'] == 'Source')
        assert source_col['cellRenderer'] == 'SourceLinksRenderer'

    def test_source_column_has_value_getter(self, empty_test_database):
        engine, db_path = empty_test_database
        cols = self._get_cols(engine, db_path)
        source_col = next(c for c in cols if c['headerName'] == 'Source')
        assert 'valueGetter' in source_col
        vg = source_col['valueGetter']['function']
        # Should reference all three ID fields
        assert 'scanNumber' in vg
        assert 'recon_id' in vg
        assert 'wirerecon_id' in vg

    def test_source_column_is_only_inserted_once(self, empty_test_database):
        engine, db_path = empty_test_database
        cols = self._get_cols(engine, db_path)
        source_count = sum(1 for c in cols if c.get('headerName') == 'Source')
        assert source_count == 1, "Source column should appear exactly once"

    def test_column_order(self, empty_test_database):
        """Source should appear right after Peak Indexing ID."""
        engine, db_path = empty_test_database
        cols = self._get_cols(engine, db_path)
        headers = [c['headerName'] for c in cols]
        pi_idx = headers.index('Peak Indexing ID')
        src_idx = headers.index('Source')
        assert src_idx == pi_idx + 1, (
            f"Source (idx {src_idx}) should immediately follow "
            f"Peak Indexing ID (idx {pi_idx})"
        )

    def test_remaining_columns_present(self, empty_test_database):
        engine, db_path = empty_test_database
        cols = self._get_cols(engine, db_path)
        headers = [c['headerName'] for c in cols]
        for expected in ['Peak Indexing ID', 'Source', 'Points', 'Author', 'Notes', 'Box', 'Date', 'Status']:
            assert expected in headers, f"Expected column '{expected}' not found"


# ---------------------------------------------------------------------------
# 2. Row data tests  (raw fields still present for the renderer)
# ---------------------------------------------------------------------------

class TestSourceColumnRowData:
    """Row data must still carry scanNumber, recon_id, wirerecon_id."""

    def _get_records(self, engine, db_path):
        with patch('laue_portal.config.db_file', db_path):
            import lau_dash  # noqa
            from laue_portal.pages.peakindexings import _get_peakindexings
            with patch('laue_portal.database.session_utils.get_engine', lambda: engine):
                _, records = _get_peakindexings()
        return records

    def test_mask_recon_row_data(self, test_peakindex_database):
        """PeakIndex linked to a mask recon should have recon_id in row data."""
        engine, db_path, meta, job, recon, pi = test_peakindex_database
        with patch('laue_portal.database.session_utils.get_engine', lambda: engine):
            from sqlalchemy.orm import Session
            with Session(engine) as s:
                s.add(meta)
                s.add(job)
                s.add(recon)
                s.flush()  # flush so recon gets its auto-generated recon_id
                pi.recon_id = recon.recon_id  # link PeakIndex to the Recon
                s.add(pi)
                s.commit()

        records = self._get_records(engine, db_path)
        assert len(records) >= 1
        row = records[0]
        assert 'scanNumber' in row, "Row must contain scanNumber for the renderer"
        assert 'recon_id' in row, "Row must contain recon_id for the renderer"
        assert 'wirerecon_id' in row, "Row must contain wirerecon_id for the renderer"
        # For a mask-recon-linked PI, wirerecon_id should be None
        assert row['recon_id'] is not None
        assert row['wirerecon_id'] is None

    def test_wire_recon_row_data(self):
        """PeakIndex linked to a wire recon should have wirerecon_id in row data."""
        from tests.conftest import create_test_metadata, create_test_job, create_test_catalog

        def populate(session, engine):
            meta = create_test_metadata(scan_number=2)
            job_wr = create_test_job(scan_number=2)
            job_pi = create_test_job(scan_number=3)  # separate job for peakindex
            job_pi.job_id = 3
            catalog = create_test_catalog(scan_number=2)
            wr = _create_wirerecon(scan_number=2, job_id=2)
            session.add_all([meta, job_wr, job_pi, catalog, wr])
            session.flush()  # flush so wr gets its auto-generated wirerecon_id
            pi = _create_peakindex_with_wirerecon(scan_number=2, wirerecon_id=wr.wirerecon_id, job_id=3)
            session.add(pi)

        engine, db_path = _setup_db_with_peakindex(populate)
        try:
            with patch('laue_portal.config.db_file', db_path):
                import lau_dash  # noqa
                from laue_portal.pages.peakindexings import _get_peakindexings
                with patch('laue_portal.database.session_utils.get_engine', lambda: engine):
                    _, records = _get_peakindexings()

            assert len(records) >= 1
            row = records[0]
            assert row['wirerecon_id'] is not None
            assert row['recon_id'] is None
        finally:
            os.unlink(db_path)

    def test_empty_database_returns_no_rows(self, empty_test_database):
        engine, db_path = empty_test_database
        records = self._get_records(engine, db_path)
        assert records == []


# ---------------------------------------------------------------------------
# 3. valueGetter expression correctness (evaluated in Python as proxy)
# ---------------------------------------------------------------------------

class TestValueGetterExpression:
    """
    Evaluate the JS valueGetter expression in Python to confirm the string
    it would produce for filtering/sorting.
    """

    @staticmethod
    def _eval_valuegetter(scan_number, recon_id, wirerecon_id):
        """
        Replicate the JS valueGetter logic in Python.
        The JS expression is:
            (params.data.scanNumber != null ? 'SN' + params.data.scanNumber : '') +
            (params.data.recon_id != null ? ' MR' + params.data.recon_id : '') +
            (params.data.wirerecon_id != null ? ' WR' + params.data.wirerecon_id : '')
            || 'Unlinked'
        """
        parts = ''
        if scan_number is not None:
            parts += f'SN{scan_number}'
        if recon_id is not None:
            parts += f' MR{recon_id}'
        if wirerecon_id is not None:
            parts += f' WR{wirerecon_id}'
        return parts.strip() if parts.strip() else 'Unlinked'

    def test_scan_and_mask_recon(self):
        result = self._eval_valuegetter(276994, 3, None)
        assert result == 'SN276994 MR3'

    def test_scan_and_wire_recon(self):
        result = self._eval_valuegetter(276994, None, 1)
        assert result == 'SN276994 WR1'

    def test_scan_only(self):
        result = self._eval_valuegetter(276994, None, None)
        assert result == 'SN276994'

    def test_unlinked(self):
        result = self._eval_valuegetter(None, None, None)
        assert result == 'Unlinked'

    def test_mutual_exclusivity_assumed(self):
        """recon_id and wirerecon_id should not both be set, but if they are
        the expression still produces a valid string."""
        result = self._eval_valuegetter(100, 5, 7)
        assert 'SN100' in result
        assert 'MR5' in result
        assert 'WR7' in result


# ---------------------------------------------------------------------------
# 4. JS renderer existence and correctness
# ---------------------------------------------------------------------------

class TestSourceLinksRendererJS:
    """Static analysis of the SourceLinksRenderer in customAgGridFunctions.js."""

    JS_PATH = os.path.join(project_root, 'assets', 'customAgGridFunctions.js')

    @pytest.fixture(autouse=True)
    def _load_js(self):
        with open(self.JS_PATH) as f:
            self.js_content = f.read()

    def test_renderer_defined(self):
        assert 'dagcomponentfuncs.SourceLinksRenderer' in self.js_content

    def test_scan_link_url(self):
        assert "'/scan?scan_id='" in self.js_content or \
               "'/scan?scan_id=' + data.scanNumber" in self.js_content, \
               "SourceLinksRenderer should link to /scan?scan_id="

    def test_recon_link_url(self):
        assert "'/reconstruction?recon_id=' + data.recon_id" in self.js_content, \
               "SourceLinksRenderer should link to /reconstruction?recon_id="

    def test_wire_recon_link_url(self):
        assert "'/wire_reconstruction?wirerecon_id=' + data.wirerecon_id" in self.js_content, \
               "SourceLinksRenderer should link to /wire_reconstruction?wirerecon_id="

    def test_sn_prefix_in_renderer(self):
        assert "'SN' + data.scanNumber" in self.js_content

    def test_mr_prefix_in_renderer(self):
        assert "'MR' + data.recon_id" in self.js_content

    def test_wr_prefix_in_renderer(self):
        assert "'WR' + data.wirerecon_id" in self.js_content

    def test_unlinked_fallback(self):
        assert "'Unlinked'" in self.js_content


# ---------------------------------------------------------------------------
# 5. Navbar tests
# ---------------------------------------------------------------------------

class TestNavbar:
    """Verify Mask Reconstructions is commented out of the navbar."""

    NAVBAR_PATH = os.path.join(project_root, 'laue_portal', 'components', 'navbar.py')

    @pytest.fixture(autouse=True)
    def _load_navbar(self):
        with open(self.NAVBAR_PATH) as f:
            self.navbar_content = f.read()

    def test_mask_recon_commented_out(self):
        """The Mask Reconstructions nav link should be commented out."""
        for line in self.navbar_content.splitlines():
            if 'Mask Reconstructions' in line:
                stripped = line.lstrip()
                assert stripped.startswith('#'), (
                    "The 'Mask Reconstructions' navbar entry should be commented out"
                )
                return
        pytest.fail("'Mask Reconstructions' not found in navbar.py at all")

    def test_other_nav_items_still_active(self):
        """Scans, Wire Reconstructions, Indexations, Run Monitor should remain."""
        for label in ['Scans', 'Wire Reconstructions', 'Indexations', 'Run Monitor']:
            # Find lines that contain the label and are NOT commented out
            found = False
            for line in self.navbar_content.splitlines():
                if label in line and not line.lstrip().startswith('#'):
                    found = True
                    break
            assert found, f"'{label}' should still be active in the navbar"


# ---------------------------------------------------------------------------
# 6. End-to-end _get_peakindexings smoke tests
# ---------------------------------------------------------------------------

class TestGetPeakindexingsSmoke:
    """Full round-trip tests calling _get_peakindexings against a temp DB."""

    def test_with_mask_recon_peakindex(self, test_peakindex_database):
        engine, db_path, meta, job, recon, pi = test_peakindex_database

        with patch('laue_portal.database.session_utils.get_engine', lambda: engine):
            from sqlalchemy.orm import Session
            with Session(engine) as s:
                s.add(meta)
                s.add(job)
                s.add(recon)
                s.flush()  # flush so recon gets its auto-generated recon_id
                pi.recon_id = recon.recon_id  # link PeakIndex to the Recon
                s.add(pi)
                s.commit()

        with patch('laue_portal.config.db_file', db_path):
            import lau_dash  # noqa
            from laue_portal.pages.peakindexings import _get_peakindexings
            with patch('laue_portal.database.session_utils.get_engine', lambda: engine):
                cols, records = _get_peakindexings()

        # Columns
        headers = [c['headerName'] for c in cols]
        assert 'Source' in headers
        assert 'Scan ID' not in headers
        assert 'Recon ID' not in headers
        assert 'Wire Recon ID' not in headers

        # Records
        assert len(records) == 1
        row = records[0]
        assert row['scanNumber'] == 1
        assert row['recon_id'] is not None
        assert row['wirerecon_id'] is None

    def test_empty_database(self, empty_test_database):
        engine, db_path = empty_test_database

        with patch('laue_portal.config.db_file', db_path):
            import lau_dash  # noqa
            from laue_portal.pages.peakindexings import _get_peakindexings
            with patch('laue_portal.database.session_utils.get_engine', lambda: engine):
                cols, records = _get_peakindexings()

        assert isinstance(cols, list) and len(cols) > 0
        assert records == []

    def test_callback_wrong_path_raises(self, empty_test_database):
        from dash.exceptions import PreventUpdate
        engine, db_path = empty_test_database
        with patch('laue_portal.config.db_file', db_path):
            import lau_dash  # noqa
            from laue_portal.pages.peakindexings import get_peakindexings
            with pytest.raises(PreventUpdate):
                get_peakindexings('/wrong_path')
