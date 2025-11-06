#!/bin/bash
# Development startup script

set -e

echo "======================================"
echo "Starting VeriNews Development Server"
echo "======================================"

# Navigate to root directory
cd "$(dirname "$0")/../.."

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "Error: .env file not found in project root!"
    echo "Please copy ../.env.example to ../.env and configure it."
    exit 1
fi

# Start Docker services
echo ""
echo "Starting Docker services..."
docker compose -f docker/docker-compose.yml up -d postgres adminer

# Wait for PostgreSQL to be ready
echo ""
echo "Waiting for PostgreSQL to be ready..."
sleep 3

# Navigate to backend directory
cd backend

# Run migrations
echo ""
echo "Running database migrations..."
uv run alembic upgrade head

# Start FastAPI server
echo ""
echo "Starting FastAPI server..."
echo "API: http://localhost:8000"
echo "Docs: http://localhost:8000/api/v1/docs"
echo "Adminer: http://localhost:8080"
echo ""
uv run python -m app.main
