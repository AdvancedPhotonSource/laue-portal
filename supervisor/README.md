# Supervisor Configuration for Laue Portal

This directory contains the supervisor configuration for managing Laue Portal services.

## Overview

Supervisor manages three services:
- **dash**: The Dash web application (port 2052)
- **redis**: Redis server for job queuing (optional)
- **rq_worker**: Background job processor

## Setup

1. Configure supervisor for your environment:
   
   Using a conda environment name:
   ```bash
   ./supervisor/setup_supervisor.sh laue-portal-conda-env
   ```
   
   Using a custom conda environment path:
   ```bash
   ./supervisor/setup_supervisor.sh /net/s34data/export/s34data1/LauePortal/envs/lau_portal
   ```
   
   To use system Redis instead of supervisor-managed Redis:
   ```bash
   ./supervisor/setup_supervisor.sh <conda_env_name_or_path> --no-redis
   ```

2. Start all services:
   ```bash
   ./supervisor/start_supervisor.sh
   ```

## Management Commands

```bash
# Check status of all services
./supervisor/manage_supervisor.sh status

# Control all services
./supervisor/manage_supervisor.sh start all
./supervisor/manage_supervisor.sh stop all
./supervisor/manage_supervisor.sh restart all

# Control individual services
./supervisor/manage_supervisor.sh start dash
./supervisor/manage_supervisor.sh stop redis
./supervisor/manage_supervisor.sh restart rq_worker

# View logs
./supervisor/manage_supervisor.sh tail -f dash
./supervisor/manage_supervisor.sh tail -100 rq_worker

# Stop supervisor daemon
./supervisor/manage_supervisor.sh shutdown
```

## File Structure

```
supervisor/
├── README.md                    # This file
├── supervisord.conf.template    # Template for supervisor config
├── supervisord.conf            # Generated config (git-ignored)
├── .gitignore                  # Ignores generated files
├── setup_supervisor.sh         # Configure supervisor
├── start_supervisor.sh         # Start supervisor daemon
├── manage_supervisor.sh        # Control services
├── cleanup_supervisor.sh       # Clean up processes/files
├── logs/                       # Service logs (git-ignored)
│   ├── supervisord.log         # Supervisor daemon log
│   ├── dash.log               # Dash application log
│   ├── redis.log              # Redis server log
│   └── rq_worker_*.log        # Worker logs
└── redis_data/                # Redis persistence (git-ignored)
```

## Configuration Details

### Service Priorities
- Redis: 100 (starts first)
- Dash: 200 (starts after Redis)
- RQ Worker: 300 (starts last)

### Logging
- All services use combined stdout/stderr logging
- Log rotation: 10MB max size, 5 backups
- Logs are stored in `supervisor/logs/`

### Process Management
- All services auto-start and auto-restart on failure
- Services are grouped as "laue-portal" for easy management
- RQ worker starts with 1 process (configurable in template)

## Troubleshooting

### Service won't start
1. Check logs: `./supervisor/manage_supervisor.sh tail -100 <service_name>`
2. Verify conda environment exists and has required packages
3. For Redis issues, check if port 6379 is already in use

### Supervisor won't start
1. If supervisor is in an inconsistent state, use: `./supervisor/cleanup_supervisor.sh`
2. Verify supervisor is installed: `pip install supervisor`
3. Check the log file: `tail -50 supervisor/logs/supervisord.log`

### "Supervisor already running but socket missing" error
This happens when supervisor crashed or was killed improperly. To fix:
```bash
./supervisor/cleanup_supervisor.sh
./supervisor/start_supervisor.sh
```

### Permission issues
Ensure the current user has write permissions to:
- `supervisor/logs/`
- `supervisor/redis_data/` (if using supervisor-managed Redis)

## Scripts

All scripts are located in the `supervisor/` directory:

- **setup_supervisor.sh** - Configure supervisor for your environment
- **start_supervisor.sh** - Start the supervisor daemon
- **manage_supervisor.sh** - Control services (start/stop/restart/status)
- **cleanup_supervisor.sh** - Clean up stale processes and files
