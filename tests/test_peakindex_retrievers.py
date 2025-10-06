"""
Smoke tests for peak index retrieval functions in the Laue Portal application.

This test module verifies that peak index retrieval functions like _get_peakindexs
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


class TestPeakIndexRetrievers:
    """Test class for peak index retrieval functions in the Laue Portal application."""
    
    def test_get_peakindexs_function_smoke(self, test_peakindex_database):
        """Test that _get_peakindexs function can execute without errors."""
        test_engine, test_db_file, test_metadata, test_job, test_recon, test_peakindex = test_peakindex_database
        
        # Mock the config to use test database
        with patch('laue_portal.config.db_file', test_db_file):
            # Import after patching config
            import lau_dash
            from laue_portal.pages.peakindexings import _get_peakindexings
            import laue_portal.database.db_utils as db_utils
            from sqlalchemy.orm import Session
            
            # Patch the central engine getter to return our test engine
            with patch('laue_portal.database.session_utils.get_engine', lambda: test_engine):
                # Add test data to the database
                with Session(test_engine) as session:
                    session.add(test_metadata)
                    session.add(test_job)
                    session.add(test_recon)
                    session.commit()
                    
                    # Update peakindex with the correct recon_id
                    test_peakindex.recon_id = test_recon.recon_id
                    session.add(test_peakindex)
                    session.commit()
                
                # Test the _get_peakindexings function
                cols, peakindexs = _get_peakindexings()
            
            # Verify that the function returns the expected structure
            assert isinstance(cols, list), "Columns should be returned as a list"
            assert isinstance(peakindexs, list), "PeakIndexs should be returned as a list"
            
            # Check that columns are properly formatted
            for col in cols:
                assert isinstance(col, dict), "Each column should be a dictionary"
                assert 'headerName' in col, "Each column should have a headerName"
                assert 'field' in col, "Each column should have a field"
            
            # Check that we have at least one peakindex record
            assert len(peakindexs) >= 1, "Should have at least one peak index record"
            
            # Check that each peakindex record has the expected fields
            for peakindex in peakindexs:
                assert isinstance(peakindex, dict), "Each peakindex should be a dictionary"
                # Check for some expected fields based on VISIBLE_COLS (note: dataset_id is commented out in VISIBLE_COLS)
                expected_fields = ['peakindex_id', 'submit_time', 'scanNumber', 'recon_id', 'wirerecon_id', 'notes']
                for field in expected_fields:
                    assert field in peakindex, f"PeakIndex record should contain field: {field}"

    def test_get_peakindexs_callback_smoke(self, test_peakindex_database):
        """Test that get_peakindexs callback function can execute without errors."""
        test_engine, test_db_file, test_metadata, test_job, test_recon, test_peakindex = test_peakindex_database
        
        # Mock the config to use test database
        with patch('laue_portal.config.db_file', test_db_file):
            # Import after patching config
            import lau_dash
            from laue_portal.pages.peakindexings import get_peakindexings
            import laue_portal.database.db_utils as db_utils
            from sqlalchemy.orm import Session
            
            # Patch the central engine getter to return our test engine
            with patch('laue_portal.database.session_utils.get_engine', lambda: test_engine):
                # Add test data to the database
                with Session(test_engine) as session:
                    session.add(test_metadata)
                    session.add(test_job)
                    session.add(test_recon)
                    session.commit()
                    
                    # Update peakindex with the correct recon_id
                    test_peakindex.recon_id = test_recon.recon_id
                    session.add(test_peakindex)
                    session.commit()
                
                # Test the callback with correct path
                cols, peakindexs = get_peakindexings('/peakindexings')
            
            # Verify that the callback returns the expected structure
            assert isinstance(cols, list), "Callback should return columns as a list"
            assert isinstance(peakindexs, list), "Callback should return peakindexs as a list"
            assert len(peakindexs) >= 1, "Should have at least one peak index record"
            
            # Test the callback with incorrect path (should raise PreventUpdate)
            with pytest.raises(PreventUpdate):
                get_peakindexings('/wrong_path')

    def test_get_peakindexs_empty_database_smoke(self, empty_peakindex_database):
        """Test that _get_peakindexs function handles empty database gracefully."""
        test_engine, test_db_file = empty_peakindex_database
        
        # Mock the config to use test database
        with patch('laue_portal.config.db_file', test_db_file):
            # Import after patching config
            import lau_dash
            from laue_portal.pages.peakindexings import _get_peakindexings
            import laue_portal.database.db_utils as db_utils
            
            # Patch the central engine getter to return our test engine
            with patch('laue_portal.database.session_utils.get_engine', lambda: test_engine):
                # Test the _get_peakindexings function with empty database
                cols, peakindexs = _get_peakindexings()
            
            # Verify that the function handles empty database gracefully
            assert isinstance(cols, list), "Columns should be returned as a list even with empty database"
            assert isinstance(peakindexs, list), "PeakIndexs should be returned as a list even with empty database"
            assert len(peakindexs) == 0, "Empty database should return empty peakindexs list"
            
            # Check that columns are still properly formatted
            assert len(cols) > 0, "Should still have column definitions even with empty database"
            for col in cols:
                assert isinstance(col, dict), "Each column should be a dictionary"
                assert 'headerName' in col, "Each column should have a headerName"
                assert 'field' in col, "Each column should have a field"
            
            # Verify specific expected columns are present
            column_fields = [col['field'] for col in cols]
            expected_columns = ['peakindex_id', 'submit_time', 'scanNumber', 'recon_id', 'wirerecon_id', 'notes']
            for expected_col in expected_columns:
                assert expected_col in column_fields, f"Column {expected_col} should be present in column definitions"
