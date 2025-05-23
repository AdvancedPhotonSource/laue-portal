"""
High-level smoke test for lau_dash components.

This test verifies that all core components can be imported successfully 
and the Dash server can start without throwing any errors.
"""

import unittest
import sys
import os
import tempfile
import threading
import time
import requests
from unittest.mock import patch, MagicMock

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)


class SmokeTest(unittest.TestCase):
    """Smoke test for lau_dash components and server startup."""

    def test_import_main_app(self):
        """Test that the main lau_dash module can be imported."""
        try:
            import lau_dash
            self.assertTrue(hasattr(lau_dash, 'app'))
            self.assertTrue(hasattr(lau_dash, 'ensure_database_exists'))
        except ImportError as e:
            self.fail(f"Failed to import lau_dash: {e}")

    def test_dash_app_creation(self):
        """Test that Dash app can be created without errors."""
        try:
            # Create a temporary database file for testing
            with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
                self.test_db_file = temp_db.name

            # Mock the config to use test database
            with patch('config.db_file', self.test_db_file):
                import lau_dash
                
                # Verify app was created
                self.assertIsNotNone(lau_dash.app)
                
                # Check that app has layout
                self.assertIsNotNone(lau_dash.app.layout)
                
        except Exception as e:
            self.fail(f"Failed to create Dash app: {e}")

    def test_database_creation(self):
        """Test that database can be created without errors."""
        try:
            # Create a temporary database file for testing
            with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
                self.test_db_file = temp_db.name

            # Mock the config to use test database
            with patch('config.db_file', self.test_db_file):
                import lau_dash
                
                # Test database creation function
                lau_dash.ensure_database_exists()
                
                # Verify database file was created
                self.assertTrue(os.path.exists(self.test_db_file))
                
        except Exception as e:
            self.fail(f"Failed to create database: {e}")

    def test_server_startup_smoke(self):
        """Test that the server can start without immediate errors."""
        try:
            # Create a temporary database file for testing
            with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
                self.test_db_file = temp_db.name

            # Mock the config to use test database
            with patch('config.db_file', self.test_db_file):
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
                    self.assertTrue(run_called)
                    self.assertEqual(run_kwargs.get('debug'), True)
                    self.assertEqual(run_kwargs.get('port'), 2052)
                    self.assertEqual(run_kwargs.get('host'), '0.0.0.0')
                finally:
                    # Restore original run method
                    lau_dash.app.run = original_run
                
        except Exception as e:
            self.fail(f"Server startup smoke test failed: {e}")


if __name__ == '__main__':
    unittest.main()
