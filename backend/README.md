# VeriNews Backend

AI-powered news verification system with hybrid retrieval pipeline.

## Quick Start

### Prerequisites

- Python 3.13+
- [UV package manager](https://github.com/astral-sh/uv)
- Docker & Docker Compose

### Installation

```bash
# From VeriNews root
cp .env.example .env
# Edit .env with your API keys and configuration

# Install dependencies
cd backend
uv sync

# Start services and API
./scripts/verinews dev start

# Run migrations (if needed)
uv run alembic upgrade head
```

The API will be available at http://localhost:8000

## CLI Commands

VeriNews provides a unified CLI tool: `./scripts/verinews`

### Development

```bash
./scripts/verinews dev start        # Start Docker + API server
./scripts/verinews dev stop         # Stop all services
./scripts/verinews dev reset        # Reset database (⚠️ deletes data)
./scripts/verinews health           # Check API health
```

### Crawler

```bash
./scripts/verinews crawler start    # Start Celery workers + Beat scheduler
./scripts/verinews crawler stop     # Stop crawler
./scripts/verinews crawler status   # Check crawler status
```

### RSS Feeds

```bash
./scripts/verinews feeds sync                              # Sync from sources.yaml
./scripts/verinews feeds list                              # List all feeds
./scripts/verinews feeds add SOURCE URL --topic "Topic"    # Add feed
./scripts/verinews feeds remove URL                        # Remove feed
./scripts/verinews feeds set-active URL true/false         # Enable/disable
```

### Logs

```bash
./scripts/verinews logs worker      # Celery worker logs
./scripts/verinews logs beat        # Celery Beat scheduler logs
./scripts/verinews logs api         # API server logs
```

## Configuration

### Environment Variables

Configuration is split between:
- **`.env`** (root): Infrastructure settings (database, API keys, secrets)
- **`config/config.yaml`**: Application settings (weights, thresholds)

See `.env.example` for required environment variables.

### Database

Access Adminer UI at http://localhost:8080

Default credentials (from `.env`):
- Server: `postgres`
- Username: `verinews_user`
- Password: `verinews_password`
- Database: `verinews_db`

## Database Migrations

```bash
# Create migration
uv run alembic revision --autogenerate -m "description"

# Apply migrations
uv run alembic upgrade head

# Check status
uv run alembic current
```

## API Documentation

- **Swagger UI**: http://localhost:8000/api/v1/docs
- **ReDoc**: http://localhost:8000/api/v1/redoc

### Health Check

```bash
curl http://localhost:8000/api/v1/health
```

## Architecture

### Project Structure

```
backend/
├── app/
│   ├── api/              # API routes (health, verification)
│   ├── config/           # Database and settings
│   ├── core/             # Logging utilities
│   ├── models/           # SQLAlchemy models
│   ├── schemas/          # Pydantic schemas
│   ├── services/         # Business logic
│   │   ├── ai/           # LLM providers (OpenAI)
│   │   ├── cache/        # Redis caching
│   │   ├── content/      # Chunking, embeddings
│   │   ├── crawler/      # RSS, scraping
│   │   ├── repository/   # Data access layer
│   │   └── retrieval/    # Hybrid search pipeline
│   └── tasks/            # Celery tasks
├── alembic/              # Database migrations
├── config/               # YAML configuration
├── scripts/              # CLI tools
└── tests/                # Test suite
```

### Retrieval Pipeline

The hybrid retrieval system combines vector and keyword search:

1. **Query Extraction** - Clean query + factual claims (LLM)
2. **Embedding Generation** - Convert queries to vectors (OpenAI)
3. **Hybrid Search** - Vector (pgvector) + BM25 (PostgreSQL FTS)
4. **Fusion** - Reciprocal Rank Fusion (RRF)
5. **Reranking** - LLM-based relevance scoring
6. **Aggregation** - Chunk-to-article grouping with caching

### Crawler Pipeline

Background tasks for news collection (Celery + Redis):

1. **Scheduler** - Triggers crawls periodically (Celery Beat)
2. **RSS Parsing** - Fetches and parses RSS feeds
3. **Article Scraping** - Extracts full content (trafilatura)
4. **Chunking** - Intelligent paragraph-level splitting (500-2000 chars)
5. **Embedding** - Generates and stores vectors (OpenAI)

RSS feeds are configured in `config/sources.yaml`.

## Testing

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=app --cov-report=html

# Run specific tests
pytest tests/unit/
pytest tests/integration/
```

See [tests/README.md](tests/README.md) for detailed testing guide.

## Code Quality

Pre-commit hooks with `ruff` linting and formatting:

```bash
# Run on all files
uv run pre-commit run --all-files

# Manual checks
uv run ruff check .
uv run ruff format .
```

## Troubleshooting

### Database Connection Failed

```bash
# Check PostgreSQL status
docker compose -f docker/docker-compose.yml ps

# Restart database
docker compose -f docker/docker-compose.yml restart postgres
```

### Port Already in Use

```bash
# Find and kill process
lsof -i :8000
kill -9 <PID>
```

### Migration Issues

```bash
# Check migration status
uv run alembic current
uv run alembic check

# Force stamp to specific version
uv run alembic stamp head
```

## Additional Resources

- [AI Service Documentation](app/services/ai/README.md)
- [System Design](../docs/system-design.md)
- [Project Description](../docs/project-description.md)
