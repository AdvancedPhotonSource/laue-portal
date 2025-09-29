"""
Compatibility shim for SQLAlchemy ORM models.

This module re-exports the split models so existing imports
(`import laue_portal.database.db_schema as db_schema`) continue to work.

Models are now organized under:
- laue_portal/database/base.py            -> Declarative Base
- laue_portal/database/models/*.py        -> Individual model classes
"""
from laue_portal.database.base import Base
from laue_portal.database.models import (
    Metadata,
    Scan,
    Catalog,
    Job,
    SubJob,
    Calib,
    Recon,
    WireRecon,
    PeakIndex,
)

__all__ = [
    "Base",
    "Metadata",
    "Scan",
    "Catalog",
    "Job",
    "SubJob",
    "Calib",
    "Recon",
    "WireRecon",
    "PeakIndex",
    "MASK_FOCUS_TABLE",
]

# NOTE: Not Implemented
MASK_FOCUS_TABLE = [
    "cenx (Z)",
    "dist (Y)",
    "anglez (angleX)",
    "angley (angleY)",
    "anglex (angleZ)",
    "cenz (X)",
    "shift parameter",
]
