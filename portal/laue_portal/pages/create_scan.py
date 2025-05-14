import dash_bootstrap_components as dbc
from dash import html, Input, State, set_props, ALL
import dash
import laue_portal.pages.ui_shared as ui_shared
from dash import dcc
import base64
import yaml
import laue_portal.database.db_utils as db_utils
import datetime
import laue_portal.database.db_schema as db_schema
from sqlalchemy.orm import Session

dash.register_page(__name__)

layout = dbc.Container(
    [html.Div([
        ui_shared.navbar,
        dbc.Alert(
            "Hello! I am an alert",
            id="alert-upload",
            dismissable=True,
            is_open=False,
        ),
        dbc.Alert(
            "Hello! I am an alert",
            id="alert-submit",
            dismissable=True,
            is_open=False,
        ),
        html.Hr(),
        html.Center(
            html.Div(
                [
                    html.Div([
                        dbc.Button('Copy From Existing (TODO)', id='copy-existing', className='mr-2'),
                    ], style={'display':'inline-block'}),
                    html.Div([
                            dcc.Upload(dbc.Button('Upload Log'), id='upload-metadata-log'),
                    ], style={'display':'inline-block'}),
                ],
            )
        ),
        html.Hr(),
        html.Center(
            dbc.Button('Submit', id='submit_metadata', color='primary'),
        ),
        html.Hr(),
        ui_shared.metadata_form,
    ],
    )
    ],
    className='dbc', 
    fluid=True
)

"""
=======================
Callbacks
=======================
"""
@dash.callback(
    Input('upload-metadata-log', 'contents'),
    prevent_initial_call=True,
)
def upload_log(contents):
    try:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        log, scans = db_utils.parse_metadata(decoded) #yaml.safe_load(decoded)
        metadata_row = db_utils.import_metadata_row(log)
        scan_cards = []; scan_rows = []
        for i,scan in enumerate(scans):
            scan_cards.append(ui_shared.make_scan_card(i))
            scan_rows.append(db_utils.import_scan_row(scan))
        set_props("scans_container", {'children': scan_cards})
        
        metadata_row.date = datetime.datetime.now()
        metadata_row.commit_id = ''
        metadata_row.calib_id = ''
        metadata_row.runtime = ''
        metadata_row.computer_name = ''
        metadata_row.dataset_id = 0
        metadata_row.notes = ''

        set_props("alert-upload", {'is_open': True, 
                                    'children': 'Log uploaded successfully',
                                    'color': 'success'})
        ui_shared.set_metadata_form_props(metadata_row,scan_rows)

    except Exception as e:
        set_props("alert-upload", {'is_open': True, 
                                    'children': f'Upload Failed! Error: {e}',
                                    'color': 'danger'})


@dash.callback(
    Input('submit_metadata', 'n_clicks'),
    
    State('scanNumber', 'value'),

    State('scans_container', 'children'),

    State({'type': 'scan_dim', 'index': ALL}, 'value'),
    State({'type': 'scan_npts', 'index': ALL}, 'value'),
    State({'type': 'scan_after', 'index': ALL}, 'value'),
    State({'type': 'scan_positioner1_PV', 'index': ALL}, 'value'),
    State({'type': 'scan_positioner1_ar', 'index': ALL}, 'value'),
    State({'type': 'scan_positioner1_mode', 'index': ALL}, 'value'),
    State({'type': 'scan_positioner1', 'index': ALL}, 'value'),
    State({'type': 'scan_positioner2_PV', 'index': ALL}, 'value'),
    State({'type': 'scan_positioner2_ar', 'index': ALL}, 'value'),
    State({'type': 'scan_positioner2_mode', 'index': ALL}, 'value'),
    State({'type': 'scan_positioner2', 'index': ALL}, 'value'),
    State({'type': 'scan_positioner3_PV', 'index': ALL}, 'value'),
    State({'type': 'scan_positioner3_ar', 'index': ALL}, 'value'),
    State({'type': 'scan_positioner3_mode', 'index': ALL}, 'value'),
    State({'type': 'scan_positioner3', 'index': ALL}, 'value'),
    State({'type': 'scan_positioner4_PV', 'index': ALL}, 'value'),
    State({'type': 'scan_positioner4_ar', 'index': ALL}, 'value'),
    State({'type': 'scan_positioner4_mode', 'index': ALL}, 'value'),
    State({'type': 'scan_positioner4', 'index': ALL}, 'value'),
    State({'type': 'scan_detectorTrig1_PV', 'index': ALL}, 'value'),
    State({'type': 'scan_detectorTrig1_VAL', 'index': ALL}, 'value'),
    State({'type': 'scan_detectorTrig2_PV', 'index': ALL}, 'value'),
    State({'type': 'scan_detectorTrig2_VAL', 'index': ALL}, 'value'),
    State({'type': 'scan_detectorTrig3_PV', 'index': ALL}, 'value'),
    State({'type': 'scan_detectorTrig3_VAL', 'index': ALL}, 'value'),
    State({'type': 'scan_detectorTrig4_PV', 'index': ALL}, 'value'),
    State({'type': 'scan_detectorTrig4_VAL', 'index': ALL}, 'value'),
    State({'type': 'scan_cpt', 'index': ALL}, 'value'),
    
    prevent_initial_call=True,
)
def submit_scanlog(n,
    scanNumber,

    scan_cards,

    dim,
    npts,
    after,
    positioner1_PV,
    positioner1_ar,
    positioner1_mode,
    positioner1,
    positioner2_PV,
    positioner2_ar,
    positioner2_mode,
    positioner2,
    positioner3_PV,
    positioner3_ar,
    positioner3_mode,
    positioner3,
    positioner4_PV,
    positioner4_ar,
    positioner4_mode,
    positioner4,
    detectorTrig1_PV,
    detectorTrig1_VAL,
    detectorTrig2_PV,
    detectorTrig2_VAL,
    detectorTrig3_PV,
    detectorTrig3_VAL,
    detectorTrig4_PV,
    detectorTrig4_VAL,
    cpt,
    
):
    # TODO: Input validation and reponse
    
    for i in range(len(scan_cards)):
        scan = db_schema.Scan(
            id = 0,
            scanNumber=scanNumber,

            scan_dim=dim[i],
            scan_npts=npts[i],
            scan_after=after[i],
            scan_positioner1_PV=positioner1_PV[i],
            scan_positioner1_ar=positioner1_ar[i],
            scan_positioner1_mode=positioner1_mode[i],
            scan_positioner1=positioner1[i],
            scan_positioner2_PV=positioner2_PV[i],
            scan_positioner2_ar=positioner2_ar[i],
            scan_positioner2_mode=positioner2_mode[i],
            scan_positioner2=positioner2[i],
            scan_positioner3_PV=positioner3_PV[i],
            scan_positioner3_ar=positioner3_ar[i],
            scan_positioner3_mode=positioner3_mode[i],
            scan_positioner3=positioner3[i],
            scan_positioner4_PV=positioner4_PV[i],
            scan_positioner4_ar=positioner4_ar[i],
            scan_positioner4_mode=positioner4_mode[i],
            scan_positioner4=positioner4[i],
            scan_detectorTrig1_PV=detectorTrig1_PV[i],
            scan_detectorTrig1_VAL=detectorTrig1_VAL[i],
            scan_detectorTrig2_PV=detectorTrig2_PV[i],
            scan_detectorTrig2_VAL=detectorTrig2_VAL[i],
            scan_detectorTrig3_PV=detectorTrig3_PV[i],
            scan_detectorTrig3_VAL=detectorTrig3_VAL[i],
            scan_detectorTrig4_PV=detectorTrig4_PV[i],
            scan_detectorTrig4_VAL=detectorTrig4_VAL[i],
            scan_cpt=cpt[i],
        )

        with Session(db_utils.ENGINE) as session:
            session.add(scan)
            
            session.commit()
    
    # set_props("alert-submit", {'is_open': True, 
    #                             'children': 'Log Added to Database',
    #                             'color': 'success'})

@dash.callback(
    Input('submit_metadata', 'n_clicks'),

    State('scanNumber', 'value'),
    State('time_epoch', 'value'),
    State('time', 'value'),
    State('user_name', 'value'),
    State('source_beamBad', 'value'),
    State('source_CCDshutter', 'value'),
    State('source_monoTransStatus', 'value'),
    State('source_energy_unit', 'value'),
    State('source_energy', 'value'),
    State('source_IDgap_unit', 'value'),
    State('source_IDgap', 'value'),
    State('source_IDtaper_unit', 'value'),
    State('source_IDtaper', 'value'),
    State('source_ringCurrent_unit', 'value'),
    State('source_ringCurrent', 'value'),
    State('sample_XYZ_unit', 'value'),
    State('sample_XYZ_desc', 'value'),
    State('sample_XYZ', 'value'),
    State('knife-edge_XYZ_unit', 'value'),
    State('knife-edge_XYZ_desc', 'value'),
    State('knife-edge_XYZ', 'value'),
    State('knife-edge_knifeScan_unit', 'value'),
    State('knife-edge_knifeScan', 'value'),
    State('mda_file', 'value'),
    State('scanEnd_abort', 'value'),
    State('scanEnd_time_epoch', 'value'),
    State('scanEnd_time', 'value'),
    State('scanEnd_scanDuration_unit', 'value'),
    State('scanEnd_scanDuration', 'value'),
    State('scanEnd_source_beamBad', 'value'),
    State('scanEnd_source_ringCurrent_unit', 'value'),
    State('scanEnd_source_ringCurrent', 'value'),

    prevent_initial_call=True,
)
def submit_log(n,
    scanNumber,
    time_epoch,
    time,
    user_name,
    source_beamBad,
    source_CCDshutter,
    source_monoTransStatus,
    source_energy_unit,
    source_energy,
    source_IDgap_unit,
    source_IDgap,
    source_IDtaper_unit,
    source_IDtaper,
    source_ringCurrent_unit,
    source_ringCurrent,
    sample_XYZ_unit,
    sample_XYZ_desc,
    sample_XYZ,
    knifeEdge_XYZ_unit,
    knifeEdge_XYZ_desc,
    knifeEdge_XYZ,
    knifeEdge_knifeScan_unit,
    knifeEdge_knifeScan,
    mda_file,
    scanEnd_abort,
    scanEnd_time_epoch,
    scanEnd_time,
    scanEnd_scanDuration_unit,
    scanEnd_scanDuration,
    scanEnd_source_beamBad,
    scanEnd_source_ringCurrent_unit,
    scanEnd_source_ringCurrent,
    
):
    # TODO: Input validation and reponse
    
    metadata = db_schema.Metadata(
        date=datetime.datetime.now(),
        commit_id='TEST',
        calib_id='TEST',
        runtime='TEST',
        computer_name='TEST',
        dataset_id=0,
        notes='TODO', 

        scanNumber=scanNumber,
        time_epoch=time_epoch,
        time=time,
        user_name=user_name,
        source_beamBad=source_beamBad,
        source_CCDshutter=source_CCDshutter,
        source_monoTransStatus=source_monoTransStatus,
        source_energy_unit=source_energy_unit,
        source_energy=source_energy,
        source_IDgap_unit=source_IDgap_unit,
        source_IDgap=source_IDgap,
        source_IDtaper_unit=source_IDtaper_unit,
        source_IDtaper=source_IDtaper,
        source_ringCurrent_unit=source_ringCurrent_unit,
        source_ringCurrent=source_ringCurrent,
        sample_XYZ_unit=sample_XYZ_unit,
        sample_XYZ_desc=sample_XYZ_desc,
        sample_XYZ=sample_XYZ,
        knifeEdge_XYZ_unit=knifeEdge_XYZ_unit,
        knifeEdge_XYZ_desc=knifeEdge_XYZ_desc,
        knifeEdge_XYZ=knifeEdge_XYZ,
        knifeEdge_knifeScan_unit=knifeEdge_knifeScan_unit,
        knifeEdge_knifeScan=knifeEdge_knifeScan,
        mda_file=mda_file,
        scanEnd_abort=scanEnd_abort,
        scanEnd_time_epoch=scanEnd_time_epoch,
        scanEnd_time=scanEnd_time,
        scanEnd_scanDuration_unit=scanEnd_scanDuration_unit,
        scanEnd_scanDuration=scanEnd_scanDuration,
        scanEnd_source_beamBad=scanEnd_source_beamBad,
        scanEnd_source_ringCurrent_unit=scanEnd_source_ringCurrent_unit,
        scanEnd_source_ringCurrent=scanEnd_source_ringCurrent,
    )

    with Session(db_utils.ENGINE) as session:
        session.add(metadata)
        
        session.commit()
    
    set_props("alert-submit", {'is_open': True, 
                                'children': 'Log Added to Database',
                                'color': 'success'})
