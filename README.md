# VeriNews

**AI-Powered News Verification for Social Media**

VeriNews is an intelligent browser extension that combats misinformation by providing instant, AI-driven verification of news posts shared on social media.

## Overview

VeriNews performs multi-layered analysis to determine the authenticity of social media posts:

1. **Image Authenticity** - Detects AI-generated images
2. **Content Similarity** - Finds relevant articles from trusted news sources
3. **Factual Claim Verification** - Verifies claims against trusted sources
4. **Credibility Scoring** - Provides an overall credibility judgment

## Quick Start

### Prerequisites

- Python 3.13+
- [UV package manager](https://github.com/astral-sh/uv)
- Docker & Docker Compose

### Setup

```bash
# Clone and setup
git clone <repository-url>
cd VeriNews
cp .env.example .env
# Edit .env with your configuration

# Start backend
cd backend
./scripts/verinews dev start

# Start crawler (optional)
./scripts/verinews crawler start
```

## Project Structure

```
VeriNews/
├── backend/           # FastAPI backend service
│   ├── app/          # Application code
│   ├── tests/        # Test suite
│   └── scripts/      # CLI tools
└── docker/           # Docker configuration
```

## Documentation

- [Backend README](backend/README.md) - Setup, development, and API documentation
- [Testing Guide](backend/tests/README.md) - Running and writing tests
- [System Design](docs/system-design.md) - Architecture overview
- [Project Description](docs/project-description.md) - Product vision

## Tech Stack

**Backend**: FastAPI, PostgreSQL + pgvector, SQLAlchemy, Celery + Redis
**AI/ML**: OpenAI embeddings, GPT-4
**Frontend** (Coming Soon): TypeScript, Manifest V3

## Development Status

- ✅ **Phase 1**: Infrastructure, database, migrations, Docker setup
- ✅ **Phase 2**: News crawler, RSS feeds, article processing, vector search, comprehensive test suite
- 🚧 **Phase 3**: Verification API, caching, authentication
- 📋 **Phase 4**: Browser extension
- 📋 **Phase 5**: Production deployment

## Contributing

1. Create a feature branch
2. Make your changes with tests
3. Submit a pull request

---

Built for fighting misinformation
