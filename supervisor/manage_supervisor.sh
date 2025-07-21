#!/bin/bash

# Script to manage supervisor and its services

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SUPERVISOR_DIR="$SCRIPT_DIR"

# Try to connect to supervisor directly
# This is more reliable than checking for socket file existence
# Suppress stderr to avoid pkg_resources warnings, but check if we get a valid PID
if ! supervisorctl -c "$SUPERVISOR_DIR/supervisord.conf" pid 2>/dev/null | grep -q '^[0-9]'; then
    echo "Error: Cannot connect to supervisor!"
    echo ""
    
    # Check if socket exists but can't connect
    if [ -e "$SUPERVISOR_DIR/supervisor.sock" ]; then
        echo "Socket file exists but cannot connect. Possible issues:"
        echo "  - Permission problem (check socket permissions)"
        echo "  - Supervisor crashed but left socket file"
        echo ""
    fi
    
    echo "Please start supervisor first with:"
    echo "  ./supervisor/start_supervisor.sh"
    echo ""
    echo "If supervisor was running and crashed, clean up with:"
    echo "  ./supervisor/cleanup_supervisor.sh"
    exit 1
fi

# Pass all arguments to supervisorctl
supervisorctl -c "$SUPERVISOR_DIR/supervisord.conf" "$@"
