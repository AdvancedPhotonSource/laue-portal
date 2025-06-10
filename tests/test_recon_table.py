"""
Smoke tests for data retrieval functions in the Laue Portal application.

This test module verifies that data retrieval functions like _get_recons
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
def test_database():
    """
    Pytest fixture that creates a temporary database with test data.
    
    Returns:
        tuple: (test_engine, test_db_file, test_metadata, test_recon)
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
            
            # Create test metadata record (required for foreign key)
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
            
            # Create test reconstruction record
            test_recon = db_schema.Recon(
                scanNumber=1,
                date=datetime.datetime.now(),
                commit_id='TEST_COMMIT',
                calib_id=1,
                runtime='TEST_RUNTIME',
                computer_name='TEST_COMPUTER',
                dataset_id=1,
                notes='Test reconstruction for smoke test',
                
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
            
            yield test_engine, test_db_file, test_metadata, test_recon
            
    finally:
        # Clean up temporary database file
        if os.path.exists(test_db_file):
            os.unlink(test_db_file)


@pytest.fixture
def empty_test_database():
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


class TestDataRetrievers:
    """Test class for data retrieval functions in the Laue Portal application."""
    
    def test_get_recons_function_smoke(self, test_database):
        """Test that _get_recons function can execute without errors."""
        test_engine, test_db_file, test_metadata, test_recon = test_database
        
        # Mock the config to use test database
        with patch('config.db_file', test_db_file):
            # Import after patching config
            import lau_dash
            from laue_portal.pages.reconstructions import _get_recons
            import laue_portal.database.db_utils as db_utils
            from sqlalchemy.orm import Session
            
            # Patch the ENGINE in db_utils to use our test engine
            with patch.object(db_utils, 'ENGINE', test_engine):
                # Add test data to the database
                with Session(test_engine) as session:
                    session.add(test_metadata)
                    session.add(test_recon)
                    session.commit()
                
                # Test the _get_recons function
                cols, recons = _get_recons()
            
            # Verify that the function returns the expected structure
            assert isinstance(cols, list), "Columns should be returned as a list"
            assert isinstance(recons, list), "Recons should be returned as a list"
            
            # Check that columns are properly formatted
            for col in cols:
                assert isinstance(col, dict), "Each column should be a dictionary"
                assert 'headerName' in col, "Each column should have a headerName"
                assert 'field' in col, "Each column should have a field"
            
            # Check that we have at least one recon record
            assert len(recons) >= 1, "Should have at least one reconstruction record"
            
            # Check that each recon record has the expected fields
            for recon in recons:
                assert isinstance(recon, dict), "Each recon should be a dictionary"
                # Check for some expected fields based on VISIBLE_COLS
                expected_fields = ['recon_id', 'date', 'calib_id', 'dataset_id', 'notes']
                for field in expected_fields:
                    assert field in recon, f"Recon record should contain field: {field}"

    def test_get_recons_callback_smoke(self, test_database):
        """Test that get_recons callback function can execute without errors."""
        test_engine, test_db_file, test_metadata, test_recon = test_database
        
        # Mock the config to use test database
        with patch('config.db_file', test_db_file):
            # Import after patching config
            import lau_dash
            from laue_portal.pages.reconstructions import get_recons
            import laue_portal.database.db_utils as db_utils
            from sqlalchemy.orm import Session
            
            # Patch the ENGINE in db_utils to use our test engine
            with patch.object(db_utils, 'ENGINE', test_engine):
                # Add test data to the database
                with Session(test_engine) as session:
                    session.add(test_metadata)
                    session.add(test_recon)
                    session.commit()
                
                # Test the callback with correct path
                cols, recons = get_recons('/reconstructions')
            
            # Verify that the callback returns the expected structure
            assert isinstance(cols, list), "Callback should return columns as a list"
            assert isinstance(recons, list), "Callback should return recons as a list"
            assert len(recons) >= 1, "Should have at least one reconstruction record"
            
            # Test the callback with incorrect path (should raise PreventUpdate)
            with pytest.raises(PreventUpdate):
                get_recons('/wrong_path')


    def test_get_recons_empty_database_smoke(self, empty_test_database):
        """Test that _get_recons function handles empty database gracefully."""
        test_engine, test_db_file = empty_test_database
        
        # Mock the config to use test database
        with patch('config.db_file', test_db_file):
            # Import after patching config
            import lau_dash
            from laue_portal.pages.reconstructions import _get_recons
            import laue_portal.database.db_utils as db_utils
            
            # Patch the ENGINE in db_utils to use our test engine
            with patch.object(db_utils, 'ENGINE', test_engine):
                # Test the _get_recons function with empty database
                cols, recons = _get_recons()
            
            # Verify that the function handles empty database gracefully
            assert isinstance(cols, list), "Columns should be returned as a list even with empty database"
            assert isinstance(recons, list), "Recons should be returned as a list even with empty database"
            assert len(recons) == 0, "Empty database should return empty recons list"
            
            # Check that columns are still properly formatted
            assert len(cols) > 0, "Should still have column definitions even with empty database"
            for col in cols:
                assert isinstance(col, dict), "Each column should be a dictionary"
                assert 'headerName' in col, "Each column should have a headerName"
                assert 'field' in col, "Each column should have a field"
