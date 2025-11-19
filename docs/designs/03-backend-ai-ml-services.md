# Backend: AI/ML Services

## What It Is

The AI/ML Services provide intelligent processing using OpenAI's models. These services power the "understanding" parts of the retrieval system.

## What's Implemented

### 1. Embedding Service

**What it does**: Converts text into 1536-dimensional vectors

**How it works**:
- Takes text (query or article chunk)
- Calls OpenAI API (text-embedding-3-small model)
- Returns a vector (array of 1536 numbers)
- These vectors capture the meaning of the text

**Features**:
- Batch processing (multiple texts in one API call)
- Automatic vector normalization
- Error handling and retries

**When it's used**:
- During article ingestion (embed all chunks)
- During verification (embed user's query)

### 2. Query Extraction Service

**What it does**: Extracts clean queries, specific claims, and entities from social media posts

**How it works**:
- Takes messy post with emojis, hashtags, etc.
- Sends to GPT-4o-mini with structured prompt
- Gets back:
  - **Clean query**: 1-2 sentences, core topic cleaned of noise
  - **Claims**: List of up to 10 verifiable statements
  - **Entities**: Extracted persons, organizations, locations, etc.
  - **Factual Confidence**: Score (1-3) indicating if post contains verifiable facts

**Example**:
```
Input: "🚨 BREAKING: PM announces new tax policy! #Politics #Vietnam"

Output:
- Clean query: "Prime Minister announces new tax policy"
- Claims: ["Prime Minister announced tax policy"]
- Entities: {"persons": ["Prime Minister"], "locations": ["Vietnam"]}
- Factual Confidence: 3 (Verifiable)
```

**Implementation details**:
- Uses GPT-4o-mini (configurable)
- Temperature set to 0 (deterministic output)
- JSON mode for structured response
- **Two-step process**: Generates rationale first, then JSON for better reasoning

### 3. Chunk Reranking Service

**What it does**: Scores how relevant each article chunk is to the query

**How it works**:
- Takes original post + list of article chunks (top 100 from search)
- **Pre-filtering**: Optional entity filter removes chunks from articles that don't match query entities
- **Scoring**: Asks LLM to score each chunk on 0-10 scale
- **Parallelism**: Distributes chunks to 4 parallel workers (round-robin batching)
- Returns chunks sorted by score (threshold ≥ 5.0)

**Why it's needed**: Search algorithms aren't perfect. AI can understand context and judge true relevance better than vector/keyword search.

**Implementation details**:
- **Parallel Workers**: 4 concurrent API calls to reduce latency
- **Round-Robin Batching**: Prevents positional bias from search results
- **Timeout Protection**: 15s limit per worker
- **Entity Filtering**: Reduces cost/time by ignoring irrelevant content

### 4. Article Reranking Service (NEW)

**What it does**: Validates that the *full article's* main topic matches the query

**How it works**:
- Takes aggregated articles (top 10)
- Sends Title + Source + Top Chunk Snippet to LLM
- Asks: "Is the main topic of this article the same event/claim as the query?"
- Scores on 0-10 scale (Strict threshold ≥ 7.0)

**Why it's needed**: Prevents "false positives" where a single chunk matches keywords, but the article itself is about a different event or topic.

**Implementation details**:
- **High Parallelism**: 8 workers for fast processing
- **Short Timeout**: 5s limit (shorter prompt = faster response)
- **Adaptive Batching**: Sends all items to one worker if count is small (for listwise comparison)

### 5. Confidence Scoring Service (NEW)

**What it does**: Calculates multi-signal confidence score for the final results

**How it works**:
- Analyzes 5 signals:
  1. **Top Score** (35%): How good is the best article?
  2. **Score Gap** (25%): Is the best article clearly better than #2?
  3. **Entity Coverage** (20%): Do articles mention the people/places in the query?
  4. **Temporal Alignment** (10%): Do dates match?
  5. **Title Similarity** (10%): Does the article title match the query?
- Produces an **Overall Confidence** (0-1 scale) and Tier (HIGH, MEDIUM, LOW, NONE)

**Why it's needed**: To detect when the system fails to find relevant news (e.g., for a fake story or very new event) and warn the user instead of showing bad results.

### 6. Vietnamese Text Processor

**What it does**: Tokenizes Vietnamese text for search

**How it works**:
- Identifies Vietnamese compound words using `pyvi`
- Joins them with underscores: "công ty" → "công_ty"
- Preserves diacritical marks
- Mixed Vietnamese-English text supported

**Why it's needed**: Vietnamese doesn't have spaces between all word boundaries. Compound words need special handling for keyword search (BM25).

## AI Provider Abstraction

The code has a base `AIProvider` class that can work with different providers:
- **OpenAIProvider**: Currently implemented (handles both Embeddings and LLM)
- Future: Could add Anthropic, local models, etc.

This makes it easy to switch or add alternative AI providers via `config.yaml`.

## Cost Management

Current estimated usage per verification request (using `gpt-4o-mini`):
- Embedding generation: ~1,500 tokens
- Query extraction: ~800 tokens (increased due to entities/reasoning)
- Chunk Reranking: ~4,000 tokens (filtering reduces this)
- Article Reranking: ~500 tokens
- **Total**: ~$0.01 - $0.02 per verification

With caching (Redis), repeated queries cost ~0.

## What's NOT Implemented

- Image analysis (AI-generated image detection)
- Claim verification (checking if claims are true/false - logic layer)
- Source Credibility scoring (ranking *sources* by reliability, distinct from result confidence)
- Local model deployment

## Configuration

Settings in `config/config.yaml`:
- `ai.provider`: "openai"
- `ai.llm_model`: "gpt-4o-mini"
- `retrieval.query_extraction`: Max claims, confidence threshold
- `retrieval.reranking`: Worker counts, timeouts, entity filters
- `retrieval.confidence_scoring`: Weights and thresholds
