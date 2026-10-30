#!/bin/bash
set -euo pipefail
usage() {
  echo "Usage: $0 start|stop|list" >&2
  echo 'Set LAUE_ENDPOINT_ENV and LAUE_ENDPOINT_NAME in the private deployment environment.' >&2
  echo 'Starting/stopping also requires LAUE_ENDPOINT_HOST (the configured short hostname).' >&2
}
if [[ $# != 1 ]]; then usage; exit 2; fi
case "$1" in
  -h|--help) usage; exit 0 ;;
  start|stop|list) ;;
  *) usage; exit 2 ;;
esac
: "${LAUE_ENDPOINT_ENV:?Set LAUE_ENDPOINT_ENV to the endpoint environment prefix}"
: "${LAUE_ENDPOINT_NAME:?Set LAUE_ENDPOINT_NAME to the configured endpoint name}"
export PATH="$LAUE_ENDPOINT_ENV/bin:${LAUE_PBS_BIN:-/opt/pbs/bin}:$PATH"
export TMPDIR="${LAUE_ENDPOINT_TMPDIR:-${TMPDIR:-/tmp}}"
umask 077
if [[ "$1" != list ]]; then
  : "${LAUE_ENDPOINT_HOST:?Set LAUE_ENDPOINT_HOST to the configured short hostname}"
  if [[ "$(hostname -s)" != "$LAUE_ENDPOINT_HOST" ]]; then
    echo 'Use the host configured by LAUE_ENDPOINT_HOST.' >&2
    exit 1
  fi
fi
case "$1" in
  start)
    globus-compute-endpoint start --detach "$LAUE_ENDPOINT_NAME"
    globus-compute-endpoint list
    ;;
  stop) globus-compute-endpoint stop "$LAUE_ENDPOINT_NAME" ;;
  list) globus-compute-endpoint list ;;
esac
