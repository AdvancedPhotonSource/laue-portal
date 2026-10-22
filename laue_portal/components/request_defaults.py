"""Shared creation defaults for batch and live parameter panels."""

from types import SimpleNamespace

from laue_portal.config import DEFAULT_VARIABLES, PEAKINDEX_DEFAULTS, WIRERECON_DEFAULTS
from laue_portal.workflows.constants import DEFAULT_SKIP


def create_default_wirerecon(overrides=None):
    """Return form data using the canonical reconstruction field names."""
    defaults = {
        "id": None,
        "scan_number": None,
        "root_path": DEFAULT_VARIABLES.get("root_path", ""),
        "data_path": "",
        "input_path": "",
        "filename_prefixes": [],
        "author": DEFAULT_VARIABLES.get("author", ""),
        "notes": DEFAULT_VARIABLES.get("notes", ""),
        "geometry_file": WIRERECON_DEFAULTS.get("geoFile"),
        "percent_brightest": WIRERECON_DEFAULTS.get("percent_brightest"),
        "wire_edges": WIRERECON_DEFAULTS.get("wire_edges"),
        "depth_start": WIRERECON_DEFAULTS.get("depth_start"),
        "depth_end": WIRERECON_DEFAULTS.get("depth_end"),
        "depth_resolution": WIRERECON_DEFAULTS.get("depth_resolution"),
        "frame_skip": WIRERECON_DEFAULTS.get("frame_skip", DEFAULT_SKIP),
        "wire_skip": WIRERECON_DEFAULTS.get("wire_skip", DEFAULT_SKIP),
        "num_threads": DEFAULT_VARIABLES.get("num_threads"),
        "memory_limit_mb": DEFAULT_VARIABLES.get("memory_limit_mb"),
        "scan_points": WIRERECON_DEFAULTS.get("scanPoints", ""),
        "output_path_template": "analysis/rec_%d/data",
        "verbose": DEFAULT_VARIABLES.get("verbose"),
    }
    if overrides:
        defaults.update(overrides)
    return SimpleNamespace(**defaults)


def create_default_peakindex(overrides=None):
    """Return form data using canonical indexing field names."""
    defaults = {
        "id": None,
        "scan_number": None,
        "reconstruction_id": None,
        "root_path": DEFAULT_VARIABLES.get("root_path", ""),
        "data_path": "",
        "input_path": "",
        "filename_prefixes": [],
        "author": DEFAULT_VARIABLES.get("author", ""),
        "notes": DEFAULT_VARIABLES.get("notes", ""),
        "threshold": PEAKINDEX_DEFAULTS.get("threshold"),
        "threshold_ratio": PEAKINDEX_DEFAULTS.get("thresholdRatio"),
        "max_rfactor": PEAKINDEX_DEFAULTS.get("maxRfactor"),
        "box_size": PEAKINDEX_DEFAULTS.get("boxsize"),
        "max_number": PEAKINDEX_DEFAULTS.get("max_number"),
        "min_separation": PEAKINDEX_DEFAULTS.get("min_separation"),
        "peak_shape": PEAKINDEX_DEFAULTS.get("peakShape"),
        "min_size": PEAKINDEX_DEFAULTS.get("min_size"),
        "max_peaks": PEAKINDEX_DEFAULTS.get("max_peaks"),
        "smooth": PEAKINDEX_DEFAULTS.get("smooth"),
        "cosmic_filter": False,
        "mask_file": PEAKINDEX_DEFAULTS.get("maskFile"),
        "index_kev_max_calc": PEAKINDEX_DEFAULTS.get("indexKeVmaxCalc"),
        "index_kev_max_test": PEAKINDEX_DEFAULTS.get("indexKeVmaxTest"),
        "index_angle_tolerance": PEAKINDEX_DEFAULTS.get("indexAngleTolerance"),
        "index_h": PEAKINDEX_DEFAULTS.get("indexH"),
        "index_k": PEAKINDEX_DEFAULTS.get("indexK"),
        "index_l": PEAKINDEX_DEFAULTS.get("indexL"),
        "index_cone": PEAKINDEX_DEFAULTS.get("indexCone"),
        "detector_crop_x1": PEAKINDEX_DEFAULTS.get("detectorCropX1"),
        "detector_crop_x2": PEAKINDEX_DEFAULTS.get("detectorCropX2"),
        "detector_crop_y1": PEAKINDEX_DEFAULTS.get("detectorCropY1"),
        "detector_crop_y2": PEAKINDEX_DEFAULTS.get("detectorCropY2"),
        "energy_unit": PEAKINDEX_DEFAULTS.get("energyUnit"),
        "exposure_unit": PEAKINDEX_DEFAULTS.get("exposureUnit"),
        "reciprocal_lattice_unit": PEAKINDEX_DEFAULTS.get("recipLatticeUnit"),
        "lattice_parameters_unit": PEAKINDEX_DEFAULTS.get("latticeParametersUnit"),
        "output_path_template": "analysis/index_%d",
        "output_xml": PEAKINDEX_DEFAULTS.get("outputXML", "output.xml"),
        "geometry_file": PEAKINDEX_DEFAULTS.get("geoFile"),
        "crystal_file": PEAKINDEX_DEFAULTS.get("crystFile"),
        "beamline": PEAKINDEX_DEFAULTS.get("beamline"),
        "depth": PEAKINDEX_DEFAULTS.get("depth"),
        "scan_points": PEAKINDEX_DEFAULTS.get("scanPoints", ""),
        "depth_range": PEAKINDEX_DEFAULTS.get("depthRange", ""),
    }
    if overrides:
        defaults.update(overrides)
    return SimpleNamespace(**defaults)
