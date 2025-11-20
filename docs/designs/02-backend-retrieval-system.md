# Backend: Retrieval System

## What It Is

The Retrieval System finds relevant news articles for a given social media post. It uses a 9-stage pipeline that combines AI understanding with traditional search methods to find the most relevant articles from the database, with multi-signal confidence validation.

## What It Does

Takes a social media post → Returns ranked list of relevant news articles

## The 9 Stages

### Stage 1: Query Extraction
**What happens**: AI extracts clean queries, claims, and entities from the social media post

**Input**: Raw social media post (10-10,000 characters)

**Output**:
```json
{
  "clean_query": "President signs climate bill",
  "claims": ["President signed climate bill", "Climate bill passed"],
  "entities": {
    "persons": ["President"],
    "organizations": ["Congress"],
    "locations": ["Washington DC"],
    "products_topics": [],
    "decision_ids": []
  },
  "query_count": 3,
  "factual_confidence": 3,
  "rationale": "This is a specific policy claim that can be verified..."
}
```

**Implementation Details**:
- Uses OpenAI gpt-4o-mini (configurable via settings)
- Temperature: 0 for deterministic output
- Two-step output: Generates RATIONALE first, then structured JSON
- Max claims extracted: 10 (default, configurable)
- Entity types: `persons`, `organizations`, `locations`, `products_topics`, `decision_ids`
- Factual confidence scale: 1=Opinion/Satire, 2=Vague/Mixed, 3=Highly Verifiable
- Handles Vietnamese text natively:
  - Vietnamese pronouns: "công ty đó" (that company)
  - Causal words: "vì", "do", "nên" (because, due to, so)
  - Temporal phrases: "năm ngoái" (last year), "tháng 6" (June)
  - Location phrases: "tại Hà Nội" (at Hanoi)
  - Normalizes named entities (strips years from event names)
- Fallback on JSON parse error: Uses original post as clean_query with factual_confidence=3

**Early Exit (Gate 1)**: If `factual_confidence < min_factual_confidence` (default 2.0):
- Returns empty articles array
- Sets `exit_reason: "LOW_CONFIDENCE"`
- Effectively blocks score **1** posts (pure opinion/satire). Score **2** (vague) posts are allowed through but often yield fewer claims.
- Skips entire retrieval pipeline for that post

### Stage 2: Embedding Generation
**What happens**: Converts text queries into semantic vectors

**Input**: List of queries from Stage 1:
- 1 clean query
- N claims (0-10 items, capped at 10)
- Total: 1-11 text items depending on extracted claims

**Process**:
1. Batch all queries together in single API call to OpenAI
2. Generate embeddings for each query
3. **Similarity Filter** (enabled by default): Remove redundant claims via cosine similarity against the clean query
4. Return embedding vectors

**Output**: `List[List[float]]` - N vectors of 1536 dimensions each

**Implementation Details**:
- Model: OpenAI `text-embedding-3-small` (1536 dimensions)
- Batch processing: All queries in single API call (not multiple batch calls)
- Redundancy filtering:
  - Calculates cosine similarity between each claim and clean_query
  - Filters claims with similarity > 0.9 (default threshold, configurable)
  - Only compares each claim to clean_query (not inter-claim similarity)
  - **Status**: Implemented and **enabled by default** (`enable_similarity_filter: true`)

**Performance**: Single embedding call for 1-11 queries ~300-600ms total (depending on claim count)

### Stage 3: Hybrid Search
**What happens**: Searches database using vector similarity and keyword matching

**Execution Model**:
- **Per query**: Vector search + BM25 search run **sequentially** per query (not parallel)
- **Reason**: SQLAlchemy AsyncSession doesn't support concurrent operations within same session
- **Result**: For N queries (1 clean + up to 5 claims) → 2N result lists created

**Method A - Vector Search**:
- Compares query embedding (1536-dim vector) with article chunk embeddings
- Similarity metric: Cosine distance (1 - distance = similarity score)
- Finds semantically similar content even if words are different
- **Index**: pgvector IVFFlat (approximate nearest neighbor for speed)
- **Top K**: 100 results per query (default, configurable)
- **No score normalization**: Raw cosine scores (0-1 range)

**Method B - BM25 Keyword Search**:
- Traditional PostgreSQL full-text search with ts_rank_cd (BM25-like ranking)
- Good for exact terms, names, and keywords
- **Vietnamese Processing** (implemented):
  - Uses `pyvi.ViTokenizer` to segment Vietnamese text
  - Converts compound words: "nhà máy xây dựng" → "nhà_máy & xây_dựng"
  - Preserves underscores in tokenized output
  - Uses AND logic for tsquery (all words must match)
  - Removes special characters before search
  - **Enabled by default**: Vietnamese tokenization active
- **Top K**: 100 results per query (default, configurable)

**Combined Result**:
- For single query: 200 total results (100 vector + 100 BM25)
- For N queries: 2N result lists, ~100-200 unique chunks after deduplication

### Stage 4: Reciprocal Rank Fusion (RRF)
**What happens**: Intelligently merges multiple search result lists into single ranked list

**Input**: 2N result lists from Stage 3:
- N vector search results
- N BM25 search results

**Algorithm**:
```
RRF_score(chunk) = sum over all lists: 1 / (k + rank(chunk))
```

Where:
- k = fusion constant (default 60, configurable)
- rank(chunk) = position in list (1-indexed)
- If chunk appears in N lists, scores are summed

**Implementation Details**:
- Rank-based (not score-based), so works with incomparable vector/BM25 scores
- Chunk appearing in multiple lists gets boosted score
- Example: Chunk ranked #1 in vector + #1 in BM25:
  - RRF = 1/61 + 1/61 = 0.0328 (high score)
- Single appearance (e.g., only in vector): RRF = 1/61 = 0.0164 (lower)
- Keeps chunk with best individual score from original search
- Returns fused results sorted by RRF score (descending)

**Output**: ~100-200 unique chunks with RRF scores, ready for reranking

**Why**:
- Vector search excels at semantic meaning but weak at exact terms
- BM25 excels at exact matches but weak at synonyms
- RRF combines strengths without requiring score normalization

### Stage 5: Chunk Reranking
**What happens**: AI scores chunk relevance using parallel workers with entity-based pre-filtering

**Step 1: Entity Filtering** (Pre-reranking optimization):
- Groups chunks by article_id
- Checks if article contains query entities (persons, organizations, locations, etc.)
- Uses case-insensitive substring matching (no word boundaries)
- **Entity match ratio** (default 60% / 0.6):
  - Article must contain at least 60% of extracted entities
  - If matched, includes ALL chunks from that article
  - Filters out articles with <60% entity presence
- **Effect**: Aggressively filters unrelated articles before reranking (still configurable)
- **Status**: **Fully implemented** and **enabled by default**

**Step 2: Parallel Worker Reranking**:
- Takes filtered chunks (typically 50-100 items)
- Distributes round-robin to 4 parallel workers (configurable)
- Each worker handles ~12-25 chunks

**Worker Details**:
- **LLM**: gpt-4o-mini (default, configurable)
- **Timeout**: 15 seconds per worker (default, configurable)
- **Concurrency**: Up to 4 concurrent API calls (rate limited)
- **Scoring**: 0-10 scale with detailed rubric prompt
- **Batch Processing**: JSON mode response from LLM
- **Score Reconstruction**: Uses round-robin indices to map scores back to original chunks

**Scoring Rubric** (0-10 scale):
- 9-10: Perfect match to query topic
- 7-8: Strong relevance
- 5-6: Moderate relevance, mentions entities
- 3-4: Weak relevance
- 0-2: Not relevant

**Score Threshold**: 5.0 minimum (chunks below filtered out)

**Fallback Handling**:
- Worker timeout (7s exceeded): Falls back to original RRF score
- Failed JSON parse: Falls back to RRF score
- Graceful degradation: System continues even with partial worker failures

**Output**: Top 10 chunks sorted by LLM score (descending)

**Key Design Rationale**:
- **Entity filtering**: Reduces computation cost while improving precision
- **Parallel workers**: 4 concurrent calls faster than sequential (7s vs 28s)
- **Round-robin**: Prevents positional bias from vector search ordering
- **Timeout protection**: Ensures predictable tail latency (<10s total)
- **Graceful fallback**: Reliability even with API failures

### Stage 6: Article Aggregation
**What happens**: Groups reranked chunks back into their parent articles

**Input**: Top 10 chunks from Stage 5 with LLM scores (0-10 scale)

**Process**:
1. Groups chunks by article_id
2. Calculates article relevance score = maximum chunk score from that article
3. Filters articles: Only includes if max_score >= 5.0 (configurable min_chunk_score)
4. Fetches article metadata from database:
   - Title, source_name, URL, published_at timestamp
   - Full article content (used by verification pipeline)
5. Includes relevant chunk excerpts (if configured)
6. Sorts articles by relevance_score (descending)
7. Limits to max 10 articles (configurable)

**Output Structure** per article:
```json
{
  "article_id": "uuid",
  "title": "Article Title",
  "source_name": "News Source",
  "published_at": "2025-01-15T10:30:00Z",
  "url": "https://...",
  "relevance_score": 8.5,
  "chunk_count": 3,
  "content": "Full article text for verification pipeline",
  "relevant_chunks": [
    {
      "chunk_id": "uuid",
      "chunk_index": 0,
      "chunk_text": "Article excerpt...",
      "score": 8.5
    }
  ]
}
```

**Key Design Decision**:
- Uses **maximum chunk score** (not sum or average) to avoid:
  - Overscoring articles with many weak chunks
  - Underscoring articles with one strong chunk
  - Dependency on chunk count
- Maximum score better represents "best match within article"

**Performance**: ~20ms (database query + in-memory grouping)

### Stage 7: Article-Level Reranking
**What happens**: AI validates that each article's main topic matches the original query

**Input**: Up to 10 articles from Stage 6

**Early Exit Optimization**:
```python
if len(articles) == 1 and articles[0].relevance_score >= 9.0:
    return articles  # Single high-confidence article, skip reranking
```
- Single article with score ≥ 9.0: Skip reranking, return immediately
- Saves ~150ms for common case (one perfect match)

**Parallel Worker Reranking**:
- Distributes articles to 8 parallel workers (configurable, vs 4 for chunks)
- Each worker handles ~1-2 articles (fewer items = more workers)
- **Timeout**: 5 seconds per worker (faster than chunk workers, simplified prompts)
- **Concurrency**: Up to 8 concurrent API calls
- **Scoring**: 0-10 scale with simplified rubric (faster inference)

**Adaptive Batching Strategy**:
- If articles ≤ 4 items:
  - Send all to single worker for listwise/comparative scoring
  - Enables pairwise comparison (article A vs article B relevance)
  - More accurate but higher token cost
- If articles > 4 items:
  - Distribute round-robin across 8 workers
  - Each worker scores independently
  - Lower cost, suitable for larger sets

**Worker Input**:
- Article title
- Article source name
- Top chunk snippet (200 chars max)
- Original query
- Original post claims

**Scoring Rubric** (0-10 scale):
- 10: Article's main topic exactly matches query/claims
- 9: Almost perfect match
- 7-8: Article discusses query topic substantially
- 5-6: Article mentions query entities but different main topic
- 3-4: Weak relevance to query
- 0-2: Completely different topic

**Score Threshold**: 7.0 minimum (articles below filtered out)

**Performance**: ~150ms (5s timeout × 8 workers in parallel ≈ 150-200ms wall time)

**Why Article-Level Reranking**:
- Prevents false positives where chunks match but article context is different
- Example: Chunk mentions "climate" from movie review; article is about weather
- Validates main topic match at full-article level
- Two-stage approach (chunks then articles) provides fine-grained + coarse-grained validation

### Stage 8: Confidence Scoring
**What happens**: Multi-signal quality assessment of final articles

**Input**: Final article list from Stage 7 (typically 0-10 articles)

**5-Signal Weighting** (overall_confidence = 0-1 scale):
```
overall_confidence = (
  0.35 * top_article_score +       # 35%: Article quality
  0.25 * score_gap_ratio +         # 25%: Distinctiveness
  0.20 * entity_coverage +         # 20%: Completeness
  0.10 * temporal_alignment +      # 10%: Specificity
  0.10 * title_similarity          # 10%: Topicality
)
```

**Signal Details**:

1. **Top Article Score** (35% weight):
   - Normalized from Stage 7 LLM score (0-10 → 0-1)
   - Formula: score / 10.0
   - Indicates raw quality of best match

2. **Score Gap Ratio** (25% weight):
   - Gap between #1 and #2 article scores
   - Formula: (score[0] - score[1]) / score[0] if len ≥ 2, else 1.0 (single article = perfect gap)
   - High gap = clear winner (more confident)
   - Low gap = competing articles (less confident)

3. **Entity Coverage** (20% weight):
   - Percentage of query entities found in top article
   - Case-insensitive substring matching
   - Formula: (# entities found) / (total entities) × 100
   - Default if no entities extracted: 0.5 (neutral)

4. **Temporal Alignment** (10% weight):
   - Boolean: Does article publication date align with query recency?
   - Returns 0.0 or 1.0
   - If query mentions recent dates, article should be recent too
   - Ensures temporal relevance

5. **Title Similarity** (10% weight):
   - Cosine similarity between query embedding and article title embedding
   - Uses OpenAI embeddings (separate call)
   - Range: 0.0-1.0
   - High similarity indicates topic match

**Spatial Alignment** (informational, not weighted):
- Boolean: Does article location match query locations?
- Included in response but not weighted in overall_confidence

**Confidence Tiers**:
- **HIGH**: >= 0.75 (strong multi-signal agreement)
- **MEDIUM**: >= 0.50 (moderate match)
- **LOW**: >= 0.25 (weak match)
- **NONE**: < 0.25 (no relevant articles)

**Output Metrics**:
```json
{
  "overall_confidence": 0.82,
  "confidence_tier": "HIGH",
  "top_article_score": 0.85,
  "score_gap_ratio": 0.45,
  "entity_coverage_ratio": 0.80,
  "temporal_alignment": true,
  "spatial_alignment": true,
  "title_similarity": 0.92,
  "total_qualifying_chunks": 15,
  "article_count": 3
}
```

**Performance**: ~350ms (single embedding call for title similarity + calculation)

### Stage 9: Final Validation Gate
**What happens**: Final quality gate based on confidence scoring

**Gate Decision**:
```python
if overall_confidence < min_confidence_threshold (default 0.25):
    # No relevant articles found
    return {
        "articles": [],
        "early_exit": True,
        "exit_reason": "NO_RELEVANT_ARTICLES",
        "confidence_metrics": confidence_metrics
    }
```

**Two Outcomes**:

1. **Low Confidence (< 0.25)**:
   - Returns empty articles array
   - Sets `exit_reason: "NO_RELEVANT_ARTICLES"`
   - Includes confidence metrics for debugging
   - User sees: "No relevant articles found"

2. **Sufficient Confidence (>= 0.25)**:
   - Returns articles with full metadata
   - Sets `early_exit: False`
   - May include `low_confidence_warning: True` if confidence is LOW or MEDIUM tier
   - User gets results but knows confidence is moderate/low

**Low Confidence Warning**:
```python
low_confidence_warning = (
    confidence_metrics.confidence_tier in ["LOW", "MEDIUM"]
    and len(articles) > 0
)
```
- Signals: Results exist but may not be fully accurate
- Confidence tier is LOW (0.25-0.50) or MEDIUM (0.50-0.75)
- User can make informed decision on result quality

**Why This Gate**:
- Earlier stages optimize for **recall** (find relevant content)
- This gate optimizes for **precision** (reject bad recommendations)
- Better UX: Clear "no results" vs uncertain recommendations
- Prevents false positives that slipped through earlier filters
- Configurable threshold (default 0.25) allows tuning precision/recall trade-off

**Configuration**:
- `min_confidence_threshold`: 0.25 (25%)
- Can be lowered to accept more results with lower confidence
- Can be raised to be stricter

## Vietnamese Language Support

Comprehensive Vietnamese NLP throughout the pipeline:

**Stage 1 - Query Extraction**:
- LLM prompt includes Vietnamese-specific instructions
- Handles Vietnamese pronouns: "công ty đó", "ông ấy" → resolved clearly
- Preserves causal words: "vì", "do", "nên" (because, due to, so)
- Keeps temporal phrases: "năm ngoái" (last year), "tháng 6" (June)
- Keeps location phrases: "tại Hà Nội" (at Hanoi), "ở tỉnh Bắc Ninh"
- Normalizes named entities: "Festival Sông Hồng 2025" → "Festival Sông Hồng"

**Stage 3 - BM25 Search with Vietnamese Tokenization**:
- Library: `pyvi.ViTokenizer` for word segmentation
- Process:
  1. Input: "nhà máy xây dựng công ty" (construction factory company)
  2. Tokenize: "nhà_máy xây_dựng công_ty" (underscores link compound words)
  3. Normalize: Lowercase, remove special characters
  4. Query Logic: " & ".join(tokens) → "nhà_máy & xây_dựng & công_ty"
  5. tsquery: PostgreSQL AND logic (all words must match)
- Benefits:
  - Keeps compound words intact (not split into individual characters)
  - Handles Vietnamese word boundaries correctly
  - Better recall for phrases like "nhà máy" (factory) vs "nhà" (house)
- Enabled by default (vietnamese_tokenization: true)

**Stage 5 - Entity Matching**:
- Case-insensitive substring matching (no word boundaries)
- Example: "Công ty ABC" matches in text "công ty abc"
- Handles Vietnamese names with diacritics

**Stage 8 - Title Similarity**:
- OpenAI embeddings natively handle Vietnamese
- Model: text-embedding-3-small trained on multilingual data
- Works well for Vietnamese text without special preprocessing

**Language Coverage**:
- ✅ Vietnamese: Full support (stages 1, 3, 5, 8)
- ✅ English: Full support
- ⚠️ Other languages: Not tested (embeddings may work, BM25 tokenization won't)

## Performance

**Typical Timing Breakdown** (fresh query, no cache):

| Stage | Time | Notes |
|-------|------|-------|
| Stage 1: Query Extraction | 200-300ms | LLM call (gpt-4o-mini) with JSON response |
| Stage 2: Embedding Generation | 300-600ms | Single batch API call for 1-11 queries (clean query + up to 10 claims) |
| Stage 3: Hybrid Search | 500-1000ms | Sequential vector + BM25 per query (AsyncSession limitation) |
| Stage 4: RRF Fusion | 10-20ms | In-memory rank aggregation |
| Stage 5: Chunk Reranking | 300-500ms | 4 parallel workers × 15s timeout, with fallback |
| Stage 6: Article Aggregation | 15-25ms | Database grouping + metadata fetching |
| Stage 7: Article Reranking | 150-250ms | 8 parallel workers × 5s timeout (simplified prompts) |
| Stage 8: Confidence Scoring | 300-400ms | Title embedding generation + multi-signal calculation |
| Stage 9: Final Validation | <5ms | In-memory threshold check |
| **Total (Fresh)** | **1,600-3,000ms** | Typical: 2,000-2,500ms |
| **With Cache Hit** | **NOT APPLICABLE** | Cache is at API layer; this doc covers retrieval pipeline only |

**Parallelization Benefits**:
- Chunk reranking: 4 workers × 15s timeout → ~500ms wall time (vs ~2,800ms sequential)
- Article reranking: 8 workers × 5s timeout → ~250ms wall time (vs ~2,000ms sequential)
- Total savings: ~2,200ms through parallel execution

**Entity Filtering Impact**:
- Reduces chunks to rerank by 30-50%
- Example: 100 chunks → 50-70 chunks after filtering
- Faster reranking: Fewer chunks to score
- Better quality: Only scores entity-relevant content

**Early Exit Optimizations**:

1. **Stage 1 - Low Factual Confidence**:
   - If factual_confidence < 2.0 (default threshold): Return empty immediately (~200ms)
   - Skips all retrieval stages
   - Threshold is configurable via `min_factual_confidence` setting

2. **Stage 7 - High Confidence Short-Circuit**:
   - Single article with score ≥ 9.0: Skip article reranking
   - Returns immediately after aggregation
   - Saves ~150-250ms

3. **Stage 9 - Confidence Gate**:
   - If overall_confidence < 0.25: Return empty
   - User sees clear "no relevant articles" vs uncertain recommendations

**Caching Behavior**:
- Caching is handled at the API layer, not within the retrieval pipeline
- See backend API documentation for cache implementation details
- This retrieval system always runs the full pipeline when invoked

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

All configurable via `backend/app/config/settings.py` (pulled from environment variables and config.yaml):

### Query Extraction
| Parameter | Default | Description |
|-----------|---------|-------------|
| `enabled` | true | Enable query extraction stage |
| `max_claims` | 10 | Maximum claims to extract (0-10 per post) |
| `min_factual_confidence` | 2.0 | Minimum confidence to proceed (1=opinion, 2=vague, 3=verifiable) |
| `enable_similarity_filter` | true | Filter redundant claims via cosine similarity |
| `similarity_threshold` | 0.90 | Threshold for redundancy detection (0-1 scale) |

### Embedding
| Parameter | Default | Description |
|-----------|---------|-------------|
| `model` | text-embedding-3-small | OpenAI embedding model |
| `dimensions` | 1536 | Vector embedding dimensions |

### Search
| Parameter | Default | Description |
|-----------|---------|-------------|
| `vector_search.enabled` | true | Enable vector search (pgvector) |
| `vector_search.top_k` | 100 | Results per vector search query |
| `vector_search.similarity_metric` | cosine | Distance metric (cosine, l2, inner_product) |
| `bm25_search.enabled` | true | Enable BM25 keyword search |
| `bm25_search.top_k` | 100 | Results per BM25 search query |
| `vietnamese_tokenization.enabled` | true | Use pyvi for Vietnamese word segmentation |
| `fusion.rrf_k` | 60 | RRF fusion constant (controls rank weighting) |

### Chunk Reranking (Stage 5)
| Parameter | Default | Description |
|-----------|---------|-------------|
| `enabled` | true | Enable chunk reranking |
| `num_parallel_workers` | 4 | Concurrent LLM scoring workers |
| `worker_timeout_seconds` | 15.0 | Timeout per worker (seconds) |
| `max_concurrent_calls` | 4 | API concurrency limit |
| `score_threshold` | 5.0 | Minimum score to include (0-10 scale) |
| `top_n` | 10 | Chunks to return after reranking |
| `entity_filter.enabled` | true | Enable entity-based pre-filtering |
| `entity_filter.min_entity_match_ratio` | 0.6 | Min % of entities article must contain (0.6 = 60%) |

### Article Reranking (Stage 7)
| Parameter | Default | Description |
|-----------|---------|-------------|
| `enabled` | true | Enable article-level reranking |
| `num_parallel_workers` | 8 | Concurrent LLM scoring workers |
| `worker_timeout_seconds` | 5.0 | Timeout per worker (seconds) |
| `max_concurrent_calls` | 8 | API concurrency limit |
| `score_threshold` | 7.0 | Minimum article score (0-10 scale) |
| `min_items_for_listwise_scoring` | 4 | Use listwise scoring if ≤4 articles |
| `max_articles_to_rerank` | 15 | Limit articles before reranking |

### Article Aggregation (Stage 6)
| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_articles` | 10 | Maximum articles to return |
| `min_chunk_score` | 5.0 | Minimum article relevance score (0-10) |
| `include_chunks_in_response` | true | Include chunk excerpts in response |

### Confidence Scoring (Stage 8)
| Parameter | Default | Description |
|-----------|---------|-------------|
| `enabled` | true | Enable confidence scoring |
| `min_confidence_threshold` | 0.25 | Confidence gate for final validation |
| `weights.top_article_score` | 0.35 | Weight for article quality |
| `weights.score_gap_ratio` | 0.25 | Weight for distinctiveness |
| `weights.entity_coverage` | 0.20 | Weight for completeness |
| `weights.temporal_alignment` | 0.10 | Weight for temporal relevance |
| `weights.title_similarity` | 0.10 | Weight for title match |
| `thresholds.high` | 0.75 | HIGH confidence tier threshold |
| `thresholds.medium` | 0.50 | MEDIUM confidence tier threshold |
| `thresholds.low` | 0.25 | LOW confidence tier threshold |

### Caching
| Parameter | Default | Description |
|-----------|---------|-------------|
| `enabled` | true | Enable Redis caching |
| `ttl_hours` | 24 | Cache time-to-live (hours) |
| `provider` | redis | Cache backend |

### LLM Models
| Parameter | Default | Description |
|-----------|---------|-------------|
| `query_extraction_model` | gpt-4o-mini | Model for claim extraction (configurable) |
| `reranking_model` | gpt-4o-mini | Model for chunk/article reranking |

## Implementation Status & Deviations from Documentation

### Fully Implemented Features ✅

- ✅ 9-stage retrieval pipeline with all stages functional
- ✅ Query extraction with entity extraction and factual confidence scoring
- ✅ Batch embedding generation with optional redundancy filtering
- ✅ Hybrid search (vector + BM25) with RRF fusion
- ✅ Entity filtering in chunk reranking (enabled by default)
- ✅ Parallel workers for both chunk and article reranking
- ✅ Timeout handling and graceful fallback to RRF scores
- ✅ Article-level reranking with early exit optimization
- ✅ Multi-signal confidence scoring (5 weighted factors)
- ✅ Vietnamese language support (tokenization, entity handling, embeddings)
- ✅ Two early-exit gates (factual confidence + confidence threshold)
- ✅ Redis caching with 24-hour TTL

### Notable Implementation Nuances ⚠️

1. **Hybrid Search Sequencing**:
   - Vector and BM25 searches run sequentially per query because the shared SQLAlchemy AsyncSession cannot handle concurrent statements.
   - Overall latency scales linearly with query_count (though each search remains fast).

2. **Similarity Filtering Scope**:
   - Redundancy filtering compares each claim only to the clean_query embedding.
   - Inter-claim deduplication is not implemented, so near-duplicate claims can still slip through if both differ from the clean query in different ways.

3. **Entity Filtering Strictness**:
   - With the default 60% threshold, queries that extract many entities can aggressively prune articles.
   - Tuning `min_entity_match_ratio` may be necessary for very broad claims.

4. **Title Similarity Cost**:
   - Confidence scoring issues an additional embedding batch (query + title) for every retrieval run.
   - When API budgets are tight, reduce frequency by caching embeddings or disabling the signal.

5. **Sequential Database Access**:
   - Article metadata lookups, vector search, and BM25 search all share the same AsyncSession instance.
   - Scaling beyond a single request relies on FastAPI-level concurrency, not per-request DB parallelism.

### Advanced Features (Undocumented)

- 🎯 **Adaptive Batching** (Stage 7): Uses listwise scoring for ≤4 articles, round-robin for >4
- 🎯 **Score Gap Ratio** (Stage 8): Measures distinctiveness between top articles
- 🎯 **Temporal/Spatial Alignment** (Stage 8): Checks date and location relevance
- 🎯 **Full Article Content**: Included in response for verification pipeline
- 🎯 **Two-Step Query Extraction**: Generates RATIONALE before JSON output

## What's NOT Implemented

- ❌ Image/video analysis
- ❌ Claim verification (NLI-based stance classification is in verification pipeline, not retrieval)
- ❌ Credibility scoring of news sources
- ❌ Multi-language support beyond Vietnamese/English
- ❌ Query deduplication across claims (redundant queries hit database)
- ❌ Stemming/lemmatization (only word tokenization for Vietnamese)
