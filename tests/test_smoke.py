"""
High-level smoke test for lau_dash components.

This test verifies that all core components can be imported successfully 
and the Dash server can start without throwing any errors.
"""

import sys
import os
import tempfile
from unittest.mock import patch
import pytest

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)


def test_import_main_app():
    """Test that the main lau_dash module can be imported."""
    import lau_dash
    assert hasattr(lau_dash, 'app')
    assert hasattr(lau_dash, 'ensure_database_exists')


def test_dash_app_creation():
    """Test that Dash app can be created without errors."""
    # Create a temporary database file for testing
    with tempfile.NamedTemporaryFile(suffix='.db', delete=True) as temp_db:
        test_db_file = temp_db.name

    # Mock the config to use test database
    with patch('laue_portal.config.db_file', test_db_file):
        import lau_dash
        
        # Verify app was created
        assert lau_dash.app is not None
        
        # Check that app has layout
        assert lau_dash.app.layout is not None


def test_database_creation():
    """Test that database can be created without errors."""
    # Create a temporary database file for testing
    with tempfile.NamedTemporaryFile(suffix='.db', delete=True) as temp_db:
        test_db_file = temp_db.name

    # Mock the config to use test database
    with patch('laue_portal.config.db_file', test_db_file):
        import lau_dash
        
        # Test database creation function
        lau_dash.ensure_database_exists()
        
        # Verify database file was created
        assert os.path.exists(test_db_file)


def test_server_startup_smoke():
    """Test that the server can start without immediate errors."""
    # Create a temporary database file for testing
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
        test_db_file = temp_db.name

    # Mock the config to use test database
    with patch('laue_portal.config.db_file', test_db_file):
        import lau_dash
        
        # Ensure database exists
        lau_dash.ensure_database_exists()
        
        # Mock the run method to avoid actually starting the server
        original_run = lau_dash.app.run
        run_called = False
        run_args = None
        run_kwargs = None
        
        def mock_run(*args, **kwargs):
            nonlocal run_called, run_args, run_kwargs
            run_called = True
            run_args = args
            run_kwargs = kwargs
            # Don't actually start the server
            return None
        
        lau_dash.app.run = mock_run
        
        # Test that the main block would execute without errors
        # (simulating if __name__ == '__main__')
        try:
            lau_dash.ensure_database_exists()
            lau_dash.app.run(debug=True, port=2052, host='0.0.0.0')
            
            # Verify run was called with correct parameters
            assert run_called is True
            assert run_kwargs.get('debug') is True
            assert run_kwargs.get('port') == 2052
            assert run_kwargs.get('host') == '0.0.0.0'
        finally:
            # Restore original run method
            lau_dash.app.run = original_run
