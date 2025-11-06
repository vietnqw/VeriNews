# VeriNews Backend

AI-powered news verification system for social media.

## Table of Contents

- [Overview](#overview)
- [Project Structure](#project-structure)
- [Setup](#setup)
- [Development](#development)
- [Database Migrations](#database-migrations)
- [API Documentation](#api-documentation)

## Overview

VeriNews backend is built with FastAPI and provides a robust, scalable API for news verification using AI-powered analysis.

## Project Structure

```
backend/
├── alembic/              # Database migrations
│   ├── versions/         # Migration files
│   └── env.py           # Alembic configuration
├── app/
│   ├── api/             # API routes
│   │   ├── health.py    # Health check endpoints
│   │   └── main.py      # Main router
│   ├── config/          # Configuration modules
│   │   ├── database.py  # Database setup
│   │   └── settings.py  # Application settings
│   ├── core/            # Core utilities
│   │   └── logging.py   # Logging configuration
│   ├── models/          # SQLAlchemy models
│   │   └── base.py      # Base model class
│   ├── schemas/         # Pydantic schemas
│   ├── services/        # Business logic
│   └── main.py          # FastAPI application
├── config/              # YAML configuration
│   └── config.yaml      # Application settings
├── logs/                # Log files (production)
├── scripts/             # Utility scripts
├── pyproject.toml       # Project dependencies
└── alembic.ini         # Alembic configuration

```

## Setup

### Prerequisites

- Python 3.13+
- UV package manager
- Docker & Docker Compose

### Installation

1. **Clone the repository and navigate to the root**:
   ```bash
   git clone <repository-url>
   cd VeriNews
   ```

2. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Install dependencies using UV** (from the `backend` directory):
   ```bash
   cd backend
   uv sync
   ```

4. **Start Docker services** (from the project root):
   ```bash
   # This is handled by the start_dev.sh script, but can be run manually
   docker compose -f docker/docker-compose.yml up -d
   ```

5. **Run database migrations** (from the `backend` directory):
   ```bash
   uv run alembic upgrade head
   ```

6. **Start the development server** (from the `backend` directory):
   ```bash
   ./scripts/start_dev.sh
   ```

By default, the API will be available at: http://localhost:8000

## Development

### Running the Server

To start the entire development environment (Docker containers, migrations, and FastAPI server), simply run the `start_dev.sh` script from the `backend` directory.

```bash
# From backend/ directory
./scripts/start_dev.sh
```

The script handles all startup logic, and the server runs with auto-reload enabled.

### Development Scripts

All scripts are located in `backend/scripts/` and should be run from the `backend` directory.

- `start_dev.sh`: Starts Docker containers, runs migrations, and launches the FastAPI server.
- `stop_dev.sh`: Stops the Docker containers.
- `reset_db.sh`: **Deletes all data!** Resets the database by stopping containers, removing the data volume, and restarting everything.
- `check_health.sh`: Pings the health check endpoints to verify the server is running correctly.

### Environment Configuration

Configuration is split into two files:

1. **`.env`** (Project root): Infrastructure settings (database, API keys, secrets)
2. **`config/config.yaml`**: Application logic settings (scoring weights, thresholds)

#### `.env` Variables

```env
# General
PROJECT_NAME=VeriNews
ENVIRONMENT=local
API_PREFIX=/api/v1

# Server
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
BACKEND_CORS_ORIGINS=["*"]
SECRET_KEY=your_secret_key

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/app.log

# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=verinews_user
POSTGRES_PASSWORD=verinews_password
POSTGRES_DB=verinews_db

# AI/ML
OPENAI_API_KEY=your_openai_api_key
```

### Docker Services

The `start_dev.sh` and `stop_dev.sh` scripts manage the Docker services for you. The services are defined in `docker/docker-compose.yml`.

**Manual Docker Commands** (run from the project root):

**Start services**:
```bash
docker compose -f docker/docker-compose.yml up -d
```

**Stop services**:
```bash
docker compose -f docker/docker-compose.yml down
```

**Stop and remove volumes** (⚠️ deletes all data):
```bash
docker compose -f docker/docker-compose.yml down -v
```

**Check status**:
```bash
docker compose -f docker/docker-compose.yml ps
```

### Adminer Database UI

Access Adminer at: http://localhost:8080.The default Adminer database credentials below are defined in the `.env` file and can be changed as needed.

- **Server**: postgres
- **Username**: verinews_user
- **Password**: verinews_password
- **Database**: verinews_db


## Database Migrations

### Create a Migration

```bash
# Auto-generate migration from model changes
uv run alembic revision --autogenerate -m "description_of_changes"

# Create empty migration
uv run alembic revision -m "description_of_changes"
```

### Apply Migrations

```bash
# Upgrade to latest
uv run alembic upgrade head

# Upgrade one version
uv run alembic upgrade +1

# Downgrade one version
uv run alembic downgrade -1
```

### Check Migration Status

```bash
# Current version
uv run alembic current

# Migration history
uv run alembic history

# Check for pending migrations
uv run alembic check
```

## API Documentation

### Interactive Documentation

- **Swagger UI**: http://localhost:8000/api/v1/docs
- **ReDoc**: http://localhost:8000/api/v1/redoc

### Health Check Endpoints

**Full Health Check**:
```bash
curl http://localhost:8000/api/v1/health
```

Response:
```json
{
  "status": "healthy",
  "api": "running",
  "database": "connected",
  "pgvector": "available (v0.8.1)"
}
```

**Simple Health Check**:
```bash
curl http://localhost:8000/api/v1/health/simple
```

Response:
```json
{
  "status": "ok"
}
```

## Logging

Logs are configured using Loguru:

- **Development** (`ENVIRONMENT=local`): Console output with colors
- **Production** (`ENVIRONMENT=production`): Console + file rotation

Log files are stored in `logs/` directory with:
- Rotation: 500 MB
- Retention: 10 days
- Compression: zip

## Testing

```bash
# Run tests (when test suite is added)
uv run pytest

# Run with coverage
uv run pytest --cov=app
```

## Code Quality

The project uses `ruff` for linting and formatting, enforced by `pre-commit` hooks.

**Run pre-commit on all files**:
```bash
# From backend/ directory
uv run pre-commit run --all-files
```

**Run linter**:
```bash
uv run ruff check .
```

**Run formatter**:
```bash
uv run ruff format .
```

## Troubleshooting

### Database Connection Failed

```bash
# Check if PostgreSQL is running
docker compose -f docker/docker-compose.yml ps

# Check logs
docker logs verinews-postgres

# Restart database
docker compose -f docker/docker-compose.yml restart postgres
```

### Port Already in Use

```bash
# Find process using port 8000
lsof -i :8000

# Kill the process
kill -9 <PID>
```

### Migration Issues

```bash
# Check current migration status
uv run alembic current

# Check for inconsistencies
uv run alembic check

# If needed, stamp to a specific version (e.g., 'head')
uv run alembic stamp head
```
