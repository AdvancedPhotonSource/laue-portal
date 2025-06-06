import dash_bootstrap_components as dbc
from dash import callback, Input, Output, State, set_props
from laue_portal.components.form_base import _stack, _field, _ckbx


peakindex_form = dbc.Row(
                [
                    dbc.Accordion(
                        [
                        dbc.AccordionItem(
                            [
                                _stack(
                                    [   
                                        _field("Scan ID", "dataset", size='sm'),
                                        _field("Recon ID", "recon_id", size='sm'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Files Path", "filefolder", size='hg'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Filename Prefix", "filenamePrefix", size='lg'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Scan Point (Inner Index) Range Start", "scanPointStart", size='md'),
                                        _field("Scan Point (Inner Index) Range End", "scanPointEnd", size='md'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Geo File", "geoFile", size='hg'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Output Path", "outputFolder", size='hg'),
                                    ]
                                ),
                                # _stack(
                                #     [
                                #         _field("Depth (Outer Index) Range Start", "depthRangeStart", size='lg'),
                                #         _field("Depth (Outer Index) Range End", "depthRangeEnd", size='lg'),
                                #     ]
                                # ),
                            ],
                            title="Files",
                        ),
                        dbc.AccordionItem(
                            [
                                # _stack(
                                #     [
                                #         _field("Peak Program", "peakProgram", size='md'),
                                #     ]
                                # ),
                                _stack(
                                    [
                                        _field("Box Size", "boxsize", size='md'),
                                        _field("Max Rfactor", "maxRfactor", size='md'),
                                        _field("Threshold", "threshold", size='md'),
                                        _field("Threshold Ratio", "thresholdRatio", size='md'),
                                        
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Min Spot Size", "min_size", size='md'),
                                        _field("Min Spot Separation", "min_separation", size='md'),
                                        _field("Max No. of Spots", "max_number", size='md')
                                    ]
                                ),
                                _stack(
                                    [
                                        #_field("Peak Shape", "peakShape", size='lg'),
                                        dbc.Select(
                                            placeholder="Peak Shape",
                                            options=[
                                                {"label": "Lorentzian", "value": "Lorentzian"},
                                                {"label": "Gaussian", "value": "Gaussian"},
                                            ],
                                            style={'width':200},
                                            id="peakShape",
                                        ),
                                        _ckbx("Smooth peak before fitting", "smooth", size='md'),
                                        _ckbx("Cosmic Filter", "cosmicFilter", size='md'),
                                        # _ckbx("Cosmic Filter", "cosmicFilter", size='lg'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Detector CropX1", "detectorCropX1", size='md'),
                                        _field("Detector CropY1", "detectorCropY1", size='md'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Detector CropX2", "detectorCropX2", size='md'),
                                        _field("Detector CropY2", "detectorCropY2", size='md'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Mask File", "maskFile", size='hg'),
                                    ]
                                ),
                                dbc.Button(
                                    "Show Paths to Programs",
                                    id="collapse1-button",
                                    className="mb-3",
                                    color="primary",
                                    n_clicks=0,
                                ),
                                dbc.Collapse(
                                    [
                                        _field("peaksearch Path", "peaksearchPath", size='hg'),
                                        _field("p2q Path", "p2qPath", size='hg'),
                                    ],
                                id="collapse1",
                                is_open=False,
                                ),
                            ],
                            title="Peak Search",
                        ),
                        dbc.AccordionItem(
                            [
                                _stack(
                                    [
                                        _field("Cryst File", "crystFile", size='hg'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Max Calc Energy [keV]", "indexKeVmaxCalc", size='md'),
                                        _field("Max Test Energy [keV]", "indexKeVmaxTest", size='md'),
                                        _field("Index Angle Tolerance", "indexAngleTolerance", size='md'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Index HKL", "indexHKL", size='md'),
                                        # _field("Index H", "indexH", size='md'),
                                        # _field("Index K", "indexK", size='md'),
                                        # _field("Index L", "indexL", size='md'),
                                        _field("Index Cone", "indexCone", size='md'),
                                        _field("Max Peaks", "max_peaks", size='md'),
                                    ]
                                ),
                                dbc.Button(
                                    "Show Path to Program",
                                    id="collapse2-button",
                                    className="mb-3",
                                    color="primary",
                                    n_clicks=0,
                                ),
                                dbc.Collapse(
                                    [
                                        _field("Indexing Path", "indexingPath", size='hg'),
                                    ],
                                id="collapse2",
                                is_open=False,
                                ),
                            ],
                            title="Indexing",
                        ),
                        dbc.AccordionItem(
                            [
                                _stack(
                                    [
                                        _field("Energy Unit", "energyUnit", size='md'),
                                        _field("Exposure Unit", "exposureUnit", size='md'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Recip Lattice Unit", "recipLatticeUnit", size='md'),
                                        _field("Lattice Parameters Unit", "latticeParametersUnit", size='md'),
                                    ]
                                ),
                                _stack(
                                    [
                                        _field("Beamline", "beamline", size='md'),
                                        _field("Depth", "depth", size='md'),
                                    ]
                                ),
                            ],
                            title="Labels",
                        ),
                        ],
                        always_open=True
                    ),
                ],
                style={'width': '100%', 'overflow-x': 'auto'}
        )


def set_peakindex_form_props(peakindex, read_only=False):
    #set_props("dataset", {'value':peakindex.dataset_id, 'readonly':read_only})
    set_props("dataset", {'value':peakindex.dataset_id, 'readonly':read_only})
    set_props("recon_id", {'value':peakindex.recon_id, 'readonly':read_only})
    
    # set_props("peakProgram", {'value':peakindex.peakProgram, 'readonly':read_only})
    set_props("threshold", {'value':peakindex.threshold, 'readonly':read_only})
    set_props("thresholdRatio", {'value':peakindex.thresholdRatio, 'readonly':read_only})
    set_props("maxRfactor", {'value':peakindex.maxRfactor, 'readonly':read_only})
    set_props("boxsize", {'value':peakindex.boxsize, 'readonly':read_only})
    set_props("max_number", {'value':peakindex.max_number, 'readonly':read_only})
    set_props("min_separation", {'value':peakindex.min_separation, 'readonly':read_only})
    set_props("peakShape", {'value':peakindex.peakShape, 'readonly':read_only})
    set_props("scanPointStart", {'value':peakindex.scanPointStart, 'readonly':read_only})
    set_props("scanPointEnd", {'value':peakindex.scanPointEnd, 'readonly':read_only})
    # set_props("depthRangeStart", {'value':peakindex.depthRangeStart, 'readonly':read_only})
    # set_props("depthRangeEnd", {'value':peakindex.depthRangeEnd, 'readonly':read_only})
    set_props("detectorCropX1", {'value':peakindex.detectorCropX1, 'readonly':read_only})
    set_props("detectorCropX2", {'value':peakindex.detectorCropX2, 'readonly':read_only})
    set_props("detectorCropY1", {'value':peakindex.detectorCropY1, 'readonly':read_only})
    set_props("detectorCropY2", {'value':peakindex.detectorCropY2, 'readonly':read_only})
    set_props("min_size", {'value':peakindex.min_size, 'readonly':read_only})
    set_props("max_peaks", {'value':peakindex.max_peaks, 'readonly':read_only})
    set_props("smooth", {'value':peakindex.smooth, 'readonly':read_only})
    set_props("maskFile", {'value':peakindex.maskFile, 'readonly':read_only})
    set_props("indexKeVmaxCalc", {'value':peakindex.indexKeVmaxCalc, 'readonly':read_only})
    set_props("indexKeVmaxTest", {'value':peakindex.indexKeVmaxTest, 'readonly':read_only})
    set_props("indexAngleTolerance", {'value':peakindex.indexAngleTolerance, 'readonly':read_only})
    set_props("indexHKL", {'value':''.join(
        [str(idx) for idx in [peakindex.indexH, peakindex.indexK, peakindex.indexL]]
                                          ),
                           'readonly':read_only})
    # set_props("indexH", {'value':peakindex.indexH, 'readonly':read_only})
    # set_props("indexK", {'value':peakindex.indexK, 'readonly':read_only})
    # set_props("indexL", {'value':peakindex.indexL, 'readonly':read_only})
    set_props("indexCone", {'value':peakindex.indexCone, 'readonly':read_only})
    set_props("energyUnit", {'value':peakindex.energyUnit, 'readonly':read_only})
    set_props("exposureUnit", {'value':peakindex.exposureUnit, 'readonly':read_only})
    set_props("cosmicFilter", {'value':peakindex.cosmicFilter, 'readonly':read_only})
    set_props("recipLatticeUnit", {'value':peakindex.recipLatticeUnit, 'readonly':read_only})
    set_props("latticeParametersUnit", {'value':peakindex.latticeParametersUnit, 'readonly':read_only})
    set_props("peaksearchPath", {'value':peakindex.peaksearchPath, 'readonly':read_only})
    set_props("p2qPath", {'value':peakindex.p2qPath, 'readonly':read_only})
    set_props("indexingPath", {'value':peakindex.indexingPath, 'readonly':read_only})
    set_props("outputFolder", {'value':peakindex.outputFolder, 'readonly':read_only})
    set_props("filefolder", {'value':peakindex.filefolder, 'readonly':read_only})
    set_props("filenamePrefix", {'value':peakindex.filenamePrefix, 'readonly':read_only})
    set_props("geoFile", {'value':peakindex.geoFile, 'readonly':read_only})
    set_props("crystFile", {'value':peakindex.crystFile, 'readonly':read_only})
    set_props("depth", {'value':peakindex.depth, 'readonly':read_only})
    set_props("beamline", {'value':peakindex.beamline, 'readonly':read_only})
    # set_props("cosmicFilter", {'value':peakindex.cosmicFilter, 'readonly':read_only})


@callback(
    Output("collapse1", "is_open"),
    [Input("collapse1-button", "n_clicks")],
    [State("collapse1", "is_open")],
)
def toggle_collapse12(n, is_open):
    if n:
        return not is_open
    return is_open

@callback(
    Output("collapse2", "is_open"),
    [Input("collapse2-button", "n_clicks")],
    [State("collapse2", "is_open")],
)
def toggle_collapse2(n, is_open):
    if n:
        return not is_open
    return is_open