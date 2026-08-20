#!/usr/bin/env python3
"""Command-line entry point for the workflow database migration."""

import sys
from pathlib import Path


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root))
    from scripts.workflow_migration import main as migrate_main

    return migrate_main()


if __name__ == "__main__":
    main()
