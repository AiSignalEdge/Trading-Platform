"""Add scheduled_jobs table for APScheduler-backed job scheduling.

Revision ID: 001_add_scheduled_jobs
Revises:
Create Date: 2025-05-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = '001_add_scheduled_jobs'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'scheduled_jobs',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('job_type', sa.String(), nullable=False),
        sa.Column('payload', JSONB(), nullable=False, default=dict),
        sa.Column('trigger_type', sa.String(), nullable=False),
        sa.Column('trigger_config', JSONB(), nullable=False, default=dict),
        sa.Column('enabled', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('next_run', sa.DateTime(), nullable=True),
        sa.Column('last_run', sa.DateTime(), nullable=True),
        sa.Column('last_status', sa.String(), nullable=True),
        sa.Column('run_count', sa.Integer(), default=0),
        sa.Column('description', sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('scheduled_jobs')