#!/bin/bash

# Quick check script for supervisor setup

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SUPERVISOR_DIR="$SCRIPT_DIR"

echo "=== Supervisor Quick Check ==="
echo ""

# Check if configured
if [ -f "$SUPERVISOR_DIR/supervisord.conf" ]; then
    echo "✓ Supervisor is configured"
else
    echo "✗ Supervisor not configured"
    echo "  Run: ./supervisor/setup_supervisor.sh <conda_env_name_or_path>"
    exit 1
fi

# Check if running
if [ -f "$SUPERVISOR_DIR/supervisor.sock" ]; then
    # Check if we can get a valid PID (suppress stderr to avoid pkg_resources warnings)
    if supervisorctl -c "$SUPERVISOR_DIR/supervisord.conf" pid 2>/dev/null | grep -q '^[0-9]'; then
        echo "✓ Supervisor is running"
        echo ""
        echo "Service Status:"
        supervisorctl -c "$SUPERVISOR_DIR/supervisord.conf" status
    else
        echo "✗ Supervisor socket exists but cannot connect"
    fi
else
    echo "✗ Supervisor is not running"
    echo "  Run: ./supervisor/start_supervisor.sh"
fi
