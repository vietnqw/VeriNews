"""
AI Service Factory

Provides a centralized way to create and manage AI providers.
Supports singleton pattern for efficient resource usage.
"""

from __future__ import annotations

from typing import Dict, Optional

from loguru import logger

from app.config.settings import settings
from app.services.ai.base import AIProviderType, BaseAIProvider
from app.services.ai.providers.openai_provider import OpenAIProvider


class AIServiceFactory:
    """
    Factory for creating and managing AI service providers.

    Implements singleton pattern to reuse provider instances across the application.
    """

    _instances: Dict[AIProviderType, BaseAIProvider] = {}

    @classmethod
    def create_provider(
        cls, provider_type: Optional[AIProviderType] = None
    ) -> BaseAIProvider:
        """
        Create or retrieve an AI provider instance.

        Args:
            provider_type: Type of provider to create (defaults to settings)

        Returns:
            BaseAIProvider instance

        Raises:
            ValueError: If provider type is not supported
        """
        # Use provider from settings if not specified
        if provider_type is None:
            provider_type = AIProviderType(settings.ai.provider)

        # Return cached instance if exists
        if provider_type in cls._instances:
            return cls._instances[provider_type]

        # Create new provider instance
        provider = cls._create_provider_instance(provider_type)
        cls._instances[provider_type] = provider

        logger.info(f"Created AI provider: {provider_type.value}")
        return provider

    @classmethod
    def _create_provider_instance(cls, provider_type: AIProviderType) -> BaseAIProvider:
        """Create a new provider instance based on type."""
        if provider_type == AIProviderType.OPENAI:
            return OpenAIProvider(
                api_key=settings.openai_api_key,
                embedding_model=settings.ai.embedding_model,
                llm_model=settings.ai.llm_model,
            )
        elif provider_type == AIProviderType.ANTHROPIC:
            # Future: Implement Anthropic provider
            raise NotImplementedError("Anthropic provider not yet implemented")
        elif provider_type == AIProviderType.LOCAL:
            # Future: Implement local model provider
            raise NotImplementedError("Local model provider not yet implemented")
        else:
            raise ValueError(f"Unsupported provider type: {provider_type}")

    @classmethod
    def clear_cache(cls):
        """Clear all cached provider instances."""
        cls._instances.clear()
        logger.info("Cleared AI provider cache")

    @classmethod
    def get_embedding_provider(cls, provider_type: Optional[AIProviderType] = None):
        """Get the embedding provider from the specified or default AI provider."""
        provider = cls.create_provider(provider_type)
        embedding_provider = provider.get_embedding_provider()

        if embedding_provider is None:
            raise ValueError(
                f"Provider {provider.provider_type} does not support embeddings"
            )

        return embedding_provider

    @classmethod
    def get_llm_provider(cls, provider_type: Optional[AIProviderType] = None):
        """Get the LLM provider from the specified or default AI provider."""
        provider = cls.create_provider(provider_type)
        llm_provider = provider.get_llm_provider()

        if llm_provider is None:
            raise ValueError(f"Provider {provider.provider_type} does not support LLM")

        return llm_provider


# Convenience function for getting the default provider
def get_ai_provider() -> BaseAIProvider:
    """Get the default AI provider instance."""
    return AIServiceFactory.create_provider()
