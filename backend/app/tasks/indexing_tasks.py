"""
Indexing Tasks

Background tasks for indexing article chunks for BM25 search.
"""

from uuid import UUID

from celery import shared_task
from sqlalchemy import select

from app.config.database import async_session_maker
from app.core.logging import get_logger
from app.models.article_chunk import ArticleChunk
from app.services.retrieval.bm25_search_service import BM25SearchService

logger = get_logger(__name__)


@shared_task(
    bind=True,
    name="indexing.reindex_all_chunks",
    max_retries=3,
    default_retry_delay=60,
)
def reindex_all_chunks_for_bm25(self, batch_size: int = 100):
    """
    Reindex all existing ArticleChunks for BM25 search.

    This task is run once after deploying the BM25 search feature
    to populate the search_vector column for all existing chunks.

    Args:
        batch_size: Number of chunks to process per batch
    """
    import asyncio

    async def _reindex():
        try:
            async with async_session_maker() as session:
                # Get all chunk IDs
                stmt = select(ArticleChunk.id)
                result = await session.execute(stmt)
                chunk_ids = [row[0] for row in result.all()]

                total_chunks = len(chunk_ids)
                logger.info(f"Starting BM25 reindexing for {total_chunks} chunks")

                if total_chunks == 0:
                    logger.info("No chunks to index")
                    return {"status": "success", "indexed_count": 0}

                # Create BM25 service and batch index
                bm25_service = BM25SearchService(session)
                indexed_count = await bm25_service.batch_index_chunks(
                    chunk_ids, batch_size=batch_size
                )

                logger.info(
                    f"BM25 reindexing complete: {indexed_count}/{total_chunks} chunks"
                )

                return {
                    "status": "success",
                    "indexed_count": indexed_count,
                    "total_chunks": total_chunks,
                }

        except Exception as e:
            logger.error(f"Error during BM25 reindexing: {e}")
            raise self.retry(exc=e)

    # Run the async function
    return asyncio.run(_reindex())


@shared_task(
    bind=True,
    name="indexing.index_chunk",
    max_retries=3,
    default_retry_delay=10,
)
def index_chunk_for_bm25(self, chunk_id: str):
    """
    Index a single ArticleChunk for BM25 search.

    This task is called when a new chunk is created.

    Args:
        chunk_id: UUID of the chunk to index (as string)
    """
    import asyncio

    async def _index():
        try:
            async with async_session_maker() as session:
                # Fetch the chunk
                stmt = select(ArticleChunk).where(ArticleChunk.id == UUID(chunk_id))
                result = await session.execute(stmt)
                chunk = result.scalar_one_or_none()

                if not chunk:
                    logger.warning(f"Chunk {chunk_id} not found for indexing")
                    return {"status": "not_found", "chunk_id": chunk_id}

                # Index the chunk
                bm25_service = BM25SearchService(session)
                await bm25_service.index_chunk(chunk)

                logger.info(f"Indexed chunk {chunk_id} for BM25 search")

                return {"status": "success", "chunk_id": chunk_id}

        except Exception as e:
            logger.error(f"Error indexing chunk {chunk_id}: {e}")
            raise self.retry(exc=e)

    return asyncio.run(_index())


@shared_task(
    bind=True,
    name="indexing.update_denormalized_fields",
    max_retries=3,
    default_retry_delay=60,
)
def update_denormalized_fields_for_all_chunks(self, batch_size: int = 100):
    """
    Update denormalized fields (article_title, source_name, published_at) for all chunks.

    This is a one-time task to populate denormalized fields for existing chunks.

    Args:
        batch_size: Number of chunks to process per batch
    """
    import asyncio

    async def _update():
        try:
            async with async_session_maker() as session:
                from sqlalchemy import update
                from sqlalchemy.orm import joinedload

                # Get all chunks with their articles (using joinedload for efficiency)
                stmt = (
                    select(ArticleChunk)
                    .options(
                        joinedload(ArticleChunk.article)
                        .joinedload(
                            ArticleChunk.article.property.mapper.class_.rss_feed
                        )
                        .joinedload(
                            ArticleChunk.article.property.mapper.class_.rss_feed.property.mapper.class_.news_source
                        )
                    )
                    .order_by(ArticleChunk.id)
                )

                result = await session.execute(stmt)
                chunks = result.scalars().all()

                total_chunks = len(chunks)
                logger.info(
                    f"Starting denormalized field updates for {total_chunks} chunks"
                )

                if total_chunks == 0:
                    logger.info("No chunks to update")
                    return {"status": "success", "updated_count": 0}

                updated_count = 0
                batch_count = 0

                for i, chunk in enumerate(chunks):
                    # Update denormalized fields
                    update_stmt = (
                        update(ArticleChunk)
                        .where(ArticleChunk.id == chunk.id)
                        .values(
                            article_title=chunk.article.title,
                            source_name=chunk.article.rss_feed.news_source.name,
                            published_at=chunk.article.published_at,
                        )
                    )

                    await session.execute(update_stmt)
                    updated_count += 1

                    # Commit in batches
                    if (i + 1) % batch_size == 0:
                        await session.commit()
                        batch_count += 1
                        logger.info(
                            f"Updated batch {batch_count}: {updated_count} chunks"
                        )

                # Final commit
                await session.commit()

                logger.info(
                    f"Denormalized field updates complete: {updated_count}/{total_chunks} chunks"
                )

                return {
                    "status": "success",
                    "updated_count": updated_count,
                    "total_chunks": total_chunks,
                }

        except Exception as e:
            logger.error(f"Error updating denormalized fields: {e}")
            raise self.retry(exc=e)

    return asyncio.run(_update())
