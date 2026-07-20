"""Scan XML parsing and database import services."""

import logging
import os
import tempfile
import time
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

import laue_portal.database.db_schema as db_schema
import laue_portal.database.session_utils as session_utils
from laue_portal.config import MOTOR_GROUPS

logger = logging.getLogger(__name__)

SCAN_LOG_XMLNS = "http://sector34.xray.aps.anl.gov/34ide/scanLog"
SCAN_LOG_CACHE_DIR = Path(tempfile.gettempdir()) / "laue-portal-scan-imports"
SCAN_LOG_CACHE_TTL_SECONDS = 24 * 60 * 60


def parse_metadata(xml, xmlns=SCAN_LOG_XMLNS, scan_no=2, empty="\n\t\t"):
    """Parse one scan by its child index in an XML scan log."""
    root = ET.fromstring(xml)
    return _parse_scan_element(root[scan_no], xmlns=xmlns, empty=empty)


def _parse_scan_element(scan, xmlns=SCAN_LOG_XMLNS, empty="\n\t\t"):
    """Convert an already-parsed ``fullScan`` element into import dictionaries."""

    def name(s, xmlns=xmlns):
        return s.replace(f"{{{xmlns}}}", "")

    def traverse_tree(fields, tree_dict=None, parent_name=""):
        if tree_dict is None:
            tree_dict = {}
        if not len(fields):
            pass
        else:
            for field in list(fields):
                field_name = name(field.tag)
                if not any([field_name == f for f in ["scan", "cpt"]]):
                    path_name = f"{parent_name}{field_name}"
                    field_dict = dict([(f"{path_name}_{k}", v) for k, v in field.attrib.items()])
                    if field.text and empty not in field.text:
                        field_dict[path_name] = field.text
                    tree_dict.update(field_dict)
                    traverse_tree(field, tree_dict, path_name + "_")
        return tree_dict

    # Define numeric fields that should be None instead of empty string
    numeric_fields = {
        "time_epoch",
        "source_energy",
        "source_IDgap",
        "source_IDtaper",
        "source_ringCurrent",
        "knife-edge_knifeScan",
        "scanEnd_time_epoch",
        "scanEnd_scanDuration",
        "scanEnd_source_ringCurrent",
    }

    scanNumber = scan.get("scanNumber")
    log_dict = {
        "scanNumber": scanNumber,
        "time_epoch": None,
        "time": "",
        "user_name": "",
        "source_beamBad": "",
        "source_CCDshutter": "",
        "source_monoTransStatus": "",
        "source_energy_unit": "",
        "source_energy": None,
        "source_IDgap_unit": "",
        "source_IDgap": None,
        "source_IDtaper_unit": "",
        "source_IDtaper": None,
        "source_ringCurrent_unit": "",
        "source_ringCurrent": None,
        "sample_XYZ_unit": "",
        "sample_XYZ_desc": "",
        "sample_XYZ": "",
        "knife-edge_XYZ_unit": "",
        "knife-edge_XYZ_desc": "",
        "knife-edge_XYZ": "",
        "knife-edge_knifeScan_unit": "",
        "knife-edge_knifeScan": None,
        "mda_file": "",
        "scanEnd_abort": "",
        "scanEnd_time_epoch": None,
        "scanEnd_time": "",
        "scanEnd_scanDuration_unit": "",
        "scanEnd_scanDuration": None,
        "scanEnd_source_beamBad": "",
        "scanEnd_source_ringCurrent_unit": "",
        "scanEnd_source_ringCurrent": None,
    }

    log_dict = traverse_tree(scan, log_dict)

    # Convert empty strings to None for numeric fields
    for field in numeric_fields:
        if field in log_dict and log_dict[field] == "":
            log_dict[field] = None

    scan_label = "scan"
    scan_dims = list(scan.iter(f"{{{xmlns}}}{scan_label}"))
    # scan_dims_num = str(len(scan_dims))

    # *****#
    PV_label1 = "positioner"
    PV_label2 = "detectorTrig"
    scanEnd_cpt_list = scan.find(f"{{{xmlns}}}scanEnd").find(f"{{{xmlns}}}cpt").text.split()[::-1]
    # Define numeric fields for scan dimensions
    scan_numeric_fields = {"dim", "npts", "cpt"}

    dims_dict_list = []
    for ii, dim in enumerate(scan_dims):
        dim_dict = {
            "scanNumber": scanNumber,
            "dim": None,
            "npts": None,
            "after": "",
            "positioner1_PV": "",
            "positioner1_ar": "",
            "positioner1_mode": "",
            "positioner1": "",
            "positioner2_PV": "",
            "positioner2_ar": "",
            "positioner2_mode": "",
            "positioner2": "",
            "positioner3_PV": "",
            "positioner3_ar": "",
            "positioner3_mode": "",
            "positioner3": "",
            "positioner4_PV": "",
            "positioner4_ar": "",
            "positioner4_mode": "",
            "positioner4": "",
            "detectorTrig1_PV": "",
            "detectorTrig1_VAL": "",
            "detectorTrig2_PV": "",
            "detectorTrig2_VAL": "",
            "detectorTrig3_PV": "",
            "detectorTrig3_VAL": "",
            "detectorTrig4_PV": "",
            "detectorTrig4_VAL": "",
            "cpt": None,
        }
        dim_dict.update(dim.attrib)
        PV_count_dict = {PV_label1: 0, PV_label2: 0}
        for record in dim:
            # record_name = name(record.tag)
            if "PV" in record.attrib.keys():
                record_name = name(record.tag)
                for PV_label in PV_count_dict.keys():
                    if PV_label in record_name:
                        PV_count_dict[PV_label] += 1
                        record_label = f"{PV_label}{PV_count_dict[PV_label]}"
                        record_dict = dict([("_".join([record_label, k]), v) for k, v in record.attrib.items()])
                        if record.text:
                            record_dict[f"{record_label}"] = record.text
                        dim_dict.update(record_dict)
        dim_dict["cpt"] = scanEnd_cpt_list[ii]

        # Convert empty strings to None for numeric fields
        for field in scan_numeric_fields:
            if field in dim_dict and dim_dict[field] == "":
                dim_dict[field] = None

        dim_dict = {f"{scan_label}_{k}" if k != "scanNumber" else k: v for k, v in dim_dict.items()}
        dims_dict_list.append(dim_dict)
    # *****#

    return log_dict, dims_dict_list


def _find_text(element, path, default=""):
    """Return stripped child text without making missing optional fields fatal."""
    child = element.find(path)
    if child is None or child.text is None:
        return default
    return child.text.strip()


def _scan_index_entry(scan, scan_index, xmlns=SCAN_LOG_XMLNS):
    """Build the lightweight row used by the first-stage scan index."""
    namespace = f"{{{xmlns}}}"
    time_element = scan.find(f"{namespace}time")
    energy_element = scan.find(f"{namespace}source/{namespace}energy")

    return {
        "scan_key": str(scan_index),
        "scan_index": scan_index,
        "scanNumber": scan.get("scanNumber", ""),
        "time": _find_text(scan, f"{namespace}time"),
        "time_epoch": time_element.get("epoch", "") if time_element is not None else "",
        "user_name": _find_text(scan, f"{namespace}user/{namespace}name"),
        "energy": _find_text(scan, f"{namespace}source/{namespace}energy"),
        "energy_unit": energy_element.get("unit", "") if energy_element is not None else "",
        "sample_XYZ": _find_text(scan, f"{namespace}sample/{namespace}XYZ"),
        "num_dims": sum(1 for _ in scan.iter(f"{namespace}scan")),
    }


def index_scans_from_xml(xml_bytes, xmlns=SCAN_LOG_XMLNS):
    """Parse a log once and return lightweight scan summaries for selection."""
    root = ET.fromstring(xml_bytes)
    return [
        _scan_index_entry(element, scan_index, xmlns=xmlns)
        for scan_index, element in enumerate(root)
        if element.tag.endswith("Scan")
    ]


def _scan_result(scan, scan_index, xmlns=SCAN_LOG_XMLNS):
    log, scans = _parse_scan_element(scan, xmlns=xmlns)
    return {
        "scan_key": str(scan_index),
        "scan_index": scan_index,
        "scanNumber": log.get("scanNumber", ""),
        "log": log,
        "scans": scans,
        "time": log.get("time", ""),
        "user_name": log.get("user_name", ""),
        "energy": log.get("source_energy", ""),
        "energy_unit": log.get("source_energy_unit", ""),
        "sample_XYZ": log.get("sample_XYZ", ""),
        "num_dims": len(scans),
    }


def _parse_scans_from_root(root, selected_indices=None, xmlns=SCAN_LOG_XMLNS):
    selected = None if selected_indices is None else {int(index) for index in selected_indices}
    found = set()
    results = []

    for scan_index, element in enumerate(root):
        if not element.tag.endswith("Scan") or (selected is not None and scan_index not in selected):
            continue

        found.add(scan_index)
        try:
            results.append(_scan_result(element, scan_index, xmlns=xmlns))
        except Exception:
            logger.exception("Skipping scan at XML index %s after parse failure", scan_index)

    if selected is not None:
        missing = selected - found
        if missing:
            missing_display = ", ".join(str(index) for index in sorted(missing))
            raise ValueError(f"Selected scan indices are not present in the staged log: {missing_display}")

    return results


def parse_selected_scans_from_xml(xml_bytes, scan_indices, xmlns=SCAN_LOG_XMLNS):
    """Fully parse only the selected top-level scan elements in one document pass."""
    root = ET.fromstring(xml_bytes)
    return _parse_scans_from_root(root, selected_indices=scan_indices, xmlns=xmlns)


def _ensure_scan_log_cache_dir():
    SCAN_LOG_CACHE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        SCAN_LOG_CACHE_DIR.chmod(0o700)
    except OSError:
        logger.warning("Could not restrict permissions on scan-log cache %s", SCAN_LOG_CACHE_DIR)


def _scan_log_cache_path(token):
    if not isinstance(token, str):
        raise ValueError("Invalid staged scan-log token")
    try:
        canonical_token = uuid.UUID(token).hex
    except (ValueError, AttributeError) as error:
        raise ValueError("Invalid staged scan-log token") from error
    if token != canonical_token:
        raise ValueError("Invalid staged scan-log token")
    return SCAN_LOG_CACHE_DIR / f"{canonical_token}.xml"


def cleanup_expired_scan_logs(now=None):
    """Remove staged logs that have not been accessed within the cache TTL."""
    if not SCAN_LOG_CACHE_DIR.exists():
        return

    cutoff = (time.time() if now is None else now) - SCAN_LOG_CACHE_TTL_SECONDS
    for path in SCAN_LOG_CACHE_DIR.glob("*.xml"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
        except FileNotFoundError:
            continue
        except OSError:
            logger.warning("Could not clean up staged scan log %s", path, exc_info=True)


def stage_scan_log(xml_bytes):
    """Store an already-validated uploaded scan log and return an opaque token."""
    _ensure_scan_log_cache_dir()
    cleanup_expired_scan_logs()

    token = uuid.uuid4().hex
    final_path = _scan_log_cache_path(token)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{token}-", suffix=".tmp", dir=SCAN_LOG_CACHE_DIR)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(xml_bytes)
        temporary_path.chmod(0o600)
        temporary_path.replace(final_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return token


def load_staged_scan_log(token):
    """Load a staged scan log, refreshing its expiry window on access."""
    path = _scan_log_cache_path(token)
    try:
        if path.stat().st_mtime < time.time() - SCAN_LOG_CACHE_TTL_SECONDS:
            path.unlink()
            raise FileNotFoundError
        xml_bytes = path.read_bytes()
        path.touch()
    except FileNotFoundError as error:
        raise FileNotFoundError("The staged scan log expired or is unavailable; upload it again.") from error
    return xml_bytes


def find_motor_group(pv_value):
    """
    Find which motor group contains the given motor string.

    Args:
        pv_value: The motor PV string to search for

    Returns:
        The motor group key if found, "none" if pv_value is None,
        or "other" if pv_value is not None but not found
    """
    if pv_value is None:
        return "none"

    motor_string = pv_value.split(".VAL")[0]
    for group_key, motor_list in MOTOR_GROUPS.items():
        if motor_string in motor_list:
            return group_key

    return "other"


def update_motor_group_totals(motor_group_totals, scan):
    """
    Updates the motor group total programmed points and completed points
    with the data for each motor group from a single scan.
    """
    for PV_i in range(1, 5):
        pv_attr = f"scan_positioner{PV_i}_PV"
        if getattr(scan, pv_attr, None):
            motor_group = find_motor_group(getattr(scan, pv_attr))
            if motor_group not in motor_group_totals:
                motor_group_totals[motor_group] = {"points": 1, "completed": 1}

            motor_group_totals[motor_group]["points"] *= int(scan.scan_npts)
            motor_group_totals[motor_group]["completed"] *= int(scan.scan_cpt)
    return motor_group_totals


def convert_time_string_to_datetime(time_string):
    """
    Convert time string to datetime object.
    Handles various time formats commonly found in the XML data.
    """
    if not time_string or time_string == "":
        return None

    # Common time formats in the XML data
    time_formats = [
        "%Y-%m-%dT%H:%M:%S",  # ISO format: 2023-02-01T18:46:06
        "%Y-%m-%d %H:%M:%S",  # Alternative format
        "%Y-%m-%d, %H:%M:%S",  # Format with comma: 2023-02-25, 04:00:38
        "%Y-%m-%dT%H:%M:%S.%f",  # With microseconds
    ]

    for fmt in time_formats:
        try:
            return datetime.strptime(time_string, fmt)
        except ValueError:
            continue

    # If none of the formats work, raise an error
    raise ValueError(f"Unable to parse time string: {time_string}")


def convert_epoch_string_to_int(epoch_string):
    """
    Convert epoch time string to integer.
    """
    if not epoch_string or epoch_string == "" or epoch_string is None:
        return None

    try:
        return int(epoch_string)
    except ValueError:
        return None


def import_metadata_row(metadata_object):
    """
    Reads a yaml file and creates a new Metadata ORM object with
    the base data of the file
    """

    metadata_row = db_schema.Metadata(
        scanNumber=metadata_object["scanNumber"],
        time_epoch=convert_epoch_string_to_int(metadata_object["time_epoch"]),
        time=convert_time_string_to_datetime(metadata_object["time"]),
        user_name=metadata_object["user_name"],
        source_beamBad=metadata_object["source_beamBad"],
        source_CCDshutter=metadata_object["source_CCDshutter"],
        source_monoTransStatus=metadata_object["source_monoTransStatus"],
        source_energy_unit=metadata_object["source_energy_unit"],
        source_energy=metadata_object["source_energy"],
        source_IDgap_unit=metadata_object["source_IDgap_unit"],
        source_IDgap=metadata_object["source_IDgap"],
        source_IDtaper_unit=metadata_object["source_IDtaper_unit"],
        source_IDtaper=metadata_object["source_IDtaper"],
        source_ringCurrent_unit=metadata_object["source_ringCurrent_unit"],
        source_ringCurrent=metadata_object["source_ringCurrent"],
        sample_XYZ_unit=metadata_object["sample_XYZ_unit"],
        sample_XYZ_desc=metadata_object["sample_XYZ_desc"],
        sample_XYZ=metadata_object["sample_XYZ"],
        knifeEdge_XYZ_unit=metadata_object["knife-edge_XYZ_unit"],
        knifeEdge_XYZ_desc=metadata_object["knife-edge_XYZ_desc"],
        knifeEdge_XYZ=metadata_object["knife-edge_XYZ"],
        knifeEdge_knifeScan_unit=metadata_object["knife-edge_knifeScan_unit"],
        knifeEdge_knifeScan=metadata_object["knife-edge_knifeScan"],
        mda_file=metadata_object["mda_file"],
        scanEnd_abort=metadata_object["scanEnd_abort"],
        scanEnd_time_epoch=convert_epoch_string_to_int(metadata_object["scanEnd_time_epoch"]),
        scanEnd_time=metadata_object["scanEnd_time"],
        scanEnd_scanDuration_unit=metadata_object["scanEnd_scanDuration_unit"],
        scanEnd_scanDuration=metadata_object["scanEnd_scanDuration"],
        scanEnd_source_beamBad=metadata_object["scanEnd_source_beamBad"],
        scanEnd_source_ringCurrent_unit=metadata_object["scanEnd_source_ringCurrent_unit"],
        scanEnd_source_ringCurrent=metadata_object["scanEnd_source_ringCurrent"],
    )
    return metadata_row


def import_scan_row(scan_object):
    """Create a Scan ORM object from a scan dictionary."""
    scan_row = db_schema.Scan(
        scanNumber=scan_object["scanNumber"],
        scan_dim=scan_object["scan_dim"],
        scan_npts=scan_object["scan_npts"],
        scan_after=scan_object["scan_after"],
        scan_positioner1_PV=scan_object["scan_positioner1_PV"],
        scan_positioner1_ar=scan_object["scan_positioner1_ar"],
        scan_positioner1_mode=scan_object["scan_positioner1_mode"],
        scan_positioner1=scan_object["scan_positioner1"],
        scan_positioner2_PV=scan_object["scan_positioner2_PV"],
        scan_positioner2_ar=scan_object["scan_positioner2_ar"],
        scan_positioner2_mode=scan_object["scan_positioner2_mode"],
        scan_positioner2=scan_object["scan_positioner2"],
        scan_positioner3_PV=scan_object["scan_positioner3_PV"],
        scan_positioner3_ar=scan_object["scan_positioner3_ar"],
        scan_positioner3_mode=scan_object["scan_positioner3_mode"],
        scan_positioner3=scan_object["scan_positioner3"],
        scan_positioner4_PV=scan_object["scan_positioner4_PV"],
        scan_positioner4_ar=scan_object["scan_positioner4_ar"],
        scan_positioner4_mode=scan_object["scan_positioner4_mode"],
        scan_positioner4=scan_object["scan_positioner4"],
        scan_detectorTrig1_PV=scan_object["scan_detectorTrig1_PV"],
        scan_detectorTrig1_VAL=scan_object["scan_detectorTrig1_VAL"],
        scan_detectorTrig2_PV=scan_object["scan_detectorTrig2_PV"],
        scan_detectorTrig2_VAL=scan_object["scan_detectorTrig2_VAL"],
        scan_detectorTrig3_PV=scan_object["scan_detectorTrig3_PV"],
        scan_detectorTrig3_VAL=scan_object["scan_detectorTrig3_VAL"],
        scan_detectorTrig4_PV=scan_object["scan_detectorTrig4_PV"],
        scan_detectorTrig4_VAL=scan_object["scan_detectorTrig4_VAL"],
        scan_cpt=scan_object["scan_cpt"],
    )
    return scan_row


def parse_all_scans_from_xml(xml_bytes):
    """
    Parse ALL <fullScan> elements from an XML log file.

    Returns a list of dicts, one per scan, each containing:
        - 'scan_index': index of the scan element in the XML root
        - 'scanNumber': the scan number as a string
        - 'log': the parsed metadata dict (from parse_metadata)
        - 'scans': list of parsed scan-dimension dicts (from parse_metadata)
        - 'time': timestamp string
        - 'user_name': user name string
        - 'energy': energy value string
        - 'sample_XYZ': sample position string
        - 'num_dims': number of scan dimensions
    """
    root = ET.fromstring(xml_bytes)

    return _parse_scans_from_root(root)


def check_existing_scan_numbers(scan_numbers):
    """
    Check which scan numbers already exist in the database.

    Args:
        scan_numbers: list of scan number values (strings or ints)

    Returns:
        set of scan numbers (as ints) that already exist in the DB
    """
    int_scan_numbers = [int(sn) for sn in scan_numbers]

    with Session(session_utils.get_engine()) as session:
        existing = (
            session.query(db_schema.Metadata.scanNumber)
            .filter(db_schema.Metadata.scanNumber.in_(int_scan_numbers))
            .all()
        )
        return {row[0] for row in existing}


def bulk_import_scans(parsed_scans, catalog_defaults):
    """
    Import multiple scans into the database, committing each scan individually
    so that a failure in one scan does not roll back the others.

    Args:
        parsed_scans: list of dicts from parse_all_scans_from_xml(),
                      filtered to only scans the user wants to import
        catalog_defaults: dict with keys: filefolder, filenamePrefix,
                         aperture, sample_name, notes

    Returns:
        dict mapping scanNumber -> {'status': 'success'|'skipped'|'failed', 'message': str}
    """
    results = {}

    for parsed in parsed_scans:
        scan_number = parsed["scanNumber"]

        with Session(session_utils.get_engine()) as session:
            try:
                # Check if already exists
                exists = (
                    session.query(db_schema.Metadata).filter(db_schema.Metadata.scanNumber == int(scan_number)).first()
                )

                if exists:
                    results[scan_number] = {"status": "skipped", "message": f"Scan {scan_number} already exists"}
                    continue

                # Create metadata ORM object
                metadata = import_metadata_row(parsed["log"])

                # Create scan dimension ORM objects and compute motor groups
                motor_group_totals = {}
                for scan_dict in parsed["scans"]:
                    scan_row = import_scan_row(scan_dict)
                    session.add(scan_row)
                    motor_group_totals = update_motor_group_totals(motor_group_totals, scan_row)

                # Apply motor group totals with fallback logic
                if motor_group_totals:
                    for specific_motor_group in ["sample", "depth"]:
                        if specific_motor_group not in motor_group_totals:
                            if any(group.get("completed", 0) for group in motor_group_totals.values()):
                                motor_group_totals[specific_motor_group] = {"points": 0, "completed": 1}

                    for motor_group, totals in motor_group_totals.items():
                        setattr(metadata, f"motorGroup_{motor_group}_npts_total", totals["points"])
                        setattr(metadata, f"motorGroup_{motor_group}_cpt_total", totals["completed"])

                session.add(metadata)

                # Create catalog entry
                catalog = db_schema.Catalog(
                    scanNumber=int(scan_number),
                    filefolder=catalog_defaults.get("filefolder", ""),
                    filenamePrefix=catalog_defaults.get("filenamePrefix", []),
                    aperture=catalog_defaults.get("aperture") or "none",
                    sample_name=catalog_defaults.get("sample_name", ""),
                    notes=catalog_defaults.get("notes", ""),
                )
                session.add(catalog)

                session.commit()

                results[scan_number] = {"status": "success", "message": f"Scan {scan_number} imported successfully"}

            except Exception as e:
                session.rollback()
                results[scan_number] = {"status": "failed", "message": f"Error importing scan {scan_number}: {str(e)}"}

    return results
