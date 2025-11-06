# VeriNews

**AI-Powered News Verification for Social Media**

VeriNews is an intelligent browser extension that combats misinformation by providing users with instant, AI-driven verification of news posts shared on social media.

## 🎯 Overview

VeriNews performs sophisticated, multi-layered analysis to determine the authenticity of social media posts:

1. **Image Authenticity** - Detects AI-generated images
2. **Content Similarity** - Finds relevant articles from trusted news sources
3. **Factual Claim Alignment** - Verifies individual claims against trusted sources
4. **Contextual Analysis** - Provides an overall credibility judgment

## 🏗️ Project Structure

```
VeriNews/
├── backend/              # FastAPI backend service
│   ├── app/             # Application code
│   ├── alembic/         # Database migrations
│   ├── config/          # Configuration files
│   └── scripts/         # Development scripts
├── docker/              # Docker configuration
│   └── docker-compose.yml
├── docs/                # Project documentation
│   ├── system-design.md
│   └── project-description.md
├── .env                 # Environment variables (not in git)
└── .env.example         # Environment template
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- UV package manager ([installation](https://github.com/astral-sh/uv))
- Docker & Docker Compose
- Git

### Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd VeriNews
   ```

2. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Start the backend**:
   ```bash
   cd backend
   ./scripts/start_dev.sh
   ```

The API will be available at:
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/api/v1/docs
- **Adminer**: http://localhost:8080

## 📚 Documentation

- [Backend README](backend/README.md) - Detailed backend setup and API documentation
- [System Design](docs/system-design.md) - Architecture and component overview
- [Project Description](docs/project-description.md) - Product vision and features

## 🛠️ Tech Stack

### Backend
- **Framework**: FastAPI
- **Database**: PostgreSQL 18 with pgvector
- **ORM**: SQLAlchemy 2.0 (async)
- **Migrations**: Alembic
- **Logging**: Loguru
- **Package Manager**: UV

### Frontend (Coming Soon)
- **Framework**: Vanilla JS/TypeScript (Manifest V3)
- **Build Tool**: Webpack/Vite

### AI/ML
- **Embeddings**: OpenAI text-embedding-3-small
- **LLM**: GPT-4 / Claude API
- **Image Detection**: Third-party API

## 🧪 Development

### Backend Development

```bash
cd backend

# Install dependencies
uv sync

# Start development server
./scripts/start_dev.sh

# Check health
./scripts/check_health.sh

# Stop services
./scripts/stop_dev.sh

# Reset database (⚠️ deletes all data)
./scripts/reset_db.sh
```

### Database Migrations

```bash
cd backend

# Create new migration
uv run alembic revision --autogenerate -m "description"

# Apply migrations
uv run alembic upgrade head

# Check current version
uv run alembic current
```

## 🐳 Docker Services

**PostgreSQL** with pgvector extension:
- Port: 5432
- Database: verinews_db
- User: verinews_user

**Adminer** (Database UI):
- URL: http://localhost:8080
- Server: postgres

## 📖 API Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/api/v1/docs
- **ReDoc**: http://localhost:8000/api/v1/redoc

### Health Check

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

## 🗺️ Roadmap

### Phase 1: Foundation ✅
- [x] Project structure setup
- [x] Configuration system (.env + YAML)
- [x] Logging with Loguru
- [x] Database setup (PostgreSQL + pgvector)
- [x] Alembic migrations
- [x] FastAPI application bootstrap
- [x] Health check endpoints
- [x] Docker setup
- [x] Documentation

### Phase 2: Core Services (In Progress)
- [ ] News crawler service
- [ ] Article processor
- [ ] Embedding generator
- [ ] Vector similarity search
- [ ] Claim verification service
- [ ] Image analysis integration

### Phase 3: API Development
- [ ] Verification endpoints
- [ ] Article management endpoints
- [ ] Source management
- [ ] Caching with Redis
- [ ] Rate limiting
- [ ] Authentication & authorization

### Phase 4: Browser Extension
- [ ] Extension manifest setup
- [ ] Content scripts
- [ ] Popup UI
- [ ] Background service worker
- [ ] API integration

### Phase 5: Deployment
- [ ] CI/CD pipeline
- [ ] Production deployment
- [ ] Monitoring & logging
- [ ] Performance optimization

## 🤝 Contributing

1. Create a feature branch
2. Make your changes
3. Write/update tests
4. Submit a pull request

## 📝 License

See [LICENSE](LICENSE) file for details.

## 📧 Contact

For questions or feedback, please open an issue in the repository.

---

Built with ❤️ for fighting misinformation
