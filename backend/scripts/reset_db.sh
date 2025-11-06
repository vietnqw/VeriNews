#!/bin/bash
# Reset database (⚠️ DELETES ALL DATA)

set -e

echo "======================================"
echo "⚠️  Database Reset"
echo "======================================"
echo ""
echo "This will DELETE ALL DATA in the database!"
echo ""
read -p "Are you sure? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

# Navigate to root directory
cd "$(dirname "$0")/../.."

# Stop and remove volumes
echo ""
echo "Stopping Docker and removing volumes..."
docker compose -f docker/docker-compose.yml down -v postgres adminer

# Start fresh
echo ""
echo "Starting fresh Docker services..."
docker compose -f docker/docker-compose.yml up -d postgres adminer

# Wait for PostgreSQL
echo ""
echo "Waiting for PostgreSQL to be ready..."
sleep 5

# Navigate to backend directory
cd backend

# Run migrations
echo ""
echo "Running migrations..."
uv run alembic upgrade head

echo ""
echo "✅ Database reset complete"

