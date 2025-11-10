"""
Unit tests for News Source Repository.

Tests CRUD operations and custom methods for NewsSource model.
Uses in-memory SQLite database for fast, isolated testing.
"""

import pytest
import uuid
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.news_source import NewsSource
from app.models.rss_feed import RssFeed
from app.services.repository.news_source_repository import NewsSourceRepository
from app.services.exceptions import NotFoundError, DuplicateError


@pytest.mark.unit
class TestNewsSourceRepository:
    """Unit tests for NewsSourceRepository."""

    @pytest.fixture
    async def db_session(self):
        """Create test database session with only necessary tables."""
        # Create async engine with in-memory SQLite
        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False,
        )

        # Create only the tables we need (NewsSource and RssFeed)
        async with engine.begin() as conn:
            await conn.run_sync(NewsSource.__table__.create)
            await conn.run_sync(RssFeed.__table__.create)

        # Create session
        async_session_maker = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        async with async_session_maker() as session:
            yield session
            await session.rollback()

        # Cleanup
        async with engine.begin() as conn:
            await conn.run_sync(NewsSource.__table__.drop)
            await conn.run_sync(RssFeed.__table__.drop)
        await engine.dispose()

    @pytest.fixture
    def repository(self):
        """Create repository instance."""
        return NewsSourceRepository()

    @pytest.mark.asyncio
    async def test_create_news_source(self, db_session, repository):
        """Test creating a news source."""
        source = await repository.create(
            db_session,
            name="VnExpress",
            base_url="https://vnexpress.net",
        )

        assert source.id is not None
        assert source.name == "VnExpress"
        assert source.base_url == "https://vnexpress.net"
        assert source.created_at is not None

    @pytest.mark.asyncio
    async def test_get_by_id_exists(self, db_session, repository):
        """Test getting a news source by ID when it exists."""
        # Create source
        source = await repository.create(
            db_session,
            name="VnExpress",
            base_url="https://vnexpress.net",
        )
        await db_session.commit()

        # Get by ID
        retrieved = await repository.get_by_id(db_session, source.id)

        assert retrieved is not None
        assert retrieved.id == source.id
        assert retrieved.name == "VnExpress"

    @pytest.mark.asyncio
    async def test_get_by_id_not_exists(self, db_session, repository):
        """Test getting a news source by ID when it doesn't exist."""
        non_existent_id = uuid.uuid4()

        result = await repository.get_by_id(db_session, non_existent_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_id_or_raise_exists(self, db_session, repository):
        """Test get_by_id_or_raise when source exists."""
        source = await repository.create(
            db_session,
            name="VnExpress",
            base_url="https://vnexpress.net",
        )
        await db_session.commit()

        retrieved = await repository.get_by_id_or_raise(db_session, source.id)

        assert retrieved.id == source.id
        assert retrieved.name == "VnExpress"

    @pytest.mark.asyncio
    async def test_get_by_id_or_raise_not_exists(self, db_session, repository):
        """Test get_by_id_or_raise raises NotFoundError when source doesn't exist."""
        non_existent_id = uuid.uuid4()

        with pytest.raises(NotFoundError) as exc_info:
            await repository.get_by_id_or_raise(db_session, non_existent_id)

        assert "NewsSource" in str(exc_info.value)
        assert str(non_existent_id) in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_by_name_exists(self, db_session, repository):
        """Test getting a news source by name when it exists."""
        await repository.create(
            db_session,
            name="VnExpress",
            base_url="https://vnexpress.net",
        )
        await db_session.commit()

        source = await repository.get_by_name(db_session, "VnExpress")

        assert source is not None
        assert source.name == "VnExpress"
        assert source.base_url == "https://vnexpress.net"

    @pytest.mark.asyncio
    async def test_get_by_name_not_exists(self, db_session, repository):
        """Test getting a news source by name when it doesn't exist."""
        result = await repository.get_by_name(db_session, "NonExistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_name_case_sensitive(self, db_session, repository):
        """Test that get_by_name is case-sensitive."""
        await repository.create(
            db_session,
            name="VnExpress",
            base_url="https://vnexpress.net",
        )
        await db_session.commit()

        # Different case should not match
        result = await repository.get_by_name(db_session, "vnexpress")

        assert result is None

    @pytest.mark.asyncio
    async def test_list_all_empty(self, db_session, repository):
        """Test listing all sources when database is empty."""
        sources = await repository.list_all(db_session)

        assert sources == []

    @pytest.mark.asyncio
    async def test_list_all_multiple(self, db_session, repository):
        """Test listing all sources with multiple sources."""
        # Create multiple sources
        await repository.create(
            db_session,
            name="VnExpress",
            base_url="https://vnexpress.net",
        )
        await repository.create(
            db_session,
            name="Tuổi Trẻ",
            base_url="https://tuoitre.vn",
        )
        await repository.create(
            db_session,
            name="Thanh Niên",
            base_url="https://thanhnien.vn",
        )
        await db_session.commit()

        sources = await repository.list_all(db_session)

        assert len(sources) == 3
        names = {source.name for source in sources}
        assert names == {"VnExpress", "Tuổi Trẻ", "Thanh Niên"}

    @pytest.mark.asyncio
    async def test_update_news_source(self, db_session, repository):
        """Test updating a news source."""
        source = await repository.create(
            db_session,
            name="VnExpress",
            base_url="https://vnexpress.net",
        )
        await db_session.commit()

        # Update base_url
        updated = await repository.update(
            db_session,
            source.id,
            base_url="https://new.vnexpress.net",
        )
        await db_session.commit()

        assert updated is not None
        assert updated.id == source.id
        assert updated.base_url == "https://new.vnexpress.net"
        assert updated.name == "VnExpress"  # Name unchanged

    @pytest.mark.asyncio
    async def test_update_non_existent(self, db_session, repository):
        """Test updating a non-existent news source returns None."""
        non_existent_id = uuid.uuid4()

        result = await repository.update(
            db_session,
            non_existent_id,
            base_url="https://example.com",
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_news_source(self, db_session, repository):
        """Test deleting a news source."""
        source = await repository.create(
            db_session,
            name="VnExpress",
            base_url="https://vnexpress.net",
        )
        await db_session.commit()

        # Delete
        deleted = await repository.delete(db_session, source.id)
        await db_session.commit()

        assert deleted is True

        # Verify deletion
        result = await repository.get_by_id(db_session, source.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_non_existent(self, db_session, repository):
        """Test deleting a non-existent news source returns False."""
        non_existent_id = uuid.uuid4()

        result = await repository.delete(db_session, non_existent_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_get_or_create_new(self, db_session, repository):
        """Test get_or_create when source doesn't exist (creates new)."""
        source, created = await repository.get_or_create(
            db_session,
            name="VnExpress",
            base_url="https://vnexpress.net",
        )

        assert created is True
        assert source.name == "VnExpress"
        assert source.base_url == "https://vnexpress.net"
        assert source.id is not None

    @pytest.mark.asyncio
    async def test_get_or_create_existing(self, db_session, repository):
        """Test get_or_create when source exists (returns existing)."""
        # Create initial source
        existing = await repository.create(
            db_session,
            name="VnExpress",
            base_url="https://vnexpress.net",
        )
        await db_session.commit()

        # Try to get_or_create with same name but different URL
        source, created = await repository.get_or_create(
            db_session,
            name="VnExpress",
            base_url="https://different-url.com",
        )

        assert created is False
        assert source.id == existing.id
        assert source.base_url == "https://vnexpress.net"  # Original URL preserved

    @pytest.mark.asyncio
    async def test_create_with_vietnamese_characters(self, db_session, repository):
        """Test creating source with Vietnamese characters."""
        await repository.create(
            db_session,
            name="Tuổi Trẻ Online",
            base_url="https://tuoitre.vn",
        )
        await db_session.commit()

        retrieved = await repository.get_by_name(db_session, "Tuổi Trẻ Online")

        assert retrieved is not None
        assert retrieved.name == "Tuổi Trẻ Online"

    @pytest.mark.asyncio
    async def test_create_duplicate_url_raises_error(self, db_session, repository):
        """Test that creating source with duplicate base_url raises DuplicateError."""
        # base_url has unique constraint
        await repository.create(
            db_session,
            name="Source 1",
            base_url="https://example.com",
        )
        await db_session.commit()

        # Attempt to create with same URL should raise DuplicateError
        with pytest.raises(DuplicateError):
            await repository.create(
                db_session,
                name="Source 2",
                base_url="https://example.com",
            )

    @pytest.mark.asyncio
    async def test_update_preserves_created_at(self, db_session, repository):
        """Test that update doesn't change created_at timestamp."""
        source = await repository.create(
            db_session,
            name="VnExpress",
            base_url="https://vnexpress.net",
        )
        await db_session.commit()

        original_created_at = source.created_at

        # Update and wait a bit
        import asyncio

        await asyncio.sleep(0.01)
        await repository.update(
            db_session,
            source.id,
            base_url="https://new-url.com",
        )
        await db_session.commit()

        # Refresh to get latest data
        await db_session.refresh(source)

        assert source.created_at == original_created_at

    @pytest.mark.asyncio
    async def test_create_with_empty_name(self, db_session, repository):
        """Test creating source with empty name."""
        # Empty string should be allowed (validation happens at API layer)
        source = await repository.create(
            db_session,
            name="",
            base_url="https://example.com",
        )

        assert source.name == ""
