"""
OpenAI Provider Implementation

Implements both embedding and LLM services using OpenAI's API.
"""

from __future__ import annotations

from typing import Any, List, Optional

from loguru import logger
from openai import AsyncOpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config.settings import settings
from app.services.ai.base import (
    AIProviderType,
    BaseAIProvider,
    BaseEmbeddingProvider,
    BaseLLMProvider,
    EmbeddingResponse,
    LLMMessage,
    LLMResponse,
)


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """OpenAI embedding provider using text-embedding-3-small."""

    def __init__(self, api_key: str, default_model: str = "text-embedding-3-small"):
        self.client = AsyncOpenAI(api_key=api_key)
        self._default_model = default_model
        # Dimensions for text-embedding-3-small
        self._dimensions = 1536

    @property
    def default_model(self) -> str:
        return self._default_model

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @retry(
        retry=retry_if_exception_type((Exception,)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def generate_embedding(
        self, text: str, model: Optional[str] = None
    ) -> EmbeddingResponse:
        """Generate embedding for a single text with retry logic."""
        model_name = model or self.default_model

        try:
            response = await self.client.embeddings.create(
                model=model_name, input=text, encoding_format="float"
            )

            return EmbeddingResponse(
                embedding=response.data[0].embedding,
                model=response.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
            )
        except Exception as e:
            logger.error(f"OpenAI embedding generation failed: {e}")
            raise

    @retry(
        retry=retry_if_exception_type((Exception,)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def generate_embeddings_batch(
        self, texts: List[str], model: Optional[str] = None
    ) -> List[EmbeddingResponse]:
        """Generate embeddings for multiple texts in a batch."""
        model_name = model or self.default_model

        try:
            response = await self.client.embeddings.create(
                model=model_name, input=texts, encoding_format="float"
            )

            return [
                EmbeddingResponse(
                    embedding=item.embedding,
                    model=response.model,
                    usage={
                        "prompt_tokens": response.usage.prompt_tokens
                        // len(texts),  # Approximate per-text
                        "total_tokens": response.usage.total_tokens // len(texts),
                    },
                )
                for item in response.data
            ]
        except Exception as e:
            logger.error(f"OpenAI batch embedding generation failed: {e}")
            raise


class OpenAILLMProvider(BaseLLMProvider):
    """OpenAI LLM provider using GPT models."""

    def __init__(self, api_key: str, default_model: str = "gpt-4o-mini"):
        self.client = AsyncOpenAI(api_key=api_key)
        self._default_model = default_model

    @property
    def default_model(self) -> str:
        return self._default_model

    @retry(
        retry=retry_if_exception_type((Exception,)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def generate_completion(
        self,
        messages: List[LLMMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a completion from GPT model with retry logic."""
        model_name = model or self.default_model

        try:
            # Convert LLMMessage to OpenAI format
            openai_messages = [
                {"role": msg.role, "content": msg.content} for msg in messages
            ]

            response = await self.client.chat.completions.create(
                model=model_name,
                messages=openai_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )

            return LLMResponse(
                content=response.choices[0].message.content or "",
                model=response.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                finish_reason=response.choices[0].finish_reason,
            )
        except Exception as e:
            logger.error(f"OpenAI LLM completion failed: {e}")
            raise

    async def generate_completion_stream(
        self,
        messages: List[LLMMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ):
        """Generate a streaming completion from GPT model."""
        model_name = model or self.default_model

        try:
            # Convert LLMMessage to OpenAI format
            openai_messages = [
                {"role": msg.role, "content": msg.content} for msg in messages
            ]

            stream = await self.client.chat.completions.create(
                model=model_name,
                messages=openai_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                **kwargs,
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"OpenAI LLM streaming failed: {e}")
            raise


class OpenAIProvider(BaseAIProvider):
    """Combined OpenAI provider for both embeddings and LLM."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        embedding_model: str = "text-embedding-3-small",
        llm_model: str = "gpt-4o-mini",
    ):
        """
        Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key (defaults to settings)
            embedding_model: Default embedding model
            llm_model: Default LLM model
        """
        self.api_key = api_key or settings.openai_api_key
        if not self.api_key:
            raise ValueError("OpenAI API key is required")

        self.embedding = OpenAIEmbeddingProvider(self.api_key, embedding_model)
        self.llm = OpenAILLMProvider(self.api_key, llm_model)

    @property
    def provider_type(self) -> AIProviderType:
        return AIProviderType.OPENAI

    def get_embedding_provider(self) -> Optional[BaseEmbeddingProvider]:
        return self.embedding

    def get_llm_provider(self) -> Optional[BaseLLMProvider]:
        return self.llm
