"""add_image_fields_to_news_articles

Revision ID: 3ba908b50db5
Revises: f6259a90055e
Create Date: 2026-01-08 00:40:38.306711

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3ba908b50db5'
down_revision: Union[str, Sequence[str], None] = 'f6259a90055e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add image fields to news_articles table."""
    op.add_column('news_articles', sa.Column('featured_image_url', sa.String(length=1000), nullable=True))
    op.add_column('news_articles', sa.Column('thumbnail_url', sa.String(length=1000), nullable=True))
    op.add_column('news_articles', sa.Column('image_caption', sa.String(length=500), nullable=True))
    op.add_column('news_articles', sa.Column('image_alt_text', sa.String(length=200), nullable=True))


def downgrade() -> None:
    """Remove image fields from news_articles table."""
    op.drop_column('news_articles', 'image_alt_text')
    op.drop_column('news_articles', 'image_caption')
    op.drop_column('news_articles', 'thumbnail_url')
    op.drop_column('news_articles', 'featured_image_url')
