"""Render DM workflow definitions from private site configuration; never register them."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
from pathlib import Path

import yaml


def _replace(value, variables):
    if isinstance(value, dict):
        return {key: _replace(item, variables) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace(item, variables) for item in value]
    if isinstance(value, str):
        return re.sub(r"\{\{([A-Z_]+)\}\}", lambda match: variables[match[1]], value)
    return value


def render_workflows(settings, output_directory):
    """Write new private JSON files, preserving existing files on failure."""
    source = Path(__file__).resolve().parent
    output_directory = Path(output_directory).resolve()
    if output_directory.is_relative_to(source.parent):
        raise ValueError("Render site workflows outside the source checkout")
    dm = settings["dm"]
    for key in ("owner", "workflow", "launcher_code", "launcher_python", "launcher_config"):
        if not isinstance(dm.get(key), str) or not dm[key].strip():
            raise ValueError(f"dm.{key} must be a nonempty string")
    for key in ("launcher_code", "launcher_python", "launcher_config"):
        if not Path(dm[key]).is_absolute():
            raise ValueError(f"dm.{key} must be an absolute path")
    command = shlex.join(
        [
            "env",
            "LAUE_PORTAL_SOURCE=" + dm["launcher_code"],
            "LAUE_PORTAL_PYTHON=" + dm["launcher_python"],
            "LAUE_BDP_CONFIG=" + dm["launcher_config"],
            str(Path(dm["launcher_code"]) / "deploy/dm-stage.sh"),
        ]
    )
    variables = {
        "OWNER": dm["owner"],
        "USER_ACCOUNT": dm.get("user_account") or dm["owner"],
        "STAGE_COMMAND": command,
    }
    documents = {}
    for name, workflow in [("workflow-bdp", dm["workflow"]), ("workflow-bdp-cancel", dm.get("cancel_workflow"))]:
        if workflow:
            template = json.loads((source / f"{name}.json.template").read_text())
            documents[output_directory / f"{name}.json"] = _replace(template, {**variables, "WORKFLOW_NAME": workflow})
    for path in documents:
        if path.exists() or path.is_symlink():
            raise FileExistsError(path)
    output_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    created = []
    try:
        for path, document in documents.items():
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            created.append(path)
            with os.fdopen(descriptor, "w") as handle:
                json.dump(document, handle, indent=2)
                handle.write("\n")
    except Exception:
        for path in created:
            path.unlink()
        raise
    return list(documents)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    settings = yaml.safe_load(args.config.read_text())
    for destination in render_workflows(settings, args.output_dir):
        print(destination)
