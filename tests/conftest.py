"""
Shared pytest fixtures and utilities for the Laue Portal test suite.

This module provides reusable database fixtures and entity factories
to reduce code duplication across test files.
"""

import datetime
import os
import sys
import tempfile
from typing import Any
from unittest.mock import patch

import pytest

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)


def create_test_metadata(scan_number: int = 1) -> Any:
    """
    Factory function to create a test Metadata record.

    Args:
        scan_number: The scan number for the metadata record

    Returns:
        db_schema.Metadata: A test metadata record
    """
    import laue_portal.database.db_schema as db_schema

    return db_schema.Metadata(
        scanNumber=scan_number,
        time_epoch=1640995200,
        time=datetime.datetime(2022, 1, 1, 0, 0, 0),
        user_name="test_user",
        source_beamBad="false",
        source_CCDshutter="open",
        source_monoTransStatus="ok",
        source_energy_unit="keV",
        source_energy=10.0,
        source_IDgap_unit="mm",
        source_IDgap=5.0,
        source_IDtaper_unit="mm",
        source_IDtaper=0.0,
        source_ringCurrent_unit="mA",
        source_ringCurrent=100.0,
        sample_XYZ_unit="mm",
        sample_XYZ_desc="Sample position",
        sample_XYZ="0,0,0",
        knifeEdge_XYZ_unit="mm",
        knifeEdge_XYZ_desc="Knife edge position",
        knifeEdge_XYZ="0,0,0",
        knifeEdge_knifeScan_unit="mm",
        knifeEdge_knifeScan=1.0,
        mda_file="test.mda",
        scanEnd_abort="false",
        scanEnd_time_epoch=1640995300,
        scanEnd_time="2022-01-01T00:01:40",
        scanEnd_scanDuration_unit="s",
        scanEnd_scanDuration=100.0,
        scanEnd_source_beamBad="false",
        scanEnd_source_ringCurrent_unit="mA",
        scanEnd_source_ringCurrent=100.0,
    )


def create_test_reconstruction_run(scan_number: int | None = 1, job_id: int = 1) -> Any:
    """Create a unified wire reconstruction run for tests."""
    import laue_portal.database.db_schema as db_schema

    return db_schema.ReconstructionRun(
        scan_number=scan_number,
        job_id=job_id,
        method="wire",
        input_path="/test/input",
        output_path="/test/output/rec_1",
        author="test_user",
        notes="test reconstruction",
        algorithm_version="test-version",
        created_at=datetime.datetime(2022, 1, 1, 0, 0, 0),
    )


def create_test_wire_reconstruction_parameters(reconstruction_id: int | None = None) -> Any:
    """Create wire-specific parameters for a unified reconstruction run."""
    import laue_portal.database.db_schema as db_schema

    values = {
        "filename_prefixes": ["test_*.h5"],
        "geometry_file": "/test/geometry.xml",
        "percent_brightest": 10.0,
        "wire_edges": "0 1",
        "depth_start": -10.0,
        "depth_end": 10.0,
        "depth_resolution": 0.5,
        "num_threads": 4,
        "memory_limit_mb": 1024,
        "scan_points": "1-10",
        "scan_points_len": 10,
        "verbose": 1,
    }
    if reconstruction_id is not None:
        values["reconstruction_id"] = reconstruction_id
    return db_schema.WireReconstructionParameters(**values)


def create_test_indexing_run(
    scan_number: int | None = 1,
    job_id: int = 2,
    reconstruction_id: int | None = None,
) -> Any:
    """Create a unified LaueGo indexing run for tests."""
    import laue_portal.database.db_schema as db_schema

    return db_schema.IndexingRun(
        scan_number=scan_number,
        reconstruction_id=reconstruction_id,
        job_id=job_id,
        method="lauego",
        input_path="/test/input",
        output_path="/test/output/index_1",
        author="test_user",
        notes="test indexing",
        algorithm_version="test-version",
        created_at=datetime.datetime(2022, 1, 1, 0, 0, 0),
    )


def create_test_lauego_parameters(indexing_id: int | None = None) -> Any:
    """Create LaueGo-specific parameters for a unified indexing run."""
    import laue_portal.database.db_schema as db_schema

    values = {
        "filename_prefixes": ["test_%d.h5"],
        "threshold": 250,
        "threshold_ratio": None,
        "max_rfactor": 0.5,
        "box_size": 18,
        "max_number": 300,
        "min_separation": 20,
        "peak_shape": "Lorentzian",
        "scan_points": "1-2",
        "scan_points_len": 2,
        "depth_range": None,
        "depth_range_len": None,
        "detector_crop_x1": 0,
        "detector_crop_x2": 2047,
        "detector_crop_y1": 0,
        "detector_crop_y2": 2047,
        "min_size": 3.0,
        "max_peaks": 200,
        "smooth": False,
        "mask_file": None,
        "index_kev_max_calc": 17.2,
        "index_kev_max_test": 35.0,
        "index_angle_tolerance": 0.1,
        "index_h": 0,
        "index_k": 0,
        "index_l": 1,
        "index_cone": 72.0,
        "energy_unit": "keV",
        "exposure_unit": "sec",
        "cosmic_filter": True,
        "reciprocal_lattice_unit": "1/nm",
        "lattice_parameters_unit": "nm",
        "output_xml": "output.xml",
        "geometry_file": "/test/geometry.xml",
        "crystal_file": "/test/crystal.xtal",
        "depth": None,
        "beamline": "34ID-E",
    }
    if indexing_id is not None:
        values["indexing_id"] = indexing_id
    return db_schema.LaueGoIndexingParameters(**values)


def create_test_catalog(scan_number: int = 1) -> Any:
    """
    Factory function to create a test Catalog record.

    Args:
        scan_number: The scan number for the catalog record

    Returns:
        db_schema.Catalog: A test catalog record
    """
    import laue_portal.database.db_schema as db_schema

    return db_schema.Catalog(
        scanNumber=scan_number,
        filefolder="/test/folder",
        filenamePrefix="test_prefix",
        aperture="50um",
        sample_name="test_sample",
    )


def create_test_scan(scan_number: int = 1) -> Any:
    """
    Factory function to create a test Scan record.

    Args:
        scan_number: The scan number for the scan record

    Returns:
        db_schema.Scan: A test scan record
    """
    import laue_portal.database.db_schema as db_schema

    return db_schema.Scan(
        scanNumber=scan_number,
        scan_dim=2,
        scan_npts=100,
        scan_after="true",
        scan_positioner1_PV="test:pos1",
        scan_positioner1_ar="true",
        scan_positioner1_mode="absolute",
        scan_positioner1="motor1",
        scan_positioner2_PV="test:pos2",
        scan_positioner2_ar="true",
        scan_positioner2_mode="absolute",
        scan_positioner2="motor2",
        scan_positioner3_PV="test:pos3",
        scan_positioner3_ar="false",
        scan_positioner3_mode="relative",
        scan_positioner3="motor3",
        scan_positioner4_PV="test:pos4",
        scan_positioner4_ar="false",
        scan_positioner4_mode="relative",
        scan_positioner4="motor4",
        scan_detectorTrig1_PV="test:det1",
        scan_detectorTrig1_VAL="1",
        scan_detectorTrig2_PV="test:det2",
        scan_detectorTrig2_VAL="1",
        scan_detectorTrig3_PV="test:det3",
        scan_detectorTrig3_VAL="0",
        scan_detectorTrig4_PV="test:det4",
        scan_detectorTrig4_VAL="0",
        scan_cpt=1000,
    )


def create_test_job(scan_number: int = 1) -> Any:
    """
    Factory function to create a test Job record.

    Args:
        scan_number: The scan number for the job record (used as job_id)

    Returns:
        db_schema.Job: A test job record
    """
    import laue_portal.database.db_schema as db_schema

    return db_schema.Job(
        job_id=scan_number,
        computer_name="TEST_COMPUTER",
        status=1,  # Running
        priority=5,
        submit_time=datetime.datetime(2022, 1, 1, 0, 0, 0),
        start_time=datetime.datetime(2022, 1, 1, 0, 1, 0),
        finish_time=datetime.datetime(2022, 1, 1, 0, 2, 0),
        messages="Test job for smoke test",
    )


def create_test_database_with_entities(entities: list[str], scan_number: int = 1) -> tuple[Any, str, list[Any]]:
    """
    Create a temporary database with specified entities.

    Args:
        entities: Entity types to create (metadata, catalog, scan, or job)
        scan_number: The scan number to use for all entities

    Returns:
        tuple: (test_engine, test_db_file, [created_entities])
    """
    # Create a temporary database file for testing
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
        test_db_file = temp_db.name

    # Mock the config to use test database
    with patch("laue_portal.config.db_file", test_db_file):
        # Import after patching config
        import sqlalchemy

        import laue_portal.database.db_schema as db_schema

        # Create a new engine for the test database and create tables
        test_engine = sqlalchemy.create_engine(f"sqlite:///{test_db_file}")
        db_schema.Base.metadata.create_all(test_engine)

        # Create requested entities
        created_entities = []
        entity_map = {
            "metadata": create_test_metadata,
            "catalog": create_test_catalog,
            "scan": create_test_scan,
            "job": create_test_job,
        }

        for entity_type in entities:
            if entity_type in entity_map:
                entity = entity_map[entity_type](scan_number)
                created_entities.append(entity)
            else:
                raise ValueError(f"Unknown entity type: {entity_type}")

        return test_engine, test_db_file, created_entities


@pytest.fixture
def test_metadata_database():
    """
    Pytest fixture that creates a temporary database with metadata, scan, and catalog data.
    Compatible with existing test_metadata_retrievers.py tests.

    Returns:
        tuple: (test_engine, test_db_file, test_metadata, test_scan, test_catalog)
    """
    test_engine, test_db_file, entities = create_test_database_with_entities(["metadata", "scan", "catalog"])

    try:
        yield test_engine, test_db_file, entities[0], entities[1], entities[2]
    finally:
        # Clean up temporary database file
        if os.path.exists(test_db_file):
            os.unlink(test_db_file)


@pytest.fixture
def empty_test_database():
    """
    Pytest fixture that creates a temporary empty database (no test data).
    Compatible with all existing empty database tests.

    Returns:
        tuple: (test_engine, test_db_file)
    """
    # Create a temporary database file for testing
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
        test_db_file = temp_db.name

    try:
        # Mock the config to use test database
        with patch("laue_portal.config.db_file", test_db_file):
            # Import after patching config
            import sqlalchemy

            import laue_portal.database.db_schema as db_schema

            # Create a new engine for the test database and create tables
            test_engine = sqlalchemy.create_engine(f"sqlite:///{test_db_file}")
            db_schema.Base.metadata.create_all(test_engine)

            yield test_engine, test_db_file

    finally:
        # Clean up temporary database file
        if os.path.exists(test_db_file):
            os.unlink(test_db_file)


# Alias fixtures for backward compatibility with different names used in test files
empty_metadata_database = empty_test_database
