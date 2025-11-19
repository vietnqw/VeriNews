# Backend: Retrieval System

## What It Is

The Retrieval System finds relevant news articles for a given social media post. It uses a 9-stage pipeline that combines AI understanding with traditional search methods to find the most relevant articles from the database, with multi-signal confidence validation.

## What It Does

Takes a social media post → Returns ranked list of relevant news articles

## The 9 Stages

### Stage 1: Query Extraction
**What happens**: AI extracts clean queries and entities from the noisy post

- Sends post to gpt-4o-mini (configurable LLM)
- Gets back:
  - Clean query (main topic)
  - Factual claims (up to 8 specific statements)
  - Entities grouped by type (persons, organizations, locations, products_topics, decision_ids)
  - Factual confidence score (1-3 scale)
- Example:
  - Input: "🚨 Breaking: President signs climate bill! #Politics"
  - Output: Clean query: "President signs climate bill", Claims: ["President signed climate bill"], Entities: {persons: [], locations: [], ...}

**Implementation**: Uses OpenAI gpt-4o-mini API with structured JSON prompts

**Early Exit**: If factual confidence < 2 (opinion/satire), returns empty results immediately

### Stage 2: Embedding Generation
**What happens**: Converts text queries into numbers (vectors)

- Takes the clean query + claims from Stage 1
- Sends to OpenAI to generate 1536-dimensional vectors
- Batches multiple queries together for efficiency
- Optional: Filters redundant claims (>0.75 cosine similarity to clean_query)
- These vectors capture the semantic meaning of the text

**Implementation**: Uses OpenAI text-embedding-3-small model

### Stage 3: Hybrid Search
**What happens**: Searches database using two different methods simultaneously

**Method A - Vector Search**:
- Compares query vectors with article chunk vectors
- Uses cosine similarity (measures how similar vectors are)
- Finds semantically similar content even if words are different
- Uses pgvector extension with IVFFlat index for fast search

**Method B - BM25 Keyword Search**:
- Traditional keyword matching
- Uses PostgreSQL full-text search
- Good at finding exact terms and names
- Custom Vietnamese tokenizer for compound words

Both methods run sequentially (to avoid database session concurrency issues), each returning top 100 results.

### Stage 4: Reciprocal Rank Fusion (RRF)
**What happens**: Combines all the search results into one ranked list

- Has multiple result lists from Stage 3 (vector + BM25 for each query)
- Uses RRF algorithm to merge them intelligently
- Chunks appearing in multiple lists get boosted
- Results in ~100-200 unique article chunks

**Why**: Different search methods are good at different things. RRF combines their strengths.

### Stage 5: Chunk Reranking (Parallel Workers + Entity Filtering)
**What happens**: AI scores how relevant each chunk is using parallel workers with entity-based pre-filtering

- Takes top 100 chunks from Stage 4
- **Entity filtering** (optional): Filters articles that contain at least 60% of extracted entities
- Distributes remaining chunks round-robin to 4 parallel workers
- Each worker scores its batch using gpt-4o-mini (0-10 scale with detailed rubric)
- Workers run concurrently with 15s timeout per worker
- Failed/timeout workers fall back to RRF scores
- Filters chunks below score threshold (5+)
- Re-sorts by AI relevance scores and returns top 10

**Why**: Search algorithms aren't perfect. AI can understand context and nuance better. Parallel processing reduces latency while round-robin distribution prevents positional bias. Entity filtering ensures we only rerank chunks from articles that mention relevant entities from the query.

**Key Optimizations**:
- **Entity filtering**: Pre-filters at article level based on presence of query entities (persons, organizations, locations)
  - Reduces chunks to rerank by ~30-50% on average
  - Improves relevance by focusing on entity-rich content
  - Configurable threshold (default: 60% entity match ratio)
  - Case-insensitive substring matching
- **Round-robin batching**: Each worker gets mix of high/medium/low similarity chunks (prevents bias from vector search ordering)
- **Parallel execution**: 4 concurrent API calls instead of sequential
- **Timeout protection**: 15s limit per worker prevents long tail latency
- **Graceful degradation**: Uses fallback RRF scores for failed workers
- **Score threshold filtering**: Only returns high-relevance results (5+ out of 10)
- **Detailed rubric prompt**: 0-10 grading rubric for consistent calibration

### Stage 6: Article Aggregation
**What happens**: Groups chunks back into full articles

- Each chunk belongs to an article
- Groups all chunks from same article together
- Uses **maximum chunk score** as article relevance (not sum)
- Filters articles with max_score < 5.0
- Returns up to 10 articles
- Includes relevant excerpts from matched chunks

### Stage 7: Article Reranking
**What happens**: AI validates that each article's main topic matches the query

- Takes aggregated articles from Stage 6
- 8 parallel workers score articles using gpt-4o-mini (0-10 scale)
- Prompt includes: title, source, top chunk snippet (200 chars)
- 5s timeout per worker (shorter than chunk reranking)
- Filters articles scoring < 5.0
- Returns top 10 articles sorted by score

**Why**: Individual chunks might match, but the full article could be tangential. This stage validates main topic relevance. Includes optimization to early exit if a single article has very high confidence (score ≥ 9.0).

**Scoring Rubric**:
- 10: Article's main topic = same specific event/claim as query
- 7-9: Article discusses query topic substantially
- 5-6: Article mentions query entities but different main topic
- 0-4: Article about completely different topic

### Stage 8: Confidence Scoring
**What happens**: Multi-signal quality assessment of retrieved articles

Calculates overall confidence (0-1 scale) using 5 weighted signals:
- **Top article score** (35%): Raw quality of best article (normalized 0-10 → 0-1)
- **Score gap ratio** (25%): Gap between #1 and #2 (indicates clear winner)
- **Entity coverage** (20%): Percentage of query entities found in articles
- **Temporal alignment** (10%): Whether date/time entities match
- **Title similarity** (10%): Cosine similarity between query and article title embeddings

**Confidence Tiers**:
- HIGH: >= 0.75 (strong match)
- MEDIUM: >= 0.50 (moderate match)
- LOW: >= 0.25 (weak match)
- NONE: < 0.25 (no relevant articles)

### Stage 9: Final Validation
**What happens**: Gate final results based on confidence

- If overall confidence < 0.25 (NONE tier): Returns "no relevant articles" to user
- Otherwise: Returns articles with confidence metrics and low_confidence_warning if needed
- Prevents returning irrelevant articles that passed earlier filters

## Vietnamese Language Support

Handles Vietnamese text specially:
- Keeps compound words together ("công ty" stays as one term)
- Preserves diacritical marks
- Custom tokenization for BM25 search
- OpenAI embeddings handle Vietnamese well natively

## Performance

Typical timing breakdown (with parallel reranking):
- Query extraction: 100-200ms
- Embedding generation: 200ms
- Hybrid search: 80ms (sequential execution of vector + BM25)
- Fusion: 20ms
- Chunk reranking: 300ms (4 parallel workers, 15s timeout)
- Article aggregation: 20ms
- Article reranking: 150ms (8 parallel workers, 5s timeout)
- Confidence scoring: 100ms (includes title embedding)
- **Total**: ~850-1000ms

With caching: <10ms for repeated queries

**Reranking Performance Details**:
- Chunk reranking: 4 workers × ~75ms = 300ms (parallel with round-robin)
- Article reranking: 8 workers × ~20ms = 150ms (fewer items, more workers)
- Entity filtering reduces chunks by ~30-50% before reranking
- Timeout protection ensures predictable latency

**Early Exit Optimizations**:
- Low factual confidence: Skip entire retrieval pipeline
- No relevant articles (confidence < 0.25): Return early with clear indication

## Technology Stack

- **Query Extraction**: OpenAI gpt-4o-mini (configurable to gpt-4o, claude-3-5-sonnet, etc.)
- **Embeddings**: OpenAI text-embedding-3-small (1536 dimensions)
- **Vector Search**: PostgreSQL pgvector extension with IVFFlat index
- **Keyword Search**: PostgreSQL full-text search with custom Vietnamese config
- **Chunk/Article Reranking**: OpenAI gpt-4o-mini with parallel workers
- **Orchestration**: Python async/await for parallel operations
- **Caching**: Redis for storing results

## Key Design Choices

**Why hybrid search?**
- Vector search: Good at meaning, weak at exact terms
- Keyword search: Good at exact terms, weak at synonyms
- Together: Best of both worlds

**Why use AI twice (extraction + reranking)?**
- Extraction: Cleans up messy input
- Reranking: Improves final quality with detailed relevance assessment
- Cost-effective placement in the pipeline (only scores top 100, not all chunks)

**Why parallel workers for reranking?**
- Shorter prompts per worker = faster LLM processing
- Concurrent API calls = better latency
- Round-robin distribution = less bias from search ordering
- Timeout protection = predictable tail latency
- Graceful degradation = reliability even with partial failures

**Why entity filtering before reranking?**
- Reduces computational cost by filtering irrelevant chunks early
- Improves quality by focusing on entity-relevant content
- Entities are strong signals of topical relevance (persons, orgs, locations)
- Configurable threshold allows tuning precision/recall trade-off (default: 60%)
- Works synergistically with hybrid search (vector + BM25)

**Why chunk articles?**
- Long articles don't match well as a whole
- Smaller chunks are more precise
- Can return relevant excerpts, not just article titles

**Why two-stage reranking (chunks then articles)?**
- Chunk reranking: Finds most relevant excerpts (fine-grained)
- Article reranking: Validates main topic match (coarse-grained)
- Prevents false positives where chunks match but article is tangential
- Different worker counts optimize for each stage (4 for 100 chunks, 8 for 10 articles)

**Why confidence scoring with multiple signals?**
- Single scores can be misleading (high score on wrong topic)
- Entity coverage ensures completeness
- Score gap indicates distinctiveness (#1 clearly better than #2)
- Temporal/spatial alignment validates event relevance
- Title similarity confirms topic match
- Combined signals provide robust quality assessment

**Why final validation gate?**
- Previous filters optimize for recall (finding relevant content)
- Confidence gate optimizes for precision (rejecting irrelevant results)
- Better user experience: "no relevant articles" vs bad recommendations
- Configurable threshold (0.25) balances precision/recall

## Configuration

All configurable via `config/config.yaml`:

**Query Extraction**:
- `max_claims`: Maximum claims to extract (default: 8)
- `min_factual_confidence`: Minimum confidence to proceed (default: 2)
- `enable_similarity_filter`: Filter redundant claims (default: true)
- `similarity_threshold`: Similarity threshold for filtering (default: 0.75)

**Search**:
- `vector_search.top_k`: Vector search results (default: 100)
- `bm25_search.top_k`: BM25 search results (default: 100)
- `fusion.rrf_k`: RRF fusion constant (default: 60)

**Chunk Reranking**:
- `num_parallel_workers`: Number of concurrent workers (default: 4)
- `worker_timeout_seconds`: Timeout per worker (default: 15s)
- `max_concurrent_calls`: Rate limiting for API calls (default: 4)
- `score_threshold`: Minimum score to include (default: 5)
- `top_n`: Chunks to return after reranking (default: 10)
- `entity_filter.enabled`: Enable entity-based filtering (default: true)
- `entity_filter.min_entity_match_ratio`: Minimum entity match ratio (default: 0.6 = 60%)

**Article Reranking**:
- `article_level.enabled`: Enable article reranking (default: true)
- `article_level.num_parallel_workers`: Workers for articles (default: 8)
- `article_level.worker_timeout_seconds`: Timeout per worker (default: 5s)
- `article_level.score_threshold`: Minimum article score (default: 5.0)
- `article_level.max_articles_to_rerank`: Limit articles (default: 15)

**Aggregation**:
- `max_articles`: Maximum articles to return (default: 10)
- `min_chunk_score`: Minimum max chunk score (default: 5.0)

**Confidence Scoring**:
- `min_confidence_threshold`: Reject below this (default: 0.25)
- `weights.top_article_score`: Weight (default: 0.35)
- `weights.score_gap_ratio`: Weight (default: 0.25)
- `weights.entity_coverage`: Weight (default: 0.20)
- `weights.temporal_alignment`: Weight (default: 0.10)
- `weights.title_similarity`: Weight (default: 0.10)
- `thresholds.high/medium/low`: Tier thresholds (default: 0.75/0.50/0.25)

**Cache**:
- `ttl_hours`: Cache duration (default: 24 hours)

## What's NOT Implemented

- Image analysis
- Claim verification (checking if claims are true/false)
- Credibility scoring
- Multi-language support (only Vietnamese/English)
