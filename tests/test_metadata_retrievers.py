"""
Smoke tests for metadata retrieval functions in the Laue Portal application.

This test module verifies that metadata retrieval functions like _get_metadatas
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


class TestMetadataRetrievers:
    """Test class for metadata retrieval functions in the Laue Portal application."""
    
    def test_get_metadatas_function_smoke(self, test_metadata_database):
        """Test that _get_metadatas function can execute without errors."""
        test_engine, test_db_file, test_metadata, test_scan, test_catalog = test_metadata_database
        
        # Mock the config to use test database
        with patch('laue_portal.config.db_file', test_db_file):
            # Import after patching config
            import lau_dash
            from laue_portal.pages.scans import _get_metadatas
            import laue_portal.database.db_utils as db_utils
            from sqlalchemy.orm import Session
            
            # Patch the central engine getter to return our test engine
            with patch('laue_portal.database.session_utils.get_engine', lambda: test_engine):
                # Add test data to the database
                with Session(test_engine) as session:
                    session.add(test_metadata)
                    session.add(test_catalog)
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
                expected_fields = ['scanNumber', 'sample_name', 'aperture', 'user_name', 'time', 'notes']
                for field in expected_fields:
                    assert field in metadata, f"Metadata record should contain field: {field}"
                
                # Check that scan_dim field is included (from the JOIN)
                assert 'scan_dim' in metadata, "Metadata record should contain scan_dim field from JOIN"

    def test_get_metadatas_callback_smoke(self, test_metadata_database):
        """Test that get_metadatas callback function can execute without errors."""
        test_engine, test_db_file, test_metadata, test_scan, test_catalog = test_metadata_database
        
        # Mock the config to use test database
        with patch('laue_portal.config.db_file', test_db_file):
            # Import after patching config
            import lau_dash
            from laue_portal.pages.scans import get_metadatas
            import laue_portal.database.db_utils as db_utils
            from sqlalchemy.orm import Session
            
            # Patch the central engine getter to return our test engine
            with patch('laue_portal.database.session_utils.get_engine', lambda: test_engine):
                # Add test data to the database
                with Session(test_engine) as session:
                    session.add(test_metadata)
                    session.add(test_catalog)
                    session.add(test_scan)
                    session.commit()
                
                # Test the callback with correct path ('/scans')
                cols, metadatas = get_metadatas('/scans')
            
            # Verify that the callback returns the expected structure
            assert isinstance(cols, list), "Callback should return columns as a list"
            assert isinstance(metadatas, list), "Callback should return metadatas as a list"
            assert len(metadatas) >= 1, "Should have at least one metadata record"
            
            # Test the callback with incorrect path (should raise PreventUpdate)
            with pytest.raises(PreventUpdate):
                get_metadatas('/')

    def test_get_metadatas_empty_database_smoke(self, empty_metadata_database):
        """Test that _get_metadatas function handles empty database gracefully."""
        test_engine, test_db_file = empty_metadata_database
        
        # Mock the config to use test database
        with patch('laue_portal.config.db_file', test_db_file):
            # Import after patching config
            import lau_dash
            from laue_portal.pages.scans import _get_metadatas
            import laue_portal.database.db_utils as db_utils
            
            # Patch the central engine getter to return our test engine
            with patch('laue_portal.database.session_utils.get_engine', lambda: test_engine):
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
            expected_columns = ['checkbox', 'scanNumber', 'sample_name', 'aperture', 'scan_dim', 'technique', 'user_name', 'time', 'notes']
            for expected_col in expected_columns:
                assert expected_col in column_fields, f"Column {expected_col} should be present in column definitions"
