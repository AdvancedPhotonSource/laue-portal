"""XML output merge helpers for Laue processing jobs."""

import glob
import logging
import os
import xml.etree.ElementTree as ET
from typing import Any, Dict

logger = logging.getLogger(__name__)


def merge_xml_files(xml_dir: str, output_xml_path: str) -> Dict[str, Any]:
    """
    Merge multiple XML files from a directory into a single XML file.

    Each individual XML file has an <AllSteps> root with one or more <step> elements.
    The merged file will have a single <AllSteps> root containing all <step> elements
    from all input files.

    Args:
        xml_dir: Directory containing the individual XML files
        output_xml_path: Path for the merged output XML file

    Returns:
        Dict with merge status information:
        - success: bool
        - files_merged: int
        - output_path: str
        - error: str (if failed)
    """
    result = {"success": False, "files_merged": 0, "output_path": output_xml_path, "error": None}

    try:
        # Find all XML files in the directory
        xml_pattern = os.path.join(xml_dir, "*.xml")
        xml_files = sorted(glob.glob(xml_pattern))

        if not xml_files:
            result["error"] = f"No XML files found in {xml_dir}"
            logger.warning(result["error"])
            return result

        # Create the merged root element
        merged_root = ET.Element("AllSteps")

        # Process each XML file
        for xml_file in xml_files:
            try:
                tree = ET.parse(xml_file)
                root = tree.getroot()

                # Find all <step> elements and add them to the merged root.
                # Use a match that handles both namespaced and non-namespaced
                # step elements. ElementTree represents namespaced tags as
                # {namespace_uri}localname, so a plain findall('.//step') will
                # miss elements like <step xmlns="...">.
                found_steps = root.findall(".//step")
                if not found_steps:
                    # Try wildcard namespace match: .//{*}step matches
                    # <step> in any namespace (Python 3.8+)
                    found_steps = root.findall(".//{*}step")

                for step in found_steps:
                    # Deep copy the step element to avoid issues with element ownership
                    merged_root.append(step)

            except ET.ParseError as e:
                logger.warning(f"Failed to parse XML file {xml_file}: {e}")
                continue
            except Exception as e:
                logger.warning(f"Error processing XML file {xml_file}: {e}")
                continue

        # Check if we have any steps (handle both namespaced and non-namespaced)
        steps = list(merged_root)
        if not steps:
            result["error"] = f"No valid <step> elements found in XML files from {xml_dir}"
            logger.warning(result["error"])
            return result

        # Create the output directory if it doesn't exist
        output_dir = os.path.dirname(output_xml_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        # Format and write the merged XML file
        ET.indent(merged_root, space="    ")
        tree = ET.ElementTree(merged_root)

        with open(output_xml_path, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" ?>\n')
            tree.write(f, encoding="unicode", xml_declaration=False)

        result["success"] = True
        result["files_merged"] = len(xml_files)
        logger.info(f"Successfully merged {len(xml_files)} XML files into {output_xml_path}")

        return result

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Error merging XML files: {e}")
        return result
