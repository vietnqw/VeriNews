"""
Embedding Service

Generates embeddings for text chunks. Currently returns a dummy vector for
development; replace with OpenAI or local model later.
"""

from __future__ import annotations

from typing import List


EMBEDDING_DIMENSIONS = 1536


def generate_embedding(text: str) -> List[float]:
    # Placeholder: deterministic but simple embedding (zeros)
    # Replace with real model inference.
    return [0.0] * EMBEDDING_DIMENSIONS
