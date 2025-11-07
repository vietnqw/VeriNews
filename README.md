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
├── .env                 # Environment variables (not in git)
├── .env.example         # Environment template
└── .pre-commit-config.yaml # Pre-commit hooks configuration
```

## 🚀 Quick Start

### Prerequisites

- Python 3.13+
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
   ./scripts/verinews dev start
   ```

4. **Start the crawler** (optional, for news collection):
   ```bash
   ./scripts/verinews crawler start
   ```


## 📚 Documentation

For detailed technical information, including setup, development, and API documentation, please see the [Backend README](backend/README.md).

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
- [x] Pre-commit setup for code quality
- [x] Documentation

### Phase 2: Core Services ✅
- [x] News crawler service (Celery + Redis task queue)
- [x] RSS feed management (sync, add, remove feeds)
- [x] Article processor with smart chunking
  - [x] Multi-stage content extraction (trafilatura + fallbacks)
  - [x] Intelligent paragraph-level chunking (500-2000 chars)
  - [x] Vietnamese text optimization
- [x] Embedding generator (OpenAI text-embedding-3-small)
- [x] Vector similarity search (pgvector)
- [x] Unified CLI tool for all operations
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
