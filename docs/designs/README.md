# VeriNews Backend Design Documentation

This folder contains detailed design documentation for the VeriNews backend system. Each document covers a specific component or pipeline of the system.

## Document Index

### Core API and Pipelines

1. **[01-backend-api-layer.md](01-backend-api-layer.md)**
   - FastAPI endpoints and request/response handling
   - Health checks and verification endpoint
   - Request validation and error handling
   - Performance characteristics

2. **[02-backend-retrieval-pipeline.md](02-backend-retrieval-pipeline.md)**
   - Hybrid search architecture (Vector + BM25)
   - Query extraction and embedding generation
   - Reciprocal Rank Fusion (RRF)
   - Chunk and article reranking
   - Multi-signal confidence scoring

3. **[03-backend-verification-pipeline.md](03-backend-verification-pipeline.md)** ⭐ NEW
   - Stance classification (SUPPORTS/REFUTES/NOT_ENOUGH_INFO)
   - Verdict aggregation across claims
   - Vietnamese explanation generation
   - Multi-signal verification confidence

### AI/ML and Supporting Services

4. **[04-backend-ai-ml-services.md](04-backend-ai-ml-services.md)** 🔄 UPDATED
   - Embedding service (OpenAI text-embedding-3-small)
   - Query extraction with LLM
   - Chunk and article reranking with LLM
   - Confidence scoring algorithms
   - Vietnamese text processing
   - AI provider abstraction
   - **Note:** Verification AI services moved to document 03

### Data Layer

5. **[05-backend-database.md](05-backend-database.md)**
   - PostgreSQL schema design
   - pgvector integration for embeddings
   - Article and ArticleChunk models
   - Full-text search with tsvector
   - Database migrations with Alembic

6. **[06-backend-cache-layer.md](06-backend-cache-layer.md)**
   - Redis caching strategy
   - Cache key design and TTL
   - Celery task queue
   - Performance optimization

### Data Ingestion

7. **[07-data-pipeline.md](07-data-pipeline.md)**
   - Background crawler architecture
   - RSS feed processing
   - Content scraping (Trafilatura + fallbacks)
   - Article chunking and embedding
   - 24-hour data retention policy

## Document Reorganization (November 2025)

**What Changed:**
- **NEW**: Created dedicated `03-backend-verification-pipeline.md` for verification logic
- **UPDATED**: Refactored `04-backend-ai-ml-services.md` to focus only on retrieval AI services
- **RENUMBERED**: Documents 04-07 shifted to accommodate new verification doc

**Why:**
- Separates retrieval and verification pipelines for clarity
- Verification pipeline is conceptually distinct from retrieval
- Easier to navigate and maintain documentation

**Old Structure → New Structure:**
```
01-backend-api-layer.md              → 01-backend-api-layer.md (unchanged)
02-backend-retrieval-system.md       → 02-backend-retrieval-pipeline.md (unchanged)
03-backend-ai-ml-services.md         → 03-backend-verification-pipeline.md (NEW, verification content)
                                        04-backend-ai-ml-services.md (retrieval AI only)
04-backend-database.md               → 05-backend-database.md
05-backend-cache-layer.md            → 06-backend-cache-layer.md
06-data-pipeline.md                  → 07-data-pipeline.md
```

## How to Navigate

### By Use Case

**Understanding the verification flow:**
1. Start with `01-backend-api-layer.md` (entry point)
2. Read `02-backend-retrieval-pipeline.md` (find relevant articles)
3. Read `03-backend-verification-pipeline.md` (classify and aggregate verdicts)

**Understanding AI/ML services:**
- Retrieval AI: `04-backend-ai-ml-services.md`
- Verification AI: `03-backend-verification-pipeline.md`

**Understanding data storage:**
- Database: `05-backend-database.md`
- Caching: `06-backend-cache-layer.md`
- Data ingestion: `07-data-pipeline.md`

### By Pipeline

**Retrieval Pipeline (Query → Articles):**
- API: `01-backend-api-layer.md`
- Pipeline: `02-backend-retrieval-pipeline.md`
- AI Services: `04-backend-ai-ml-services.md`
- Data: `05-backend-database.md`, `06-backend-cache-layer.md`

**Verification Pipeline (Articles → Verdict):**
- API: `01-backend-api-layer.md`
- Pipeline: `03-backend-verification-pipeline.md`
- Data: `05-backend-database.md`

**Data Ingestion Pipeline (RSS → Database):**
- Pipeline: `07-data-pipeline.md`
- Data: `05-backend-database.md`
- AI Services: `04-backend-ai-ml-services.md` (embeddings)

## Related Documentation

- **[../system-design.md](../system-design.md)**: High-level system architecture
- **[../project-description.md](../project-description.md)**: Project overview and goals
- **[../report.md](../report.md)**: Comprehensive project report
- **[../../CLAUDE.md](../../CLAUDE.md)**: Developer guide for Claude Code

## Contributing

When adding new design documents:
1. Follow the numbering convention (01, 02, 03, etc.)
2. Update this README with the new document
3. Add cross-references to related documents at the end of your doc
4. Use the same structure: What It Is → How It Works → Configuration → Implementation Status
