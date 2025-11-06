"""
Base Service Classes

Provides common functionality for service layer classes.
"""

from typing import Generic, Optional, TypeVar, Type, List
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.base import Base
from app.services.exceptions import NotFoundError, DuplicateError


# Generic type for database models
ModelType = TypeVar("ModelType", bound=Base)


class BaseService(Generic[ModelType]):
    """
    Base service class providing common CRUD operations.

    Generic type ModelType should be a SQLAlchemy model inheriting from Base.
    """

    def __init__(self, model: Type[ModelType]):
        """
        Initialize base service with model class.

        Args:
            model: SQLAlchemy model class
        """
        self.model = model
        self.model_name = model.__name__

    async def get_by_id(
        self, session: AsyncSession, id: uuid.UUID
    ) -> Optional[ModelType]:
        """
        Get a single record by ID.

        Args:
            session: Database session
            id: UUID of the record

        Returns:
            Model instance if found, None otherwise
        """
        result = await session.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()

    async def get_by_id_or_raise(
        self, session: AsyncSession, id: uuid.UUID
    ) -> ModelType:
        """
        Get a single record by ID or raise NotFoundError.

        Args:
            session: Database session
            id: UUID of the record

        Returns:
            Model instance

        Raises:
            NotFoundError: If record not found
        """
        instance = await self.get_by_id(session, id)
        if instance is None:
            raise NotFoundError(self.model_name, str(id))
        return instance

    async def list_all(self, session: AsyncSession) -> List[ModelType]:
        """
        List all records.

        Args:
            session: Database session

        Returns:
            List of all model instances
        """
        result = await session.execute(select(self.model))
        return list(result.scalars().all())

    async def create(self, session: AsyncSession, **kwargs) -> ModelType:
        """
        Create a new record.

        Args:
            session: Database session
            **kwargs: Model fields

        Returns:
            Created model instance

        Raises:
            DuplicateError: If unique constraint violated
        """
        instance = self.model(**kwargs)
        session.add(instance)
        try:
            await session.flush()
        except IntegrityError as e:
            await session.rollback()
            # Try to extract field name from error message
            field = "id"  # Default
            if "unique constraint" in str(e).lower():
                # Parse constraint name if possible
                pass
            raise DuplicateError(
                self.model_name, field, str(kwargs.get(field, "unknown"))
            )
        return instance

    async def delete(self, session: AsyncSession, id: uuid.UUID) -> bool:
        """
        Delete a record by ID.

        Args:
            session: Database session
            id: UUID of the record to delete

        Returns:
            True if deleted, False if not found
        """
        instance = await self.get_by_id(session, id)
        if instance:
            await session.delete(instance)
            await session.flush()
            return True
        return False

    async def update(
        self, session: AsyncSession, id: uuid.UUID, **kwargs
    ) -> Optional[ModelType]:
        """
        Update a record by ID.

        Args:
            session: Database session
            id: UUID of the record
            **kwargs: Fields to update

        Returns:
            Updated model instance if found, None otherwise
        """
        instance = await self.get_by_id(session, id)
        if not instance:
            return None

        for key, value in kwargs.items():
            if value is not None and hasattr(instance, key):
                setattr(instance, key, value)

        await session.flush()
        return instance
