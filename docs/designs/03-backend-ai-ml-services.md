# Backend: AI/ML Services

## What It Is

The AI/ML Services provide intelligent processing using OpenAI's models. These services power the "understanding" parts of the retrieval system.

## What's Implemented

### 1. Embedding Service

**What it does**: Converts text into 1536-dimensional semantic vectors

**How it works**:
- Takes text (query or article chunk)
- Calls OpenAI API (text-embedding-3-small model, default)
- Returns a vector (array of 1536 floating-point numbers)
- Vectors capture semantic meaning for similarity comparison

**Implementation** (`app/services/content/embedding_service.py`):

```python
# Synchronous API (backward compatible)
embedding = generate_embedding(text: str) -> List[float]

# Asynchronous API (recommended for pipeline)
embeddings = await generate_embeddings_batch(texts: List[str]) -> List[List[float]]

# Utility function
dimensions = get_embedding_dimensions()  # Returns 1536
```

**Features**:
- **Batch Processing**: All texts in single API call (more efficient)
- **Async Support**: Non-blocking for pipeline integration
- **Error Handling**: 3-attempt retry with exponential backoff (2-10s)
- **Fallback**: Synchronous wrapper using `asyncio.run()` for backward compatibility

**Retry Logic**:
- Max attempts: 3
- Backoff: Exponential (2s, 4-10s, 8-20s)
- Catches: All exceptions
- Reraises: After 3 failures

**When it's used**:
- During article ingestion (embed all chunks for pgvector index)
- During hybrid search (embed query claims for vector search)
- During confidence scoring (embed article titles for title similarity)

**Token Cost**:
- Approximately 1 token per 4 characters
- ~25 tokens per 100-char chunk
- Typical embedding batch (6 queries): ~150 tokens ($0.00015 at current rates)

### 2. Query Extraction Service

**What it does**: Extracts clean queries, specific claims, and entities from social media posts

**How it works**:
- Takes messy post with emojis, hashtags, Vietnamese text, etc.
- **Step 1**: LLM generates RATIONALE (chain-of-thought reasoning)
- **Step 2**: LLM outputs structured JSON with:
  - **Clean query**: Main topic (1-2 sentences), cleaned of noise
  - **Claims**: List of verifiable statements (default max: 10)
  - **Entities**: Extracted and grouped by type (5 types total)
  - **Factual Confidence**: Score (1-3) indicating if post is verifiable

**Entity Types Extracted** (5 categories):
- `persons`: Named individuals (requires title/role for identification)
- `organizations`: Companies, government agencies, institutions
- `locations`: Geographic places, regions, countries
- `products_topics`: Brand names, products, medical/scientific terms
- `decision_ids`: Official decision numbers (e.g., "628/QĐ-QLD")

**Entity Normalization Rules**:
- Remove years from recurring events: "Festival Tết 2025" → "Festival Tết"
- Strip legal suffixes: "Công ty VinFast Chi nhánh Hà Nội" → "VinFast"
- Preserve version numbers: "iPhone 15" kept as-is

**Example**:
```
Input: "🚨 BREAKING: PM Phạm Minh Chính announces new tax policy! #Politics #Vietnam"

Output:
{
  "clean_query": "Prime Minister announces new tax policy",
  "claims": ["Prime Minister announced new tax policy"],
  "entities": {
    "persons": ["Phạm Minh Chính"],
    "locations": ["Vietnam"],
    "organizations": [],
    "products_topics": ["tax policy"],
    "decision_ids": []
  },
  "query_count": 2,
  "factual_confidence": 3,
  "rationale": "This is a specific news claim with person, location, and policy details..."
}
```

**Implementation Details**:

**LLM Configuration**:
- Model: GPT-4o-mini (configurable to gpt-4o, claude-3-5-sonnet, etc.)
- Temperature: 0 (deterministic output)
- Response Format: JSON mode (strict validation)
- Max Tokens: 2,000

**Prompt Structure** (~1,200 tokens):
- Detailed instructions for Vietnamese language handling
- Entity extraction guidelines
- Factual confidence calibration examples
- Vietnamese-specific examples (pronouns, causal words, dates)

**Two-Step LLM Process**:
1. **RATIONALE Step**: LLM explains its reasoning before JSON
   - Helps improve accuracy through chain-of-thought
   - Prevents "lazy" LLM outputs
2. **JSON Step**: Structured output parsed and returned

**Factual Confidence Scale** (1-3):
- **1 (Opinion/Satire)**: Pure opinion, humor, or satirical content
  - No verifiable claims
  - No specific entities/dates/numbers
- **2 (Vague/Mixed)**: Mix of fact and opinion
  - Contains some specific details but vague
  - Includes hearsay ("supposedly", "allegedly", "some say")
- **3 (High-Verifiable)**: Specific, objective claims
  - Named entities, specific dates, numbers
  - Testable against news sources

**Error Handling**:
- **JSON Parse Failure**: Falls back to original post as clean_query, confidence=3
- **Missing Keys**: Uses sensible defaults (empty arrays, neutral confidence)
- **Invalid Confidence**: Normalizes to 1-3 range
- **Logs**: All errors logged for debugging

**Token Cost**:
- Prompt: ~1,200 tokens (detailed instructions)
- Response: ~300-500 tokens (rationale + JSON)
- **Total per extraction**: ~1,500-1,700 tokens
- **Cost**: ~$0.001-0.002 per request

### 3. Chunk Reranking Service

**What it does**: LLM-based relevance scoring for article chunks

**Input**:
- Original post + extracted claims/entities
- Top ~100 fused chunks from hybrid search + RRF (before filtering)

**Output**: Top 10 chunks with scores 0-10 (threshold ≥ 5.0)

**How it works**:

**Step 1: Entity-Based Pre-Filtering** (optional, enabled by default):
- Groups chunks by article_id
- Checks if article contains query entities (persons, organizations, locations, products/topics, decision IDs)
- Entity matching: Case-insensitive substring (Vietnamese-compatible)
- **Entity match ratio** (default 60% / 0.6): Article must contain ≥60% of query entities
- **Effect**: Reduces ~100 fused chunks → 40-70 chunks on average
- **Benefit**: Faster reranking + higher quality (focuses on entity-relevant content)

**Step 2: Parallel Worker Scoring**:

**Configuration**:
- **Num Workers**: 4 concurrent workers
- **Timeout**: 15 seconds per worker (default, configurable)
- **Concurrency Limit**: 4 max concurrent API calls (rate limited)
- **Batch Strategy**: Round-robin distribution

**Round-Robin Distribution**:
```python
# For 100 chunks, 4 workers:
Worker 0: [chunk_0, chunk_4, chunk_8, ...]   # 25 chunks
Worker 1: [chunk_1, chunk_5, chunk_9, ...]   # 25 chunks
Worker 2: [chunk_2, chunk_6, chunk_10, ...]  # 25 chunks
Worker 3: [chunk_3, chunk_7, chunk_11, ...]  # 25 chunks
```
- **Purpose**: Mix of high/medium/low scores (prevents positional bias)
- **Benefit**: Parallel execution reduces latency

**Scoring Process**:
- **LLM Model**: gpt-4o-mini (configurable)
- **Prompt**: ~300 tokens
- **Response Format**: JSON with chunk IDs and scores
- **Scale**: 0-10 points

**Scoring Rubric** (0-10 scale):
- **9-10**: Perfect match - exact claim/event with all details
- **7-8**: Excellent - same event/topic with most details
- **5-6**: Good - moderate relevance, mentions query entities
- **3-4**: Weak - mentions some entities but limited overlap
- **0-2**: Not relevant - completely different topic

**Score Threshold**: 5.0 minimum (chunks below filtered out)

**Error Handling**:
- **Worker Timeout** (>15s): Falls back to original RRF score
- **JSON Parse Failure**: Falls back to RRF score
- **Partial Failures**: System continues with remaining worker results
- **Graceful Degradation**: Returns best-effort results even with timeouts

**Output**: Top 10 chunks (configurable) sorted by LLM score

**Why it's needed**:
- Vector/keyword search isn't perfect (many false positives)
- LLM understands context, nuance, and semantic relevance better
- Pre-filters ensure only entity-relevant content is scored (cost efficient)

**Token Cost**:
- Input chunks: ~400 tokens (prompt + chunk snippets)
- Response: ~100 tokens (JSON with scores)
- 4 workers × 500 tokens = 2,000 tokens total
- **Cost**: ~$0.002-0.003 per request

### 4. Article-Level Reranking Service

**What it does**: Validates that full article's main topic matches the original query

**Input**: 5-10 aggregated articles (from aggregation service)

**Output**: Top 10 articles with scores ≥ 7.0

**How it works**:

**Early Exit Optimization**:
```python
if len(articles) == 1 and articles[0].score >= 9.0:
    return articles  # Single perfect article, skip reranking
```
- Single article with score ≥ 9.0 → return immediately
- **Savings**: ~150-200ms per request

**Adaptive Batching Strategy**:
- **≤ 4 articles**: Send all to ONE worker for **listwise scoring**
  - LLM can compare articles directly
  - More accurate (pairwise comparison)
  - Higher token cost (~1,000 tokens)
- **> 4 articles**: Distribute across workers with **round-robin batching**
  - Each worker scores independently
  - Lower cost (~300 tokens each)

**Worker Configuration**:
- **Num Workers**: 8 (vs 4 for chunks - more workers for fewer items)
- **Timeout**: 5 seconds per worker (faster than chunk workers)
- **Concurrency Limit**: 8 max concurrent API calls
- **LLM Model**: gpt-4o-mini

**Scoring Process**:
- **Input**: Article title + source + top chunk snippet (200 chars max) + original query
- **Prompt**: ~300 tokens (simplified vs 1,200 for chunks)
- **Response Format**: JSON with article IDs and scores
- **Scale**: 0-10 points (strict interpretation)

**Scoring Rubric** (0-10 scale):
- **10**: EXACT match - article's main topic = exact same event as query
- **7-9**: STRONG match - article discusses query topic substantially
- **5-6**: WEAK MATCH - mentions query entities but DIFFERENT main topic
- **0-4**: COMPLETELY WRONG - different event, time, location, or topic

**Critical Rule**: Different event with same entities = 0-4, NOT 5+
- Same names ≠ same event
- Different dates = different events
- Different locations = different events
- Must be about the SAME occurrence

**Score Threshold**: 7.0 minimum (articles below filtered out)
- Higher threshold than chunk reranking (7.0 vs 5.0)
- Ensures full article relevance, not just snippet match

**Error Handling**:
- **Worker Timeout** (>5s): Skip article (score = 0.0)
- **JSON Parse Failure**: Skip article
- **Partial Failures**: Return results from successful workers
- **Logged**: All timeouts/errors logged as warnings

**Output**: Top 10 articles (configurable) sorted by score

**Why it's needed**:
- Chunks might match keywords, but article could be about different event
- **Example**:
  - Query: "Apple releases iPhone 15"
  - Chunk: "Steve Jobs died in 2011" (mentions Apple, but different event)
  - Chunk score: 4/10 (weak match)
  - Article reranking: 0/10 (Steve Jobs article ≠ iPhone article)
- Validates semantic relevance at full article level
- Two-stage reranking (chunks → articles) provides both fine-grained + coarse-grained filtering

**Token Cost**:
- Small batch (≤4 articles): ~1,000 tokens (listwise)
- Large batch (>4 articles): ~300 tokens per worker × 8 = 2,400 tokens
- **Cost**: ~$0.0005-0.003 per request

### 5. Confidence Scoring Service

**What it does**: Multi-signal quality assessment of retrieved articles

**Input**: Final article list (0-10 articles from article reranking)

**Output**:
```json
{
  "overall_confidence": 0.82,
  "confidence_tier": "HIGH",
  "top_article_score": 0.85,
  "score_gap_ratio": 0.45,
  "entity_coverage_ratio": 0.80,
  "temporal_alignment": true,
  "spatial_alignment": true,
  "title_similarity": 0.92
}
```

**5-Signal Confidence Calculation**:

```python
overall_confidence = (
    0.35 * top_article_score +      # 35%: Article quality
    0.25 * score_gap_ratio +        # 25%: Distinctiveness
    0.20 * entity_coverage +        # 20%: Completeness
    0.10 * temporal_alignment +     # 10%: Specificity
    0.10 * title_similarity         # 10%: Topicality
)
```

**Signal Details**:

**Signal 1: Top Article Score** (35% weight):
- Normalized from article reranking score (0-10 → 0-1)
- Formula: `score / 10.0`
- Measures raw quality of best article match

**Signal 2: Score Gap Ratio** (25% weight):
- Gap between #1 and #2 article scores
- Formula: `(score[0] - score[1]) / score[0]` if len ≥ 2, else 1.0
- Range: 0.0-1.0
- **High gap** (0.8-1.0): Clear winner (confident)
- **Low gap** (0.0-0.3): Competing articles (uncertain)
- Measures distinctiveness of top result

**Signal 3: Entity Coverage** (20% weight):
- Percentage of query entities found in top article
- Case-insensitive substring matching (Vietnamese-compatible)
- Formula: `(# matched entities) / (total query entities)`
- Range: 0.0-1.0
- **Default if no entities**: 0.5 (neutral)
- Measures completeness of entity mention

**Signal 4: Temporal Alignment** (10% weight):
- Boolean: Does article contain query date entities?
- Returns 1.0 if match, 0.0 if not
- Example: Query mentions "January 2025" → article date must be ~January 2025
- Measures temporal specificity

**Signal 5: Title Similarity** (10% weight):
- Cosine similarity between query embedding + article title embedding
- Requires 2 additional embedding API calls
- Formula: `cosine_similarity(query_emb, title_emb)`
- Range: 0.0-1.0
- Measures topical match at article level

**Bonus Signal (Informational, not weighted)**:

**Spatial Alignment** (not weighted):
- Boolean: Does article location match query locations?
- Included in response for debugging
- Contributes indirectly via entity coverage

**Confidence Tiers**:

```python
if confidence >= 0.75:
    tier = "HIGH"        # Strong multi-signal agreement
elif confidence >= 0.50:
    tier = "MEDIUM"      # Moderate match
elif confidence >= 0.25:
    tier = "LOW"         # Weak match
else:
    tier = "NONE"        # No relevant articles
```

**Final Validation Gate**:
- If `overall_confidence < 0.25` (NONE tier): Return empty articles
- If `0.25 ≤ confidence < 0.75` (LOW/MEDIUM): Include `low_confidence_warning: true`
- If `confidence ≥ 0.75` (HIGH): Return articles with confidence

**Why it's needed**:
- Single score can be misleading (high LLM score on wrong topic)
- Multi-signal catches failures:
  - No competing articles → high gap, but score low → detected
  - Few entities → low entity coverage → detected
  - Recent post, old article → temporal misalignment → detected
  - Entity match but different topic → low title similarity → detected
- Prevents showing bad recommendations for fake stories or very new events

**Token Cost**:
- Query embedding: ~1 token per 4 chars
- Title embeddings: 6 titles × 50 tokens = 300 tokens
- Calculation: ~10 tokens (negligible)
- **Total**: ~350 tokens
- **Cost**: ~$0.00035 per request

### 6. Vietnamese Text Processor

**What it does**: Vietnamese word tokenization for BM25 keyword search

**How it works**:

**Step 1: Word Segmentation**:
- Uses `pyvi.ViTokenizer` library (specialized for Vietnamese)
- Detects compound words: "công ty" (company) → "công_ty"
- Preserves diacritical marks: "Hà Nội", "Việt Nam"
- Handles Vietnamese text naturally

**Step 2: Query Preparation for BM25**:
```python
# Input: "nhà máy xây dựng công ty"
# After tokenization: "nhà_máy xây_dựng công_ty"
# After sanitization: "nhà_máy xây_dựng công_ty" (remove special chars)
# After formatting: "nhà_máy & xây_dựng & công_ty"
# For PostgreSQL: to_tsquery('simple', 'nhà_máy & xây_dựng & công_ty')
```

**Configuration**:
- **Enabled by default**: `vietnamese_tokenization.enabled: true`
- **Library**: `pyvi` (standard for Vietnamese NLP)

**Why it's needed**:
- Vietnamese doesn't use spaces between all words (morphologically agglutinative)
- "Nhà máy" (factory) should stay together, not split into "nhà" + "máy"
- Without tokenization:
  - "nhà máy xây dựng" → searches for each word separately
  - May find articles about just "nhà" (house) or "máy" (machine)
  - Low precision, many false positives
- With tokenization:
  - "nhà_máy" → specific compound word
  - Better recall and precision for Vietnamese text

**Token Cost**: Negligible (pure Python processing, no API calls)

### 7. Stance Classifier Service (Verification Pipeline)

**What it does**: Classifies whether articles support, refute, or don't provide enough info for claims

**Input**: Claim-article pairs (5 claims × 10 articles = 50 pairs max)

**Output**: Stance results with evidence spans
```python
{
    "stance": "SUPPORTS",  # or REFUTES, NOT_ENOUGH_INFO
    "confidence": 0.92,
    "evidence_spans": [
        {"text": "...", "reasoning": "..."}
    ],
    "overall_reasoning": "..."
}
```

**How it works**:

**LLM Configuration**:
- Model: gpt-4o-mini (configurable)
- Task: Natural Language Inference (NLI)
- Prompt: ~1,000 tokens per pair
- Language: Vietnamese (instructions in Vietnamese)

**Parallel Processing**:
- **Num Workers**: 4 concurrent workers
- **Timeout**: 10 seconds per worker
- **Batch Strategy**: Round-robin distribution
- **Concurrency Limit**: 4 max concurrent API calls

**Classification Output**:
- **SUPPORTS**: Article directly supports the claim
- **REFUTES**: Article contradicts/refutes the claim
- **NOT_ENOUGH_INFO**: Article doesn't provide sufficient evidence

**Evidence Extraction**:
- Direct quotes from article supporting/refuting claim
- Reasoning explaining why quote is relevant
- Confidence score (0-1) on stance classification

**Error Handling**:
- **Worker Timeout** (>10s): Return default `NOT_ENOUGH_INFO`
- **JSON Parse Failure**: Return default `NOT_ENOUGH_INFO`
- **Logged**: All failures logged as warnings

**Token Cost**:
- Input: ~1,000 tokens per claim-article pair
- 50 pairs × 1,000 tokens = ~50,000 tokens
- **Cost**: ~$0.01-0.02 per verification request

### 8. Explanation Generator Service (Verification Pipeline)

**What it does**: Generates human-readable Vietnamese explanation of verification results

**Input**:
- Overall verdict (FULLY_SUPPORTED, PARTIALLY_SUPPORTED, REFUTED, NOT_ENOUGH_INFO)
- Original post text
- Claim verdicts with evidence counts
- Supporting/refuting article count

**Output**: Vietnamese explanation (max 500 characters)

**How it works**:

**Processing Modes**:

1. **Rule-Based Mode** (Simple cases):
   - No articles found → "Không tìm thấy bài viết liên quan"
   - No claims extracted → "Không tìm thấy tuyên bố có thể xác minh"
   - All claims supported → "Hoàn toàn chính xác"

2. **LLM Mode** (Complex cases):
   - Uses gpt-4o-mini with temperature 0.3 (slight creativity)
   - Prompt: "Generate a concise Vietnamese explanation of this verdict..."
   - Max tokens: 150
   - Ensures natural, readable output

3. **Fallback Mode** (LLM failure):
   - Returns rule-based explanation
   - Logged as warning

**Verdict Mapping** (Vietnamese):
```python
{
    "FULLY_SUPPORTED": "HOÀN TOÀN CHÍNH XÁC",
    "PARTIALLY_SUPPORTED": "ĐÚNG MỘT PHẦN",
    "REFUTED": "SAI SỰ THẬT",
    "NOT_ENOUGH_INFO": "CHƯA ĐỦ BẰNG CHỨNG"
}
```

**Example Outputs**:
```
Input: FULLY_SUPPORTED, 3/3 claims supported, 5 sources
Output: "Cả 3 tuyên bố đều được xác nhận bởi 5 nguồn tin đáng tin cậy. Thông tin này là chính xác."

Input: PARTIALLY_SUPPORTED, 2/3 claims supported
Output: "2 trong 3 tuyên bố được xác nhận. Tuyên bố thứ 3 chưa có đủ bằng chứng từ các nguồn tin."

Input: REFUTED, 0/3 claims supported
Output: "Thông tin này không chính xác. Tất cả tuyên bố đều mâu thuẫn với các nguồn tin đáng tin cậy."
```

**Token Cost**:
- Rule-based: ~0 tokens (pure logic)
- LLM-based: ~400 tokens (prompt + response)
- **Cost**: ~$0.0005 per explanation

---

## AI Provider Abstraction

The code has a base `AIProvider` class that can work with different providers:
- **OpenAIProvider**: Currently implemented (handles both Embeddings and LLM)
- Future: Could add Anthropic, local models, etc.

This makes it easy to switch or add alternative AI providers via `config.yaml`.

## Cost Management

### Token Breakdown per Verification Request

**Retrieval Pipeline**:

| Stage | Tokens | Cost (USD) |
|-------|--------|-----------|
| Query Extraction | 1,500 | 0.001-0.002 |
| Embedding (6 queries) | 150 | 0.00015 |
| Chunk Reranking (4 workers) | 2,000 | 0.002-0.003 |
| Article Reranking (8 workers) | 2,400 | 0.0005-0.003 |
| Confidence Scoring (embeddings) | 350 | 0.00035 |
| **Retrieval Total** | **6,400** | **$0.005-0.009** |

**Verification Pipeline** (if articles found):

| Stage | Tokens | Cost (USD) |
|-------|--------|-----------|
| Stance Classification (50 pairs) | 50,000 | 0.01-0.02 |
| Explanation Generation | 400 | 0.0005 |
| **Verification Total** | **50,400** | **$0.011-0.021** |

**Overall Cost per Verification**:
- **Typical Request**: ~29,500 tokens = **$0.015-0.027**
- **At 100 requests/day**: $1.50-2.70/day = **$45-81/month**
- **At 1,000 requests/day**: $15-27/day = **$450-810/month**

**With Caching** (Redis):
- **Cache hit**: Skips retrieval pipeline only; verification still runs (~1-2 seconds total)
- **Cache TTL**: 24 hours
- **Expected cache hit rate**: 20-40% (repeated queries from same users)
- **Monthly savings**: Partial reduction in API costs (verification still incurs LLM costs)

### Cost Optimization Strategies

1. **Entity Filtering** (Chunk Reranking): Reduces chunks to score by 30-50%
2. **Parallel Workers**: Distributes load efficiently
3. **Early Exit Optimization** (Article Reranking): Skips scoring if single high-confidence article
4. **Score Thresholds**: Stops processing low-confidence results early
5. **Redis Caching**: Completely eliminates costs for repeated queries

## Implementation Status & Deviations from Documentation

### Fully Implemented Services ✅

- ✅ Embedding Service (with batch processing and retries)
- ✅ Query Extraction Service (two-step prompt, entity extraction)
- ✅ Chunk Reranking Service (parallel workers, entity filtering)
- ✅ Article-Level Reranking Service (adaptive batching, early exit)
- ✅ Confidence Scoring Service (5-signal calculation with title similarity)
- ✅ Stance Classifier Service (NLI-based verification)
- ✅ Explanation Generator Service (Vietnamese explanations)
- ✅ Vietnamese Text Processor (pyvi integration)
- ✅ AI Provider Abstraction (factory pattern, singleton caching)

### Undocumented Features ✨

- 🎯 **Two-Step Query Extraction Prompt**: RATIONALE step before JSON
- 🎯 **Entity Normalization**: Strips years from events, legal suffixes
- 🎯 **Explanation Generator Service**: Rule-based + LLM modes
- 🎯 **Early Exit Optimization**: Article reranking skips if score ≥ 9.0
- 🎯 **Adaptive Batching**: Article reranking listwise vs pairwise
- 🎯 **Error Handling**: Comprehensive timeout + fallback mechanisms
- 🎯 **Vietnamese-Specific Prompt Instructions**: Detailed guidelines in query extraction

### Provider Abstraction Details

**Supported Providers**:
- ✅ **OpenAI** (fully implemented)
- ⚠️ **Anthropic** (defined in factory, raises NotImplementedError)
- ⚠️ **Local** (defined in factory, raises NotImplementedError)

**Singleton Caching**: Provider instances cached in `_instances` dict for efficiency

## Configuration

### AI Configuration

```yaml
ai:
  provider: "openai"                    # openai, anthropic, local
  embedding_model: "text-embedding-3-small"
  llm_model: "gpt-4o-mini"             # gpt-4o, gpt-4-turbo, etc.
  max_retries: 3                        # Retry attempts
  timeout_seconds: 30                   # API timeout
```

### Retrieval Pipeline Configuration

```yaml
retrieval:
  query_extraction:
    enabled: true
    max_claims: 10                      # Default (was 8 in docs)
    min_factual_confidence: 2           # 1-3 scale (1=opinion, 3=verifiable)
    enable_similarity_filter: true
    similarity_threshold: 0.9

  reranking:
    enabled: true
    top_n: 10
    num_parallel_workers: 4             # Chunks
    worker_timeout_seconds: 15
    max_concurrent_calls: 4
    score_threshold: 5
    entity_filter:
      enabled: true
      min_entity_match_ratio: 0.6       # 60% entity coverage requirement
    article_level:
      enabled: true
      num_parallel_workers: 8
      worker_timeout_seconds: 5
      max_concurrent_calls: 8
      score_threshold: 7.0
      min_items_for_listwise_scoring: 4

  confidence_scoring:
    enabled: true
    min_confidence_threshold: 0.25
    weights:
      top_article_score: 0.35
      score_gap_ratio: 0.25
      entity_coverage: 0.20
      temporal_alignment: 0.10
      title_similarity: 0.10             # Requires 2 embedding calls
```

### Verification Pipeline Configuration

```yaml
verification:
  enabled: true
  stance_classification:
    num_parallel_workers: 4
    worker_timeout_seconds: 10
    min_confidence: 0.6
  explanation:
    language: "vi"
    max_length: 500
```

## What's NOT Implemented

- ❌ Image/video analysis (AI-generated image detection)
- ❌ Source Credibility scoring (source-level reliability ranking)
- ❌ Anthropic Provider (partially defined, not implemented)
- ❌ Local Model deployment
- ❌ Other language support (Vietnamese/English only)
