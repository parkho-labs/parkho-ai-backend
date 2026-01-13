"""add_news_articles_table_with_rag_tracking

Revision ID: f6259a90055e
Revises: e9f8a7b6c5d4
Create Date: 2026-01-04 23:01:07.055652

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f6259a90055e'
down_revision: Union[str, Sequence[str], None] = 'e9f8a7b6c5d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create news_articles table with RAG tracking fields."""
    op.create_table('news_articles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('url', sa.String(length=1000), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('source', sa.String(length=200), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('full_content', sa.Text(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('keywords', sa.JSON(), nullable=True),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('fetched_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('rag_document_id', sa.String(length=255), nullable=True),
        sa.Column('rag_indexed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('url')
    )

    # Create indexes for better performance
    op.create_index('idx_news_articles_source', 'news_articles', ['source'])
    op.create_index('idx_news_articles_category', 'news_articles', ['category'])
    op.create_index('idx_news_articles_published_at', 'news_articles', ['published_at'])
    op.create_index('idx_news_articles_rag_document_id', 'news_articles', ['rag_document_id'])


def downgrade() -> None:
    """Drop news_articles table and indexes."""
    op.drop_index('idx_news_articles_rag_document_id', 'news_articles')
    op.drop_index('idx_news_articles_published_at', 'news_articles')
    op.drop_index('idx_news_articles_category', 'news_articles')
    op.drop_index('idx_news_articles_source', 'news_articles')
    op.drop_table('news_articles')
