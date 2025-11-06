#!/bin/bash
# Stop Celery Beat scheduler gracefully

set -e

echo "Stopping Celery Beat scheduler..."

# Find and kill celery beat processes gracefully
pkill -TERM -f "celery.*beat" || echo "No beat process found"

echo "Celery Beat scheduler stopped"
