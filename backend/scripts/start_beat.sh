#!/bin/bash
# Start Celery Beat scheduler for VeriNews crawler

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

echo "Starting Celery Beat scheduler..."

# Start Celery Beat in the foreground
# The schedule will be persisted to celerybeat-schedule file
uv run celery -A app.celery_app beat \
    --loglevel=info

echo "Celery Beat scheduler started"
