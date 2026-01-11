"""Add is_rag_indexed field to news_articles

Revision ID: add_is_rag_indexed_field
Revises: 3ba908b50db5
Create Date: 2026-01-09 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_is_rag_indexed_field'
down_revision = '3ba908b50db5'
branch_labels = None
depends_on = None


def upgrade():
    """Add is_rag_indexed boolean field to news_articles table"""
    # Add the new column
    op.add_column('news_articles', sa.Column('is_rag_indexed', sa.Boolean(), nullable=True, default=False))

    # Update existing records: set is_rag_indexed=True where rag_document_id is not null
    op.execute("""
        UPDATE news_articles
        SET is_rag_indexed = CASE
            WHEN rag_document_id IS NOT NULL AND rag_document_id != '' THEN true
            ELSE false
        END
    """)

    # Set the column to not nullable with default False
    op.alter_column('news_articles', 'is_rag_indexed', nullable=False, server_default='false')


def downgrade():
    """Remove is_rag_indexed field from news_articles table"""
    op.drop_column('news_articles', 'is_rag_indexed')