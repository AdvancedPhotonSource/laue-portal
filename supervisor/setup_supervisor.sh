#!/bin/bash

# Simplified supervisor setup script for Laue Portal
# This script processes the supervisor template to create the actual config

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# Go up one level to get project root
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SUPERVISOR_DIR="$SCRIPT_DIR"

# Check arguments
if [ $# -eq 0 ]; then
    echo "Usage: .supervisor/setup_supervisor.sh <conda_env_name_or_path>"
    echo ""
    echo "Examples:"
    echo "  .supervisor/setup_supervisor.sh laue-portal-conda-env"
    echo ""
    echo "This script configures supervisor to manage:"
    echo "  - Dash web application"
    echo "  - Redis server (optional)"
    echo "  - RQ Worker for background jobs"
    echo ""
    echo "Options:"
    echo "  --no-redis    Skip Redis configuration (use system Redis instead)"
    exit 1
fi

CONDA_ENV_ARG=$1
USE_REDIS=true

# Parse optional arguments
if [ "$2" = "--no-redis" ]; then
    USE_REDIS=false
fi

# Determine if the argument is a path or environment name
if [[ "$CONDA_ENV_ARG" == /* ]]; then
    # Absolute path provided
    CONDA_ENV_PATH="$CONDA_ENV_ARG"
    CONDA_ENV_NAME=$(basename "$CONDA_ENV_PATH")
    echo "Using conda environment at: $CONDA_ENV_PATH"
elif [[ "$CONDA_ENV_ARG" == */* ]]; then
    # Relative path provided
    CONDA_ENV_PATH="$(cd "$(dirname "$CONDA_ENV_ARG")" && pwd)/$(basename "$CONDA_ENV_ARG")"
    CONDA_ENV_NAME=$(basename "$CONDA_ENV_PATH")
    echo "Using conda environment at: $CONDA_ENV_PATH"
else
    # Environment name provided, look in standard conda location
    if command -v conda &> /dev/null; then
        CONDA_BASE=$(conda info --base)
        echo "Found conda at: $CONDA_BASE"
        CONDA_ENV_PATH="$CONDA_BASE/envs/$CONDA_ENV_ARG"
        CONDA_ENV_NAME="$CONDA_ENV_ARG"
    else
        echo "Error: conda not found in PATH and no absolute path provided!"
        exit 1
    fi
fi

# Set binary paths
PYTHON_BIN="$CONDA_ENV_PATH/bin/python"
REDIS_BIN="$CONDA_ENV_PATH/bin/redis-server"

# Verify Python exists
if [ ! -f "$PYTHON_BIN" ]; then
    echo "Error: Python not found at $PYTHON_BIN"
    echo "Make sure the conda environment at '$CONDA_ENV_PATH' exists and has Python installed."
    exit 1
fi

# Create directories
mkdir -p "$SUPERVISOR_DIR/logs"
mkdir -p "$SUPERVISOR_DIR/redis_data"

echo "Setting up supervisor configuration..."

# Process the supervisor template
if [ -f "$SUPERVISOR_DIR/supervisord.conf.template" ]; then
    # Create config from template
    sed -e "s|{{PYTHON_BIN}}|$PYTHON_BIN|g" \
        -e "s|{{REDIS_BIN}}|$REDIS_BIN|g" \
        -e "s|{{PROJECT_DIR}}|$PROJECT_DIR|g" \
        "$SUPERVISOR_DIR/supervisord.conf.template" > "$SUPERVISOR_DIR/supervisord.conf"
    
    # If not using Redis, comment it out
    if [ "$USE_REDIS" = false ]; then
        echo "  - Disabling Redis service (use --no-redis flag)"
        # Comment out Redis program section
        sed -i.bak '/\[program:redis\]/,/^$/s/^/# /' "$SUPERVISOR_DIR/supervisord.conf"
        # Remove redis from group
        sed -i.bak 's/programs=dash,redis,rq_worker/programs=dash,rq_worker/' "$SUPERVISOR_DIR/supervisord.conf"
        # Clean up backup files
        rm -f "$SUPERVISOR_DIR/supervisord.conf.bak"
    fi
else
    echo "Error: Template file not found at $SUPERVISOR_DIR/supervisord.conf.template"
    exit 1
fi

# Process the Redis configuration template if using Redis
if [ "$USE_REDIS" = true ] && [ -f "$SUPERVISOR_DIR/redis.conf.template" ]; then
    echo "  - Configuring Redis..."
    sed -e "s|{{SUPERVISOR_DIR}}|$SUPERVISOR_DIR|g" \
        "$SUPERVISOR_DIR/redis.conf.template" > "$SUPERVISOR_DIR/redis.conf"
fi

echo ""
echo "Configuration complete!"
echo "  Environment: $CONDA_ENV_NAME (at $CONDA_ENV_PATH)"
echo "  Project root: $PROJECT_DIR"
echo "  Python: $PYTHON_BIN"
if [ "$USE_REDIS" = true ]; then
    echo "  Redis: $REDIS_BIN"
else
    echo "  Redis: Using system Redis"
fi
echo ""
echo "To start all services: ./supervisor/start_supervisor.sh"
echo "To manage services: ./supervisor/manage_supervisor.sh [command]"
echo ""
echo "Available commands:"
echo "  ./supervisor/manage_supervisor.sh status     - Show status of all services"
echo "  ./supervisor/manage_supervisor.sh start all  - Start all services"
echo "  ./supervisor/manage_supervisor.sh stop all   - Stop all services"
echo "  ./supervisor/manage_supervisor.sh restart all - Restart all services"
echo "  ./supervisor/manage_supervisor.sh tail -f dash - Follow logs for a service"
