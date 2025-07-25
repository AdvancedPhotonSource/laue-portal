"""
Smoke tests for data retrieval functions in the Laue Portal application.

This test module verifies that data retrieval functions like _get_recons
can execute without errors and return properly formatted data.
"""

import sys
import os
from unittest.mock import patch
import pytest
from dash.exceptions import PreventUpdate

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)


class TestDataRetrievers:
    """Test class for data retrieval functions in the Laue Portal application."""
    
    def test_get_recons_function_smoke(self, test_database):
        """Test that _get_recons function can execute without errors."""
        test_engine, test_db_file, test_metadata, test_job, test_recon, test_catalog = test_database
        
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
                    session.add(test_job)
                    session.add(test_catalog)
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
                # Check for some expected fields based on VISIBLE_COLS (note: dataset_id is commented out in VISIBLE_COLS)
                expected_fields = ['recon_id', 'submit_time', 'calib_id', 'scanNumber', 'sample_name', 'aperture', 'notes']
                for field in expected_fields:
                    assert field in recon, f"Recon record should contain field: {field}"

    def test_get_recons_callback_smoke(self, test_database):
        """Test that get_recons callback function can execute without errors."""
        test_engine, test_db_file, test_metadata, test_job, test_recon, test_catalog = test_database
        
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
                    session.add(test_job)
                    session.add(test_catalog)
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
