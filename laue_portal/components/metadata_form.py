import dash_bootstrap_components as dbc
from dash import html, set_props
from laue_portal.components.form_base import _stack, _field
from datetime import datetime
from laue_portal.database.db_utils import find_motor_group


metadata_form = dbc.Row(
                [
                    dbc.Accordion(
                        [
                        dbc.AccordionItem(
                            [
                                _stack(
                                    [
                                        _field("Scan Number", "scanNumber", size='md'),
                                        html.Div(
                                            [_field("Time Epoch", "time_epoch", size='lg')],
                                            style={'display': 'none'}
                                        ),
                                        _field("Time", "time", size='lg'),
                                        _field("User Name", "user_name", size='lg'),
                                    ]
                                ),
                            ],
                            title="Identifiers",
                        ),
                        dbc.AccordionItem(
                            [
                                _stack(
                                    [
                                        _field("Beam Bad", "source_beamBad", size='lg'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("CCD Shutter", "source_CCDshutter", size='lg'),
                                        _field("monoTransStatus", "source_monoTransStatus", size='lg'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Source Energy", "source_energy", size='lg'),
                                        _field("Units", "source_energy_unit", size='sm'),
                                        _field("Source Ring Current", "source_ringCurrent", size='lg'),
                                        _field("Units", "source_ringCurrent_unit", size='sm'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Source ID Gap", "source_IDgap", size='lg'),
                                        _field("Units", "source_IDgap_unit", size='sm'),
                                        _field("Source ID Taper", "source_IDtaper", size='lg'),
                                        _field("Units", "source_IDtaper_unit", size='sm'),
                                    ]
                                ),
                            ],
                            title="Source",
                        ),
                        dbc.AccordionItem(
                            [
                                _stack(
                                    [
                                        _field("Sample XYZ", "sample_XYZ", size='lg'),
                                        _field("Units", "sample_XYZ_unit", size='sm'),
                                        _field("Description", "sample_XYZ_desc", size='sm'),
                                    ]
                                ),
                            ],
                            title="Sample Positioner",
                        ),
                        dbc.AccordionItem(
                            [
                                _stack(
                                    [
                                        _field("Aperture XYZ", "knife-edge_XYZ", size='lg'),
                                        _field("Units", "knife-edge_XYZ_unit", size='sm'),
                                        _field("Description", "knife-edge_XYZ_desc", size='sm'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Scan", "knife-edge_knifeScan", size='lg'),
                                        _field("Units", "knife-edge_knifeScan_unit", size='sm'),
                                    ]
                                ),
                            ],
                            title="Aperture Positioner",
                        ),
                        dbc.AccordionItem(
                            [
                                dbc.Row(id="scan_accordions"),
                            ],
                            title="Scan",
                        ),
                        dbc.AccordionItem(
                            [
                                _stack(
                                    [
                                        _field("MDA File", "mda_file", size='lg'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Abort", "scanEnd_abort", size='lg'),
                                        html.Div(
                                            [_field("Time Epoch", "scanEnd_time_epoch", size='lg')],
                                            style={'display': 'none'}
                                        ),
                                        _field("Time", "scanEnd_time", size='lg'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Scan Duration", "scanEnd_scanDuration", size='lg'),
                                        _field("Units", "scanEnd_scanDuration_unit", size='sm'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Beam Bad", "scanEnd_source_beamBad", size='lg'),
                                        _field("Ring Current", "scanEnd_source_ringCurrent", size='lg'),
                                        _field("Units", "scanEnd_source_ringCurrent_unit", size='sm'),
                                    ]
                                ),
                            ],
                            title="Scan End",
                        ),
                        ],
                        always_open=True
                    ),
                    html.Div(id="hidden-scan-fields", children=[
                        *[
                            html.Div([
                                dbc.Input(id={"type": "hidden_scan_dim", "index": i}, type="hidden"),
                                dbc.Input(id={"type": "hidden_scan_npts", "index": i}, type="hidden"),
                                dbc.Input(id={"type": "hidden_scan_after", "index": i}, type="hidden"),
                                dbc.Input(id={"type": "hidden_scan_positioner1_PV", "index": i}, type="hidden"),
                                dbc.Input(id={"type": "hidden_scan_positioner1_ar", "index": i}, type="hidden"),
                                dbc.Input(id={"type": "hidden_scan_positioner1_mode", "index": i}, type="hidden"),
                                dbc.Input(id={"type": "hidden_scan_positioner1", "index": i}, type="hidden"),
                                dbc.Input(id={"type": "hidden_scan_positioner2_PV", "index": i}, type="hidden"),
                                dbc.Input(id={"type": "hidden_scan_positioner2_ar", "index": i}, type="hidden"),
                                dbc.Input(id={"type": "hidden_scan_positioner2_mode", "index": i}, type="hidden"),
                                dbc.Input(id={"type": "hidden_scan_positioner2", "index": i}, type="hidden"),
                                dbc.Input(id={"type": "hidden_scan_positioner3_PV", "index": i}, type="hidden"),
                                dbc.Input(id={"type": "hidden_scan_positioner3_ar", "index": i}, type="hidden"),
                                dbc.Input(id={"type": "hidden_scan_positioner3_mode", "index": i}, type="hidden"),
                                dbc.Input(id={"type": "hidden_scan_positioner3", "index": i}, type="hidden"),
                                dbc.Input(id={"type": "hidden_scan_positioner4_PV", "index": i}, type="hidden"),
                                dbc.Input(id={"type": "hidden_scan_positioner4_ar", "index": i}, type="hidden"),
                                dbc.Input(id={"type": "hidden_scan_positioner4_mode", "index": i}, type="hidden"),
                                dbc.Input(id={"type": "hidden_scan_positioner4", "index": i}, type="hidden"),
                                dbc.Input(id={"type": "hidden_scan_detectorTrig1_PV", "index": i}, type="hidden"),
                                dbc.Input(id={"type": "hidden_scan_detectorTrig1_VAL", "index": i}, type="hidden"),
                                dbc.Input(id={"type": "hidden_scan_detectorTrig2_PV", "index": i}, type="hidden"),
                                dbc.Input(id={"type": "hidden_scan_detectorTrig2_VAL", "index": i}, type="hidden"),
                                dbc.Input(id={"type": "hidden_scan_detectorTrig3_PV", "index": i}, type="hidden"),
                                dbc.Input(id={"type": "hidden_scan_detectorTrig3_VAL", "index": i}, type="hidden"),
                                dbc.Input(id={"type": "hidden_scan_detectorTrig4_PV", "index": i}, type="hidden"),
                                dbc.Input(id={"type": "hidden_scan_detectorTrig4_VAL", "index": i}, type="hidden"),
                                dbc.Input(id={"type": "hidden_scan_cpt", "index": i}, type="hidden"),
                            ])
                            for i in range(10)
                        ]
                    ], style={'display': 'none'}),
                ],
                style={'width': '100%', 'overflow-x': 'auto'}
        )


def _should_display(value):
    """Check if a value should be displayed (non-None, non-empty)."""
    return value is not None and str(value).strip() != ''


def _make_positioner_fields(scan_data, i, pos_num, read_only):
    """Build fields for a single positioner if any have values."""
    pv_attr = f'scan_positioner{pos_num}_PV'
    name_attr = f'scan_positioner{pos_num}'
    ar_attr = f'scan_positioner{pos_num}_ar'
    mode_attr = f'scan_positioner{pos_num}_mode'

    fields = []
    pv_val = getattr(scan_data, pv_attr)
    if _should_display(pv_val):
        fields.append(_field(f"Positioner {pos_num} PV",
                             {"type": pv_attr, "index": i}, size='md',
                             kwargs={'value': pv_val, 'readonly': read_only}))
        motor_group = find_motor_group(pv_val)
        fields.append(html.Div(f"{motor_group.capitalize()}", className="mb-3"))
    if _should_display(getattr(scan_data, name_attr)):
        fields.append(_field(f"Positioner {pos_num}",
                             {"type": name_attr, "index": i}, size='md',
                             kwargs={'value': getattr(scan_data, name_attr), 'readonly': read_only}))
    if _should_display(getattr(scan_data, ar_attr)):
        fields.append(_field(f"Positioner {pos_num} ar",
                             {"type": ar_attr, "index": i}, size='md',
                             kwargs={'value': getattr(scan_data, ar_attr), 'readonly': read_only}))
    if _should_display(getattr(scan_data, mode_attr)):
        fields.append(_field(f"Positioner {pos_num} mode",
                             {"type": mode_attr, "index": i}, size='md',
                             kwargs={'value': getattr(scan_data, mode_attr), 'readonly': read_only}))
    return fields


def _make_detector_fields(scan_data, i, det_num, read_only):
    """Build fields for a single detector trigger if any have values."""
    pv_attr = f'scan_detectorTrig{det_num}_PV'
    val_attr = f'scan_detectorTrig{det_num}_VAL'

    fields = []
    if _should_display(getattr(scan_data, pv_attr)):
        fields.append(_field(f"Detector Trig {det_num} PV",
                             {"type": pv_attr, "index": i}, size='md',
                             kwargs={'value': getattr(scan_data, pv_attr), 'readonly': read_only}))
    if _should_display(getattr(scan_data, val_attr)):
        fields.append(_field(f"Detector Trig {det_num} VAL",
                             {"type": val_attr, "index": i}, size='sm',
                             kwargs={'value': getattr(scan_data, val_attr), 'readonly': read_only}))
    return fields


def make_scan_accordion(i, scan_data, read_only=True):
    """
    Create a scan accordion with pre-populated values.
    Only includes fields that have non-None values.
    """
    stacks = []

    # General scan info
    general_fields = []
    if _should_display(scan_data.scan_npts):
        general_fields.append(_field("No. Points", {"type": "scan_npts", "index": i}, size='md',
                                   kwargs={'value': scan_data.scan_npts, 'readonly': read_only}))
    if _should_display(scan_data.scan_cpt):
        general_fields.append(_field("No. Points Completed", {"type": "scan_cpt", "index": i}, size='md',
                                   kwargs={'value': scan_data.scan_cpt, 'readonly': read_only}))
    if _should_display(scan_data.scan_after):
        general_fields.append(_field("After", {"type": "scan_after", "index": i}, size='md',
                                   kwargs={'value': scan_data.scan_after, 'readonly': read_only}))
    if general_fields:
        stacks.append(_stack(general_fields))

    # Positioners 1-4
    for pos_num in range(1, 5):
        pos_fields = _make_positioner_fields(scan_data, i, pos_num, read_only)
        if pos_fields:
            stacks.append(_stack(pos_fields))

    # Detector Triggers 1-4
    for det_num in range(1, 5):
        det_fields = _make_detector_fields(scan_data, i, det_num, read_only)
        if det_fields:
            stacks.append(_stack(det_fields))

    if stacks:
        return dbc.Accordion(
            [
                dbc.AccordionItem(
                    stacks,
                    title=f"Scan {scan_data.scan_dim}",
                ),
            ],
            id={"type": "scan_accordion", "index": i},
        )
    return html.Div()


def set_metadata_form_props(metadata, scans=None, read_only=True):
    set_props("scanNumber", {'value': metadata.scanNumber, 'readonly': read_only})

    set_props("time_epoch", {'value': metadata.time_epoch, 'readonly': read_only})
    time_value = metadata.time
    if isinstance(time_value, datetime):
        time_value = time_value.strftime('%Y-%m-%d, %H:%M:%S')
    set_props("time", {'value': time_value, 'readonly': read_only})
    set_props("user_name", {'value': metadata.user_name, 'readonly': read_only})

    set_props("source_beamBad", {'value': metadata.source_beamBad, 'readonly': read_only})
    set_props("source_CCDshutter", {'value': metadata.source_CCDshutter, 'readonly': read_only})
    set_props("source_monoTransStatus", {'value': metadata.source_monoTransStatus, 'readonly': read_only})
    set_props("source_energy_unit", {'value': metadata.source_energy_unit, 'readonly': read_only})
    set_props("source_energy", {'value': metadata.source_energy, 'readonly': read_only})
    set_props("source_IDgap_unit", {'value': metadata.source_IDgap_unit, 'readonly': read_only})
    set_props("source_IDgap", {'value': metadata.source_IDgap, 'readonly': read_only})
    set_props("source_IDtaper_unit", {'value': metadata.source_IDgap_unit, 'readonly': read_only})
    set_props("source_IDtaper", {'value': metadata.source_IDgap, 'readonly': read_only})
    set_props("source_ringCurrent_unit", {'value': metadata.source_ringCurrent_unit, 'readonly': read_only})
    set_props("source_ringCurrent", {'value': metadata.source_ringCurrent, 'readonly': read_only})

    set_props("sample_XYZ_unit", {'value': metadata.sample_XYZ_unit, 'readonly': read_only})
    set_props("sample_XYZ_desc", {'value': metadata.sample_XYZ_desc, 'readonly': read_only})
    set_props("sample_XYZ", {'value': metadata.sample_XYZ, 'readonly': read_only})

    set_props("knife-edge_XYZ_unit", {'value': metadata.knifeEdge_XYZ_unit, 'readonly': read_only})
    set_props("knife-edge_XYZ_desc", {'value': metadata.knifeEdge_XYZ_desc, 'readonly': read_only})
    set_props("knife-edge_XYZ", {'value': metadata.knifeEdge_XYZ, 'readonly': read_only})
    set_props("knife-edge_knifeScan_unit", {'value': metadata.knifeEdge_knifeScan_unit, 'readonly': read_only})
    set_props("knife-edge_knifeScan", {'value': metadata.knifeEdge_knifeScan, 'readonly': read_only})

    set_props("mda_file", {'value': metadata.mda_file, 'readonly': read_only})
    set_props("scanEnd_abort", {'value': metadata.scanEnd_abort, 'readonly': read_only})
    set_props("scanEnd_time_epoch", {'value': metadata.scanEnd_time_epoch, 'readonly': read_only})
    set_props("scanEnd_time", {'value': metadata.scanEnd_time, 'readonly': read_only})
    set_props("scanEnd_scanDuration_unit", {'value': metadata.scanEnd_scanDuration_unit, 'readonly': read_only})
    set_props("scanEnd_scanDuration", {'value': metadata.scanEnd_scanDuration, 'readonly': read_only})
    set_props("scanEnd_source_ringCurrent_unit", {'value': metadata.scanEnd_source_ringCurrent_unit, 'readonly': read_only})
    set_props("scanEnd_source_ringCurrent", {'value': metadata.scanEnd_source_ringCurrent, 'readonly': read_only})

    if scans:
        for i, scan in enumerate(scans):
            set_props({"type": "hidden_scan_dim", "index": i}, {'value': scan.scan_dim})
            set_props({"type": "hidden_scan_npts", "index": i}, {'value': scan.scan_npts})
            set_props({"type": "hidden_scan_after", "index": i}, {'value': scan.scan_after})
            set_props({"type": "hidden_scan_positioner1_PV", "index": i}, {'value': scan.scan_positioner1_PV})
            set_props({"type": "hidden_scan_positioner1_ar", "index": i}, {'value': scan.scan_positioner1_ar})
            set_props({"type": "hidden_scan_positioner1_mode", "index": i}, {'value': scan.scan_positioner1_mode})
            set_props({"type": "hidden_scan_positioner1", "index": i}, {'value': scan.scan_positioner1})
            set_props({"type": "hidden_scan_positioner2_PV", "index": i}, {'value': scan.scan_positioner2_PV})
            set_props({"type": "hidden_scan_positioner2_ar", "index": i}, {'value': scan.scan_positioner2_ar})
            set_props({"type": "hidden_scan_positioner2_mode", "index": i}, {'value': scan.scan_positioner2_mode})
            set_props({"type": "hidden_scan_positioner2", "index": i}, {'value': scan.scan_positioner2})
            set_props({"type": "hidden_scan_positioner3_PV", "index": i}, {'value': scan.scan_positioner3_PV})
            set_props({"type": "hidden_scan_positioner3_ar", "index": i}, {'value': scan.scan_positioner3_ar})
            set_props({"type": "hidden_scan_positioner3_mode", "index": i}, {'value': scan.scan_positioner3_mode})
            set_props({"type": "hidden_scan_positioner3", "index": i}, {'value': scan.scan_positioner3})
            set_props({"type": "hidden_scan_positioner4_PV", "index": i}, {'value': scan.scan_positioner4_PV})
            set_props({"type": "hidden_scan_positioner4_ar", "index": i}, {'value': scan.scan_positioner4_ar})
            set_props({"type": "hidden_scan_positioner4_mode", "index": i}, {'value': scan.scan_positioner4_mode})
            set_props({"type": "hidden_scan_positioner4", "index": i}, {'value': scan.scan_positioner4})
            set_props({"type": "hidden_scan_detectorTrig1_PV", "index": i}, {'value': scan.scan_detectorTrig1_PV})
            set_props({"type": "hidden_scan_detectorTrig1_VAL", "index": i}, {'value': scan.scan_detectorTrig1_VAL})
            set_props({"type": "hidden_scan_detectorTrig2_PV", "index": i}, {'value': scan.scan_detectorTrig2_PV})
            set_props({"type": "hidden_scan_detectorTrig2_VAL", "index": i}, {'value': scan.scan_detectorTrig2_VAL})
            set_props({"type": "hidden_scan_detectorTrig3_PV", "index": i}, {'value': scan.scan_detectorTrig3_PV})
            set_props({"type": "hidden_scan_detectorTrig3_VAL", "index": i}, {'value': scan.scan_detectorTrig3_VAL})
            set_props({"type": "hidden_scan_detectorTrig4_PV", "index": i}, {'value': scan.scan_detectorTrig4_PV})
            set_props({"type": "hidden_scan_detectorTrig4_VAL", "index": i}, {'value': scan.scan_detectorTrig4_VAL})
            set_props({"type": "hidden_scan_cpt", "index": i}, {'value': scan.scan_cpt})


def set_scan_accordions(scan_rows, read_only=True):
    """Create and set scan accordions with pre-populated data."""
    scan_accordions = [
        make_scan_accordion(i, scan_row, read_only)
        for i, scan_row in enumerate(scan_rows)
    ]
    set_props("scan_accordions", {'children': scan_accordions})