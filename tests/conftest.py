"""
Shared pytest fixtures and utilities for the Laue Portal test suite.

This module provides reusable database fixtures and entity factories
to reduce code duplication across test files.
"""

import sys
import os
import tempfile
from unittest.mock import patch
import pytest
import datetime
from typing import List, Optional, Tuple, Any

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
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
        user_name='test_user',
        source_beamBad='false',
        source_CCDshutter='open',
        source_monoTransStatus='ok',
        source_energy_unit='keV',
        source_energy=10.0,
        source_IDgap_unit='mm',
        source_IDgap=5.0,
        source_IDtaper_unit='mm',
        source_IDtaper=0.0,
        source_ringCurrent_unit='mA',
        source_ringCurrent=100.0,
        sample_XYZ_unit='mm',
        sample_XYZ_desc='Sample position',
        sample_XYZ='0,0,0',
        knifeEdge_XYZ_unit='mm',
        knifeEdge_XYZ_desc='Knife edge position',
        knifeEdge_XYZ='0,0,0',
        knifeEdge_knifeScan_unit='mm',
        knifeEdge_knifeScan=1.0,
        mda_file='test.mda',
        scanEnd_abort='false',
        scanEnd_time_epoch=1640995300,
        scanEnd_time='2022-01-01T00:01:40',
        scanEnd_scanDuration_unit='s',
        scanEnd_scanDuration=100.0,
        scanEnd_source_beamBad='false',
        scanEnd_source_ringCurrent_unit='mA',
        scanEnd_source_ringCurrent=100.0,
    )


def create_test_recon(scan_number: int = 1) -> Any:
    """
    Factory function to create a test Recon record.
    
    Args:
        scan_number: The scan number for the recon record
        
    Returns:
        db_schema.Recon: A test reconstruction record
    """
    import laue_portal.database.db_schema as db_schema
    
    return db_schema.Recon(
        scanNumber=scan_number,
        calib_id=1,
        job_id=1,
        
        # Required file parameters
        file_path='/test/path',
        file_output='/test/output',
        file_range=[1, 100],
        file_threshold=50,
        file_frame=[0, 100, 0, 100],
        file_ext='h5',
        file_stacked=False,
        file_h5_key='data',
        
        # Required comp parameters
        comp_server='test_server',
        comp_workers=1,
        comp_usegpu=False,
        comp_batch_size=1,
        
        # Required geo parameters
        geo_mask_path='/test/mask',
        geo_mask_reversed=False,
        geo_mask_bitsizes=[1.0, 1.0, 1.0],
        geo_mask_thickness=1.0,
        geo_mask_resolution=1.0,
        geo_mask_smoothness=1.0,
        geo_mask_alpha=1.0,
        geo_mask_widening=1.0,
        geo_mask_pad=1.0,
        geo_mask_stretch=1.0,
        geo_mask_shift=1.0,
        
        geo_mask_focus_cenx=1.0,
        geo_mask_focus_dist=1.0,
        geo_mask_focus_anglez=1.0,
        geo_mask_focus_angley=1.0,
        geo_mask_focus_anglex=1.0,
        geo_mask_focus_cenz=1.0,
        
        geo_mask_cal_id=1,
        geo_mask_cal_path='/test/cal',
        
        geo_scanner_step=1.0,
        geo_scanner_rot=[0.0, 0.0, 0.0],
        geo_scanner_axis=[1.0, 0.0, 0.0],
        
        geo_detector_shape=[100, 100],
        geo_detector_size=[10.0, 10.0],
        geo_detector_rot=[0.0, 0.0, 0.0],
        geo_detector_pos=[0.0, 0.0, 100.0],
        
        geo_source_offset=1.0,
        geo_source_grid=[1.0, 1.0, 1.0],
        
        # Required algo parameters
        algo_iter=10,
        algo_pos_method='test',
        algo_pos_regpar=1,
        algo_pos_init='test',
        algo_sig_recon=True,
        algo_sig_method='test',
        algo_sig_order=1,
        algo_sig_scale=1,
        algo_sig_init_maxsize=1,
        algo_sig_init_avgsize=1,
        algo_sig_init_atol=1,
        algo_ene_recon=True,
        algo_ene_exact=True,
        algo_ene_method='test',
        algo_ene_range=[1, 100]
    )


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
        filefolder='/test/folder',
        filenamePrefix='test_prefix',
        outputFolder='/test/output',
        geoFile='/test/geo.yaml',
        aperture='50um',
        sample_name='test_sample'
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
        scan_after='true',
        scan_positioner1_PV='test:pos1',
        scan_positioner1_ar='true',
        scan_positioner1_mode='absolute',
        scan_positioner1='motor1',
        scan_positioner2_PV='test:pos2',
        scan_positioner2_ar='true',
        scan_positioner2_mode='absolute',
        scan_positioner2='motor2',
        scan_positioner3_PV='test:pos3',
        scan_positioner3_ar='false',
        scan_positioner3_mode='relative',
        scan_positioner3='motor3',
        scan_positioner4_PV='test:pos4',
        scan_positioner4_ar='false',
        scan_positioner4_mode='relative',
        scan_positioner4='motor4',
        scan_detectorTrig1_PV='test:det1',
        scan_detectorTrig1_VAL='1',
        scan_detectorTrig2_PV='test:det2',
        scan_detectorTrig2_VAL='1',
        scan_detectorTrig3_PV='test:det3',
        scan_detectorTrig3_VAL='0',
        scan_detectorTrig4_PV='test:det4',
        scan_detectorTrig4_VAL='0',
        scan_cpt=1000
    )


def create_test_peakindex(scan_number: int = 1, recon_id: Optional[int] = None) -> Any:
    """
    Factory function to create a test PeakIndex record.
    
    Args:
        scan_number: The scan number for the peakindex record
        recon_id: The recon_id for the peakindex record (will be set after recon is saved if None)
        
    Returns:
        db_schema.PeakIndex: A test peakindex record
    """
    import laue_portal.database.db_schema as db_schema
    
    return db_schema.PeakIndex(
        scanNumber=scan_number,
        job_id=scan_number,
        recon_id=recon_id,  # This will be set after recon is saved if None
        
        # Required peak search and indexing parameters
        threshold=250,
        thresholdRatio=-1,
        maxRfactor=0.5,
        boxsize=18,
        max_number=50,  # maps to max_peaks from defaults
        min_separation=40,
        peakShape='Lorentzian',
        scanPointStart=1,
        scanPointEnd=2,
        detectorCropX1=0,
        detectorCropX2=2047,
        detectorCropY1=0,
        detectorCropY2=2047,
        min_size=1.13,
        max_peaks=50,
        smooth=False,  # Boolean field
        maskFile=None,  # Optional field
        indexKeVmaxCalc=17.2,
        indexKeVmaxTest=30.0,
        indexAngleTolerance=0.1,
        indexH=1,
        indexK=1,
        indexL=1,
        indexCone=72.0,
        energyUnit='keV',
        exposureUnit='sec',
        cosmicFilter=True,  # Boolean field
        recipLatticeUnit='1/nm',
        latticeParametersUnit='nm',
        peaksearchPath=None,  # Optional field
        p2qPath=None,  # Optional field
        indexingPath=None,  # Optional field
        outputFolder='tests/data/output',
        filefolder='tests/data/gdata',
        filenamePrefix='HAs_long_laue1_',
        geoFile='tests/data/geo/geoN_2022-03-29_14-15-05.xml',
        crystFile='tests/data/crystal/Al.xtal',
        depth='2D',  # String field, using '2D' instead of NaN
        beamline='34ID-E'
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
        computer_name='TEST_COMPUTER',
        status=1,  # Running
        priority=5,
        submit_time=datetime.datetime(2022, 1, 1, 0, 0, 0),
        start_time=datetime.datetime(2022, 1, 1, 0, 1, 0),
        finish_time=datetime.datetime(2022, 1, 1, 0, 2, 0),
        author='test_user',
        notes='Test job for smoke test'
    )


def create_test_database_with_entities(
    entities: List[str], 
    scan_number: int = 1
) -> Tuple[Any, str, List[Any]]:
    """
    Create a temporary database with specified entities.
    
    Args:
        entities: List of entity types to create ('metadata', 'recon', 'catalog', 'scan', 'peakindex')
        scan_number: The scan number to use for all entities
        
    Returns:
        tuple: (test_engine, test_db_file, [created_entities])
    """
    # Create a temporary database file for testing
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
        test_db_file = temp_db.name

    # Mock the config to use test database
    with patch('config.db_file', test_db_file):
        # Import after patching config
        import laue_portal.database.db_schema as db_schema
        import sqlalchemy
        
        # Create a new engine for the test database and create tables
        test_engine = sqlalchemy.create_engine(f'sqlite:///{test_db_file}')
        db_schema.Base.metadata.create_all(test_engine)
        
        # Create requested entities
        created_entities = []
        entity_map = {
            'metadata': create_test_metadata,
            'recon': create_test_recon,
            'catalog': create_test_catalog,
            'scan': create_test_scan,
            'peakindex': create_test_peakindex,
            'job': create_test_job
        }
        
        for entity_type in entities:
            if entity_type in entity_map:
                entity = entity_map[entity_type](scan_number)
                created_entities.append(entity)
            else:
                raise ValueError(f"Unknown entity type: {entity_type}")
        
        return test_engine, test_db_file, created_entities


@pytest.fixture
def test_database():
    """
    Pytest fixture that creates a temporary database with metadata, job, recon, and catalog data.
    Compatible with existing test_recon_table.py tests.
    
    Returns:
        tuple: (test_engine, test_db_file, test_metadata, test_job, test_recon, test_catalog)
    """
    test_engine, test_db_file, entities = create_test_database_with_entities(
        ['metadata', 'job', 'recon', 'catalog']
    )
    
    try:
        yield test_engine, test_db_file, entities[0], entities[1], entities[2], entities[3]
    finally:
        # Clean up temporary database file
        if os.path.exists(test_db_file):
            os.unlink(test_db_file)


@pytest.fixture
def test_metadata_database():
    """
    Pytest fixture that creates a temporary database with metadata, scan, and catalog data.
    Compatible with existing test_metadata_retrievers.py tests.
    
    Returns:
        tuple: (test_engine, test_db_file, test_metadata, test_scan, test_catalog)
    """
    test_engine, test_db_file, entities = create_test_database_with_entities(
        ['metadata', 'scan', 'catalog']
    )
    
    try:
        yield test_engine, test_db_file, entities[0], entities[1], entities[2]
    finally:
        # Clean up temporary database file
        if os.path.exists(test_db_file):
            os.unlink(test_db_file)


@pytest.fixture
def test_peakindex_database():
    """
    Pytest fixture that creates a temporary database with metadata, job, recon, and peakindex data.
    Compatible with existing test_peakindex_retrievers.py tests.
    
    Returns:
        tuple: (test_engine, test_db_file, test_metadata, test_job, test_recon, test_peakindex)
    """
    test_engine, test_db_file, entities = create_test_database_with_entities(
        ['metadata', 'job', 'recon', 'peakindex']
    )
    
    try:
        yield test_engine, test_db_file, entities[0], entities[1], entities[2], entities[3]
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
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
        test_db_file = temp_db.name

    try:
        # Mock the config to use test database
        with patch('config.db_file', test_db_file):
            # Import after patching config
            import laue_portal.database.db_schema as db_schema
            import sqlalchemy
            
            # Create a new engine for the test database and create tables
            test_engine = sqlalchemy.create_engine(f'sqlite:///{test_db_file}')
            db_schema.Base.metadata.create_all(test_engine)
            
            yield test_engine, test_db_file
            
    finally:
        # Clean up temporary database file
        if os.path.exists(test_db_file):
            os.unlink(test_db_file)


# Alias fixtures for backward compatibility with different names used in test files
empty_metadata_database = empty_test_database
empty_peakindex_database = empty_test_database
