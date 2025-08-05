#!/bin/bash

# Script to clean up supervisor processes and files

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SUPERVISOR_DIR="$SCRIPT_DIR"

echo "=== Supervisor Cleanup ==="
echo ""

# Check for running supervisor process
if [ -f "$SUPERVISOR_DIR/supervisord.pid" ]; then
    PID=$(cat "$SUPERVISOR_DIR/supervisord.pid")
    if ps -p $PID > /dev/null 2>&1; then
        echo "Found running supervisor process (PID: $PID)"
        read -p "Kill this process? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "Killing supervisor process..."
            kill $PID
            sleep 2
            # Force kill if still running
            if ps -p $PID > /dev/null 2>&1; then
                echo "Process didn't stop gracefully, force killing..."
                kill -9 $PID
            fi
        else
            echo "Skipping process termination"
        fi
    else
        echo "No running supervisor process found"
    fi
fi

# Clean up files
echo ""
echo "Cleaning up supervisor files..."

if [ -f "$SUPERVISOR_DIR/supervisord.pid" ]; then
    echo "  Removing PID file..."
    rm -f "$SUPERVISOR_DIR/supervisord.pid"
fi

if [ -f "$SUPERVISOR_DIR/supervisor.sock" ]; then
    echo "  Removing socket file..."
    rm -f "$SUPERVISOR_DIR/supervisor.sock"
fi

# Check for any supervisor processes that might be orphaned
echo ""
echo "Checking for orphaned supervisor processes..."
ORPHANED=$(ps aux | grep -E "supervisord.*$SUPERVISOR_DIR" | grep -v grep | awk '{print $2}')
if [ ! -z "$ORPHANED" ]; then
    echo "Found orphaned supervisor processes: $ORPHANED"
    read -p "Kill these processes? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        for pid in $ORPHANED; do
            echo "  Killing PID $pid..."
            kill $pid
        done
    fi
else
    echo "No orphaned processes found"
fi

echo ""
echo "Cleanup complete!"
echo ""
echo "You can now start supervisor with:"
echo "  ./supervisor/start_supervisor.sh"
