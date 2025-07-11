#!/bin/bash

# This script sets up ALL supervisor-managed services (Dash, Redis, etc.)
# It processes template files in etc/supervisor/conf.d/ to create actual configs

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SUPERVISOR_DIR="$SCRIPT_DIR/etc/supervisor"

# Check arguments
if [ $# -eq 0 ]; then
    echo "Usage: ./setup_supervisor.sh <conda_env_name>"
    echo "Example: ./setup_supervisor.sh laue-portal-conda-env"
    echo ""
    echo "This script configures all supervisor-managed services:"
    echo "  - Dash web application"
    echo "  - Redis (when added later)"
    exit 1
fi

CONDA_ENV=$1

# Find conda base directory
if command -v conda &> /dev/null; then
    CONDA_BASE=$(conda info --base)
    echo "Found conda at: $CONDA_BASE"
else
    echo "Error: conda not found in PATH!"
    exit 1
fi

# Create directories
mkdir -p "$SUPERVISOR_DIR/logs"
mkdir -p "$SUPERVISOR_DIR/conf.d"

echo "Setting up supervisor services..."

# Process Dash configuration
if [ -f "$SUPERVISOR_DIR/conf.d/dash.conf.template" ]; then
    echo "  - Configuring Dash..."
    sed -e "s|{{CONDA_ENV}}|$CONDA_ENV|g" \
        -e "s|{{CONDA_BASE}}|$CONDA_BASE|g" \
        -e "s|{{SCRIPT_DIR}}|$SCRIPT_DIR|g" \
        -e "s|{{SUPERVISOR_DIR}}|$SUPERVISOR_DIR|g" \
        "$SUPERVISOR_DIR/conf.d/dash.conf.template" > "$SUPERVISOR_DIR/conf.d/dash.conf"
fi

# Process Redis configuration (when template exists)
if [ -f "$SUPERVISOR_DIR/conf.d/redis.conf.template" ]; then
    echo "  - Configuring Redis..."
    sed -e "s|{{SCRIPT_DIR}}|$SCRIPT_DIR|g" \
        -e "s|{{SUPERVISOR_DIR}}|$SUPERVISOR_DIR|g" \
        "$SUPERVISOR_DIR/conf.d/redis.conf.template" > "$SUPERVISOR_DIR/conf.d/redis.conf"
fi

# Future: Add more services here as needed

echo ""
echo "Configuration complete!"
echo "  Environment: $CONDA_ENV"
echo "  Project root: $SCRIPT_DIR"
echo ""
echo "To start all services: ./start_supervisor.sh"
echo "To manage services: ./manage_supervisor.sh [command]"
