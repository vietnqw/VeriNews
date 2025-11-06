#!/bin/bash
# Start Celery workers for VeriNews crawler

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

echo "Starting Celery workers..."

# Get worker count from config (default to 4)
WORKER_COUNT=4

# Start Celery worker in the foreground
# For background operation, add & and use --pidfile/--logfile
uv run celery -A app.celery_app worker \
    --loglevel=info \
    --concurrency=$WORKER_COUNT

echo "Celery workers started with concurrency=$WORKER_COUNT"
