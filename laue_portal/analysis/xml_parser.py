"""
Parse AllSteps XML files produced by laueanalysis.indexing.index()
into structured numpy arrays for visualization.

This module has zero Dash/Plotly dependencies.
"""

import xml.etree.ElementTree as ET
import functools
import os
import numpy as np
from pathlib import Path


# ---------------------------------------------------------------------------
# Caching layer
# ---------------------------------------------------------------------------
# NOTE: This in-process lru_cache works for single-worker deployments
# (the current setup).  If Dash is ever run with multiple Gunicorn workers
# or behind a multi-process load balancer, replace this with a shared cache
# backend such as flask_caching + diskcache so that all workers share parsed
# results instead of each maintaining an independent copy.
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=4)
def _cached_parse(xml_path: str, mtime_ns: int) -> dict:
    """Cache-internal parser keyed on (path, mtime).

    The *mtime_ns* argument is only used as a cache-key so that edits
    to the XML file invalidate stale entries.  It is not read inside
    the function body.
    """
    return _parse_indexing_xml_impl(xml_path)


def parse_indexing_xml(xml_path: str) -> dict:
    """
    Parse an AllSteps XML file into numpy arrays.

    Results are cached in-process by (path, mtime) so that multiple
    Dash callbacks referencing the same file don't re-parse it.

    Parameters
    ----------
    xml_path : str
        Path to the AllSteps XML file.

    Returns
    -------
    dict with keys:
        positions : ndarray (N, 3) -- Xsample, Ysample, Zsample
        depths : ndarray (N,) -- depth values (may contain NaN)
        energies : ndarray (N,) -- beam energy in keV
        scan_nums : ndarray (N,) -- scan numbers
        n_patterns : ndarray (N,) -- number of grains per step

        # Per-pattern data (first/best pattern per step):
        recip_lattices : ndarray (N, 3, 3) -- reciprocal lattice matrices
        rms_errors : ndarray (N,) -- RMS angular error
        goodnesses : ndarray (N,) -- goodness of fit
        n_indexed : ndarray (N,) -- number of indexed peaks per pattern

        # Crystal structure (from last step with indexing data):
        space_group : int
        lattice_params : ndarray (6,) -- a, b, c, alpha, beta, gamma
        structure_desc : str

        # Raw per-step peak data stored for detail views:
        _steps : list[dict] -- raw per-step data for get_step_peaks()
    """
    xml_path = str(xml_path)
    try:
        mtime_ns = os.stat(xml_path).st_mtime_ns
    except OSError:
        # File doesn't exist yet or is inaccessible -- skip cache
        return _parse_indexing_xml_impl(xml_path)
    return _cached_parse(xml_path, mtime_ns)


def _parse_indexing_xml_impl(xml_path: str) -> dict:
    """Uncached implementation of parse_indexing_xml."""
    xml_path = str(xml_path)
    tree = ET.parse(xml_path)
    root = tree.getroot()

    steps = root.findall("step")
    n_steps = len(steps)

    if n_steps == 0:
        raise ValueError(f"No <step> elements found in {xml_path}")

    # Pre-allocate arrays
    positions = np.full((n_steps, 3), np.nan)
    depths = np.full(n_steps, np.nan)
    energies = np.full(n_steps, np.nan)
    scan_nums = np.zeros(n_steps, dtype=np.int64)
    n_patterns = np.zeros(n_steps, dtype=np.int32)
    recip_lattices = np.full((n_steps, 3, 3), np.nan)
    rms_errors = np.full(n_steps, np.nan)
    goodnesses = np.full(n_steps, np.nan)
    n_indexed = np.zeros(n_steps, dtype=np.int32)

    # Crystal structure -- populated from first step that has indexing/xtl
    space_group = 0
    lattice_params = np.zeros(6)
    structure_desc = ""

    # Store raw step data for get_step_peaks()
    step_data_list = []

    for i, step in enumerate(steps):
        # -- Sample position --
        positions[i, 0] = _float_text(step, "Xsample")
        positions[i, 1] = _float_text(step, "Ysample")
        positions[i, 2] = _float_text(step, "Zsample")
        depths[i] = _float_text(step, "depth")

        # -- Energy --
        energies[i] = _float_text(step, "energy")

        # -- Scan number --
        scan_num_text = _text(step, "scanNum")
        if scan_num_text:
            try:
                scan_nums[i] = int(scan_num_text)
            except ValueError:
                pass

        # -- Indexing results --
        indexing_el = step.find("indexing")
        step_peaks = {
            "indexing_el": None,
            "detector_el": step.find("detector"),
        }

        if indexing_el is not None:
            step_peaks["indexing_el"] = indexing_el

            n_pat = int(indexing_el.get("Npatterns", "0"))
            n_patterns[i] = n_pat

            # Use best (first) pattern
            patterns = indexing_el.findall("pattern")
            if patterns:
                best = patterns[0]
                rms_errors[i] = float(best.get("rms_error", "nan"))
                goodnesses[i] = float(best.get("goodness", "nan"))
                n_indexed[i] = int(best.get("Nindexed", "0"))

                # Reciprocal lattice
                recip_el = best.find("recip_lattice")
                if recip_el is not None:
                    astar = _float_array(recip_el, "astar")
                    bstar = _float_array(recip_el, "bstar")
                    cstar = _float_array(recip_el, "cstar")
                    if astar is not None and bstar is not None and cstar is not None:
                        recip_lattices[i] = np.array([astar, bstar, cstar])

            # Crystal structure (grab once)
            if space_group == 0:
                xtl_el = indexing_el.find("xtl")
                if xtl_el is not None:
                    sg_text = _text(xtl_el, "SpaceGroup")
                    if sg_text:
                        try:
                            space_group = int(sg_text)
                        except ValueError:
                            pass
                    lp_text = _text(xtl_el, "latticeParameters")
                    if lp_text:
                        lattice_params = np.fromstring(lp_text.strip(), sep=" ")
                    desc_text = _text(xtl_el, "structureDesc")
                    if desc_text:
                        structure_desc = desc_text.strip()

        step_data_list.append(step_peaks)

    return {
        "positions": positions,
        "depths": depths,
        "energies": energies,
        "scan_nums": scan_nums,
        "n_patterns": n_patterns,
        "recip_lattices": recip_lattices,
        "rms_errors": rms_errors,
        "goodnesses": goodnesses,
        "n_indexed": n_indexed,
        "space_group": space_group,
        "lattice_params": lattice_params,
        "structure_desc": structure_desc,
        "_steps": step_data_list,
    }


def get_step_peaks(parsed: dict, step_index: int) -> dict | None:
    """
    Get per-peak data for a specific step.

    Parameters
    ----------
    parsed : dict
        Output from parse_indexing_xml().
    step_index : int
        Index of the step (0-based).

    Returns
    -------
    dict or None
        None if step has no peak data. Otherwise dict with:
            pixel_positions : ndarray (M, 2) -- Xpixel, Ypixel
            q_vectors : ndarray (M, 3) -- Qx, Qy, Qz
            intensities : ndarray (M,) -- peak intensities
            integrals : ndarray (M,) -- integrated intensities
            patterns : list[dict] -- per-pattern indexing info, each with:
                pattern_num : int
                rms_error : float
                goodness : float
                n_indexed : int
                hkl : ndarray (K, 3) -- h, k, l
                peak_indices : ndarray (K,) -- PkIndex mapping
    """
    steps = parsed["_steps"]
    if step_index < 0 or step_index >= len(steps):
        return None

    step_info = steps[step_index]
    detector_el = step_info["detector_el"]
    indexing_el = step_info["indexing_el"]

    if detector_el is None:
        return None

    peaks_el = detector_el.find("peaksXY")
    if peaks_el is None:
        return None

    # Parse peak positions and Q-vectors
    xpixel = _float_array_from_el(peaks_el, "Xpixel")
    ypixel = _float_array_from_el(peaks_el, "Ypixel")
    qx = _float_array_from_el(peaks_el, "Qx")
    qy = _float_array_from_el(peaks_el, "Qy")
    qz = _float_array_from_el(peaks_el, "Qz")
    intens = _float_array_from_el(peaks_el, "Intens")
    integral = _float_array_from_el(peaks_el, "Integral")

    n_peaks = int(peaks_el.get("Npeaks", "0"))

    pixel_positions = None
    if xpixel is not None and ypixel is not None:
        pixel_positions = np.column_stack([xpixel, ypixel])

    q_vectors = None
    if qx is not None and qy is not None and qz is not None:
        q_vectors = np.column_stack([qx, qy, qz])

    # Parse per-pattern indexing info
    patterns = []
    if indexing_el is not None:
        for pat_el in indexing_el.findall("pattern"):
            pat_info = {
                "pattern_num": int(pat_el.get("num", "0")),
                "rms_error": float(pat_el.get("rms_error", "nan")),
                "goodness": float(pat_el.get("goodness", "nan")),
                "n_indexed": int(pat_el.get("Nindexed", "0")),
                "hkl": None,
                "peak_indices": None,
            }
            hkl_el = pat_el.find("hkl_s")
            if hkl_el is not None:
                h = _int_array(hkl_el, "h")
                k = _int_array(hkl_el, "k")
                l = _int_array(hkl_el, "l")
                pk_idx = _int_array(hkl_el, "PkIndex")
                if h is not None and k is not None and l is not None:
                    pat_info["hkl"] = np.column_stack([h, k, l])
                if pk_idx is not None:
                    pat_info["peak_indices"] = pk_idx
            patterns.append(pat_info)

    return {
        "pixel_positions": pixel_positions,
        "q_vectors": q_vectors,
        "intensities": intens,
        "integrals": integral,
        "n_peaks": n_peaks,
        "patterns": patterns,
    }


def get_all_indexed_peaks(parsed: dict) -> list[dict]:
    """
    Build a flat list of all indexed peaks across all steps and patterns.

    Useful for populating the indexed peak table (AG Grid).

    Returns
    -------
    list[dict]
        Each dict has keys: step_index, step_scan_num, pattern_num,
        h, k, l, peak_index, x_pixel, y_pixel, intensity, integral,
        qx, qy, qz, rms_error, goodness
    """
    rows = []
    n_steps = len(parsed["_steps"])

    for si in range(n_steps):
        step_peaks = get_step_peaks(parsed, si)
        if step_peaks is None:
            continue

        scan_num = int(parsed["scan_nums"][si])

        for pat in step_peaks["patterns"]:
            if pat["hkl"] is None or pat["peak_indices"] is None:
                continue

            hkl = pat["hkl"]
            pk_indices = pat["peak_indices"]
            n_idx = len(pk_indices)

            for j in range(n_idx):
                pk_i = int(pk_indices[j])
                row = {
                    "step_index": si,
                    "step_scan_num": scan_num,
                    "pattern_num": pat["pattern_num"],
                    "h": int(hkl[j, 0]),
                    "k": int(hkl[j, 1]),
                    "l": int(hkl[j, 2]),
                    "peak_index": pk_i,
                    "rms_error": pat["rms_error"],
                    "goodness": pat["goodness"],
                }

                # Add pixel position and Q-vector if available
                if (step_peaks["pixel_positions"] is not None
                        and pk_i < len(step_peaks["pixel_positions"])):
                    row["x_pixel"] = float(step_peaks["pixel_positions"][pk_i, 0])
                    row["y_pixel"] = float(step_peaks["pixel_positions"][pk_i, 1])
                else:
                    row["x_pixel"] = None
                    row["y_pixel"] = None

                if (step_peaks["intensities"] is not None
                        and pk_i < len(step_peaks["intensities"])):
                    row["intensity"] = float(step_peaks["intensities"][pk_i])
                else:
                    row["intensity"] = None

                if (step_peaks["integrals"] is not None
                        and pk_i < len(step_peaks["integrals"])):
                    row["integral"] = float(step_peaks["integrals"][pk_i])
                else:
                    row["integral"] = None

                if (step_peaks["q_vectors"] is not None
                        and pk_i < len(step_peaks["q_vectors"])):
                    row["qx"] = float(step_peaks["q_vectors"][pk_i, 0])
                    row["qy"] = float(step_peaks["q_vectors"][pk_i, 1])
                    row["qz"] = float(step_peaks["q_vectors"][pk_i, 2])
                else:
                    row["qx"] = None
                    row["qy"] = None
                    row["qz"] = None

                rows.append(row)

    return rows


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _text(parent, tag: str) -> str | None:
    """Get text content of a child element, or None."""
    el = parent.find(tag)
    if el is not None and el.text:
        return el.text.strip()
    return None


def _float_text(parent, tag: str) -> float:
    """Get float from a child element text; returns NaN on failure."""
    text = _text(parent, tag)
    if text is None:
        return np.nan
    try:
        return float(text)
    except ValueError:
        return np.nan


def _float_array(parent, tag: str) -> np.ndarray | None:
    """Parse space-separated floats from a child element."""
    text = _text(parent, tag)
    if text is None:
        return None
    try:
        return np.fromstring(text, sep=" ")
    except ValueError:
        return None


def _float_array_from_el(parent, tag: str) -> np.ndarray | None:
    """Parse space-separated floats from a child element (handles long lines)."""
    el = parent.find(tag)
    if el is None or not el.text:
        return None
    try:
        return np.fromstring(el.text.strip(), sep=" ")
    except ValueError:
        return None


def _int_array(parent, tag: str) -> np.ndarray | None:
    """Parse space-separated ints from a child element."""
    text = _text(parent, tag)
    if text is None:
        return None
    try:
        values = np.fromstring(text, sep=" ")
        return values.astype(np.int64)
    except ValueError:
        return None
