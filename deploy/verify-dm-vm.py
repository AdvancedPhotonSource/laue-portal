#!/usr/bin/env python3
"""Verify the VM installation without logging in, registering flows, or submitting jobs."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
import os
import platform
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml
from packaging.requirements import Requirement


def requirements(path):
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-r "):
            yield from requirements(path.parent / line[3:].strip())
        else:
            yield Requirement(line)


def verify_flow(config, temporary):
    """Check the generated batched flow with disposable, unauthenticated state."""
    from laue_portal.processing.bdp.flow import client_class

    flow = client_class({**config, "state_directory": str(temporary)})(auto_registration=False)
    try:
        if config.get("auth_profile", "personal") == "personal":
            from globus_sdk.scopes import TransferScopes

            flow.login_manager.add_requirements([TransferScopes.all])
            scopes = flow.login_manager.scopes_by_resource_server(flow.login_manager.required_scopes)
            flow.login_manager.globus_app.add_scope_requirements(scopes)
            assert {"flows.globus.org", "funcx_service", "transfer.api.globus.org"} <= set(scopes)
        definition = flow.get_flow_definition()
        states = definition["States"]
        assert definition["StartAt"] == "InitInputTransfer"
        assert states["InitInputTransfer"]["Next"] == "InputTransfer"
        assert states["InputTransfer"]["Next"] == "AdvanceInputTransfer"
        assert states["AdvanceInputTransfer"]["Next"] == "MoreInputTransfers"
        assert states["MoreInputTransfers"]["Choices"][0]["Next"] == "InputTransfer"
        assert states["MoreInputTransfers"]["Default"] == "InputsReady"
        assert states["InputsReady"]["Next"] == "RunPbsJob"
        assert states["RunPbsJob"]["Next"] == "ResultTransfer"
        assert states["ResultTransfer"]["End"] is True
        return list(states)
    finally:
        # Gladier owns the token store, so GlobusApp.close() does not close it.
        app = flow.login_manager.globus_app
        if app is not None:
            app.close()
        token_storage = getattr(flow.login_manager, "token_storage", None)
        if token_storage is not None:
            token_storage.close()


def verify(root, network, config_file=None):
    root = root.expanduser().resolve()
    source = root / "src"
    prefix = root / "envs/laue-portal"
    setup = root / "state/setup"
    assert Path(sys.prefix).resolve() == prefix.resolve(), "Use the installed environment's Python"
    os.chdir(source)
    sys.path.insert(0, str(source))

    source_manifest = json.loads((setup / "source-manifest.json").read_text())
    for name, expected in source_manifest["files"].items():
        actual = hashlib.sha256((source / name).read_bytes()).hexdigest()
        assert actual == expected, f"Source checksum mismatch: {name}"

    checked = {}
    for requirement in requirements(source / "deploy" / "requirements-aps.txt"):
        distribution = metadata.distribution(requirement.name)
        assert requirement.specifier.contains(distribution.version), str(requirement)
        checked[requirement.name] = distribution.version
        if requirement.url and requirement.name != "lauelab":
            direct = json.loads(distribution.read_text("direct_url.json"))
            assert direct["vcs_info"]["commit_id"] == requirement.url.rsplit("@", 1)[1]

    import lauelab

    assert Path(lauelab.__file__).resolve().is_relative_to(prefix.resolve())
    direct = json.loads(metadata.distribution("lauelab").read_text("direct_url.json"))
    assert not direct.get("dir_info", {}).get("editable"), "Native lauelab must not depend on a dev checkout"
    names = sorted({d.metadata["Name"] for d in metadata.distributions()}, key=str.lower)
    assert not any(name.lower() in {"funcx", "funcx-endpoint", "globus-compute-endpoint"} for name in names)
    subprocess.run([sys.executable, "-m", "pip", "check"], check=True)

    config_file = Path(config_file or root / "config/bdp.yaml").expanduser().resolve()
    config = yaml.safe_load(config_file.read_text())
    assert Path(config["state_directory"]).is_dir(), "Configured state directory must exist"
    subprocess.run(
        [str(source / "deploy/dm-stage.sh"), "--help"],
        env={
            **os.environ,
            "LAUE_PORTAL_ROOT": str(root),
            "LAUE_PORTAL_SOURCE": str(source),
            "LAUE_PORTAL_PYTHON": str(prefix / "bin/python"),
            "LAUE_BDP_CONFIG": str(config_file),
        },
        check=True,
        capture_output=True,
        text=True,
    )
    temporary_root = root / "tmp"
    temporary_root.mkdir(exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix="verify-flow-", dir=temporary_root) as temporary:
        states = verify_flow(config, temporary)

    connectivity = {}
    if network:
        for name, url in {
            "auth": "https://auth.globus.org/",
            "flows": "https://flows.globus.org/",
            "compute": "https://compute.api.globus.org/",
            "transfer": "https://transfer.api.globus.org/",
        }.items():
            try:
                with urllib.request.urlopen(url, timeout=10) as response:
                    connectivity[name] = response.status
            except urllib.error.HTTPError as error:
                # An HTTP authorization/not-found response still verifies HTTPS connectivity.
                connectivity[name] = error.code

    manifest = {
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "host": platform.node(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "prefix": str(prefix),
        "source": source_manifest,
        "checked_requirements": checked,
        "packages": {name: metadata.version(name) for name in names},
        "lauelab_file": lauelab.__file__,
        "https_connectivity": connectivity,
        "flow_states": list(states),
        "globus_login_performed": False,
        "dm_workflow_registration_performed": False,
        "services_started": False,
        "experiment_database_modified": False,
        "pbs_jobs_submitted": False,
    }
    (setup / "install-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: manifest[key]
                for key in [
                    "host",
                    "python",
                    "prefix",
                    "flow_states",
                    "https_connectivity",
                    "experiment_database_modified",
                ]
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--config", type=Path, help="Private BDP configuration; defaults to ROOT/config/bdp.yaml")
    parser.add_argument(
        "--network", action="store_true", help="Check public Globus HTTPS responses without credentials"
    )
    arguments = parser.parse_args()
    verify(arguments.root, arguments.network, arguments.config)
