"""Canonical workflow identities used by workflow submission forms."""

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from laue_portal.database import db_schema

_IDENTITY_RE = re.compile(r"^(SN|R|I)(\d+)$", re.IGNORECASE)


@dataclass(frozen=True)
class WorkflowIdentity:
    """One scan/reconstruction/indexing provenance chain."""

    scan_number: int | None = None
    reconstruction_id: int | None = None
    indexing_id: int | None = None


def parse_workflow_identities(value, session: Session) -> list[WorkflowIdentity]:
    """Parse semicolon-separated ``SN``, ``R``, and ``I`` identities.

    A single entry may show its full chain (for example ``SN12 | R3``).
    Parent values are loaded from the unified run tables and explicit values
    must agree with the persisted chain.
    """

    if value is None or not str(value).strip():
        return [WorkflowIdentity()]

    identities = []
    for entry in str(value).split(";"):
        entry = entry.strip()
        if not entry or entry.lower() == "none":
            identities.append(WorkflowIdentity())
            continue

        explicit = {}
        for token in entry.split("|"):
            token = token.strip()
            match = _IDENTITY_RE.fullmatch(token)
            if match is None:
                raise ValueError(f"Invalid workflow identity: {token!r}; use SN<number>, R<number>, or I<number>")
            prefix, number = match.groups()
            key = {"SN": "scan_number", "R": "reconstruction_id", "I": "indexing_id"}[prefix.upper()]
            if key in explicit:
                raise ValueError(f"Duplicate {prefix.upper()} identity in {entry!r}")
            explicit[key] = int(number)

        scan_number = explicit.get("scan_number")
        reconstruction_id = explicit.get("reconstruction_id")
        indexing_id = explicit.get("indexing_id")

        if indexing_id is not None:
            indexing = session.get(db_schema.IndexingRun, indexing_id)
            if indexing is None:
                raise ValueError(f"Indexing I{indexing_id} was not found")
            scan_number = _agree("scan", scan_number, indexing.scan_number, entry)
            reconstruction_id = _agree("reconstruction", reconstruction_id, indexing.reconstruction_id, entry)

        if reconstruction_id is not None:
            reconstruction = session.get(db_schema.ReconstructionRun, reconstruction_id)
            if reconstruction is None:
                raise ValueError(f"Reconstruction R{reconstruction_id} was not found")
            scan_number = _agree("scan", scan_number, reconstruction.scan_number, entry)

        identities.append(WorkflowIdentity(scan_number, reconstruction_id, indexing_id))

    return identities


def _agree(label: str, explicit: int | None, persisted: int | None, entry: str) -> int | None:
    if explicit is not None and persisted is not None and explicit != persisted:
        raise ValueError(f"{entry!r} has conflicting {label} identities")
    return explicit if explicit is not None else persisted


def merged_identity_value(identities: list[WorkflowIdentity], field: str) -> str | None:
    """Return one value or a semicolon-aligned value for pooled form parsing."""

    values = [getattr(identity, field) for identity in identities]
    if not values or all(value is None for value in values):
        return None
    if all(value == values[0] for value in values):
        return str(values[0]) if values[0] is not None else None
    return "; ".join("None" if value is None else str(value) for value in values)
