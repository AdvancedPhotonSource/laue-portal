"""White-beam acquisition metadata must not replace indexing energy cutoffs."""

from unittest.mock import patch

import dash
from sqlalchemy.orm import Session

import lau_dash  # noqa: F401
from laue_portal.config import PEAKINDEX_DEFAULTS
from laue_portal.pages import create_peakindexing as page
from laue_portal.pages import create_wire_reconstruction as wire_page
from tests.conftest import create_test_metadata
from tests.run_support import make_engine


def test_loading_real_scan_preserves_configured_indexing_cutoffs(tmp_path, monkeypatch):
    engine = make_engine(tmp_path, monkeypatch)
    with Session(engine) as session:
        scan = create_test_metadata(277820)
        scan.source_energy = 11.099141253769188
        session.add(scan)
        session.commit()
    with patch.object(page, "set_peakindex_form_props") as setter, patch.object(page, "set_props"):
        page.load_scan_data_from_url("http://localhost/create-peakindexing?scan_id=277820")
    form = setter.call_args.args[0]
    assert form.index_kev_max_calc == PEAKINDEX_DEFAULTS["indexKeVmaxCalc"]
    assert form.index_kev_max_test == PEAKINDEX_DEFAULTS["indexKeVmaxTest"]
    engine.dispose()


def test_loading_scan_keeps_explicit_reconstruction_subset(tmp_path, monkeypatch):
    engine = make_engine(tmp_path, monkeypatch)
    monkeypatch.setitem(wire_page.WIRERECON_DEFAULTS, "scanPoints", "2")
    with Session(engine) as session:
        session.add(create_test_metadata(277820))
        session.commit()
    with patch.object(wire_page, "set_wire_recon_form_props") as setter, patch.object(wire_page, "set_props"):
        result = wire_page.load_scan_data_from_url("http://localhost/create-wire-reconstruction?scan_id=277820")
    assert setter.call_args.args[0].scan_points == "2"
    assert result is dash.no_update
    engine.dispose()
