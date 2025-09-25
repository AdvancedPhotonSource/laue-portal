"""
Contains scan metadata not contained in the scan XML log. 
"""
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String, JSON, ForeignKey
from laue_portal.database.base import Base


class Catalog(Base):
    __tablename__ = "catalog"

    catalog_id: Mapped[int] = mapped_column(primary_key=True)
    scanNumber: Mapped[int] = mapped_column(ForeignKey("metadata.scanNumber"), unique=True)

    filefolder: Mapped[str] = mapped_column(String)  # infile
    # filenamePrefix: Mapped[str] = mapped_column(String) # infile
    filenamePrefix: Mapped[list[str]] = mapped_column(JSON)  # infile

    aperture: Mapped[str] = mapped_column(String)
    sample_name: Mapped[str] = mapped_column(String, nullable=True)
    notes: Mapped[str] = mapped_column(String, nullable=True)
