"""initial_setup_pgvector

Revision ID: 15cf52c90f29
Revises: 
Create Date: 2025-11-06 02:44:48.013965

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '15cf52c90f29'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Install pgvector extension."""
    # Install pgvector extension for vector similarity search
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')


def downgrade() -> None:
    """Downgrade schema - Remove pgvector extension."""
    # Remove pgvector extension
    op.execute('DROP EXTENSION IF EXISTS vector')
