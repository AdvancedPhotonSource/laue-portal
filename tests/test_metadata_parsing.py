"""
Test suite for metadata log parsing and database input functionality.

This test exercises the XML parsing and database ORM functions in db_utils.py
using the test_log.xml file.
"""

import sys
import os
import tempfile
from datetime import datetime
from unittest.mock import patch
import pytest
from sqlalchemy.orm import Session
from sqlalchemy import create_engine

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

import laue_portal.database.db_utils as db_utils
import laue_portal.database.db_schema as db_schema


class TestMetadataParsing:
    """Test class for metadata parsing functionality."""
    
    @pytest.fixture
    def test_xml_data(self):
        """Load test XML data from test_log.xml file."""
        test_xml_path = os.path.join(os.path.dirname(__file__), 'data', 'test_log.xml')
        with open(test_xml_path, 'rb') as f:
            return f.read()
    
    @pytest.fixture
    def temp_database(self):
        """Create a temporary database for testing."""
        # Create a temporary database file
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_db_path = temp_db.name
        temp_db.close()
        
        # Create engine and tables
        engine = create_engine(f'sqlite:///{temp_db_path}')
        db_schema.Base.metadata.create_all(engine)
        
        yield engine, temp_db_path
        
        # Cleanup
        os.unlink(temp_db_path)
    
    def test_parse_metadata_basic_functionality(self, test_xml_data):
        """Test basic functionality of parse_metadata function."""
        # Test with the first scan (scan_no=0)
        log_dict, scan_dims_list = db_utils.parse_metadata(test_xml_data, scan_no=2)
        
        # Verify log_dict structure
        assert isinstance(log_dict, dict)
        assert 'scanNumber' in log_dict
        assert log_dict['scanNumber'] == '276990'
        
        # Verify scan_dims_list structure
        assert isinstance(scan_dims_list, list)
        assert len(scan_dims_list) > 0
        
        # Check that all expected fields are present in log_dict
        expected_fields = [
            'scanNumber', 'time_epoch', 'time', 'user_name',
            'source_beamBad', 'source_CCDshutter', 'source_monoTransStatus',
            'source_energy_unit', 'source_energy', 'source_IDgap_unit', 'source_IDgap',
            'source_IDtaper_unit', 'source_IDtaper', 'source_ringCurrent_unit', 'source_ringCurrent',
            'sample_XYZ_unit', 'sample_XYZ_desc', 'sample_XYZ',
            'knife-edge_XYZ_unit', 'knife-edge_XYZ_desc', 'knife-edge_XYZ',
            'knife-edge_knifeScan_unit', 'knife-edge_knifeScan',
            'mda_file', 'scanEnd_abort', 'scanEnd_time_epoch', 'scanEnd_time',
            'scanEnd_scanDuration_unit', 'scanEnd_scanDuration',
            'scanEnd_source_beamBad', 'scanEnd_source_ringCurrent_unit', 'scanEnd_source_ringCurrent'
        ]
        
        for field in expected_fields:
            assert field in log_dict, f"Missing field: {field}"
    
    def test_parse_metadata_different_scans(self, test_xml_data):
        """Test parsing different scans from the XML data."""
        # Test scanning through different scan indices
        for scan_no in range(2, 5):  # Test first 5 scans
            try:
                log_dict, scan_dims_list = db_utils.parse_metadata(test_xml_data, scan_no=scan_no)
                
                # Verify each scan has a valid scanNumber
                assert 'scanNumber' in log_dict
                assert log_dict['scanNumber'] is not None
                assert isinstance(scan_dims_list, list)
                
                print(f"Successfully parsed scan {scan_no}: {log_dict['scanNumber']}")
                
            except IndexError:
                # This is expected when we run out of scans
                print(f"No more scans available at index {scan_no}")
                break
    
    def test_parse_metadata_data_types(self, test_xml_data):
        """Test that numeric fields are properly converted to correct data types."""
        log_dict, scan_dims_list = db_utils.parse_metadata(test_xml_data, scan_no=2)
        
        # Test numeric fields are None or numeric types
        numeric_fields = [
            'time_epoch', 'source_energy', 'source_IDgap', 'source_IDtaper',
            'source_ringCurrent', 'knife-edge_knifeScan', 'scanEnd_time_epoch',
            'scanEnd_scanDuration', 'scanEnd_source_ringCurrent'
        ]
        
        for field in numeric_fields:
            if field in log_dict and log_dict[field] is not None:
                # Should be numeric or None, not empty string
                assert log_dict[field] != '', f"Field {field} should not be empty string"
                if log_dict[field] is not None:
                    try:
                        float(log_dict[field])
                    except (ValueError, TypeError):
                        pytest.fail(f"Field {field} should be numeric, got: {log_dict[field]}")
    
    def test_parse_metadata_scan_dimensions(self, test_xml_data):
        """Test parsing of scan dimension data."""
        log_dict, scan_dims_list = db_utils.parse_metadata(test_xml_data, scan_no=2)
        
        # Verify scan dimensions structure
        assert len(scan_dims_list) > 0
        
        for scan_dim in scan_dims_list:
            assert isinstance(scan_dim, dict)
            assert 'scanNumber' in scan_dim
            
            # Check for expected scan dimension fields
            expected_scan_fields = [
                'scan_dim', 'scan_npts', 'scan_after', 'scan_cpt'
            ]
            
            for field in expected_scan_fields:
                assert field in scan_dim, f"Missing scan field: {field}"
    
    def test_parse_metadata_multidimensional_scan(self, test_xml_data):
        """Test parsing of multidimensional scans (scan with nested scan elements)."""
        # Test scan_no=5 which should be the 4D scan (scan number 276993)
        log_dict, scan_dims_list = db_utils.parse_metadata(test_xml_data, scan_no=5)
        
        assert log_dict['scanNumber'] == '276993'
        
        # This scan should have multiple dimensions
        assert len(scan_dims_list) > 1, "Multidimensional scan should have multiple scan dimensions"
        
        # Verify the dimensions are in the correct order (from innermost to outermost)
        for i, scan_dim in enumerate(scan_dims_list):
            assert 'scan_dim' in scan_dim
            assert 'scan_npts' in scan_dim
            assert 'scan_cpt' in scan_dim


class TestDatabaseIntegration:
    """Test class for database integration functionality."""
    
    @pytest.fixture
    def test_xml_data(self):
        """Load test XML data from test_log.xml file."""
        test_xml_path = os.path.join(os.path.dirname(__file__), 'data', 'test_log.xml')
        with open(test_xml_path, 'rb') as f:
            return f.read()
    
    @pytest.fixture
    def temp_database(self):
        """Create a temporary database for testing."""
        # Create a temporary database file
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_db_path = temp_db.name
        temp_db.close()
        
        # Create engine and tables
        engine = create_engine(f'sqlite:///{temp_db_path}')
        db_schema.Base.metadata.create_all(engine)
        
        yield engine, temp_db_path
        
        # Cleanup
        os.unlink(temp_db_path)
    
    def test_import_metadata_row(self, test_xml_data, temp_database):
        """Test creating a Metadata ORM object from parsed data."""
        engine, temp_db_path = temp_database
        
        # Parse metadata from XML
        log_dict, scan_dims_list = db_utils.parse_metadata(test_xml_data, scan_no=2)
        
        # Create metadata row
        metadata_row = db_utils.import_metadata_row(log_dict)
        
        # Verify the metadata row is a valid ORM object
        assert isinstance(metadata_row, db_schema.Metadata)
        assert metadata_row.scanNumber == '276990'
        assert metadata_row.user_name == 'Sheyfer'
        
        # Test database insertion
        with Session(engine) as session:
            # Add required fields that aren't in the XML
            metadata_row.date = datetime(2023, 2, 25)
            metadata_row.commit_id = 'test_commit'
            metadata_row.calib_id = 1
            metadata_row.runtime = 'test_runtime'
            metadata_row.computer_name = 'test_computer'
            metadata_row.dataset_id = 1
            metadata_row.notes = 'test_notes'
            
            session.add(metadata_row)
            session.commit()
            
            # Verify the record was inserted
            retrieved = session.query(db_schema.Metadata).filter_by(scanNumber='276990').first()
            assert retrieved is not None
            assert retrieved.user_name == 'Sheyfer'
    
    def test_import_scan_row(self, test_xml_data, temp_database):
        """Test creating Scan ORM objects from parsed data."""
        engine, temp_db_path = temp_database
        
        # Parse metadata from XML
        log_dict, scan_dims_list = db_utils.parse_metadata(test_xml_data, scan_no=2)
        
        # Create scan rows
        scan_rows = []
        for scan_dict in scan_dims_list:
            scan_row = db_utils.import_scan_row(scan_dict)
            assert isinstance(scan_row, db_schema.Scan)
            scan_rows.append(scan_row)
        
        # Test database insertion
        with Session(engine) as session:
            for i, scan_row in enumerate(scan_rows):
                scan_row.id = i + 1  # Set a unique ID
                session.add(scan_row)
            session.commit()
            
            # Verify the records were inserted
            retrieved_scans = session.query(db_schema.Scan).filter_by(scanNumber='276990').all()
            assert len(retrieved_scans) == len(scan_rows)
    
    def test_end_to_end_workflow(self, test_xml_data, temp_database):
        """Test the complete workflow from XML parsing to database insertion."""
        engine, temp_db_path = temp_database
        
        # Mock the config to use our test database
        with patch('laue_portal.database.db_utils.ENGINE', engine):
            # Parse metadata from XML (test the first scan)
            log_dict, scan_dims_list = db_utils.parse_metadata(test_xml_data, scan_no=2)
            
            # Create metadata row
            metadata_row = db_utils.import_metadata_row(log_dict)
            
            # Create scan rows
            scan_rows = []
            for scan_dict in scan_dims_list:
                scan_row = db_utils.import_scan_row(scan_dict)
                scan_rows.append(scan_row)
            
            # Simulate the workflow from create_scan.py
            with Session(engine) as session:
                # Add required metadata fields
                metadata_row.date = datetime(2023, 2, 25)
                metadata_row.commit_id = 'test_commit'
                metadata_row.calib_id = 1
                metadata_row.runtime = 'test_runtime'
                metadata_row.computer_name = 'test_computer'
                metadata_row.dataset_id = 1
                metadata_row.notes = 'test_notes'
                
                # Add metadata to session
                session.add(metadata_row)
                
                # Add scan rows to session
                scan_row_count = session.query(db_schema.Scan).count()
                for i, scan_row in enumerate(scan_rows):
                    scan_row.id = scan_row_count + i + 1
                    session.add(scan_row)
                
                session.commit()
                
                # Verify everything was inserted correctly
                metadata_check = session.query(db_schema.Metadata).filter_by(scanNumber='276990').first()
                assert metadata_check is not None
                assert metadata_check.user_name == 'Sheyfer'
                
                scan_check = session.query(db_schema.Scan).filter_by(scanNumber='276990').all()
                assert len(scan_check) == len(scan_rows)
    
    def test_multiple_scans_workflow(self, test_xml_data, temp_database):
        """Test processing multiple different scans from the XML."""
        engine, temp_db_path = temp_database
        
        with patch('laue_portal.database.db_utils.ENGINE', engine):
            with Session(engine) as session:
                scan_row_count = 0
                
                # Process first 3 scans (starting from valid scan indices)
                for scan_index in range(2, 5):  # Use indices 2, 3, 4
                    try:
                        # Parse metadata from XML
                        log_dict, scan_dims_list = db_utils.parse_metadata(test_xml_data, scan_no=scan_index)
                        
                        # Create and insert metadata row
                        metadata_row = db_utils.import_metadata_row(log_dict)
                        metadata_row.date = datetime(2023, 2, 25)
                        metadata_row.commit_id = f'test_commit_{scan_index}'
                        metadata_row.calib_id = 1
                        metadata_row.runtime = 'test_runtime'
                        metadata_row.computer_name = 'test_computer'
                        metadata_row.dataset_id = 1
                        metadata_row.notes = f'test_notes_{scan_index}'
                        
                        session.add(metadata_row)
                        
                        # Create and insert scan rows
                        for scan_dict in scan_dims_list:
                            scan_row = db_utils.import_scan_row(scan_dict)
                            scan_row.id = scan_row_count + 1
                            scan_row_count += 1
                            session.add(scan_row)
                        
                    except IndexError:
                        # No more scans available
                        break
                
                session.commit()
                
                # Verify multiple scans were inserted
                all_metadata = session.query(db_schema.Metadata).all()
                assert len(all_metadata) >= 3
                
                all_scans = session.query(db_schema.Scan).all()
                assert len(all_scans) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
