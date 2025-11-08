# Backend: Retrieval System

## What It Is

The Retrieval System finds relevant news articles for a given social media post. It uses a 6-stage pipeline that combines AI understanding with traditional search methods to find the most relevant articles from the database.

## What It Does

Takes a social media post → Returns ranked list of relevant news articles

## The 6 Stages

### Stage 1: Query Extraction
**What happens**: AI extracts clean queries from the noisy post

- Sends post to GPT-4
- Gets back a clean query (main topic) and factual claims (specific statements)
- Example:
  - Input: "🚨 Breaking: President signs climate bill! #Politics"
  - Output: Clean query: "President signs climate bill", Claims: ["President signed climate bill"]

**Implementation**: Uses OpenAI GPT-4 API with structured prompts

### Stage 2: Embedding Generation
**What happens**: Converts text queries into numbers (vectors)

- Takes the clean query + claims from Stage 1
- Sends to OpenAI to generate 1536-dimensional vectors
- Batches multiple queries together for efficiency
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

Both methods run in parallel, each returning top 50 results per query.

### Stage 4: Reciprocal Rank Fusion (RRF)
**What happens**: Combines all the search results into one ranked list

- Has multiple result lists from Stage 3 (vector + BM25 for each query)
- Uses RRF algorithm to merge them intelligently
- Chunks appearing in multiple lists get boosted
- Results in ~100-200 unique article chunks

**Why**: Different search methods are good at different things. RRF combines their strengths.

### Stage 5: Reranking
**What happens**: AI scores how relevant each result actually is

- Takes top 100 chunks from Stage 4
- Asks GPT-4 to score each chunk's relevance (0-10 scale)
- Processes in batches of 5-10 for efficiency
- Re-sorts by these AI relevance scores
- Keeps top 50 most relevant

**Why**: Search algorithms aren't perfect. AI can understand context and nuance better.

### Stage 6: Article Aggregation
**What happens**: Groups chunks back into full articles

- Each chunk belongs to an article
- Groups all chunks from same article together
- Sums up relevance scores for each article
- Returns top 10-20 articles
- Includes relevant excerpts from matched chunks

## Vietnamese Language Support

Handles Vietnamese text specially:
- Keeps compound words together ("công ty" stays as one term)
- Preserves diacritical marks
- Custom tokenization for BM25 search
- OpenAI embeddings handle Vietnamese well natively

## Performance

Typical timing breakdown:
- Query extraction: 100ms
- Embedding generation: 200ms
- Hybrid search: 80ms (both methods in parallel)
- Fusion: 20ms
- Reranking: 500ms
- Aggregation: 50ms
- **Total**: ~1 second

With caching: <10ms for repeated queries

## Technology Stack

- **Query Extraction**: OpenAI GPT-4 API
- **Embeddings**: OpenAI text-embedding-3-small (1536 dimensions)
- **Vector Search**: PostgreSQL pgvector extension with IVFFlat index
- **Keyword Search**: PostgreSQL full-text search with custom Vietnamese config
- **Orchestration**: Python async/await for parallel operations
- **Caching**: Redis for storing results

## Key Design Choices

**Why hybrid search?**
- Vector search: Good at meaning, weak at exact terms
- Keyword search: Good at exact terms, weak at synonyms
- Together: Best of both worlds

**Why use AI twice (extraction + reranking)?**
- Extraction: Cleans up messy input
- Reranking: Improves final quality
- Cost-effective placement in the pipeline

**Why chunk articles?**
- Long articles don't match well as a whole
- Smaller chunks are more precise
- Can return relevant excerpts, not just article titles

## Configuration

All configurable via `config/config.yaml`:
- Top-k results per stage
- BM25 ranking parameters
- Vietnamese tokenization settings
- Reranking batch size
- Cache TTL

## What's NOT Implemented

- Image analysis
- Claim verification (checking if claims are true/false)
- Credibility scoring
- Multi-language support (only Vietnamese/English)
