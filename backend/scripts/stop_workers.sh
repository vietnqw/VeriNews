#!/bin/bash
# Stop Celery workers gracefully

set -e

echo "Stopping Celery workers..."

# Find and kill celery worker processes gracefully
pkill -TERM -f "celery.*worker" || echo "No worker processes found"

echo "Celery workers stopped"
