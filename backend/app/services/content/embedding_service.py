"""
Embedding Service

Generates embeddings for text chunks using the configured AI provider.
Provides both synchronous and asynchronous interfaces.
"""

from __future__ import annotations

import asyncio
from typing import List

from loguru import logger

from app.services.ai.factory import AIServiceFactory


# For backward compatibility and non-async contexts
def generate_embedding(text: str) -> List[float]:
    """
    Generate embedding for a single text (synchronous wrapper).

    Args:
        text: Text to embed

    Returns:
        List of floats representing the embedding vector

    Note:
        This is a synchronous wrapper around the async implementation.
        For better performance in async contexts, use generate_embedding_async directly.
    """
    return asyncio.run(generate_embedding_async(text))


async def generate_embedding_async(text: str) -> List[float]:
    """
    Generate embedding for a single text.

    Args:
        text: Text to embed

    Returns:
        List of floats representing the embedding vector
    """
    try:
        embedding_provider = AIServiceFactory.get_embedding_provider()
        response = await embedding_provider.generate_embedding(text)
        return response.embedding
    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
        raise


async def generate_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for multiple texts in a batch (more efficient).

    Args:
        texts: List of texts to embed

    Returns:
        List of embedding vectors
    """
    try:
        embedding_provider = AIServiceFactory.get_embedding_provider()
        responses = await embedding_provider.generate_embeddings_batch(texts)
        return [response.embedding for response in responses]
    except Exception as e:
        logger.error(f"Failed to generate batch embeddings: {e}")
        raise


def get_embedding_dimensions() -> int:
    """
    Get the dimensions of embeddings from the current provider.

    Returns:
        Number of dimensions in the embedding vector
    """
    embedding_provider = AIServiceFactory.get_embedding_provider()
    return embedding_provider.dimensions
