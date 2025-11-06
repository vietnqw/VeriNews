#!/bin/bash
# Start complete crawler environment (Redis, workers, and scheduler)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "===================================="
echo "VeriNews Crawler Startup"
echo "===================================="
echo ""

# Check if Redis is running
echo "1. Checking Redis..."
cd "$PROJECT_ROOT"
if docker compose -f docker/docker-compose.yml ps redis | grep -q "Up"; then
    echo "   ✓ Redis is running"
else
    echo "   Starting Redis..."
    docker compose -f docker/docker-compose.yml up -d redis
    sleep 2
    echo "   ✓ Redis started"
fi
echo ""

# Check if PostgreSQL is running
echo "2. Checking PostgreSQL..."
if docker compose -f docker/docker-compose.yml ps postgres | grep -q "Up"; then
    echo "   ✓ PostgreSQL is running"
else
    echo "   Starting PostgreSQL..."
    docker compose -f docker/docker-compose.yml up -d postgres
    sleep 5
    echo "   ✓ PostgreSQL started"
fi
echo ""

echo "3. Starting Celery workers in background..."
echo "   Logs: backend/logs/celery-worker.log"
cd "$SCRIPT_DIR/.."
mkdir -p logs
nohup uv run celery -A app.celery_app worker --loglevel=info > logs/celery-worker.log 2>&1 &
WORKER_PID=$!
echo "   ✓ Workers started (PID: $WORKER_PID)"
echo ""

echo "4. Starting Celery Beat scheduler in background..."
echo "   Logs: backend/logs/celery-beat.log"
nohup uv run celery -A app.celery_app beat --loglevel=info > logs/celery-beat.log 2>&1 &
BEAT_PID=$!
echo "   ✓ Scheduler started (PID: $BEAT_PID)"
echo ""

echo "===================================="
echo "Crawler Environment Ready!"
echo "===================================="
echo ""
echo "To view logs:"
echo "  Worker:    tail -f backend/logs/celery-worker.log"
echo "  Scheduler: tail -f backend/logs/celery-beat.log"
echo ""
echo "To stop:"
echo "  $ ./scripts/stop_workers.sh"
echo "  $ ./scripts/stop_beat.sh"
echo ""
