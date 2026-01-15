"""
Configuration module for Laue Portal.
Reads configuration from config.yaml file in the project root.
If config.yaml doesn't exist, it will be created from config.yaml.template.
"""

import os
import shutil
import yaml
from pathlib import Path

# Get the project root directory (parent of laue_portal)
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_FILE = PROJECT_ROOT / "config.yaml"
CONFIG_TEMPLATE = PROJECT_ROOT / "config.yaml.template"


def _ensure_config_exists():
    """
    Ensure config.yaml exists. If not, copy from config.yaml.template.
    """
    if not CONFIG_FILE.exists():
        if CONFIG_TEMPLATE.exists():
            shutil.copy(CONFIG_TEMPLATE, CONFIG_FILE)
            print(f"NOTE: Created {CONFIG_FILE} from {CONFIG_TEMPLATE}")
            print("      Please review and customize the configuration as needed.")
        else:
            raise FileNotFoundError(
                f"Configuration template not found: {CONFIG_TEMPLATE}\n"
                "Please ensure config.yaml.template exists in the project root."
            )


def _load_config():
    """
    Load configuration from config.yaml file.
    """
    _ensure_config_exists()
    
    with open(CONFIG_FILE, 'r') as f:
        config = yaml.safe_load(f)
    
    return config


# Load the configuration
_config = _load_config()

# Export configuration variables
db_file = _config.get('db_file', 'Laue_Records.db')
DEFAULT_VARIABLES = _config.get('DEFAULT_VARIABLES', {})
REDIS_CONFIG = _config.get('REDIS_CONFIG', {})
DASH_CONFIG = _config.get('DASH_CONFIG', {})
MOTOR_GROUPS = _config.get('MOTOR_GROUPS', {})
VALID_HDF_EXTENSIONS = _config.get('VALID_HDF_EXTENSIONS', [])
PEAKINDEX_DEFAULTS = _config.get('PEAKINDEX_DEFAULTS', {})
