# VeriNews Backend

AI-powered news verification system for social media.

## Table of Contents

- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Setup](#setup)
- [Development](#development)
- [Database Migrations](#database-migrations)
- [API Documentation](#api-documentation)

## Overview

VeriNews backend is built with FastAPI and provides a robust, scalable API for news verification using AI-powered analysis.

## Tech Stack

- **Framework**: FastAPI 0.118+
- **Database**: PostgreSQL 18 with pgvector extension
- **ORM**: SQLAlchemy 2.0 (async)
- **Migrations**: Alembic
- **Logging**: Loguru
- **Package Manager**: UV
- **Containerization**: Docker & Docker Compose

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

- Python 3.11+
- UV package manager
- Docker & Docker Compose
- PostgreSQL (via Docker)

### Installation

1. **Navigate to backend directory**:
   ```bash
   cd backend
   ```

2. **Install dependencies using UV**:
   ```bash
   uv sync
   ```

3. **Set up environment variables**:
   ```bash
   # Copy example env file from project root
   cp ../.env.example ../.env
   # Edit .env with your configuration
   nano ../.env
   ```

4. **Start Docker services** (PostgreSQL + Adminer):
   ```bash
   cd ..
   docker compose -f docker/docker-compose.yml up -d
   ```

5. **Run database migrations**:
   ```bash
   cd backend
   uv run alembic upgrade head
   ```

6. **Start the development server**:
   ```bash
   uv run python -m app.main
   ```

The API will be available at: http://localhost:8000

## Development

### Running the Server

```bash
# From backend/ directory
uv run python -m app.main
```

The server runs with auto-reload enabled for development.

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

Access the database through Adminer at: http://localhost:8080

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

```bash
# Format code (when configured)
uv run ruff format .

# Lint code
uv run ruff check .
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

# If needed, stamp to specific version
uv run alembic stamp head
```

## Next Steps

1. Add more API endpoints (verification, articles, etc.)
2. Implement business logic services
3. Add comprehensive test suite
4. Set up CI/CD pipeline
5. Add API authentication and authorization

## License

See LICENSE file in project root.
