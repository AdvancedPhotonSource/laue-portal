#!/bin/bash

# Script to manage supervisor and its services

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SUPERVISOR_DIR="$SCRIPT_DIR/etc/supervisor"

# Pass all arguments to supervisorctl
supervisorctl -c "$SUPERVISOR_DIR/supervisord.conf" "$@"
