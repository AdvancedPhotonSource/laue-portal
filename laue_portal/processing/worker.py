#!/usr/bin/env python
"""
RQ Worker for processing Laue Portal jobs.

This script starts an RQ worker that processes jobs from the Redis queue.
It can be run directly or managed by supervisor.

Usage:
    python -m laue_portal.processing.worker
    
Or with custom settings:
    python -m laue_portal.processing.worker --burst  # Process jobs and exit
    python -m laue_portal.processing.worker --name custom-worker-1
"""

import sys
import logging
import argparse
from rq import Worker, Queue
from laue_portal.processing.redis_utils import redis_conn, job_queue

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main worker entry point."""
    parser = argparse.ArgumentParser(description='Start an RQ worker for Laue Portal jobs')
    parser.add_argument(
        '--burst', 
        action='store_true',
        help='Run in burst mode (process all jobs and exit)'
    )
    parser.add_argument(
        '--name',
        type=str,
        default=None,
        help='Custom name for this worker'
    )
    parser.add_argument(
        '--log-level',
        type=str,
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Set the logging level'
    )
    
    args = parser.parse_args()
    
    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Start the worker
    worker = Worker(
        [job_queue],
        connection=redis_conn,
        name=args.name,
        log_job_description=True,
        disable_default_exception_handler=False
    )
    
    logger.info(f"Starting worker: {worker.name}")
    logger.info(f"Listening on queue: {job_queue.name}")
    
    try:
        worker.work(burst=args.burst, with_scheduler=True)
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Worker error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
