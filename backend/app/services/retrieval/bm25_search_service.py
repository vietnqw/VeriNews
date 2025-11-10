"""
BM25 Keyword Search Service

Provides BM25-based full-text search using PostgreSQL's ts_rank_cd and Vietnamese tokenization.
"""

from typing import List
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.core.logging import get_logger
from app.models.article_chunk import ArticleChunk
from app.services.retrieval.vietnamese_processor import tokenize_for_search

logger = get_logger(__name__)


class ChunkSearchResult:
    """Result from chunk search"""

    def __init__(
        self,
        chunk_id: UUID,
        chunk_text: str,
        chunk_index: int,
        article_id: UUID,
        article_title: str | None,
        source_name: str | None,
        score: float,
    ):
        self.chunk_id = chunk_id
        self.chunk_text = chunk_text
        self.chunk_index = chunk_index
        self.article_id = article_id
        self.article_title = article_title
        self.source_name = source_name
        self.score = score

    def __repr__(self) -> str:
        return f"ChunkSearchResult(chunk_id={self.chunk_id}, article_id={self.article_id}, score={self.score:.4f})"


class BM25SearchService:
    """
    BM25-based keyword search using PostgreSQL full-text search.

    Uses Vietnamese-aware tokenization for better compound word handling.
    Implements BM25-like ranking using PostgreSQL's ts_rank_cd function.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.top_k = settings.retrieval.bm25_search.top_k

    async def index_chunk(self, chunk: ArticleChunk) -> None:
        """
        Generate and store search_vector for a chunk.

        This is called when creating or updating chunks to populate the tsvector column.

        Args:
            chunk: ArticleChunk to index
        """
        from app.services.retrieval.vietnamese_processor import tokenize_vietnamese

        # Tokenize the chunk text
        tokenized = await tokenize_vietnamese(chunk.chunk_text)

        # Update the search_vector using PostgreSQL's to_tsvector
        # Using 'simple' configuration to avoid English stemming
        stmt = text(
            "UPDATE article_chunks "
            "SET search_vector = to_tsvector('simple', :tokenized) "
            "WHERE id = :chunk_id"
        ).bindparams(tokenized=tokenized, chunk_id=chunk.id)

        await self.session.execute(stmt)
        await self.session.commit()

        logger.debug(f"Indexed chunk {chunk.id} for BM25 search")

    async def search(
        self, query: str, top_k: int | None = None
    ) -> List[ChunkSearchResult]:
        """
        Search for chunks using BM25-like full-text search.

        Args:
            query: Search query (Vietnamese text)
            top_k: Number of results to return (defaults to config value)

        Returns:
            List of ChunkSearchResult ordered by relevance score (highest first)
        """
        if top_k is None:
            top_k = self.top_k

        # Tokenize the query for tsquery
        tokenized_query = await tokenize_for_search(query)

        # Build the query using ts_rank_cd for BM25-like ranking
        # ts_rank_cd uses cover density ranking, similar to BM25
        stmt = (
            select(
                ArticleChunk.id,
                ArticleChunk.chunk_text,
                ArticleChunk.chunk_index,
                ArticleChunk.article_id,
                ArticleChunk.article_title,
                ArticleChunk.source_name,
                func.ts_rank_cd(
                    ArticleChunk.search_vector,
                    func.to_tsquery("simple", tokenized_query),
                ).label("score"),
            )
            .where(
                ArticleChunk.search_vector.op("@@")(
                    func.to_tsquery("simple", tokenized_query)
                )
            )
            .order_by(text("score DESC"))
            .limit(top_k)
        )

        result = await self.session.execute(stmt)
        rows = result.all()

        results = [
            ChunkSearchResult(
                chunk_id=row.id,
                chunk_text=row.chunk_text,
                chunk_index=row.chunk_index,
                article_id=row.article_id,
                article_title=row.article_title,
                source_name=row.source_name,
                score=float(row.score),
            )
            for row in rows
        ]

        logger.info(
            f"BM25 search for '{query[:50]}...' returned {len(results)} results"
        )

        return results

    async def batch_index_chunks(
        self, chunk_ids: List[UUID], batch_size: int = 100
    ) -> int:
        """
        Index multiple chunks in batches.

        Args:
            chunk_ids: List of chunk IDs to index
            batch_size: Number of chunks to process per batch

        Returns:
            Number of chunks indexed
        """
        from app.services.retrieval.vietnamese_processor import tokenize_vietnamese

        indexed_count = 0

        # Process in batches
        for i in range(0, len(chunk_ids), batch_size):
            batch_chunk_ids = chunk_ids[i : i + batch_size]

            # Fetch chunks
            stmt = select(ArticleChunk).where(ArticleChunk.id.in_(batch_chunk_ids))
            result = await self.session.execute(stmt)
            chunks = result.scalars().all()

            # Tokenize and update each chunk
            for chunk in chunks:
                tokenized = await tokenize_vietnamese(chunk.chunk_text)

                update_stmt = text(
                    "UPDATE article_chunks "
                    "SET search_vector = to_tsvector('simple', :tokenized) "
                    "WHERE id = :chunk_id"
                ).bindparams(tokenized=tokenized, chunk_id=chunk.id)

                await self.session.execute(update_stmt)
                indexed_count += 1

            # Commit the batch
            await self.session.commit()

            logger.info(f"Indexed batch {i // batch_size + 1}: {len(chunks)} chunks")

        logger.info(f"Batch indexing complete: {indexed_count} chunks indexed")
        return indexed_count
