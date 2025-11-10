"""
Article Processing Service

Orchestrates article content processing: chunking and embedding generation.
"""

from __future__ import annotations

import uuid
from typing import List

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.article import Article
from app.models.article_chunk import ArticleChunk
from app.services.content.embedding_service import generate_embedding_async
from app.services.content.chunking_service import chunk_text
from app.services.retrieval.bm25_search_service import BM25SearchService


async def process_article(session: AsyncSession, article_id: uuid.UUID) -> int:
    """
    Process an article: chunk content, create ArticleChunk rows with embeddings and BM25 indexing.

    This function:
    1. Chunks the article content
    2. Generates embeddings for each chunk
    3. Populates denormalized fields (title, source, published_at)
    4. Indexes each chunk for BM25 search

    Args:
        session: Async database session
        article_id: UUID of the Article to process

    Returns:
        int: Number of chunks created
    """
    # Fetch article with joined relationships for denormalized fields
    result = await session.execute(
        select(Article)
        .options(
            joinedload(Article.rss_feed).joinedload(
                Article.rss_feed.property.mapper.class_.news_source
            )
        )
        .where(Article.id == article_id)
    )
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

    # Get denormalized values
    article_title = article.title
    source_name = article.rss_feed.news_source.name
    published_at = article.published_at

    # Initialize BM25 service
    bm25_service = BM25SearchService(session)

    chunks: List[str] = chunk_text(article.content, strategy="paragraph")
    created = 0
    for idx, chunk in enumerate(chunks):
        # Generate embedding
        embedding = await generate_embedding_async(chunk)

        # Create chunk with denormalized fields
        article_chunk = ArticleChunk(
            article_id=article.id,
            chunk_index=idx,
            chunk_text=chunk,
            embedding=embedding,
            article_title=article_title,
            source_name=source_name,
            published_at=published_at,
        )
        session.add(article_chunk)
        created += 1

    # Flush to get chunk IDs
    await session.flush()

    # Index all chunks for BM25 search
    # Get the newly created chunks
    chunk_result = await session.execute(
        select(ArticleChunk).where(ArticleChunk.article_id == article.id)
    )
    new_chunks = chunk_result.scalars().all()

    # Index each chunk for BM25
    for chunk in new_chunks:
        await bm25_service.index_chunk(chunk)

    await session.flush()
    return created
