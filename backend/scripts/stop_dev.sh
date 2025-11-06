#!/bin/bash
# Stop development services

set -e

echo "======================================"
echo "Stopping VeriNews Development Server"
echo "======================================"

# Navigate to root directory
cd "$(dirname "$0")/../.."

# Stop FastAPI if running
echo ""
echo "Stopping FastAPI server..."
pkill -f "python -m app.main" || true

# Stop Docker services
echo ""
echo "Stopping Docker services..."
docker compose -f docker/docker-compose.yml stop postgres adminer

echo ""
echo "✅ All services stopped"

