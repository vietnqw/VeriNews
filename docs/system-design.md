# 🏗️ VeriNews System Design

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Browser Extension                        │
│  ┌────────────┐  ┌────────────┐  ┌──────────────────────────┐  │
│  │  Content   │  │  Popup/    │  │  Background Service      │  │
│  │  Scripts   │  │  Results   │  │  Worker                  │  │
│  │            │  │  Panel     │  │  (API Communication)     │  │
│  └────────────┘  └────────────┘  └──────────────────────────┘  │
└─────────────────────────────┬───────────────────────────────────┘
                              │ HTTPS
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Backend API                              │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Verification Orchestrator                    │   │
│  │         (Workflow Engine / Request Handler)               │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│         ┌────────────────────┼────────────────────┐             │
│         ▼                    ▼                    ▼             │
│  ┌─────────────┐  ┌──────────────────┐  ┌─────────────────┐   │
│  │   Image     │  │   Content        │  │  Claim          │   │
│  │   Analysis  │  │   Similarity     │  │  Verification   │   │
│  │   Service   │  │   Search         │  │  Service        │   │
│  └─────────────┘  └──────────────────┘  └─────────────────┘   │
│         │                  │                      │             │
│         └──────────────────┼──────────────────────┘             │
│                            ▼                                    │
│                  ┌──────────────────┐                           │
│                  │  Final Verdict   │                           │
│                  │  Generator       │                           │
│                  └──────────────────┘                           │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Data Layer                               │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────┐   │
│  │   Vector     │  │  Trusted     │  │   Cache Layer       │   │
│  │   Database   │  │  News DB     │  │   (Redis)           │   │
│  │  (Embeddings)│  │  (Articles)  │  │                     │   │
│  └──────────────┘  └──────────────┘  └─────────────────────┘   │
└───────────────────────────────────────────────────────────────▲─┘
                                                                │
┌───────────────────────────────────────────────────────────────┘
│                    Data Ingestion Pipeline                       │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────┐   │
│  │   News       │  │  Article     │  │   Embedding         │   │
│  │   Crawler    │─▶│  Processor   │─▶│   Generator         │   │
│  │              │  │              │  │                     │   │
│  └──────────────┘  └──────────────┘  └─────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. **Browser Extension (Frontend)**

#### 1.1 Content Scripts
- Inject "Verify" button into social media posts
- Extract post content (text, images, metadata)
- Display verification results in UI overlay
- Handle user interactions

#### 1.2 Results Panel
- Show verification verdict (🟢 Verified / 🔴 Misleading / 🟡 Unverified)
- Display credibility score
- Show AI image warning (⚠️ if detected)
- List linked trusted sources
- Provide explanation/reasoning

#### 1.3 Background Service Worker
- Manage API communication with backend
- Handle authentication/API keys
- Monitor extension state

---

### 2. **Backend API**

#### 2.1 Verification Orchestrator
- **Role:** Central workflow coordinator
- **Responsibilities:**
  - Receive verification requests from extension
  - Orchestrate the verification pipeline
  - Aggregate results from all AI services
  - Return structured response to frontend

#### 2.2 AI/ML Services

##### Image Analysis Service
- **Purpose:** Detect AI-generated images
- **Input:** Image URL or base64 data
- **Output:** Probability score (0-1) + classification

##### Content Similarity Search Service
- **Purpose:** Find relevant articles from trusted sources
- **Input:** Social media post text
- **Process:**
  - Generate semantic embedding of post
  - Perform vector similarity search
  - Rank and filter top K articles
- **Output:** List of most relevant trusted articles

##### Claim Verification Service
- **Purpose:** Extract and verify factual claims
- **Input:**
  - Social media post text
  - Matched trusted articles (from similarity search)
- **Process:**
  - Decompose post into individual claims
  - Check each claim against articles
  - Classify as: Support / Contradict / Not Mentioned
- **Output:** Claim-by-claim verification results

##### Final Verdict Generator
- **Purpose:** Synthesize overall credibility judgment
- **Input:**
  - Image analysis results
  - Similarity search results
  - Claim verification results
- **Process:**
  - Analyze evidence from all sources
  - Calculate credibility score (0-100)
  - Determine final verdict category
  - Generate human-readable explanation
- **Output:** Final verdict + score + reasoning

---

### 3. **Data Layer**

#### 3.1 Vector Database
- Store semantic embeddings of trusted articles
- Enable fast similarity search

#### 3.2 Trusted News Database
- Store full article content and metadata

#### 3.3 Cache Layer
- Cache recent verification results
- Cache frequently accessed articles

---

### 4. **Data Ingestion Pipeline**

#### 4.1 News Crawler
- Scrape articles from trusted news sources
- Schedule periodic updates (daily/hourly)
- Handle various website structures

#### 4.2 Article Processor
- Clean and normalize article text
- Extract metadata (title, author, date, source)
- Validate and deduplicate articles

#### 4.3 Embedding Generator
- Generate semantic embeddings for articles
- Store embeddings in vector database
- Link embeddings to article records

---

## Data Flow

### Verification Request Flow

```
1. User clicks "Verify" on social media post
   ↓
2. Extension extracts post content (text + image)
   ↓
3. Background worker sends request to Backend API
   ↓
4. Orchestrator initiates parallel processing:
   ├─→ Image Analysis Service (AI detection)
   └─→ Content Similarity Search (find articles)
       ↓
       Claim Verification Service (check claims against articles)
       ↓
5. Final Verdict Generator synthesizes results
   ↓
6. Backend returns structured response
   ↓
7. Extension displays results in panel
```

---

## Technology Stack (Proposed)

### Frontend
- **Framework:** Vanilla JS / TypeScript (Manifest V3)
- **UI:** HTML/CSS

### Backend
- **API Framework:** FastAPI (Python)
- **AI/ML:** PyTorch, Transformers, Diffusers
- **Async Processing:** asyncio, Celery (for heavy tasks)

### Data
- **Vector DB:** pgvector
- **Relational DB:** PostgreSQL
- **Cache:** Redis

### Infrastructure
- **Containerization:** Docker
- **Orchestration:** Docker Compose (dev) / Kubernetes (prod)
- **Web Scraping:** Scrapy / Firecrawl

### AI Models
- **Embeddings:** text-embedding-3-small OpenAI model
- **Claim Verification:** GPT-4 / Claude API
- **Image Detection:** Third-party API
