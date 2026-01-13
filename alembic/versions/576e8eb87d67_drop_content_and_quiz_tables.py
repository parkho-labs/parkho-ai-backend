"""drop_content_and_quiz_tables

Revision ID: 576e8eb87d67
Revises: db1375176257
Create Date: 2025-12-24 22:31:52.235924

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '576e8eb87d67'
down_revision: Union[str, Sequence[str], None] = 'db1375176257'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop content_jobs and quiz_questions tables as these APIs are being removed."""
    # Drop quiz_questions first due to foreign key dependency
    op.drop_table('quiz_questions')
    # Then drop content_jobs
    op.drop_table('content_jobs')


def downgrade() -> None:
    """Recreate content_jobs and quiz_questions tables."""
    # Recreate content_jobs table first
    op.create_table('content_jobs',
        sa.Column('id', sa.INTEGER(), nullable=False),
        sa.Column('user_id', sa.INTEGER(), nullable=False),
        sa.Column('status', sa.VARCHAR(length=20), nullable=False),
        sa.Column('progress', sa.INTEGER(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False),
        sa.Column('completed_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('input_config', sa.JSON(), nullable=True),
        sa.Column('output_config', sa.JSON(), nullable=True),
        sa.Column('title', sa.VARCHAR(length=255), nullable=True),
        sa.Column('error_message', sa.TEXT(), nullable=True),
        sa.Column('collection_name', sa.VARCHAR(length=255), nullable=True),
        sa.Column('should_add_to_collection', sa.BOOLEAN(), nullable=True),
        sa.Column('rag_context_used', sa.TEXT(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Then recreate quiz_questions table
    op.create_table('quiz_questions',
        sa.Column('id', sa.INTEGER(), nullable=False),
        sa.Column('job_id', sa.INTEGER(), nullable=False),
        sa.Column('question_id', sa.VARCHAR(length=50), nullable=False),
        sa.Column('question', sa.TEXT(), nullable=False),
        sa.Column('type', sa.VARCHAR(length=50), nullable=False),
        sa.Column('answer_config', sa.JSON(), nullable=True),
        sa.Column('context', sa.TEXT(), nullable=True),
        sa.Column('max_score', sa.INTEGER(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False),
        sa.Column('question_metadata', sa.JSON(), nullable=True),
        sa.Column('submitted', sa.BOOLEAN(), nullable=True),
        sa.Column('submitted_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('user_responses', sa.JSON(), nullable=True),
        sa.Column('score', sa.INTEGER(), nullable=True),
        sa.ForeignKeyConstraint(['job_id'], ['content_jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
