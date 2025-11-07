"""
Base AI Provider Interfaces

Defines protocols and base classes for AI service providers (embeddings and LLMs).
This allows easy switching between providers (OpenAI, Anthropic, local models, etc.).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class AIProviderType(str, Enum):
    """Supported AI provider types."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"


class EmbeddingResponse(BaseModel):
    """Response from embedding generation."""

    embedding: List[float]
    model: str
    usage: Optional[Dict[str, int]] = None


class LLMMessage(BaseModel):
    """Message in a conversation."""

    role: str  # "system", "user", "assistant"
    content: str


class LLMResponse(BaseModel):
    """Response from LLM completion."""

    content: str
    model: str
    usage: Optional[Dict[str, int]] = None
    finish_reason: Optional[str] = None


class BaseEmbeddingProvider(ABC):
    """Base class for embedding providers."""

    @abstractmethod
    async def generate_embedding(
        self, text: str, model: Optional[str] = None
    ) -> EmbeddingResponse:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed
            model: Optional model name override

        Returns:
            EmbeddingResponse with embedding vector and metadata
        """
        pass

    @abstractmethod
    async def generate_embeddings_batch(
        self, texts: List[str], model: Optional[str] = None
    ) -> List[EmbeddingResponse]:
        """
        Generate embeddings for multiple texts in a batch.

        Args:
            texts: List of texts to embed
            model: Optional model name override

        Returns:
            List of EmbeddingResponse objects
        """
        pass

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Return the default embedding model name."""
        pass

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Return the embedding dimensions for the default model."""
        pass


class BaseLLMProvider(ABC):
    """Base class for LLM providers."""

    @abstractmethod
    async def generate_completion(
        self,
        messages: List[LLMMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Generate a completion from the LLM.

        Args:
            messages: Conversation history
            model: Optional model name override
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            **kwargs: Provider-specific parameters

        Returns:
            LLMResponse with generated content and metadata
        """
        pass

    @abstractmethod
    async def generate_completion_stream(
        self,
        messages: List[LLMMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ):
        """
        Generate a streaming completion from the LLM.

        Args:
            messages: Conversation history
            model: Optional model name override
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            **kwargs: Provider-specific parameters

        Yields:
            Chunks of generated text
        """
        pass

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Return the default LLM model name."""
        pass


class BaseAIProvider(ABC):
    """
    Combined AI provider interface.

    Providers can implement both embedding and LLM capabilities,
    or just one depending on their offerings.
    """

    @property
    @abstractmethod
    def provider_type(self) -> AIProviderType:
        """Return the provider type."""
        pass

    @abstractmethod
    def get_embedding_provider(self) -> Optional[BaseEmbeddingProvider]:
        """Return the embedding provider, or None if not supported."""
        pass

    @abstractmethod
    def get_llm_provider(self) -> Optional[BaseLLMProvider]:
        """Return the LLM provider, or None if not supported."""
        pass
