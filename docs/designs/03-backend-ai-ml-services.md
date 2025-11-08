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

**What it does**: Extracts clean, searchable queries from social media posts

**How it works**:
- Takes messy post with emojis, hashtags, etc.
- Sends to GPT-4 with structured prompt
- Gets back:
  - Clean query (1-2 sentences, core topic)
  - Factual claims (list of verifiable statements)

**Example**:
```
Input: "🚨 BREAKING: PM announces new tax policy! #Politics #Vietnam"

Output:
- Clean query: "Prime Minister announces new tax policy"
- Claims: ["Prime Minister announced tax policy"]
```

**Implementation details**:
- Uses GPT-4 for best quality (or GPT-3.5-turbo for cost savings)
- Temperature set to 0 (deterministic output)
- JSON mode for structured response
- Fallback to simple text cleaning if API fails

### 3. Reranking Service

**What it does**: Scores how relevant each article chunk is to the query

**How it works**:
- Takes original post + list of article chunks
- Asks GPT-4 to score each chunk (0-10 scale)
- Processes in batches (5-10 chunks per API call)
- Returns normalized scores (0-1)

**Why it's needed**: Search algorithms aren't perfect. AI can understand context and judge true relevance.

**Implementation details**:
- Batch processing for efficiency
- Parallel API calls
- Handles JSON parsing errors gracefully
- Falls back to fusion scores if reranking fails

### 4. Vietnamese Text Processor

**What it does**: Tokenizes Vietnamese text for search

**How it works**:
- Identifies Vietnamese compound words
- Joins them with underscores: "công ty" → "công_ty"
- Preserves diacritical marks
- Mixed Vietnamese-English text supported

**Why it's needed**: Vietnamese doesn't have spaces between all word boundaries. Compound words need special handling for keyword search.

**Implementation**: Dictionary-based approach with common Vietnamese compounds

## AI Provider Abstraction

The code has a base `AIProvider` class that can work with different providers:
- **OpenAIProvider**: Currently implemented
- Future: Could add Anthropic, local models, etc.

This makes it easy to switch or add alternative AI providers.

## Cost Management

Current usage per verification request:
- Embedding generation: ~1,500 tokens → $0.00003
- Query extraction: ~500 tokens → $0.005
- Reranking: ~2,000 tokens → $0.02
- **Total**: ~$0.025 per verification (without caching)

With caching (80%+ hit rate): ~$0.005 per verification

## What's NOT Implemented

- Image analysis (AI-generated image detection)
- Claim verification (fact-checking logic)
- Credibility scoring
- Local model deployment
- Other AI providers (only OpenAI)

## Configuration

Settings in `.env`:
- `OPENAI_API_KEY`: Your API key
- Model selection in `config/config.yaml`
- Batch sizes and timeouts configurable
