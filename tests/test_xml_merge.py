"""
Unit tests for XML merge functionality in redis_utils.
"""

import os
import tempfile
import pytest
import xml.etree.ElementTree as ET

from laue_portal.processing.redis_utils import merge_xml_files


def create_test_xml(path: str, step_data: dict):
    """Helper to create a test XML file with step data."""
    root = ET.Element('AllSteps')
    step = ET.SubElement(root, 'step')
    
    for key, value in step_data.items():
        elem = ET.SubElement(step, key)
        elem.text = str(value)
    
    tree = ET.ElementTree(root)
    ET.indent(root, space="    ")
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" ?>\n')
        tree.write(f, encoding='unicode', xml_declaration=False)


class TestMergeXmlFiles:
    """Test suite for merge_xml_files function."""
    
    def test_merge_single_file(self, tmp_path):
        """Test merging a single XML file."""
        xml_dir = tmp_path / "xml"
        xml_dir.mkdir()
        
        # Create a single test XML
        create_test_xml(
            xml_dir / "test_1.xml",
            {"scanNum": "1", "Xsample": "100.0"}
        )
        
        output_path = tmp_path / "output.xml"
        result = merge_xml_files(str(xml_dir), str(output_path))
        
        assert result['success'] is True
        assert result['files_merged'] == 1
        assert os.path.exists(output_path)
        
        # Verify content
        tree = ET.parse(output_path)
        root = tree.getroot()
        assert root.tag == 'AllSteps'
        steps = root.findall('step')
        assert len(steps) == 1
        assert steps[0].find('scanNum').text == '1'
    
    def test_merge_multiple_files(self, tmp_path):
        """Test merging multiple XML files."""
        xml_dir = tmp_path / "xml"
        xml_dir.mkdir()
        
        # Create multiple test XMLs
        for i in range(5):
            create_test_xml(
                xml_dir / f"test_{i+1}.xml",
                {"scanNum": str(i+1), "Xsample": str(100.0 + i)}
            )
        
        output_path = tmp_path / "output.xml"
        result = merge_xml_files(str(xml_dir), str(output_path))
        
        assert result['success'] is True
        assert result['files_merged'] == 5
        
        # Verify all steps are present
        tree = ET.parse(output_path)
        root = tree.getroot()
        steps = root.findall('step')
        assert len(steps) == 5
        
        # Verify they're sorted (by filename)
        scan_nums = [step.find('scanNum').text for step in steps]
        assert scan_nums == ['1', '2', '3', '4', '5']
    
    def test_merge_empty_directory(self, tmp_path):
        """Test handling of empty directory."""
        xml_dir = tmp_path / "xml"
        xml_dir.mkdir()
        
        output_path = tmp_path / "output.xml"
        result = merge_xml_files(str(xml_dir), str(output_path))
        
        assert result['success'] is False
        assert result['files_merged'] == 0
        assert 'No XML files found' in result['error']
    
    def test_merge_nonexistent_directory(self, tmp_path):
        """Test handling of non-existent directory."""
        xml_dir = tmp_path / "nonexistent"
        output_path = tmp_path / "output.xml"
        
        result = merge_xml_files(str(xml_dir), str(output_path))
        
        assert result['success'] is False
        assert result['files_merged'] == 0
    
    def test_merge_creates_output_directory(self, tmp_path):
        """Test that output directory is created if it doesn't exist."""
        xml_dir = tmp_path / "xml"
        xml_dir.mkdir()
        
        create_test_xml(
            xml_dir / "test_1.xml",
            {"scanNum": "1"}
        )
        
        # Output to a nested directory that doesn't exist
        output_path = tmp_path / "nested" / "deep" / "output.xml"
        result = merge_xml_files(str(xml_dir), str(output_path))
        
        assert result['success'] is True
        assert os.path.exists(output_path)
    
    def test_merge_skips_malformed_xml(self, tmp_path):
        """Test that malformed XML files are skipped with warning."""
        xml_dir = tmp_path / "xml"
        xml_dir.mkdir()
        
        # Create a valid XML
        create_test_xml(
            xml_dir / "test_1.xml",
            {"scanNum": "1"}
        )
        
        # Create a malformed XML
        (xml_dir / "test_2.xml").write_text("This is not valid XML <broken>")
        
        # Create another valid XML
        create_test_xml(
            xml_dir / "test_3.xml",
            {"scanNum": "3"}
        )
        
        output_path = tmp_path / "output.xml"
        result = merge_xml_files(str(xml_dir), str(output_path))
        
        assert result['success'] is True
        assert result['files_merged'] == 3  # All files attempted
        
        # Verify only valid steps are present
        tree = ET.parse(output_path)
        root = tree.getroot()
        steps = root.findall('step')
        assert len(steps) == 2  # Only the 2 valid XMLs
    
    def test_merge_with_complex_structure(self, tmp_path):
        """Test merging XMLs with nested elements (like detector/indexing)."""
        xml_dir = tmp_path / "xml"
        xml_dir.mkdir()
        
        # Create XML with nested structure
        root = ET.Element('AllSteps')
        step = ET.SubElement(root, 'step')
        
        ET.SubElement(step, 'scanNum').text = '1'
        detector = ET.SubElement(step, 'detector')
        ET.SubElement(detector, 'inputImage').text = '/path/to/image.h5'
        ET.SubElement(detector, 'Nx').text = '2048'
        
        indexing = ET.SubElement(step, 'indexing')
        indexing.set('indexProgram', 'euler')
        pattern = ET.SubElement(indexing, 'pattern')
        pattern.set('num', '0')
        
        tree = ET.ElementTree(root)
        ET.indent(root, space="    ")
        
        xml_path = xml_dir / "test_1.xml"
        with open(xml_path, 'w', encoding='utf-8') as f:
            f.write('<?xml version="1.0" ?>\n')
            tree.write(f, encoding='unicode', xml_declaration=False)
        
        output_path = tmp_path / "output.xml"
        result = merge_xml_files(str(xml_dir), str(output_path))
        
        assert result['success'] is True
        
        # Verify nested structure is preserved
        tree = ET.parse(output_path)
        root = tree.getroot()
        step = root.find('step')
        
        assert step.find('detector/inputImage').text == '/path/to/image.h5'
        assert step.find('indexing').get('indexProgram') == 'euler'
        assert step.find('indexing/pattern').get('num') == '0'
    
    def test_output_path_returned_in_result(self, tmp_path):
        """Test that output_path is correctly returned in result."""
        xml_dir = tmp_path / "xml"
        xml_dir.mkdir()
        
        create_test_xml(xml_dir / "test_1.xml", {"scanNum": "1"})
        
        output_path = tmp_path / "custom_output.xml"
        result = merge_xml_files(str(xml_dir), str(output_path))
        
        assert result['output_path'] == str(output_path)
