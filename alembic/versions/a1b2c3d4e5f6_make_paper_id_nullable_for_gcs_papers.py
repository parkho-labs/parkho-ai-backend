"""make paper_id nullable for gcs papers

Revision ID: a1b2c3d4e5f6
Revises: 19482b1b5a4b
Create Date: 2025-12-23 15:17:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '19482b1b5a4b'
branch_labels = None
depends_on = None


def upgrade():
    # Make paper_id nullable to support GCS-only papers
    op.alter_column('user_attempts', 'paper_id',
               existing_type=sa.INTEGER(),
               nullable=True)


def downgrade():
    # Revert paper_id to NOT NULL
    op.alter_column('user_attempts', 'paper_id',
               existing_type=sa.INTEGER(),
               nullable=False)
