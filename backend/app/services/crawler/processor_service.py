"""
Article Processing Service

Orchestrates article content processing: chunking and embedding generation.
"""

from __future__ import annotations

import uuid
from typing import List

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.models.article_chunk import ArticleChunk
from app.services.content.embedding_service import generate_embedding_async
from app.services.content.chunking_service import chunk_text


async def process_article(session: AsyncSession, article_id: uuid.UUID) -> int:
    """
    Process an article: chunk content and create ArticleChunk rows.

    Args:
        session: Async database session
        article_id: UUID of the Article to process

    Returns:
        int: Number of chunks created
    """
    result = await session.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        return 0
    if not article.content:
        return 0

    # Remove existing chunks (idempotent processing) without lazy-loading
    await session.execute(
        delete(ArticleChunk).where(ArticleChunk.article_id == article.id)
    )
    await session.flush()

    chunks: List[str] = chunk_text(article.content, strategy="paragraph")
    created = 0
    for idx, chunk in enumerate(chunks):
        embedding = await generate_embedding_async(chunk)
        session.add(
            ArticleChunk(
                article_id=article.id,
                chunk_index=idx,
                chunk_text=chunk,
                embedding=embedding,
            )
        )
        created += 1

    await session.flush()
    return created
