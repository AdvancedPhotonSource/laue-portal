"""Shared database-adjacent form and path helpers."""

import os

import laue_portal.database.db_schema as db_schema


def resolve_path_with_root(path, root_path):
    """Resolve a relative path under ``root_path`` while preserving absolute paths."""
    if not path:
        return ""
    if os.path.isabs(path):
        return path
    return os.path.join(root_path, path.lstrip("/"))


def remove_root_path_prefix(file_path, root_path):
    """Return ``file_path`` relative to ``root_path`` when it is below that root."""
    if not file_path:
        return ""
    if root_path and file_path.startswith(root_path):
        return file_path[len(root_path) :].lstrip("/")
    return file_path


def import_catalog_row(catalog_object):
    """Create a catalog row from imported scan-catalog data."""
    return db_schema.Catalog(
        scanNumber=catalog_object["scanNumber"],
        filefolder=catalog_object["filefolder"],
        filenamePrefix=catalog_object["filenamePrefix"],
        aperture=catalog_object["aperture"]["options"],
        sample_name=catalog_object["sample_name"],
        notes=catalog_object["notes"],
    )


def get_catalog_by_scan_number(session, scan_number):
    """Return the catalog row identified by its unique scan number."""
    return session.query(db_schema.Catalog).filter(db_schema.Catalog.scanNumber == scan_number).one_or_none()


def get_catalog_data(session, scan_number, root_path="", CATALOG_DEFAULTS=None):
    """Return catalog paths and filename prefixes for one scan."""
    catalog_data = get_catalog_by_scan_number(session, scan_number)
    if catalog_data:
        filefolder = catalog_data.filefolder
        return {
            "filefolder": filefolder,
            "filenamePrefix": catalog_data.filenamePrefix,
            "data_path": remove_root_path_prefix(filefolder, root_path),
        }
    if CATALOG_DEFAULTS:
        filefolder = CATALOG_DEFAULTS.get("filefolder", "")
        return {
            "filefolder": filefolder,
            "filenamePrefix": CATALOG_DEFAULTS.get("filenamePrefix", ""),
            "data_path": filefolder,
        }
    return {"filefolder": "", "filenamePrefix": "", "data_path": ""}


def parse_parameter(parameter_value, num_inputs=None, delimiter=";"):
    """Split one pooled form value and optionally broadcast it to every input."""
    if parameter_value is None:
        values = [None]
    else:
        str_value = str(parameter_value)
        if delimiter in str_value:
            values = [
                None if value.strip().lower() in {"none", ""} else value.strip() for value in str_value.split(delimiter)
            ]
        elif str_value.lower() in {"none", ""}:
            values = [None]
        else:
            values = [parameter_value]

    if num_inputs is not None:
        if len(values) == 1 and num_inputs > 1:
            values *= num_inputs
        elif len(values) != num_inputs and len(values) != 1:
            raise ValueError(f"Parameter has {len(values)} values but there are {num_inputs} inputs")
    return values


def get_num_inputs_from_fields(fields_dict, delimiter=";"):
    """Return the largest pooled-value count across a set of form fields."""
    num_inputs = 1
    for field_value in fields_dict.values():
        if field_value is not None and field_value != "":
            num_inputs = max(num_inputs, len(str(field_value).split(delimiter)))
    return num_inputs
