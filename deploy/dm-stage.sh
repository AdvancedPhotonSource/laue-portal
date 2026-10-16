#!/bin/bash
set -euo pipefail
laue_root="${LAUE_PORTAL_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)}"
laue_source="${LAUE_PORTAL_SOURCE:-$laue_root/src}"
laue_python="${LAUE_PORTAL_PYTHON:-$laue_root/envs/laue-portal/bin/python}"
export PYTHONNOUSERSITE=1
export PYTHONPATH="$laue_source"
cd "$laue_source"
exec "$laue_python" -m laue_portal.processing.bdp.stage \
    --config "${LAUE_BDP_CONFIG:-$laue_root/config/bdp.yaml}" "$@"
