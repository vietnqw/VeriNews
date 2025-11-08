# Backend: AI/ML Services

## Overview

The AI/ML Services component provides intelligent processing capabilities powered by large language models (LLMs) and machine learning algorithms. These services enable semantic understanding, natural language processing, and advanced reasoning required for accurate news verification.

## Purpose

Leverage artificial intelligence to:
- Understand semantic meaning of text beyond keywords
- Extract structured information from unstructured posts
- Generate embeddings for similarity search
- Score relevance and credibility
- Detect AI-generated content
- Perform complex reasoning and fact-checking

## Key Responsibilities

1. **Embedding Generation**
   - Convert text into dense vector representations
   - Enable semantic similarity search
   - Support multiple languages
   - Batch processing for efficiency

2. **Query Extraction**
   - Parse noisy social media posts
   - Extract clean, searchable queries
   - Identify factual claims
   - Remove noise (emojis, hashtags, mentions)

3. **Relevance Scoring**
   - Assess how well articles match queries
   - Understand contextual relevance
   - Handle nuanced language
   - Provide explainable scores

4. **Image Analysis** (Future)
   - Detect AI-generated images
   - Identify manipulated photos
   - Reverse image search
   - Extract text from images (OCR)

5. **Claim Verification** (Future)
   - Decompose posts into verifiable claims
   - Check claims against trusted sources
   - Classify support/contradiction/neutral
   - Generate verification explanations

6. **Credibility Scoring** (Future)
   - Synthesize evidence from all sources
   - Calculate overall credibility score
   - Generate user-friendly explanations
   - Provide confidence intervals

## Sub-Components

### 1. Embedding Service

**Purpose**: Generate semantic embeddings for text content

**Model**: OpenAI text-embedding-3-small
- Dimensions: 1536
- Max input: 8,192 tokens (~30,000 characters)
- Cost: $0.02 per 1M tokens
- Latency: ~100-200ms per request

**Use Cases**:
- Article chunk embedding (during ingestion)
- Query embedding (during verification)
- Semantic similarity comparison

**Operations**:

**Single Embedding**:
- Input: Text string (up to 8K tokens)
- Process: API call to OpenAI
- Output: 1536-dim vector, normalized to unit length

**Batch Embedding**:
- Input: Array of text strings (up to 100 items)
- Process: Single API call with multiple inputs
- Output: Array of vectors
- Benefit: Reduced latency and cost

**Best Practices**:
- Normalize vectors for cosine similarity
- Cache embeddings for repeated queries
- Batch when possible (5-10 items optimal)
- Handle rate limits (3,000 requests/min)
- Retry with exponential backoff on failures

**Error Handling**:
- Token limit exceeded → Truncate or split text
- API rate limit → Queue and retry
- API error → Use cached embeddings or fallback
- Network timeout → Retry up to 3 times

### 2. Query Extraction Service

**Purpose**: Transform raw posts into structured search queries

**Model**: GPT-4 or GPT-3.5-turbo
- Better reasoning than embedding models
- Understands context and intent
- Follows instructions reliably

**Process**:

**Clean Query Extraction**:
```
System Prompt:
"You are a search query extractor. Given a social media post,
extract the core information-seeking query. Remove hashtags,
mentions, emojis, and promotional language. Keep only the
factual question or statement. Respond in 1-2 sentences max."

User Message:
"{social_media_post}"
```

Example:
- Input: "🚨 BREAKING: President signs climate bill! #Climate #Politics @username"
- Output: "President signs climate bill"

**Claim Extraction**:
```
System Prompt:
"Extract distinct factual claims from this post. Each claim
should be a verifiable statement. Ignore opinions and questions.
Return as JSON array. Max 5 claims."

User Message:
"{social_media_post}"

Expected Format:
{
  "claims": [
    "President signed climate bill",
    "Bill includes carbon tax provision"
  ]
}
```

**Implementation Details**:
- Temperature: 0.0 (deterministic)
- Max tokens: 200
- Timeout: 10 seconds
- Caching: Hash post text, cache for 1 hour
- Fallback: Simple regex-based extraction

**Cost Optimization**:
- Use GPT-3.5-turbo when possible ($0.50 per 1M tokens)
- Use GPT-4 only for complex cases ($10 per 1M tokens)
- Cache common post patterns
- Batch process during off-peak hours

### 3. Reranking Service

**Purpose**: Score relevance of retrieved articles using deep understanding

**Model**: GPT-3.5-turbo or GPT-4

**Process**:

**Input**:
- Original social media post
- List of article chunks with metadata

**Scoring Prompt**:
```
System Prompt:
"Rate the relevance of this article excerpt to the given post.
Consider semantic meaning, not just keyword overlap.

Scoring:
- 10: Directly addresses the exact topic/claim
- 7-9: Highly relevant, discusses related aspects
- 4-6: Somewhat relevant, tangential information
- 1-3: Barely relevant, mentions in passing
- 0: Not relevant

Return only the numeric score (0-10)."

User Message:
"Post: {post_text}

Article excerpt: {chunk_text}

Relevance score:"
```

**Output**: Numeric score 0-10

**Batch Processing**:
- Group 5-10 chunks per API call
- Use JSON mode for structured output
- Parallel requests for speed
- Aggregate scores efficiently

**Example**:
```
Request:
{
  "post": "President announces new climate policy",
  "chunks": [
    {"id": 1, "text": "President unveiled climate initiative..."},
    {"id": 2, "text": "New regulations target emissions..."},
    {"id": 3, "text": "Sports results from last night..."}
  ]
}

Response:
{
  "scores": [
    {"id": 1, "score": 9},
    {"id": 2, "score": 8},
    {"id": 3, "score": 0}
  ]
}
```

**Benefits Over Simple Scoring**:
- Understands synonyms and paraphrasing
- Recognizes contradictory information
- Considers context and nuance
- Identifies supporting vs. unrelated facts

### 4. Image Analysis Service (Future)

**Purpose**: Detect AI-generated or manipulated images

**Approach Options**:

**Option A: Third-Party API**
- Services: Hive AI, Illuminarty, Optic
- Pros: Ready-to-use, high accuracy
- Cons: Cost per request, external dependency

**Option B: Self-Hosted Model**
- Models: CLIP, ResNet fine-tuned on synthetic images
- Pros: Lower cost at scale, data privacy
- Cons: GPU infrastructure required, maintenance

**Features**:
- AI generation detection (DALL-E, Midjourney, etc.)
- Manipulation detection (Photoshop edits)
- Deepfake detection (for faces)
- Reverse image search (TinEye, Google)

**Output**:
```
{
  "ai_generated_probability": 0.85,
  "confidence": "high",
  "artifacts_detected": [
    "unnatural lighting",
    "inconsistent shadows"
  ],
  "reverse_search_matches": [
    {
      "url": "https://...",
      "similarity": 0.95,
      "first_seen": "2024-01-10"
    }
  ]
}
```

### 5. Claim Verification Service (Future)

**Purpose**: Fact-check individual claims against trusted articles

**Process**:

1. **Claim Decomposition**
   - Break post into atomic claims
   - Each claim is independently verifiable
   - Remove compound statements

2. **Evidence Retrieval**
   - Search for relevant articles (use Retrieval System)
   - Focus on high-authority sources
   - Prioritize recent articles

3. **Entailment Classification**
   - For each claim + article pair:
     - **Supports**: Article confirms the claim
     - **Refutes**: Article contradicts the claim
     - **Neutral**: Article doesn't address the claim
   - Use NLI (Natural Language Inference) model

4. **Aggregation**
   - Combine evidence from multiple articles
   - Weight by source credibility
   - Handle conflicting information
   - Calculate confidence score

**Example**:
```
Claim: "President signed climate bill yesterday"

Evidence:
- Article 1 (BBC): "President signed bill on Tuesday" → Supports (if today is Wednesday)
- Article 2 (CNN): "Bill signing scheduled for next week" → Refutes
- Article 3 (NYT): "Congress passed climate legislation" → Neutral

Verdict: Likely True (2 support, 0 refute) with 75% confidence
```

**Models**:
- GPT-4 for reasoning
- RoBERTa-based NLI models for efficiency
- Ensemble for higher accuracy

### 6. Credibility Scoring Service (Future)

**Purpose**: Generate overall credibility assessment

**Inputs**:
- Claim verification results
- Image analysis results
- Source matching results
- Author/platform credibility
- Engagement patterns

**Scoring Factors**:

**Evidence Strength (40%)**:
- Number of supporting articles
- Quality of sources
- Consistency of information
- Recency of evidence

**Image Authenticity (20%)**:
- AI generation probability
- Manipulation detection
- Reverse search results

**Content Quality (20%)**:
- Grammar and coherence
- Emotional language vs. factual
- Clickbait indicators
- Source citations

**Contextual Signals (20%)**:
- Author history and credibility
- Platform patterns (bot-like behavior)
- Virality vs. verification timeline
- Cross-platform consistency

**Output**:
```
{
  "credibility_score": 75,  // 0-100
  "verdict": "likely_verified",  // verified | likely_verified | unverified | likely_false | false
  "confidence": 0.82,
  "explanation": "Post is supported by 3 trusted sources...",
  "breakdown": {
    "evidence_strength": 85,
    "image_authenticity": 90,
    "content_quality": 60,
    "contextual_signals": 65
  },
  "recommendation": "proceed_with_caution"
}
```

## AI Provider Architecture

### Provider Abstraction

**Purpose**: Support multiple AI providers (OpenAI, Anthropic, local models)

**Interface**:
```
AIProvider:
  - generate_embedding(text) → vector
  - complete(prompt, model) → text
  - batch_embed(texts) → vectors[]
  - chat(messages, model) → response
```

**Implementations**:
- **OpenAIProvider**: Primary (GPT-4, text-embedding-3-small)
- **AnthropicProvider**: Alternative (Claude for reasoning)
- **LocalProvider**: Self-hosted (Llama, Mistral for cost savings)

**Benefits**:
- Easy provider switching
- Fallback to alternatives
- Cost optimization (route by task complexity)
- A/B testing different models

### Cost Management

**Budget Allocation**:
- Embeddings: $500/month (25M tokens)
- Query extraction: $200/month (400K requests)
- Reranking: $1,000/month (2M requests)
- Total: ~$1,700/month for 400K verifications

**Optimization Strategies**:
- Cache aggressively (80%+ hit rate)
- Use cheaper models when possible (GPT-3.5 vs GPT-4)
- Batch requests to reduce overhead
- Rate limit expensive operations
- Monitor and alert on cost spikes

**Cost Per Verification**:
- Target: < $0.005 per verification
- Breakdown:
  - Embedding generation: $0.001
  - Query extraction: $0.0005
  - Reranking: $0.002
  - Buffer: $0.0015

### Rate Limiting

**OpenAI Limits (Standard Tier)**:
- Embeddings: 3,000 requests/min
- GPT-4: 500 requests/min
- GPT-3.5: 3,500 requests/min

**Handling Strategies**:
- Request queuing with priority
- Exponential backoff on 429 errors
- Distribute load across multiple API keys
- Cache to reduce API calls
- Monitor usage proactively

## Prompt Engineering

### Best Practices

1. **Clear Instructions**
   - Be explicit about expected output
   - Provide examples (few-shot learning)
   - Specify format (JSON, text, numeric)

2. **Context Management**
   - Include necessary context only
   - Avoid token waste on irrelevant info
   - Use system prompts for role-setting

3. **Temperature Settings**
   - 0.0 for deterministic tasks (extraction)
   - 0.3-0.7 for creative tasks (explanations)
   - 1.0 for diverse generation (not typical use)

4. **Output Parsing**
   - Use JSON mode when available
   - Validate output format
   - Have fallback parsing logic
   - Handle malformed responses

### Prompt Versioning

**Strategy**:
- Version prompts in code (PROMPT_V1, PROMPT_V2)
- A/B test prompt variations
- Track performance metrics per version
- Gradual rollout of improvements

**Metrics**:
- Task accuracy (human evaluation)
- Latency (response time)
- Cost (tokens used)
- Reliability (error rate)

## Testing & Validation

### Unit Testing
- Mock AI provider responses
- Test error handling (timeouts, rate limits)
- Validate output formats
- Check edge cases (empty input, very long text)

### Integration Testing
- Test with real API calls (small scale)
- Validate end-to-end flows
- Test rate limiting behavior
- Verify cost tracking

### Quality Assurance
- Manual review of outputs (sample 5%)
- Compare AI results to human annotations
- Track user feedback and corrections
- Monitor drift in model behavior over time

## Monitoring & Observability

### Key Metrics
- **Latency**: p50, p95, p99 response times
- **Cost**: Tokens used, $ spent per day
- **Errors**: Rate limits, timeouts, API errors
- **Quality**: Accuracy on test sets

### Alerts
- High error rate (> 5%)
- Slow response times (p95 > 5s)
- Cost spike (> 120% of daily budget)
- API quota near exhaustion (> 80%)

## Future Enhancements

1. **Model Fine-Tuning**
   - Fine-tune embeddings on news domain
   - Fine-tune LLM on verification tasks
   - Improve accuracy and reduce cost

2. **Multi-Modal Models**
   - GPT-4 Vision for image analysis
   - Audio/video content processing
   - Cross-modal reasoning

3. **Specialized Models**
   - NLI model for claim verification
   - Named Entity Recognition for key facts
   - Sentiment analysis for bias detection

4. **Local Model Deployment**
   - Self-host Llama 3 or Mistral for cost savings
   - GPU infrastructure for inference
   - Hybrid approach (local + cloud)
