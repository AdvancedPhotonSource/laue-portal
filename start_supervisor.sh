#!/bin/bash

# Script to start the supervisor daemon

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SUPERVISOR_DIR="$SCRIPT_DIR/etc/supervisor"

# Check if Dash is configured
if [ ! -f "$SUPERVISOR_DIR/conf.d/dash.conf" ]; then
    echo "Error: Dash service not configured yet!"
    echo "Run: ./setup_supervisor.sh <conda_env_name>"
    exit 1
fi

# Future: Check if Redis is configured
# if [ ! -f "$SUPERVISOR_DIR/conf.d/redis.conf" ]; then
#     echo "Error: Redis service not configured yet!"
#     echo "Run: ./setup_supervisor.sh <conda_env_name>"
#     exit 1
# fi

# Check if already running
if [ -f "$SUPERVISOR_DIR/supervisord.pid" ]; then
    PID=$(cat "$SUPERVISOR_DIR/supervisord.pid")
    if ps -p $PID > /dev/null 2>&1; then
        echo "Supervisor already running (PID: $PID)"
        echo "Use ./manage_supervisor.sh to control services"
        exit 1
    fi
fi

# Start supervisord
echo "Starting Supervisor..."
supervisord -c "$SUPERVISOR_DIR/supervisord.conf"

# Give it a moment to start
sleep 2

# Check status
"$SCRIPT_DIR/manage_supervisor.sh" status
