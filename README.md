# Laue Portal

A Dash interface for managing Laue diffraction scans, wire reconstruction,
indexing, and visualization at APS beamline 34-ID-E.

![Laue Portal](images/temp_splash.png)

## Setup

Use Python 3.12. Building the pinned lauelab dependency requires a C compiler
with OpenMP, CMake >= 3.24, GSL 2.8, HDF5 1.14, zlib, Ninja, and patchelf.
The [CI configuration](.github/workflows/python-tests.yml) shows the conda-forge
build environment. Redis is required for local processing.

```bash
git clone https://github.com/Linked-Liszt/laue-portal.git
cd laue-portal
python -m pip install -r requirements.txt
cp config.yaml.template config.yaml
```

Edit `config.yaml`: set `db_file`, the experiment root and output paths,
`REDIS_CONFIG`, and `DASH_CONFIG`. Use `LAUE_PORTAL_CONFIG` to select an external
configuration file. Keep `DASH_CONFIG.debug: false` for deployed servers.

```bash
python lau_dash.py
```

Local processing also needs an RQ worker. [Supervisor](supervisor/README.md)
manages the web server, Redis, and worker. Optional DM/Globus execution and its
separate deployment requirements are described in [deploy/README.md](deploy/README.md).

## Code layout

- `laue_portal/pages/` and `components/`: Dash pages and forms.
- `laue_portal/workflows/`: requests, manifests, run records, and lifecycle.
- `laue_portal/processing/`: local workers, compute adapters, and remote runners.
- `laue_portal/processing/bdp/`: DM, Globus, PBS, and returned-result publication.
- `deploy/`: remote runtime requirements, deployment templates, and endpoint tools.
- `supervisor/`: service configuration and management scripts.

## Tests

```bash
python -m pytest tests/
# Include optional workflow tests, as CI does:
python -m pip install -r deploy/requirements-workflows.txt
python -m pytest tests/ workflow_tests/
ruff check .
ruff format --check .
```

The workflow tests use fixtures and mocks without contacting live DM/Globus
services or submitting PBS jobs. Runtime configuration, credentials, databases,
and generated state stay outside Git.
