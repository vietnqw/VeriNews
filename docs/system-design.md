# 🏗️ VeriNews System Design

## System Overview

VeriNews is an AI-powered fact-checking system that verifies social media posts against trusted Vietnamese news sources in real-time.

```mermaid
%%{init: {'theme':'base', 'themeVariables': { 'fontSize':'16px'}}}%%
graph TD
    %% Browser Extension Layer
    subgraph BrowserExt["<b>Browser Extension</b>"]
        direction TB
        ContentScript["<b>Content Scripts</b><br/><i>Extract Post Content</i>"]
        ResultsPanel["<b>Results Panel</b><br/><i>Display Verdict & Evidence</i>"]
    end

    %% Backend API Layer
    subgraph BackendAPI["<b>Backend API (FastAPI)</b>"]
        direction TB

        Orchestrator["<b>Verification Orchestrator</b><br/>"]

        subgraph Pipeline["<b>Processing Pipeline</b>"]
            direction LR

            Retrieval["<b>Retrieval</b><br/><div style='text-align:left'>• Extract Claims<br/>• Hybrid Search <br> (Vector, BM25)<br/>• Rerank & Score</div>"]
            Verification["<b>Verification</b><br/><div style='text-align:left'>• Classify Stance<br/>• Aggregate Verdict<br/>• Generate Explanation</div>"]

            Retrieval ==> Verification
        end

        Orchestrator ==> Pipeline
    end

    %% Data Layer (Left Side)
    subgraph DataLayer["<b>Data Layer</b>"]
        direction TB
        Cache["<b>Redis Cache</b><br/><i>24h TTL</i>"]
        Database["<b>PostgreSQL</b><br/><div style='text-align:left'>• Vector DB (pgvector)<br/>• Article DB (FTS)<br/>• Embeddings</div>"]
    end

    %% External AI (Right Side)
    OpenAI["<b>🤖 OpenAI API</b><br/><div style='text-align:left'>• text-embedding-3-small<br/>• GPT-4o-mini</div>"]

    %% Data Crawler (Background)
    subgraph CrawlerPipeline["<b>Data Crawler</b> <br> <i>(Background - Every 30 minutes)</i>"]
        direction LR
        Crawl["<b>Crawl & Scrape</b><br/><i>RSS → Content</i>"]
        Process["<b>Process & Index</b><br/><i>Chunk → Embed → Index</i>"]

        Crawl --> Process
    end

    %% External Sources (Bottom)
    RSSFeeds["<b>📰 Trusted News Sources</b><br/><i>100+ RSS Feeds</i><br/>Thanh Niên, Tuổi Trẻ, VNExpress, etc."]

    %% Main Verification Flow
    ContentScript ==>|POST /verify| Orchestrator
    Orchestrator -->|Check Cache| Cache
    Orchestrator ==>|Response| ResultsPanel

    Pipeline -->|Search Results| Database
    Pipeline -->|Extract, Rerank, Verify| OpenAI

    %% Background Crawler Flow
    RSSFeeds -.->|Fetch RSS| Crawl
    Crawl -.->|Generate Embeddings| OpenAI
    OpenAI -.->|Vectors| Process
    Process -.->|Store| Database

    %% Styling
    classDef browserStyle fill:#fff3e0,stroke:#f57c00,stroke-width:3px,color:#e65100,rx:10,ry:10
    classDef apiStyle fill:#e8f5e9,stroke:#388e3c,stroke-width:3px,color:#1b5e20,rx:10,ry:10
    classDef crawlerStyle fill:#fff9c4,stroke:#f57f17,stroke-width:3px,color:#f57f17,rx:10,ry:10
    classDef dataStyle fill:#fce4ec,stroke:#c2185b,stroke-width:3px,color:#880e4f,rx:10,ry:10
    classDef externalStyle fill:#e0f2f1,stroke:#00897b,stroke-width:2px,color:#004d40,rx:8,ry:8
    classDef pipelineStyle fill:#f5f5f5,stroke:#9e9e9e,stroke-width:2px,stroke-dasharray:5 5,rx:10,ry:10
    classDef nodeStyle fill:#ffffff,stroke:#424242,stroke-width:2px,color:#212121,rx:8,ry:8
    classDef orchestratorStyle fill:#ffecb3,stroke:#ff6f00,stroke-width:3px,color:#e65100,rx:8,ry:8

    class BrowserExt browserStyle
    class BackendAPI apiStyle
    class CrawlerPipeline crawlerStyle
    class DataLayer dataStyle
    class RSSFeeds,OpenAI externalStyle
    class Pipeline pipelineStyle
    class ContentScript,ResultsPanel,Crawl,Process,Cache,Database nodeStyle
    class Retrieval,Verification nodeStyle
    class Orchestrator orchestratorStyle
```

**Key Capabilities:**
- ✅ Real-time verification of Vietnamese social media posts
- ✅ Hybrid AI approach combining semantic search + keyword matching
- ✅ Multi-claim analysis with stance classification
- ✅ Automated news ingestion from 100+ trusted sources
- ✅ 24-hour fresh data with automatic cleanup
- ✅ Sub-second response with intelligent caching

---

## Detailed Architecture

```mermaid
%%{init: {'theme':'base', 'themeVariables': { 'fontSize':'18px'}}}%%
graph TD
    %% Browser Extension Layer
    subgraph BrowserExt["<b>Browser Extension</b>"]
        direction TB
        ContentScript["<b>Content Scripts</b><br/><i>Extract Post Content</i>"]
        ServiceWorker["<b>Service Worker</b><br/><i>API Communication</i>"]
        ResultsPanel["<b>Results Panel</b><br/><i>Verdict Display</i>"]

        ContentScript -->|"Extract Text"| ServiceWorker
        ServiceWorker ==>|"Display Results"| ResultsPanel
    end

    %% Backend API Layer
    subgraph BackendAPI["<b>Backend API</b>"]
        direction TB

        Orchestrator["<b>Verification Orchestrator</b><br/><i>Workflow Coordinator</i>"]

        %% Invisible spacer to add distance between Orchestrator and Pipelines
        SPACE1(( )):::invisible

        %% Pipeline Container for better layout
        subgraph Pipelines["<b>Processing Pipeline</b>"]
            direction LR

            subgraph Retrieval["<b>Retrieval Phase</b>"]
                direction TB
                QueryExtract["<b>Query Extraction</b><br/><i>Claims & Entities</i>"]
                HybridSearch["<b>Hybrid Search</b><br/><i>Vector + BM25</i>"]
                Reranking["<b>Reranking & Scoring</b><br/><i>Multi-Signal Confidence</i>"]

                QueryExtract ==>|"Queries"| HybridSearch
                HybridSearch ==>|"Top-n Chunks"| Reranking
            end

            %% Invisible spacers between subgraphs
            SPACE2(( )):::invisible
            SPACE3(( )):::invisible

            subgraph Verification["<b>Verification Phase</b>"]
                direction TB
                StanceClass["<b>Stance Classification</b><br/><i>NLI-based Analysis</i>"]
                VerdictAgg["<b>Verdict Aggregation</b><br/><i>Multi-Claim Synthesis</i>"]

                StanceClass ==>|"Stances"| VerdictAgg
            end

            Retrieval ==>|"Top Articles"| Verification
        end

        FinalResponse["<b>Final Response</b><br/><i>Verdict + Evidence + Explanation</i>"]

        Orchestrator ==>|"Start Verification"| Pipelines
        Pipelines ==>|"Result"| FinalResponse
    end

    %% Data Crawler Pipeline (Background)
    subgraph CrawlerPipeline["<b>Data Crawler Pipeline</b><br/><i>Background Tasks (Celery)</i>"]
        direction TB

        Scheduler["<b>Celery Beat Scheduler</b><br/><i>Every 5 minutes</i>"]

        subgraph CrawlerStages["<b>3-Phase Processing</b>"]
            direction LR

            CrawlScrape["<b>1. Crawl & Scrape</b><br/><i>RSS <br> Content Extraction</i><br/>"]
            ProcessIndex["<b>2. Process & Index</b><br/><i>Chunk→Embed→Index</i><br/><i>(Vector + BM25)</i>"]
            Cleanup["<b>3. Data Cleanup</b><br/><i>Delete > 24h articles</i><br/><i>(Prevent DB bloat)</i>"]

            CrawlScrape --> ProcessIndex
            ProcessIndex --> Cleanup
        end

        Scheduler -.->|"Trigger"| CrawlerStages
    end

    %% RSS Feeds Source
    RSSFeeds["<b>RSS Feeds</b><br/><i>100+ Trusted Sources</i><br/><i>Thanh Niên, Tuổi Trẻ, etc.</i>"]

    %% Data Layer
    subgraph DataLayer["<b>Data Layer</b>"]
        direction LR
        VectorDB["<b>Vector DB</b><br/><i>pgvector (1536-dim)</i>"]
        ArticleDB["<b>Article DB</b><br/><i>PostgreSQL + FTS</i>"]
        CacheLayer["<b>Cache</b><br/><i>Redis (24h TTL)</i>"]
    end

    %% Main System Connections
    ServiceWorker ==>|"POST /verify"| Orchestrator
    FinalResponse ==>|"JSON Response"| ServiceWorker

    %% Data Layer Interactions (Verification)
    Orchestrator -.->|"Check Cache"| CacheLayer
    HybridSearch -.->|"Vector Search"| VectorDB
    HybridSearch -.->|"BM25 Search"| ArticleDB
    Reranking -.->|"Fetch Context"| ArticleDB
    StanceClass -.->|"Fetch Content"| ArticleDB

    %% Crawler Pipeline Connections
    RSSFeeds -.->|"Fetch Feeds"| CrawlScrape
    CrawlScrape -.->|"Raw Articles"| ProcessIndex
    ProcessIndex -.->|"Store Chunks"| ArticleDB
    ProcessIndex -.->|"Store Embeddings"| VectorDB
    Cleanup -.->|"Delete Expired"| ArticleDB
    Scheduler -.->|"Message Queue"| CacheLayer

    %% Invisible class (this works in PNG/SVG!)
    classDef invisible fill:none,stroke:none,color:transparent;

    %% Enhanced Styling with Gradients and Shadows
    classDef browserStyle fill:#fff3e0,stroke:#f57c00,stroke-width:3px,color:#e65100,rx:10,ry:10
    classDef apiStyle fill:#e8f5e9,stroke:#388e3c,stroke-width:3px,color:#1b5e20,rx:10,ry:10
    classDef crawlerStyle fill:#fff9c4,stroke:#f57f17,stroke-width:3px,color:#f57f17,rx:10,ry:10
    classDef dataStyle fill:#fce4ec,stroke:#c2185b,stroke-width:3px,color:#880e4f,rx:10,ry:10
    classDef retrievalStyle fill:#e3f2fd,stroke:#1976d2,stroke-width:3px,color:#0d47a1,rx:10,ry:10
    classDef verificationStyle fill:#f3e5f5,stroke:#7b1fa2,stroke-width:3px,color:#4a148c,rx:10,ry:10
    classDef pipelineStyle fill:#ffffff,stroke:#9e9e9e,stroke-width:2px,stroke-dasharray:5 5,rx:10,ry:10
    classDef nodeStyle fill:#ffffff,stroke:#424242,stroke-width:2px,color:#212121,rx:8,ry:8
    classDef orchestratorStyle fill:#ffecb3,stroke:#ff6f00,stroke-width:3px,color:#e65100,rx:8,ry:8
    classDef responseStyle fill:#c8e6c9,stroke:#2e7d32,stroke-width:3px,color:#1b5e20,rx:8,ry:8
    classDef crawlerNodeStyle fill:#fffde7,stroke:#f9a825,stroke-width:2px,color:#f57f17,rx:8,ry:8
    classDef sourceStyle fill:#e0f2f1,stroke:#00897b,stroke-width:2px,color:#004d40,rx:8,ry:8

    %% Apply Styles
    class BrowserExt browserStyle
    class BackendAPI apiStyle
    class CrawlerPipeline crawlerStyle
    class DataLayer dataStyle
    class Retrieval retrievalStyle
    class Verification verificationStyle
    class Pipelines,CrawlerStages pipelineStyle
    class ContentScript,ServiceWorker,ResultsPanel,QueryExtract,HybridSearch,Reranking,StanceClass,VerdictAgg,VectorDB,ArticleDB,CacheLayer nodeStyle
    class Orchestrator orchestratorStyle
    class FinalResponse responseStyle
    class Scheduler,CrawlScrape,ProcessIndex,Cleanup crawlerNodeStyle
    class RSSFeeds sourceStyle
```

---

## Core Components

### 1. **Browser Extension (Frontend)**

#### 1.1 Content Scripts
- Inject "Verify" button into social media posts (Facebook, feeds, comments)
- Extract post text content using DOM traversal and MutationObserver
- Handle "See more" button expansion for full post text
- Handle user interactions (button clicks)
- **Note**: Image extraction not yet implemented

#### 1.2 Results Panel
- Show verification verdict (🟢 Fully Supported / 🟡 Partially Supported / 🔴 Refuted / ⚪ Not Enough Info)
- Display credibility score (0-100)
- Show Vietnamese explanation of verdict
- List linked trusted articles with relevance scores
- Display claim-by-claim breakdown
- Provide links to source articles for further reading

#### 1.3 Background Service Worker
- Manage API communication with backend (POST /api/v1/verify)
- Cache verification results locally (chrome.storage API)
- Handle request/response serialization
- Monitor extension health and API availability

---

### 2. **Backend API (FastAPI)**

**Endpoint**: `POST /api/v1/verify`

**Input Schema**:
```json
{
  "text": "string (10-10,000 characters)",
  "cache_bypass": "boolean (optional, default: false)"
}
```

#### 2.1 Verification Orchestrator
- **Role:** Central workflow coordinator and request handler
- **Location**: `backend/app/api/verification.py`
- **Responsibilities:**
  - Validate incoming verification requests
  - Check Redis cache for previous results (24-hour TTL)
  - Orchestrate retrieval and verification pipelines
  - Aggregate results from all services
  - Return structured JSON response to frontend
  - Cache results in Redis

#### 2.2 Retrieval Pipeline (3 Phases) - Query → Search → Score

**Location**: `backend/app/services/retrieval/`

1. **Query Extraction & Embedding**
   - LLM extracts claims and entities from post
   - OpenAI text-embedding-3-small generates 1536-dimensional vectors
   - Files: `query_extraction_service.py`, `embedding_service.py`

2. **Hybrid Search & Fusion**
   - **Vector Search**: pgvector with COSINE similarity
   - **BM25 Search**: PostgreSQL full-text search with Vietnamese tokenization
   - Reciprocal Rank Fusion (k=60) merges results
   - File: `retrieval_orchestrator.py`

3. **Reranking & Validation**
   - LLM reranks top-100 chunks and full articles (threshold: 5.0/10.0)
   - Multi-signal confidence scoring (5 weighted factors)
   - Final validation rejects results below confidence threshold (default 0.25)
   - Files: `chunk_reranking_service.py`, `article_reranking_service.py`, `confidence_scoring_service.py`

**Output**: List of most relevant articles with relevance scores and chunk details

#### 2.3 Verification Pipeline (2 Phases) - Classify → Aggregate

**Location**: `backend/app/services/verification/`

1. **Stance Classification**
   - NLI-based classification for each claim-article pair
   - Possible stances: **SUPPORTS**, **REFUTES**, **NOT_ENOUGH_INFO**
   - Minimum confidence threshold: 0.6 (60%)
   - Files: `stance_classifier_service.py`, `verification_service.py`

2. **Verdict Aggregation & Explanation**
   - Combines claim verdicts into overall assessment
   - Possible verdicts: **FULLY_SUPPORTED**, **PARTIALLY_SUPPORTED**, **REFUTED**, **NOT_ENOUGH_INFO**
   - Generates Vietnamese explanation with confidence scores and sources
   - File: `verdict_aggregator_service.py`, `explanation_generator_service.py`

**Output**: VerificationResult with verdict, confidence, explanation, and claim-by-claim breakdown

---

### 3. **Data Layer**

#### 3.1 Vector Database (pgvector in PostgreSQL)
**Location**: `ArticleChunk.embedding` column
- **Dimension**: 1536 floats (OpenAI embedding standard)
- **Index Type**: IVFFlat (Approximate Nearest Neighbor)
- **Index Config**: lists=100 (number of clusters)
- **Metric**: COSINE similarity
- **Query Speed**: ~10-100ms for top-k search
- **Storage**: ~1.5GB per 100K articles

#### 3.2 Trusted News Database (PostgreSQL)
**Tables**:
- **Article**: title, url, content, published_at, feed_id, created_at
- **ArticleChunk**: chunk_text, embedding, search_vector (BM25), article_title, source_name, published_at
- **RssFeed**: feed_url, topic, is_active, last_fetched_at, source_id
- **NewsSource**: name, website_url, topic

**Key Constraint**:
- Unique index on Article.url (prevents duplicate articles)
- Unique constraint on (ArticleChunk.article_id, chunk_index)
- Cascade deletes: Deleting Article cascades to ArticleChunk

#### 3.3 Full-Text Search (PostgreSQL tsvector + GIN Index)
**Column**: `ArticleChunk.search_vector`
- **Tokenization**: Vietnamese-aware using pyvi library
- **Config**: PostgreSQL 'simple' config (no stemming)
- **Index Type**: GIN (Generalized Inverted Index)
- **Purpose**: BM25-like keyword search for lexical matching

#### 3.4 Cache Layer (Redis)
**Purpose**: Cache verification results to avoid reprocessing
- **Key Format**: `retrieval:{SHA256(post_text)}`
- **Value**: Complete retrieval results (articles, timings, query count)
- **TTL**: 24 hours (configurable)
- **Hit Speed**: <50ms vs. 2.5-4.5s for cache miss
- **Also used**: Celery message broker for task queue

---

### 4. **Data Ingestion Pipeline (Background Celery Tasks)**

**Framework**: Celery 5.4+ with Beat scheduler
**Interval**: Every 5 minutes (configurable)
**Workers**: 4 parallel workers (configurable)

**3-Phase Process**:

1. **Crawl & Scrape** (`rss_service.py`, `scraper_service.py`)
   - Fetches RSS feeds from 100+ trusted sources (Thanh Niên, Tuổi Trẻ, Lào Cái)
   - Extracts content using 4-stage fallback: Trafilatura → MVP → BeautifulSoup
   - Deduplicates by URL, filters articles >48 hours old, rate-limits to 50/feed

2. **Process & Index** (`chunking_service.py`, `embedding_service.py`, `bm25_search_service.py`)
   - Chunks articles into 500-2000 character segments with denormalized metadata
   - Generates OpenAI embeddings (1536-dimensional vectors)
   - Creates vector index (pgvector IVFFlat) and BM25 index (PostgreSQL GIN) automatically

3. **Data Cleanup** (`cleanup_expired_articles` task)
   - Runs every 5 minutes alongside crawl
   - Deletes Article records >24 hours old (cascade deletes chunks)
   - Purpose: Prevent database bloat while maintaining fresh data for verification

---

## Data Flow

### Verification Request Flow (Simplified)

```mermaid
sequenceDiagram
    actor User
    participant Ext as Browser<br/>Extension
    participant API as Backend<br/>API
    participant Cache as Redis<br/>Cache
    participant DB as PostgreSQL<br/>Database
    participant LLM as OpenAI<br/>API

    User->>Ext: Click "Verify" button
    Ext->>Ext: Extract post text via DOM
    Ext->>API: POST /api/v1/verify {text}

    API->>Cache: Check cache (SHA256 hash)
    alt Cache Hit
        Cache-->>API: Return cached result
    else Cache Miss (Retrieval Pipeline)
        API->>LLM: Extract claims & generate embeddings
        LLM-->>API: claims[], embeddings[]

        API->>DB: Hybrid search (vector + BM25)<br/>Reciprocal Rank Fusion
        DB-->>API: Ranked articles

        API->>LLM: Rerank chunks & articles
        LLM-->>API: Top articles with scores

        API->>API: Confidence scoring & validation
        API-->>API: Top-N articles selected

        note over API: Verification Pipeline
        API->>LLM: Classify claim stances (NLI)
        LLM-->>API: SUPPORTS/REFUTES/NOT_ENOUGH_INFO

        API->>LLM: Aggregate verdict & generate explanation
        LLM-->>API: Vietnamese explanation

        API->>Cache: Cache result (24h TTL)
    end

    API-->>Ext: JSON {verdict, articles, confidence, explanation}
    Ext->>Ext: Render results panel
    Ext-->>User: Display verdict, sources, explanation
```

### Data Ingestion Flow (Background Pipeline)

**Note**: Data ingestion runs as a background Celery task every 5 minutes. Articles are retained for 24 hours and then automatically cleaned up.

```mermaid
graph LR
    Feed["📡 RSS Feeds<br/>(100+ sources)<br/>Thanh Niên, Tuổi Trẻ, etc."]

    Crawl["🔍 Crawl & Scrape<br/>- Fetch RSS feeds<br/>- Extract content<br/>(4-stage fallback)"]

    Process["⚙️ Process<br/>- Chunk text<br/>(500-2000 chars)<br/>- Generate embeddings"]

    Index["🔎 Index<br/>- Vector index (IVFFlat)<br/>- BM25 index (GIN)<br/>- Vietnamese tokenization"]

    DB["💾 PostgreSQL<br/>Articles + Chunks<br/>(24h retention)"]

    Feed --> Crawl
    Crawl --> Process
    Process --> Index
    Index --> DB

    style Crawl fill:#e3f2fd
    style Process fill:#f3e5f5
    style Index fill:#fce4ec
```

---

## Technology Stack

### Frontend (Browser Extension)
- **Language:** JavaScript (ES6+)
- **Standard:** Manifest V3 (Chrome/Chromium 88+)
- **DOM Manipulation:** Native DOM API + MutationObserver
- **Storage:** Chrome Storage API (local)
- **Testing:** Jest + Puppeteer (headless Chrome)

### Backend
**Python 3.13+ with UV Package Manager**

**API Framework:**
- FastAPI 0.109+ (HTTP server)
- Pydantic 2.12+ (request/response validation)
- Uvicorn (async ASGI server)

**Async & Task Queue:**
- asyncio (built-in async runtime)
- Celery 5.4+ with Beat scheduler (task queue + scheduling)
- asyncpg (PostgreSQL async driver)

**Text Processing:**
- Trafilatura 1.8+ (content extraction)
- BeautifulSoup4 (HTML parsing)
- Readability-lxml (content detection)
- justext (boilerplate removal)
- PyVi 0.1+ (Vietnamese tokenization)

**AI/ML:**
- OpenAI Python SDK 1.3+ (embeddings + LLM APIs)
- scikit-learn (NLI-based stance classification)
- Loguru (structured logging)

**ORM & Migrations:**
- SQLAlchemy 2.0+ (async ORM)
- Alembic 1.13+ (database migrations)

**Data:**
- **Vector Database:** pgvector extension on PostgreSQL
- **Relational Database:** PostgreSQL 18
- **Cache:** Redis 7
- **Full-Text Search:** PostgreSQL built-in (tsvector + GIN index)

### Infrastructure
- **Containerization:** Docker + Docker Compose
- **Database Versioning:** Alembic (migrations)
- **Logging:** Loguru (structured logs to files)
- **Code Quality:** Ruff (linting + formatting)
- **Pre-commit:** Hooks for code quality

### AI Models & APIs
**Currently Implemented:**
- **Embeddings:** OpenAI text-embedding-3-small (1536-dim)
  - Cost: ~$0.00002 per 1K tokens
- **LLM (Query Extraction, Reranking):** GPT-4o-mini
  - Cost: ~$0.15/1M input tokens, $0.6/1M output tokens
- **LLM (Stance Classification):** GPT-4o-mini
  - Cost: ~$0.15/1M input tokens, $0.6/1M output tokens
- **LLM (Explanation Generation):** GPT-4o-mini

**Planned (Not Yet Implemented):**
- **Image Detection:** Third-party vision API (TBD - Google Vision, AWS Rekognition, Azure Computer Vision)

### Development Tools
- **Package Manager:** UV (fast pip alternative)
- **Database CLI:** psql + pgAdmin web interface
- **Task Monitoring:** Celery Flower (optional web UI)
- **API Documentation:** Swagger UI + ReDoc (auto-generated from FastAPI)
- **Testing Framework:** pytest + pytest-asyncio + pytest-cov

### Response Time Characteristics
- **Cache Hit**: 50-100ms
- **Cache Miss (Verification)**: 2.5-4.5 seconds
  - Query Extraction: 200-300ms
  - Embeddings: 300-600ms
  - Hybrid Search: 500-1,000ms
  - Reranking: 1,000-1,500ms
  - Verification: 1,000-2,000ms
