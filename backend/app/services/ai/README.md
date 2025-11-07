# AI Services Architecture

Modular, provider-agnostic AI services for VeriNews. Supports embeddings and LLM completions from multiple providers (OpenAI, Anthropic, local models).

## Features

- **Provider Abstraction**: Easy to switch between AI providers
- **Modular Design**: Separate embedding and LLM services
- **Retry Logic**: Automatic retries with exponential backoff
- **Batch Operations**: Efficient batch embedding generation
- **Type Safety**: Full type hints and Pydantic models
- **Configuration**: YAML-based configuration with environment variables

## Architecture

```
app/services/ai/
├── base.py                  # Base interfaces and protocols
├── factory.py               # Service factory with singleton pattern
├── providers/
│   ├── openai_provider.py   # OpenAI implementation
│   └── __init__.py
├── __init__.py
└── README.md
```

## Quick Start

### 1. Configuration

Add to your `.env` file:
```env
AI_SERVICE_API_KEY=your_api_key_here
```

The unified `AI_SERVICE_API_KEY` works for all AI providers (OpenAI, Anthropic, etc.).

Update `config/config.yaml`:
```yaml
ai:
  provider: "openai"
  embedding_model: "text-embedding-3-small"
  llm_model: "gpt-4o-mini"
  max_retries: 3
  timeout_seconds: 30
```

### 2. Using Embeddings

```python
from app.services.content.embedding_service import generate_embedding_async, generate_embeddings_batch

# Single embedding
embedding = await generate_embedding_async("Hello, world!")
# Returns: List[float] with 1536 dimensions

# Batch embeddings (more efficient)
texts = ["Text 1", "Text 2", "Text 3"]
embeddings = await generate_embeddings_batch(texts)
# Returns: List[List[float]]
```

### 3. Using LLM

```python
from app.services.ai import AIServiceFactory, LLMMessage

# Get LLM provider
llm = AIServiceFactory.get_llm_provider()

# Generate completion
messages = [
    LLMMessage(role="system", content="You are a helpful assistant."),
    LLMMessage(role="user", content="What is AI?")
]

response = await llm.generate_completion(
    messages=messages,
    temperature=0.7,
    max_tokens=500
)

print(response.content)  # AI-generated response
print(response.usage)    # Token usage stats
```

### 4. Streaming Completions

```python
async for chunk in llm.generate_completion_stream(messages=messages):
    print(chunk, end="", flush=True)
```

## Provider Details

### OpenAI

**Supported Models:**
- Embeddings: `text-embedding-3-small`, `text-embedding-3-large`
- LLM: `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo`, `gpt-3.5-turbo`

**Configuration:**
```yaml
ai:
  provider: "openai"
  embedding_model: "text-embedding-3-small"  # 1536 dimensions
  llm_model: "gpt-4o-mini"  # Fast, cost-effective
```

### Adding New Providers

1. **Create Provider Class:**

```python
# app/services/ai/providers/anthropic_provider.py
from app.services.ai.base import BaseAIProvider, BaseEmbeddingProvider, BaseLLMProvider

class AnthropicProvider(BaseAIProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.llm = AnthropicLLMProvider(api_key)

    @property
    def provider_type(self) -> AIProviderType:
        return AIProviderType.ANTHROPIC

    def get_embedding_provider(self) -> Optional[BaseEmbeddingProvider]:
        return None  # Anthropic doesn't provide embeddings

    def get_llm_provider(self) -> Optional[BaseLLMProvider]:
        return self.llm
```

2. **Register in Factory:**

```python
# app/services/ai/factory.py
elif provider_type == AIProviderType.ANTHROPIC:
    return AnthropicProvider(
        api_key=settings.anthropic_api_key,
        llm_model=settings.ai.llm_model
    )
```

## API Reference

### Base Classes

#### `BaseEmbeddingProvider`
- `generate_embedding(text, model=None)` - Generate single embedding
- `generate_embeddings_batch(texts, model=None)` - Batch generate embeddings
- `default_model` - Property: default embedding model
- `dimensions` - Property: embedding dimensions

#### `BaseLLMProvider`
- `generate_completion(messages, model=None, temperature=0.7, max_tokens=None)` - Generate completion
- `generate_completion_stream(messages, model=None, temperature=0.7, max_tokens=None)` - Stream completion
- `default_model` - Property: default LLM model

### Models

#### `EmbeddingResponse`
```python
class EmbeddingResponse(BaseModel):
    embedding: List[float]
    model: str
    usage: Optional[Dict[str, int]]  # prompt_tokens, total_tokens
```

#### `LLMResponse`
```python
class LLMResponse(BaseModel):
    content: str
    model: str
    usage: Optional[Dict[str, int]]  # prompt_tokens, completion_tokens, total_tokens
    finish_reason: Optional[str]  # stop, length, content_filter, etc.
```

#### `LLMMessage`
```python
class LLMMessage(BaseModel):
    role: str  # "system", "user", "assistant"
    content: str
```

## Error Handling

All providers include automatic retry logic with exponential backoff:

```python
@retry(
    retry=retry_if_exception_type((Exception,)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
```

Exceptions are logged and re-raised for handling at the application level.

## Performance Considerations

1. **Batch Operations**: Use `generate_embeddings_batch()` for multiple texts - it's much more efficient than individual calls

2. **Singleton Pattern**: Providers are cached and reused across the application

3. **Async/Await**: All operations are async for better performance

4. **Connection Pooling**: OpenAI client automatically pools connections

## Testing

```python
# Test with a simple script
from app.services.ai import get_ai_provider

provider = get_ai_provider()
print(f"Provider: {provider.provider_type}")

# Test embedding
embedding_provider = provider.get_embedding_provider()
print(f"Embedding model: {embedding_provider.default_model}")
print(f"Dimensions: {embedding_provider.dimensions}")

# Test LLM
llm_provider = provider.get_llm_provider()
print(f"LLM model: {llm_provider.default_model}")
```

## Troubleshooting

**API Key Not Found:**
```
ValueError: OpenAI API key is required
```
- Solution: Add `AI_SERVICE_API_KEY` to your `.env` file

**Provider Not Supported:**
```
ValueError: Unsupported provider type: anthropic
```
- Solution: Only `openai` is currently implemented. Check `config.yaml`

**Rate Limits:**
- OpenAI has rate limits based on your account tier
- The retry logic will handle temporary rate limits
- For persistent issues, consider upgrading your OpenAI account

## Future Enhancements

- [ ] Anthropic (Claude) provider
- [ ] Local model provider (Ollama, LM Studio)
- [ ] Caching layer for embeddings
- [ ] Cost tracking and analytics
- [ ] Model performance monitoring
- [ ] A/B testing between providers
