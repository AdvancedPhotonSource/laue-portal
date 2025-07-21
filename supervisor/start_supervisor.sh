#!/bin/bash

# Script to start the supervisor daemon

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SUPERVISOR_DIR="$SCRIPT_DIR"

# Check if supervisor is configured
if [ ! -f "$SUPERVISOR_DIR/supervisord.conf" ]; then
    echo "Error: Supervisor not configured yet!"
    echo "Run: ./supervisor/setup_supervisor.sh <conda_env_name>"
    exit 1
fi

# Check if already running
if [ -f "$SUPERVISOR_DIR/supervisord.pid" ]; then
    PID=$(cat "$SUPERVISOR_DIR/supervisord.pid")
    if ps -p $PID > /dev/null 2>&1; then
        # Process is running, but check if socket exists
        if [ -f "$SUPERVISOR_DIR/supervisor.sock" ]; then
            echo "Supervisor already running (PID: $PID)"
            echo "Use ./supervisor/manage_supervisor.sh to control services"
            exit 1
        else
            echo "Warning: Supervisor process found (PID: $PID) but socket is missing!"
            echo "This usually means supervisor crashed or was killed improperly."
            echo ""
            echo "Options:"
            echo "1. Kill the existing process and restart:"
            echo "   kill $PID"
            echo "   ./supervisor/start_supervisor.sh"
            echo ""
            echo "2. Or clean up and restart:"
            echo "   rm -f $SUPERVISOR_DIR/supervisord.pid"
            echo "   rm -f $SUPERVISOR_DIR/supervisor.sock"
            echo "   ./supervisor/start_supervisor.sh"
            exit 1
        fi
    else
        echo "Removing stale PID file..."
        rm -f "$SUPERVISOR_DIR/supervisord.pid"
        rm -f "$SUPERVISOR_DIR/supervisor.sock"
    fi
fi

# Start supervisord
echo "Starting Supervisor..."
supervisord -c "$SUPERVISOR_DIR/supervisord.conf"

# Give it more time to start and check if it's actually running
echo "Waiting for supervisor to start..."
for i in {1..10}; do
    sleep 1
    if [ -f "$SUPERVISOR_DIR/supervisor.sock" ]; then
        # Socket exists, try to connect
        # Suppress stderr to avoid pkg_resources warnings
        if supervisorctl -c "$SUPERVISOR_DIR/supervisord.conf" pid 2>/dev/null | grep -q '^[0-9]'; then
            echo ""
            echo "Supervisor started successfully!"
            echo ""
            echo "Checking service status..."
            "$SCRIPT_DIR/manage_supervisor.sh" status
            echo ""
            echo "Use ./supervisor/manage_supervisor.sh to control individual services"
            exit 0
        fi
    fi
    echo -n "."
done

# If we get here, supervisor failed to start
echo ""
echo "ERROR: Supervisor failed to start properly!"
echo ""
echo "Check the log file for errors:"
echo "  tail -50 $SUPERVISOR_DIR/logs/supervisord.log"
echo ""
echo "Common issues:"
echo "  - Port already in use"
echo "  - Permission problems"
echo "  - Invalid configuration"
exit 1
