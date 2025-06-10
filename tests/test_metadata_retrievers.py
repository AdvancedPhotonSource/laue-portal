"""
Smoke tests for metadata retrieval functions in the Laue Portal application.

This test module verifies that metadata retrieval functions like _get_metadatas
can execute without errors and return properly formatted data.
"""

import sys
import os
import tempfile
from unittest.mock import patch
import pytest
import datetime
from dash.exceptions import PreventUpdate

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)


@pytest.fixture
def test_metadata_database():
    """
    Pytest fixture that creates a temporary database with test metadata and scan data.
    
    Returns:
        tuple: (test_engine, test_db_file, test_metadata, test_scan)
    """
    # Create a temporary database file for testing
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
        test_db_file = temp_db.name

    try:
        # Mock the config to use test database
        with patch('config.db_file', test_db_file):
            # Import after patching config
            import laue_portal.database.db_utils as db_utils
            import laue_portal.database.db_schema as db_schema
            from sqlalchemy.orm import Session
            import sqlalchemy
            
            # Create a new engine for the test database and create tables
            test_engine = sqlalchemy.create_engine(f'sqlite:///{test_db_file}')
            db_schema.Base.metadata.create_all(test_engine)
            
            # Create test metadata record
            test_metadata = db_schema.Metadata(
                scanNumber=1,
                date=datetime.datetime.now(),
                commit_id='TEST_COMMIT',
                calib_id=1,
                runtime='TEST_RUNTIME',
                computer_name='TEST_COMPUTER',
                dataset_id=1,
                notes='Test metadata for smoke test',
                time_epoch=1640995200,
                time='2022-01-01T00:00:00',
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
                sample_name='test_sample'
            )
            
            # Create test scan record (for the JOIN operation in _get_metadatas)
            test_scan = db_schema.Scan(
                scanNumber=1,
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
            
            yield test_engine, test_db_file, test_metadata, test_scan
            
    finally:
        # Clean up temporary database file
        if os.path.exists(test_db_file):
            os.unlink(test_db_file)


@pytest.fixture
def empty_metadata_database():
    """
    Pytest fixture that creates a temporary empty database (no test data).
    
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


class TestMetadataRetrievers:
    """Test class for metadata retrieval functions in the Laue Portal application."""
    
    def test_get_metadatas_function_smoke(self, test_metadata_database):
        """Test that _get_metadatas function can execute without errors."""
        test_engine, test_db_file, test_metadata, test_scan = test_metadata_database
        
        # Mock the config to use test database
        with patch('config.db_file', test_db_file):
            # Import after patching config
            import lau_dash
            from laue_portal.pages.scans import _get_metadatas
            import laue_portal.database.db_utils as db_utils
            from sqlalchemy.orm import Session
            
            # Patch the ENGINE in db_utils to use our test engine
            with patch.object(db_utils, 'ENGINE', test_engine):
                # Add test data to the database
                with Session(test_engine) as session:
                    session.add(test_metadata)
                    session.add(test_scan)
                    session.commit()
                
                # Test the _get_metadatas function
                cols, metadatas = _get_metadatas()
            
            # Verify that the function returns the expected structure
            assert isinstance(cols, list), "Columns should be returned as a list"
            assert isinstance(metadatas, list), "Metadatas should be returned as a list"
            
            # Check that columns are properly formatted
            for col in cols:
                assert isinstance(col, dict), "Each column should be a dictionary"
                assert 'headerName' in col, "Each column should have a headerName"
                assert 'field' in col, "Each column should have a field"
            
            # Check that we have at least one metadata record
            assert len(metadatas) >= 1, "Should have at least one metadata record"
            
            # Check that each metadata record has the expected fields
            for metadata in metadatas:
                assert isinstance(metadata, dict), "Each metadata should be a dictionary"
                # Check for some expected fields based on VISIBLE_COLS
                expected_fields = ['scanNumber', 'user_name', 'date', 'notes']
                for field in expected_fields:
                    assert field in metadata, f"Metadata record should contain field: {field}"
                
                # Check that scan_dim field is included (from the JOIN)
                assert 'scan_dim' in metadata, "Metadata record should contain scan_dim field from JOIN"

    def test_get_metadatas_callback_smoke(self, test_metadata_database):
        """Test that get_metadatas callback function can execute without errors."""
        test_engine, test_db_file, test_metadata, test_scan = test_metadata_database
        
        # Mock the config to use test database
        with patch('config.db_file', test_db_file):
            # Import after patching config
            import lau_dash
            from laue_portal.pages.scans import get_metadatas
            import laue_portal.database.db_utils as db_utils
            from sqlalchemy.orm import Session
            
            # Patch the ENGINE in db_utils to use our test engine
            with patch.object(db_utils, 'ENGINE', test_engine):
                # Add test data to the database
                with Session(test_engine) as session:
                    session.add(test_metadata)
                    session.add(test_scan)
                    session.commit()
                
                # Test the callback with correct path (root path '/')
                cols, metadatas = get_metadatas('/')
            
            # Verify that the callback returns the expected structure
            assert isinstance(cols, list), "Callback should return columns as a list"
            assert isinstance(metadatas, list), "Callback should return metadatas as a list"
            assert len(metadatas) >= 1, "Should have at least one metadata record"
            
            # Test the callback with incorrect path (should raise PreventUpdate)
            with pytest.raises(PreventUpdate):
                get_metadatas('/wrong_path')

    def test_get_metadatas_empty_database_smoke(self, empty_metadata_database):
        """Test that _get_metadatas function handles empty database gracefully."""
        test_engine, test_db_file = empty_metadata_database
        
        # Mock the config to use test database
        with patch('config.db_file', test_db_file):
            # Import after patching config
            import lau_dash
            from laue_portal.pages.scans import _get_metadatas
            import laue_portal.database.db_utils as db_utils
            
            # Patch the ENGINE in db_utils to use our test engine
            with patch.object(db_utils, 'ENGINE', test_engine):
                # Test the _get_metadatas function with empty database
                cols, metadatas = _get_metadatas()
            
            # Verify that the function handles empty database gracefully
            assert isinstance(cols, list), "Columns should be returned as a list even with empty database"
            assert isinstance(metadatas, list), "Metadatas should be returned as a list even with empty database"
            assert len(metadatas) == 0, "Empty database should return empty metadatas list"
            
            # Check that columns are still properly formatted
            assert len(cols) > 0, "Should still have column definitions even with empty database"
            for col in cols:
                assert isinstance(col, dict), "Each column should be a dictionary"
                assert 'headerName' in col, "Each column should have a headerName"
                assert 'field' in col, "Each column should have a field"
            
            # Verify specific expected columns are present
            column_fields = [col['field'] for col in cols]
            expected_columns = ['scanNumber', 'user_name', 'date', 'scan_dim', 'actions', 'notes']
            for expected_col in expected_columns:
                assert expected_col in column_fields, f"Column {expected_col} should be present in column definitions"
