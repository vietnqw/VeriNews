# Backend: Retrieval System

## Overview

The Retrieval System is the core intelligence of VeriNews, responsible for finding relevant trusted news articles that match or relate to social media posts being verified. It uses a sophisticated hybrid search approach combining semantic understanding (vector search) and keyword matching (BM25) to maximize both precision and recall.

## Purpose

Find the most relevant trusted news articles for a given social media post by:
- Understanding the semantic meaning of posts beyond keywords
- Matching specific terminology and named entities
- Ranking results by relevance and recency
- Handling multiple languages (especially Vietnamese)
- Returning results quickly (< 2 seconds)

## Key Responsibilities

1. **Query Understanding**
   - Extract clean, searchable queries from noisy social media posts
   - Identify and extract factual claims that can be verified
   - Handle hashtags, mentions, emojis, and informal language
   - Normalize text for better matching

2. **Hybrid Search Execution**
   - Perform semantic search using vector embeddings
   - Execute keyword-based search using BM25
   - Run multiple query variations in parallel
   - Handle Vietnamese compound words and diacritics

3. **Result Fusion**
   - Combine results from vector and keyword searches
   - Apply Reciprocal Rank Fusion (RRF) algorithm
   - Balance precision and diversity
   - Avoid duplicate or near-duplicate results

4. **Relevance Reranking**
   - Use AI to score relevance of each result
   - Consider contextual factors (recency, source credibility)
   - Filter out low-relevance matches
   - Prioritize high-quality sources

5. **Result Aggregation**
   - Group article chunks back into full articles
   - Calculate article-level relevance scores
   - Include relevant excerpts from articles
   - Limit to top N most relevant articles

## Retrieval Pipeline

The retrieval process consists of **6 sequential stages**:

### Stage 1: Query Extraction

**Purpose**: Transform raw social media post into structured search queries

**Process**:
1. **Clean Query Generation**
   - Remove emojis, hashtags, mentions
   - Fix grammar and spelling where needed
   - Extract core information-seeking query
   - Keep 1-2 sentence summary

2. **Claim Extraction**
   - Identify distinct factual claims
   - Each claim is a separate searchable statement
   - Remove opinions and subjective statements
   - Extract up to 5 key claims

**Input**:
```
"🚨 Breaking: President announces new policy on climate!
#ClimateChange #Politics Everyone needs to know this!"
```

**Output**:
```
{
  "clean_query": "President announces new climate policy",
  "claims": [
    "President announced new climate policy",
    "New policy relates to climate change"
  ]
}
```

**Implementation Details**:
- Use LLM (GPT-4) for intelligent extraction
- Provide examples in prompts for consistency
- Fallback to simple text cleaning if LLM fails
- Cache common query patterns

### Stage 2: Embedding Generation

**Purpose**: Convert text queries into dense vector representations

**Process**:
1. Take clean query + claims (multiple queries)
2. Generate embeddings for each using OpenAI API
3. Batch requests for efficiency (up to 100 at once)
4. Normalize vectors to unit length

**Technical Details**:
- Model: text-embedding-3-small (1536 dimensions)
- Batch size: 5-10 queries per API call
- Caching: Store embeddings for common queries
- Fallback: Use simpler model if primary fails

**Output**: Array of 1536-dimensional vectors

### Stage 3: Hybrid Search

**Purpose**: Find candidate articles using both semantic and keyword approaches

**Sub-Process 3A: Vector Search**
- Query pgvector database for similar embeddings
- Use cosine similarity metric
- Leverage IVFFlat index for fast approximate nearest neighbor search
- Return top K chunks (default K=50) per query
- Include similarity scores (0-1 range)

**Sub-Process 3B: BM25 Keyword Search**
- Query PostgreSQL full-text search
- Use custom Vietnamese tokenizer for compound words
- Apply BM25 ranking algorithm (considers term frequency, document length)
- Return top K chunks (default K=50) per query
- Include relevance scores

**Parallel Execution**:
- Both searches run simultaneously for each query
- Total queries: 1 clean query + N claims = (N+1) queries
- Total result lists: 2 × (N+1) lists

**Example**:
- Clean query → Vector results + BM25 results
- Claim 1 → Vector results + BM25 results
- Claim 2 → Vector results + BM25 results
- **Total**: 6 result lists (if 2 claims)

### Stage 4: Reciprocal Rank Fusion (RRF)

**Purpose**: Intelligently combine multiple ranked lists into one unified ranking

**Algorithm**:
```
For each chunk appearing in any result list:
  score = 0
  For each list where chunk appears:
    rank = position in that list (1, 2, 3, ...)
    score += 1 / (k + rank)

  # k is a constant (typically 60)
  # Lower rank (better position) = higher score
```

**Benefits**:
- Rewards chunks that appear in multiple result lists
- Handles different scoring scales (vector vs. BM25)
- Prioritizes top results without ignoring lower ranks
- No manual weight tuning required

**Configuration**:
- k parameter: 60 (standard value from research)
- Customizable per deployment

**Output**: Single ranked list of ~100-200 unique chunks

### Stage 5: Reranking

**Purpose**: Apply AI-powered relevance scoring for final ranking

**Process**:
1. Take top 100 chunks from fusion results
2. Batch chunks (5-10 per API call) with original post
3. Ask LLM to score relevance (0-10 scale)
4. Normalize scores to 0-1 range
5. Re-sort by new scores
6. Keep top 50 most relevant

**Prompt Strategy**:
```
Given this social media post:
"{post_text}"

Rate the relevance of this article excerpt:
"{chunk_text}"

Score 0-10 where:
- 10: Directly addresses the exact topic/claim
- 7-9: Highly relevant, discusses related aspects
- 4-6: Somewhat relevant, tangential information
- 1-3: Barely relevant, mentions topic in passing
- 0: Not relevant at all

Return only the numeric score.
```

**Benefits**:
- Considers semantic relevance beyond keyword matching
- Understands context and nuance
- Identifies contradictory vs. supporting information
- Handles complex reasoning

**Optimization**:
- Batch processing reduces API calls
- Parallel requests for speed
- Caching for repeated content
- Fallback to fusion scores if LLM fails

### Stage 6: Article Aggregation

**Purpose**: Group ranked chunks back into complete articles with metadata

**Process**:
1. **Chunk-to-Article Mapping**
   - Each chunk has an article_id
   - Group all chunks by article_id
   - Preserve chunk scores

2. **Article-Level Scoring**
   - Sum scores of all chunks from same article
   - OR take max chunk score (configurable)
   - Articles with more matching chunks rank higher

3. **Filtering**
   - Remove articles below relevance threshold (e.g., score < 0.3)
   - Limit to top N articles (default N=10)
   - Ensure diversity (avoid multiple articles from same source)

4. **Enrichment**
   - Include article metadata (title, author, date, source)
   - Include relevant chunk excerpts
   - Calculate confidence score
   - Add source credibility indicators

**Output Structure**:
```
{
  "articles": [
    {
      "article_id": "uuid",
      "title": "Article title",
      "source": "BBC News",
      "published_date": "2024-01-15",
      "url": "https://...",
      "relevance_score": 0.92,
      "matching_chunks": [
        {
          "text": "Relevant excerpt...",
          "score": 0.85,
          "position": 2
        }
      ],
      "claim_support": {
        "claim_1": "supports",
        "claim_2": "neutral"
      }
    }
  ],
  "processing_stages": {
    "query_extraction": "45ms",
    "embedding_generation": "120ms",
    "hybrid_search": "85ms",
    "fusion": "15ms",
    "reranking": "650ms",
    "aggregation": "20ms",
    "total": "935ms"
  }
}
```

## Vietnamese Language Support

### Challenges
- Compound words that should stay together: "công ty" (company), "Việt Nam" (Vietnam)
- Diacritical marks affect meaning: "ma" (ghost) vs "mà" (but) vs "má" (mother)
- Word boundaries not explicit like English
- Mixed Vietnamese-English content common

### Solutions

**Vietnamese Tokenizer**:
- Custom tokenization preserving compound words
- Dictionary of common Vietnamese compounds
- Join multi-word entities with underscore: công_ty
- Preserve diacritics for matching

**Search Strategies**:
- Diacritic-sensitive matching (exact)
- Diacritic-insensitive fallback (approximate)
- Both tokenized and raw text indexing
- Configure in BM25 search

**Embedding Handling**:
- OpenAI embeddings handle Vietnamese well
- Preserves semantic meaning despite tokenization differences
- No special preprocessing needed for vector search

## Performance Optimization

### Latency Breakdown (Target)
- Query extraction: < 100ms (LLM call)
- Embedding generation: < 200ms (API call, batched)
- Vector search: < 50ms per query (pgvector)
- BM25 search: < 30ms per query (PostgreSQL FTS)
- Fusion: < 20ms (in-memory computation)
- Reranking: < 500ms (LLM calls, batched)
- Aggregation: < 50ms (database queries + computation)
- **Total**: < 1 second (with caching)

### Optimization Techniques

**Caching Strategy**:
- Cache query extractions (common post patterns)
- Cache embeddings (query strings)
- Cache search results (query + top results)
- Cache final article results (post hash)
- TTL: 1 hour for results, 24 hours for embeddings

**Parallel Execution**:
- Vector and BM25 searches run concurrently
- Multiple query searches in parallel
- Batch LLM calls where possible
- Async/await for I/O operations

**Database Optimization**:
- IVFFlat index for fast vector search
- GIN index for full-text search
- Proper chunking (500-2000 chars) for granularity
- Connection pooling

**Query Limits**:
- Max 5 claims extracted per post
- Top 50 results per search (vector/BM25)
- Top 100 chunks for reranking
- Top 10-20 articles returned

## Quality Metrics

### Retrieval Quality
- **Precision@10**: How many of top 10 results are relevant?
- **Recall@50**: What % of all relevant articles found in top 50?
- **Mean Reciprocal Rank (MRR)**: Average position of first relevant result
- **NDCG**: Normalized Discounted Cumulative Gain

### Operational Metrics
- Search latency (p50, p95, p99)
- Cache hit rate
- Vector search coverage (% queries using vectors)
- Reranking effectiveness (score improvement vs. fusion)

## Error Handling

### Graceful Degradation
- LLM query extraction fails → Use raw post text
- Embedding generation fails → Use keyword search only
- Vector search fails → Use BM25 only
- Reranking fails → Use fusion results directly
- All searches fail → Return cached results or empty

### Fallback Strategies
- Simplified query if extraction too slow
- Reduce number of queries if timeout risk
- Skip reranking if results already high quality
- Return partial results if some searches fail

## Future Enhancements

1. **Multi-modal Search**
   - Image-based search for visual claims
   - Video content retrieval
   - Audio/podcast search

2. **Temporal Awareness**
   - Prioritize recent articles for breaking news
   - Historical context for older claims
   - Trending topic detection

3. **Cross-lingual Search**
   - Translate queries for multi-language search
   - Find English articles for Vietnamese posts
   - Regional dialect handling

4. **Learning from Feedback**
   - User ratings to improve ranking
   - Click-through rate analysis
   - A/B testing of retrieval strategies

5. **Advanced Fusion**
   - Neural reranking models
   - Learned fusion weights
   - Context-aware result blending
